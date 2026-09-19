# The EPED1-NN gold behind the kernel test `pedestal::tests::eped1nn_is_epednn_jl_on_three_machines`
# (FR-TR-009): EPEDNN.jl's own answer on three machines, printed to full precision.
#
#   julia --project=<env with EPEDNN.jl> tools/benchmark-epednn-gold.jl
#
# EPEDNN.jl: third_party/FUSE/EPEDNN.jl (the model file EPED1NNmodel.bson ships with it).
# Inputs per machine: (a, betan, bt, delta, ip, kappa, m, neped, r, zeffped).
# Output: 9 pressures [MPa] and 9 widths — (GH, G, H) × (H, meta, superH) — which the kernel
# test embeds verbatim and matches to < 4e-15 (the FYTOK-SRS-04 gold band).
using EPEDNN
m = EPEDNN.loadmodel("EPED1NNmodel.bson")
cases = [
  ("iter",  (2.0, 1.8, 5.3, 0.48, 15.0, 1.86, 2.5, 7.0, 6.2, 1.8)),
  ("d3d",   (0.6, 2.2, 2.0, 0.55, 1.2, 1.8, 2.0, 5.0, 1.7, 1.8)),
  ("cfedr", (2.5, 1.9, 6.0, 0.45, 15.0, 1.8, 2.5, 6.5, 7.2, 1.7)),
]
for (name, x) in cases
    s = m(x...; warn_nn_train_bounds=false)
    p = Float64[]; w = Float64[]
    for d in (:GH, :G, :H), sol in (:H, :meta, :superH)
        push!(p, Float64(getproperty(getproperty(s.pressure, d), sol)))
        push!(w, Float64(getproperty(getproperty(s.width, d), sol)))
    end
    println(name, " P ", join(string.(p), ","))
    println(name, " W ", join(string.(w), ","))
end
