import time
import pandas as pd
import numpy as np
import dimod 
import neal
from typing import Optional
import os
import json
from datetime import datetime

from dwave.system import DWaveSampler, EmbeddingComposite
from pprint import pprint
from collections import Counter

# ==================== Functions for Discrete/QUBO Optimization ====================
def solve_enumerate(Q, Beta):
    """
    Solves the QUBO model using the exact solver by enumerating all possible solutions, prints the solving time, and returns the sampling result.

    Parameters
    ----------
    Q : np.array
        The Q matrix of the QUBO model.
    Beta : float
        The offset of the QUBO model.

    Returns
    -------
    exactSamples : dimod.SampleSet
        The samples returned by the exact solver.
    """
    model = dimod.BinaryQuadraticModel.from_qubo(Q, offset=Beta)
    exactSampler = dimod.reference.samplers.ExactSolver()

    # Time the execution of the sampling
    start = time.time()
    exactSamples = exactSampler.sample(model)
    end = time.time()
    print("Execution time: ", end - start) 

    return exactSamples

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
        Directory to save output files, by default "result_raw"

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
    start = time.time()
    simAnnSamples = simAnnSampler.sample(model, num_reads=1000)
    end = time.time()

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
        Note: options are "pegasus", "zephyr"
        See DWaveSampler documentation for available topologies: https://docs.ocean.dwavesys.com/en/stable/docs_dimod/reference/samplers/advanced/dwave_sampler.html#dimod.samplers.advanced.dwave_sampler.DWaveSampler

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
    start = time.time()
    DWavesampler = EmbeddingComposite(base_sampler)
    DWaveSamples = DWavesampler.sample(
        bqm=model,
        num_reads=1000,
        return_embedding=True,
        # chain_strength=chain_strength,
        # annealing_time=annealing_time
    )
    end = time.time()

    # Compute time to solution for the quantum annealing sampler
    execution_time = end - start

    print("Execution time (QAnn): ", execution_time)
    print("System name: ", system_name) 

    print(DWaveSamples.info)

    if save:
        os.makedirs(output_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        result_dict = _serialize_sampleset_to_result_dict(
            sampleset=DWaveSamples,
            execution_time=execution_time,
            solver_name=f"dwave_qpu_{system_name}",
            include_solutions=False
        )
        # Guarantee top-level info present even if serializer changes in future
        if 'info' not in result_dict and hasattr(DWaveSamples, 'info') and isinstance(DWaveSamples.info, dict):
            info_copy = dict(DWaveSamples.info)
            info_copy.setdefault('tts_tictoc', float(execution_time))
            result_dict['info'] = info_copy
        save_result_json(result_dict, output_dir, filename_prefix='Dwave_QA_results')

    return DWaveSamples, execution_time

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

def _serialize_sampleset_to_result_dict(sampleset, execution_time, solver_name, include_solutions=True, extra_meta=None):
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

def import_sampleset(path, qa=False, qci_extra=False):
    """
    Import sampleset from JSON file and convert to DataFrame.
    
    Parameters
    ----------
    path : str
        Path to the JSON file containing the sampleset results.
    qa : bool, optional
        If True, also returns QPU access time for quantum annealing results, by default False
    qci_extra : bool, optional
        If True, includes extra QCI columns (solutions, num_samples, etc.), by default False
        
    Returns
    -------
    tuple or tuple of tuples
        If qa=False: (df, execution_time)
        If qa=True: ((df, execution_time), t_qa_qpu)
    """
    with open(path, 'r') as f:
        result = json.load(f)
    df_or_tuple = sampleset_to_df(result, imported=True, qci_extra=qci_extra)

    # If QA, return both the execution time and the qpu access time in seconds 
    if qa:
        t_qa_qpu = result['info']['timing']['qpu_access_time'] / 1e6
        return df_or_tuple, t_qa_qpu

    # sampleset_to_df(imported=True) returns (df, execution_time)
    return df_or_tuple
    
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

def import_qa_timing_info(filepath):
    """
    Import the timing information from the quantum annealing solver.

    Parameters
    ----------
    filepath : str
        The path to the file containing the timing information.

    Returns
    -------
    execution_time : float
        The time to solution for the quantum annealing solver.
    """
    import ast

    # Read the file as a string
    with open(filepath, 'r') as file:
        content = file.read()

    # Safely evaluate the string to convert it into a Python dictionary
    data = ast.literal_eval(content)

    # Access the 'timing' and 'tts_tictoc' information
    timing_info = data['timing']
    tts_tictoc_info = data['tts_tictoc']

    # Print the results
    print("Timing Info:", timing_info)
    print("TTS Tictoc Info:", tts_tictoc_info)

    return timing_info, tts_tictoc_info

def import_sa_timing_info(filepath):
    """
    Import the timing information from the simulated annealing solver.

    Parameters
    ----------
    filepath : str
        The path to the file containing the timing information.

    Returns
    -------
    timing_info : dict
        The timing information dictionary.
    tts_tictoc_info : float
        The time to solution (tictoc) for the simulated annealing solver.
    """
    import ast

    # Read the file as a string
    with open(filepath, 'r') as file:
        content = file.read()

    # Safely evaluate the string to convert it into a Python dictionary
    data = ast.literal_eval(content)

    # Access the 'timing' and 'tts_tictoc' information
    timing_info = data.get('timing', {})
    tts_tictoc_info = data.get('tts_tictoc', None)

    # Print the results
    print("Timing Info:", timing_info)
    print("TTS Tictoc Info:", tts_tictoc_info)

    return timing_info, tts_tictoc_info

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

def summarize_bar_graph_data(df_list, df_names, round_decimals=2):
    """
    Create a summary DataFrame for multi-bar graph data.

    Parameters
    ----------
    df_list : list of pd.DataFrame
        The list of dataframes to summarize.
    df_names : list of str
        The names of the dataframes.
    round_decimals : int, optional
        The number of decimal places to round the energy levels to, by default 2.

    Returns
    -------
    pd.DataFrame
        The summarized DataFrame with probabilities from each input dataframe.
    """
    # Round indices for consistency
    for df in df_list:
        df.index = df.index.map(lambda x: round(x, round_decimals))
    
    # Get all unique energy levels
    energy_levels = sorted(set.union(*(set(df.index) for df in df_list)))
    
    summary_df = pd.DataFrame({'Energy': energy_levels}).set_index('Energy')

    # Add each dataframe's probability as a separate column
    for df, name in zip(df_list, df_names):
        # Group by rounded energy levels
        grouped_df = df.groupby(df.index).sum()
        # Join to the summary dataframe
        summary_df[name] = grouped_df['Probability']
    
    # Replace NaN with 0 where energy levels are missing in some datasets
    # summary_df = summary_df.fillna(0)
    
    return summary_df

# ==================== Filepath Management Functions ====================
def setup_output_directories(base_dir=".", create_dirs=True):
    """
    Set up output directories for the optimization results.
    
    Parameters
    ----------
    base_dir : str, optional
        Base directory for outputs, by default "."
    create_dirs : bool, optional
        Whether to create directories if they don't exist, by default True
        
    Returns
    -------
    dict
        Dictionary containing paths to various output directories
    """
    import os
    
    dirs = {
        'base': base_dir,
        'result_raw': os.path.join(base_dir, 'result_raw'),
        'julia_exports': os.path.join(base_dir, 'julia_exports'),
        'plots': os.path.join(base_dir, 'plots')
    }
    
    if create_dirs:
        for dir_path in dirs.values():
            os.makedirs(dir_path, exist_ok=True)
    
    return dirs

def get_julia_export_paths(base_dir=".", file_suffix="1"):
    """
    Get the filepaths for Julia export files.
    
    Parameters
    ----------
    base_dir : str, optional
        Base directory containing julia_exports, by default "."
    file_suffix : str, optional
        Suffix for the export files, by default "1"
        
    Returns
    -------
    dict
        Dictionary containing paths to Julia export files
    """
    import os
    
    julia_dir = os.path.join(base_dir, 'julia_exports')
    
    return {
        'Q_matrix': os.path.join(julia_dir, f'Q_matrix_{file_suffix}.csv'),
        'L_vector': os.path.join(julia_dir, f'L_vector_{file_suffix}.csv'),
        'scalars': os.path.join(julia_dir, f'scalars_{file_suffix}.csv')
    }

def compare_dataframe_energy_levels(df_list, df_names, round_decimals=2, energy_threshold=None):
    """
    Compare energy levels across multiple dataframes and create a summary table.
    
    This function compares energy levels (rounded to specified decimals) across multiple
    dataframes and generates a summary showing:
    - Which energy levels are present in each dataframe
    - Which energy levels are missing in each dataframe
    - A summary table with statistics
    
    Parameters
    ----------
    df_list : list of pd.DataFrame
        List of dataframes to compare. Each dataframe should have energy levels as index.
    df_names : list of str
        List of names for each dataframe (must match length of df_list)
    round_decimals : int, optional
        Number of decimal places to round energy levels for comparison, by default 2
    energy_threshold : float, optional
        If provided, only consider energy levels below this threshold, by default None
        
    Returns
    -------
    dict
        Dictionary containing:
        - 'summary_table': DataFrame with summary statistics for each dataframe
        - 'energy_presence': DataFrame showing which energy levels are present in which dataframes
        - 'missing_energies': dict mapping dataframe names to sets of missing energy levels
        - 'unique_energies': dict mapping dataframe names to sets of unique energy levels
        - 'all_energies': set of all unique energy levels across all dataframes
        
    Examples
    --------
    >>> df_list = [simAnn_df_feas, dwave_df_feas, dwave_df_adv2_feas, qci_result_df]
    >>> df_names = ['SA', 'QA_adv1', 'QA_adv2', 'QCI']
    >>> results = compare_dataframe_energy_levels(df_list, df_names)
    >>> print(results['summary_table'])
    >>> print(results['missing_energies']['QA_adv2'])
    """
    if len(df_list) != len(df_names):
        raise ValueError(f"df_list and df_names must have the same length. Got {len(df_list)} and {len(df_names)}")
    
    # Round energy levels and filter by threshold if provided
    df_rounded_list = []
    energy_sets = {}
    
    for df, name in zip(df_list, df_names):
        df_rounded = df.copy()
        
        # Filter by threshold if provided
        if energy_threshold is not None:
            df_rounded = df_rounded[df_rounded.index < energy_threshold]
        
        # Round energy levels
        df_rounded.index = df_rounded.index.map(lambda x: round(x, round_decimals))
        df_rounded_list.append(df_rounded)
        
        # Get unique energy levels
        energy_sets[name] = set(df_rounded.index)
    
    # Get all unique energy levels across all dataframes
    all_energies = set()
    for energy_set in energy_sets.values():
        all_energies.update(energy_set)
    all_energies = sorted(all_energies)
    
    # Create summary table
    summary_data = []
    missing_energies_dict = {}
    
    for name, energy_set in energy_sets.items():
        # Find missing energies (present in others but not in this dataframe)
        other_energies = set()
        for other_name, other_energy_set in energy_sets.items():
            if other_name != name:
                other_energies.update(other_energy_set)
        
        missing_energies = other_energies - energy_set
        missing_energies_dict[name] = missing_energies
        
        # Find unique energies (only in this dataframe)
        unique_energies = energy_set - other_energies
        
        # Get dataframe for statistics
        df_idx = df_names.index(name)
        df_rounded = df_rounded_list[df_idx]
        
        summary_data.append({
            'Dataframe': name,
            'Total_Energy_Levels': len(energy_set),
            'Unique_Energy_Levels': len(unique_energies),
            'Missing_Energy_Levels': len(missing_energies),
            'Min_Energy': min(energy_set) if energy_set else None,
            'Max_Energy': max(energy_set) if energy_set else None,
            'Best_Energy': min(energy_set) if energy_set else None
        })
    
    summary_table = pd.DataFrame(summary_data)
    
    # Create energy presence table (binary matrix)
    presence_data = []
    for energy in all_energies:
        row = {'Energy': energy}
        for name in df_names:
            row[name] = 1 if energy in energy_sets[name] else 0
        presence_data.append(row)
    
    energy_presence = pd.DataFrame(presence_data)
    energy_presence = energy_presence.set_index('Energy')
    
    return {
        'summary_table': summary_table,
        'energy_presence': energy_presence,
        'missing_energies': missing_energies_dict,
        'unique_energies': {name: energy_sets[name] - (set().union(*[energy_sets[n] for n in df_names if n != name])) 
                          for name in df_names},
        'all_energies': set(all_energies)
    }

def imported_json_to_df(filepath):
    """
    Import the JSON file to a dataframe.

    Parameters
    ----------
    filepath : str
        The path to the JSON file.

    Returns
    -------
    df : pd.DataFrame
        The dataframe containing the energies, occurrences, and solutions.
    """
    with open(filepath, 'r') as f:
        data = json.load(f)
    df_energies = data['energy']
    df_occurrences = data['num_occurrences']
    df_solutions = data['solutions']
    df = pd.DataFrame({'Energy': df_energies, 'Occurrences': df_occurrences, 'Solutions': df_solutions})
    return df