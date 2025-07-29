import time
import pandas as pd
import numpy as np
import dimod 
import neal

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

def solve_sim_annealing(Q, Beta, save=False, output_dir="."):
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
    start = time.time()
    simAnnSamples = simAnnSampler.sample(model, num_reads=1000)
    end = time.time()

    # Compute time to solution for the simulated annealing sampler
    execution_time = end - start

    print("Execution time (simAnn): ", execution_time) 
    
    if save:
        import os
        os.makedirs(output_dir, exist_ok=True)
        simAnnSamples.to_pandas_dataframe().to_csv(os.path.join(output_dir, 'SA_results.csv'))
        simAnnSamples.info['tts_tictoc'] = execution_time
        with open(os.path.join(output_dir, 'SA_run_info.txt'), 'w') as f:
            pprint(simAnnSamples.info, stream=f)

    return simAnnSamples, execution_time

def solve_qa_dwave(Q: np.ndarray, Beta: float, save: bool=False, output_dir="result_raw"):
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

    Returns
    -------
    DWaveSamples : dimod.SampleSet
        The samples returned by the quantum annealing solver.
    execution_time : float
        The time to solution for the quantum annealing solver.
    """
    # Create a binary quadratic model
    model = dimod.BinaryQuadraticModel.from_qubo(Q, offset=Beta)
    

    # Time the execution of the sampling
    start = time.time()
    DWavesampler = EmbeddingComposite(DWaveSampler())
    DWaveSamples = DWavesampler.sample(bqm=model, num_reads=1000, 
                                    return_embedding=True, 
                                    #  chain_strength=chain_strength, 
                                    #  annealing_time=annealing_time
                                    )
    end = time.time()

    # Compute time to solution for the quantum annealing sampler
    execution_time = end - start

    print("Execution time (QAnn): ", execution_time) 
    
    print(DWaveSamples.info)

    if save:
        import os
        os.makedirs(output_dir, exist_ok=True)
        DWaveSamples.to_pandas_dataframe().to_csv(os.path.join(output_dir, 'Dwave_QA_results.csv'))
        DWaveSamples.info['tts_tictoc'] = execution_time
        with open(os.path.join(output_dir, 'Dwave_QA_run_info.txt'), 'w') as f:
            pprint(DWaveSamples.info, stream=f)
        
    return DWaveSamples, execution_time

def solve_eqc_qci(Q, beta, filename, num_sample=5, jobinfo=False, output_dir="."):
    from qci_client import QciClient
    
    # Make the Q symmetric
    symQ = (Q.T/2)+Q/2
    # Get API token from environment variable or use placeholder
    import os
    token = os.getenv("QCI_API_TOKEN", "YOUR_API_TOKEN_HERE")
    api_url = "https://api.qci-prod.com"
    qclient = QciClient(api_token=token, url=api_url)
    
    qubo_data = {
    'file_name': filename,
    'file_config': {'qubo':{"data": symQ}}
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
    
    if jobinfo is True:
        return qci_result, job_body, job_response 

    return qci_result   
    
def sampleset_to_df(results, skip=1, imported=False, qci=False):
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
    qci : bool, optional
        If the results are from QCI, includes 'solutions', 'num_samples', 'execution_time', etc., 
        by default False
    """

    if imported:
        energies = results['energy']
        occurrences = results['num_occurrences']
    else:
        energies = results.data_vectors['energy']
        occurrences = results.data_vectors['num_occurrences']

    counts = Counter(energies)
    total = sum(occurrences)
    counts = {}
    for index, energy in enumerate(energies):
        if energy in counts.keys():
            counts[energy] += occurrences[index]
        else:
            counts[energy] = occurrences[index]
    for key in counts:
        counts[key] /= total
    df = pd.DataFrame.from_dict(counts, orient='index').sort_index()

    # index is the energy, the column is the probability
    df.columns = ['Probability']
    df.index.name = 'Energy'

    if qci:
        # Flattened columns of interest
        df_extra = pd.DataFrame({
            "Energy": energies,
            "Occurrences": occurrences
        })

        if 'solutions' in results:
            df_extra['Solution'] = [list(sol) for sol in results['solutions']]

        if 'num_samples' in results:
            df_extra['Num_Samples'] = results['num_samples']

        if 'execution_time' in results:
            df_extra['Execution_Time'] = results['execution_time']

        # Merge on Energy to retain consistency
        df_extra_grouped = df_extra.groupby("Energy").agg({
            "Occurrences": "sum",
            "Solution": lambda x: list(x),
            "Num_Samples": "first",
            "Execution_Time": "first"
        }).reset_index()

        df_full = df.reset_index().merge(df_extra_grouped, on="Energy", how="left")
        df = df_full.set_index("Energy")

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
