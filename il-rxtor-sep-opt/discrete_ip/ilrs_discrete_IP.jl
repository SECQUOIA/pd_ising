"""
This script is a reformulation of the discrete part of the Ionic Liquid Selection Program, adopted from ilrs_MIP.ipynb (also see ilrs_MIP_julia.ipynb). 

The problem involves selecting ionic liquids for a reactor-separator network design, where the goal is to minimize the total cost while satisfying various flow constraints. It is formulated as an integer programming to select ionic liquids and reactor-separator network based on various logical constraints, formulated as linear and/or quadratic constraints. 

The problem is adapted from the following source:
    Iftakher A, Hasan MMF. Exploring Quantum Optimization for Computer-aided Molecular and Process Design. Systems and Control Transactions 3:292-299 (2024) https://doi.org/10.69997/sct.143809 
    """

using JuMP
using SparseArrays
using JSON
using Dates
using Gurobi

include("../ilrs_utils.jl");

const data_filepath = joinpath(@__DIR__, "..", "data")
const export_dir = joinpath(@__DIR__, "result_gurobi")

@doc"""
    build_discrete_ip_model(data_filepath::String; use_quad_constraints::Bool = true)

    Builds the IP model for the discrete part of the Ionic Liquid Selection Program.

    # Arguments
    - `data_filepath::String`: Path to the data file.
    - `use_quad_constraints::Bool`: Whether to use quadratic constraints. If false, the model uses linear constraints.

    # Returns
    - `m`: The JuMP model.
    - `vars`: A dictionary of variable references.
"""
function build_discrete_ip_model(
    data_filepath::String;
    use_quad_constraints::Bool = true,
    )

    # === Import data ===
    data_alpha, data_beta, data_cost = import_data(data_filepath)
    num_reactors = maximum(data_alpha.reactor)
    num_separators = maximum(data_beta[!, "separator-k"])
    num_cation = maximum(data_beta[!, "cation-c"])
    num_anion = maximum(data_beta[!, "anion-a"])

    reactors = 1:num_reactors
    separators = 1:num_separators
    unit_keys = vcat(["r$i" for i in reactors], ["s$j" for j in separators])
    source = "srce"
    sink = "sink"

    m = Model()

    @variable(m, y[k in unit_keys], Bin)
    @variable(m, z_cat[c in 1:num_cation], Bin)
    @variable(m, z_an[a in 1:num_anion], Bin)

    flow_pairs = []
    for r in reactors
        push!(flow_pairs, (source, "r$r"))
        for s in separators
            push!(flow_pairs, ("r$r", "s$s"))
        end
    end
    for s in separators
        push!(flow_pairs, ("s$s", sink))
    end

    @variable(m, f[i_j in flow_pairs], Bin)

    # === Parameters ===
    α = Dict(data_alpha.reactor[i] => data_alpha.alpha[i] for i in 1:nrow(data_alpha))
    β = Dict((data_beta[i, "separator-k"], data_beta[i, "cation-c"], data_beta[i, "anion-a"]) => data_beta[i, "beta"] for i in 1:nrow(data_beta))

    cost_fixed = Dict(data_cost.unit[i] => data_cost.fixed[i] for i in 1:nrow(data_cost))
    cost_oper = Dict(data_cost.unit[i] => data_cost.operating[i] for i in 1:nrow(data_cost))
    cost_emiss = Dict(data_cost.unit[i] => data_cost.emission[i] for i in 1:nrow(data_cost))

    # connecting units to binary flow variables
    @constraint(m, [r in reactors],
        f[(source, "r$r")] == y["r$r"] 
    )
    @constraint(m, [s in separators],
        f[("s$s", sink)] == y["s$s"]
    )
    # At least one flow at sink
    @constraint(m, sum(f[("s$s", sink)] for s in separators) >= 1)
    
    # If reactor is selected, at least one flow out from the reactor 
    @constraint(m, [r in reactors],
            (1 - f[(source, "r$r")]) + sum(f[("r$r", "s$s")] for s in separators) >= 1
        )
        
    # If there is flow out of separator, there is at least one inflow into separator 
    @constraint(m, [s in separators],
            (1 - f[("s$s", sink)]) + sum(f[("r$r", "s$s")] for r in reactors) >= 1
        )

    # === One IL selection constraint ===
    @constraint(m, sum(z_cat[c] for c in 1:num_cation) == 1)
    @constraint(m, sum(z_an[a] for a in 1:num_anion) == 1)

    # Define new variables, w, to represent the product of z_cat and z_an
    @variable(m, w[1:num_cation, 1:num_anion], Bin)
    @constraint(m,[i in 1:num_cation, j in 1:num_anion], w[i, j] == z_cat[i] * z_an[j])

    @objective(m, Min, 
        sum(cost_fixed[k] * y[k] for k in unit_keys) 
        + 2 * sum(cost_oper["r$r"] * y["r$r"] * α[r]  for r in reactors) 
        + 2 * sum(cost_oper["s$s"] * y["s$s"] * β[s, c, a] * w[c,a] for s in separators, c in 1:num_cation, a in 1:num_anion)
        )

    if !use_quad_constraints
        # === Logic Constraints === 
        # At least one flow from source to reactor
        @constraint(m, sum(f[(source, "r$r")] for r in reactors) - f[(source, "r1")]*f[(source, "r2")] == 1)

        # If there is a flow from reactor to separator, there is inflow into reactor
        @constraint(m, [r in reactors, s in separators],
            f[("r$r", "s$s")] * f[(source, "r$r")] == f[("r$r", "s$s")]
        )

        # If separator is selected (there is inflow), at least one flow out from the separator
        @constraint(m, [r in reactors, s in separators],
            f[("r$r", "s$s")] * f[("s$s", sink)] == f[("r$r", "s$s")]
        )

    else            
        # === Logic Constraints === 
        # At least one flow from source to reactor
        @constraint(m, sum(f[(source, "r$r")] for r in reactors) >= 1)  

        # If there is a flow from reactor to separator, there is inflow into reactor
        for s in separators, r in reactors
            @constraint(m,
                (1 - f[("r$r", "s$s")]) + f[(source, "r$r")] >= 1
            )
        end

        # If separator is selected (there is inflow), at least one flow out from the separator
        for s in separators, r in reactors
            @constraint(m,
                (1 - f[("r$r", "s$s")]) + f[("s$s", sink)] >= 1
            )
        end
    end

    # Return model and variable references
    return m, Dict(:y => y, :z_cat => z_cat, :z_an => z_an, :f => f, :w => w)
end

@doc"""
    add_integer_cuts!(m::Model, vars::Dict, n_iter::Int; save_solns::Bool = false)

    Adds integer cuts to the model iteratively. The cuts are added based on the solution of the previous iteration. 
    If save_solns is true, the solution dictionary of all iterations (n_iter) is saved to a CSV file.

    # Arguments
    - `m::Model`: The JuMP model.
    - `vars::Dict`: A dictionary of variable references.
    - `n_iter::Int`: The number of iterations.
    - `save_solns::Bool`: Whether to save the solution dictionary.
"""
function add_integer_cuts!(
    m::Model, 
    vars::Dict, 
    n_iter::Int; 
    save_solns::Bool = false
    )

    y = vars[:y]
    z_cat = vars[:z_cat]
    z_an = vars[:z_an]
    f = vars[:f]
    w = vars[:w]

    # ===== Add integer cuts iteratively =====
    iter = 0
    time_total = 0

    dict_solns = Dict{Tuple{Int, Symbol, Any}, Float64}()

    for iter in 1:n_iter
        println("Iteration #$iter")
        optimize!(m)

        solve_time_iter = solve_time(m)
        time_total += solve_time_iter

        println("Solve time: ", solve_time(m), " seconds")
        println("Objective value: ", objective_value(m))

        dict_solns[(iter, :solve_time, "")] = solve_time_iter
        dict_solns[(iter, :objective_value, "")] = objective_value(m)

        cut_expr = 0.0

        for (var_name, var_set) in zip([:y, :z_cat, :z_an], [y, z_cat, z_an])
            index_set = hasproperty(var_set, :axes) ? var_set.axes[1] : keys(var_set)

            for idx in index_set
                val = value(var_set[idx])
                dict_solns[(iter, var_name, idx)] = val  

                if val < 0.5
                    cut_expr += var_set[idx]
                else
                    cut_expr += 1 - var_set[idx]
                end
            end
        end

        @constraint(m, cut_expr >= 1)
        println("Integer Cut #$iter added")
    end

    if save_solns
        save_solndict_csv(dict_solns; filename=joinpath(export_dir, "optimization_results_$(today()).csv"))
    end

end

m, vars = build_discrete_ip_model(data_filepath, use_quad_constraints = true)
set_optimizer(m, Gurobi.Optimizer)
optimize!(m)
add_integer_cuts!(m, vars, 84, save_solns = true)


# ============== QUBO conversion ==============
m_qubo = convert_to_qubo(identity, m)
println(m_qubo)
solution_summary(m)

# === Export QUBO matrices ===
export_qubo_matrices(m, m_qubo;)
