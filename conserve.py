"""Discover conserved quantities in tracked motion, without being told which ones to look for.

Builds every monomial of degree <= 2 in the state (x, y, vx, vy of every object), then finds the
sparsest weighted sums that stay constant over time. Momentum shows up as vx + m*vx1 = const
(m = mass ratio), energy as vx^2 + vy^2 + 2g*y = const, a string as x^2 + y^2 + c*y = const.
  python conserve.py collide.csv
"""
import argparse, itertools, json, re
import numpy as np
from scipy.signal import savgol_filter
from law import load, axes


def state(d, smooth, snr=3):
    """Smoothed positions and velocities of coordinates that really move. A coordinate whose
    spread is under snr x its own noise (raw - smoothed) is static: returned separately."""
    t, s, static = d["t"], {}, []
    w = max(5, smooth | 1)  # odd window
    for a in axes(d):
        sm = savgol_filter(d[a], w, 2)
        if sm.std() < snr * (d[a] - sm).std():
            static.append(a)
            continue
        s[a] = sm - sm.mean()  # laws must not depend on where the origin is
        s["v" + a] = savgol_filter(d[a], w, 2, deriv=1, delta=float(np.median(np.diff(t))))
    return s, static


def features(s):
    names = list(s)
    f = {n: s[n] for n in names}
    for a, b in itertools.combinations_with_replacement(names, 2):
        f[f"{a}*{b}" if a != b else f"{a}^2"] = s[a] * s[b]
    return f


def conserved(d, smooth=9, tol=0.05, max_terms=3, top=5):
    """Return sparse combinations whose std over time is < tol of the std of their parts."""
    s, static = state(d, smooth)
    f = features(s)
    trim = slice(smooth, -smooth)  # derivative edges are unreliable
    names = [n for n in f if np.std(f[n][trim]) > 0]
    Z = {n: (f[n][trim] - f[n][trim].mean()) / f[n][trim].std() for n in names}
    found = []
    for size in range(2, max_terms + 1):
        for combo in itertools.combinations(names, size):
            if any(set(c["terms"]) <= set(combo) for c in found):
                continue  # already explained by a sparser law
            if len({v for n in combo for v in re.split(r"[*^]", n) if not v.isdigit()}) < 2:
                continue  # f(one variable) = const only if it is static, handled above
            M = np.column_stack([Z[n] for n in combo])
            _, sv, vt = np.linalg.svd(M, full_matrices=False)
            rel = sv[-1] / np.sqrt(len(M))  # std of the best unit-norm combination, parts have std 1
            if rel < tol:
                w = vt[-1] / np.array([f[n][trim].std() for n in combo])  # back to physical units
                w = w / w[0]
                found.append({"terms": list(combo), "weights": [float(x) for x in w], "spread": float(rel),
                              "law": " + ".join(f"{x:.4g}*{n}" for x, n in zip(w, combo)) + " = const"})
    trivial = [{"terms": [a], "weights": [1.0], "spread": 0.0, "law": f"{a} = const (does not move)"} for a in static]
    return trivial + sorted(found, key=lambda c: (len(c["terms"]), c["spread"]))[:top]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--smooth", type=int, default=9, help="Savitzky-Golay window (frames) for velocities")
    ap.add_argument("--tol", type=float, default=0.05, help="max relative spread to call something conserved")
    ap.add_argument("-o", "--out", default="conserved.json")
    a = ap.parse_args()
    found = conserved(load(a.csv), a.smooth, a.tol)
    for c in found:
        print(f"conserved within {c['spread']:.1%}:  {c['law']}")
    if not found:
        print(f"nothing conserved within {a.tol:.0%}")
    json.dump(found, open(a.out, "w"), indent=2)


if __name__ == "__main__":
    main()
