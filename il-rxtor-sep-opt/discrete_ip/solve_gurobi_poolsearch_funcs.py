"""
This script contains functions supporting the PoolSearch feature of Gurobi when solving the IP problem for the discrete part of the Ionic Liquid Selection Program. 

The problem is described in ilrs_discrete_IP.jl.
See ilrs_discrete_IP_poolsearch.ipynb for running the model and analyzing the results.
"""
import os
import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
from pyomo.environ import (
    ConcreteModel, Var, Binary, Constraint, Objective, minimize,
    Set, Param, value, SolverFactory
)
from pyomo.opt import SolverStatus, TerminationCondition
from datetime import date, datetime
import gurobipy as grb
import tempfile

# ================== Functions for Running the Model ===================

def relabel_unit(u):
    """
    Relabel the unit variables.
    
    Parameters
    ----------
    u : str
        The unit variable (e.g., "r0", "s0")
    
    Returns
    -------
    str
        The relabeled unit variable (e.g., "r1", "s1")
    """
    prefix = u[0]
    index = int(u[1]) + 1
    return f"{prefix}{index}"

def import_data(data_filepath):
    """
    Import data from CSV files and return them as DataFrames.
    
    Parameters
    ----------
    data_filepath : str
        Path to the directory containing the CSV files
    
    Returns
    -------
    tuple
        (data_alpha, data_beta, data_cost) - Three pandas DataFrames
    """
    data_alpha = pd.read_csv(os.path.join(data_filepath, "parameter_alpha.csv"))
    data_beta = pd.read_csv(os.path.join(data_filepath, "parameter_beta.csv"))
    data_cost = pd.read_csv(os.path.join(data_filepath, "parameter_cost.csv"))
    
    # Relabel units (r0 -> r1, s0 -> s1, etc.)
    data_cost['unit'] = data_cost['unit'].apply(relabel_unit)
    data_cost = data_cost.sort_values('unit').reset_index(drop=True)
    
    return data_alpha, data_beta, data_cost

def build_discrete_ip_model(data_filepath, use_quad_constraints=True):
    """
    Builds the IP model for the discrete part of the Ionic Liquid Selection Program.
    
    Parameters
    ----------
    data_filepath : str
        Path to the data file directory
    use_quad_constraints : bool, optional
        Whether to use quadratic constraints. If False, the model uses linear constraints.
        Default is True.
    
    Returns
    -------
    tuple
        (m, vars_dict) where:
        - m: The Pyomo ConcreteModel
        - vars_dict: A dictionary of variable references
    """
    # === Import data ===
    data_alpha, data_beta, data_cost = import_data(data_filepath)
    num_reactors = data_alpha['reactor'].max()
    num_separators = data_beta['separator-k'].max()
    num_cation = data_beta['cation-c'].max()
    num_anion = data_beta['anion-a'].max()
    
    reactors = list(range(1, num_reactors + 1))
    separators = list(range(1, num_separators + 1))
    unit_keys = [f"r{i}" for i in reactors] + [f"s{j}" for j in separators]
    source = "srce"
    sink = "sink"
    
    # Create Pyomo model
    m = ConcreteModel()
    
    # === Variables ===
    m.y = Var(unit_keys, domain=Binary)
    m.z_cat = Var(range(1, num_cation + 1), domain=Binary)
    m.z_an = Var(range(1, num_anion + 1), domain=Binary)
    
    # Flow pairs
    flow_pairs = []
    for r in reactors:
        flow_pairs.append((source, f"r{r}"))
        for s in separators:
            flow_pairs.append((f"r{r}", f"s{s}"))
    for s in separators:
        flow_pairs.append((f"s{s}", sink))
    
    m.f = Var(flow_pairs, domain=Binary)
    
    # === Parameters ===
    alpha = {row['reactor']: row['alpha'] for _, row in data_alpha.iterrows()}
    beta = {
        (row['separator-k'], row['cation-c'], row['anion-a']): row['beta']
        for _, row in data_beta.iterrows()
    }
    
    cost_fixed = {row['unit']: row['fixed'] for _, row in data_cost.iterrows()}
    cost_oper = {row['unit']: row['operating'] for _, row in data_cost.iterrows()}
    cost_emiss = {row['unit']: row['emission'] for _, row in data_cost.iterrows()}
    
    # === Constraints ===
    # Connecting units to binary flow variables
    def flow_source_reactor_rule(m, r):
        return m.f[(source, f"r{r}")] == m.y[f"r{r}"]
    m.flow_source_reactor = Constraint(reactors, rule=flow_source_reactor_rule)
    
    def flow_separator_sink_rule(m, s):
        return m.f[(f"s{s}", sink)] == m.y[f"s{s}"]
    m.flow_separator_sink = Constraint(separators, rule=flow_separator_sink_rule)
    
    # At least one flow at sink
    def at_least_one_sink_rule(m):
        return sum(m.f[(f"s{s}", sink)] for s in separators) >= 1
    m.at_least_one_sink = Constraint(rule=at_least_one_sink_rule)
    
    # If reactor is selected, at least one flow out from the reactor
    def reactor_flow_out_rule(m, r):
        return (1 - m.f[(source, f"r{r}")]) + sum(m.f[(f"r{r}", f"s{s}")] for s in separators) >= 1
    m.reactor_flow_out = Constraint(reactors, rule=reactor_flow_out_rule)
    
    # If there is flow out of separator, there is at least one inflow into separator
    def separator_flow_in_rule(m, s):
        return (1 - m.f[(f"s{s}", sink)]) + sum(m.f[(f"r{r}", f"s{s}")] for r in reactors) >= 1
    m.separator_flow_in = Constraint(separators, rule=separator_flow_in_rule)
    
    # === One IL selection constraint ===
    def one_cation_rule(m):
        return sum(m.z_cat[c] for c in range(1, num_cation + 1)) == 1
    m.one_cation = Constraint(rule=one_cation_rule)
    
    def one_anion_rule(m):
        return sum(m.z_an[a] for a in range(1, num_anion + 1)) == 1
    m.one_anion = Constraint(rule=one_anion_rule)
    
    # Define new variables, w, to represent the product of z_cat and z_an
    # Linearization: w[i,j] = z_cat[i] * z_an[j] for binary variables
    m.w = Var(range(1, num_cation + 1), range(1, num_anion + 1), domain=Binary)
    
    def w_product_rule1(m, i, j):
        return m.w[i, j] <= m.z_cat[i]
    m.w_product1 = Constraint(
        range(1, num_cation + 1), 
        range(1, num_anion + 1), 
        rule=w_product_rule1
    )
    
    def w_product_rule2(m, i, j):
        return m.w[i, j] <= m.z_an[j]
    m.w_product2 = Constraint(
        range(1, num_cation + 1), 
        range(1, num_anion + 1), 
        rule=w_product_rule2
    )
    
    def w_product_rule3(m, i, j):
        return m.w[i, j] >= m.z_cat[i] + m.z_an[j] - 1
    m.w_product3 = Constraint(
        range(1, num_cation + 1), 
        range(1, num_anion + 1), 
        rule=w_product_rule3
    )
    
    # === Objective Function ===
    def objective_rule(m):
        obj = sum(cost_fixed[k] * m.y[k] for k in unit_keys)
        obj += 2 * sum(cost_oper[f"r{r}"] * m.y[f"r{r}"] * alpha[r] for r in reactors)
        obj += 2 * sum(
            cost_oper[f"s{s}"] * m.y[f"s{s}"] * beta[(s, c, a)] * m.w[c, a]
            for s in separators
            for c in range(1, num_cation + 1)
            for a in range(1, num_anion + 1)
        )
        return obj
    m.objective = Objective(rule=objective_rule, sense=minimize)
    
    # === Logic Constraints ===
    if not use_quad_constraints:
        # Linear constraints version (with quadratic terms that need linearization)
        # At least one flow from source to reactor
        # Note: This constraint has a quadratic term f[(source, "r1")] * f[(source, "r2")]
        # For binary variables: f1 * f2 can be replaced with auxiliary variable
        # But since we're using linear constraints, we'll use a different formulation
        # The constraint sum(f) - f1*f2 == 1 can be linearized as:
        # sum(f) >= 1 (already satisfied by the constraint below)
        # and we add: f1 + f2 <= 1 + sum(f) - 1 = sum(f)
        # Actually, looking at the Julia code, this seems to be a specific constraint
        # that enforces exactly one flow. Let's linearize it properly.
        if len(reactors) >= 2:
            # Linearize: sum(f) - f[r1]*f[r2] == 1
            # For binary f1, f2: f1*f2 can be replaced with auxiliary variable u
            # u <= f1, u <= f2, u >= f1 + f2 - 1
            # Then: sum(f) - u == 1
            m.u_source_reactor = Var(domain=Binary)
            def u_source_reactor_rule1(m):
                return m.u_source_reactor <= m.f[(source, "r1")]
            m.u_source_reactor1 = Constraint(rule=u_source_reactor_rule1)
            
            def u_source_reactor_rule2(m):
                return m.u_source_reactor <= m.f[(source, "r2")]
            m.u_source_reactor2 = Constraint(rule=u_source_reactor_rule2)
            
            def u_source_reactor_rule3(m):
                return m.u_source_reactor >= m.f[(source, "r1")] + m.f[(source, "r2")] - 1
            m.u_source_reactor3 = Constraint(rule=u_source_reactor_rule3)
            
            def at_least_one_source_reactor_rule(m):
                return (
                    sum(m.f[(source, f"r{r}")] for r in reactors) 
                    - m.u_source_reactor == 1
                )
            m.at_least_one_source_reactor = Constraint(rule=at_least_one_source_reactor_rule)
        else:
            def at_least_one_source_reactor_rule(m):
                return sum(m.f[(source, f"r{r}")] for r in reactors) == 1
            m.at_least_one_source_reactor = Constraint(rule=at_least_one_source_reactor_rule)
        
        # If there is a flow from reactor to separator, there is inflow into reactor
        # Linearize: f[(r, s)] * f[(source, r)] == f[(r, s)]
        # This is equivalent to: f[(r, s)] <= f[(source, r)]
        def reactor_separator_flow_rule(m, r, s):
            return m.f[(f"r{r}", f"s{s}")] <= m.f[(source, f"r{r}")]
        m.reactor_separator_flow = Constraint(reactors, separators, rule=reactor_separator_flow_rule)
        
        # If separator is selected (there is inflow), at least one flow out from the separator
        # Linearize: f[(r, s)] * f[(s, sink)] == f[(r, s)]
        # This is equivalent to: f[(r, s)] <= f[(s, sink)]
        def separator_reactor_flow_rule(m, r, s):
            return m.f[(f"r{r}", f"s{s}")] <= m.f[(f"s{s}", sink)]
        m.separator_reactor_flow = Constraint(reactors, separators, rule=separator_reactor_flow_rule)
    else:
        # Quadratic constraints version (linearized)
        # At least one flow from source to reactor
        def at_least_one_source_reactor_rule(m):
            return sum(m.f[(source, f"r{r}")] for r in reactors) >= 1
        m.at_least_one_source_reactor = Constraint(rule=at_least_one_source_reactor_rule)
        
        # If there is a flow from reactor to separator, there is inflow into reactor
        def reactor_separator_flow_rule(m, r, s):
            return (1 - m.f[(f"r{r}", f"s{s}")]) + m.f[(source, f"r{r}")] >= 1
        m.reactor_separator_flow = Constraint(reactors, separators, rule=reactor_separator_flow_rule)
        
        # If separator is selected (there is inflow), at least one flow out from the separator
        def separator_reactor_flow_rule(m, r, s):
            return (1 - m.f[(f"r{r}", f"s{s}")]) + m.f[(f"s{s}", sink)] >= 1
        m.separator_reactor_flow = Constraint(reactors, separators, rule=separator_reactor_flow_rule)
    
    # Return model and variable references
    vars_dict = {
        'y': m.y,
        'z_cat': m.z_cat,
        'z_an': m.z_an,
        'f': m.f,
        'w': m.w
    }
    
    return m, vars_dict

def extract_solution_values(gurobi_model, sol_index):
    """
    Extract variable values for a specific solution from the pool.
    Uses Xn attribute which correctly accesses solution pool values.
    
    Parameters
    ----------
    gurobi_model : grb.Model
        Gurobi model
    sol_index : int
        Solution index in the pool
    
    Returns
    -------
    dict
        Dictionary mapping variable names to their values for this solution
    """
    # Set solution number using Params attribute (consistent with solve_gurobi_pool.py)
    gurobi_model.Params.SolutionNumber = sol_index
    
    # Extract all variable values using Xn attribute
    # Xn correctly accesses the variable value for solution number sol_index
    var_values = {
        v.VarName: round(v.Xn, 1) for v in gurobi_model.getVars()
        }
    
    return var_values

def solve_gurobi_pool(
    m,
    vars_dict,
    pool_search_mode: int = 2,
    pool_solutions: int = 100,
    output_dir: Optional[Path] = None,
    output_filename: Optional[str] = None,
    verbose: bool = True,
    save: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Solve optimization problem using Gurobi's solution pool and extract all solutions.
    
    Parameters
    ----------
    m : ConcreteModel
        Pyomo model
    vars_dict : dict
        Dictionary of variable references
    pool_search_mode : int, optional
        Gurobi PoolSearchMode parameter (default: 2 for finding multiple solutions)
    pool_solutions : int, optional
        Maximum number of solutions to find in pool (default: 100)
    output_dir : Path, optional
        Directory to save results. If None, uses script directory / "result_gurobi"
    output_filename : str, optional
        Output JSON filename. If None, generates timestamped filename.
    verbose : bool, optional
        Whether to print progress information (default: True)
    save : bool, optional
        Whether to save the results to a JSON file (default: False)
    
    Returns
    -------
    dict or None
        Dictionary containing:
        - 'run_info': Model metadata and pool search info
        - 'solutions': List of solution dictionaries
        Returns None if optimization was not successful
    """
    
    # Set up output directory
    if output_dir is None:
        script_dir = Path(__file__).parent
        output_dir = script_dir / "result_gurobi"
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Write model to temporary LP file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lp', delete=False) as tmp_file:
        tmp_lp_path = tmp_file.name
    
    try:
        # Write Pyomo model to LP file
        m.write(tmp_lp_path, io_options={'symbolic_solver_labels': True})
        
        # Read and solve with Gurobi directly to access solution pool
        gurobi_model = grb.read(tmp_lp_path)
        
        # Set pool search parameters
        gurobi_model.setParam('PoolSearchMode', pool_search_mode)
        gurobi_model.setParam('PoolSolutions', pool_solutions)
        
        # Optimize
        if verbose:
            print("Solving model...")
        gurobi_model.optimize()
        
        solve_time = gurobi_model.Runtime
        if verbose:
            print(f"\nSolve time: {solve_time} seconds")
        
        # Get number of solutions in the pool
        num_solutions = gurobi_model.SolCount
        if verbose:
            print(f"Number of solutions in pool: {num_solutions}")
        
        # Check solution status
        if gurobi_model.Status == grb.GRB.OPTIMAL:
            # Initialize result dictionary
            result_dict = {}
            
            # Organize result dictionary with run_info
            result_dict["run_info"] = {
                "model_info": {
                    "ModelName": gurobi_model.ModelName,
                    "NumVars": gurobi_model.NumVars,
                    "NumConstrs": gurobi_model.NumConstrs,
                    "NumObj": gurobi_model.NumObj,
                    "Sense": "Min" if gurobi_model.ModelSense == 1 else "Max",
                    "IsMIP": bool(gurobi_model.IsMIP),
                    "NumBinVars": gurobi_model.NumBinVars,
                    "NumIntVars": gurobi_model.NumIntVars,
                    "NumNZs": gurobi_model.NumNZs
                },
                "Pool Search Info": {
                    "PoolSearchMode Parameter": pool_search_mode,
                    "PoolSolutions Parameter": pool_solutions,
                    "Solve Time": solve_time,
                    "NumSolutions Found": num_solutions
                }
            }
            
            # Initialize solutions list
            result_dict["solutions"] = []
            
            # Extract all solutions from the pool
            for sol_index in range(num_solutions):
                # Get objective value for this solution from the pool
                gurobi_model.Params.SolutionNumber = sol_index
                obj_value = gurobi_model.PoolObjVal
                
                # Extract all variable values using Xn attribute
                var_values = extract_solution_values(gurobi_model, sol_index)
                
                # Store solution in list (consistent format with solve_gurobi_pool.py)
                solution = {
                    "solution_id": sol_index + 1,
                    "ip_obj_value": obj_value,
                    "values": var_values
                }
                
                result_dict["solutions"].append(solution)
                
                if verbose:
                    print(f"Solution {sol_index + 1}: Objective = {obj_value:.2f}")
            
            # Save all solutions to JSON file
            if output_filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"ilrs_gpool_n{pool_solutions}_{timestamp}.json"
            
            output_path = output_dir / output_filename
            
            if save:
                with open(output_path, 'w') as f:
                    json.dump(result_dict, f, indent=2)
                print(f"\nAll {num_solutions} solutions saved to: {output_path}")
            
            return result_dict
            
        else:
            if verbose:
                print(f"Model status: {gurobi_model.Status}")
                if gurobi_model.Status == grb.GRB.OPTIMAL:
                    print("Optimal solution found")
                elif gurobi_model.Status == grb.GRB.INFEASIBLE:
                    print("Model is infeasible")
                elif gurobi_model.Status == grb.GRB.UNBOUNDED:
                    print("Model is unbounded")
                else:
                    print(f"Status code: {gurobi_model.Status}")
            return None
        
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_lp_path):
            os.unlink(tmp_lp_path)

# ================== Functions for Analyzing the Results ===================
def load_gurobi_pool_results(json_path: str) -> Dict[str, Any]:
    """
    Load Gurobi pool search results from JSON file.
    
    Parameters
    ----------
    json_path : str
        Path to the JSON file
    
    Returns
    -------
    dict
        Dictionary containing 'run_info' and 'solutions'
    """
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data

def create_flattened_dataframe(solutions: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Create a flattened DataFrame from a list of solutions.
    Rounds objective values to 2 decimal places.
    
    Handles the new format where all variables are in a 'values' dictionary
    with Gurobi variable names like "y(r1)", "f(srce_r1)", etc.
    
    Parameters
    ----------
    solutions : list
        List of solution dictionaries with 'solution_id', 'ip_obj_value', and 'values' dict
    
    Returns
    -------
    pd.DataFrame
        Flattened DataFrame with one row per solution
    """
    flattened_solutions = []
    
    for solution in solutions:
        flat = {
            'solution_id': solution['solution_id'],
            'ip_obj_value': round(solution['ip_obj_value'], 2)
        }
        
        # Extract variables from the 'values' dictionary
        if 'values' in solution:
            for var_name, var_value in solution['values'].items():
                flattened_name = var_name.replace('(', '_').replace(')', '')
                flat[flattened_name] = var_value
        
        flattened_solutions.append(flat)
    
    return pd.DataFrame(flattened_solutions)

def print_run_info(run_info: Dict[str, Any]):
    """
    Print run information in a formatted way.
    
    Parameters
    ----------
    run_info : dict
        Run info dictionary containing model_info and Pool Search Info
    """
    print("Run Info:")
    print(f"  Model: {run_info['model_info']['ModelName']}")
    print(f"  Variables: {run_info['model_info']['NumVars']}")
    print(f"  Constraints: {run_info['model_info']['NumConstrs']}")
    print(f"  Solve Time: {run_info['Pool Search Info']['Solve Time']:.2f} seconds")
    print(f"  Solutions Found: {run_info['Pool Search Info']['NumSolutions Found']}")

def group_by_objective(df: pd.DataFrame) -> Dict[float, pd.DataFrame]:
    """
    Group solutions by objective value.
    
    Parameters
    ----------
    df : pd.DataFrame
        Flattened DataFrame with solutions
    
    Returns
    -------
    dict
        Dictionary mapping objective values to DataFrames of solutions with that objective
    """
    grouped = {}
    for obj_val, group in df.groupby('ip_obj_value'):
        grouped[obj_val] = group.reset_index(drop=True)
    return grouped

def find_duplicate_solutions(df: pd.DataFrame, exclude_cols: List[str] = None, tolerance: float = 1e-10) -> pd.DataFrame:
    """
    Find duplicate solutions based on variable values (excluding solution_id and ip_obj_value).
    Duplicate solutions have the SAME values for ALL variables.
    
    Parameters
    ----------
    df : pd.DataFrame
        Flattened DataFrame with solutions
    exclude_cols : list, optional
        Columns to exclude from comparison (default: ['solution_id', 'ip_obj_value'])
    tolerance : float, optional
        Tolerance for floating point comparison (default: 1e-10)
    
    Returns
    -------
    pd.DataFrame
        DataFrame with duplicate information added
    """
    if exclude_cols is None:
        exclude_cols = ['solution_id', 'ip_obj_value']
    
    # Get columns to compare (all except excluded)
    compare_cols = [col for col in df.columns if col not in exclude_cols]
    
    # Create a signature for each row based on variable values
    # Round to avoid floating point precision issues (for binary/integer vars, this shouldn't matter)
    df = df.copy()
    
    # For binary/integer variables, round to nearest integer
    # This handles any tiny floating point differences
    df_rounded = df[compare_cols].round(10)  # Round to 10 decimal places
    
    df['variable_signature'] = df_rounded.apply(
        lambda row: tuple(row.values), axis=1
    )
    
    # Count occurrences of each signature
    signature_counts = df['variable_signature'].value_counts()
    df['duplicate_count'] = df['variable_signature'].map(signature_counts)
    df['is_duplicate'] = df['duplicate_count'] > 1
    
    return df

def analyze_solution_groups(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze solutions to distinguish between:
    - Duplicate solutions: Same variable values (all variables match) - MUST have same objective
    - Same objective solutions: Same objective value but different variable combinations
    
    Note: If same variables have different objectives, that's flagged as an inconsistency.
    
    Parameters
    ----------
    df : pd.DataFrame
        Flattened DataFrame with solutions
    
    Returns
    -------
    dict
        Dictionary with analysis results
    """
    # Find duplicates (same variable values)
    df_with_dups = find_duplicate_solutions(df)
    
    # Group by variable signature first
    var_groups = df_with_dups.groupby('variable_signature')
    
    # For each variable signature group, check objectives
    analysis = {
        'duplicate_solutions': {},  # Solutions with same variable values (and same objective)
        'same_obj_different_vars': {},  # Solutions with same obj but different variables
        'unique_solutions': [],  # Solutions that are unique in both obj and vars
        'inconsistencies': []  # Same variables but different objectives (shouldn't happen)
    }
    
    # First pass: Group by variable signature
    for var_sig, var_group in var_groups:
        unique_objs = var_group['ip_obj_value'].nunique()
        
        if len(var_group) > 1:
            if unique_objs == 1:
                # Same variables, same objective - TRUE DUPLICATES
                obj_val = var_group['ip_obj_value'].iloc[0]
                analysis['duplicate_solutions'][obj_val] = {
                    'count': len(var_group),
                    'solution_ids': var_group['solution_id'].tolist(),
                    'variable_signature': var_sig
                }
            else:
                # Same variables but different objectives - INCONSISTENCY
                analysis['inconsistencies'].append({
                    'variable_signature': var_sig,
                    'solution_ids': var_group['solution_id'].tolist(),
                    'objective_values': sorted(var_group['ip_obj_value'].unique().tolist()),
                    'count': len(var_group)
                })
        else:
            # Single solution with this variable signature - check if unique
            solution_id = var_group['solution_id'].iloc[0]
            obj_val = var_group['ip_obj_value'].iloc[0]
            
            # Check if this objective appears with different variables
            obj_group = df[df['ip_obj_value'] == obj_val]
            if len(obj_group) == 1:
                # Unique in both variables and objective
                analysis['unique_solutions'].append({
                    'solution_id': solution_id,
                    'obj_value': obj_val,
                    'variable_signature': var_sig
                })
    
    # Second pass: Group by objective to find same objective, different variables
    obj_groups = df.groupby('ip_obj_value')
    for obj_val, obj_group in obj_groups:
        if len(obj_group) > 1:
            # Get variable signatures for this objective group
            compare_cols = [col for col in obj_group.columns 
                          if col not in ['solution_id', 'ip_obj_value']]
            signatures = obj_group[compare_cols].apply(
                lambda row: tuple(row.values), axis=1
            )
            
            unique_signatures = signatures.nunique()
            
            if unique_signatures > 1:
                # Same objective but different variable combinations
                # Only add if not already in duplicates (which would be same vars)
                if obj_val not in analysis['duplicate_solutions']:
                    analysis['same_obj_different_vars'][obj_val] = {
                        'count': len(obj_group),
                        'solution_ids': obj_group['solution_id'].tolist(),
                        'unique_variable_combinations': int(unique_signatures)
                    }
    
    return analysis

def print_solution_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze solutions and print a formatted summary.
    
    Parameters
    ----------
    df : pd.DataFrame
        Flattened DataFrame with solutions
    
    Returns
    -------
    dict
        Dictionary containing:
        - 'analysis': Analysis results from analyze_solution_groups
        - 'gpool_with_duplicates': DataFrame with duplicate information
        - 'num_unique_vars': Number of unique variable combinations
        - 'num_duplicate_vars': Number of solutions with duplicate variable combinations
    """
    # Analyze solutions to distinguish duplicates vs same objective
    analysis = analyze_solution_groups(df)
    
    # Find duplicate solutions (same variable values)
    gpool_with_duplicates = find_duplicate_solutions(df)
    num_unique_vars = (gpool_with_duplicates['duplicate_count'] == 1).sum()
    num_duplicate_vars = (gpool_with_duplicates['is_duplicate']).sum()
    
    print(f"\n" + "="*80)
    print("SOLUTION ANALYSIS")
    print("="*80)
    
    print(f"\n1. DUPLICATE SOLUTIONS (same variable values AND same objective):")
    print(f"   Total solutions with duplicate variable combinations: {num_duplicate_vars}")
    print(f"   Unique variable combinations: {num_unique_vars}")
    
    if analysis['duplicate_solutions']:
        print(f"\n   Duplicate groups (same variables, same objective):")
        for obj_val, info in sorted(analysis['duplicate_solutions'].items()):
            print(f"     Objective {obj_val:.2f}: {info['count']} solutions (IDs: {info['solution_ids']})")
    else:
        print(f"   No true duplicate solutions found")
    
    if analysis['inconsistencies']:
        print(f"\n   ⚠️  INCONSISTENCIES DETECTED (same variables, different objectives):")
        print(f"   This should not happen - indicates data extraction or model issue!")
        for inc in analysis['inconsistencies']:
            print(f"     Variable signature group: {inc['count']} solutions")
            print(f"       Solution IDs: {inc['solution_ids']}")
            print(f"       Different objectives: {inc['objective_values']}")
    
    print(f"\n2. SAME OBJECTIVE, DIFFERENT VARIABLES:")
    print(f"   Objective values with multiple variable combinations: {len(analysis['same_obj_different_vars'])}")
    if analysis['same_obj_different_vars']:
        for obj_val, info in sorted(analysis['same_obj_different_vars'].items()):
            print(f"     Objective {obj_val:.2f}: {info['count']} solutions, {info['unique_variable_combinations']} unique variable combinations")
            print(f"       Solution IDs: {info['solution_ids']}")
    
    print(f"\n3. UNIQUE SOLUTIONS (unique in both objective and variables):")
    print(f"   Count: {len(analysis['unique_solutions'])}")
    
    return {
        'analysis': analysis,
        'gpool_with_duplicates': gpool_with_duplicates,
        'num_unique_vars': num_unique_vars,
        'num_duplicate_vars': num_duplicate_vars
    }

if __name__ == "__main__":
    # Set up paths
    script_dir = Path(__file__).parent
    data_filepath = script_dir / ".." / "data"
    result_dir = script_dir / "result_gurobi"
    
    # Build model
    m_poolsearch, vars_poolsearch = build_discrete_ip_model(
        str(data_filepath), 
        use_quad_constraints=True
    )
    
    # Solve with pool search
    result_dict = solve_gurobi_pool(
        m=m_poolsearch,
        vars_dict=vars_poolsearch,
        pool_search_mode=2,
        pool_solutions=228,
        output_dir=result_dir,
        verbose=True
    )
