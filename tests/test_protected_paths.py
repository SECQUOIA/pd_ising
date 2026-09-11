"""Tests for the committed-results guard used by the protect-results workflow."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".github" / "scripts"))

from check_protected_paths import find_violations, is_protected  # noqa: E402


@pytest.mark.parametrize(
    "path",
    [
        "ds-mfg/discrete_ip/result_raw/Dwave_QA_results_20260626_143653.json",
        "ds-mfg/discrete_ip/result_gurobi/gurobi_pool_solutions_n5.json",
        "ds-mfg/discrete_ip/result_gurobi/replicates/ilrs_gpool_n500.json",
        "il-rxtor-sep-opt/original_mip/result_all_configs/summary.md",
        "il-rxtor-sep-opt/original_mip/result_all_configs/figures/fig1.png",
        "il-rxtor-sep-opt/discrete_qubo/julia_exports/Q_matrix_1.csv",
        "il-rxtor-sep-opt/data/parameter_alpha.csv",
        "ds-mfg/simulation/data/bounds.json",
        "images/260115_ilrs_feas.svg",
    ],
)
def test_result_and_data_paths_are_protected(path):
    assert is_protected(path)


@pytest.mark.parametrize(
    "path",
    [
        "ds-mfg/discrete_ip/ds_mfg_utils.py",
        "il-rxtor-sep-opt/ilrs_common.py",
        "il-rxtor-sep-opt/ilrs_utils.jl",
        "README.md",
        ".github/workflows/protect-results.yml",
        "tests/test_protected_paths.py",
        "ds-mfg/discrete_ip/flst_opti_QUBO.ipynb",
        # A file *named* data, rather than a directory, is ordinary source.
        "ds-mfg/discrete_ip/data.py",
        # "images" is protected only at the repository root.
        "docs/images/diagram.png",
    ],
)
def test_source_paths_are_not_protected(path):
    assert not is_protected(path)


def test_adding_a_result_file_is_allowed():
    """Adding new results is how the record grows; only altering it is blocked."""
    diff = "A\tds-mfg/discrete_ip/result_raw/Dwave_QA_results_20260626_143653.json\n"
    assert find_violations(diff) == []


@pytest.mark.parametrize(
    ("status", "label"),
    [("M", "modified"), ("D", "deleted"), ("T", "type changed")],
)
def test_altering_a_result_file_is_blocked(status, label):
    path = "il-rxtor-sep-opt/discrete_qubo/result_raw/SA_results_20260114_163501.json"
    assert find_violations(f"{status}\t{path}\n") == [(status, path)]


def test_renaming_a_result_file_is_blocked():
    """A rename removes the committed path, so the source path is what matters."""
    diff = (
        "R100\til-rxtor-sep-opt/discrete_qubo/julia_exports/Q_matrix_1.csv"
        "\til-rxtor-sep-opt/discrete_qubo/julia_exports/Q_matrix.csv\n"
    )
    assert find_violations(diff) == [
        ("R", "il-rxtor-sep-opt/discrete_qubo/julia_exports/Q_matrix_1.csv")
    ]


def test_source_only_pull_request_passes():
    diff = (
        "M\tds-mfg/discrete_ip/ds_mfg_utils.py\n"
        "M\til-rxtor-sep-opt/ilrs_common.py\n"
        "A\ttests/test_protected_paths.py\n"
        "D\tds-mfg/discrete_ip/ds_mfg_helper_fn.py\n"
    )
    assert find_violations(diff) == []


def test_mixed_pull_request_reports_only_the_altered_result():
    diff = (
        "M\tds-mfg/discrete_ip/ds_mfg_utils.py\n"
        "A\tds-mfg/discrete_ip/result_raw/new_run.json\n"
        "M\tds-mfg/discrete_ip/result_raw/old_run.json\n"
    )
    assert find_violations(diff) == [
        ("M", "ds-mfg/discrete_ip/result_raw/old_run.json")
    ]


def test_empty_diff_passes():
    assert find_violations("") == []
