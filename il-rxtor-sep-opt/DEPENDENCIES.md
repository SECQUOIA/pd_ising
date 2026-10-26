# Dependencies Documentation (`il-rxtor-sep-opt/DEPENDENCIES.md`)

This document describes the reproducible environment definitions for the `il-rxtor-sep-opt` case study, which uses both Python and Julia.

## Single Environment Definition (`pixi.toml` + `Project.toml`)

The subproject uses two complementary lockfiles committed to the repository:

1. **`pixi.toml` & `pixi.lock`** — Locks the Python `3.12` interpreter, `juliaup`, and all Conda and PyPI scientific/quantum optimization packages.
2. **`Project.toml` & `Manifest.toml`** — Locks the Julia `1.11.5` package graph (including `Gurobi.jl v1.7.0` / `Gurobi_jll v12.0.3`, `JuMP v1.26.0`, `MathOptInterface v1.41.0`, `QUBO v0.6.4`, `QUBOTools v0.16.3`, and `ToQUBO v0.7.1`).

## Julia Dependencies (`Project.toml` & `Manifest.toml`)

### Direct Dependencies (`[deps]`)

- **CSV** (`=0.10.15`): CSV data import/export
- **DWave** (`=0.8.2`): D-Wave quantum and simulated annealing interface
- **DataFrames** (`=1.7.0`): Tabular data manipulation
- **Dates** (`1.11.0`, stdlib): Date/timestamp formatting for exports and metadata
- **DelimitedFiles** (`=1.9.1`): Matrix and vector CSV export (`writedlm`)
- **Gurobi** (`=1.7.0`, with `Gurobi_jll v12.0.3` in `Manifest.toml`): Gurobi MIP/MINLP solver interface
- **JSON** (`=0.21.4`): JSON result serialization
- **JuMP** (`=1.26.0`): Algebraic modeling language for mathematical optimization
- **LaTeXStrings** (`=1.4.0`): LaTeX string formatting for plots
- **MathOptInterface** (`=1.41.0`): Mathematical optimization solver abstraction
- **Plots** (`=1.40.15`): Plotting and QUBO density visualization
- **Printf** (`1.11.0`, stdlib): Formatted console output
- **PseudoBooleanOptimization** (`=0.3.0`): Pseudo-Boolean polynomial Quadratization (`Ifthaker` encoding)
- **QCIOpt** (`=0.2.0`, `https://github.com/SECQUOIA/QCIOpt.jl.git#v0.2.0`): QCi Dirac-3 optimization interface
- **QUBO** (`=0.6.4`): Quadratic Unconstrained Binary Optimization umbrella package
- **QUBOTools** (`=0.16.3`): QUBO model representation and querying
- **SHA** (`=0.7.0`, stdlib): SHA-256 input-file hashing for provenance metadata
- **SparseArrays** (`=1.11.0`, stdlib): Sparse QUBO matrix construction
- **Statistics** (`=1.11.1`): Summary statistics across solver runs
- **ToQUBO** (`=0.7.1`): Automatic JuMP-to-QUBO reformulation compiler

### Instantiating Julia Packages

```bash
cd il-rxtor-sep-opt
julia --project=. -e 'using Pkg; Pkg.instantiate(); Pkg.status()'
```

If Julia `1.11.5` is not yet installed on your machine, provision it via `pixi`:

```bash
pixi run setup-julia
```

## Python Dependencies (`pixi.toml` & `pixi.lock`)

### Conda Packages (`conda-forge`)
- **python** (`3.12.*`): Python interpreter
- **juliaup** (`==1.19.9`): Julia version manager used by `pixi run setup-julia` to provision Julia `1.11.5`
- **numpy** (`==1.26.4`): Numerical array computing
- **pandas** (`==2.2.2`): DataFrame manipulation and CSV I/O
- **scipy** (`==1.13.1`): Statistical routines (`scipy.stats`) for pool-search confidence intervals
- **matplotlib** (`==3.8.4`): Plotting and figure generation
- **networkx** (`==3.3`): Graph construction and topology visualization
- **pyomo** (`==6.9.2`): Algebraic optimization modeling (`original_mip/ilrs_MIP.py` and `discrete_ip/solve_gurobi_poolsearch_funcs.py`)
- **jupyter** (`==1.1.1`) & **ipykernel** (`==6.29.5`): Notebook execution environment
- **python-dateutil** (`>=2.7,<3`): Date utilities pinned for `dwave-cloud-client` compatibility

### PyPI Packages (`[pypi-dependencies]`)
- **dimod** (`==0.12.20`): Binary quadratic model primitives
- **dwave-neal** (`==0.6.0`): Simulated annealing sampler (`neal`)
- **dwave-system** (`==1.31.0`): D-Wave system samplers and embedding composites
- **dwave-networkx** (`==0.8.17`): Chimera/Pegasus/Zephyr graph utilities
- **minorminer** (`==0.2.18`): Minor-embedding heuristics
- **gurobipy** (`==12.0.3`): Gurobi Python API (`PoolSearchMode=2` solution-pool search)

### Installing and Running via Pixi

```bash
cd il-rxtor-sep-opt

# Install from the committed pixi.lock
pixi install

# Verify core Python imports
pixi run verify-python

# Run scripts or notebooks inside the locked environment
pixi run python original_mip/ilrs_MIP.py
pixi run jupyter lab
```

## Automated Setup

You can also run [`setup_dependencies.sh`](setup_dependencies.sh) from `il-rxtor-sep-opt/`:

```bash
./setup_dependencies.sh
```
