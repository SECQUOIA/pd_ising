"""Regression tests for credential-free D-Wave QA helper behavior.

The fake sampler pins the boundary contract only: submitted QUBO data is
dimensionless [-], the sample set is fake, and no live D-Wave service is used.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ListVector(list):
    """Small stand-in for dimod data vectors with a ``tolist`` method."""

    def tolist(self):
        return list(self)


class FakeSampleSet:
    """Fake D-Wave sample set with dimensionless energy/count fixture data."""

    def __init__(self, events):
        self._events = events
        self.data_vectors = {
            "energy": ListVector([1.5, 2.5]),
            "num_occurrences": ListVector([2, 3]),
        }
        self.variables = [0, 1]
        self.record = types.SimpleNamespace()
        self.info = {"problem_id": "fake-problem-id"}

    def resolve(self):
        self._events.append("resolve")


def install_dependency_stubs(monkeypatch, events):
    """Install import-time stubs for optional scientific/D-Wave dependencies."""

    def module(name):
        stub = types.ModuleType(name)
        monkeypatch.setitem(sys.modules, name, stub)
        return stub

    pandas = module("pandas")
    pandas.read_csv = None

    numpy = module("numpy")
    numpy.ndarray = object
    numpy.array = lambda value: value

    matplotlib = module("matplotlib")
    pyplot = module("matplotlib.pyplot")
    matplotlib.pyplot = pyplot

    module("networkx")
    pyomo = module("pyomo")
    pyomo_environ = module("pyomo.environ")
    pyomo.environ = pyomo_environ

    gurobipy = module("gurobipy")
    gurobipy.read = None

    class FakeBinaryQuadraticModel:
        @staticmethod
        def from_qubo(qubo, offset=0.0):
            events.append(("from_qubo", qubo, offset))
            return {"qubo": qubo, "offset": offset}

    dimod = module("dimod")
    dimod.BinaryQuadraticModel = FakeBinaryQuadraticModel

    neal = module("neal")
    neal.SimulatedAnnealingSampler = object

    fake_sampleset = FakeSampleSet(events)

    class FakeDWaveSampler:
        def __init__(self, solver=None):
            events.append(("sampler", solver))
            self.solver = types.SimpleNamespace(name="Advantage2_system1")
            self.properties = {"topology": {"type": "zephyr", "nodes": 5760}}

    class FakeEmbeddingComposite:
        def __init__(self, base_sampler):
            self.base_sampler = base_sampler

        def sample(self, **kwargs):
            events.append(("sample", kwargs))
            return fake_sampleset

    dwave = module("dwave")
    dwave_system = module("dwave.system")
    dwave.system = dwave_system
    dwave_system.DWaveSampler = FakeDWaveSampler
    dwave_system.EmbeddingComposite = FakeEmbeddingComposite
    dwave_system.FixedEmbeddingComposite = object


def load_helper_module(monkeypatch, relative_path, module_name, events):
    install_dependency_stubs(monkeypatch, events)
    module_path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    helper_module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, helper_module)
    spec.loader.exec_module(helper_module)

    loaded_path = Path(helper_module.__file__).resolve()
    assert PROJECT_ROOT in loaded_path.parents
    return helper_module


@pytest.mark.parametrize(
    ("relative_path", "module_name"),
    [
        ("ds-mfg/discrete_ip/ds_mfg_utils.py", "ds_mfg_utils_under_test"),
        ("il-rxtor-sep-opt/ilrs_common.py", "ilrs_common_under_test"),
    ],
)
def test_solve_qa_dwave_resolves_before_timing_and_saves_solver_meta(
    monkeypatch, tmp_path, relative_path, module_name
):
    events = []
    helper_module = load_helper_module(
        monkeypatch, relative_path, module_name, events
    )

    clock_values = iter([10.0, 14.25])

    def fake_perf_counter():
        events.append("perf_counter")
        return next(clock_values)

    monkeypatch.setattr(
        helper_module, "time", types.SimpleNamespace(perf_counter=fake_perf_counter)
    )

    # QUBO entries and beta offset are dimensionless [-] in this boundary test.
    sampleset, execution_time = helper_module.solve_qa_dwave(
        [[0.0, 1.0], [1.0, 0.0]],
        0.5,
        save=True,
        output_dir=str(tmp_path),
        topology="zephyr",
    )

    assert sampleset.info["problem_id"] == "fake-problem-id"
    assert execution_time == 4.25
    clock_indices = [
        index for index, event in enumerate(events) if event == "perf_counter"
    ]
    assert len(clock_indices) == 2
    assert events.index("resolve") < clock_indices[1]

    saved_files = list(tmp_path.glob("Dwave_QA_results_*.json"))
    assert len(saved_files) == 1

    result = json.loads(saved_files[0].read_text())
    assert result["meta"]["topology"] == {"type": "zephyr", "nodes": 5760}
    assert result["meta"]["solver_name"] == "Advantage2_system1"
    assert result["solver"] == "dwave_qpu_Advantage2_system1"
    assert result["num_samples"] == 5
    assert result["info"]["problem_id"] == "fake-problem-id"
