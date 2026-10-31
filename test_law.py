import numpy as np
from law import fit, discover, derive, falsify, finish

rng = np.random.default_rng(0)
t = np.linspace(0, 10, 600)
x = 0.1 * np.exp(-0.15 * t) * np.cos(2 * np.pi * t) + rng.normal(0, 0.002, t.size)
d = {"t": t, "x": x, "y": x}

damped = fit(d, "x", "A*exp(-b*t)*cos(w*t+p)", ["A", "b", "w", "p"], [0.1, 0.1, 6.3, 0])
plain = fit(d, "x", "A*cos(w*t+p)", ["A", "w", "p"], [0.1, 6.3, 0])
assert damped["holdout_rmse"] < plain["holdout_rmse"] / 2, (damped, plain)
assert abs(damped["params"]["w"] - 2 * np.pi) < 0.05, damped
assert "error" in fit(d, "x", "__import__('os')", [])
assert "error" in fit(d, "x", "t.real", [])
for bad in ("(lambda: 1)()", "sin.__class__", "c0*open", "1;2", "[c0]", "ｓｉｎ(t)", "sin(t, out=t)"):
    assert "error" in fit(d, "x", bad, ["c0"]), bad
# reviewer findings: attribute access must not mutate the data; huge powers must fail fast, not hang
t0 = d["t"].copy()
assert "error" in fit(d, "x", "t.fill(fill) or t", ["fill"]) and np.array_equal(d["t"], t0)
assert "error" in fit(d, "x", "c0*t.size", ["c0", "size"])
import time
s0 = time.time()
assert "error" in fit(d, "x", "c0+9**9**9", ["c0"]) and "error" in fit(d, "x", "c0*t**9**9**9", ["c0"])
assert time.time() - s0 < 2

# error bars: the true omega lies within 3 sigma, and sigma is small but non-zero
s = damped["sigma"]["w"]
assert 0 < s < 0.01 and abs(damped["params"]["w"] - 2 * np.pi) < 3 * s, damped

# discovery with no family given: damping must be found unprompted
best = discover(d, "x")[0]
assert "exp" in best["expr"] and "cos" in best["expr"], best["expr"]
w = [v for v in best["params"].values() if 6 < abs(v) < 6.6]
assert w and abs(abs(w[0]) - 2 * np.pi) < 0.05, best

# a falling object: quadratic in t, and g derived with error bars in code
y = 1.5 + 0.4 * t - 0.5 * 9.81 * t ** 2 + rng.normal(0, 0.003, t.size)
fall = {"t": t, "x": 0 * t + rng.normal(0, 1e-4, t.size), "y": y}
b = discover(fall, "y")[0]
quad = [k for k in b["params"] if f"{k}*t**2" in b["expr"]]
assert quad, b["expr"]
g, sg = derive(f"-2*{quad[0]}", b)
assert abs(g - 9.81) < 3 * sg + 0.01 and sg < 0.05, (g, sg)

# self-falsification: an undamped law on a damped clip must be caught; the right law survives
assert falsify(d, "x", plain)["verdict"].startswith("FALSIFIED"), falsify(d, "x", plain)
assert falsify(d, "x", damped)["verdict"] == "survived", falsify(d, "x", damped)

# closed loop: prediction computed in code, then a second clip confirms it
r1 = finish(d, {"axis": "x", "expr": damped["expr"], "params": damped["params"],
                "prediction": {"quantity": "period", "expr": "2*pi/w", "unit": "s"}})
assert abs(r1["prediction"]["value"] - 1.0) < 0.01, r1["prediction"]
r2 = finish(d, {"axis": "x", "expr": damped["expr"], "params": damped["params"],
                "measured": {"expr": "2*pi/w", "unit": "s"}}, verify=r1["prediction"])
assert r2["measured"]["verdict"] == "CONFIRMED", r2["measured"]
print("ok")
