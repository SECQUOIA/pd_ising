"""Tests for standardized result organization, bundling, and PR review setup (#4)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))

from check_results_organization import (  # noqa: E402
    bundle_replicates,
    load_replicate_records,
    validate_diff,
    validate_result_file,
)


@pytest.mark.parametrize(
    "probe",
    [
        "ds-mfg/discrete_ip/result_raw/SA_results_20250819_163847.json",
        "ds-mfg/discrete_ip/result_gurobi/replicates/gurobi_pool_solutions_n5_20260204_164336_692422.json",
        "il-rxtor-sep-opt/discrete_qubo/julia_exports/Q_matrix_1.csv",
        "il-rxtor-sep-opt/original_mip/result_all_configs/summary.json",
        "ds-mfg/pixi.lock",
        "il-rxtor-sep-opt/Manifest.toml",
    ],
)
def test_gitattributes_marks_generated_results_as_linguist_generated(probe):
    res = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-attr", "linguist-generated", probe],
        check=True,
        capture_output=True,
        text=True,
    )
    assert res.stdout.strip().endswith(": linguist-generated: true"), res.stdout


def test_gitattributes_leaves_source_and_notebooks_reviewable():
    for source_path in (
        "ds-mfg/discrete_ip/flst_opti_IP.py",
        "il-rxtor-sep-opt/discrete_qubo/ilrs_qubo.ipynb",
        "REPRODUCE.md",
    ):
        res = subprocess.run(
            [
                "git",
                "-C",
                str(REPO_ROOT),
                "check-attr",
                "linguist-generated",
                source_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        assert res.stdout.strip().endswith(": linguist-generated: unspecified")


def test_pr_template_separates_code_review_from_generated_artifacts():
    template = (REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(
        encoding="utf-8"
    )
    assert "## What to Review" in template
    assert "## Generated Result & Export Artifacts" in template
    assert "REPRODUCE.md" in template


def test_valid_new_result_file_passes(tmp_path):
    rel = "ds-mfg/discrete_ip/result_raw/SA_results_20261026_120000.json"
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "run_info": {
                    "solver": "neal.SimulatedAnnealingSampler",
                    "timestamp": "20261026_120000",
                    "seed": 42,
                },
                "energies": [-10.0],
            }
        ),
        encoding="utf-8",
    )
    assert validate_result_file(rel, tmp_path) == []
    assert validate_diff(f"A\t{rel}\n", tmp_path) == []


def test_result_file_without_provenance_fails(tmp_path):
    rel = "il-rxtor-sep-opt/discrete_qubo/result_raw/SA_results_20261026_120000.json"
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"energies": [-10.0]}), encoding="utf-8")
    errors = validate_result_file(rel, tmp_path)
    assert len(errors) == 1
    assert "run_info" in errors[0]


def test_result_file_with_bad_filename_or_location_fails(tmp_path):
    bad_name = "ds-mfg/discrete_ip/result_raw/untimestamped.json"
    errors = validate_result_file(bad_name, tmp_path)
    assert any("must match" in e for e in errors)

    bad_root = "unknown-subproject/discrete_ip/result_raw/SA_results_20261026_120000.json"
    errors_root = validate_result_file(bad_root, tmp_path)
    assert any("must live under" in e for e in errors_root)


def test_uncompressed_replicate_flood_is_blocked_until_bundled(tmp_path):
    rep_dir = tmp_path / "ds-mfg" / "discrete_ip" / "result_gurobi" / "replicates"
    rep_dir.mkdir(parents=True, exist_ok=True)
    diff_lines = []
    for i in range(25):
        fname = f"gurobi_pool_n10_20261026_1200{i:02d}.json"
        (rep_dir / fname).write_text(
            json.dumps({"run_info": {"seed": i}, "solutions": []}),
            encoding="utf-8",
        )
        diff_lines.append(f"A\tds-mfg/discrete_ip/result_gurobi/replicates/{fname}")

    errors = validate_diff("\n".join(diff_lines) + "\n", tmp_path)
    assert any("loose JSON files under replicates/" in e for e in errors)

    archive_path, rep_path = bundle_replicates(
        rep_dir, keep_representative=True, delete_bundled=True
    )
    assert archive_path.is_file()
    assert rep_path is not None and rep_path.is_file()
    assert len(list(rep_dir.glob("*.json"))) == 1

    bundled_diff = (
        f"A\tds-mfg/discrete_ip/result_gurobi/replicates/{rep_path.name}\n"
        f"A\tds-mfg/discrete_ip/result_gurobi/replicates/{archive_path.name}\n"
    )
    assert validate_diff(bundled_diff, tmp_path) == []

    records = load_replicate_records(rep_dir)
    assert len(records) == 25
    assert records["gurobi_pool_n10_20261026_120024.json"]["run_info"]["seed"] == 24


def test_aggregate_pool_run_timings_reads_bundled_replicates(tmp_path, monkeypatch):
    import importlib.util
    import types

    for mod_name in (
        "gurobipy",
        "pyomo",
        "pyomo.environ",
        "scipy",
        "scipy.stats",
        "matplotlib",
        "matplotlib.pyplot",
        "ds_mfg_utils",
    ):
        monkeypatch.setitem(sys.modules, mod_name, types.ModuleType(mod_name))
    flst_mod = types.ModuleType("flst_opti_IP")
    flst_mod.FlowsheetOptimizer = object
    flst_mod.get_default_paths = lambda: (None, None)
    monkeypatch.setitem(sys.modules, "flst_opti_IP", flst_mod)

    spec = importlib.util.spec_from_file_location(
        "solve_gurobi_pool",
        REPO_ROOT / "ds-mfg" / "discrete_ip" / "solve_gurobi_pool.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    rep_dir = tmp_path / "replicates"
    rep_dir.mkdir(parents=True, exist_ok=True)
    for idx, n in enumerate((10, 10, 20)):
        fname = f"gurobi_pool_solutions_n{n}_20260204_16433{idx}.json"
        (rep_dir / fname).write_text(
            json.dumps(
                {
                    "run_info": {
                        "Pool Search Info": {
                            "Solve Time": 0.05 * (idx + 1),
                            "NumSolutions Found": n,
                        }
                    },
                    "solutions": [],
                }
            ),
            encoding="utf-8",
        )

    df_loose = mod.aggregate_pool_run_timings(rep_dir)
    assert len(df_loose) == 3

    bundle_replicates(rep_dir, keep_representative=True, delete_bundled=True)
    assert len(list(rep_dir.glob("*.json"))) == 1
    df_bundled = mod.aggregate_pool_run_timings(rep_dir)
    assert df_bundled.equals(df_loose)


def test_ilrs_aggregate_pool_run_timings_and_archive_validation(tmp_path, monkeypatch):
    import importlib.util
    import types

    for mod_name in (
        "gurobipy",
        "pyomo",
        "pyomo.environ",
        "pyomo.opt",
        "scipy",
        "scipy.stats",
        "matplotlib",
        "matplotlib.pyplot",
    ):
        m = types.ModuleType(mod_name)
        m.__path__ = []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, mod_name, m)
    for attr in (
        "ConcreteModel",
        "Var",
        "Binary",
        "Constraint",
        "Objective",
        "minimize",
        "Set",
        "Param",
        "value",
        "SolverFactory",
    ):
        setattr(sys.modules["pyomo.environ"], attr, object)
    for attr in ("SolverStatus", "TerminationCondition"):
        setattr(sys.modules["pyomo.opt"], attr, object)

    spec = importlib.util.spec_from_file_location(
        "solve_gurobi_poolsearch_funcs",
        REPO_ROOT
        / "il-rxtor-sep-opt"
        / "discrete_ip"
        / "solve_gurobi_poolsearch_funcs.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    rep_dir = tmp_path / "il-rxtor-sep-opt" / "discrete_ip" / "result_gurobi" / "replicates"
    rep_dir.mkdir(parents=True, exist_ok=True)
    for idx, n in enumerate((100, 100, 200)):
        fname = f"ilrs_gpool_n{n}_20260204_15573{idx}.json"
        (rep_dir / fname).write_text(
            json.dumps(
                {
                    "run_info": {
                        "Pool Search Info": {
                            "Solve Time": 0.1 * (idx + 1),
                            "NumSolutions Found": n,
                        }
                    },
                    "solutions": [],
                }
            ),
            encoding="utf-8",
        )

    with pytest.raises(ValueError, match="Invalid archive_name"):
        bundle_replicates(rep_dir, archive_name="bad_name.zip")

    df_loose = mod.aggregate_pool_run_timings(rep_dir)
    assert len(df_loose) == 3

    archive_path, rep_path = bundle_replicates(
        rep_dir, keep_representative=True, delete_bundled=True
    )
    df_bundled = mod.aggregate_pool_run_timings(rep_dir)
    assert df_bundled.equals(df_loose)

    # Removing the representative .json file should fail validate_diff
    assert rep_path is not None
    rep_path.unlink()
    archive_only_diff = (
        f"A\til-rxtor-sep-opt/discrete_ip/result_gurobi/replicates/{archive_path.name}\n"
    )
    errors = validate_diff(archive_only_diff, tmp_path)
    assert any("representative .json" in e for e in errors)


