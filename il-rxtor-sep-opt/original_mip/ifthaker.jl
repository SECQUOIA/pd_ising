@doc raw"""
"""
struct Ifthaker{T} <: ToQUBO.Encoding.IntervalVariableEncodingMethod end

Ifthaker() = Ifthaker{Float64}()

# @doc raw"""
#     encode(var::Function, ::Ifthaker{T}, S::Tuple{T,T}) where {T}
# """
# function encode(var::Function, e::Ifthaker{T}, S::Tuple{T,T}; tol::Union{T,Nothing} = nothing) where {T}
#     !isnothing(tol) && return encode(var, e, S, nothing; tol)

#     a, b = integer_interval(S)

#     if a == b
#         return (ToQUBO.VI[], PBO.PBF{ToQUBO.VI,T}(a), nothing)
#     end

#     M = trunc(Int, b - a)
#     N = ceil(Int, (sqrt(1 + 8M) - 1) / 2)

#     y = var(N)::Vector{ToQUBO.VI}
#     ξ = PBO.PBF{ToQUBO.VI,T}(
#         [
#             a
#             [y[i] => i for i = 1:N-1]
#             y[N] => M - N * (N - 1) / 2
#         ],
#     )

#     return (y, ξ, nothing) # No penalty function
# end

# function encoding_bits(::Ifthaker{T}, S::Tuple{T,T}, tol::T) where {T}
#     @assert tol > zero(T)

#     a, b = S

#     return ceil(Int, (1 + sqrt(3 + abs(b - a) / 2tol)) / 2)
# end

# Real (fixed)
function ToQUBO.Encoding.encode(
    var::Function,
    e::Ifthaker{T},
    S::Tuple{T,T},
    n::Union{Integer,Nothing};
    tol::Union{T,Nothing} = nothing,
) where {T}
    @assert !(isnothing(tol) && isnothing(n))

    # if isnothing(n)
    #     n = encoding_bits(e, S, tol)
    # end

    @assert n >= 0
    @assert n % 4 == 1

    J = n ÷ 4

    a, b = S

    if J == 0
        z = var()::ToQUBO.VI
        ξ = ToQUBO.PBO.PBF{ToQUBO.VI,T}([a; z => b - a])
        y = ToQUBO.VI[z]
    else
        w = var()::ToQUBO.VI
        z = [var(4)::Vector{ToQUBO.VI} for _ = 1:J]
        ξ = ToQUBO.PBO.PBF{ToQUBO.VI,T}([
            a;
            w => T(10) ^ (-J) * (b - a);
        ])

        for j = 1:J
            ξ += T(10) ^ (-j) * (b - a) * ToQUBO.PBO.PBF{ToQUBO.VI,T}([
                z[j][1] => 1,
                z[j][2] => 2,
                z[j][3] => 3,
                z[j][4] => 3,
            ])
        end

        y = ToQUBO.VI[w]

        append!(y, z...)
    end

    return (y, ξ, nothing) # No penalty function
end