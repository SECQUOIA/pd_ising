"""Generate Lomustine superstructure input tables, PyNomad black-box optimization
results, and 36-solution discrete-IP rankings on the corrected current PharmaPy model.

All outputs are written to dedicated ``corrected_model_pharmapy_current/`` and
``result_corrected_model/`` directories so that the legacy 2022-2023 provenance
records in ``ds-mfg/simulation/data/``, ``ds-mfg/discrete_ip/data/ssopt_gen_1.csv``,
and ``ds-mfg/discrete_ip/result_gurobi/`` remain untouched.

Provenance & Model Differences vs. Legacy 2022-2023 PharmaPy
------------------------------------------------------------
Between the original 2022-2023 runs (``PharmaPy`` commit ``04499cc``) and the
corrected current ``PharmaPy`` model (commit ``3194efd``), four upstream bugs
affecting this superstructure were fixed:

1. ``CSTR.material_balance`` residence-time inversion (``PharmaPy`` commit ``88a7a0e``):
   In 2022 ``PharmaPy``, CSTR dilution used an inverted residence time, which allowed
   the legacy NOMAD run in ``obj_mass_prod_crys/x_input_sorted.csv`` to drive
   ``tau_R02 -> 0`` on the 12 ``R02 == 'CSTR'`` configurations (``#04``-``#07``,
   ``#16``-``#19``, ``#28``-``#31``), producing unphysical runaway ``lom``
   concentrations (e.g., ``sm_obj_value = -1541.91`` on ``#28`` and a numerical
   blowup ``-5.016e9`` on ``#06``) and inflating the ``R02 == 'CSTR'`` edge weight
   ``f09`` in ``ssopt_gen_1.csv`` to ``9.717``.
2. ``LiquidPhase`` / ``LiquidStream`` solvent-free concentration closure
   (``PharmaPy`` commit ``8109dd6``, issue ``#439``):
   When ``name_solv='THF'`` and ``mole_conc`` are specified, ``THF`` solvent mole
   fraction is now closed from pure-species liquid molar volumes rather than the
   approximate mixture density.
3. ``DynamicCollector`` liquid species inventory integration
   (``PharmaPy`` commit ``87d0bdd``, issue ``#467``):
   ``DynamicCollector`` (``HOLD01``, ``HOLD02``) now integrates extensive liquid
   molar inventories ``N_j`` [mol] rather than intensive mole fractions.
4. ``DynamicCollector`` slurry holdup volume accounting in ``GetCAPEX()``
   (``PharmaPy`` ``Containers.py``):
   In 2022 ``PharmaPy`` (``04499cc``), ``DynamicCollector`` after a continuous
   ``MSMPR`` crystallizer read ``self.Outlet.vol_slurry``, which defaulted to
   ``1.0`` m^3 on an un-updated ``Slurry`` object, causing every ``HOLD`` tank
   after ``cont1``/``cont2``/``cont3`` to report an identical vessel volume of
   ``1.0 / 0.75 = 1.333333`` m^3 (``f17 = 1.333`` in ``ssopt_gen_1.csv``)
   regardless of throughput. Current ``PharmaPy`` reads ``self.Outlet.vol``
   (the true accumulated liquid + solid slurry volume ``Liquid_1.vol + Solid_1.vol``).
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
SIM_DIR = SCRIPT_DIR.parent
REPO_ROOT = SIM_DIR.parent.parent
SIM_DATA = SIM_DIR / "data"
CORR_SIM_DIR = SIM_DATA / "corrected_model_pharmapy_current"

DIP_DIR = REPO_ROOT / "ds-mfg" / "discrete_ip"
CORR_DIP_DATA = DIP_DIR / "data" / "corrected_model_pharmapy_current"
CORR_DIP_RES = DIP_DIR / "result_corrected_model"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generating_structures import (  # noqa: E402
    all_vars,
    get_constraints_values,
    get_input_dictionary,
    get_mass_and_size,
    get_objective_value,
    get_objective_value_cost,
    load_optimal_points,
    make_graph,
    path,
    run_flowsheet,
    valid_combos,
)
from helper import translate_scale  # noqa: E402

try:
    import PyNomad
except ImportError:  # pragma: no cover - optional for --eval-only mode
    PyNomad = None

try:
    import pyomo.environ as pyo
except ImportError:  # pragma: no cover - optional when Pyomo is absent
    pyo = None


CAPEX_TBL = pd.read_csv(SIM_DATA / "capex_coeff.csv").set_index("Equipment")


def format_combo_legacy(layout: list[str] | tuple[str, ...]) -> str:
    """Format layout tuple as ``('R01'_ 'R02'_ 'VAP01'_ 'CR01')`` for legacy CSVs."""
    inner = "_ ".join(f"'{item}'" for item in layout)
    return f"({inner})"


def compute_turton_capex_usd(
    flowsheet: Any,
    layout: tuple[str, ...],
    sizes: dict[str, float],
) -> dict[str, float]:
    """Compute unit-by-unit Turton bare-module equipment cost [USD] using ``capex_coeff.csv``."""
    rows = []
    for uo_name in sizes.keys():
        if uo_name.startswith("R"):
            r_mode = layout[0] if uo_name == "R01" else layout[1]
            eq_type = "Tubular reactor" if r_mode == "PFR" else "Tank reactor"
        elif uo_name.startswith("HOLD"):
            eq_type = "Holding tank"
        elif uo_name.startswith("VAP"):
            eq_type = "Vaporizer"
        elif uo_name.startswith("CR"):
            eq_type = "Crystallizer"
        elif uo_name.startswith("F"):
            eq_type = "Filter"
        else:
            raise ValueError(f"Unknown unit operation name: {uo_name}")
        rows.append(CAPEX_TBL.loc[eq_type])
    sub = pd.DataFrame(rows)
    cost_dict = flowsheet.GetCAPEX(
        size_equipment=sizes,
        k_vals=sub[["K1", "K2", "K3"]].to_numpy(),
        b_vals=sub[["B1", "B2"]].to_numpy(),
        f_pres=sub["f_pres"].to_numpy(),
        f_mat=sub["f_mat"].to_numpy(),
        min_capacity=sub["A_min"].to_numpy(),
    )
    return {k: float(v) for k, v in cost_dict.items()}


def evaluate_point(combo_idx: int, x_vec: list[float]) -> dict[str, Any]:
    """Evaluate a single normalized decision vector ``x_vec`` in ``[0, 1]^d``."""
    layout = valid_combos[combo_idx]
    graph = make_graph(layout)
    bound_dict = get_input_dictionary(all_vars, layout)
    keys = list(bound_dict.keys())
    inputs = {
        k: translate_scale(float(x_vec[i]), bound_dict[k])
        for i, k in enumerate(keys)
    }
    t0 = time.perf_counter()
    flowsheet, success = run_flowsheet(
        path=path, inputs=inputs, layout=layout, graph=graph
    )
    eval_s = time.perf_counter() - t0
    if not success:
        return {
            "combo_idx": combo_idx,
            "layout": list(layout),
            "success": False,
            "eval_s": float(eval_s),
        }

    mass_prod, crystal_size = get_mass_and_size(
        flowsheet, layout=layout, inputs=inputs
    )  # [kg/s], [um]
    obj_val = -get_objective_value(
        flowsheet, layout=layout, inputs=inputs
    )  # [-], minimization objective -(6e4 * mass_prod + crystal_size)
    cost_obj = get_objective_value_cost(
        flowsheet, layout=layout, inputs=inputs
    )  # [-]
    g1, g2 = get_constraints_values(
        flowsheet, layout=layout, inputs=inputs, include_heptane_constraint=True
    )  # [kg*s**0.5/m**3], [-]
    equip_sizes = {k: float(v) for k, v in flowsheet.GetCAPEX().items()}
    total_equip_size = float(sum(equip_sizes.values()))
    turton_usd = compute_turton_capex_usd(flowsheet, layout, equip_sizes)
    total_turton_usd = float(sum(turton_usd.values()))

    return {
        "combo_idx": combo_idx,
        "layout": list(layout),
        "x": [float(v) for v in x_vec],
        "success": True,
        "eval_s": float(eval_s),
        "mass_prod_kg_s": float(mass_prod),
        "crystal_size_um": float(crystal_size),
        "obj_val": float(obj_val),
        "cost_obj": float(cost_obj),
        "g1_solub_path_con": float(g1),
        "g2_heptane_shortfall": float(g2),
        "equip_sizes": equip_sizes,
        "total_equip_size": total_equip_size,
        "turton_capex_usd": turton_usd,
        "total_turton_capex_usd": total_turton_usd,
    }


def optimize_single_combo(
    combo_idx: int,
    x_init: list[float],
    max_bb_eval: int = 60,
) -> dict[str, Any]:
    """Run baseline evaluation and PyNomad optimization for ``combo_idx``."""
    if PyNomad is None:
        raise ImportError("PyNomad is required for black-box optimization.")

    layout = valid_combos[combo_idx]
    graph = make_graph(layout)
    bound_dict = get_input_dictionary(all_vars, layout)
    keys = list(bound_dict.keys())
    dim = len(keys)

    base_res = evaluate_point(combo_idx, x_init)
    best_state = {
        "x": list(x_init),
        "obj": base_res["obj_val"] if base_res["success"] else 1e20,
        "g1": base_res["g1_solub_path_con"] if base_res["success"] else 1e20,
    }

    def bb(x_nomad: Any) -> int:
        try:
            coords = [float(x_nomad.get_coord(i)) for i in range(dim)]
            inp = {
                k: translate_scale(coords[i], bound_dict[k])
                for i, k in enumerate(keys)
            }
            fs, ok = run_flowsheet(
                path=path, inputs=inp, layout=layout, graph=graph
            )
            if ok:
                obj = float(-get_objective_value(fs, layout=layout, inputs=inp))
                g1_val, g2_val = get_constraints_values(
                    fs,
                    layout=layout,
                    inputs=inp,
                    include_heptane_constraint=False,
                )
                g1_val = float(g1_val)
                g2_val = float(g2_val)
                if np.isfinite(obj) and np.isfinite(g1_val) and g1_val <= 1e-9:
                    if obj < best_state["obj"]:
                        best_state["obj"] = obj
                        best_state["x"] = coords
                        best_state["g1"] = g1_val
            else:
                obj, g1_val, g2_val = 1e20, 1e20, 1e20
            x_nomad.setBBO(f"{obj} {g1_val} {g2_val}".encode("UTF-8"))
        except Exception:
            return 0
        return 1

    params = [
        f"DIMENSION {dim}",
        "BB_OUTPUT_TYPE OBJ PB PB",
        f"MAX_BB_EVAL {max_bb_eval}",
        "DISPLAY_DEGREE 0",
    ]
    t_start = time.perf_counter()
    nomad_out = PyNomad.optimize(
        bb,
        [float(v) for v in x_init],
        [0.0] * dim,
        [1.0] * dim,
        params,
    )
    opt_wall_s = time.perf_counter() - t_start

    x_best = best_state["x"]
    if isinstance(nomad_out, dict) and nomad_out.get("h_single_best", 1.0) <= 1e-9:
        if nomad_out.get("f_single_best", 1e20) <= best_state["obj"]:
            x_best = [float(v) for v in nomad_out["x_single_best"]]

    opt_res = evaluate_point(combo_idx, x_best)
    opt_res["opt_wall_s"] = float(opt_wall_s)
    opt_res["nb_evals"] = int(
        nomad_out.get("nb_evals", max_bb_eval)
        if isinstance(nomad_out, dict)
        else max_bb_eval
    )
    opt_res["nb_iters"] = int(
        nomad_out.get("nb_iters", 0) if isinstance(nomad_out, dict) else 0
    )
    opt_res["stop_reason"] = str(
        nomad_out.get("stop_reason", "") if isinstance(nomad_out, dict) else ""
    )

    return {
        "combo_idx": combo_idx,
        "baseline": base_res,
        "optimized": opt_res,
    }


def compute_ssopt_table(
    records_36: list[dict[str, Any]],
    use_turton_musd: bool = False,
) -> pd.DataFrame:
    """Compute the 19-edge discrete superstructure cost table (``ssopt_gen_1`` schema)."""
    r01: dict[str, list[float]] = {"PFR": [], "CSTR": [], "batch": []}
    hold_r01_r02: list[float] = []
    r02: dict[str, list[float]] = {"PFR": [], "CSTR": [], "batch": []}
    vap: list[float] = []
    cr: dict[str, list[float]] = {
        "cont1": [],
        "cont2": [],
        "cont3": [],
        "batchU": [],
    }
    hold_cr: list[float] = []

    for rec in records_36:
        combo = tuple(rec["layout"])
        cap = rec["turton_capex_usd"] if use_turton_musd else rec["equip_sizes"]
        scale = 1e-6 if use_turton_musd else 1.0
        r01[combo[0]].append(cap["R01"] * scale)
        if combo[0] != "batch" and combo[1] == "batch":
            hold_r01_r02.append(cap["HOLD01"] * scale)
        if combo[1] in ("PFR", "CSTR"):
            r02[combo[1]].append((cap["R02"] + cap["HOLD01"]) * scale)
        else:
            r02["batch"].append(cap["R02"] * scale)
        vap.append(cap["VAP01"] * scale)
        if combo[3] == "batchU":
            cr["batchU"].append(cap["CR01"] * scale)
        elif combo[3] == "cont1":
            cr["cont1"].append(cap["CR01"] * scale)
            hold_cr.append(cap.get("HOLD02", cap.get("HOLD01")) * scale)
        elif combo[3] == "cont2":
            cr["cont2"].append((cap["CR01"] + cap["CR02"]) * scale)
            hold_cr.append(cap.get("HOLD02", cap.get("HOLD01")) * scale)
        elif combo[3] == "cont3":
            cr["cont3"].append(
                (cap["CR01"] + cap["CR02"] + cap["CR03"]) * scale
            )
            hold_cr.append(cap.get("HOLD02", cap.get("HOLD01")) * scale)

    base_df = pd.read_csv(DIP_DIR / "data" / "ssopt_gen_1.csv")
    means = {
        "f00": 0.0,
        "f01": round(float(np.mean(r01["PFR"])), 4),
        "f02": round(float(np.mean(r01["CSTR"])), 4),
        "f03": round(float(np.mean(r01["batch"])), 4),
        "f04": 0.0,
        "f05": 0.0,
        "f06": round(float(np.mean(hold_r01_r02)), 4),
        "f07": 0.0,
        "f08": round(float(np.mean(r02["PFR"])), 4),
        "f09": round(float(np.mean(r02["CSTR"])), 4),
        "f10": round(float(np.mean(r02["batch"])), 4),
        "f11": round(float(np.mean(vap)), 4),
        "f12": 0.0,
        "f13": round(float(np.mean(cr["cont1"])), 4),
        "f14": round(float(np.mean(cr["cont2"])), 4),
        "f15": round(float(np.mean(cr["cont3"])), 4),
        "f16": round(float(np.mean(cr["batchU"])), 4),
        "f17": round(float(np.mean(hold_cr)), 4),
        "f18": 0.0,
    }
    base_df["Flow Cost"] = [means[fl] for fl in base_df["Flow"]]
    return base_df


def solve_36_nogood_cuts(
    ssopt_csv_path: Path,
    sim_sum_csv_path: Path,
    out_json_path: Path,
    solver_name: str = "appsi_highs",
) -> dict[str, Any]:
    """Enumerate all 36 discrete superstructure solutions via no-good integer cuts."""
    if pyo is None:
        raise ImportError("Pyomo is required to solve the discrete IP.")

    flst_data = pd.read_csv(ssopt_csv_path)
    flow_with_uo = [
        row["Flow"] for _, row in flst_data.iterrows() if row["uo"] != "none"
    ]
    uo_keys = {
        row["Flow"]: row["uo"]
        for _, row in flst_data.iterrows()
        if row["uo"] not in ("none", "holdT", "noholdT")
    }
    flow_network = {
        row["Flow"]: (row["From"], row["To"]) for _, row in flst_data.iterrows()
    }
    flow_cost = {
        row["Flow"]: float(row["Flow Cost"]) for _, row in flst_data.iterrows()
    }

    flows = list(flow_network.keys())
    nodes = sorted(set(sum(flow_network.values(), ())))
    source_node, sink_node = nodes[0], nodes[-1]

    model = pyo.ConcreteModel(doc="flowsheet optimization model")
    model.flows = pyo.Set(initialize=flows)
    model.nodes = pyo.Set(initialize=nodes)
    model.f = pyo.Var(model.flows, domain=pyo.Binary)
    model.fcost = pyo.Param(model.flows, initialize=flow_cost, mutable=True)
    model.capex = pyo.Objective(
        expr=sum(model.f[f] * model.fcost[f] for f in model.flows),
        sense=pyo.minimize,
    )

    def flow_conservation_rule(m: Any, node: str) -> Any:
        inflow = sum(m.f[fl] for fl in m.flows if flow_network[fl][1] == node)
        outflow = sum(m.f[fl] for fl in m.flows if flow_network[fl][0] == node)
        if node == source_node:
            return outflow == 1.0
        if node == sink_node:
            return inflow == 1.0
        return inflow == outflow

    model.flow_conservation = pyo.Constraint(
        model.nodes, rule=flow_conservation_rule
    )
    model.continuous_to_batch = pyo.ConstraintList()
    model.continuous_to_batch.add(
        (1 - model.f["f01"]) + (1 - model.f["f10"]) + model.f["f06"] >= 1
    )
    model.continuous_to_batch.add(
        (1 - model.f["f02"]) + (1 - model.f["f10"]) + model.f["f06"] >= 1
    )
    model.continuous_to_batch.add(
        (1 - model.f["f03"]) + (1 - model.f["f10"]) + (1 - model.f["f06"]) >= 1
    )
    model.continuous_to_batch.add(
        model.f["f01"] + model.f["f02"] + model.f["f05"] >= 1
    )
    model.continuous_to_batch.add(model.f["f10"] + model.f["f05"] >= 1)
    for fl in ("f13", "f14", "f15"):
        model.continuous_to_batch.add((1 - model.f[fl]) + model.f["f17"] >= 1)

    model.int_cuts = pyo.ConstraintList()

    sim_data = pd.read_csv(sim_sum_csv_path)
    sim_data["Combination_Key"] = sim_data["Combination"].apply(
        lambda x: x.replace("(", "")
        .replace(")", "")
        .replace("_ ", " ")
        .replace("'", "")
        .strip()
    )

    solver = pyo.SolverFactory(solver_name)
    result_dict: dict[str, Any] = {}

    for it in range(1, 37):
        t0 = time.perf_counter()
        res = solver.solve(model, tee=False)
        solve_time = time.perf_counter() - t0
        sol = {fl: float(round(pyo.value(model.f[fl]))) for fl in flows}
        op_modes = [
            uo_keys[fl] for fl in flows if fl in uo_keys and sol[fl] == 1.0
        ]
        op_str = " ".join(op_modes)

        entry: dict[str, Any] = {fl: sol[fl] for fl in flows}
        entry["operating_modes"] = op_modes
        entry["solve_time"] = float(solve_time)
        entry["ip_obj_value"] = round(float(pyo.value(model.capex)), 6)
        entry["termination_condition"] = str(res.solver.termination_condition)

        match = sim_data.loc[sim_data["Combination_Key"] == op_str]
        if not match.empty:
            row = match.iloc[0]
            entry["sm_obj_value"] = float(row["Best Objective Value"])
            entry["sm_eval_time"] = int(row["Evaluation Time"])
            entry["sm_capex"] = float(row["Total_CAPEX"])
            entry["sm_turton_capex_usd"] = float(row["Total_Turton_CAPEX_USD"])
            entry["sm_mass_prod_kg_s"] = float(row["Mass_Productivity_kg_s"])
            entry["sm_crystal_size_um"] = float(row["Crystal_Size_um"])

        result_dict[str(it)] = entry

        cut_expr = sum(
            (1.0 - model.f[fl]) if sol[fl] == 1.0 else model.f[fl]
            for fl in flow_with_uo
        )
        model.int_cuts.add(cut_expr >= 1.0)

    out_json_path.write_text(
        json.dumps(result_dict, indent=2) + "\n", encoding="utf-8"
    )
    return result_dict


def write_all_tables_from_bundle(bundle: dict[str, Any]) -> None:
    """Write simulation CSV/JSON tables and discrete-IP tables from ``bundle``."""
    CORR_SIM_DIR.mkdir(parents=True, exist_ok=True)
    CORR_DIP_DATA.mkdir(parents=True, exist_ok=True)
    CORR_DIP_RES.mkdir(parents=True, exist_ok=True)

    opt_points_nomad: dict[str, list[str]] = {}
    mass_size_eval: dict[str, list[float]] = {}
    mass_size_nomad: dict[str, list[float]] = {}

    for idx in range(40):
        key = str(idx)
        base = bundle[key]["baseline"]
        opt = bundle[key]["optimized"]

        opt_points_nomad[key] = [f"{float(v):.8g}" for v in opt["x"]]
        mass_size_eval[key] = [
            float(base["mass_prod_kg_s"]),
            float(base["crystal_size_um"]),
        ]
        mass_size_nomad[key] = [
            float(opt["mass_prod_kg_s"]),
            float(opt["crystal_size_um"]),
        ]

    (CORR_SIM_DIR / "optimal_points_corrected_nomad.json").write_text(
        json.dumps(opt_points_nomad, indent=2) + "\n", encoding="utf-8"
    )
    (CORR_SIM_DIR / "optimal_mass_size_corrected_eval.json").write_text(
        json.dumps(mass_size_eval, indent=2) + "\n", encoding="utf-8"
    )
    (CORR_SIM_DIR / "optimal_mass_size_corrected_nomad.json").write_text(
        json.dumps(mass_size_nomad, indent=2) + "\n", encoding="utf-8"
    )

    for tag, field in [("eval", "baseline"), ("nomad", "optimized")]:
        rows_sorted_36 = []
        rows_capex_36 = []
        rows_sum_36 = []
        rows_sum_40 = []

        for idx in range(40):
            rec = bundle[str(idx)][field]
            layout = tuple(rec["layout"])
            combo_str = format_combo_legacy(layout)
            x_str = " ".join(f"{float(v):.8g}" for v in rec["x"])
            nb_evals = int(rec.get("nb_evals", 1))
            eval_time_s = int(
                round(rec.get("opt_wall_s", rec.get("eval_s", 1.0)))
            )

            sum_row = {
                "Combination_Index": idx,
                "Combination": combo_str,
                "Layout": str(layout),
                "Evaluation Time": eval_time_s,
                "Best Solution (feasible)": f"( {x_str} )",
                "Best Objective Value": float(rec["obj_val"]),
                "Blackbox Evaluations": nb_evals,
                "Total Model Evaluations": nb_evals,
                "Total Number of Evaluations": nb_evals,
                "Mass_Productivity_kg_s": float(rec["mass_prod_kg_s"]),
                "Crystal_Size_um": float(rec["crystal_size_um"]),
                "Cost_Objective_Value": float(rec["cost_obj"]),
                "g1_solub_path_con": float(rec["g1_solub_path_con"]),
                "g2_heptane_shortfall": float(rec["g2_heptane_shortfall"]),
                "CAPEX": str(rec["equip_sizes"]),
                "Total_CAPEX": float(rec["total_equip_size"]),
                "Turton_CAPEX_USD": str(rec["turton_capex_usd"]),
                "Total_Turton_CAPEX_USD": float(rec["total_turton_capex_usd"]),
            }
            rows_sum_40.append(sum_row)

            if idx < 36:
                rows_sorted_36.append({"Combination": combo_str, "x": x_str})
                rows_capex_36.append(
                    {
                        "Combination": combo_str,
                        "Values": f" {x_str} ",
                        "CAPEX": str(rec["equip_sizes"]),
                        "Total_CAPEX": float(rec["total_equip_size"]),
                        "Turton_CAPEX_USD": str(rec["turton_capex_usd"]),
                        "Total_Turton_CAPEX_USD": float(
                            rec["total_turton_capex_usd"]
                        ),
                    }
                )
                rows_sum_36.append(sum_row)

        pd.DataFrame(rows_sorted_36).to_csv(
            CORR_SIM_DIR / f"x_input_sorted_corrected_{tag}.csv", index=False
        )
        pd.DataFrame(rows_capex_36).to_csv(
            CORR_SIM_DIR / f"x_input_with_total_capex_corrected_{tag}.csv",
            index=False,
        )
        pd.DataFrame(rows_sum_36).to_csv(
            CORR_SIM_DIR / f"run_objmassprodcrys_sum_corrected_{tag}.csv",
            index=False,
        )
        pd.DataFrame(rows_sum_40).to_csv(
            CORR_SIM_DIR / f"run_objmassprodcrys_sum_all40_corrected_{tag}.csv",
            index=False,
        )

    eval_36 = [bundle[str(i)]["baseline"] for i in range(36)]
    nomad_36 = [bundle[str(i)]["optimized"] for i in range(36)]

    df_ssopt_eval = compute_ssopt_table(eval_36, use_turton_musd=False)
    df_ssopt_nomad = compute_ssopt_table(nomad_36, use_turton_musd=False)
    df_ssopt_turton = compute_ssopt_table(nomad_36, use_turton_musd=True)

    ssopt_eval_path = CORR_DIP_DATA / "ssopt_gen_1_corrected_eval.csv"
    ssopt_nomad_path = CORR_DIP_DATA / "ssopt_gen_1_corrected_nomad.csv"
    ssopt_turton_path = CORR_DIP_DATA / "ssopt_gen_1_corrected_turton_musd.csv"

    df_ssopt_eval.to_csv(ssopt_eval_path, index=False)
    df_ssopt_nomad.to_csv(ssopt_nomad_path, index=False)
    df_ssopt_turton.to_csv(ssopt_turton_path, index=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--eval-only",
        action="store_true",
        help="Evaluate published and saved NOMAD points without running PyNomad.",
    )
    parser.add_argument(
        "--max-bb-eval",
        type=int,
        default=60,
        help="Maximum PyNomad black-box evaluations per configuration.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=max(1, (os.cpu_count() or 4) // 2),
        help="Number of parallel worker processes.",
    )
    args = parser.parse_args(argv)

    opt_pts = load_optimal_points(include_pfr_update=True)
    bundle: dict[str, Any] = {}

    if args.eval_only:
        saved_nomad_path = CORR_SIM_DIR / "optimal_points_corrected_nomad.json"
        if saved_nomad_path.is_file():
            nomad_pts = json.loads(saved_nomad_path.read_text(encoding="utf-8"))
        else:
            nomad_pts = opt_pts
        for idx in range(len(valid_combos)):
            key = str(idx)
            base_res = evaluate_point(idx, [float(v) for v in opt_pts[key]])
            opt_res = evaluate_point(idx, [float(v) for v in nomad_pts[key]])
            bundle[key] = {
                "combo_idx": idx,
                "baseline": base_res,
                "optimized": opt_res,
            }
    else:
        with ProcessPoolExecutor(max_workers=args.max_workers) as pool:
            fut_to_idx = {
                pool.submit(
                    optimize_single_combo,
                    idx,
                    [float(v) for v in opt_pts[str(idx)]],
                    args.max_bb_eval,
                ): idx
                for idx in range(len(valid_combos))
            }
            for fut in as_completed(fut_to_idx):
                idx = fut_to_idx[fut]
                bundle[str(idx)] = fut.result()

    CORR_SIM_DIR.mkdir(parents=True, exist_ok=True)
    ordered = {str(idx): bundle[str(idx)] for idx in range(len(valid_combos))}
    (
        CORR_SIM_DIR / "all40_corrected_model_evaluation_and_nomad.json"
    ).write_text(json.dumps(ordered, indent=2) + "\n", encoding="utf-8")
    write_all_tables_from_bundle(ordered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
