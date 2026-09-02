"""Vendor-external neural surrogates — the loader, and only the loader.

★★**No model weights are compiled into the kernel or the wasm.**  A surrogate's weights are DATA:
TGLF-NN's `sat2` model is 3.5 MB across a 20-member ensemble, and putting
that inside a library a browser downloads would be the wrong place for it.
They live in ``nn_tables/`` as ``.npz`` and are read when something asks:

* the repository's own ``nn_tables/`` is the default location, and small
  models live there (EPED-NN is 32 kB);
* ``$FYLITE_NN_DIR`` overrides it, which is where a BIG model goes —
  TGLF-NN's ``sat2`` ensemble is 3.5 MB and belongs wherever the user
  keeps such things, not necessarily in a checkout;
* nothing is read at import — :class:`NNDataMissing` is raised at the point
  of USE, so every capability that needs no surrogate keeps working with
  nothing configured;
* a model is loaded on first use and cached for the process.

An exported model is one ``.npz`` written by ``tools/nn-export.jl`` from a
Julia checkout that has the upstream package.  The exporter records the
architecture, the normalisation, the training-box bounds and the flat
weights, plus the sha256 of the file it came from — so a number quoted
from a run can be tied back to a specific upstream artefact.  **Nothing
about the upstream model is redistributed by this repository.**

The kernel does the arithmetic (`rust/fylite/src/nn.rs`); this module only
finds the file, checks it against the shape it declares, and marshals it.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

__all__ = ["NNDataMissing", "NN_ENV", "BUILTIN_DIR", "ACT_CODES",
           "configured", "model_dirs", "available", "load", "Surrogate"]

#: Overrides the built-in table directory.  Unset is a normal state.
NN_ENV = "FYLITE_NN_DIR"

#: The repository's own table directory — the default, and the one small
#: models ship in.  Resolved relative to the package so a wheel keeps it.
BUILTIN_DIR = Path(__file__).resolve().parents[2] / "nn_tables"

#: ★★The activation NAME a model file declares -> the integer code that
#: crosses the C ABI (`rust/fylite/src/nn.rs`'s `Act::from_code`).  This is
#: the ONE table: `kernel.py` imports it rather than spelling it again.
#:
#: It was two tables — this one, which only VALIDATED, and a literal in
#: `kernel.nn_ensemble`, which was the one that actually reached the
#: kernel.  Two copies of a wire format are not a wire format: adding
#: `tanh` to this one alone would have let a QLKNN model load and then
#: raise `KeyError` at the call, and adding it to the other alone would
#: have sent code 3 for a model this loader had already refused.
ACT_CODES = {"identity": 0, "elu": 1, "gelu": 2, "tanh": 3, "relu": 4}


class NNDataMissing(RuntimeError):
    """A surrogate is needed and none is configured, or the named one is
    not in the configured directory.

    Raised at the point of USE, never at import — the same contract
    :class:`fylite.device.MachineDataMissing` keeps for machine data.
    """


def configured() -> bool:
    """Whether any directory with models in it is reachable."""
    return bool(available())


def model_dirs() -> list[Path]:
    """Where to look, in order: ``$FYLITE_NN_DIR`` first (so an override
    really overrides), then the built-in ``nn_tables/``."""
    out = []
    d = os.environ.get(NN_ENV)
    if d:
        p = Path(d).expanduser()
        if not p.is_dir():
            raise NNDataMissing(f"${NN_ENV} points at {p}, which is not a "
                                f"directory")
        out.append(p)
    if BUILTIN_DIR.is_dir():
        out.append(BUILTIN_DIR)
    return out


def available() -> list[str]:
    """Every model name reachable, nearest directory winning; ``[]`` when
    there are none — asking what is available must not be what raises."""
    try:
        dirs = model_dirs()
    except NNDataMissing:
        return []
    seen = {}
    for d in dirs:
        for p in sorted(d.glob("*.npz")):
            seen.setdefault(p.stem, p)
    return sorted(seen)


class Surrogate:
    """One exported model: its shape, its normalisation, its weights.

    ``__call__`` takes the inputs in the model's own ``xnames`` order and
    returns ``(mean, spread)`` over the ensemble — the spread being the
    members' sample standard deviation, which is what the ensemble can say
    about its own scatter and **not** a physics uncertainty.  It is worth
    reading: on the ITER benchmark the 20 members' electron energy flux
    spans 1.93 to 8.09 about a mean of 5.38.
    """

    def __init__(self, path: Path):
        z = np.load(path, allow_pickle=False)
        self.path = path
        self.name = str(path.stem)
        self.n_in = int(z["n_in"])
        self.n_hidden = int(z["n_hidden"])
        self.n_hidden_layers = int(z["n_hidden_layers"]) \
            if "n_hidden_layers" in z.files else 0
        self.n_blocks = int(z["n_blocks"])
        self.n_out = int(z["n_out"])
        self.n_members = int(z["n_members"])
        #: text fields travel as NUL-separated UTF-8 bytes — NPZ has no
        #: string array, and the name lists are contract (they fix the
        #: input ORDER), so they round-trip rather than being rebuilt
        txt = lambda k: bytes(z[k]).decode("utf-8")  # noqa: E731
        self.activation = txt("activation")
        self.xnames = txt("xnames").split("\0")
        self.ynames = txt("ynames").split("\0")
        self.log10_mask = np.ascontiguousarray(z["log10_mask"], np.int32)
        #: the model's own input conditioning, applied before everything
        #: else; absent means the model declares none
        self.x_shift = (np.ascontiguousarray(z["x_shift"], float)
                        if "x_shift" in z.files else np.zeros(0, float))
        self.x_abs = (np.ascontiguousarray(z["x_abs"], np.int32)
                      if "x_abs" in z.files else np.zeros(0, np.int32))
        self.xm = np.ascontiguousarray(z["xm"], float)
        self.xs = np.ascontiguousarray(z["xs"], float)
        self.ym = np.ascontiguousarray(z["ym"], float)
        self.ys = np.ascontiguousarray(z["ys"], float)
        self.xbounds = np.ascontiguousarray(z["xbounds"], float)
        self.weights = np.ascontiguousarray(z["weights"], float).ravel()
        #: ★the optional POWER-LAW head: EPED-NN fits one and trains the
        #: network to correct it, TGLF-NN has none.  An ABSENT head and a
        #: head of zeros are different things, so absent stays empty.
        self.powerlaw = (np.ascontiguousarray(z["powerlaw"], float).ravel()
                         if "powerlaw" in z.files else
                         np.zeros(0, float))
        #: provenance the exporter carried across
        self.source = {k: txt(k) for k in
                       ("source_package", "source_version", "source_file",
                        "source_sha256") if k in z}
        if self.activation not in ACT_CODES:
            raise NNDataMissing(
                f"{path.name}: activation {self.activation!r} is not one the "
                f"kernel implements ({sorted(ACT_CODES)})")
        #: ★checked against the KERNEL's own arithmetic, not against a
        #: number recomputed here — a loader that agrees with itself would
        #: not catch a truncated export
        from . import kernel as K

        per = K.nn_weight_count(self.n_in, self.n_hidden,
                                self.n_hidden_layers, self.n_blocks,
                                self.n_out)
        want = per * self.n_members
        if self.weights.size != want:
            raise NNDataMissing(
                f"{path.name}: holds {self.weights.size} weights, but "
                f"{self.n_members} members of this shape need {want} "
                f"({per} each) — the export is truncated or its declared "
                f"shape is wrong")
        if (self.powerlaw.size
                and self.powerlaw.size != self.n_out * (self.n_in + 1)):
            raise NNDataMissing(
                f"{path.name}: the power-law head has {self.powerlaw.size} "
                f"coefficients, expected {self.n_out} x ({self.n_in} + 1)")
        for nm, arr, n in (("log10_mask", self.log10_mask, self.n_in),
                           ("xm", self.xm, self.n_in),
                           ("xs", self.xs, self.n_in),
                           ("ym", self.ym, self.n_out),
                           ("ys", self.ys, self.n_out),
                           ("xnames", self.xnames, self.n_in),
                           ("ynames", self.ynames, self.n_out)):
            if len(arr) != n:
                raise NNDataMissing(f"{path.name}: {nm} has {len(arr)} "
                                    f"entries, expected {n}")

    def outside_training_box(self, x) -> dict:
        """``{name: (value, lo, hi)}`` for inputs outside the box the
        exporter carried from the model file, with the log10 already
        applied where the mask says so — upstream WARNS rather than
        refuses, so this reports and the caller decides."""
        x = np.asarray(x, float)
        out = {}
        for i, nm in enumerate(self.xnames):
            v = x[i]
            if self.x_shift.size:
                v += self.x_shift[i]
            if self.x_abs.size and self.x_abs[i]:
                v = abs(v)
            if self.log10_mask[i] and v > 0:
                v = np.log10(v)
            lo, hi = self.xbounds[i]
            if v < lo or v > hi:
                out[nm] = (float(v), float(lo), float(hi))
        return out

    def __call__(self, x):
        from . import kernel as K

        return K.nn_ensemble(self, np.asarray(x, float))

    def __repr__(self):
        head = " +powerlaw" if self.powerlaw.size else ""
        depth = (f"x{self.n_hidden_layers}"
                 + (f"+{self.n_blocks}res" if self.n_blocks else ""))
        return (f"<Surrogate {self.name}: {self.n_in}->{self.n_hidden}"
                f"{depth}->{self.n_out}, {self.n_members} members, "
                f"{self.activation}{head}>")


_cache: dict[str, Surrogate] = {}


def load(name_or_path) -> Surrogate:
    """A surrogate by name (in ``$FYLITE_NN_DIR``) or by explicit path.

    Cached per resolved path for the process — the weights are megabytes
    and a flux match asks for the same model thousands of times.
    """
    p = Path(name_or_path).expanduser()
    if p.suffix == ".npz" and p.is_file():
        path = p
    else:
        stem = Path(name_or_path).name
        dirs = model_dirs()
        for d in dirs:
            cand = d / f"{stem}.npz"
            if cand.is_file():
                path = cand
                break
        else:
            have = available()
            where = ", ".join(str(d) for d in dirs) or "(nowhere to look)"
            raise NNDataMissing(
                f"{stem}.npz is not in {where}"
                + (f" — available: {', '.join(have)}" if have else
                   f".  Big models are not shipped: export one with "
                   f"tools/nn-export.jl and point ${NN_ENV} at it"))
    key = str(path.resolve())
    if key not in _cache:
        _cache[key] = Surrogate(path)
    return _cache[key]
