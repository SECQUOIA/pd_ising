# Using JuMP and QUBO to convert mps file into QUBO format and solve it using SA and QA solvers
using JuMP
using QUBO
using Dates
using DelimitedFiles

const export_dir = joinpath(@__DIR__, "..", "julia_exports")

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

    open(joinpath(export_dir, "$(filename_prefix)_scalar_$(today()).csv"), "w") do io
        writedlm(io, ["n, a, b"])  # Write header row
        writedlm(io, [n a b], ',')  # Write the scalar values in one line
    end

    writedlm(joinpath(export_dir, "$(filename_prefix)_L_$(today()).csv"), L, ',')
    writedlm(joinpath(export_dir,"$(filename_prefix)_Q_$(today()).csv"), Q, ',')

    if attribute_returns
        return n, L, Q, a, b, ρ
    end
end

# Load the MPS file
m = JuMP.read_from_file(
    joinpath(@__DIR__, "flowsheet_opti_simple.mps")
)


# ============== QUBO conversion ==============
m_qubo = convert_to_qubo(identity, m)
println(m_qubo)
solution_summary(m)

# === Export QUBO matrices ===
export_qubo_matrices(m, m_qubo;)
