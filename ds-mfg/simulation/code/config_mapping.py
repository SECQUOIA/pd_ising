"""
Based on the combinations of operating modes for the reactors, vaporizers, and crystallizers from the configuration optimization framework, this script writes the result combination of operating modes to a file 'active_fs.txt' from the configuration optimization result. 

"""
import itertools
import re
from generating_structures import make_graph, get_input_dictionary
import json

def generate_graphs(valid_combos, file_name=None, identify_uo=False):
    """
    Generate graphs for all valid combinations of operating modes for the reactors, vaporizers, and crystallizers.

    Parameters
    ----------
    valid_combos : list
        List of valid combinations of operating modes for the reactors, vaporizers, and crystallizers.
    name : str, optional
        Name of the file to save the graphs, by default None
    identify_uo : bool, optional
        If True, the units in the graph will be replaced with the corresponding combination units, by default False

    """

    # Open a file to save all graphs
    if file_name: 
        output_name = file_name
    else: 
        output_name = 'all_graphs.txt'

    with open(output_name, 'w') as file:
        for combo in valid_combos:
            layout = combo  # The layout is directly the valid combo tuple
            graph = make_graph(layout)
            
            if identify_uo:
            # Replace the units in the graph with the corresponding combination units
                for i, unit in enumerate(["R01", "R02", "VAP01", "CR01"]):
                    graph = re.sub(rf"\b{unit}\b", f"{unit}: '{combo[i]}'", graph)

            # Write the combination and the corresponding graph to the file
            file.write(f"Combination: {combo}\n")
            file.write(f"Graph:\n{graph}\n")
            file.write("-" * 40 + "\n")  # Add a separator between different graphs
            
            # print(f"Graph for combo {combo} saved in all_graphs.txt")

    print(f"All graphs have been saved to {output_name}")
    
def identify_unique_uos_from_file(filename):
    """
    Identify unique unit operations (UOs) that are separated by '-->' in the graph data from a text file.

    Parameters
    ----------
    filename : str
        Name of the file containing the graph data.

    Returns
    -------
    unique_uos : set
        Set of unique unit operations (UOs) found in the graphs.
    """
    
    unique_uos = set()

    with open(filename, 'r') as file:
        data = file.read()

    # Find all graph sections in the file
    graphs = re.findall(r"Graph:\n(.+?)\n-{40}", data, re.DOTALL)

    for graph in graphs:
        # Extract units that are separated by '-->'
        uos_in_graph = re.split(r"\s*-->\s*", graph.strip())

        # Add each unique UO to the set
        unique_uos.update(uos_in_graph)

        # Include the last unit (after the last '-->'), which may not be captured
        last_uo = re.search(r"-->\s*([A-Z0-9]+[0-9]*)", graph)
        if last_uo:
            unique_uos.add(last_uo.group(1))

    return unique_uos



# All reactor operating mode options
R01_opts = ['batch', 'CSTR', 'PFR', 'Semibatch']
R02_opts = ['batch', 'CSTR', 'PFR', 'Semibatch']

# All vaporizer operating mode options
VAP01_opts = ['batch']

# All crystallizer operating mode options
CR01_opts = ['batchU', 'cont1', 'cont2', 'cont3']  # Add batch seeded (batchS) if it is not too hard.

# Ordering 
UO_keys = {0: 'R01', 1: 'R02', 2: 'VAP01', 3: 'CR01'}
UO_keys_sb = {0: 'R01', 2: 'VAP01', 3: 'CR01'}

all_combos = list(itertools.product(*[R01_opts, R02_opts, VAP01_opts, CR01_opts]))
valid_combos = []

# Heuristic rules for valid combinations can be added here -- this can be translated into constraints in the optimization problem
for i in all_combos:
    if 'Semibatch' not in i:
        valid_combos.append(i)
    elif i[0] == 'Semibatch' and i[1] == 'Semibatch':
        # if R01 is semibatch, R02 must be semibatch for valid combo
        valid_combos.append(i)

# Save the valid combos to a file
with open('valid_combos.txt', 'w') as f:
    for i in valid_combos:
        f.write(str(i) + '\n')

# Generate graphs for all valid combinations of operating modes
# generate_graphs(valid_combos, file_name='all_graphs_1.txt', identify_uo=True)

with open('../data/bounds.json') as f:
    all_vars = json.load(f)

# Generate input dictionary for each valid combination of operating modes

x_input = []

for combo in valid_combos:
    print(combo)
    layout = combo  # The layout is directly the valid combo tuple
    input = get_input_dictionary(all_vars, layout)
    x_input.append(input)

print(x_input)

# Start with a set of combinations to obtain capital costs from each unit (?) 
# These capital costs will be used and fed into the flowsheet optimization problem as disjunction penalty costs 
# Will operating costs/raw material costs be considered in the flowsheet optimization problem as the flow cost? 

# From PharmaPy simulation / data to be extracted into the flowsheet optimization problem: 
# - Capital costs for each unit (disjunction penalty costs--but these are parameters)
# - Raw material costs for each unit (flow cost)
# ----- are we tuning the parameters to approximate the objective function value and constraints in the flowsheet optimization problem? 
# - feasibility of the flowsheet (constraints violated or not?)

# (from each iteration of the flowsheet optimization problem)
# - "no good cut" - additional constraint for flowsheet optimization problem for next iteration
# - if the objective function (approximated?) is lower than already found optimal objective function, do not run the simulation ? 


# From flowsheet optimization problem to PharmaPy simulation: 
# - operating modes of each unit (optimal result)
# - binary variables for each unit need to be translated back into unit operating modes
# - 'active_fs.txt' file with the    operating modes of each unit
 
# This script / config_mapping should: 
# - specify the operations (nodes) and their possible operating modes for each node (binary variables)
# - based on the potential operating modes of each node, generate all possible flows (combinations of operating modes)
# - translate these decision options into language that pyomo/qubo can understand 
# ----Pyomo script needs: flows, from node, to node, flow cost, disjunction penalty costs, constraints
# ----QUBO script needs: flows, from node, to node, flow cost, disjunction penalty costs (csv)

# - also have all graphs (all uos included based on the uo choices) and give us the capEx cost which then will be used in the flowsheet optimization problem



# for combo in valid_combos:
#     file = 'active_fs.txt'

#     with open(file, 'w') as filetowrite:
#         for item in combo:
#             filetowrite.write(item + ' ')

#     exec(open("nomad_opt.py").read())

