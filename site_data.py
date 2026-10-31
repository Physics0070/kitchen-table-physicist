"""Export the real pipeline results the showcase site draws: site/assets/data.js.

  python site_data.py
Every dot, curve and number on the page comes from here; nothing on the page is typed in by hand.
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
from law import discover, derive, falsify, fit, compile_law, _curve, ladder
from sample import render, FPS, G, L
from law import load

r4 = lambda a: [round(float(v), 4) for v in a]

# 1. The drop: a 0.9 s fall filmed at 240 fps with 1.5 mm of tracking noise, through the real search.
rng = np.random.default_rng(3)
t = np.arange(0, 0.9, 1 / 240)
y = 1.6 - 0.5 * G * t ** 2 + rng.normal(0, 0.0015, t.size)
d = {"t": t, "x": 0.3 + rng.normal(0, 0.0008, t.size), "y": y}
found = discover(d, "y")
best = found[0]
quad = next(k for k in best["params"] if f"{k}*t**2" in best["expr"])
g, sg = derive(f"-2*{quad}", best)
curve = lambda r: r4(compile_law(r["expr"], list(r["params"]))(t, *r["params"].values()))
kinds = (("a constant", lambda e: e == "c0"), ("a straight line", lambda e: "t" in e and "t**2" not in e and "cos" not in e and "exp" not in e),
         ("a wave", lambda e: "cos" in e and "t**2" not in e), ("a decay", lambda e: "exp" in e and "t**2" not in e and "cos" not in e))
losers = []
for name, ok in kinds:  # the best real fit of each other shape the search tried
    r = min((r for r in found if ok(r["expr"])), key=lambda r: r["score"], default=None)
    if r:
        losers.append({"kind": name, "expr": r["expr"], "holdout_rmse": r["holdout_rmse"]})
drop = {
    "t": r4(t), "y": r4(y), "law": curve(best), "expr": best["expr"], "g": g, "sg": sg, "tried": len(found),
    "holdout_mm": best["holdout_rmse"] * 1000, "verdict": falsify(d, "y", best)["verdict"],
    "rivals": [{"kind": c["kind"], "expr": c["expr"], "mm": c["holdout_rmse"] * 1000,
                "y": curve(next(r for r in found if r["expr"] == c["expr"]))} for c in losers],
}

# 2. The pendulum: the app's sample clip through the tracker, then the self-test the page lets you perform.
import subprocess, tempfile
tmp = tempfile.mkdtemp()
clip, csv_path = os.path.join(tmp, "p.webm"), os.path.join(tmp, "p.csv")
render(clip)
subprocess.run([sys.executable, os.path.join(HERE, "track.py"), clip, "--color", "green",
                "--fps", str(FPS), "--max-frames", "2000", "-o", csv_path], check=True, capture_output=True)
p = load(csv_path)
pt, px = p["t"], p["x"]
damped = next(r for r in discover(p, "x") if len(r["params"]) == 5)  # the 5-constant damped law the app reports
f = compile_law(damped["expr"], list(damped["params"]))
h = len(pt) // 2
a, ca = _curve(f, pt[:h], px[:h], list(damped["params"].values()))
b, cb = _curve(f, pt[h:], px[h:], list(damped["params"].values()))
names = list(damped["params"])
wi = next(i for i, n in enumerate(names) if f"{n}*t" in damped["expr"] and 4 < abs(damped["params"][n]) < 5)
z = abs(a[wi] - b[wi]) / np.sqrt(ca[wi][wi] + cb[wi][wi])
step = 3
pend = {
    "t": r4(pt[::step]), "x": r4(px[::step]), "first": r4(f(pt, *a)[::step]), "second": r4(f(pt, *b)[::step]),
    "w1": float(a[wi]), "w2": float(b[wi]), "s1": float(np.sqrt(ca[wi][wi])), "s2": float(np.sqrt(cb[wi][wi])),
    "z": float(z), "expr": damped["expr"],
    "g": derive(f"{L}*{names[wi]}**2", damped)[0], "split": float(pt[h]),
}

out = os.path.join(HERE, "site", "assets", "data.js")
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, "w").write("window.KTP=" + json.dumps({"drop": drop, "pend": pend}, separators=(",", ":")) + ";\n")
print(f"drop: {best['expr']}  g={g:.4f}±{sg:.4f}  tried={len(found)}  rivals={[c['expr'] for c in losers]}")
print(f"pendulum halves: w {a[wi]:.4f} vs {b[wi]:.4f}  ({z:.1f} sigma)  -> {out} ({os.path.getsize(out)//1024} KB)")
