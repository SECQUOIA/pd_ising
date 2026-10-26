# Flowsheet Optimization for Drug Substance Manufacturing (`ds-mfg/`)

This directory contains the drug-substance manufacturing flowsheet optimization case study, combining discrete Integer Programming (IP) and Quadratic Unconstrained Binary Optimization (QUBO) configuration synthesis (`discrete_ip/`) with downstream dynamic flowsheet simulation (`simulation/`).

## Directory and File Inventory

### Discrete IP and QUBO Workflow (`discrete_ip/`)

See [`discrete_ip/README.md`](discrete_ip/README.md) for additional workflow details.

1. **`discrete_ip/ds_mfg_utils.py`** & **`discrete_ip/ds_mfg_helper_fn.py`** - Common utility and helper functions for importing flowsheet data, building and solving QUBO/SA/QA models, and post-processing results
2. **`discrete_ip/ds_mfg_plotting.py`** - Plotting and visualization utilities for Pareto fronts and energy/objective distributions
3. **`discrete_ip/flst_opti_IP.py`** & **`discrete_ip/flst_opti_IP.ipynb`** - Pyomo/Gurobi discrete IP implementation with iterative integer (no-good) cuts and Pareto comparison against downstream simulation results
4. **`discrete_ip/solve_gurobi_pool.py`** & **`discrete_ip/ds_mfg_discrete_IP_poolsearch.ipynb`** - Gurobi solution-pool search (`PoolSearchMode=2`) and replicate confidence-interval analysis
5. **`discrete_ip/convert_to_qubo.jl`** - Julia (`JuMP` / `ToQUBO.jl` / `QUBOTools.jl`) script converting `discrete_ip/flowsheet_opti_simple.mps` to QUBO matrices in `discrete_ip/julia_exports/`
6. **`discrete_ip/flst_opti_QUBO.ipynb`** - Jupyter notebook comparing simulated annealing (SA), D-Wave quantum annealing (QA), and QCi Dirac entropy computing (EC) on the exported QUBO
7. **`discrete_ip/flowsheet_opti_simple.mps`** - MPS format model file for the discrete flowsheet IP
8. **`discrete_ip/data/`** - Flowsheet superstructure arc and cost data (`discrete_ip/data/ssopt_gen_1.csv`)
9. **`discrete_ip/julia_exports/`** - Committed Julia QUBO exports (`Q_matrix.csv`, `L_vector.csv`, `scalars.csv`)
10. **`discrete_ip/result_gurobi/`** - Committed Gurobi no-good-cut and solution-pool JSON results (including `discrete_ip/result_gurobi/replicates/`)
11. **`discrete_ip/result_raw/`** - Committed SA, D-Wave QA, and QCi EC raw JSON results

### Downstream Flowsheet Simulation (`simulation/`)

1. **`simulation/code/generating_structures.py`** - Flowsheet graph generation, input dictionary mapping, and `PharmaPy` `SimulationExec` execution
2. **`simulation/code/make_units.py`** - Unit-operation builders (reactors, vaporizers, crystallizers, filters, mixers, hold tanks) for `PharmaPy`
3. **`simulation/code/helper.py`** - Reaction and crystallization kinetics helpers, variable scaling, and path constraints
4. **`simulation/code/nomad_opt.py`** & **`simulation/code/run_all_opts.py`** - NOMAD blackbox optimization driver across valid flowsheet operating-mode combinations (`simulation/code/active_fs.txt`, `simulation/code/valid_combos.txt`)
5. **`simulation/code/process_results.py`** & **`simulation/code/data_organizer.py`** - Log parsing, CAPEX calculation, and summary table generation
6. **`simulation/code/config_mapping.py`** - Operating-mode combination and flowsheet graph mapping utilities
7. **`simulation/data/`** - Tracked cost coefficient tables (`simulation/data/capex_coeff.csv`, `simulation/data/raw_material_cost.csv`) used by `simulation/code/process_results.py` and `simulation/code/data_organizer.py`

### Figures and Environment Files

- **`images/`** - Flowsheet schematic and superstructure diagrams (`images/ds_schematic.jpg`, `images/ds_opt_flowsheet.jpg`)
- **`pixi.toml`** & **`pixi.lock`** - Locked Conda/PyPI environments (`default` for QUBO/IP and `simulation` for downstream `PharmaPy` simulation)
- **`Project.toml`**, **`Manifest.toml`**, & **`CondaPkg.toml`** - Locked Julia `1.11.5` package environment (`Gurobi v1.7.0` / `Gurobi_jll v12.0.3`, `JuMP v1.26.0`, `QUBO v0.6.4`, `QUBOTools v0.16.3`, `ToQUBO v0.7.1`)
- **`README.md`** - This documentation file

## Installation and Environment Setup

### 1. Python Environments (`pixi`)

`ds-mfg/pixi.toml` defines two isolated environments locked in `ds-mfg/pixi.lock`:

- **`default` (Discrete IP & QUBO stack — Python 3.12)**: `pyomo`, `gurobipy == 12.0.3`, `dimod == 0.12.20`, `dwave-neal == 0.6.0`, `dwave-system == 1.31.0`, `dwave-networkx == 0.8.17`, `minorminer == 0.2.18`, `scipy == 1.13.1`, `pandas == 2.2.2`, `numpy == 1.26.4`, `matplotlib == 3.8.4`, `networkx == 3.3`, and `juliaup`.
- **`simulation` (Downstream PharmaPy simulation stack — Python 3.8.13)**: `assimulo == 3.2.9`, `cyipopt == 1.1.0`, `ampl-mp == 3.1.0`, `ipopt == 3.14.4`, `sundials == 5.8.0`, `numdifftools == 0.9.40`, `scipy == 1.8.0`, `pandas == 1.4.2`, `numpy == 1.22.3`, `matplotlib == 3.5.1`, and `networkx == 2.7.1`.

```bash
cd ds-mfg

# Install and verify the default QUBO/IP environment
pixi install
pixi run verify-python

# Install the downstream simulation environment
pixi install -e simulation
```

> **Note on external `simulation/` dependencies (`PharmaPy` and `PyNomad`):**
> `simulation/code/` imports `PharmaPy` (an external Git checkout as of `2022-09-29`, <https://github.com/CryPTSys/PharmaPy>) and `PyNomad` (the Python binding to `NOMAD 3.9.1`, used only when re-running blackbox NOMAD searches via `simulation/code/nomad_opt.py`). Neither is distributed as a pinned package for this stack on `conda-forge` or PyPI. To run live `PharmaPy` simulations rather than reading the committed summary tables in `simulation/data/`, install `PharmaPy` into the `simulation` environment:
> ```bash
> pixi run -e simulation pip install --no-build-isolation -e /path/to/PharmaPy
> ```

### 2. Julia Environment (`Project.toml` / `Manifest.toml`)

The QUBO reformulation script (`discrete_ip/convert_to_qubo.jl`) uses Julia `1.11.5` with package versions locked in `Project.toml` and `Manifest.toml`:

```bash
cd ds-mfg

# If Julia 1.11.5 is already installed on PATH / via juliaup:
julia --project=. -e 'using Pkg; Pkg.instantiate(); Pkg.status()'

# Or provision Julia 1.11.5 and instantiate via pixi:
pixi run setup-julia

# Run QUBO conversion from discrete_ip/flowsheet_opti_simple.mps:
julia --project=. discrete_ip/convert_to_qubo.jl
```

## Data Format

### Flowsheet Data (`discrete_ip/data/ssopt_gen_1.csv`)

The flowsheet data CSV contains the following columns:

- `Flow`: Flow identifier (e.g., `"f01"`, `"f02"`)
- `From`: Source node
- `To`: Destination node
- `Flow Cost`: Cost associated with the flow
- `uo`: Unit operation type (e.g., `"PFR"`, `"CSTR"`, `"batch"`, `"none"`)

### Simulation Data (`simulation/data/capex_coeff.csv` & `simulation/data/raw_material_cost.csv`)

Tracked simulation cost tables include unit-operation CAPEX correlation coefficients (`simulation/data/capex_coeff.csv`) and raw material prices (`simulation/data/raw_material_cost.csv`). Downstream simulation summary tables generated by `simulation/code/process_results.py` and `simulation/code/data_organizer.py` contain:

- `Combination`: Configuration string
- `Best Objective Value`: Simulation objective value
- `Evaluation Time`: Simulation evaluation time
- `Total_CAPEX`: Capital expenditure

## Contributing

When contributing to this codebase:

1. Follow the existing code style and conventions
2. Add type hints for new functions
3. Include comprehensive docstrings
4. Add tests for new functionality
5. Update documentation as needed

## References

1. Daniel Casas-Orozco, Daniel J. Laky, Vivian Wang, Mesfin Abdi, Xin Feng, Erin Wood, Gintaras V. Reklaitis, and Zoltan K. Nagy. Techno-economic analysis of dynamic, end-to-end optimal pharmaceutical campaign manufacturing using pharmapy. *AIChE Journal*, 69(9), 2023.

2. Daniel J. Laky, Daniel Casas-Orozco, Carl D. Laird, Gintaras V. Reklaitis, and Zoltan K. Nagy. Simulation-optimization framework for the digital design of pharmaceutical processes using pyomo and pharmapy. *Industrial and Engineering Chemistry Research*, 61: 16128–16140, 2022.

3. Barhate Y, Laky DJ, Casas-Orozco D, Reklaitis GV, Nagy ZK. Hybrid rule-based and optimization-driven framework for the synthesis of end-to-end optimal pharmaceutical processes. *AIChE J.* 2025;e18888. doi:10.1002/aic.18888

## License

This project is licensed under the MIT License — see [`../LICENSE`](../LICENSE) for details. Please refer to the original references for proper attribution.
