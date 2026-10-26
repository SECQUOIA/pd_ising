# Reproducibility and Figure Provenance (`REPRODUCE.md`)

This document maps each figure and result table in the `pd_ising` case studies to the exact notebook or script cell and committed input files that produced it.

> **Retained notebook outputs:** Stored outputs inside the committed `.ipynb` notebooks are retained deliberately as part of the experimental record (hardware-backed sampler runs and licensed Gurobi solves). Do not strip or re-execute cells over the committed records unless deliberately recording a new experiment.

## Figure and Table Provenance Map

| Figure / Analysis Output | Produced by | Input Result / Data Files |
| :--- | :--- | :--- |
| **ILRS QUBO feasibility & objective distribution (`plot_multibar_graph_discrete`)** | `il-rxtor-sep-opt/discrete_qubo/ilrs_qubo.ipynb` (cells loading `result_raw` and calling `plot_multibar_graph_discrete` from `il-rxtor-sep-opt/ilrs_plotting.py`) | `il-rxtor-sep-opt/discrete_qubo/julia_exports/Q_matrix_1.csv`, `il-rxtor-sep-opt/discrete_qubo/julia_exports/L_vector_1.csv`, `il-rxtor-sep-opt/discrete_qubo/julia_exports/scalars_1.csv`, `il-rxtor-sep-opt/discrete_qubo/result_raw/SA_results_20260114_163501.json`, `il-rxtor-sep-opt/discrete_qubo/result_raw/Dwave_QA_results_20260626_161207.json`, `il-rxtor-sep-opt/discrete_qubo/result_raw/Dwave_QA_results_20260626_161210.json`, `il-rxtor-sep-opt/discrete_qubo/result_raw/QCI_EQC_results.json`, `il-rxtor-sep-opt/data/parameter_alpha.csv`, `il-rxtor-sep-opt/data/parameter_beta.csv`, `il-rxtor-sep-opt/data/parameter_cost.csv` |
| **ILRS Gurobi solution-pool replicate CI plot (`plot_pool_replicates_ci`)** | `il-rxtor-sep-opt/discrete_ip/ilrs_discrete_IP_poolsearch.ipynb` (calling `plot_pool_replicates_ci` in `il-rxtor-sep-opt/discrete_ip/solve_gurobi_poolsearch_funcs.py`) | `il-rxtor-sep-opt/discrete_ip/result_gurobi/ilrs_gpool_n228_20260126_101442.json`, `il-rxtor-sep-opt/discrete_ip/result_gurobi/optimization_results_2025-06-24.csv`, `il-rxtor-sep-opt/discrete_ip/result_gurobi/replicates/ilrs_gpool_n100_20260204_155730.json` … `il-rxtor-sep-opt/discrete_ip/result_gurobi/replicates/ilrs_gpool_n500_20260204_194637.json` (50 replicate JSON files across $N \in \{100, 150, 200, 252, 300, 500\}$) |
| **ILRS full-configuration MIP evaluation (`evaluate_all_configs.jl`)** | `il-rxtor-sep-opt/original_mip/evaluate_all_configs.jl` and `il-rxtor-sep-opt/original_mip/ilrs_MIP_julia.ipynb` | `il-rxtor-sep-opt/data/parameter_alpha.csv`, `il-rxtor-sep-opt/data/parameter_beta.csv`, `il-rxtor-sep-opt/data/parameter_cost.csv` |
| **DSMFG flowsheet diagrams** | Static flowsheet figures in `ds-mfg/images/` | `ds-mfg/images/ds_schematic.jpg`, `ds-mfg/images/ds_opt_flowsheet.jpg` |
| **DSMFG IP vs. downstream simulation Pareto front (`plot_pareto_front`)** | `ds-mfg/discrete_ip/flst_opti_IP.ipynb` (calling `plot_pareto_front` in `ds-mfg/discrete_ip/ds_mfg_plotting.py` and `ds-mfg/discrete_ip/flst_opti_IP.py`) | `ds-mfg/discrete_ip/data/ssopt_gen_1.csv`, `ds-mfg/simulation/data/obj_mass_prod_crys/run_objmassprodcrys_sum.csv`, `ds-mfg/discrete_ip/result_gurobi/gurobi_nogoodcuts_results_20260123_151347.json`, `ds-mfg/discrete_ip/result_gurobi/gurobi_pool_solutions_n36_20260126_105706.json` |
| **DSMFG Gurobi solution-pool replicate CI plot (`plot_pool_replicates_ci`)** | `ds-mfg/discrete_ip/ds_mfg_discrete_IP_poolsearch.ipynb` (calling `plot_pool_replicates_ci` in `ds-mfg/discrete_ip/solve_gurobi_pool.py`) | `ds-mfg/discrete_ip/result_gurobi/gurobi_pool_solutions_n36_20260126_105706.json`, `ds-mfg/discrete_ip/result_gurobi/replicates/gurobi_pool_solutions_n5_20260204_164336_692422.json` … `ds-mfg/discrete_ip/result_gurobi/replicates/gurobi_pool_solutions_n80_20260204_190728_362895.json` (70 replicate JSON files across $N \in \{5, 10, 20, 30, 36, 40, 50, 80\}$) |
| **DSMFG QUBO feasibility & objective distribution (`plot_multibar_graph_discrete`)** | `ds-mfg/discrete_ip/flst_opti_QUBO.ipynb` (calling `plot_multibar_graph_discrete` in `ds-mfg/discrete_ip/ds_mfg_plotting.py`) | `ds-mfg/discrete_ip/julia_exports/Q_matrix.csv`, `ds-mfg/discrete_ip/julia_exports/L_vector.csv`, `ds-mfg/discrete_ip/julia_exports/scalars.csv`, `ds-mfg/discrete_ip/result_raw/SA_results_20250819_163847.json`, `ds-mfg/discrete_ip/result_raw/Dwave_QA_results_20260626_143653.json`, `ds-mfg/discrete_ip/result_raw/Dwave_QA_results_20260626_143707.json`, `ds-mfg/discrete_ip/result_raw/QCI_EQC_results.json`, `ds-mfg/discrete_ip/data/ssopt_gen_1.csv`, `ds-mfg/simulation/data/obj_mass_prod_crys/run_objmassprodcrys_sum.csv` |

## End-to-End Walkthrough (Tracing One Row)

To reproduce the **ILRS QUBO feasibility & objective distribution** from the committed records without submitting live hardware jobs:

1. **QUBO coefficients (`julia_exports/`)**:
   - Exported from the Julia model (`il-rxtor-sep-opt/discrete_ip/ilrs_discrete_IP.jl` and `il-rxtor-sep-opt/ilrs_utils.jl`) into `il-rxtor-sep-opt/discrete_qubo/julia_exports/{Q_matrix_1,L_vector_1,scalars_1}.csv`.
2. **Recorded solver runs (`result_raw/`)**:
   - `il-rxtor-sep-opt/discrete_qubo/ilrs_qubo.ipynb` loads the committed QUBO matrices (`cell 5`) and skips the live sampler cells (`cells 6–7`) when replaying from disk.
   - `cell 9` loads the four committed JSON records from `il-rxtor-sep-opt/discrete_qubo/result_raw/`:
     - `SA_results_20260114_163501.json` (simulated annealing)
     - `Dwave_QA_results_20260626_161207.json` (D-Wave Advantage)
     - `Dwave_QA_results_20260626_161210.json` (D-Wave Advantage2)
     - `QCI_EQC_results.json` (QCi Dirac)
3. **Feasibility filtering and figure rendering**:
   - Subsequent cells decode each bitstring against `il-rxtor-sep-opt/data/parameter_{alpha,beta,cost}.csv` and call `plot_multibar_graph_discrete(...)` (`cell 13`) to render the multi-bar feasibility comparison figure.

## Known Gaps in the Historical Record

1. **Saved figure paths vs. repository tree**:
   - `il-rxtor-sep-opt/discrete_qubo/ilrs_qubo.ipynb` (`cell 13`) and `ds-mfg/discrete_ip/flst_opti_QUBO.ipynb` include `fig.savefig('../../images/260115_ilrs_feas.svg', ...)` and `fig.savefig('../../images/260115_ds_mfg_feas.svg', ...)`, referencing a root `images/` directory (and historical `260115_*` / `260715_*` filenames) that is not committed to the repository; the rendered plots are instead stored inline inside the notebook output cells.
2. **Historical vs. active result files in `result_raw/`**:
   - Alongside the primary JSON files loaded by the notebooks, `il-rxtor-sep-opt/discrete_qubo/result_raw/` and `ds-mfg/discrete_ip/result_raw/` also retain earlier runs (`Dwave_QA_results_20251120_164900.json`, `SA_results_20251121_163831.json`, `SA_results_20260105_112307.json`, `Dwave_QA_results_1_20250819_114708.json`, `Dwave_QA_results_20251121_170656.json`, and `old_format/*.csv`), and local working trees may contain untracked experimental files. Always use the exact filenames listed in the table above.
3. **Incomplete provenance metadata on older result files**:
   - `QCI_EQC_results.json` (in both case studies) has no filename timestamp and no `meta` block.
   - `discrete_ip/result_gurobi/*.json` record a filename timestamp and timing fields, but do not embed solver version, random seed, or input SHA-256 hash.
   - `julia_exports/*.csv` were renamed manually from the export routine's date-stamped output (`Q_matrix_<date>.csv` → `Q_matrix_1.csv` or `Q_matrix.csv`), so the export scripts do not regenerate those exact filenames automatically.
   - For new result writers, follow the `run_info` schema in `il-rxtor-sep-opt/original_mip/evaluate_all_configs.jl` (`gurobi_version`, `gurobi_jl_version`, `jump_version`, `julia_version`, `solver_params`, input path, and input SHA-256).
