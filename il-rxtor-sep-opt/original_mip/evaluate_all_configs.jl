"""
Evaluate all discrete unit-selection and ionic-liquid configurations for the
Ionic Liquid Selection and Reactor-Separator Network Design (ILRS) MIP/MINLP.

Usage (from il-rxtor-sep-opt/):
    julia --project=. original_mip/evaluate_all_configs.jl [--help] [--data-dir DIR] [--output FILE] [--disc|--no-disc]
Usage (from il-rxtor-sep-opt/original_mip/):
    julia --project=.. evaluate_all_configs.jl [--help] [--data-dir DIR] [--output FILE] [--disc|--no-disc]
"""

using CSV
using DataFrames
using JuMP
using Gurobi
using JSON
using Dates
using Printf
using Statistics
using SHA
using SparseArrays

include(joinpath(@__DIR__, "..", "ilrs_utils.jl"))

function parse_args(args::Vector{String})
    opts = Dict{String, Any}(
        "help" => false,
        "data_dir" => normpath(joinpath(@__DIR__, "..", "data")),
        "output" => nothing,
        "disc" => true,
        "quiet" => true,
    )
    i = 1
    while i <= length(args)
        arg = args[i]
        if arg in ("-h", "--help")
            opts["help"] = true
            i += 1
        elseif arg == "--data-dir"
            i < length(args) || error("--data-dir requires a path argument")
            opts["data_dir"] = args[i + 1]
            i += 2
        elseif startswith(arg, "--data-dir=")
            opts["data_dir"] = split(arg, "="; limit=2)[2]
            i += 1
        elseif arg in ("-o", "--output")
            i < length(args) || error("$arg requires a file path argument")
            opts["output"] = args[i + 1]
            i += 2
        elseif startswith(arg, "--output=")
            opts["output"] = split(arg, "="; limit=2)[2]
            i += 1
        elseif arg == "--disc"
            opts["disc"] = true
            i += 1
        elseif arg == "--no-disc"
            opts["disc"] = false
            i += 1
        elseif arg in ("-q", "--quiet")
            opts["quiet"] = true
            i += 1
        elseif arg in ("-v", "--verbose")
            opts["quiet"] = false
            i += 1
        else
            error("Unknown argument: $arg (pass --help for usage)")
        end
    end
    return opts
end

function print_usage(io::IO = stdout)
    println(
        io,
        """
Usage:
  julia --project=. original_mip/evaluate_all_configs.jl [options]   # from il-rxtor-sep-opt/
  julia --project=.. evaluate_all_configs.jl [options]               # from il-rxtor-sep-opt/original_mip/

Options:
  -h, --help            Show this help message and exit
      --data-dir DIR    Directory containing parameter_{alpha,beta,cost}.csv
  -o, --output FILE     Output JSON file path for configuration evaluation results
      --disc            Use discretized reactor inflow power law (default)
      --no-disc         Use continuous nonlinear reactor inflow power law
  -q, --quiet           Suppress solver console output (default)
  -v, --verbose         Enable solver console output
""",
    )
end

function compute_input_sha256(data_dir::AbstractString)
    hashes = Dict{String, String}()
    for fname in ("parameter_alpha.csv", "parameter_beta.csv", "parameter_cost.csv")
        fpath = joinpath(data_dir, fname)
        hashes[fname] = bytes2hex(SHA.sha256(read(fpath)))
    end
    return hashes
end

function evaluate_all_configurations(;
    data_dir::AbstractString = normpath(joinpath(@__DIR__, "..", "data")),
    disc::Bool = true,
    quiet::Bool = true,
    output_path::Union{Nothing, AbstractString} = nothing,
)
    global data_filepath = String(data_dir)
    data_alpha, data_beta, _ = import_data(data_filepath)
    num_reactors = maximum(data_alpha.reactor)
    num_separators = maximum(data_beta[!, "separator-k"])
    num_cation = maximum(data_beta[!, "cation-c"])
    num_anion = maximum(data_beta[!, "anion-a"])
    unit_keys = vcat(["r$i" for i in 1:num_reactors], ["s$j" for j in 1:num_separators])
    n_units = length(unit_keys)

    solutions = Vector{Dict{String, Any}}()
    solve_times = Float64[]

    for mask in 0:((1 << n_units) - 1)
        y_vals = Dict(unit_keys[idx] => ((mask >> (idx - 1)) & 1) for idx in 1:n_units)
        for c_sel in 1:num_cation, a_sel in 1:num_anion
            m = build_base_model_mip(; disc=disc)
            set_optimizer(m, Gurobi.Optimizer)
            quiet && set_silent(m)

            for k in unit_keys
                fix(m[:y][k], Float64(y_vals[k]); force=true)
            end
            for c in 1:num_cation
                fix(m[:z_cat][c], c == c_sel ? 1.0 : 0.0; force=true)
            end
            for a in 1:num_anion
                fix(m[:z_an][a], a == a_sel ? 1.0 : 0.0; force=true)
            end

            optimize!(m)
            t_solve = solve_time(m)
            push!(solve_times, t_solve)
            status = termination_status(m)
            feasible = status in (MOI.OPTIMAL, MOI.LOCALLY_SOLVED)
            obj_val = feasible ? objective_value(m) : nothing

            push!(
                solutions,
                Dict(
                    "y" => y_vals,
                    "cation" => c_sel,
                    "anion" => a_sel,
                    "status" => string(status),
                    "feasible" => feasible,
                    "objective_value" => obj_val,
                    "solve_time" => t_solve,
                ),
            )
        end
    end

    feasible_objs = [s["objective_value"] for s in solutions if s["feasible"] && s["objective_value"] !== nothing]
    run_info = Dict(
        "timestamp" => Dates.format(now(), "yyyy-mm-ddTHH:MM:SS"),
        "julia_version" => string(VERSION),
        "gurobi_version" => string(Gurobi.GRB_VERSION_MAJOR, ".", Gurobi.GRB_VERSION_MINOR, ".", Gurobi.GRB_VERSION_TECHNICAL),
        "gurobi_jl_version" => string(pkgversion(Gurobi)),
        "jump_version" => string(pkgversion(JuMP)),
        "solver_params" => Dict("disc" => disc, "quiet" => quiet),
        "input_path" => abspath(data_dir) == data_dir ? relpath(data_dir, normpath(joinpath(@__DIR__, ".."))) : data_dir,
        "input_sha256" => compute_input_sha256(data_dir),
        "num_configurations" => length(solutions),
        "num_feasible" => length(feasible_objs),
        "mean_solve_time" => isempty(solve_times) ? 0.0 : mean(solve_times),
        "best_objective" => isempty(feasible_objs) ? nothing : minimum(feasible_objs),
    )

    payload = Dict("run_info" => run_info, "solutions" => solutions)
    if output_path !== nothing
        mkpath(dirname(output_path))
        open(output_path, "w") do io
            JSON.print(io, payload, 2)
        end
        @printf("Saved %d configuration evaluations to %s\n", length(solutions), output_path)
    end
    return payload
end

function main(args::Vector{String} = ARGS)
    opts = parse_args(args)
    if opts["help"]
        print_usage()
        return 0
    end
    evaluate_all_configurations(;
        data_dir = opts["data_dir"],
        disc = opts["disc"],
        quiet = opts["quiet"],
        output_path = opts["output"],
    )
    return 0
end

if abspath(PROGRAM_FILE) == @__FILE__
    exit(main(ARGS))
end
