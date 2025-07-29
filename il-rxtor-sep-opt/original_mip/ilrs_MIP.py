"""
This script is a Python implementation of the Ionic Liquid Selection Program, Julia implementation can be found in ilrs_MIP_julia.ipynb. It uses the Pyomo package for optimization and the Gurobi solver to find the optimal solution. The script defines a mixed-integer programming (MIP) model to select ionic liquids based on various criteria, including cost, toxicity, and performance. The model is then solved using Gurobi, and the results are displayed. In this implementation, the nonlinear term in the objective function is linearized through discretization of the flow variable.

The problem is adapted from the following source:

    Iftakher, A., & Hasan, M. M. F. (2024). Exploring quantum optimization for computer-aided Molecular and Process Design. Systems and Control Transactions, 3, 292–299. https://psecommunity.org/LAPSE:2024.1540

"""

# Import libraries
import pyomo.environ as pyo
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

data_filepath = os.path.join(os.path.dirname(__file__), "..", "data")

# Import alpha and beta values (alpha: reactor conversion factor; beta: separator separation factor)
data_alpha = pd.read_csv(os.path.join(data_filepath, 'parameter_alpha.csv'))
data_beta = pd.read_csv(os.path.join(data_filepath, 'parameter_beta.csv'))
data_cost = pd.read_csv(os.path.join(data_filepath, 'parameter_cost.csv'))
data_cost = data_cost.set_index('unit')

num_reactors = data_alpha['reactor'].max()
num_separators = data_beta['separator-k'].max()
num_units = num_reactors + num_separators
num_cation = data_beta['cation-c'].max()
num_anion = data_beta['anion-a'].max()

# Define the Pyomo model
model = pyo.ConcreteModel(doc='Ionic Liquid Selection and Reactor-Separator Network Optimization')

# Define sets
model.r = pyo.Set(initialize=range(num_reactors), doc='Reactor set')
model.s = pyo.Set(initialize=range(num_separators), doc='Separator set')
model.cat = pyo.Set(initialize=range(num_cation), doc='Cation set')
model.an = pyo.Set(initialize=range(num_anion), doc='Anion set')

# Create labels for reactors and separators
reactors = [f'r{r}' for r in model.r]
separators = [f's{s}' for s in model.s]
unit_key = reactors + separators

model.unit = pyo.Set(initialize=unit_key, doc='Unit set')

# Define beta map keys: separator, cation, anion 
beta_key = []

for s in model.s: 
    for c in model.cat:
        for a in model.an:
            beta_key.append((s, c, a))

# Define beta map
beta_map = {
    beta_key[i]: data_beta['beta'][i] for i in range(len(beta_key))
}

# Define parameters 
model.alpha = pyo.Param(model.r, initialize=data_alpha['alpha'], doc='Reactor conversion factor', mutable=True)
model.beta = pyo.Param(model.s, model.cat, model.an, initialize=beta_map, doc='Separator separation factor', mutable=True)
model.demand = pyo.Param(initialize=2, doc='Product demand')

model.cost_fixed = pyo.Param(model.unit, initialize=data_cost['fixed'], doc='Fixed cost of each unit')
model.cost_oper = pyo.Param(model.unit, initialize=data_cost['operating'], doc='Operating cost of each unit')
model.cost_emiss = pyo.Param(model.unit, initialize=data_cost['emission'], doc='Emission cost of each unit')

# Define decision variables
model.y = pyo.Var(model.unit, domain=pyo.Binary, doc='unit activation')
model.z_cat = pyo.Var(model.cat, domain=pyo.Binary, doc='IL-cation selection')
model.z_an = pyo.Var(model.an, domain=pyo.Binary, doc='IL-anion selection')

# Define valid flow pairs: source-to-reactor, reactor-to-separator, separator-to-demand
flow_pairs = []

# Add source-to-reactor flows
for r in reactors:
    flow_pairs.append(('srce', r))  # 'srce' is the source node
    
# Add reactor-to-separator flows
for r in reactors:
    for s in separators:
        flow_pairs.append((r, s))

# Add separator-to-sink flows
for s in separators:
    flow_pairs.append((s, 'sink'))  # 'd' is the demand node

model.x = pyo.Var(flow_pairs, domain=pyo.NonNegativeReals, doc='flow', bounds=(0,2)) 

# Define flow bounds
f_lb = 0
f_ub = 2

# Nonlinear term in obj func (x**0.6) for inflow x into reactors 
# Linearize nonlinear term in objective function (**0.6) through discretization of x between f_lb and f_ub 
disc_num = 21
disc_flow = np.round(np.linspace(f_lb, f_ub, num=disc_num), decimals=4)
model.n = pyo.RangeSet(disc_num, doc='discretization set')

# Discretization mapping for inflow into reactors 
dx_init = {(r, n): disc_flow[n-1] for r in model.r for n in model.n}
dx_power = {(r, n): disc_flow[n-1]**0.6 for r in model.r for n in model.n}
model.dx = pyo.Param(model.r, model.n, initialize=dx_init, doc='Discretized flow values for each reactor')
model.p = pyo.Param(model.r, model.n, initialize=dx_power, doc='Discretized flow raised to power 0.6')
model.k = pyo.Var(model.r, model.n, domain=pyo.Binary, doc='Binary selector for discretized flow') 

# Sum of k for each reactor must be 1
# only one value of discretized flow can be selected for each reactor, hence for p value as well
def k_sum_rule(model, r):
    return sum(model.k[r, n] for n in model.n) == 1
model.k_sum = pyo.Constraint(model.r, rule=k_sum_rule)

# Sum of dx for each reactor must be equal to inflow from source
# keeps the inflow into reactor x equal to one value of discretized flow 
def xr_sum_rule(model, r):
    return sum(model.k[r, n]*model.dx[r, n] for n in model.n) == model.x[('srce', f'r{r}')]
model.xr_sum = pyo.Constraint(model.r, rule=xr_sum_rule)

# Upper bound flow parameter--these values are set arbitrarily, the actual values used in the paper are unknown/unavailable
f_ub_unit = {'r0': 2, 'r1': 2, 's0': 2, 's1': 2, 's2': 2}
model.x_ub = pyo.Param(model.unit, initialize=f_ub_unit, doc='Upper bound flow for each unit')


### Other Constraints 
# Define flow bounds for flows x (UB only as lb is 0-enforced by Var definition)
def flow_bounds_unit(model, k):
    # Calculate inflow to unit k
    inflow = sum(model.x[(i, j)] for (i, j) in model.x if j == k)
    return inflow <= model.x_ub[k] * model.y[k]
model.flow_bounds = pyo.Constraint(model.unit, rule=flow_bounds_unit)

# Flow conservation for reactors
def flow_conservation_reactors(model, r):
    inflow = model.x[('srce', f'r{r}')]
    outflow = sum(model.x[(f'r{r}', f's{s}')] for s in model.s)
    return inflow * model.alpha[r] == outflow
model.flow_conservation_reactors = pyo.Constraint(model.r, rule=flow_conservation_reactors)

# Flow conservation for separators
M = 1e3
def flow_conservation_separators(model, s, c, a):
    inflow = sum(model.x[(f'r{r}', f's{s}')] for r in model.r)
    outflow = model.x[(f's{s}', 'sink')]
    return outflow >= model.beta[s, c, a] * inflow - M * (2 - model.z_cat[c] - model.z_an[a])

def flow_conservation_separators_upper(model, s, c, a):
    inflow = sum(model.x[(f'r{r}', f's{s}')] for r in model.r)
    outflow = model.x[(f's{s}', 'sink')]
    return outflow <= model.beta[s, c, a] * inflow + M * (2 - model.z_cat[c] - model.z_an[a])

model.flow_conservation_separators_lb = pyo.Constraint(model.s, model.cat, model.an, rule=flow_conservation_separators)
model.flow_conservation_separators_ub = pyo.Constraint(model.s, model.cat, model.an, rule=flow_conservation_separators_upper)

# One selection constraint for each ion 
def one_selection_cation(model):
    return sum(model.z_cat[c] for c in model.cat) == 1
model.one_selection_cation = pyo.Constraint(rule=one_selection_cation)

def one_selection_anion(model):
    return sum(model.z_an[a] for a in model.an) == 1
model.one_selection_anion = pyo.Constraint(rule=one_selection_anion)

# Demand constraint at the sink
def sink_demand_rule(model):
    return sum(model.x[(i, 'sink')] for (i, j) in model.x if j == 'sink') >= model.demand
model.sink_demand = pyo.Constraint(rule=sink_demand_rule)

# Objective function
def objective_rule(model):
    fixed_cost = sum(model.cost_fixed[k] * model.y[k] for k in model.unit)
    # oper_cost_r = sum(
    #     model.cost_oper[f'r{r}'] * model.x[('srce', f'r{r}')]**0.6 for r in model.r
    # )
    oper_cost_r = sum(
        model.cost_oper[f'r{r}'] * model.p[r, n] * model.k[r, n] for r in model.r for n in model.n)
    oper_cost_s = sum(
        model.cost_oper[f's{s}']  * sum(model.x[(f'r{r}', f's{s}')] for r in model.r)**2
        for s in model.s
    )
    emiss_cost = sum(
        model.cost_emiss[f's{s}'] * (
            sum(model.x[(f'r{r}', f's{s}')] for r in model.r) - model.x[(f's{s}', 'sink')]
        ) for s in model.s
    )
    return fixed_cost + oper_cost_r + oper_cost_s + emiss_cost

model.objective = pyo.Objective(rule=objective_rule, sense=pyo.minimize, doc='Total cost')


# Solve the model
solver = pyo.SolverFactory("gurobi")
# solver.options['NonConvex'] = 2
result = solver.solve(model, tee=True)
model.pprint()

# Print results
print('Objective value:', model.objective())
print('Unit activation:')
for k in model.unit:
    print(f'Unit {k}:', model.y[k]())
print('IL-cation selection:')
for c in model.cat:
    print(f'IL-cation {c}:', model.z_cat[c]())
print('IL-anion selection:')
for a in model.an:
    print(f'IL-anion {a}:', model.z_an[a]())

# # Check the results by manually calculating the objective function
# fixed_cost = sum(model.cost_fixed[k] * model.y[k]() for k in model.unit)
# oper_cost_exact_r = sum(model.y[f'r{r}'].value*model.cost_oper[f'r{r}'] * model.x[('srce', f'r{r}')].value**0.6 for r in model.r)
# oper_cost_exact_s = sum(model.y[f's{s}'].value*model.cost_oper[f's{s}'] * sum(model.x[(f'r{r}', f's{s}')].value for r in model.r)for s in model.s)
# emiss_cost_exact = sum(model.y[f's{s}'].value*model.cost_emiss[f's{s}'] * (sum(model.x[(f'r{r}', f's{s}')].value for r in model.r) - model.x[(f's{s}', 'sink')].value)for s in model.s)

# total_cost_exact = fixed_cost + oper_cost_exact_r + oper_cost_exact_s + emiss_cost_exact
# print('Manual calculation of objective value:', total_cost_exact)
# print('Solver calculation of objective value:', model.objective()) 