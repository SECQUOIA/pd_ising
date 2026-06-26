"""
Common functions for Drug Substance Manufacturing Flowsheet Optimization

This module contains utility functions used across different flowsheet optimization
implementations for pharmaceutical manufacturing processes.

"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import networkx as nx
import pyomo.environ as pyo
import time
import dimod 
import neal
from dwave.system import DWaveSampler, EmbeddingComposite, FixedEmbeddingComposite
from pprint import pprint
from collections import Counter
from typing import Dict, Optional, Tuple, Any
import os
from datetime import datetime
import json

try:
    import gurobipy as grb
    GUROBI_AVAILABLE = True
except ImportError:
    GUROBI_AVAILABLE = False
    print("Warning: gurobipy not available. Some functions may not work.")


def import_uo_key(file_path, uo_flow=False):
    """
    Import flowsheet data and organize unit operation keys.
    
    This function imports the flowsheet data from a csv file and organizes it in a dictionary.
    
    Parameters
    ----------
    file_path : str
        The path to the csv file containing the flowsheet data.
    uo_flow : bool, optional
        If True, the function returns a list of flows with associated unit operations 
        along with a dictionary containing the unit operations associated with each flow. 
        If False, the function returns a dictionary containing the unit operations 
        associated with each flow only. The default is False.
    
    Returns
    -------
    tuple or dict
        If uo_flow=True: (uo_keys, flow_with_uo)
        If uo_flow=False: uo_keys only
        
        uo_keys: dict
            A dictionary containing the unit operations associated with each flow. 
            Includes flows associated with specific unit operations (e.g. 'CSTR', 'PFR'). 
            Does not include flows associated with hold tanks.
        flow_with_uo: list
            A list of flows with associated unit operations. Includes flows at disjunctions, 
            associated with hold tanks or without specific unit operations (e.g. 'holdT', 'noholdT').
    """
    # Import the flowsheet data
    flst_data = pd.read_csv(file_path)
    
    # Identify and label flow with the associated uo 
    flow_with_uo = []
    uo_keys = {}    
    
    for i in range(len(flst_data)):
        if flst_data['uo'][i] != 'none': 
            flow_with_uo.append(flst_data['Flow'][i])
            if flst_data['uo'][i] not in ['holdT', 'noholdT']:
                uo_keys[flst_data['Flow'][i]] = flst_data['uo'][i]
    
    if uo_flow:
        return uo_keys, flow_with_uo
    else:
        return uo_keys


def import_data(file_path):
    """
    Import flowsheet data and organize it into dictionaries.
    
    This function imports the flowsheet data from a csv file and organizes it in a dictionary.
    
    Parameters
    ----------
    file_path : str
        The path to the csv file containing the flowsheet data.
    
    Returns
    -------
    tuple
        (flow_network, flow_cost, disj_dict, flow_with_uo, uo_keys)
        
        flow_network: dict
            A dictionary containing the flowsheet data organized by flow.
        flow_cost: dict
            A dictionary containing the cost of each flow.
        disj_dict: dict
            A dictionary containing the disjunctions in the network.
        flow_with_uo: list
            A list of flows with associated unit operations.
        uo_keys: dict
            A dictionary containing the unit operations associated with each flow.
    """
    # Import the flowsheet data
    flst_data = pd.read_csv(file_path)
    
    # Identify and label flow with the associated uo
    uo_keys, flow_with_uo = import_uo_key(file_path, uo_flow=True)
    
    # Organize the flowsheet data
    flow_network = {
        row["Flow"]: (row["From"], row["To"]) for _, row in flst_data.iterrows()
    }
    flow_cost = {row["Flow"]: row["Flow Cost"] for _, row in flst_data.iterrows()}
    
    # Identify disjunctions: flows with the same 'From' node or the same 'To' node
    disjunctions = flst_data.groupby("From").filter(lambda x: len(x) > 1)
    # disjunctions_to = flst_data.groupby('To').filter(lambda x: len(x) > 1)
    
    disj_dict = {}
    for _, row in disjunctions.iterrows():
        from_node = row["From"]
        flow = row["Flow"]
        if from_node not in disj_dict:
            disj_dict[from_node] = []
        disj_dict[from_node].append(flow)
    
    return flow_network, flow_cost, disj_dict, flow_with_uo, uo_keys


def import_from_mps(filepath, plotA=False):
    """
    Import the information from the MPS file.
    
    Parameters
    ----------
    filepath : str
        The path to the MPS file.
    plotA : bool, optional
        If True, plots the sparse matrix A. Default is False.
    
    Returns
    -------
    tuple
        (A, b, c)
        
        A : np.array
            The A matrix of the QUBO model.
        b : np.array
            The b matrix of the QUBO model.
        c : np.array
            The c matrix of the QUBO model.
    """
    if not GUROBI_AVAILABLE:
        raise ImportError("gurobipy is required for this function")
    
    # Import the A, b, c, and epsilon matrices from the MPS file
    m = grb.read(filepath)
    A_raw = m.getA()
    A = A_raw.todense()
    
    b_raw = m.getAttr("RHS")
    b = np.array(b_raw)
    
    c_raw = m.getAttr("Obj")
    c = np.array(c_raw)
    
    if plotA:
        plt.spy(A_raw, markersize=0.5)
        plt.show()
    
    return A, b, c


def export_to_mps(model, filename: str = None):
    """
    Export the model to MPS format.
    
    Parameters
    ----------
    model : pyomo.environ.ConcreteModel
        The Pyomo model to export.
    filename : str, optional
        Output filename. If None, generates a timestamped filename.
        
    Returns
    -------
    None
    """
    if filename is None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"flowsheet_opti_{timestamp}.mps"
    
    model.write(
        filename=filename, 
        io_options={"symbolic_solver_labels": True}
    )
    print(f"Model exported to {filename}")


def visualize_network(flow_network, flow_cost, disj_penalty=None, disj=None, model=None):
    """
    Visualize the flow network as a directed graph.
    
    Parameters
    ----------
    flow_network : dict
        A dictionary containing the flowsheet data organized by flow. The keys are the 
        flow names, and the values are tuples containing the source and destination nodes of the flow.
    flow_cost : dict
        A dictionary containing the cost of each flow.
    disj_penalty : dict, optional
        A dictionary containing the penalty for flows with disjunctions.
    disj : dict, optional
        A dictionary containing the disjunctions in the network.
    model : pyomo.environ.ConcreteModel, optional
        The Pyomo model for flowsheet optimization.
    """
    # Create a directed graph
    G = nx.DiGraph()
    nodes = list(set(sum(flow_network.values(), ())))
    nodes.sort()
    G.add_nodes_from(nodes)
    
    plt.title("Flow Network Directed Graph")
    
    # Add edges to the graph with flow costs and disjunction penalties as labels
    for flow, (start, end) in flow_network.items():
        # Draw edge labels
        G.add_edge(start, end, key=flow)
    
    if model is not None:
        flow_decisions = {flow: pyo.value(model.f[flow]) for flow in model.flows}
    else:
        flow_decisions = {flow: 0 for flow in flow_network.keys()}
    
    pos = nx.spiral_layout(G)
    
    # Draw the graph
    nx.draw(
        G,
        pos,
        with_labels=True,
        node_size=2000,
        node_color="lightblue",
        font_size=10,
        font_weight="bold",
        arrows=True,
    )
    
    # Draw edge labels
    if disj_penalty is not None:
        edge_labels = {
            (start, end): f"{flow}\nCost: {flow_cost[flow]}\nPenalty: {disj_penalty[flow]}"
            for flow, (start, end) in flow_network.items()
        }
    else:
        edge_labels = {
            (start, end): f"{flow}\nCost: {flow_cost[flow]}"
            for flow, (start, end) in flow_network.items()
        }
    
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_color="red")
    
    if model is not None:
        active_edges = [
            (flow_network[flow][0], flow_network[flow][1], flow)
            for flow, decision in flow_decisions.items()
            if decision == 1
        ]
        inactive_edges = [
            (flow_network[flow][0], flow_network[flow][1], flow)
            for flow, decision in flow_decisions.items()
            if decision == 0
        ]
        nx.draw_networkx_edges(
            G,
            pos,
            edgelist=inactive_edges,
            edge_color="red",
            style="dashed",
            alpha=0.5,
            connectionstyle="arc3,rad=0.1",
        )
        nx.draw_networkx_edges(
            G,
            pos,
            edgelist=active_edges,
            edge_color="blue",
            width=2,
            connectionstyle="arc3,rad=0.1",
        )
    
    plt.show()


def read_sim_data(file_name, dict=False):
    """
    Read the PharmaPy simulation data from a csv file.
    
    This function reads the PharmaPy simulation data from a csv file and returns it 
    as a pandas data frame (sim_data) or a dictionary (sim_dict) if dict=True.
    
    sim_dict contains: key=configuration (Combination); evaluation time, best solution 
    (feasible), best objective value, blackbox evaluations, total model evaluations, 
    total number of evaluations, CAPEX.
    
    Parameters
    ----------
    file_name : str
        The name of the csv file containing the simulation data.
    dict : bool, optional
        If True, returns a dictionary. If False, returns a pandas DataFrame. 
        Default is False.
    
    Returns
    -------
    pandas.DataFrame or dict
        A pandas DataFrame or dictionary containing the simulation data.
    """
    # Read the simulation data
    sim_data = pd.read_csv(file_name)
    sim_data["Combination"] = sim_data["Combination"].apply(
        lambda x: x.replace("(", "")
        .replace(")", "")
        .replace("_ ", " ")
        .replace("'", "")
    )
    # convert SM Obj Value to numeric
    sim_data["Best Objective Value"] = pd.to_numeric(
        sim_data["Best Objective Value"], errors="coerce"
    )
    
    if dict:
        # Organize the data into a dictionary
        sim_dict = {}
        for index, row in sim_data.iterrows():
            combination = row["Combination"]
            sim_dict[combination] = {
                "Evaluation Time": row["Evaluation Time"],
                "Best Solution (feasible)": row["Best Solution (feasible)"],
                "Best Objective Value": row["Best Objective Value"],
                "Blackbox Evaluations": row["Blackbox Evaluations"],
                "Total Model Evaluations": row["Total Model Evaluations"],
                "Total Number of Evaluations": row["Total Number of Evaluations"],
                "CAPEX": row["Total_CAPEX"],
            }
        return sim_dict
    return sim_data

# ======================================== QUBO functions ========================================

def import_from_julia(filepath_scalar, file_path_Q, file_path_L): 
    """
    Import the QUBO model from the Julia ToQUBO conversion.  
    Calculates Q matrix and beta offset in x'Qx + beta form. 

    Parameters
    ----------
    filepath_scalar : str
        The path to the csv file containing the scalars.        
    file_path_Q : str
        The path to the csv file containing the Q matrix.
    file_path_L : str
        The path to the csv file containing the L matrix.

    Returns
    -------
    Q : np.array
        The calculated Q matrix of the QUBO model. 
    a : float
        a, scale factor of the QUBO model.
    b : float
        b, offset factor of the QUBO model.
    n : float
        n, number of variables of the QUBO model.
    """
    scalars = np.loadtxt(filepath_scalar, delimiter=',', skiprows=1)
    n, a, b = scalars  # Unpack the values  
    beta = a*b
    Qij = np.loadtxt(file_path_Q, delimiter=',')
    Li = np.loadtxt(file_path_L, delimiter=',')
    Q = Qij + np.diag(Li) 
    Q *= a

    return Q, beta

def sum_infeas_soln(df, threshold): 
    """
    Consolidate the infeasible solutions in the results dataframe.

    Parameters
    ----------
    df : pd.DataFrame
        The results of the optimization.
    threshold : float
        The energy threshold for the optimal or feasible solution.
    """
    
    infeasible = df[df.index > threshold]
    infeasible_sum = infeasible.sum()
    infeasible_sum.name = threshold
    df = df[df.index <= threshold]
    df = pd.concat([df, infeasible_sum.to_frame().T])
    return df

def calculate_Q_matrix(A, b, c, epsilon):
    """
    Calculates the Q matrix of the quadratic unconstrained binary optimization (QUBO) model based on the A, b, and c matrices and the epsilon value.

    Parameters
    ----------
    A : np.array
        The A matrix of the QUBO model.
    b : np.array
        The b matrix of the QUBO model.
    c : np.array
        The c matrix of the QUBO model.
    epsilon : float
        The epsilon value of the QUBO model.

    Returns
    -------
    Q : np.array
        The Q matrix of the QUBO model.
    """
    rho = np.sum(np.abs(c)) + epsilon
    Q = rho * np.matmul(A.T, A) 
    Q += np.diag(c) 
    Q -= rho*2*np.diag(np.matmul(b.T, A))
    Beta = rho*np.matmul(b.T,b)
    return Q, Beta
    
def sampleset_to_df(results, skip=1, imported=False, qci_extra=False):
    """
    Convert the results of the optimization to a dataframe.

    Parameters
    ----------
    results : dimod.exactSampler.sample or neal.sampler.SimulatedAnnealingSampler.sample
        The results of the optimization.
    skip : int, optional
        parameter to avoid putting all xlabels, by default 1
    imported : bool, optional
        If the results are imported from a file (or QCI result), by default False
    qci_extra : bool, optional
        If the results are from QCI, includes 'solutions', 'num_samples', 'execution_time', etc., 
        by default False
    """

    if imported:
        energies = results['energy']
        occurrences = results['num_occurrences']
        execution_time = results['execution_time']
    else:
        energies = results.data_vectors['energy']
        occurrences = results.data_vectors['num_occurrences']

    counts = Counter(energies)
    total = sum(occurrences)
    counts = {}
    occurrences_by_energy = {}
    for index, energy in enumerate(energies):
        if energy in counts.keys():
            counts[energy] += occurrences[index]
            occurrences_by_energy[energy] += occurrences[index]
        else:
            counts[energy] = occurrences[index]
            occurrences_by_energy[energy] = occurrences[index]
    for key in counts:
        counts[key] /= total
    
    # Create dataframe with both probability and occurrences
    df_data = {
        'Probability': [counts[energy] for energy in sorted(counts.keys())],
        'Occurrences': [occurrences_by_energy[energy] for energy in sorted(counts.keys())]
    }
    df = pd.DataFrame(df_data, index=sorted(counts.keys()))
    df.index.name = 'Energy'

    if qci_extra:
        # Flattened columns of interest
        df_extra = pd.DataFrame({
            "Energy": energies
        })

        if 'solutions' in results:
            df_extra['Solution'] = [list(sol) for sol in results['solutions']]

        if 'num_samples' in results:
            df_extra['Num_Samples'] = results['num_samples']

        if 'execution_time' in results:
            df_extra['Execution_Time'] = results['execution_time']

        # Merge on Energy to retain consistency
        df_extra_grouped = df_extra.groupby("Energy").agg({
            "Solution": lambda x: list(x),
            "Num_Samples": "first",
            "Execution_Time": "first"
        }).reset_index()

        df_full = df.reset_index().merge(df_extra_grouped, on="Energy", how="left")
        df = df_full.set_index("Energy")

    if imported: 
        return df, execution_time

    return df

def _serialize_sampleset_to_result_dict(sampleset, execution_time, solver_name, include_solutions=False, extra_meta=None):
    """
    Convert a dimod.SampleSet into a unified JSON-serializable result dictionary.

    The resulting dictionary is compatible with `sampleset_to_df(imported=True, qci_extra=True)`.

    Parameters
    ----------
    sampleset : dimod.SampleSet
        The sample set to serialize.
    execution_time : float
        Total wall-clock time to obtain the samples (seconds).
    solver_name : str
        Identifier for the solver, e.g., "simulated_annealing" or "dwave_qpu".
    include_solutions : bool, optional
        If True, include the sampled bitstrings in the output under 'solutions'.
    extra_meta : dict, optional
        Extra metadata to include under 'meta'.

    Returns
    -------
    dict
        JSON-serializable dictionary with keys: 'energy', 'num_occurrences',
        optional 'solutions', 'num_samples', 'execution_time', 'variables', 'solver', 'meta'.
    """
    energies = sampleset.data_vectors['energy'].tolist()
    num_occurrences = sampleset.data_vectors['num_occurrences'].tolist()

    result_dict = {
        'energy': energies,
        'num_occurrences': num_occurrences,
        'num_samples': int(sum(num_occurrences)),
        'execution_time': float(execution_time),
        'variables': list(map(str, sampleset.variables)),
        'solver': str(solver_name),
        'meta': {}
    }

    if include_solutions and hasattr(sampleset.record, 'sample'):
        # sampleset.record.sample has shape (n_records, n_variables)
        samples_np = sampleset.record.sample
        # Convert to list of lists of ints (0/1)
        result_dict['solutions'] = [[int(v) for v in row.tolist()] for row in samples_np]

    # Attach solver info/timing when present
    if hasattr(sampleset, 'info') and isinstance(sampleset.info, dict):
        # Copy to avoid mutating the original info
        info_copy = dict(sampleset.info)
        # Ensure tts_tictoc is included for convenience
        info_copy.setdefault('tts_tictoc', float(execution_time))
        # Store at top-level only; keep meta for timestamp/other misc
        result_dict['info'] = info_copy
    if extra_meta:
        result_dict['meta'].update(extra_meta)

    # Timestamp for traceability
    result_dict['meta']['timestamp'] = datetime.now().isoformat()

    return result_dict

def save_result_json(result_dict, output_dir, filename_prefix):
    """
    Save a result dictionary to JSON with a timestamped filename.

    Returns the written file path.
    """
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = os.path.join(output_dir, f'{filename_prefix}_{ts}.json')
    with open(filepath, 'w') as f:
        json.dump(result_dict, f, indent=4)
    return filepath

def load_result_json(filepath):
    """
    Load a saved result JSON file and return the dictionary.
    """
    with open(filepath, 'r') as f:
        return json.load(f)

def solve_sim_annealing(Q, Beta, save=False, output_dir="result_raw"):
    """
    Solves the QUBO model using simulated annealing, computes the time to solution, and returns the samples.

    Parameters
    ----------
    Q : np.array
        The Q matrix of the QUBO model.
    Beta : float
        The offset of the QUBO model.
    save : bool, optional
        Whether to save results to files, by default False
    output_dir : str, optional
        Directory to save output files, by default "."

    Returns
    -------
    simAnnSamples : dimod.SampleSet
        The samples returned by the simulated annealing solver.
    execution_time : float
        The time to solution for the simulated annealing solver.
    """
    model = dimod.BinaryQuadraticModel.from_qubo(Q, offset=Beta)
    simAnnSampler = neal.SimulatedAnnealingSampler()
      
    # Time the execution of the sampling
    start = time.perf_counter()
    simAnnSamples = simAnnSampler.sample(model, num_reads=1000)
    end = time.perf_counter()

    # Compute time to solution for the simulated annealing sampler
    execution_time = end - start

    print("Execution time (simAnn): ", execution_time) 
    
    if save:
        os.makedirs(output_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')

        result_dict = _serialize_sampleset_to_result_dict(
            sampleset=simAnnSamples,
            execution_time=execution_time,
            solver_name="simulated_annealing",
            include_solutions=False
        )
        save_result_json(result_dict, output_dir, filename_prefix='SA_results')

    return simAnnSamples, execution_time

def solve_qa_dwave(Q: np.ndarray, Beta: float, save: bool=False, output_dir="result_raw", topology: Optional[str] = None):
    """
    Solves the QUBO model using quantum annealing and returns the samples.

    Parameters
    ----------
    Q : np.array
        The Q matrix of the QUBO model.
    Beta : float
        The offset of the QUBO model.
    save : bool, optional
        Whether to save results to files, by default False
    output_dir : str, optional
        Directory to save output files, by default "result_raw"
    topology : str, optional
        The topology of the D-Wave quantum annealer, by default None
        Note: options are "pegasus" (default), "zephyr"
        See DWaveSampler documentation for available topologies: https://docs.dwavequantum.com/en/latest/quantum_research/topologies.html#

    Returns
    -------
    DWaveSamples : dimod.SampleSet
        The samples returned by the quantum annealing solver.
    execution_time : float
        The time to solution for the quantum annealing solver.
    """
    # Create a binary quadratic model
    model = dimod.BinaryQuadraticModel.from_qubo(Q, offset=Beta)

    # Select sampler based on topology if provided
    base_sampler = DWaveSampler(solver=dict(topology__type=topology)) if topology else DWaveSampler()
    system_name = base_sampler.solver.name

    # Time the execution of the sampling
    start = time.perf_counter()
    DWavesampler = EmbeddingComposite(base_sampler)
    DWaveSamples = DWavesampler.sample(
        bqm=model,
        num_reads=1000,
        return_embedding=True,
        # chain_strength=chain_strength,
        # annealing_time=annealing_time
    )
    DWaveSamples.resolve()
    end = time.perf_counter()

    # Compute time to solution for the quantum annealing sampler
    execution_time = end - start

    print("Execution time (QAnn): ", execution_time)
    print("System name: ", system_name) 

    print(DWaveSamples.info)

    if save:
        os.makedirs(output_dir, exist_ok=True)
        solver_topology = base_sampler.properties.get("topology", {})
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')

        meta = {
            "topology": solver_topology,
            "solver_name": system_name,
        }

        result_dict = _serialize_sampleset_to_result_dict(
            sampleset=DWaveSamples,
            execution_time=execution_time,
            solver_name=f"dwave_qpu_{system_name}",
            include_solutions=False,
            extra_meta=meta
        )
        # Guarantee top-level info present even if serializer changes in future
        if 'info' not in result_dict and hasattr(DWaveSamples, 'info') and isinstance(DWaveSamples.info, dict):
            info_copy = dict(DWaveSamples.info)
            result_dict['info'] = info_copy
        save_result_json(result_dict, output_dir, filename_prefix='Dwave_QA_results')

    return DWaveSamples, execution_time

def solve_quantum_annealing(Q: np.ndarray, Beta: float, save: bool=False):
    """
    DEPRECATED: Use solve_qa_dwave instead. Kept for backward compatibility.
    """
    print("Warning: solve_quantum_annealing is deprecated. Use solve_qa_dwave instead.")
    return solve_qa_dwave(Q, Beta, save=save)

def solve_eqc_qci(Q, beta, filename, num_sample=5, jobinfo=False, output_dir="result_raw"):
    from qci_client import QciClient

    # Make the Q symmetric
    symQ = (Q.T/2)+Q/2
    
    # Get API token from environment variable
    token = os.getenv("QCI_API_TOKEN")
    if not token:
        raise ValueError(
            "QCI_API_TOKEN environment variable not set. "
            "Please set it with: export QCI_API_TOKEN='your-actual-token'"
        )
    api_url = "https://api.qci-prod.com"
    qclient = QciClient(api_token=token, url=api_url)

    qubo_data = {
        'file_name': filename,
        'file_config': {'qubo': {"data": symQ}}
    }

    response_json = qclient.upload_file(file=qubo_data)

    job_body = qclient.build_job_body(job_type="sample-qubo",
                                      qubo_file_id=response_json['file_id'],
                                      job_params={"device_type": "dirac-1", "num_samples": num_sample})
    print(f'job_body result: {job_body}')

    job_response = qclient.process_job(job_body=job_body)
    print(f'job_response result: {job_response}')

    # Create a dictionary to store the QCI results
    qci_result = {}

    # Add the beta offset to the objective value and print it
    # Note: The beta offset is added to the energies returned by the QCI API
    obj_val = job_response['results']['energies'] + beta
    print(f'Objective value: {obj_val}')

    qci_result['energy'] = obj_val
    qci_result['num_occurrences'] = job_response['results']['counts']
    qci_result['num_samples'] = job_body['job_submission']['device_config']['dirac-1']['num_samples']
    qci_result['execution_time'] = job_response['job_info']['job_result']['device_usage_s']   # in seconds
    qci_result['solutions'] = job_response['results']['solutions']

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    # JSON (unified) already in correct schema for downstream
    with open(os.path.join(output_dir, f'QCI_EQC_results_{ts}.json'), 'w') as f:
        json.dump(qci_result, f, indent=4)

    qci_result_df = sampleset_to_df(qci_result, imported=True, qci_extra=True)
    t_qci = qci_result['execution_time']

    if jobinfo is True:
        return qci_result_df, t_qci, job_body, job_response
    else:
        return qci_result_df, t_qci

def solve_using_qci(Q, beta, filename, num_sample=5, jobinfo=False):
    """DEPRECATED: Use solve_eqc_qci instead."""
    print("Warning: solve_using_qci is deprecated. Use solve_eqc_qci instead.")
    return solve_eqc_qci(Q, beta, filename, num_sample=num_sample, jobinfo=jobinfo)

def import_sampleset(path, qa=False, qci_extra=False):
    with open(path, 'r') as f:
        result = json.load(f)
    df_or_tuple = sampleset_to_df(result, imported=True, qci_extra=qci_extra)

    # If QA, return both the execution time and the qpu access time in seconds 
    if qa:
        t_qa_qpu = result['info']['timing']['qpu_access_time'] / 1e6
        return df_or_tuple, t_qa_qpu

    # sampleset_to_df(imported=True) returns (df, execution_time)
    return df_or_tuple

def calculate_tts(sample_set, exec_time, energy_threshold, s=0.99): 
    """
    Calculate the time to solution (optimality or feasibility) for the simulated annealing solver.

    Parameters
    ----------
    sample_set : dimod.SampleSet or pd.DataFrame
        The samples returned by the simulated or quantum annealing solver.    
    exec_time : float
        The execution time of the simulated or quantum annealing solver.
    energy_threshold : float
        The energy threshold for the optimal or feasible solution.
    s : float, optional
        The success probability, by default 0.99
    """
    t = exec_time

    # Define probability of finding solution in dist with energy <= energy_threshold 
    p = 0
    n = 0 # total number of samples

    if isinstance(sample_set, pd.DataFrame):
        # If the sample_set is a DataFrame, extract the relevant columns
        dist = sample_set

        if 'Occurrences' in dist.columns:
            for idx, row in dist.iterrows():
                energy = idx
                num_ocu = row['Occurrences']

                if energy <= energy_threshold:
                    p += num_ocu

                n += num_ocu
        
        else: 
            for _, row in dist.iterrows():
                energy = row['energy']
                num_ocu = row['num_occurrences']
                
                if energy <= energy_threshold:
                    p += num_ocu

                n += num_ocu

    else:
        dist = sample_set.aggregate()
        for sample, energy, num_ocu in dist.data(['sample', 'energy', 'num_occurrences']):
            if energy <= energy_threshold:
                p += num_ocu

            n += num_ocu
        
    # Normalize the probability
    p = p/n if n > 0 else 0
    print(f'Probability of solution <= {energy_threshold} : {p}')

    # Compute time to solution
    if p == 1:
        TTS = t
    elif p == 0:
        TTS = np.inf
    else:
        TTS = t*np.log(1 - s)/np.log(1 - p)

    print(f'Time to solution <= {energy_threshold} : {TTS}')

    return TTS
