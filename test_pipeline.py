"""End-to-end on a rendered clip with known physics: video -> track.py -> discover -> g ± sigma."""
import os, subprocess, sys, tempfile
from law import load, discover, derive, falsify
from sample import render, G, L, FPS, K

tmp = tempfile.mkdtemp()
clip, csv_path = os.path.join(tmp, "pendulum.webm"), os.path.join(tmp, "track.csv")
render(clip)
out = subprocess.run([sys.executable, "track.py", clip, "--color", "green", "--fps", str(FPS),
                      "--max-frames", "2000", "-o", csv_path], capture_output=True, text=True)
assert out.returncode == 0, out.stderr
d = load(csv_path)
assert abs(d["k"][0] - K) / K < 0.02, f"auto-scale from A4 off: {d['k'][0]} vs {K}"

best = discover(d, "x")[0]
w = next(n for n, v in best["params"].items() if f"{n}*t" in best["expr"] and "cos" in best["expr"] and 4 < abs(v) < 5)
g, sg = derive(f"{L}*{w}**2", best)
print(f"law x(t) = {best['expr']}\ng = {g:.3f} ± {sg:.3f} m/s^2 (truth {G}); self-test: {falsify(d, 'x', best)['verdict']}")
assert "exp" in best["expr"], "damping not found"
assert abs(g - G) / G < 0.02, g  # 15 deg swing lengthens the period ~0.4%, scale error ~0.3%
print("ok")
