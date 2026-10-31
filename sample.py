"""Render a pendulum clip with known physics: the app's sample run and the end-to-end test's input.

  python sample.py sample.webm
"""
import sys
import cv2
import numpy as np
from scipy.integrate import solve_ivp

G, L, GAMMA, FPS, K = 9.81, 0.5, 0.1, 120, 0.002  # truth; K = metres per pixel in the render


def render(path, seconds=6, theta0=np.radians(15)):
    sol = solve_ivp(lambda t, s: [s[1], -G / L * np.sin(s[0]) - GAMMA * s[1]], (0, seconds), [theta0, 0],
                    t_eval=np.arange(0, seconds, 1 / FPS), rtol=1e-9, atol=1e-9)
    codec = "VP80" if path.endswith(".webm") else "mp4v"  # webm plays in browsers
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*codec), FPS, (640, 480))
    rng, pivot = np.random.default_rng(1), (320, 30)
    for th in sol.y[0]:
        f = np.full((480, 640, 3), 60, np.uint8)
        cv2.rectangle(f, (40, 330), (40 + round(0.297 / K), 330 + round(0.210 / K)), (245, 245, 245), -1)  # A4
        bob = (round(16 * (pivot[0] + L / K * np.sin(th))), round(16 * (pivot[1] + L / K * np.cos(th))))
        cv2.line(f, (16 * pivot[0], 16 * pivot[1]), bob, (150, 150, 150), 1, cv2.LINE_AA, 4)
        cv2.circle(f, bob, 16 * 9, (40, 200, 40), -1, cv2.LINE_AA, 4)  # shift=4: sub-pixel drawing
        vw.write(cv2.add(f, rng.integers(0, 12, f.shape, dtype=np.uint8)))
    vw.release()


if __name__ == "__main__":
    render(sys.argv[1] if len(sys.argv) > 1 else "sample.webm")
