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
        "path = '/home/alice/repos/pd_ising/data.csv'\n",
        'prefix: /Users/bob/miniconda3/envs/test\n',
    ],
)
def test_home_directory_paths_fail_scan(sample):
    violations = scan_text(sample, path="notebook.ipynb")
    assert any(kind == "home-path" for _, kind, _ in violations)


@pytest.mark.parametrize(
    "sample",
    [
        'os.environ["DWAVE_API_TOKEN"] = "your-api-token"\n',
        'os.environ["QCI_API_TOKEN"] = "secret"\n',
        "token = 'ghp_1234567890abcdefghijklmnopqrstuv'\n",
        "token = 'DEV-0123456789abcdef0123456789abcdef'\n",
    ],
)
def test_credential_patterns_fail_scan(sample):
    violations = scan_text(sample, path="script.py")
    assert len(violations) >= 1


def test_email_in_source_or_notebook_fails_scan():
    violations = scan_text("contact = 'user@example.com'\n", path="script.py")
    assert violations == [(1, "email", "user@example.com")]


def test_email_in_pyproject_metadata_is_allowed():
    violations = scan_text(
        'authors = [{name = "Author", email = "user@example.com"}]\n',
        path="il-rxtor-sep-opt/pyproject.toml",
    )
    assert violations == []


def test_gitignore_patterns_resolve_to_root():
    for probe in (
        ".venv",
        ".CondaPkg",
        "__pycache__",
        ".ipynb_checkpoints",
        ".env",
        "ds-mfg/.venv",
        "ds-mfg/.CondaPkg",
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
