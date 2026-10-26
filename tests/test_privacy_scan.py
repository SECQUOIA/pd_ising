"""Tests for privacy/credential scanning and repository hygiene (#7-#23)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))

from check_privacy_and_secrets import scan_repository, scan_text  # noqa: E402


def test_existing_tree_passes_privacy_and_credential_scan():
    assert scan_repository(REPO_ROOT) == []


@pytest.mark.parametrize(
    "sample",
    [
        "path = '" + "/home" + "/alice/repos/pd_ising/data.csv'\n",
        "prefix: " + "/Users" + "/bob/miniconda3/envs/test\n",
    ],
)
def test_home_directory_paths_fail_scan(sample):
    violations = scan_text(sample, path="notebook.ipynb")
    assert any(kind == "home-path" for _, kind, _ in violations)


@pytest.mark.parametrize(
    "sample",
    [
        "os." + 'environ["DWAVE_API_TOKEN"] = "your-api-token"\n',
        "os." + 'environ["QCI_API_TOKEN"] = "secret"\n',
        "token = 'ghp" + "_1234567890abcdefghijklmnopqrstuv'\n",
        "token = 'DEV-" + "0123456789abcdef0123456789abcdef'\n",
    ],
)
def test_credential_patterns_fail_scan(sample):
    violations = scan_text(sample, path="script.py")
    assert len(violations) >= 1


def test_email_in_source_or_notebook_fails_scan():
    email = "user" + "@" + "example.com"
    violations = scan_text(f"contact = '{email}'\n", path="script.py")
    assert violations == [(1, "email", email)]


def test_email_in_pyproject_metadata_is_allowed():
    email = "user" + "@" + "example.com"
    violations = scan_text(
        f'authors = [{{name = "Author", email = "{email}"}}]\n',
        path="il-rxtor-sep-opt/pyproject.toml",
    )
    assert violations == []


def test_gitignore_patterns_resolve_to_root():
    for probe in (
        ".venv",
        ".pixi",
        ".CondaPkg",
        "__pycache__",
        ".ipynb_checkpoints",
        ".env",
        "ds-mfg/.venv",
        "ds-mfg/.pixi",
        "ds-mfg/.CondaPkg",
        "il-rxtor-sep-opt/.pixi",
        "il-rxtor-sep-opt/__pycache__",
        "il-rxtor-sep-opt/.ipynb_checkpoints",
    ):
        res = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "check-ignore", "-v", probe],
            check=True,
            capture_output=True,
            text=True,
        )
        assert res.stdout.startswith(".gitignore:"), res.stdout

    for tracked_env_file in (
        "ds-mfg/Project.toml",
        "ds-mfg/Manifest.toml",
        "ds-mfg/CondaPkg.toml",
        "ds-mfg/pixi.toml",
        "ds-mfg/pixi.lock",
        "il-rxtor-sep-opt/Project.toml",
        "il-rxtor-sep-opt/Manifest.toml",
        "il-rxtor-sep-opt/pixi.toml",
        "il-rxtor-sep-opt/pixi.lock",
    ):
        assert (REPO_ROOT / tracked_env_file).is_file(), tracked_env_file
        res = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", tracked_env_file],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 1, f"{tracked_env_file} must not be gitignored"


def test_julia_project_and_manifest_reproducibility():
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback
        import tomli as tomllib  # type: ignore[no-redef]

    required_stdlibs = {
        "Dates",
        "DelimitedFiles",
        "Printf",
        "SHA",
        "SparseArrays",
        "Statistics",
    }
    for subproject in ("ds-mfg", "il-rxtor-sep-opt"):
        proj_path = REPO_ROOT / subproject / "Project.toml"
        man_path = REPO_ROOT / subproject / "Manifest.toml"
        proj = tomllib.loads(proj_path.read_text(encoding="utf-8"))
        man = tomllib.loads(man_path.read_text(encoding="utf-8"))

        deps = set(proj["deps"].keys())
        compat = set(proj["compat"].keys())

        assert required_stdlibs.issubset(deps), (subproject, required_stdlibs - deps)
        assert "Gurobi_jll" not in deps
        assert deps.issubset(compat), (subproject, deps - compat)
        assert proj["compat"]["julia"] == "1.11.5"
        assert proj["compat"]["Gurobi"] == "=1.7.0"

        assert man["julia_version"] == "1.11.5"
        assert man["deps"]["Gurobi"][0]["version"] == "1.7.0"
        assert man["deps"]["Gurobi_jll"][0]["version"].startswith("12.0.3")


def test_pixi_single_environment_definition():
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback
        import tomli as tomllib  # type: ignore[no-redef]

    for removed in (
        "il-rxtor-sep-opt/requirements.txt",
        "il-rxtor-sep-opt/pyproject.toml",
        "il-rxtor-sep-opt/environment.yml",
        "ds-mfg/simulation/code/environment.yml",
    ):
        assert not (REPO_ROOT / removed).exists(), f"{removed} should be removed"

    ds_pixi = tomllib.loads((REPO_ROOT / "ds-mfg" / "pixi.toml").read_text(encoding="utf-8"))
    il_pixi = tomllib.loads(
        (REPO_ROOT / "il-rxtor-sep-opt" / "pixi.toml").read_text(encoding="utf-8")
    )
    assert "default" in ds_pixi.get("environments", {})
    assert "simulation" in ds_pixi.get("environments", {})
    assert "juliaup" in ds_pixi["dependencies"]
    assert "juliaup" in il_pixi["dependencies"]


def test_readme_file_inventories_match_disk():
    stale_tokens = (
        "README_SETUP.md",
        "QUBO_Reformulation_Capabilities.md",
        "run_selected_configs.py",
        "capex_data_68_configs.csv",
    )
    for readme_rel in (
        "README.md",
        "ds-mfg/README.md",
        "ds-mfg/discrete_ip/README.md",
        "il-rxtor-sep-opt/README.md",
        "il-rxtor-sep-opt/DEPENDENCIES.md",
    ):
        text = (REPO_ROOT / readme_rel).read_text(encoding="utf-8")
        for token in stale_tokens:
            assert token not in text, f"Stale path {token!r} found in {readme_rel}"

    ds_readme = (REPO_ROOT / "ds-mfg" / "README.md").read_text(encoding="utf-8")
    for expected in (
        "discrete_ip/solve_gurobi_pool.py",
        "discrete_ip/ds_mfg_helper_fn.py",
        "simulation/code/generating_structures.py",
        "simulation/code/data_organizer.py",
        "simulation/data/capex_coeff.csv",
        "simulation/data/raw_material_cost.csv",
        "pixi.toml",
        "pixi.lock",
    ):
        assert expected in ds_readme
        assert (REPO_ROOT / "ds-mfg" / expected).exists()

    il_readme = (REPO_ROOT / "il-rxtor-sep-opt" / "README.md").read_text(encoding="utf-8")
    for expected in (
        "original_mip/evaluate_all_configs.jl",
        "discrete_ip/solve_gurobi_poolsearch_funcs.py",
        "ilrs_helper_fn.py",
        "pixi.toml",
        "pixi.lock",
    ):
        assert Path(expected).name in il_readme
        assert (REPO_ROOT / "il-rxtor-sep-opt" / expected).exists()


def test_reproduce_md_referenced_files_exist():
    reproduce = (REPO_ROOT / "REPRODUCE.md").read_text(encoding="utf-8")
    for token in (
        "il-rxtor-sep-opt/discrete_qubo/ilrs_qubo.ipynb",
        "il-rxtor-sep-opt/discrete_qubo/result_raw/SA_results_20260114_163501.json",
        "il-rxtor-sep-opt/discrete_qubo/result_raw/Dwave_QA_results_20260626_161207.json",
        "il-rxtor-sep-opt/discrete_qubo/result_raw/Dwave_QA_results_20260626_161210.json",
        "il-rxtor-sep-opt/discrete_qubo/result_raw/QCI_EQC_results.json",
        "ds-mfg/discrete_ip/flst_opti_QUBO.ipynb",
        "ds-mfg/discrete_ip/result_raw/SA_results_20250819_163847.json",
        "ds-mfg/discrete_ip/result_raw/Dwave_QA_results_20260626_143653.json",
        "ds-mfg/discrete_ip/result_raw/Dwave_QA_results_20260626_143707.json",
        "ds-mfg/discrete_ip/result_raw/QCI_EQC_results.json",
    ):
        assert token in reproduce
        assert (REPO_ROOT / token).exists()


def test_data_organizer_imports_without_side_effects(monkeypatch):
    code_dir = REPO_ROOT / "ds-mfg" / "simulation" / "code"
    monkeypatch.syspath_prepend(str(code_dir))
    # Stub PharmaPy-dependent modules so import succeeds in a lightweight test env.
    import types

    gen_mod = types.ModuleType("generating_structures")
    gen_mod.get_input_dictionary = lambda *a, **k: {}
    gen_mod.make_graph = lambda *a, **k: None
    gen_mod.run_flowsheet = lambda *a, **k: (None, False)
    helper_mod = types.ModuleType("helper")
    helper_mod.translate_scale = lambda x, b: x
    monkeypatch.setitem(sys.modules, "generating_structures", gen_mod)
    monkeypatch.setitem(sys.modules, "helper", helper_mod)

    spec = importlib.util.spec_from_file_location(
        "data_organizer", code_dir / "data_organizer.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert hasattr(module, "organize_capex_data")
    assert hasattr(module, "main")
    assert module.DATA_DIR == (REPO_ROOT / "ds-mfg" / "simulation" / "data").resolve()
