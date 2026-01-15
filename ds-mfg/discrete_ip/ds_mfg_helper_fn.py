import networkx as nx
import time
import statistics
from minorminer import find_embedding
from dwave.system import DWaveSampler
import dimod
import numpy as np
import pandas as pd

def logical_graph_from_bqm(bqm):
    G = nx.Graph()
    G.add_nodes_from(bqm.variables)
    G.add_edges_from(bqm.quadratic)
    return G

def hardware_graph_from_sampler(sampler):
    H = nx.Graph()
    H.add_edges_from(sampler.edgelist)
    return H

def measure_embedding_time(logical_G, hardware_H, trials=30, seed=None):
    """
    Measure embedding time for a given logical graph and hardware graph.
    
    Parameters:
    -----------
    logical_G : networkx.Graph
        Logical graph of the QUBO model
    hardware_H : networkx.Graph
        Hardware graph of the DWave sampler
    trials : int, optional
        Number of trials for embedding measurement (default: 30)
    seed : int, optional
        Random seed for embedding measurement (default: None)

    | Field       | Meaning                                 |
    | ----------- | --------------------------------------- |
    | `trials`    | Total attempts                          |
    | `successes` | Embeddings found                        |
    | `failures`  | Embeddings not found                    |
    | `median_s`  | Typical embedding time                  |
    | `p90_s`     | Conservative upper-bound embedding time |
    | `min_s`     | Best-case embedding                     |
    | `max_s`     | Worst-case embedding                    |

    Returns:
    --------
    dict
        Dictionary containing embedding time statistics

    """
    times = []
    failures = 0

    for _ in range(trials):
        t0 = time.perf_counter()
        emb = find_embedding(logical_G.edges, hardware_H.edges, random_seed=seed)
        t1 = time.perf_counter()

        if not emb:
            failures += 1
            continue

        times.append(t1 - t0)

    if not times:
        raise RuntimeError(f"No embeddings found in {trials} trials (failures={failures}).")

    times_sorted = sorted(times)
    # Calculate 90th percentile of embedding time
    p90 = times_sorted[int(0.9 * (len(times_sorted)-1))]

    return {
        "trials": trials,
        "successes": len(times),
        "failures": failures,
        "median_s": statistics.median(times),
        "p90_s": p90,
        "min_s": min(times),
        "max_s": max(times),
    }

def measure_embedding_times_for_samplers(Q, beta, topology__type, trials=30):
    """
    Measure embedding time for a given QUBO model and topology type.
    
    Parameters:
    -----------
    Q : dict
        QUBO matrix as a dictionary of (i, j) -> value pairs
    beta : float
        Offset value for the QUBO model
    topology__type : str
        Topology type for the DWave sampler (e.g., "pegasus", "zephyr")
    trials : int, optional
        Number of trials for embedding measurement (default: 30)
    
    Returns:
    --------
    dict
        Dictionary containing embedding time statistics
    """

    # Create BQM model from Q and beta
    model = dimod.BinaryQuadraticModel.from_qubo(Q, offset=beta)
    
    # Create logical graph from BQM
    logical_G = logical_graph_from_bqm(model)
    
    # Create sampler with specified topology
    sampler = DWaveSampler(solver=dict(topology__type=topology__type))
    
    # Get hardware graph from sampler
    H = hardware_graph_from_sampler(sampler)
    
    # Measure embedding time
    embedding_time = measure_embedding_time(logical_G, H, trials=trials)
    
    return embedding_time

def qubo_dict_from_matrix(Q):
    Q = np.asarray(Q, dtype=float)
    n = Q.shape[0]
    assert Q.shape == (n, n)

    Qdict = {}

    # Diagonal terms
    diag = np.diag(Q)
    for i, v in enumerate(diag):
        if v != 0.0:
            Qdict[(i, i)] = float(v)

    # Off-diagonal: combine both directions into one undirected term
    # (This corresponds to the x^T Q x interpretation.)
    rows, cols = np.nonzero(Q)
    for i, j in zip(rows, cols):
        if i < j:
            v = Q[i, j] + Q[j, i]
            if v != 0.0:
                Qdict[(int(i), int(j))] = float(v)

    return Qdict

def compare_Qs(Q, beta, topology__type, trials=30):
    """
    Compare embedding times for different QUBO models and topologies.
    
    Parameters:
    -----------
    Q : dict
        QUBO matrix as a dictionary of (i, j) -> value pairs
    beta : float
        Offset value for the QUBO model
    topology__type : str
        Topology type for the DWave sampler (e.g., "pegasus", "zephyr")
    trials : int, optional
        Number of trials for embedding measurement (default: 30)
    
    Returns:
    --------
    dict
        Dictionary containing embedding time statistics
    """

    Qdict = qubo_dict_from_matrix(Q)
    model_dict = dimod.BinaryQuadraticModel.from_qubo(Qdict, offset=beta)
    model = dimod.BinaryQuadraticModel.from_qubo(Q, offset=beta)

    print("Same #variables?", len(model_dict.variables) == len(model.variables))
    print("Same #interactions?", model_dict.num_interactions == model.num_interactions)
    print("Offset A, B:", model_dict.offset, model.offset)

    # Compare linear and quadratic biases exactly
    same_linear = all(model_dict.linear[v] == model.linear[v] for v in model.variables)
    same_quadr = all(model_dict.quadratic[u, v] == model.quadratic[u, v] for u, v in model.quadratic)

    print("Linear identical?", same_linear)
    print("Quadratic identical?", same_quadr)
   
def compare_dataframe_energy_levels(df_list, df_names, round_decimals=2, energy_threshold=None, display=False):
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
    display : bool, optional
        If True, print a detailed summary of the comparison including summary statistics,
        missing energy levels, unique energy levels, and energy presence matrix, by default False
        
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
    >>> results = compare_dataframe_energy_levels(df_list, df_names, display=True)
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
    
    # Calculate unique energies
    unique_energies_dict = {name: energy_sets[name] - (set().union(*[energy_sets[n] for n in df_names if n != name])) 
                          for name in df_names}
    
    # Display results if requested
    if display:
        # Display summary table
        print("=" * 60)
        print("ENERGY LEVEL COMPARISON SUMMARY")
        print("=" * 60)
        print("\nSummary Statistics:")
        print(summary_table.to_string(index=False))
        
        # Display missing energies for each dataframe
        print("\n" + "=" * 60)
        print("MISSING ENERGY LEVELS BY DATAFRAME")
        print("=" * 60)
        for name in df_names:
            missing = missing_energies_dict[name]
            if missing:
                print(f"\n{name} - Missing {len(missing)} energy level(s):")
                # Show which other dataframes have these missing energies
                for energy in sorted(missing):
                    sources = []
                    for other_name in df_names:
                        if other_name != name:
                            # Check if this energy is present in the other dataframe
                            if energy in energy_presence.index:
                                if energy_presence.loc[energy, other_name] == 1:
                                    sources.append(other_name)
                    if sources:
                        print(f"  {energy:.2f} (found in: {', '.join(sources)})")
            else:
                print(f"\n{name} - No missing energy levels (contains all energy levels from other dataframes)")
        
        # Display unique energies (only in this dataframe)
        print("\n" + "=" * 60)
        print("UNIQUE ENERGY LEVELS BY DATAFRAME")
        print("=" * 60)
        for name in df_names:
            unique = unique_energies_dict[name]
            if unique:
                print(f"\n{name} - Has {len(unique)} unique energy level(s) not found in others:")
                for energy in sorted(unique):
                    print(f"  {energy:.2f}")
            else:
                print(f"\n{name} - No unique energy levels (all energy levels also found in other dataframes)")
        
        # Display the full energy presence matrix
        print("\n" + "=" * 60)
        print("ENERGY PRESENCE MATRIX (first 20 rows)")
        print("=" * 60)
        print(energy_presence.head(20).to_string())
    
    return {
        'summary_table': summary_table,
        'energy_presence': energy_presence,
        'missing_energies': missing_energies_dict,
        'unique_energies': unique_energies_dict,
        'all_energies': set(all_energies)
    }