# IL-RXTOR-SEP-OPT: Ionic Liquid Reactor-Separator Network Optimization

A comprehensive optimization framework for ionic liquid selection and configuration of reactor-separator networks using both classical and quantum computing approaches.

## Overview

This project implements and compares multiple optimization approaches for the design of ionic liquid reactor-separator networks:

- **Mixed Integer Programming (MIP)**: Classical optimization of the original problem using Gurobi solver
- **Discrete Integer Programming (IP)**: Formulation of discrete component of MIP 
- **Quadratic Unconstrained Binary Optimization (QUBO)**: QUBO reformulation of IP to implement SA and QA 
- **Quantum Annealing**: D-Wave quantum computing implementation
- **Simulated Annealing**: Classial annealing approach using D-Wave neal 

## Citation

This work is based on the research paper:

> Iftakher, A., & Hasan, M. M. F. (2024). Exploring quantum optimization for computer-aided Molecular and Process Design. Systems and Control Transactions, 3, 292–299.
> 
> https://psecommunity.org/LAPSE:2024.1540

## Project Structure

```
il-rxtor-sep-opt/
├── data/                       # Input data files
│   ├── parameter_alpha.csv     # Reactor conversion factors
│   ├── parameter_beta.csv      # Separator separation factors
│   └── parameter_cost.csv      # Cost parameters
├── discrete_ip/                # Discrete IP implementation
│   ├── result_gurobi/          # Gurobi solver results
│   └── ilrs_discrete_IP.jl     # Julia discrete IP formulation
├── discrete_qubo/              # Discrete QUBO implementation
│   ├── julia_exports/          # Julia-generated QUBO files
│   ├── result_raw/             # Raw optimization results
│   └── ilrs_qubo.ipynb         # Jupyter notebook for QUBO analysis
├── original_mip/               # Original MIP implementation
│   ├── ilrs_MIP.py             # Python MIP implementation
│   ├── ilrs_MIP_julia.ipynb    # Julia MIP notebook
│   └── ifthaker.jl             # Encoding method from original paper
├── ilrs_common.py              # Common utilities and other functions
├── ilrs_plotting.py            # Visualization and plotting functions
├── ilrs_utils.jl               # Julia utility functions
└── [dependency files]          # Project.toml, requirements.txt, etc.
```


## Quick Start

### Prerequisites
- **Python**: 3.8 or higher
- **Julia**: 1.11.5 or higher
- **D-Wave Ocean SDK**: For quantum annealing (optional)
- **Gurobi**: For MIP optimization (optional)

### Installation

#### Automated Setup (Recommended)
```bash
# Clone the repository
git clone <repository-url>
cd il-rxtor-sep-opt

# Run the automated setup script
./setup_dependencies.sh
```

#### Manual Setup

**Python Dependencies:**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# OR
pip install -e .
```

**Julia Dependencies:**
```bash
julia --project=. -e 'using Pkg; Pkg.instantiate()'
```

**Conda Alternative:**
```bash
conda env create -f environment.yml
conda activate il-rxtor-sep-opt
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

## Documentation
- **DEPENDENCIES.md**: Detailed dependency information and setup
- **Jupyter Notebooks**: Interactive examples and tutorials
- **Code Comments**: Comprehensive inline documentation

## License
This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments
- Original research by Iftakher & Hasan (2024)
- D-Wave Systems for quantum computing infrastructure
- Gurobi for optimization solver
- The quantum computing and optimization communities

## Support
For questions and support:
- Check the documentation in `DEPENDENCIES.md`
- Review the Jupyter notebooks for examples
- Open an issue for bugs or feature requests
