#!/usr/bin/env python3
"""
Script to automatically process optimization results.

Usage:
    python process_results.py <run_id>
    
Example:
    python process_results.py run_240808_143022
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
import datetime
import argparse

# Add the current directory to the path so we can import from data_organizer_nb
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def parse_log_data(data_list, save=False, exclude_keywords=None):
    """
    Parse the data from log files and return a list of DataFrames, one for each run across all data files.    

    Parameters
    ----------
    data_list : list
        List of data IDs to parse and process.
    save : bool
        If True, the results will be saved to files.
    exclude_keywords : list
        List of keywords to exclude from the run info.

    Returns
    -------
    run_opti : list
        List of DataFrames for each run across all data files.
    run_info : list
        List of strings containing run info across all data files.
    """
    
    if exclude_keywords is None:
        exclude_keywords = [
            "BBE OBJ CONS_H TIME",
            "NOMAD outputs",
            "X_sol=x_best",
            "F_sol=f_best",
            "H_sol=h_best",
            "NB_evals=nb_evals",
            "NB_iters=nb_iters"
        ]

    run_opti = []
    run_info = []

    for data_id in data_list:
        log_file_path = f'../logs/logfile_{data_id}.txt'
        combi_file_path = f'../data/obj_mass_prod_capex/valid_combos_{data_id}.txt'
        
        # Check if files exist
        if not os.path.exists(log_file_path):
            print(f"Warning: Log file {log_file_path} not found. Skipping...")
            continue
        if not os.path.exists(combi_file_path):
            print(f"Warning: Combinations file {combi_file_path} not found. Skipping...")
            continue
            
        try:
            combi = pd.read_csv(combi_file_path, header=None)
            combi_tuples = [tuple(row) for row in combi.values]
        except Exception as e:
            print(f"Error reading combinations file {combi_file_path}: {e}")
            continue

        with open(log_file_path, 'r') as file:
            lines = file.readlines()

        print(f"Read {len(lines)} lines from log file {log_file_path}")

        # Lists to hold the data for each run
        all_runs = []
        current_run = []
        previous_bbe = None
        current_run_info = []

        # Parse the log file
        for line in lines:
            # Split the line into parts
            parts = line.split()

            # Check if the line has exactly four parts (likely BBE data)
            if len(parts) == 4 and parts[0].isdigit():
                current_bbe = int(parts[0])

                # Check if BBE number has reset, indicating a new run
                if previous_bbe is not None and current_bbe < previous_bbe:
                    if current_run:
                        all_runs.append({
                            'data': current_run,
                            'info': current_run_info
                        })  # Store the previous run's data and info
                        current_run = []  # Start collecting data for the new run
                        current_run_info = []  # Reset the run info

                current_run.append(parts)
                previous_bbe = current_bbe
            else:
                # If it's not BBE data, treat it as run info (e.g., warnings, errors, best solutions)
                current_run_info.append(line.strip())

        if current_run:  # Add the last run if it exists
            all_runs.append({
                'data': current_run,
                'info': current_run_info
            })
        
        print(f"Found {len(all_runs)} potential runs in log file")
        
        # Convert each run's data into a DataFrame and store it in a list
        run_dfs = []
        for i, run in enumerate(all_runs):
            if not run['data']:  # Skip empty runs
                print(f"Skipping run {i+1}: no data")
                continue
                
            df = pd.DataFrame(run['data'], columns=['BBE', 'OBJ', 'CONS_H', 'TIME'])
            df['BBE'] = pd.to_numeric(df['BBE'], errors='coerce')
            df['OBJ'] = pd.to_numeric(df['OBJ'], errors='coerce')
            df['CONS_H'] = pd.to_numeric(df['CONS_H'], errors='coerce')
            df['TIME'] = pd.to_numeric(df['TIME'], errors='coerce')
            
            # Remove rows with NaN values
            df = df.dropna()
            
            if df.empty:  # Skip if no valid data
                print(f"Skipping run {i+1}: no valid data after cleaning")
                continue
            
            run_info_filtered = [line for line in run['info'] if not any(keyword in line for keyword in exclude_keywords) and line.strip()]

            # Match the log data to a combination
            if i < len(combi_tuples):
                combination = combi_tuples[i]
                combination_str = '_'.join(combination)
            else:
                combination_str = f'run_{i+1}'  # Default if no matching combination

            # Add the combination information to the top of the run_info
            run_info_filtered.insert(0, f"Combination: {combination_str}")

            # Add the last time data to the run info
            run_info_filtered.append(f"Last Timestamp: {df['TIME'].iloc[-1]}")

            run_dfs.append({
                'data': df,
                'info': run_info_filtered
            })

            if save:
                # Save the data
                output_path = f'../results/parsed_log_{data_id}_{combination_str}.csv'
                df.to_csv(output_path, index=False)
                print(f"Saved: {output_path}")

                # Save the info file with combination info at the top
                info_path = f'../results/parsed_log_{data_id}_{combination_str}_info.txt'
                with open(info_path, 'w') as info_file:
                    info_file.write('\n'.join(run_info_filtered))
                print(f"Saved: {info_path}")

        print(f"Successfully processed {len(run_dfs)} runs with valid data")
        run_opti.extend([run['data'] for run in run_dfs])
        run_info.extend([run['info'] for run in run_dfs])

    return run_opti, run_info

def extract_run_info(info):
    """Extract run information from the info list."""
    best_feasible = None
    best_feas_obj = None
    best_infeasible = None
    blackbox_evals = None
    total_model_evals = None
    cache_hits = None
    total_evals = None
    multiple_feasible = 'No'
    multiple_infeasible = 'No'

    for line in info:
        if 'Best feasible solutions' in line:
            multiple_feasible = 'Yes'
            best_feasible = line.split('#')[-1].split('Evaluation OK')[0].strip()
            best_feas_obj = line.split('f = ')[-1].split('h = ')[0].strip()
        elif 'Best feasible solution' in line:
            best_feasible = line.split('#')[-1].split('Evaluation OK')[0].strip()
            best_feas_obj = line.split('f = ')[-1].split('h = ')[0].strip()
        elif 'Best infeasible solutions' in line:
            multiple_infeasible = 'Yes'
            best_infeasible = line.split('#')[-1].split('Evaluation OK')[0].strip()
        elif 'Best infeasible solution' in line:
            if not best_infeasible:
                best_infeasible = line.split('#')[-1].split('Evaluation OK')[0].strip()
        elif 'Blackbox evaluations' in line:
            blackbox_evals = int(line.split(':')[-1].strip())
        elif 'Total model evaluations' in line:
            total_model_evals = int(line.split(':')[-1].strip())
        elif 'Cache hits' in line:
            cache_hits = int(line.split(':')[-1].strip())
        elif 'Total number of evaluations' in line:
            total_evals = int(line.split(':')[-1].strip())

    return best_feasible, best_feas_obj, multiple_feasible, best_infeasible, multiple_infeasible, blackbox_evals, total_model_evals, cache_hits, total_evals

def generate_summary_table(run_opti, run_info, save=False, filename=None):
    """
    Generate a summary table of best solutions from the parsed log data.

    Parameters
    ----------
    run_opti : list
        List of DataFrames for each run across all data files.
    run_info : list
        List of strings containing run info across all data files.
    save : bool
        If True, the summary table will be saved to a CSV file.

    Returns
    -------
    summary_df : pd.DataFrame
        DataFrame with the summary table of best solutions.
    """

    summary_data = []
    for i, run in enumerate(run_opti):
        if i >= len(run_info):
            continue
            
        try:
            best_feasible, best_feas_obj, multiple_feasible, best_infeasible, multiple_infeasible, blackbox_evals, total_model_evals, cache_hits, total_evals = extract_run_info(run_info[i])
            combination = run_info[i][0].split(': ')[1]
            eval_time = run_info[i][-1].split(': ')[1]
            summary_data.append({
                'Combination': combination,
                'Evaluation Time': eval_time,
                'Best Solution (feasible)': best_feasible,
                'Best Objective Value': best_feas_obj,
                'Multiple Feasible Solutions': multiple_feasible,
                'Best Solution (infeasible)': best_infeasible,
                'Multiple Infeasible Solutions': multiple_infeasible,
                'Blackbox Evaluations': blackbox_evals,
                'Total Model Evaluations': total_model_evals,
                'Cache Hits': cache_hits,
                'Total Number of Evaluations': total_evals,
                'Run Info': run_info[i][1:],  # Store additional run info if needed
            })
        except Exception as e:
            print(f"Error processing run {i}: {e}")
            continue

    summary_df = pd.DataFrame(summary_data)

    if save and not summary_df.empty:
        output_path = f'../results/summary_table_{filename}.csv'
        summary_df.to_csv(output_path, index=False)
        print(f"Saved summary table: {output_path}")

    return summary_df

def main():
    parser = argparse.ArgumentParser(description='Process optimization results')
    parser.add_argument('run_id', help='Run ID to process (e.g., run_240808_143022)')
    parser.add_argument('--save', action='store_true', help='Save individual CSV files for each run')
    parser.add_argument('--summary', action='store_true', help='Generate summary table')
    
    args = parser.parse_args()
    
    run_id = args.run_id
    
    print(f"Processing results for run: {run_id}")
    
    # Check if log file exists
    log_file_path = f'../logs/logfile_{run_id}.txt'
    if not os.path.exists(log_file_path):
        print(f"Error: Log file {log_file_path} not found!")
        sys.exit(1)
    
    # Process the data
    print("Parsing log data...")
    run_opti, run_info = parse_log_data([run_id], save=args.save)
    
    if not run_opti:
        print("No valid data found in the log file.")
        sys.exit(1)
    
    print(f"Found {len(run_opti)} runs in the log file.")
    
    # Generate summary table
    if args.summary or args.save:
        print("Generating summary table...")
        summary_df = generate_summary_table(run_opti, run_info, save=True, filename=run_id)
        
        if not summary_df.empty:
            print(f"\nSummary table generated with {len(summary_df)} entries:")
            print(summary_df[['Combination', 'Best Objective Value', 'Evaluation Time']].head())
        else:
            print("No summary data could be extracted.")
    
    print(f"\nProcessing completed for run: {run_id}")
    print(f"Results saved in: ../results/")

if __name__ == "__main__":
    main()
