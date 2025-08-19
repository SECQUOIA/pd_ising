# Flowsheet Optimization for Drug Substance Manufacturing

This directory contains implementations of flowsheet optimization for pharmaceutical manufacturing processes, including both Integer Programming (IP) and Quantum Unconstrained Binary Optimization (QUBO) approaches.

## Files
### Core Files

1. **`ds_mfg_utils.py`** - Common utility functions used across the optimization framework
2. **`flst_opti_IP.py`** - Main IP implementation with enhanced features and iterative solution finding
3. **`flst_opti_QUBO.ipynb`** - Jupyter notebook implementing QUBO-based optimization
4. **`ds_mfg_plotting.py`** - Plotting and visualization utilities for optimization results
5. **`convert_to_qubo.jl`** - Julia script for QUBO conversion
6. **`README.md`** - This documentation file

### Data and Results

- **`data/`** - Directory containing flowsheet data files
- **`result_raw/`** - Directory for storing optimization results
- **`julia_exports/`** - Directory for Julia-related exports
- **`flowsheet_opti_simple.mps`** - MPS format model file


## Installation and Dependencies

### Required Packages

```bash
pip install pyomo pandas numpy matplotlib networkx
```

### Optional Dependencies

```bash
pip install gurobipy  # For Gurobi solver
pip install dwave-ocean-sdk  # For quantum computing features
pip install neal  # For simulated annealing
```

## Data Format

### Flowsheet Data (CSV)

The flowsheet data should be in CSV format with the following columns:

- `Flow`: Flow identifier (e.g., "f01", "f02")
- `From`: Source node
- `To`: Destination node
- `Flow Cost`: Cost associated with the flow
- `uo`: Unit operation type (e.g., "PFR", "CSTR", "batch", "none")

### Simulation Data (CSV)

Optional simulation data for comparison should include:

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

1. Daniel Casas-Orozco, Daniel J. Laky, Vivian Wang, Mesfin Abdi, Xin Feng, Erin Wood, Gintaras V. Reklaitis, and Zoltan K. Nagy. Techno-economic analysis of dynamic, end-to-end optimal pharmaceutical campaign manufacturing using pharmapy. AIChE Journal, 69, 9, 2023.

2. Daniel J. Laky, Daniel Casas-Orozco, Carl D. Laird, Gintaras V. Reklaitis, and Zoltan K. Nagy. Simulation-optimization framework for the digital design of pharmaceutical processes using pyomo and pharmapy. Industrial and Engineering Chemistry Research, 61: 16128–16140, 11 2022.

3. Barhate Y, Laky DJ, Casas-Orozco D, Reklaitis GV, Nagy ZK. Hybrid rule-based and optimization-driven framework for the synthesis of end-to-end optimal pharmaceutical processes. AIChE J. 2025;e18888. doi:10.1002/aic.18888

## License

This code is provided for research and educational purposes. Please refer to the original references for proper attribution. 