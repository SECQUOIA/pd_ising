using CSV
using DataFrames
using JuMP
using QUBO
using QUBOTools
using Plots
import DelimitedFiles: writedlm 

@doc"""
    Relabel the unit variables.
    # Arguments
    - `u::String3`: The unit variable.

    # Returns
    - `String`: The relabeled unit variable.
"""
function relabel_unit(u)
    u_str = String(u)             # convert String3 to String
    prefix = first(u_str)
    index = parse(Int, last(u_str)) + 1
    return string(prefix, index)
end

@doc"""
    Import data from CSV files and return them as DataFrames.
    # Returns
    - `data_alpha::DataFrame`: The alpha data.
    - `data_beta::DataFrame`: The beta data.
    - `data_cost::DataFrame`: The cost data.
"""
function import_data(data_filepath::String)    
    data_alpha = CSV.read(joinpath(data_filepath, "parameter_alpha.csv"), DataFrame)
    data_beta = CSV.read(joinpath(data_filepath, "parameter_beta.csv"), DataFrame)
    data_cost = CSV.read(joinpath(data_filepath, "parameter_cost.csv"), DataFrame)
    data_cost.unit = relabel_unit.(data_cost.unit)
    data_cost = sort(data_cost, :unit)
    return data_alpha, data_beta, data_cost
end

@doc"""
    Save the solution dictionary to a CSV file.
    # Arguments
    - `dict_solns::Dict{Tuple{Int, Symbol, Any}, Float64}`: The solution dictionary.
    - `filename::String`: The name of the CSV file to save the results to.
"""
function save_solndict_csv(dict_solns::Dict{Tuple{Int, Symbol, Any}, Float64}; filename="optimization_results.csv")
    n_iter = maximum([iter for (iter, _, _) in keys(dict_solns)])
    unique_keys = Set{Tuple{Symbol, Any}}()
    for ((iter, varname, idx), val) in dict_solns
        push!(unique_keys, (varname, idx))
    end
    sorted_keys = sort(collect(unique_keys))
    colnames = ["iteration"]
    append!(colnames, [ "$(varname)$(idx)" for (varname, idx) in sorted_keys ])
    rows = []
    for iter in 1:n_iter
        row = Dict{String, Any}()
        row["iteration"] = iter
        for (varname, idx) in sorted_keys
            colname = "$(varname)$(idx)"
            val = get(dict_solns, (iter, varname, idx), missing)
            row[colname] = val
        end
        push!(rows, row)
    end
    results_df = DataFrame(rows)
    results_df = results_df[:, colnames]
    CSV.write(filename, results_df)
end

@doc"""
    Convert a JuMP model to a QUBO model.
    # Arguments
    - `config!::Function`: The configuration function.
    - `m::JuMP.Model`: The JuMP model.
    - `optimizer::Optimizer`: The optimizer to use.

    # Returns
    - `QUBOTools.Model`: The QUBO model.
"""
function convert_to_qubo(config!::Function, m::JuMP.Model; optimizer=ToQUBO.Optimizer(nothing))
    set_optimizer(m, () -> optimizer)
    config!(m)
    optimize!(m)
    return QUBOTools.Model(unsafe_backend(m).target_model)
end
convert_to_qubo(m::JuMP.Model) = convert_to_qubo(identity, m)

@doc"""
    Extract the attributes of a QUBO model.
    # Arguments
    - `model::JuMP.Model`: The JuMP model.
    - `qubo_model::QUBOTools.Model`: The QUBO model.

    # Returns
    - `n::Int`: The number of variables in the QUBO model.
    - `L::SparseMatrixCSC{Float64, Int64}`: The linear terms of the QUBO model.
"""
function qubo_attributes(model::JuMP.Model, qubo_model::QUBOTools.Model)
    c = JuMP.all_constraints(model; include_variable_in_set_constraints = false)
    n, L, Q, a, b = QUBOTools.form(qubo_model, :sparse; sense = :min, domain = :bool)
    ρ = get_attribute.(c, ToQUBO.Attributes.ConstraintEncodingPenalty())
    return n, L, Q, a, b, ρ
end

@doc"""
    Plot the density map of a QUBO model.
    # Arguments
    - `model::JuMP.Model`: The JuMP model.
    - `qubo_m::QUBOTools.Model`: The QUBO model.
    - `round_to::Int`: The number of decimal places to round the values to.
    - `width::Int`: The width of the plot.

    # Returns
    - `p_matrix::Plots.Plot`: The density map plot.
"""
function plot_density_map(model::JuMP.Model, qubo_m::QUBOTools.Model; round_to=nothing, width=450)
    n, L, Q, a, b, ρ = qubo_attributes(model, qubo_m)
    Q_dense = Array(Q) 
    symQ = transpose((Q_dense/2))+Q_dense/2
    linQ = spdiagm(0 => L)
    linQ = Array(linQ)
    mat_density = linQ + symQ 
    p_matrix = heatmap(reverse(mat_density, dims=1), 
        title = "Model Density",
        color = :starrynight, 
        dpi = 300, 
        xlabel = "Variable Index", 
        ylabel = "Variable Index",
        xticks = (1:n, string.(1:n)), 
        yticks = (1:n, string.(1:n)),
        size = (width, width)
    )
    for i in 1:n
        for j in 1:n
            val = mat_density[i, j]  
            if round_to !== nothing
                val = round(val, digits=round_to)
            end
            annotate!(j, n - i + 1, text(string(val), 8, :white, :center))
        end
    end
    display(p_matrix)
end

@doc"""
    Build the base MINLP model for the Ionic Liquid Selection and Reactor-Separator Network Design problem.
    # Arguments
    - `disc::Bool`: Whether to use discretization.

    # Returns
    - `m::JuMP.Model`: The JuMP model.
"""
function build_base_model_mip(;disc=false)
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

    # Flow bounds
    f_lb = 0.0
    f_ub = 2.0

    # === Build Model ===
    m = Model()

    # === Sets ===
    @variable(m, y[k in unit_keys], Bin)
    @variable(m, z_cat[c in 1:num_cation], Bin)
    @variable(m, z_an[a in 1:num_anion], Bin)

    # Flow variable for valid pairs
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

    @variable(m, x[i_j in flow_pairs] >= 0, upper_bound=f_ub)

    # === Parameters ===
    α = Dict(data_alpha.reactor[i] => data_alpha.alpha[i] for i in 1:nrow(data_alpha))
    β = Dict((data_beta[i, "separator-k"], data_beta[i, "cation-c"], data_beta[i, "anion-a"]) => data_beta[i, "beta"] for i in 1:nrow(data_beta))

    cost_fixed = Dict(data_cost.unit[i] => data_cost.fixed[i] for i in 1:nrow(data_cost))
    cost_oper = Dict(data_cost.unit[i] => data_cost.operating[i] for i in 1:nrow(data_cost))
    cost_emiss = Dict(data_cost.unit[i] => data_cost.emission[i] for i in 1:nrow(data_cost))
    demand = 2.0

    # === Flow bounds ===
    @constraint(m, [k in unit_keys],
        sum(x[(i, j)] for (i, j) in flow_pairs if j == k) <= f_ub * y[k]
    )

    # === Flow conservation (reactors) ===
    @constraint(m, [r in reactors],
        x[(source, "r$r")] * α[r] == sum(x[("r$r", "s$s")] for s in separators)
    )

    # === Flow conservation (separators) ===
    M = 1e3
    @constraint(m, [s in separators, c in 1:num_cation, a in 1:num_anion],
        x[("s$s", sink)] ≥ β[(s, c, a)] * sum(x[("r$r", "s$s")] for r in reactors) - M * (2 - z_cat[c] - z_an[a])
    )
    @constraint(m, [s in separators, c in 1:num_cation, a in 1:num_anion],
        x[("s$s", sink)] ≤ β[(s, c, a)] * sum(x[("r$r", "s$s")] for r in reactors) + M * (2 - z_cat[c] - z_an[a])
    )

    # === One IL selection constraint ===
    @constraint(m, sum(z_cat[c] for c in 1:num_cation) == 1)
    @constraint(m, sum(z_an[a] for a in 1:num_anion) == 1)

    # === Demand constraint ===
    @constraint(m,
        sum(x[(i, sink)] for (i, j) in flow_pairs if j == sink) ≥ demand
    )

    if disc
        # === Discretization for nonlinear term ===
        disc_num = 21
        disc_flow = round.(range(f_lb, stop=f_ub, length=disc_num), digits=4)
        nset = 1:disc_num

        # Binary selectors for discretized flow
        @variable(m, k[r in reactors, n in nset], Bin)

        # Define dx and p as Dicts (lookup tables)
        dx = Dict((r, n) => disc_flow[n] for r in reactors, n in nset)
        p  = Dict((r, n) => disc_flow[n]^0.6 for r in reactors, n in nset)

        # Ensure one discretization is selected per reactor
        @constraint(m, [r in reactors], sum(k[r, n] for n in nset) == 1)

        # Inflow constraint: selected flow value must match x
        @constraint(m, [r in reactors],
            sum(k[r, n] * dx[(r, n)] for n in nset) == x[(source, "r$r")]
        )
            
        # === Objective Function ===
        @objective(m, Min,
            sum(cost_fixed[k] * y[k] for k in unit_keys)
            + sum(cost_oper["r$r"] * p[r, n] * k[r, n] for r in reactors, n in nset)
            + sum(cost_oper["s$s"] * (sum(x[("r$r", "s$s")] for r in reactors))^2 for s in separators)
            + sum(cost_emiss["s$s"] * (
                sum(x[("r$r", "s$s")] for r in reactors) - x[("s$s", sink)]
            ) for s in separators)
        )
        
        println("Model (and objective function) is built with discretization of x.")
        
        return m

    else
        # === Objective Function ===
        @objective(m, Min,
        sum(cost_fixed[k] * y[k] for k in unit_keys)
        + sum(cost_oper["r$r"] * x[(source, "r$r")]^0.6 for r in reactors)
        + sum(cost_oper["s$s"] * (sum(x[("r$r", "s$s")] for r in reactors))^2 for s in separators)
        + sum(cost_emiss["s$s"] * (
            sum(x[("r$r", "s$s")] for r in reactors) - x[("s$s", sink)]
        ) for s in separators)
        )

        println("Model is built without discretization.")

        return m
    end
    
end

@doc"""
    Solve and display the results of a JuMP model.
    # Arguments
    - `model::JuMP.Model`: The JuMP model.
    - `optimizer::Optimizer`: The optimizer to use.

    # Returns
    - `objective_value::Float64`: The objective value of the model.
    - `variables::Dict{Symbol, Float64}`: The values of the variables.
"""
function solve_and_display(model::JuMP.Model; optimizer=Gurobi.Optimizer)
    set_optimizer(model, optimizer)
    optimize!(model)
    println("Objective value: ", objective_value(model))
    for var in all_variables(model)
        println("$(name(var)) = ", value(var))
    end
end

@doc"""
    Run the experiments on QCI dirac-3 using QCIOpt.jl. 
    Requires a specific version of QCIOpt.jl. 

    # Arguments
    - `m::JuMP.Model`: The JuMP model.
    - `m_qubo::QUBOTools.Model`: The QUBO model.
    - `info_path::AbstractString`: The path to the info file.
    - `max_qubo_levels::Integer`: The maximum number of levels for the QUBO model.
    - `verbose::Bool`: Whether to print verbose output.

    # Returns
    - `results::Dict{String, Any}`: The results of the experiments.
"""
function run_qubo_dirac3(m, m_qubo;
    n_sample::Int             = 10, # number of samples 
    info_path::AbstractString = info_path,
    max_qubo_levels::Integer  = 50, # qubo running on dirac-3
    verbose::Bool             = false,) 

    n, L, Q, a, b, ρ = qubo_attributes(m, m_qubo)

    if n >= max_qubo_levels # set to 50 (max 500 imposed by device)
        @info "QUBO Instance skipped for requiring $n / $max_qubo_levels levels."
    end

    model = Model(QCIOpt.Optimizer)
    @variable(model, x[i = 1:n], Bin)
    @objective(model, Min, a * (x' * Q * x + L' * x + b))

    verbose || set_silent(model)

    set_attribute(model, "num_samples", n_sample)

    try
        optimize!(model)
    catch e
        @error e
        return nothing
    end

    y = map(i -> objective_value(model; result = i), 1:result_count(model))
    t = solve_time(model)
    multiplicity = map(i -> get_attribute(model, QCIOpt.ResultMultiplicity(i)), 1:result_count(model))
    probability = multiplicity ./ sum(multiplicity)
    
    results = Dict(
        "solve_time" => t,
        "obj_values" => y,
        "multiplicity" => multiplicity,
        "probability" => probability
    )

    open(info_path, "w") do fp
        JSON.print(fp, results, 2)
    end

    return results
end

@doc"""
    Export the QUBO matrices to CSV files.
    # Arguments
    - `m_qubo::QUBOTools.Model`: The QUBO model.
    - `filename_prefix::String`: The prefix for the output filenames.
    
    # Returns
    - `Q, L, a, b`: The QUBO matrices.
"""
function export_qubo_matrices(
    m::JuMP.Model,
    m_qubo::QUBOTools.Model;
    filename_prefix="qubo_export",
    attribute_returns::Bool=false,
    )
    

    n, L, Q, a, b, ρ = qubo_attributes(m, m_qubo)

    open(joinpath(@__DIR__, "julia_exports", "$(filename_prefix)_scalar_$(today()).csv"), "w") do io
        writedlm(io, ["n, a, b"])  # Write header row
        writedlm(io, [n a b], ',')  # Write the scalar values in one line
    end

    writedlm(joinpath(@__DIR__, "julia_exports", "$(filename_prefix)_L_$(today()).csv"), L, ',')
    writedlm(joinpath(@__DIR__, "julia_exports","$(filename_prefix)_Q_$(today()).csv"), Q, ',')

    if attribute_returns
        return n, L, Q, a, b, ρ
    end
end
