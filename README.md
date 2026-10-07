# PD_ISING: Process Design Optimization using Ising Models

Code, notebooks, and recorded results for comparing discrete process-design solvers in two case studies: ionic-liquid selection and reactor-separator network design (IL), and drug-substance manufacturing flowsheet design (DSMFG).

The discrete subproblems are solved with Gurobi branch-and-bound, including iterative no-good cuts and solution-pool searches, or reformulated as **quadratic unconstrained binary optimization (QUBO)** problems for simulated annealing (SA), D-Wave quantum annealing (QA), and QCi entropy computing (EC). Continuous optimization or simulation evaluates the selected configurations downstream. The discrete objective can rank configurations differently from the integrated process objective; this workflow does not guarantee a globally optimal integrated process design.

## Publication

Park, Y., & Bernal Neira, D. E. (2026). **A computational study of Ising-based solvers for discrete landscape exploration in process optimization.** *AIChE Journal*, e70656. [doi:10.1002/aic.70656](https://doi.org/10.1002/aic.70656). First published online September 24, 2026.

Please cite this article when using the study's code or results, together with the relevant case-study references below.

### Publication snapshot

Use commit **[`a2cb3124e07df04d984454034f913e33ef5adcfd`](https://github.com/SECQUOIA/pd_ising/tree/a2cb3124e07df04d984454034f913e33ef5adcfd)** (September 11, 2026) for the repository snapshot containing the QA data consistent with the published timing results. 


Recorded hardware runs are stochastic. New runs can produce different samples and timings. Preserve the committed results when performing new experiments.

## Repository Structure

```text
pd_ising/
├── ds-mfg/
│   ├── discrete_ip/             # Python IP and QUBO notebooks; Julia QUBO conversion
│   │   ├── data/                # Discrete flowsheet input
│   │   ├── julia_exports/       # Saved QUBO coefficients
│   │   ├── result_gurobi/       # Enumeration and solution-pool results
│   │   └── result_raw/          # Recorded SA, QA, and EC results
│   ├── simulation/
│   │   ├── code/               # PharmaPy simulation and NOMAD optimization
│   │   └── data/               # Cost coefficients
│   ├── images/                 # Flowsheet diagrams
│   ├── Project.toml
│   └── Manifest.toml
├── il-rxtor-sep-opt/
│   ├── data/                    # Conversion, separation, and cost parameters
│   ├── discrete_ip/             # Julia IP formulation and Gurobi pool notebook
│   ├── discrete_qubo/           # QUBO notebook, julia_exports/, and result_raw/
│   ├── original_mip/            # Original process-model implementations
│   ├── Project.toml
│   └── Manifest.toml
├── tests/                       # Credential-free QA helper regression tests
└── README.md
```

## Getting Started

This is a collection of research scripts and notebooks with separate Python and Julia environments. There is no single locked environment covering every workflow.

The article reports **Python 3.10.12** and **Julia 1.11**; both committed Julia manifests record **Julia 1.11.5**. The IL Python metadata declares Python >=3.8, but that declaration is not a verification that every dependency and workflow works across all newer versions.

### Python notebooks

A starting environment for the discrete optimization and analysis notebooks can be created from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install numpy pandas scipy matplotlib networkx pyomo gurobipy \
    dimod dwave-system dwave-neal dwave-networkx minorminer jupyterlab
jupyter lab
```

These commands list the external dependencies used by the notebooks and helpers; they are not a lockfile for the publication environment. The distribution providing `import neal` is [`dwave-neal`](https://pypi.org/project/dwave-neal/). Some shared helpers import Ocean packages and `gurobipy` when loaded, even when inspecting saved data. A Gurobi license is required to run its optimizations; D-Wave service access is required only when submitting QA jobs.

Run each notebook with its containing directory as the working directory, because imports and data paths are relative:

| Workflow | Entry point |
| --- | --- |
| DSMFG IP enumeration and downstream comparison | [flst_opti_IP.ipynb](ds-mfg/discrete_ip/flst_opti_IP.ipynb) |
| DSMFG Gurobi solution pool | [ds_mfg_discrete_IP_poolsearch.ipynb](ds-mfg/discrete_ip/ds_mfg_discrete_IP_poolsearch.ipynb) |
| DSMFG QUBO sampling and analysis | [flst_opti_QUBO.ipynb](ds-mfg/discrete_ip/flst_opti_QUBO.ipynb) |
| IL Gurobi solution pool | [ilrs_discrete_IP_poolsearch.ipynb](il-rxtor-sep-opt/discrete_ip/ilrs_discrete_IP_poolsearch.ipynb) |
| IL QUBO sampling and analysis | [ilrs_qubo.ipynb](il-rxtor-sep-opt/discrete_qubo/ilrs_qubo.ipynb) |
| IL original process model | [ilrs_MIP_julia.ipynb](il-rxtor-sep-opt/original_mip/ilrs_MIP_julia.ipynb) |

The QUBO notebooks mix solver-submission cells with cells that load existing results. To analyze recorded runs, use the saved-data sections and skip live solver calls.

### Julia models and QUBO conversion

Instantiate the environment for the case study you need, from the repository root:

```bash
julia --project=il-rxtor-sep-opt -e 'using Pkg; Pkg.instantiate()'
julia --project=ds-mfg -e 'using Pkg; Pkg.instantiate()'
```

The IL discrete model is in [ilrs_discrete_IP.jl](il-rxtor-sep-opt/discrete_ip/ilrs_discrete_IP.jl). DSMFG conversion is in [convert_to_qubo.jl](ds-mfg/discrete_ip/convert_to_qubo.jl). Both use the QUBO.jl ecosystem. Saved coefficient files are available under each discrete workflow's `julia_exports/` directory for analysis without regenerating them.

### Services and downstream simulation

- **D-Wave:** configure Ocean with `DWAVE_API_TOKEN` or its configuration file. If overriding the service URL, the supported variable is `DWAVE_API_ENDPOINT`; see the [D-Wave configuration documentation](https://docs.dwavequantum.com/en/latest/ocean/api_ref_cloud/configuration.html). The notebooks also contain credential-setting cells; review these before running them.
- **QCi:** the Python EC helpers use `qci_client`, read `QCI_API_TOKEN`, and submit to the `dirac-1` device. The article reports client version 4.5.0. Live runs require the client and access to a compatible service; reading stored JSON results does not.
- **Gurobi:** configure a valid license for the Python or Julia solver interface used by the selected workflow.
- **DSMFG simulation:** [simulation/code/](ds-mfg/simulation/code/) uses PharmaPy and PyNomad in addition to the discrete-workflow dependencies. Its [environment.yml](ds-mfg/simulation/code/environment.yml) is a historical Linux/Python 3.9.19 export with a placeholder environment name and an absolute local prefix, so it needs adaptation for another machine.

### Existing setup limitations

The subproject READMEs provide additional context, but their setup instructions need care:

- The IL `requirements.txt` lists standard-library modules (`pprint`, `collections`, `time`, `os`, and `ast`) as installable dependencies. Its requirements, Python project metadata, and Conda file also use `neal` instead of the `dwave-neal` distribution name. The automated setup script installs from the requirements and Python project metadata.
- The DSMFG conversion script writes dated QUBO exports to `ds-mfg/julia_exports/`, while its notebook reads the committed `Q_matrix.csv`, `L_vector.csv`, and `scalars.csv` in `ds-mfg/discrete_ip/julia_exports/`. Align the destination and filenames when regenerating coefficients.

For implementation details, see the [DSMFG README](ds-mfg/README.md), [IL README](il-rxtor-sep-opt/README.md), and the linked scripts and notebooks.

## Case-Study References

1. Casas-Orozco, D., Laky, D. J., Wang, V., Abdi, M., Feng, X., Wood, E., Reklaitis, G. V., & Nagy, Z. K. (2023). Techno-economic analysis of dynamic, end-to-end optimal pharmaceutical campaign manufacturing using PharmaPy. *AIChE Journal*, 69(9), e18142. [doi:10.1002/aic.18142](https://doi.org/10.1002/aic.18142).
2. Laky, D. J., Casas-Orozco, D., Laird, C. D., Reklaitis, G. V., & Nagy, Z. K. (2022). Simulation-optimization framework for the digital design of pharmaceutical processes using Pyomo and PharmaPy. *Industrial & Engineering Chemistry Research*, 61, 16128–16140. [doi:10.1021/acs.iecr.2c01636](https://doi.org/10.1021/acs.iecr.2c01636).
3. Barhate, Y., Laky, D. J., Casas-Orozco, D., Reklaitis, G. V., & Nagy, Z. K. (2025). Hybrid rule-based and optimization-driven framework for the synthesis of end-to-end optimal pharmaceutical processes. *AIChE Journal*, 71(9), e18888. [doi:10.1002/aic.18888](https://doi.org/10.1002/aic.18888).
4. Iftakher, A., & Hasan, M. M. F. (2024). Exploring Quantum Optimization for Computer-aided Molecular and Process Design. *Systems and Control Transactions*, 3, 292–299. [doi:10.69997/sct.143809](https://doi.org/10.69997/sct.143809).

## Contributing and Support

Use the relevant notebook and saved results to establish the behavior you are changing. Follow the existing code style, update documentation, and add regression coverage for behavioral fixes. Report bugs or questions through the repository's issues.

