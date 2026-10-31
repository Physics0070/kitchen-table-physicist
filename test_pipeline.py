"""End-to-end on a rendered clip with known physics: video -> track.py -> discover -> g ± sigma."""
import os, subprocess, sys, tempfile
import cv2
import numpy as np
from scipy.integrate import solve_ivp
from law import load, discover, derive, falsify

G, L, GAMMA, FPS, K = 9.81, 0.5, 0.1, 120, 0.002  # truth; K = metres per pixel in the render


def render(path, seconds=6, theta0=np.radians(15)):
    sol = solve_ivp(lambda t, s: [s[1], -G / L * np.sin(s[0]) - GAMMA * s[1]], (0, seconds), [theta0, 0],
                    t_eval=np.arange(0, seconds, 1 / FPS), rtol=1e-9, atol=1e-9)
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (640, 480))
    rng, pivot = np.random.default_rng(1), (320, 30)
    for th in sol.y[0]:
        f = np.full((480, 640, 3), 60, np.uint8)
        cv2.rectangle(f, (40, 330), (40 + round(0.297 / K), 330 + round(0.210 / K)), (245, 245, 245), -1)  # A4
        bob = (round(16 * (pivot[0] + L / K * np.sin(th))), round(16 * (pivot[1] + L / K * np.cos(th))))
        cv2.line(f, (16 * pivot[0], 16 * pivot[1]), bob, (150, 150, 150), 1, cv2.LINE_AA, 4)
        cv2.circle(f, bob, 16 * 9, (40, 200, 40), -1, cv2.LINE_AA, 4)  # shift=4: sub-pixel drawing
        vw.write(cv2.add(f, rng.integers(0, 12, f.shape, dtype=np.uint8)))
    vw.release()


tmp = tempfile.mkdtemp()
clip, csv_path = os.path.join(tmp, "pendulum.mp4"), os.path.join(tmp, "track.csv")
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
