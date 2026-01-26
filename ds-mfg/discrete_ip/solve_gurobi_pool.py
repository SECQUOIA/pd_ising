"""
Script to solve optimization problem using Gurobi's solution pool feature
and save all solutions to a JSON file.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import gurobipy as grb
import tempfile
import os

from flst_opti_IP import FlowsheetOptimizer, get_default_paths


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
