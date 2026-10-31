import os, tempfile
import numpy as np
os.environ["LAW_LIBRARY"] = os.path.join(tempfile.mkdtemp(), "laws.jsonl")
import library
from law import fit, finish

rng = np.random.default_rng(0)
t = np.linspace(0, 6, 500)
short = {"t": t[:120], "x": 0.1 * np.cos(2 * np.pi * t[:120]) + rng.normal(0, 0.001, 120)}  # 1.4 s: damping invisible
plain = fit(short, "x", "A*cos(w*t+p)", ["A", "w", "p"], [0.1, 6.3, 0])
e = library.add(finish(short, {"axis": "x", "expr": plain["expr"], "params": plain["params"], "note": "keys pendulum"}))
assert e["status"] == "standing" and library.search(["pendulum"])[0]["id"] == 1

# a longer clip of the same pendulum shows the decay: the old undamped law must be caught
long = {"t": t, "x": 0.1 * np.exp(-0.3 * t) * np.cos(2 * np.pi * t) + rng.normal(0, 0.001, t.size)}
r = library.check(long, library.search(["pendulum"]))
assert r[0]["broken"], r
# and a clip that really is undamped keeps it standing
same = {"t": t, "x": 0.1 * np.cos(2 * np.pi * t) + rng.normal(0, 0.001, t.size)}
assert not library.check(same, library.search(["pendulum"]))[0]["broken"]
print("ok")
