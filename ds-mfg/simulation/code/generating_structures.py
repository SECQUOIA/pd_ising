from PharmaPy.SimExec import SimulationExec

import json
import itertools
from copy import deepcopy

from make_units import add_reactor, add_vaporizer, add_crystallizer, add_filter, add_b2f, add_hold, add_mixer

from helper import path_constraint, translate_scale

with open('../data/bounds.json') as f:
    all_vars = json.load(f)

# All reactor operating mode options
R01_opts = ['batch', 'CSTR', 'PFR', 'Semibatch']
R02_opts = ['batch', 'CSTR', 'PFR', 'Semibatch']

# All vaporizer operating mode options
VAP01_opts = ['batch']

# All crystallizer operating mode options
CR01_opts = ['batchU', 'cont1', 'cont2', 'cont3']  # Add batch seeded (batchS) if it is not too hard.

UO_keys = {0: 'R01', 1: 'R02', 2: 'VAP01', 3: 'CR01'}
# UO_keys_sb = {0: 'R01', 2: 'VAP01', 3: 'CR01'}

all_combos = list(itertools.product(*[R01_opts, R02_opts, VAP01_opts, CR01_opts]))
valid_combos = []

path = '../data/compounds_lomustine.json'
partic_species = ['ISO', 'CHA', 'interm', 'TBN', 'lom', 'TBA', 'SUB1']

for i in all_combos:
    if 'Semibatch' not in i:
        valid_combos.append(i)
    elif i[0] == 'Semibatch' and i[1] == 'Semibatch':
        valid_combos.append(i)


def get_input_dictionary(val_dict, layout):
    values = {}
    if 'Semibatch' in layout:
        values.update(val_dict['R01']['Semibatch'])
    else:
        values.update(val_dict['R01'][layout[0]])
        values.update(val_dict['MIX01'])
        values.update(val_dict['R02'][layout[1]])

    values.update(val_dict['MIX02'])
    values.update(val_dict['VAP01'][layout[2]])

    values.update(val_dict['CR01'][layout[3]])
    values.update(val_dict['F01'])

    return values


# Function for generating the textual graph for the flowsheet
def make_graph(combo):
    graph = 'R01 --> '
    conn = ' --> '
    prev_unit = combo[0]
    curr_unit = combo[1]
    hold_count = 1
    B2F_count = 1
    mixer_count = 1
    for ind, val in enumerate(combo[1:]):
        curr_unit = val
        # If the unit is semibatch, we only have R01, no need for another reactor
        if 'Semibatch' in val:
            prev_unit = val
            mixer_count = 2
            continue

        # Check if the current unit needs a holding tank before it (cont --> batch)
        if 'batch' in curr_unit:
            # Must add a mixer before the vaporizer, and the second reactor
            if ('VAP' in UO_keys[ind + 1]) or ('R02' in UO_keys[ind + 1]):
                graph += ('MIX0' + str(mixer_count) + conn)
                mixer_count += 1
            # Now adding the holding tank if required.
            if 'batch' not in prev_unit:
                graph += ('HOLD' + '0' + str(hold_count) + conn)
                hold_count += 1
            graph += (UO_keys[ind + 1] + conn)
        # Now checking if current unit needs a batch to flow connector (batch --> cont)
        else:
            # Must add a mixer before the vaporizer, and the second reactor
            if ('VAP' in UO_keys[ind + 1]) or ('R02' in UO_keys[ind + 1]):
                graph += ('MIX0' + str(mixer_count) + conn)
                mixer_count += 1
            # Now adding B2F connectors when necessary
            if 'batch' in prev_unit:
                graph += ('BatchToFlow' + '0' + str(B2F_count) + conn)
                B2F_count += 1

            if 'cont' in curr_unit:
                num_cryst = int(curr_unit[-1])
                for i in range(num_cryst):
                    graph += ('CR0' + str(i + 1) + conn)
                graph += ('HOLD' + '0' + str(hold_count) + conn)
                hold_count += 1
            else:
                graph += (UO_keys[ind + 1] + conn)

        prev_unit = curr_unit

    graph += 'F01'
    return graph

# Beyond here testing.


# # Testing make_graph function for generating textual flowsheet configs
# for ind, val in enumerate(valid_combos):
#     graph = make_graph(val)
#     print(graph)
#     print(ind, val)
#     # print(i)
#     # print(get_input_dictionary(all_vars, i))
#
# print(len(valid_combos))


# Testing the system on one combination
def make_flowsheet(path=None, operating_vals=None, layout=None,
                   graph=None):
    """
    Make a flowsheet subject to the layout of the process
    (i.e., Batch --> CSTR --> Batch --> Cont3) with a given
    graph of that process process (either by hand or by
    using the 'make_graph()' function)

    :param path: filepath, Physical properties path
    :param operating_vals: dictionary, values for the operational
    decision variables used for optimization and simulation that correspond
    to those described in the bounds.json file. keys are variable names
    :param layout: tuple, process description of major unit operations
    :param graph: string, graphical representation of process connectivity

    :return: sim, SimulationExecutive object from PharmaPy. (The PharmaPy
    representation of the process that is described by the inputs)
    """
    sim = SimulationExec(path, flowsheet=graph)
    runargs = {}
    split_graph = graph.split()
    first_unit = True
    cycle_time_batch = True
    previous_batch = False
    first_batch = False
    layout_index = 0
    last_layout_unit = ''

    for i in split_graph:
        if layout_index < len(layout):
            curr_layout_unit = layout[layout_index]

        if i == '-->':
            continue
        else:
            # Adding reactors
            if 'R' == i[0]:
                sim, runargs = add_reactor(path=path, reactor_name=i, reactor_type=layout[layout_index],
                                           inputs=operating_vals, first_unit=first_unit,
                                           first_batch=first_batch, sim_obj=sim, runargs=runargs)

                last_layout_unit = curr_layout_unit
                layout_index += 1
            # Adding mixers
            elif 'M' == i[0]:
                sim, runargs = add_mixer(path=path, mixer_name=i, previous_batch=previous_batch,
                                         first_batch=first_batch, inputs=operating_vals,
                                         sim_obj=sim, runargs=runargs)
            # Adding B2F connectors
            elif 'Batch' in i:
                sim, runargs = add_b2f(b2f_name=i, curr_layout_unit=curr_layout_unit,
                                       all_batch=cycle_time_batch, inputs=operating_vals,
                                       sim_obj=sim, runargs=runargs)
            elif 'VAP' in i:
                sim, runargs = add_vaporizer(vaporizer_name=i, first_batch=first_batch,
                                             previous_batch=previous_batch, inputs=operating_vals,
                                             sim_obj=sim, runargs=runargs)

                last_layout_unit = curr_layout_unit
                layout_index += 1
            elif 'CR' in i:
                sim, runargs = add_crystallizer(path=path, cryst_name=i, cryst_type=curr_layout_unit,
                                                inputs=operating_vals, first_batch=first_batch,
                                                all_batch=cycle_time_batch, sim_obj=sim, runargs=runargs)


                layout_index += 1
            elif 'HOLD' in i:
                sim, runargs = add_hold(holder_name=i, sim_obj=sim, runargs=runargs, curr_layout=curr_layout_unit)
            elif 'F01' == i:
                sim, runargs = add_filter(filter_name=i, inputs=operating_vals, sim_obj=sim, runargs=runargs)

        if first_unit:
            first_unit = False
            if 'batch' in last_layout_unit:
                first_batch = True
        if 'batch' in last_layout_unit:
            previous_batch = True
        else:
            cycle_time_batch = False
            previous_batch = False
        # If semibatch is in the system we have (SB, SB, ...)
        # So we need to either add one extra OR increment by 2 when the
        # processed unit is SB. I increment by 2.
        if 'Semibatch' in curr_layout_unit:
            layout_index += 1


    return sim, runargs


def get_median_inputs(val_dict):
    medians = {}
    for item in val_dict.items():
        medians[item[0]] = ((item[1][0] + item[1][1]) / 2.0)

    return medians


# Simulating all the flowsheets in case of issues.
# flowsheets = []

# for i in valid_combos:
#     print(i)
#     graph = make_graph(i)
#     input_dict = get_input_dictionary(all_vars, i)
#     inputs = get_median_inputs(input_dict)
#     test, runargs_out = make_flowsheet(path=path, operating_vals=inputs, layout=i, graph=graph)
#     flowsheets.append((test, runargs_out))
#     # if 'Semibatch' not in i:
#     #     test.SolveFlowsheet(runargs_out, verbose=False)
#     # else:
#     test.SolveFlowsheet(runargs_out, verbose=False)

# Testing individual flowsheet issues.
# problem_scenario = ('batch', 'batch', 'batch', 'cont3')
# problem_graph = make_graph(problem_scenario)
# problem_input_dict = get_input_dictionary(all_vars, problem_scenario)
# problem_inputs = get_median_inputs(problem_input_dict)
# problem_inputs = {'c_in': 0.30, 'time_R01': 4000, 'vol': 5e-2, 'c_TBN': 0.30, 'time_R02': 7200,
#                   'ratio_hept': 2.25, 'time_VAP01': 10800, 'pressure': 2.5e4, 'tau_CR01': 3600, 'T_CR01': 285,
#                   'tau_CR02': 3600, 'T_CR02': 275, 'tau_CR03': 3600, 'T_CR03': 265, 'dP': 1e5, 'diam': 0.5}
#
# fs, runargs_fs = make_flowsheet(path=path, operating_vals=problem_inputs,
#                                 layout=problem_scenario, graph=problem_graph)


def get_objective_value(flowsheet, layout=None, inputs=None):
    """
    Function to get objective function value for the flowsheets.
    The objective function is of the form A*obj1 + B*obj2 where
    the objectives are mass_production_rate and crystal_size.

    :param flowsheet: SimulationExecutive object, the simulated
    version of the flowsheet being optimized.
    :param layout: :param layout: tuple, process description of
    major unit operations
    :param inputs: dictionary, values for the operational decision
    variables used for optimization and simulation that correspond
    to those described in the bounds.json file. keys are variable
    names

    :return: objective value, float, The value of A*obj1 + B*obj2
    """
    mass_out = flowsheet.F01.result.mass_cake_dry[-1] # [kg]

    cycle_time = 10 * 3600.0    # [s]

    if 'batch' in layout[-1]:
        if 'batch' in layout[0]:
            if 'Semibatch' == layout[0]:
                cycle_time = max(inputs['time_R01'], inputs['time_VAP01'],
                                 inputs['time_CR01'])
            elif 'batch' in layout[1]:
                cycle_time = max(inputs['time_R01'], inputs['time_R02'],
                                 inputs['time_VAP01'], inputs['time_CR01'])

    if '2' in layout[-1]:
        moments = flowsheet.CR02.Solid_1.getMoments()
    elif '3' in layout[-1]:
        moments = flowsheet.CR03.Solid_1.getMoments()
    else:
        moments = flowsheet.CR01.Solid_1.getMoments()

    size = moments[1] / (moments[0] + 1e-6) * 1e6   # mean crystal size [um]

    mass_production = mass_out / (cycle_time + 1e-6)    # [kg/s]

    return mass_production * 6.0e4 + size


def get_objective_value_cost(flowsheet, layout=None, inputs=None):
    """
    Function to get objective function value for the flowsheets.
    The objective function is to minimize the capital cost of the
    flowsheet.

    :param flowsheet: SimulationExecutive object, the simulated
    version of the flowsheet being optimized.

    :return: objective value, float
    """
    
    mass_out = flowsheet.F01.result.mass_cake_dry[-1]   # [kg]

    cycle_time = 10 * 3600.0    # [s]

    if 'batch' in layout[-1]:
        if 'batch' in layout[0]:
            if 'Semibatch' == layout[0]:
                cycle_time = max(inputs['time_R01'], inputs['time_VAP01'],
                                 inputs['time_CR01'])
            elif 'batch' in layout[1]:
                cycle_time = max(inputs['time_R01'], inputs['time_R02'],
                                 inputs['time_VAP01'], inputs['time_CR01'])

    mass_production = mass_out / (cycle_time + 1e-6)

    uo_capex = flowsheet.GetCAPEX()
    total_capex = sum(uo_capex.values()) 
    A = -1e3    # [$*s/kg]
    B = 1

    total_obj = A * mass_production + B * total_capex
    # opex = flowsheet.GetOPEX()

    return total_obj

def get_constraints_values(flowsheet, layout=None, inputs=None):
    """
    Function to get constraint function value for the flowsheets.
    Here there are two constraints: The material must not pre-
    maturely crystallize, and the contents exiting the vaporizer
    must be at least 0.7 mole fraction heptane to limit oiling
    out.

    :param flowsheet: SimulationExecutive object, the simulated
    version of the flowsheet being optimized.
    :param layout: :param layout: tuple, process description of
    major unit operations
    :param inputs: dictionary, values for the operational decision
    variables used for optimization and simulation that correspond
    to those described in the bounds.json file. keys are variable
    names

    :return: con values, list, The values of [solub_con, x_C7_con]
    """
    xliqVAP01 = flowsheet.VAP01.result.x_liq
    tempVAP01 = flowsheet.VAP01.result.temp
    timeVAP01 = flowsheet.VAP01.result.time

    concVAP01 = flowsheet.VAP01.Liquid_1.frac_to_conc(mole_frac=xliqVAP01, basis='mass')
    solub = flowsheet.CR01.Kinetics.get_solubility(tempVAP01, mole_frac=xliqVAP01)

    solub_path_con = path_constraint(timeVAP01, concVAP01[:, 4], y_ref=solub, sqrt=True)

    xliq_C7_con = 0.7 - xliqVAP01[-1, -1]

    return [solub_path_con, 0.0]


def run_flowsheet(path=None, inputs=None, layout=None, graph=None):

    # Create flowsheet
    flowsheet, runargs = make_flowsheet(path, inputs, layout, graph)
    # Try to run flowsheet
    try:
        flowsheet.SolveFlowsheet(runargs, verbose=False)
        success = True
    except:
        success = False

    return flowsheet, success


def get_mass_and_size(flowsheet, layout=None, inputs=None):
    """
    Function to get objective function value for the flowsheets.
    The objective function is of the form A*obj1 + B*obj2 where
    the objectives are mass_production_rate and crystal_size.

    :param flowsheet: SimulationExecutive object, the simulated
    version of the flowsheet being optimized.
    :param layout: :param layout: tuple, process description of
    major unit operations
    :param inputs: dictionary, values for the operational decision
    variables used for optimization and simulation that correspond
    to those described in the bounds.json file. keys are variable
    names

    :return: objective value, float, The value of A*obj1 + B*obj2
    """
    mass_out = flowsheet.F01.result.mass_cake_dry[-1]

    cycle_time = 10 * 3600.0

    if 'batch' in layout[-1]:
        if 'batch' in layout[0]:
            if 'Semibatch' == layout[0]:
                cycle_time = max(inputs['time_R01'], inputs['time_VAP01'],
                                 inputs['time_CR01'])
            elif 'batch' in layout[1]:
                cycle_time = max(inputs['time_R01'], inputs['time_R02'],
                                 inputs['time_VAP01'], inputs['time_CR01'])

    if '2' in layout[-1]:
        moments = flowsheet.CR02.Solid_1.getMoments()
    elif '3' in layout[-1]:
        moments = flowsheet.CR03.Solid_1.getMoments()
    else:
        moments = flowsheet.CR01.Solid_1.getMoments()

    size = moments[1] / (moments[0] + 1e-6) * 1e6

    mass_production = mass_out / (cycle_time + 1e-6)

    return [mass_production, size]



if __name__ == '__main__':
    with open('optimal_points_2.json') as f:
        all_optimals = json.load(f)

    mass_size = {}
    fs_counter = 0
    for i in valid_combos:
        var_count = 0
        bound_dict = get_input_dictionary(all_vars, i)
        input_dict = deepcopy(bound_dict)
        print(len(bound_dict.keys())) # decision variables? 
        print(len(all_optimals[str(fs_counter)])) # matching optimal data?
        for j in input_dict.keys():
            input_dict[j] = translate_scale(float(all_optimals[str(fs_counter)][var_count]), bound_dict[j])
            var_count += 1
        graph = make_graph(i)
        test, runargs_out = make_flowsheet(path=path, operating_vals=input_dict, layout=i, graph=graph)
        test.SolveFlowsheet(runargs_out, verbose=False)
        # try-except statement to catch any errors that may occur during the simulation and skip iterations 

        mass_size[fs_counter] = get_mass_and_size(test, layout=i, inputs=input_dict)
        fs_counter += 1

    with open("optimal_mass_size_2_fixed.json", "w") as outfile:
        json.dump(mass_size, outfile)
