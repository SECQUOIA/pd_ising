# IL-RXTOR-SEP-OPT: Ionic Liquid Reactor-Separator Network Optimization

A comprehensive optimization framework for ionic liquid selection and configuration of reactor-separator networks using both classical and quantum computing approaches.

## Overview

This project implements and compares multiple optimization approaches for the design of ionic liquid reactor-separator networks:

- **Mixed Integer Programming (MIP)**: Classical optimization of the original problem using Gurobi solver
- **Discrete Integer Programming (IP)**: Formulation of discrete component of MIP
- **Quadratic Unconstrained Binary Optimization (QUBO)**: QUBO reformulation of IP to implement SA, QA, and EC
- **Quantum Annealing (QA)**: D-Wave quantum computing implementation
- **Simulated Annealing (SA)**: Classical annealing approach using D-Wave `neal`

## Citation

This work is based on the research paper:

> Iftakher A, Hasan MMF. Exploring Quantum Optimization for Computer-aided Molecular and Process Design. Systems and Control Transactions 3:292-299 (2024) https://doi.org/10.69997/sct.143809

## Project Structure

```
il-rxtor-sep-opt/
├── data/                                    # Input data files
│   ├── parameter_alpha.csv                  # Reactor conversion factors
│   ├── parameter_beta.csv                   # Separator separation factors
│   └── parameter_cost.csv                   # Cost parameters
├── discrete_ip/                             # Discrete IP and Gurobi pool-search implementation
│   ├── result_gurobi/                       # Gurobi solver and replicate pool-search results
│   ├── ilrs_discrete_IP.jl                  # Julia discrete IP formulation and QUBO export
│   ├── solve_gurobi_poolsearch_funcs.py     # Python Gurobi solution-pool solver and CI analysis
│   └── ilrs_discrete_IP_poolsearch.ipynb    # Notebook for Gurobi pool search and replicate plots
├── discrete_qubo/                           # Discrete QUBO implementation
│   ├── julia_exports/                       # Julia-generated QUBO files (Q_matrix_1.csv, L_vector_1.csv, scalars_1.csv)
│   ├── result_raw/                          # Raw SA, D-Wave QA, and QCi EC optimization results
│   └── ilrs_qubo.ipynb                      # Jupyter notebook for QUBO sampling and feasibility analysis
├── original_mip/                            # Original MINLP/MIP implementation
│   ├── ilrs_MIP.py                          # Python Pyomo/Gurobi MIP implementation
│   ├── ilrs_MIP_julia.ipynb                 # Julia JuMP/QUBO.jl MIP notebook
│   ├── evaluate_all_configs.jl              # Julia CLI script evaluating all discrete configurations
│   └── ifthaker.jl                          # Custom binary encoding method from original paper
├── ilrs_common.py                           # Common Python utilities, samplers, and post-processing
├── ilrs_helper_fn.py                        # Additional helper functions for ILRS workflows
├── ilrs_plotting.py                         # Visualization and plotting functions
├── ilrs_utils.jl                            # Shared Julia model-building and QUBO utility functions
├── pixi.toml                                # Pixi environment definition (Python 3.12 + juliaup)
├── pixi.lock                                # Locked Conda and PyPI package versions
├── Project.toml                             # Julia project dependencies and [compat] bounds
├── Manifest.toml                            # Locked Julia 1.11.5 package versions
├── DEPENDENCIES.md                          # Detailed dependency documentation
├── setup_dependencies.sh                    # Automated setup script
└── README.md                                # This file
```

## Quick Start

### Prerequisites
- **[Pixi](https://pixi.sh/)**: Environment manager locking Python `3.12`, Conda, and PyPI packages via `pixi.toml` / `pixi.lock`
- **Julia**: `1.11.5` (pinned in `Project.toml` / `Manifest.toml`; can be provisioned via `pixi run setup-julia`)
- **D-Wave Ocean SDK**: Included in `pixi.toml`; requires a D-Wave API token for live quantum hardware runs (optional)
- **Gurobi**: `12.0.3` (`gurobipy == 12.0.3` and `Gurobi.jl == 1.7.0` / `Gurobi_jll == 12.0.3`); requires a Gurobi license for MIP/IP solves

### Installation

#### Automated Setup (Recommended)
```bash
# Clone the repository
git clone https://github.com/SECQUOIA/pd_ising.git
cd pd_ising/il-rxtor-sep-opt

# Run the automated setup script (installs pixi environment and instantiates Julia packages)
./setup_dependencies.sh
```

#### Manual Setup

**Python & Conda Dependencies (`pixi`):**
```bash
cd il-rxtor-sep-opt
pixi install
pixi run verify-python
```

**Julia Dependencies (`Project.toml` / `Manifest.toml`):**
```bash
cd il-rxtor-sep-opt
julia --project=. -e 'using Pkg; Pkg.instantiate(); Pkg.status()'
# Or if Julia 1.11.5 is not yet installed:
pixi run setup-julia
```

**Verify CLI Entrypoint:**
```bash
julia --project=. original_mip/evaluate_all_configs.jl --help
```

## Configuration

### D-Wave Configuration
To use quantum annealing, set up your D-Wave credentials:
```bash
export DWAVE_API_TOKEN="your-dwave-api-token"
export DWAVE_API_URL="https://cloud.dwavesys.com/sapi"
```

### QCI Configuration
To use QCI quantum computing services:
```bash
export QCI_API_TOKEN="your-qci-api-token"
```

### Gurobi Configuration
For MIP optimization, ensure Gurobi is properly licensed and configured.

## Results and Analysis
The framework provides comprehensive analysis tools:

- **Performance Comparison**: Time-to-solution across all methods
- **Solution Quality**: Energy distributions and feasibility analysis
- **Scalability Analysis**: Performance with problem size
- **Visualization**: Interactive plots and result summaries

## Contributing

We welcome pull requests with extensions and improvements! This project is designed to be extensible for various optimization approaches and quantum computing applications.

### Areas for Extensions

- **New Optimization Solvers**: Integration with additional quantum annealers or classical solvers
- **Alternative Problem Formulations**: Different mathematical formulations for reactor-separator optimization
- **Enhanced Analysis Tools**: Additional visualization and performance analysis capabilities
- **Multi-objective Optimization**: Extensions to handle multiple competing objectives
- **Real-time Optimization**: Integration with real-time process control systems
- **Machine Learning Integration**: Hybrid approaches combining optimization with ML techniques

### How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-extension`)
3. Implement your extension with appropriate documentation
4. Add tests if applicable
5. Update the documentation to reflect your changes
6. Commit your changes (`git commit -m 'Add your extension description'`)
7. Push to the branch (`git push origin feature/your-extension`)
8. Open a Pull Request with a clear description of your extension

### Code Style

- Follow the existing code style and conventions
- Add comprehensive docstrings for new functions
- Include example usage in Jupyter notebooks when appropriate
- Update dependency files (`pixi.toml` / `Project.toml`) if new packages are required

## Documentation
- **[REPRODUCE.md](../REPRODUCE.md)**: Figure-to-code and result provenance mapping. Note that Jupyter notebook outputs are retained deliberately as part of the recorded results.
- **[DEPENDENCIES.md](DEPENDENCIES.md)**: Detailed dependency information and setup
- **Jupyter Notebooks**: Interactive examples and tutorials (`discrete_qubo/ilrs_qubo.ipynb`, `discrete_ip/ilrs_discrete_IP_poolsearch.ipynb`, `original_mip/ilrs_MIP_julia.ipynb`)
- **Code Comments**: Comprehensive inline documentation

## License
This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

## Acknowledgments
- Original research by Iftakher & Hasan (2024)
- D-Wave Systems for quantum computing infrastructure
- Gurobi for optimization solver
- The quantum computing and optimization communities

## Support
For questions and support:
- Check the documentation in [`DEPENDENCIES.md`](DEPENDENCIES.md)
- Review the Jupyter notebooks for examples
- Open an issue for bugs or feature requests
