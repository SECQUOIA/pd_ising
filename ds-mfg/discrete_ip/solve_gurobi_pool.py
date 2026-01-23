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
    tee: bool = False
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
    tee : bool, optional
        Whether to print Gurobi solver output (default: False).
    
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
    model1 = optimizer.pyomo_model.model
    
    # Write model to temporary LP file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lp', delete=False) as tmp_file:
        tmp_lp_path = tmp_file.name
    
    try:
        # Write Pyomo model to LP file
        model1.write(tmp_lp_path, io_options={'symbolic_solver_labels': True})
        
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
        
        # Create mapping from flow names to Gurobi variables
        # Get Pyomo variable names first to see what format they use
        pyomo_var_names = {}
        for flow in model1.flows:
            pyomo_var = model1.f[flow]
            pyomo_var_names[flow] = pyomo_var.getname()
        
        # Get all Gurobi variable names
        all_grb_var_names = [v.VarName for v in gurobi_model.getVars()]
        
        # Build a dictionary mapping flow names to Gurobi variable objects
        flow_to_grb_var = {}
        for flow in model1.flows:
            # Get the Pyomo variable name
            pyomo_name = pyomo_var_names[flow]
            
            # First try the exact Pyomo name
            grb_var = gurobi_model.getVarByName(pyomo_name)
            if grb_var is not None:
                flow_to_grb_var[flow] = grb_var
                continue
            
            # Try different possible variable name formats that Pyomo might use
            possible_names = [
                f"f[{flow}]",           # Standard Pyomo format with symbolic labels
                f"f_{flow}",            # Alternative format with underscore
                f"f({flow})",           # Alternative with parentheses
                flow,                   # Just the flow name
                f"f{flow}",            # No separator
            ]
            
            for name in possible_names:
                grb_var = gurobi_model.getVarByName(name)
                if grb_var is not None:
                    flow_to_grb_var[flow] = grb_var
                    break
            
            # If still not found, search through all variables more flexibly
            if flow not in flow_to_grb_var:
                for v in gurobi_model.getVars():
                    vname = v.VarName
                    # Check various patterns that might match
                    if (f"[{flow}]" in vname or 
                        f"({flow})" in vname or
                        vname.endswith(f"_{flow}") or 
                        vname.endswith(f"[{flow}]") or
                        vname.endswith(f"({flow})") or
                        vname == flow or
                        vname == f"f{flow}" or
                        vname == f"f_{flow}"):
                        flow_to_grb_var[flow] = v
                        break
        
        # If still missing, try to match by position/index (last resort)
        if len(flow_to_grb_var) < len(model1.flows):
            # Get all flows as a sorted list to match with variable order
            flows_list = sorted(list(model1.flows))
            grb_vars_list = sorted(gurobi_model.getVars(), key=lambda x: x.VarName)
            
            # Try to match by position if counts match
            if len(flows_list) == len(grb_vars_list):
                for flow, grb_var in zip(flows_list, grb_vars_list):
                    if flow not in flow_to_grb_var:
                        flow_to_grb_var[flow] = grb_var
        
        if verbose:
            print(f"Found {len(flow_to_grb_var)}/{len(model1.flows)} variable mappings")
        
        if len(flow_to_grb_var) < len(model1.flows):
            missing_flows = set(model1.flows) - set(flow_to_grb_var.keys())
            if verbose:
                print(f"Warning: Missing flows: {missing_flows}")
                print(f"All Gurobi variable names: {all_grb_var_names}")
                print(f"All Pyomo variable names: {list(pyomo_var_names.values())}")
        
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
        
        for sol_index in range(num_solutions):
            # Set the solution number parameter to access solution from pool
            gurobi_model.setParam('SolutionNumber', sol_index)
            
            # Get objective value for this solution from the pool
            obj_value = gurobi_model.PoolObjVal
            
            # Extract variable values directly from Gurobi for this solution
            solution = {}
            for flow in model1.flows:
                if flow in flow_to_grb_var:
                    # Get the solution value for this solution number
                    # When SolutionNumber is set, X gives the value for that solution
                    solution[flow] = flow_to_grb_var[flow].X
                else:
                    # This should not happen if mapping was successful
                    # But if it does, we'll use 0 as a fallback
                    solution[flow] = 0
            
            # Initialize solution entry and add flow information directly
            result_dict[sol_index + 1] = {}
            for flow, value in solution.items():
                result_dict[sol_index + 1][flow] = value
            
            # Extract operating modes
            operating_modes = optimizer._extract_operating_modes(solution)
            
            # Add results information directly to result_dict
            result_dict[sol_index + 1].update({
                'operating_modes': operating_modes,
                'ip_obj_value': obj_value,
            })
            
            # Add simulation data if available
            if optimizer.summary_data is not None:
                operating_modes_str = " ".join(operating_modes)
                matching_data = optimizer.summary_data.loc[
                    optimizer.summary_data["Combination"].apply(lambda x: x == operating_modes_str)
                ]
                
                if not matching_data.empty:
                    result_dict[sol_index + 1].update({
                        'sm_obj_value': float(matching_data["Best Objective Value"].iloc[0]),
                        'sm_eval_time': int(matching_data["Evaluation Time"].iloc[0]),
                        'sm_capex': float(matching_data["Total_CAPEX"].iloc[0])
                    })
            
            if verbose:
                print(f"Solution {sol_index + 1}: {operating_modes}, Objective: {obj_value:.6f}")
        
        # Save all solutions to JSON file
        # Get the directory where this script is located
        script_dir = Path(__file__).parent
        result_dir = script_dir / "result_gurobi"
        
        # Create result_gurobi directory if it doesn't exist
        result_dir.mkdir(exist_ok=True)
        
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"gurobi_pool_solutions_{timestamp}.json"
        
        # Construct full path to save in result_gurobi folder
        output_path = result_dir / output_filename
        
        with open(output_path, 'w') as f:
            json.dump(result_dict, f, indent=2)
        
        if verbose:
            print(f"\nAll {num_solutions} solutions saved to: {output_path}")
        
        return result_dict
        
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_lp_path):
            os.unlink(tmp_lp_path)


def main():
    """Main function to run the solver with default parameters."""
    result_dict = solve_gurobi_pool()
    return result_dict


if __name__ == "__main__":
    main()
