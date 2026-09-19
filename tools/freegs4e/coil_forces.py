"""FreeGS4E side of the FR-EQ-014 cross-check: one freegs4e Coil per element, forces by Coil.getForces."""
import json, sys
import numpy as np
from freegs4e.coil import Coil, AreaCurrentLimit
inp = json.load(open(sys.argv[1]))
coils = []
for e in inp["elements"]:
    c = Coil(e["r"], e["z"], current=e["aturns"], turns=1, control=False)
    c.area = e["w"] * e["h"]          # minor radius sqrt(area / pi) for the hoop term
    coils.append(c)
class Shim:
    """Br / Bz of every coil (a zeroed coil contributes nothing) — no plasma."""
    def Br(self, R, Z):
        return sum(c.Br(R, Z) for c in coils)
    def Bz(self, R, Z):
        return sum(c.Bz(R, Z) for c in coils)
shim = Shim()
out = []
for c in coils:
    fr, fz = c.getForces(shim)
    out.append({"f_r": float(fr), "f_z": float(fz)})
json.dump({"freegs4e_forces": out}, open(sys.argv[2], "w"), indent=1)
print("ok", len(out))
