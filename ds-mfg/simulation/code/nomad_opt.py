import PyNomad
import numpy as np
import sys
import json
from generating_structures import (make_flowsheet, get_input_dictionary, get_constraints_values,
                                   get_objective_value, get_objective_value_cost, run_flowsheet, make_graph)
from helper import translate_scale
from copy import deepcopy


with open('active_fs.txt') as f:
    choices = [i for i in f]
    layout = tuple(choices[0].split())

with open('../data/bounds.json') as f:
    all_vars = json.load(f)

graph = make_graph(layout)
bound_dict = get_input_dictionary(all_vars, layout)
input_dict = deepcopy(bound_dict)

path = '../data/compounds_lomustine.json'


# This example of blackbox function is for a single process
# The blackbox output must be put in the EvalPoint passed as argument
def bb(x):
    try:
        # Recasting needed constraint values to their non-normalized values
        dim = x.size()

        count = 0
        for j in input_dict.keys():
            input_dict[j] = translate_scale(x.get_coord(count), bound_dict[j])
            count += 1

        # Calling PharmaPy
        flowsheet, success = run_flowsheet(path=path, inputs=input_dict, layout=layout, graph=graph)

        if success:
            # Objective function is to maximize mass_production_rate and crystal_size.
            obj = -get_objective_value(flowsheet=flowsheet, layout=layout, inputs=input_dict)
       
            # Objective function is to minimize the captial cost
            # obj = get_objective_value_cost(flowsheet=flowsheet, layout=layout, inputs=input_dict)
            [g1, g2] = get_constraints_values(flowsheet=flowsheet, layout=layout, inputs=input_dict)
        else:
            obj = 1e20
            g1 = 1e20
            g2 = 1e20
        rawBBO = str(obj) + " " + str(g1) + " " + str(g2)
        x.setBBO(rawBBO.encode("UTF-8"))
    except:
        print("Unexpected eval error", sys.exc_info()[0])
        return 0
    return 1  # 1: success 0: failed evaluation


X0 = [0.9, 0.5, 0.5, 0.85] + [0.25] * (len(input_dict.keys()) - 4)
params = ["DIMENSION " + str(len(input_dict.keys())), "BB_OUTPUT_TYPE OBJ PB PB", "MAX_BB_EVAL 5000",
          "MIN_MESH_SIZE ( " + "1E-5 " * len(input_dict.keys()) + ")",
          "DISPLAY_DEGREE 2", "DISPLAY_ALL_EVAL true",
          "DISPLAY_STATS BBE OBJ CONS_H TIME"]

x_return, f_return, h_return, nb_evals, nb_iters, stopflag, stop_reason = PyNomad.optimize(bb, X0, [0.0]*len(X0),
                                                                              [1.0]*len(X0), params)
print (
    "\n NOMAD outputs \n X_sol={} \n F_sol={} \n H_sol={} \n NB_evals={} \n NB_iters={} \n".format(x_return, f_return,
                                                                                                   h_return, nb_evals,
                                                                                                   nb_iters))
# tee-command will help write/save the results (linux tee command)
# python run_all_opts.py | tee log.txt 
# tee command will write the output of the command to the file log.txt
