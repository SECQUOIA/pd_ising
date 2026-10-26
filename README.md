# PD_ISING: Process Design Optimization using Ising Models

A comprehensive repository for process design optimization using both classical and quantum computing approaches. This project contains case studies for pharmaceutical manufacturing flowsheet optimization and ionic liquid reactor-separator network optimization.

## Overview

This repository provides optimization frameworks for process design problems, comparing various optimization methods in solving integer/qubo-ising problems, including branch and bound, simulated annealing,quantum computing, and entropy computing approaches.

### Subprojects

1. **`ds-mfg/`** - Flowsheet Optimization for Drug Substance Manufacturing
   - Pharmaceutical manufacturing process optimization
   - See [`ds-mfg/README.md`](ds-mfg/README.md) for detailed documentation

2. **`il-rxtor-sep-opt/`** - Ionic Liquid Reactor-Separator Network Optimization
   - Quantum Annealing and Simulated Annealing implementations
   - See [`il-rxtor-sep-opt/README.md`](il-rxtor-sep-opt/README.md) for detailed documentation

## Project Structure

```
pd_ising/
├── ds-mfg/                      # Drug Substance Manufacturing Flowsheet Optimization
│   ├── discrete_ip/             # Discrete IP and QUBO implementation
│   │   ├── data/                # Flowsheet data files
│   │   ├── julia_exports/       # Exported QUBO matrices and vectors
│   │   ├── result_gurobi/       # Gurobi branch-and-bound and pool results
│   │   └── result_raw/          # Simulated, quantum, and entropy annealing results
│   ├── simulation/              # Simulation code and results
│   │   ├── code/                # PharmaPy and NOMAD simulation scripts
│   │   └── data/                # Simulation bounds, compound, and configuration data
│   ├── images/                  # Flowsheet diagrams
│   └── README.md                # Detailed documentation
├── il-rxtor-sep-opt/            # Ionic Liquid Reactor-Separator Network Optimization
│   ├── discrete_ip/             # Discrete IP implementation
│   ├── discrete_qubo/           # Discrete QUBO implementation
│   ├── original_mip/            # Original MIP implementation
│   ├── data/                    # Input data files
│   └── README.md                # Detailed documentation
├── REPRODUCE.md                 # Figure-to-code and result provenance mapping
├── LICENSE                      # MIT License
└── README.md                    # This file
```

## Quick Start

### Prerequisites

- **Python**: 3.8 or higher
- **Julia**: 1.11.5 or higher (for some subprojects)
- **D-Wave Ocean SDK**: For quantum annealing (optional)
- **Gurobi**: For MIP/IP optimization (optional)

### Installation

Each subproject has its own installation instructions. Please refer to the respective README files:

- **ds-mfg**: See [`ds-mfg/README.md`](ds-mfg/README.md) for installation details
- **il-rxtor-sep-opt**: See [`il-rxtor-sep-opt/README.md`](il-rxtor-sep-opt/README.md) for installation details

### Common Dependencies

Most subprojects require:

```bash
pip install pyomo pandas numpy matplotlib 
```

For annealing features:
```bash
pip install dwave-ocean-sdk neal
```

For quadratic unconstrained binary optimization (qubo) features: 
- Please refer to https://github.com/JuliaQUBO/QUBO.jl


## Configuration

### D-Wave Configuration
To use quantum annealing features:
```bash
export DWAVE_API_TOKEN="your-dwave-api-token"
export DWAVE_API_URL="https://cloud.dwavesys.com/sapi"
```

### QCI Configuration
To use QCI entropy computing services:
```bash
export QCI_API_TOKEN="your-qci-api-token"
```

### Gurobi Configuration
For MIP/IP optimization, ensure Gurobi is properly licensed and configured.

## Contributing

We welcome contributions and extensions to this repository! Each subproject has specific contribution guidelines. 

### General Contribution Guidelines

1. Follow the existing code style and conventions
2. Add comprehensive docstrings for new functions
3. Include type hints where applicable
4. Update documentation as needed
5. Add tests for new functionality when appropriate

## Documentation

- **[REPRODUCE.md](REPRODUCE.md)**: Maps each figure and result table to the notebook/script and stored result files that produced it. Stored notebook outputs are retained deliberately as part of the recorded experimental record.
- **Subproject READMEs**: Each subproject contains detailed documentation (`ds-mfg/README.md`, `ds-mfg/discrete_ip/README.md`, `il-rxtor-sep-opt/README.md`)
- **Jupyter Notebooks**: Interactive examples and tutorials in subprojects
- **Code Comments**: Comprehensive inline documentation throughout

## References

### Drug Substance Manufacturing

1. Casas-Orozco, D., Laky, D. J., Wang, V., Abdi, M., Feng, X., Wood, E., Reklaitis, G. V., & Nagy, Z. K. (2023). Techno-economic analysis of dynamic, end-to-end optimal pharmaceutical campaign manufacturing using pharmapy. *AIChE Journal*, 69(9).

2. Laky, D. J., Casas-Orozco, D., Laird, C. D., Reklaitis, G. V., & Nagy, Z. K. (2022). Simulation-optimization framework for the digital design of pharmaceutical processes using pyomo and pharmapy. *Industrial and Engineering Chemistry Research*, 61, 16128–16140.

3. Barhate, Y., Laky, D. J., Casas-Orozco, D., Reklaitis, G. V., & Nagy, Z. K. (2025). Hybrid rule-based and optimization-driven framework for the synthesis of end-to-end optimal pharmaceutical processes. *AIChE J.*, e18888. doi:10.1002/aic.18888

### Ionic Liquid Reactor-Separator Optimization

Iftakher, A., & Hasan, M. M. F. (2024). Exploring Quantum Optimization for Computer-aided Molecular and Process Design. *Systems and Control Transactions*, 3, 292-299. https://doi.org/10.69997/sct.143809

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details. Please also refer to the original case-study references for proper attribution.

## Support

For questions and support:
- Check the documentation in subproject README files
- Review the Jupyter notebooks for examples
- Open an issue for bugs or feature requests

## Acknowledgments

- Original research authors cited in References
- D-Wave Systems for quantum computing infrastructure
- QCi for entropy computing infrastructure
- Gurobi for optimization solver
- The quantum computing and optimization communities
