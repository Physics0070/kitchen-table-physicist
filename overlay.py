"""Draw tracked (green) vs the agent's law (magenta) on the video. The demo's money shot.

  python overlay.py pendulum.mp4 track.csv fit.json overlay.mp4 [--fps 240]
"""
import json, sys
import cv2
import numpy as np
from law import compile_law, load


def main():
    video, track_csv, fit_json, out = sys.argv[1:5]
    fps_override = float(sys.argv[sys.argv.index("--fps") + 1]) if "--fps" in sys.argv else None
    d, law = load(track_csv), json.load(open(fit_json))
    f = compile_law(law["expr"], list(law["params"]))
    p = list(law["params"].values())
    k = d["k"][0]
    t_split = d["t"][int(len(d["t"]) * law["split"])]

    cap = cv2.VideoCapture(video)
    fps = fps_override or cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    vw = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*"mp4v"), 30, (w, h))  # play back at 30 = slow motion
    trail, i = [], 0
    while True:
        ok, frame = cap.read()
        if not ok or i / fps > d["t"][-1]:
            break
        t = i / fps
        j = int(np.abs(d["t"] - t).argmin())
        real = (int(d["px"][j]), int(d["py"][j]))
        v = float(f(np.array([t]), *p)[0])
        # ponytail: only the fitted axis is predicted; the other is taken from tracking
        pred = (int(v / k), real[1]) if law["axis"] == "x" else (real[0], int(-v / k))
        trail.append(pred)
        cv2.polylines(frame, [np.array(trail[-60:], np.int32)], False, (255, 0, 255), 2)
        cv2.circle(frame, real, 10, (0, 255, 0), 2)
        cv2.circle(frame, pred, 6, (255, 0, 255), -1)
        label = "PREDICTING unseen frames" if t > t_split else "fitting"
        cv2.putText(frame, f"{label}   {law['law']}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        m = law.get("measured") or {}
        if "verdict" in m:  # L3: the prediction is on screen before the measurement lands on it
            cv2.putText(frame, f"PREDICTED {m['predicted']:.4g} {m.get('unit', '')}", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)
            if t > t_split:
                cv2.putText(frame, f"MEASURED  {m['value']:.4g}  {m['verdict']}", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        vw.write(frame)
        i += 1
    vw.release()
    print(f"-> {out}")


if __name__ == "__main__":
    main()
