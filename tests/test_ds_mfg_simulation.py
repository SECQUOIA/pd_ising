"""Tests for the renewed Lomustine PharmaPy superstructure simulation workflow.

Verifies:
1. Path-independent import and execution of ``ds-mfg/simulation/code`` modules
   (``generating_structures``, ``config_mapping``, ``helper``, ``data_organizer``,
   ``nomad_opt``) from outside ``ds-mfg/simulation/code/``.
2. Completeness and schema of the restored ``ds-mfg/simulation/data`` files
   (``compounds_lomustine.json``, ``bounds.json``, ``optimal_points_2.json``,
   ``optimal_points_2_PFR.json``, ``optimal_mass_size_2_fixed.json``, and
   ``obj_mass_prod_crys/x_input_sorted.csv``).
3. Superstructure graph generation (``make_graph``), decision-variable bounds
   and scaling (``get_input_dictionary``, ``get_median_inputs``, ``translate_scale``),
   and constraint/solubility helpers (``solub_fn``, ``path_constraint``).
4. End-to-end PharmaPy flowsheet simulation across representative hybrid
   batch/continuous Lomustine superstructure configurations when ``PharmaPy``
   and ``assimulo`` are installed.
"""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = PROJECT_ROOT / "ds-mfg" / "simulation"
CODE_DIR = SIM_DIR / "code"
DATA_DIR = SIM_DIR / "data"

if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

import config_mapping  # noqa: E402
import data_organizer  # noqa: E402
import generating_structures as gs  # noqa: E402
import helper  # noqa: E402
import nomad_opt  # noqa: E402

HAS_PHARMAPY_ASSIMULO = (
    importlib.util.find_spec("PharmaPy") is not None
    and importlib.util.find_spec("assimulo") is not None
)


def test_simulation_data_files_exist_and_have_expected_schema() -> None:
    """Verify that all required Lomustine simulation data files are present and valid."""
    compounds_path = DATA_DIR / "compounds_lomustine.json"
    bounds_path = DATA_DIR / "bounds.json"
    opt_points_path = DATA_DIR / "optimal_points_2.json"
    opt_pfr_path = DATA_DIR / "optimal_points_2_PFR.json"
    opt_mass_size_path = DATA_DIR / "optimal_mass_size_2_fixed.json"
    x_input_sorted_path = DATA_DIR / "obj_mass_prod_crys" / "x_input_sorted.csv"

    for required_path in (
        compounds_path,
        bounds_path,
        opt_points_path,
        opt_pfr_path,
        opt_mass_size_path,
        x_input_sorted_path,
    ):
        assert required_path.is_file(), f"Missing required simulation data file: {required_path}"

    compounds = json.loads(compounds_path.read_text(encoding="utf-8"))
    expected_species = ["ISO", "CHA", "interm", "TBN", "lom", "TBA", "SUB1", "THF", "C7"]
    assert list(compounds.keys()) == expected_species
    for species, props in compounds.items():
        assert props["mw"] > 0.0, f"Invalid molecular weight for {species}"
        assert "delta_hvap" in props and "tref_hvap" in props

    bounds = json.loads(bounds_path.read_text(encoding="utf-8"))
    assert set(bounds.keys()) == {"R01", "MIX01", "R02", "MIX02", "VAP01", "CR01", "F01"}

    df_sorted = pd.read_csv(x_input_sorted_path)
    assert list(df_sorted.columns) == ["Combination", "x"]
    assert len(df_sorted) == 35


def test_corrected_model_tables_and_discrete_ip_rankings() -> None:
    """Verify the corrected-model PharmaPy tables, PyNomad results, and 36-solution IP rankings."""
    import ast
    import generate_corrected_model_tables as gcmt

    corr_sim_dir = DATA_DIR / "corrected_model_pharmapy_current"
    corr_dip_data = PROJECT_ROOT / "ds-mfg" / "discrete_ip" / "data" / "corrected_model_pharmapy_current"
    corr_dip_res = PROJECT_ROOT / "ds-mfg" / "discrete_ip" / "result_corrected_model"

    bundle = json.loads(
        (corr_sim_dir / "all40_corrected_model_evaluation_and_nomad.json").read_text(encoding="utf-8")
    )
    assert len(bundle) == 40
    for idx in range(40):
        entry = bundle[str(idx)]
        base = entry["baseline"]
        opt = entry["optimized"]
        assert base["success"] and opt["success"]
        # PyNomad minimization objective must be <= baseline objective at optimal_points_2
        assert opt["obj_val"] <= base["obj_val"] + 1e-12
        assert opt["g1_solub_path_con"] <= 1e-9

    # Verify all 36 two-reactor configurations are present (including #10 batch-PFR-batch-cont2)
    df_nomad_sum = pd.read_csv(corr_sim_dir / "run_objmassprodcrys_sum_corrected_nomad.csv")
    assert len(df_nomad_sum) == 36
    assert not df_nomad_sum["Best Objective Value"].isna().any()
    assert not df_nomad_sum["Total_CAPEX"].isna().any()
    assert (df_nomad_sum["Best Objective Value"] > -1000.0).all()

    # Verify exact empirical-mean derivation of legacy ssopt_gen_1.csv from legacy x_input_with_total_capex.csv
    legacy_capex_df = pd.read_csv(DATA_DIR / "obj_mass_prod_crys" / "x_input_with_total_capex.csv")
    legacy_records = [
        {
            "layout": ast.literal_eval(row["Combination"].replace("_ ", ", ")),
            "equip_sizes": ast.literal_eval(row["CAPEX"]),
        }
        for _, row in legacy_capex_df.iterrows()
    ]
    reconstructed_legacy_ssopt = gcmt.compute_ssopt_table(legacy_records, use_turton_musd=False)
    orig_ssopt = pd.read_csv(PROJECT_ROOT / "ds-mfg" / "discrete_ip" / "data" / "ssopt_gen_1.csv")
    np.testing.assert_allclose(
        reconstructed_legacy_ssopt["Flow Cost"].to_numpy(),
        orig_ssopt["Flow Cost"].to_numpy(),
        atol=1e-3,
    )

    # Verify corrected-model ssopt_gen_1_corrected_nomad.csv and 36-solution discrete IP ranking
    corr_ssopt = pd.read_csv(corr_dip_data / "ssopt_gen_1_corrected_nomad.csv").set_index("Flow")
    assert corr_ssopt.loc["f09", "Flow Cost"] == pytest.approx(6.5652, abs=1e-4)
    assert corr_ssopt.loc["f16", "Flow Cost"] == pytest.approx(5.6054, abs=1e-4)
    assert corr_ssopt.loc["f17", "Flow Cost"] == pytest.approx(6.1587, abs=1e-4)

    ngc_nomad = json.loads(
        (corr_dip_res / "nogoodcuts_corrected_nomad.json").read_text(encoding="utf-8")
    )
    assert len(ngc_nomad) == 36
    ip_objs = [ngc_nomad[str(k)]["ip_obj_value"] for k in range(1, 37)]
    assert all(ip_objs[i] <= ip_objs[i + 1] + 1e-9 for i in range(35))
    assert ngc_nomad["1"]["operating_modes"] == ["batch", "batch", "batch", "batchU"]
    assert ngc_nomad["1"]["ip_obj_value"] == pytest.approx(14.859)
    assert ngc_nomad["1"]["sm_capex"] == pytest.approx(0.860833, rel=1e-4)


def test_valid_combos_and_make_graph_cover_all_40_superstructure_layouts() -> None:
    """Verify the 40 valid superstructure layouts and their connectivity graphs."""
    assert len(gs.valid_combos) == 40
    assert config_mapping.valid_combos == gs.valid_combos

    expected_graphs = {
        ("batch", "batch", "batch", "batchU"): (
            "R01 --> MIX01 --> R02 --> MIX02 --> VAP01 --> CR01 --> F01"
        ),
        ("batch", "batch", "batch", "cont1"): (
            "R01 --> MIX01 --> R02 --> MIX02 --> VAP01 --> BatchToFlow01 --> CR01 --> HOLD01 --> F01"
        ),
        ("batch", "batch", "batch", "cont3"): (
            "R01 --> MIX01 --> R02 --> MIX02 --> VAP01 --> BatchToFlow01 --> "
            "CR01 --> CR02 --> CR03 --> HOLD01 --> F01"
        ),
        ("batch", "CSTR", "batch", "batchU"): (
            "R01 --> MIX01 --> BatchToFlow01 --> R02 --> MIX02 --> HOLD01 --> VAP01 --> CR01 --> F01"
        ),
        ("PFR", "CSTR", "batch", "cont2"): (
            "R01 --> MIX01 --> R02 --> MIX02 --> HOLD01 --> VAP01 --> "
            "BatchToFlow01 --> CR01 --> CR02 --> HOLD02 --> F01"
        ),
        ("Semibatch", "Semibatch", "batch", "batchU"): (
            "R01 --> MIX02 --> VAP01 --> CR01 --> F01"
        ),
        ("Semibatch", "Semibatch", "batch", "cont1"): (
            "R01 --> MIX02 --> VAP01 --> BatchToFlow01 --> CR01 --> HOLD01 --> F01"
        ),
    }
    for layout, expected_graph in expected_graphs.items():
        assert gs.make_graph(layout) == expected_graph


def test_optimal_points_match_decision_variable_dimensions() -> None:
    """Verify that every optimal point vector matches the layout's decision-variable count."""
    all_optimals = gs.load_optimal_points(include_pfr_update=True)
    assert len(all_optimals) == 40

    for idx, layout in enumerate(gs.valid_combos):
        bound_dict = gs.get_input_dictionary(gs.all_vars, layout)
        coords = [float(v) for v in all_optimals[str(idx)]]
        assert len(coords) == len(bound_dict), f"Dimension mismatch at #{idx} {layout}"
        assert all(0.0 <= c <= 1.0 for c in coords), f"Out-of-bounds coordinate at #{idx}"

        medians = gs.get_median_inputs(bound_dict)
        for key, (lb, ub) in bound_dict.items():
            assert medians[key] == pytest.approx(0.5 * (lb + ub))
            assert helper.translate_scale(0.0, [lb, ub]) == pytest.approx(lb)
            assert helper.translate_scale(1.0, [lb, ub]) == pytest.approx(ub)

    assert nomad_opt.layout in gs.valid_combos
    assert len(nomad_opt.X0) == len(nomad_opt.bound_dict)


def test_solubility_and_path_constraint_helpers() -> None:
    """Verify solubility correlation and trapezoidal path-constraint integration."""
    temp_k = np.array([273.15, 298.15])  # [K]
    mole_frac = np.zeros((2, 9))  # [-]
    mole_frac[:, 7] = np.array([0.0, 0.2])  # [-], THF mole fraction
    mole_frac[:, 8] = np.array([1.0, 0.8])  # [-], C7 mole fraction

    solub = helper.solub_fn(temp_k, mole_frac=mole_frac)  # [kg/m**3]
    assert solub.shape == (2,)
    assert np.all(solub > 0.0)
    # Increasing THF mole fraction increases Lomustine solubility by (1 + 6.5 * x_THF)
    solub_zero_thf = helper.solub_fn(298.15, mole_frac=mole_frac[0])  # [kg/m**3]
    assert solub[1] == pytest.approx(solub_zero_thf * (1.0 + 6.5 * 0.2))

    # Path constraint: y <= y_ref everywhere gives zero violation
    time_s = np.linspace(0.0, 100.0, 11)  # [s]
    y_profile = np.full_like(time_s, 10.0)  # [kg/m**3]
    y_ref = np.full_like(time_s, 15.0)  # [kg/m**3]
    assert helper.path_constraint(time_s, y_profile, y_ref=y_ref, sqrt=True) == pytest.approx(0.0)

    # Constant violation of 2.0 [kg/m**3] over 100 [s] -> sqrt(integral(4.0 dt, 0..100)) = 20.0
    y_viol = np.full_like(time_s, 17.0)  # [kg/m**3]
    assert helper.path_constraint(time_s, y_viol, y_ref=y_ref, sqrt=True) == pytest.approx(20.0)


@pytest.mark.skipif(
    not HAS_PHARMAPY_ASSIMULO,
    reason="Requires PharmaPy and Assimulo for dynamic flowsheet integration",
)
@pytest.mark.parametrize(
    ("combo_idx", "expected_mp", "expected_size"),
    [
        # (combo_idx, mass_productivity [kg/s], mean_crystal_size d10 [um])
        (0, 0.00191265, 52.0012),   # ('batch', 'batch', 'batch', 'batchU')
        (1, 0.00141169, 46.9849),   # ('batch', 'batch', 'batch', 'cont1')
        (4, 0.00274235, 65.5259),   # ('batch', 'CSTR', 'batch', 'batchU')
        (29, 0.00320856, 54.3672),  # ('PFR', 'CSTR', 'batch', 'cont1')
        (36, 0.00189054, 55.8826),  # ('Semibatch', 'Semibatch', 'batch', 'batchU')
    ],
)
def test_representative_lomustine_superstructure_flowsheets_solve(
    combo_idx: int,
    expected_mp: float,
    expected_size: float,
) -> None:
    """Solve representative hybrid Lomustine flowsheets on current PharmaPy."""
    all_optimals = gs.load_optimal_points(include_pfr_update=True)
    ref_mass_size = json.loads(
        (DATA_DIR / "optimal_mass_size_2_fixed.json").read_text(encoding="utf-8")
    )

    layout = gs.valid_combos[combo_idx]
    bound_dict = gs.get_input_dictionary(gs.all_vars, layout)
    inputs = deepcopy(bound_dict)
    for var_idx, key in enumerate(inputs.keys()):
        inputs[key] = helper.translate_scale(
            float(all_optimals[str(combo_idx)][var_idx]), bound_dict[key]
        )

    graph = gs.make_graph(layout)
    flowsheet, success = gs.run_flowsheet(
        path=gs.path, inputs=inputs, layout=layout, graph=graph
    )
    assert success, f"Flowsheet #{combo_idx} {layout} failed to solve"

    mass_prod, crystal_size = gs.get_mass_and_size(
        flowsheet, layout=layout, inputs=inputs
    )  # [kg/s], [um]
    assert mass_prod == pytest.approx(expected_mp, rel=1e-4)
    assert crystal_size == pytest.approx(expected_size, rel=1e-4)

    # Also compare against the 2022 optimal_mass_size_2_fixed.json reference
    # (recorded prior to PharmaPy commits 88a7a0e, 8109dd6 [#439], and 87d0bdd [#467]).
    ref_mp, ref_size = ref_mass_size[str(combo_idx)]  # [kg/s], [um]
    assert mass_prod == pytest.approx(ref_mp, rel=0.09)
    assert crystal_size == pytest.approx(ref_size, rel=0.12)

    obj_val = gs.get_objective_value(flowsheet, layout=layout, inputs=inputs)
    assert obj_val == pytest.approx(mass_prod * 6.0e4 + crystal_size)

    total_capex = sum(flowsheet.GetCAPEX().values())  # [$]
    assert np.isfinite(total_capex) and total_capex > 0.0
    cost_obj = gs.get_objective_value_cost(flowsheet, layout=layout, inputs=inputs)
    assert cost_obj == pytest.approx(-1e3 * mass_prod + total_capex)

    g1, g2 = gs.get_constraints_values(flowsheet, layout=layout, inputs=inputs)
    expected_g2 = 0.7 - flowsheet.VAP01.result.x_liq[-1, -1]  # [-]
    assert np.isfinite(g1) and g1 >= 0.0
    assert g2 == pytest.approx(expected_g2)


@pytest.mark.skipif(
    not HAS_PHARMAPY_ASSIMULO,
    reason="Requires PharmaPy and Assimulo for CAPEX extraction",
)
def test_organize_capex_data_extracts_unit_capex(tmp_path: Path) -> None:
    """Verify that organize_capex_data runs and populates CAPEX and Total_CAPEX."""
    subset_csv = tmp_path / "x_input_subset.csv"
    out_csv = tmp_path / "x_input_capex_out.csv"

    full_df = pd.read_csv(DATA_DIR / "obj_mass_prod_crys" / "x_input_sorted.csv")
    full_df.iloc[:2].to_csv(subset_csv, index=False)

    result_df = data_organizer.organize_capex_data(
        input_csv_path=subset_csv,
        output_csv_path=out_csv,
    )
    assert out_csv.is_file()
    assert len(result_df) == 2
    for idx in range(2):
        assert isinstance(result_df.at[idx, "CAPEX"], dict)
        assert result_df.at[idx, "Total_CAPEX"] > 0.0
