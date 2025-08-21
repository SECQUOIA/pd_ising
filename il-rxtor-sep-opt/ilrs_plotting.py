
import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt

import dwave_networkx as dnx
import networkx as nx
from collections import Counter

# Functions for plotting 

def draw_Q_matrix(Q):
    G = nx.from_numpy_array(Q)
    nx.draw(G, with_labels=True)
    plt.show()

def plot_multibar_graph_discrete(df_list, df_names, df_colors, feas_ub, vertical_line=None, skip=1, title=None, round_decimals=2):
    """
    Plot the multibar graph of the results of the optimization with discrete (evenly spaced) x-axis,
    ensuring unique energy levels with rounding.

    Parameters
    ----------
    df_list : list of pd.DataFrame
        The list of dataframes to plot.
    df_names : list of str
        The names of the dataframes.
    df_colors : list of str
        The bar colors of the dataframes.
    feas_ub : float
        The upper bound for feasible solutions. Above this value, the solutions are consolidated into one and plotted as one bar.
    vertical_line : float, optional
        The energy level to plot a vertical line at, by default None.
    skip : int, optional
        The number of x-ticks to skip, by default 1.
    title : str, optional
        The plot title, by default None.
    round_decimals : int, optional
        The number of decimal places to round the energy levels to, by default 2.
    """

    # Round the energy levels in all DataFrames
    for df in df_list:
        df.index = df.index.map(lambda x: round(x, round_decimals))
    
    # Combine all energy levels (treat as discrete categories)
    energy_levels = sorted(set.union(*(set(df.index) for df in df_list)))
    
    # Merge dataframes for common energy levels
    unique_dfs = []
    for df in df_list:
        # Group by unique energy levels and sum probabilities for identical levels
        unique_df = df.groupby(df.index).sum()
        # Align the DataFrame with the global energy_levels and fill missing with 0
        aligned_df = pd.DataFrame({'Energy': energy_levels}).set_index('Energy').join(unique_df, how='left').fillna(0)
        unique_dfs.append(aligned_df)

    width = 0.8 / len(df_list)  # Adjust width to avoid overlap

    fig, ax = plt.subplots(figsize=(18, 6))
    
    # Convert energy levels to discrete positions (0, 1, 2, ..., len(energy_levels)-1)
    pos = np.arange(len(energy_levels)) 

    # Plotting the bars at discrete positions
    for i, (df, name, color) in enumerate(zip(unique_dfs, df_names, df_colors)):
        ax.bar(pos + i * width, df['Probability'], width, alpha=0.7, color=color, label=name)

    if vertical_line is not None:
        vertical_line = round(vertical_line, round_decimals)
        ax.axvline(x=energy_levels.index(vertical_line), color='black', linestyle='--', label='Gurobi')

    # Set the y-axis label
    ax.set_ylabel('Probability')
    ax.set_xlabel('Discrete Problem Objective Function')
    plt.yscale('log')

    xtick_labels = [f"> {feas_ub} (infeas)" if e == feas_ub else f"{e:.2f}" if i % skip == 0 else "" for i, e in enumerate(energy_levels)]
    
    group_centers = pos + (width * (len(df_list) - 1)) / 2

    ax.margins(x=0.01)  # horizontal margins on the x-axis
    ax.set_xticks(group_centers)
    ax.set_xticklabels(xtick_labels, rotation=90)

    # Set the chart's title
    if title is not None:
        plt.title(str(title))

    plt.legend(loc='upper center')
    plt.show()