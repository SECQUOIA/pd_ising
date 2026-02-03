"""
Script to solve optimization problem using Gurobi's solution pool feature
and save all solutions to a JSON file.

Also contains helper functions for loading and analyzing pool search results.
See ds_mfg_discrete_IP_poolsearch.ipynb for running the model and analyzing results.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import gurobipy as grb
import tempfile
import os

import pandas as pd

from flst_opti_IP import FlowsheetOptimizer, get_default_paths


# ================== Helper functions for analysis ===================


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

    # Reorganize data to match expected format
    run_info = {
        'model_info': data.get('model_info', {}),
        'Pool Search Info': data.get('Pool Search Info', {})
    }

    return {
        'run_info': run_info,
        'solutions': data.get('solutions', [])
    }


def create_flattened_dataframe(solutions: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Create a flattened DataFrame from a list of solutions.
    Rounds objective values to 2 decimal places.

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
                # Clean variable names (remove parentheses, replace with underscore)
                flattened_name = var_name.replace('(', '_').replace(')', '').replace('f_', 'f')
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


def find_duplicate_solutions(
    df: pd.DataFrame,
    exclude_cols: Optional[List[str]] = None,
    tolerance: float = 1e-10
) -> pd.DataFrame:
    """
    Find duplicate solutions based on variable values (excluding solution_id and ip_obj_value).

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

    df = df.copy()
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

    analysis = {
        'duplicate_solutions': {},
        'same_obj_different_vars': {},
        'unique_solutions': [],
        'inconsistencies': []
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
            # Single solution with this variable signature
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
            compare_cols = [col for col in obj_group.columns
                          if col not in ['solution_id', 'ip_obj_value']]
            signatures = obj_group[compare_cols].apply(
                lambda row: tuple(row.values), axis=1
            )

            unique_signatures = signatures.nunique()

            if unique_signatures > 1:
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
        Dictionary containing analysis results
    """
    analysis = analyze_solution_groups(df)

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


def aggregate_pool_run_timings(result_dir: Optional[Path] = None) -> pd.DataFrame:
    """
    Aggregate solve time vs pool-solutions setpoint from all gurobi_pool_solutions_n*.json files.

    Parameters
    ----------
    result_dir : pathlib.Path, optional
        Directory containing Gurobi pool result JSON files. If None, uses script directory / "result_gurobi".

    Returns
    -------
    pd.DataFrame
        DataFrame with columns 'n' (pool-solutions setpoint), 'solve_time' (seconds), and 'solution_count'.
    """
    if result_dir is None:
        result_dir = Path(__file__).resolve().parent / "result_gurobi"
    result_dir = Path(result_dir)
    rows = []
    for path in sorted(result_dir.glob("gurobi_pool_solutions_n*.json")):
        # Extract n from filename (e.g. gurobi_pool_solutions_n100_20260126_105949.json -> 100)
        stem = path.stem
        parts = stem.split("_")
        n_str = next((p for p in parts if p.startswith("n") and p[1:].isdigit()), None)
        if n_str is None:
            continue
        n = int(n_str[1:])
        data = load_gurobi_pool_results(str(path))
        pool_info = data["run_info"]["Pool Search Info"]
        solve_time = pool_info["Solve Time"]
        num_solutions = pool_info["NumSolutions Found"]
        rows.append({"n": n, "solve_time": solve_time, "solution_count": num_solutions})
    if not rows:
        return pd.DataFrame(columns=["n", "solve_time", "solution_count"])
    df = pd.DataFrame(rows).sort_values("n").reset_index(drop=True)
    return df


# ================== Main solver ===================


def solve_gurobi_pool(
    flowsheet_data_path: Optional[str] = None,
    simulation_data_path: Optional[str] = None,
    pool_search_mode: int = 2,
    pool_solutions: int = 100,
    output_filename: Optional[str] = None,
    verbose: bool = True,
    save: bool = False
) -> Dict[str, Any]:
    """
    Solve optimization problem using Gurobi's solution pool and extract all solutions.
    
    Parameters
    ----------
    flowsheet_data_path : str, optional
        Path to flowsheet data CSV file. If None, uses default path.
    simulation_data_path : str, optional
        Path to simulation data CSV file. If None, uses default path.
    pool_search_mode : int, optional
        Gurobi PoolSearchMode parameter (default: 2 for finding multiple solutions).
    pool_solutions : int, optional
        Maximum number of solutions to find in pool (default: 100).
    output_filename : str, optional
        Output JSON filename. If None, generates timestamped filename.
    verbose : bool, optional
        Whether to print progress information (default: True).
    save : bool, optional
        Whether to save the results to a JSON file (default: False).
    
    Returns
    -------
    dict
        Dictionary containing:
        - 'model_info': Model metadata (name, variables, constraints, etc.)
        - 'Pool Search Info': Pool search parameters and results
        - Solution dictionaries keyed by solution number (1, 2, 3, ...)
    """
    # Get default paths if not provided
    if flowsheet_data_path is None:
        flowsheet_data_path, _ = get_default_paths()
        flowsheet_data_path = str(flowsheet_data_path)
    
    if simulation_data_path is None:
        _, simulation_data_path = get_default_paths()
        simulation_data_path = str(simulation_data_path)
    
    # Initialize optimizer
    optimizer = FlowsheetOptimizer(flowsheet_data_path, simulation_data_path)
    model = optimizer.pyomo_model.model
    
    # Write model to temporary LP file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lp', delete=False) as tmp_file:
        tmp_lp_path = tmp_file.name
    
    try:
        # Write Pyomo model to LP file
        model.write(tmp_lp_path, io_options={'symbolic_solver_labels': True})
        
        # Read and solve with Gurobi directly to access solution pool
        gurobi_model = grb.read(tmp_lp_path)
        
        # Set pool search parameters
        gurobi_model.setParam('PoolSearchMode', pool_search_mode)
        gurobi_model.setParam('PoolSolutions', pool_solutions)
        
        # Optimize
        gurobi_model.optimize()
        
        solve_time = gurobi_model.Runtime
        if verbose:
            print(f"Solve time: {solve_time} seconds")
        
        # Get number of solutions in the pool
        num_solutions = gurobi_model.SolCount
        if verbose:
            print(f"\nNumber of solutions in pool: {num_solutions}")
        
        # Extract all solutions from the solution pool
        result_dict = {}
        
        # Add model information
        result_dict["model_info"] = {
            "ModelName": gurobi_model.ModelName,
            "NumVars": gurobi_model.NumVars,
            "NumConstrs": gurobi_model.NumConstrs,
            "NumObj": gurobi_model.NumObj,
            "Sense": "Min" if gurobi_model.ModelSense == 1 else "Max",
            "IsMIP": bool(gurobi_model.IsMIP),
            "NumBinVars": gurobi_model.NumBinVars,
            "NumIntVars": gurobi_model.NumIntVars,
            "NumNZs": gurobi_model.NumNZs
        }
        
        result_dict["Pool Search Info"] = {
            "PoolSearchMode Parameter": pool_search_mode,
            "PoolSolutions Parameter": pool_solutions,
            "Solve Time": solve_time,
            "NumSolutions Found": num_solutions
        }
        
        if "solutions" not in result_dict: # If solutions are not already in the result dictionary, extract them from the solution pool
            result_dict["solutions"] = []

        for sol_index in range(num_solutions):
            # Set the solution number parameter to access solution from pool
            gurobi_model.Params.SolutionNumber = sol_index
            
            # Get objective value for this solution from the pool
            obj_value = gurobi_model.PoolObjVal
            var = {v.VarName: v.Xn for v in gurobi_model.getVars()}
            
            solution = {
                "solution_id": sol_index + 1,
                "ip_obj_value": obj_value,
                "values": var
            }

            if verbose:
                print(f"Solution {sol_index + 1}: Objective: {obj_value:.6f}")
                print(solution)

            result_dict["solutions"].append(solution)

        if save:
            output_path = Path(__file__).parent / "result_gurobi" / f"gurobi_pool_solutions_n{pool_solutions}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            output_path.parent.mkdir(exist_ok=True)

            with open(output_path, 'w') as f:
                json.dump(result_dict, f, indent=2)

            print(f"\nAll {num_solutions} solutions saved to: {output_path}")
        
        return result_dict
        
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_lp_path):
            os.unlink(tmp_lp_path)

def main():
    """Main function to run the solver with default parameters."""
    result_dict = solve_gurobi_pool(
        pool_solutions=100,
        save=True,
    )
    return result_dict


if __name__ == "__main__":
    main()
