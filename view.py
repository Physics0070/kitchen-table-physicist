"""Bundle one run's outputs into view.json for the web app (no formula evaluation in the browser).

  python view.py runs/<id>
"""
import json, os, sys
import cv2
import numpy as np
from law import compile_law, load

LAW_KEYS = ("law", "axis", "expr", "params", "sigma", "derived", "explanation", "rival", "next_experiment", "prediction",
            "measured", "falsify", "holdout_rmse", "train_rmse", "split", "candidates", "tried", "note")


def read(path, default=None):
    return json.load(open(path)) if os.path.exists(path) else default


def export(run):
    d, r = load(os.path.join(run, "track.csv")), read(os.path.join(run, "fit.json"))
    meta = read(os.path.join(run, "meta.json"), {})
    t, ax = d["t"], r["axis"]
    yhat = compile_law(r["expr"], list(r["params"]))(t, *r["params"].values())
    suffix = ax[1:]  # "" for object 0, "1" for x1/y1
    k = d["k"][0]
    if ax[0] == "x":
        pred = np.column_stack([yhat / k, d["py" + suffix]])
    else:
        pred = np.column_stack([d["px" + suffix], -yhat / k])
    w = h = None
    scale = 1.0  # data time = video time * scale (slow-mo clips are stored at a lower fps than they were shot)
    if meta.get("video"):
        cap = cv2.VideoCapture(os.path.join(run, meta["video"]))
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        vfps, real = cap.get(cv2.CAP_PROP_FPS), (meta.get("options") or {}).get("fps")
        if vfps and real:
            scale = vfps / float(real)
    r4 = lambda a: [round(float(v), 4) for v in a]
    objs = sorted({c[2:] for c in d if c.startswith("px")})
    view = {
        **meta, "frame": [w, h], "time_scale": scale, "k": k, "t": r4(t), "measured": r4(d[ax]), "predicted": r4(yhat),
        "objects": [{"px": r4(d["px" + o]), "py": r4(d["py" + o])} for o in objs],
        "pred_px": r4(pred[:, 0]), "pred_py": r4(pred[:, 1]),
        "law": {k_: r.get(k_) for k_ in LAW_KEYS},
        "conserved": read(os.path.join(run, "conserved.json"), []),
        "library": read(os.path.join(run, "library_check.json"), []),
        "plan": read(os.path.join(run, "plan.json")),
    }
    json.dump(view, open(os.path.join(run, "view.json"), "w"))
    return view


if __name__ == "__main__":
    v = export(sys.argv[1])
    print(f"view.json: {len(v['t'])} samples, law {v['law']['expr']}")
