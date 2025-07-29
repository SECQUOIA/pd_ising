# Dependencies Documentation

This document describes the dependencies for the IL-RXTOR-SEP-OPT project, which uses both Julia and Python.

## Julia Dependencies

The Julia dependencies are managed through `Project.toml` and `Manifest.toml` files.

### Core Dependencies (Project.toml)

- **CSV**: Data import/export functionality
- **DWave**: D-Wave quantum computing interface
- **DataFrames**: Data manipulation and analysis
- **GAMS**: General Algebraic Modeling System interface
- **Gurobi**: Mathematical optimization solver interface
- **JSON**: JSON data format handling
- **JuMP**: Julia for Mathematical Programming
- **LaTeXStrings**: LaTeX string formatting for plots
- **MathOptInterface**: Mathematical optimization interface
- **Plots**: Plotting and visualization
- **PseudoBooleanOptimization**: Pseudo-Boolean optimization
- **QCIOpt**: QCI optimization interface
- **QUBO**: Quadratic Unconstrained Binary Optimization
- **QUBOTools**: QUBO manipulation tools
- **ToQUBO**: QUBO conversion utilities

### Installation

To install Julia dependencies:

```bash
julia --project=. -e 'using Pkg; Pkg.instantiate()'
```

## Python Dependencies

The Python dependencies are managed through `requirements.txt` and `pyproject.toml` files.

### Core Dependencies

#### Scientific Computing
- **numpy>=1.21.0**: Numerical computing
- **pandas>=1.3.0**: Data manipulation and analysis
- **matplotlib>=3.5.0**: Plotting and visualization

#### Quantum Computing
- **dimod>=0.12.0**: Binary quadratic model handling
- **dwave-system>=1.0.0**: D-Wave quantum computing system
- **dwave-networkx>=0.8.0**: Network analysis for quantum computing
- **neal>=0.5.0**: Simulated annealing sampler
- **qci-client>=0.1.0**: QCI quantum computing client

#### Optimization
- **pyomo>=6.0.0**: Python Optimization Modeling Objects

#### Network Analysis
- **networkx>=2.6.0**: Network analysis and graph algorithms

### Optional Dependencies

#### Development (dev)
- **pytest>=6.0**: Testing framework
- **black>=21.0**: Code formatting
- **flake8>=3.8**: Linting
- **mypy>=0.910**: Type checking

#### Documentation (docs)
- **sphinx>=4.0**: Documentation generator
- **sphinx-rtd-theme>=1.0**: Read the Docs theme

### Installation

#### Using pip with requirements.txt:
```bash
pip install -r requirements.txt
```

#### Using pip with pyproject.toml:
```bash
pip install -e .
```

#### Installing with optional dependencies:
```bash
# Development dependencies
pip install -e ".[dev]"

# Documentation dependencies
pip install -e ".[docs]"

# Both
pip install -e ".[dev,docs]"
```

## Environment Setup

### Recommended Setup

1. **Create a virtual environment for Python:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Julia dependencies:**
   ```bash
   julia --project=. -e 'using Pkg; Pkg.instantiate()'
   ```

### Conda Environment (Alternative)

You can also use conda for Python dependency management:

```bash
conda create -n il-rxtor-sep-opt python=3.9
conda activate il-rxtor-sep-opt
pip install -r requirements.txt
```

## Version Compatibility

- **Python**: >=3.8
- **Julia**: 1.11.5 (as specified in Manifest.toml)

## Notes

- The project uses both Julia and Python for different aspects of the optimization pipeline
- Julia handles the core mathematical optimization and QUBO formulation
- Python handles data processing, visualization, and quantum computing interfaces
- Both languages can interact through file-based data exchange

## Troubleshooting

### Common Issues

1. **Julia package installation fails:**
   - Ensure you're using Julia 1.11.5 or compatible version
   - Try `julia --project=. -e 'using Pkg; Pkg.resolve()'`

2. **Python package conflicts:**
   - Use a virtual environment
   - Check for conflicting package versions in your global environment

3. **D-Wave dependencies:**
   - Some D-Wave packages may require specific authentication setup
   - Refer to D-Wave documentation for API key configuration

### Getting Help

- Check the individual package documentation for specific issues
- Ensure all dependencies are compatible with your system architecture
- Consider using the exact versions specified in the lock files for reproducible environments 