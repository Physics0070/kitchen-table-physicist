import numpy as np
from conserve import conserved

rng = np.random.default_rng(0)
t = np.linspace(0, 2, 400)

# 1-D elastic collision at t=1: mass 1 at 0.6 m/s hits mass 2 at rest
m1, m2, u = 1.0, 2.0, 0.6
v1, v2 = (m1 - m2) / (m1 + m2) * u, 2 * m1 / (m1 + m2) * u
x1 = np.where(t < 1, u * (t - 1), v1 * (t - 1))
x2 = np.where(t < 1, 0.05, 0.05 + v2 * (t - 1))
n = lambda: rng.normal(0, 2e-4, t.size)
d = {"t": t, "x": x1 + n(), "y": 0.3 + n(), "x1": x2 + n(), "y1": 0.3 + n()}
found = conserved(d, smooth=15, tol=0.1)
mom = [c for c in found if set(c["terms"]) == {"vx", "vx1"}]
assert mom and abs(mom[0]["weights"][1] - m2 / m1) < 0.1, found  # mass ratio recovered from momentum

# pendulum: energy  g*y + v^2/2 = const  must appear (vy^2 is tiny, so it may be left out), with g recovered
L, g = 0.5, 9.81
th = 0.3 * np.cos(np.sqrt(g / L) * t)  # small-angle is fine for a 2% energy check
d = {"t": t, "x": L * np.sin(th) + n(), "y": -L * np.cos(th) + n()}
found = conserved(d, smooth=11, tol=0.05)
en = [c for c in found if {"vx^2", "y"} <= set(c["terms"])]
assert en, found
w = dict(zip(en[0]["terms"], en[0]["weights"]))
assert abs(w["y"] / w["vx^2"] / 2 - g) / g < 0.05, w
print("ok")
