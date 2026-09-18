"""CFEDR card geometry for drawing: PF coil element rectangles (name, r, z, width, height)."""
from __future__ import annotations

import json


def coils(device_json: str) -> list[dict]:
    dev = json.load(open(device_json))
    out = []
    for coil in dev["pf_active"]["coil"]:
        fast = any((f or {}).get("name") == "b_field_fb" for f in (coil.get("function") or []))
        if fast:
            continue
        rects = []
        for el in coil.get("element") or []:
            rect = ((el.get("geometry") or {}).get("rectangle") or {})
            if all(k in rect for k in ("r", "z", "width", "height")):
                rects.append({"r": float(rect["r"]), "z": float(rect["z"]),
                              "w": float(rect["width"]), "h": float(rect["height"])})
        out.append({"name": coil.get("name") or coil.get("identifier") or "", "rects": rects,
                    "i_max_aturn": coil.get("fylite:i_max_aturn")})
    return out


if __name__ == "__main__":
    import sys
    for c in coils(sys.argv[1]):
        print(c["name"], c["rects"], c["i_max_aturn"])
