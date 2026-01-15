import numpy as np
import json
from generating_structures import (get_input_dictionary, run_flowsheet, make_graph)
from helper import translate_scale
from copy import deepcopy

# Extract Capital Expenditure (CAPEX) using PharmaPy's GetCAPEX function for each process configuration in x_input_sorted.csv

path = '../data/compounds_lomustine.json'
data_lines = pd.read_csv('../data/obj_mass_prod_crys/x_input_sorted.csv', header=0, names=['Combination', 'Values'])

# Initialize 'CAPEX' and 'Total_CAPEX' columns in the DataFrame
data_lines['CAPEX'] = None
data_lines['Total_CAPEX'] = None

with open('../data/bounds.json') as f:
    all_vars = json.load(f)

for index, row in data_lines.iterrows():
    # Access the combination string and values string
    combo_str = row['Combination']
    values_str = row['Values']
    
    # Clean and format the combination string
    layout = tuple(combo_str.replace("('", "").replace("')", "").replace("'", "").replace("_", " ").split())
    
    # # Split the numeric values into a list of floats
    x = [float(x) for x in values_str.split()]

    graph = make_graph(layout)
    bound_dict = get_input_dictionary(all_vars, layout)
    input_dict = deepcopy(bound_dict)
    
    count = 0 
    for j in input_dict.keys():
        input_dict[j] = translate_scale(x[count], bound_dict[j])
        count += 1

    # Calling PharmaPy
    flowsheet, success = run_flowsheet(path=path, inputs=input_dict, layout=layout, graph=graph)
    
    if success:
        capex = flowsheet.GetCAPEX()
        total_capex = sum(capex.values()) 

        data_lines.at[index, 'CAPEX'] = capex
        data_lines.at[index, 'Total_CAPEX'] = total_capex   

# Save the updated DataFrame to a new CSV file
data_lines.to_csv('x_input_with_total_capex_2.csv', index=False)
