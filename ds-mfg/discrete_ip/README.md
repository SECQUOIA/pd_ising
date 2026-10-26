# DSMFG Discrete IP and QUBO Optimization (`ds-mfg/discrete_ip/`)

This directory contains the discrete integer programming (IP) and quadratic unconstrained binary optimization (QUBO) workflows for the drug-substance manufacturing flowsheet case study.

## Contents

- `flst_opti_IP.py` & `flst_opti_IP.ipynb` — Pyomo/Gurobi discrete IP formulation, iterative no-good cuts, and Pareto comparison against downstream simulation results.
- `solve_gurobi_pool.py` & `ds_mfg_discrete_IP_poolsearch.ipynb` — Gurobi solution-pool search and replicate confidence-interval analysis.
- `convert_to_qubo.jl` — Julia (`JuMP` / `ToQUBO.jl` / `QUBOTools.jl`) script exporting the MPS model (`flowsheet_opti_simple.mps`) to `julia_exports/`.
- `flst_opti_QUBO.ipynb` — QUBO sampling and feasibility comparison across simulated annealing (SA), D-Wave quantum annealing (QA), and QCi Dirac entropy computing (EC).
- `ds_mfg_utils.py` & `ds_mfg_plotting.py` — Shared solver, post-processing, and plotting utilities.
- `data/ssopt_gen_1.csv` — Flowsheet arc and unit-operation cost table.
- `julia_exports/` — Committed QUBO exports (`Q_matrix.csv`, `L_vector.csv`, `scalars.csv`).
- `result_gurobi/` — Committed Gurobi no-good-cut and solution-pool JSON records (including `replicates/`).
- `result_raw/` — Committed SA, D-Wave QA, and QCi EC JSON records.
