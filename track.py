"""Phone video -> CSV of object positions (metres, seconds, y up).

SAM 3.1 by default; --color uses plain OpenCV colour tracking as a fallback.
Scale: --m-per-px, else a white reference sheet found by OpenCV, else SAM finds the reference.
  python track.py pendulum.mp4 --prompt "keys hanging on a cable" --fps 240
  python track.py collide.mp4 --color green,orange          # two objects -> x,y,x1,y1
  python track.py clip.mp4 --plan plan.json                 # objects + reference chosen by see.py
"""
import argparse, base64, csv, json, os
import cv2
import numpy as np

COLORS = {  # HSV ranges for a brightly coloured marker on the object
    "green": ((40, 80, 60), (85, 255, 255)),
    "blue": ((95, 120, 60), (130, 255, 255)),
    "yellow": ((20, 100, 100), (35, 255, 255)),
    "orange": ((8, 120, 120), (20, 255, 255)),
}


def by_color(frame, color):
    lo, hi = COLORS[color]
    mask = cv2.inRange(cv2.cvtColor(frame, cv2.COLOR_BGR2HSV), lo, hi)
    cs = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
    if not cs:
        return None
    m = cv2.moments(max(cs, key=cv2.contourArea))
    if not m["m00"]:
        return None
    return m["m10"] / m["m00"], m["m01"] / m["m00"], 0, 0  # sub-pixel centroid as a zero-size box


def find_sheet(frame, min_frac=0.01):
    """Longest side (px) of the biggest white quadrilateral, e.g. an A4 sheet; None if absent."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 0, 170), (180, 60, 255))
    best = None
    for c in cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
        area = cv2.contourArea(c)
        quad = len(cv2.approxPolyDP(c, 0.03 * cv2.arcLength(c, True), True)) == 4
        if quad and area > min_frac * mask.size and (best is None or area > cv2.contourArea(best)):
            best = c
    return max(cv2.minAreaRect(best)[1]) if best is not None else None


def by_sam(frame, prompt, client):
    jpg = base64.b64encode(cv2.imencode(".jpg", frame)[1]).decode()
    r = client.responses.create(model="sam-3.1", input=[{"role": "user", "content": [
        {"type": "input_text", "text": prompt},
        {"type": "input_image", "image_url": "data:image/jpeg;base64," + jpg}]}])
    return first_box(r.model_dump(), getattr(r, "output_text", None), frame.shape[1], frame.shape[0])


def first_box(dump, text=None, w=1, h=1):
    """(x, y, w, h) px of the first box anywhere in a SAM response; None for an empty result.
    # ponytail: SAM 3.1 schema unverified; this accepts any 4-number '*box*' field, xyxy or xywh,
    # pixel or normalised. Pin it to the documented field once a live response has been seen."""
    def quad(v):
        return isinstance(v, list) and len(v) == 4 and all(type(n) in (int, float) and np.isfinite(n) for n in v)

    def find(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if "box" in k.lower() and isinstance(v, list) and v and quad(v[0]):
                    v = v[0]  # a list of boxes: take the first detection
                if "box" in k.lower() and quad(v):
                    return v, k
                if (hit := find(v)) is not None:
                    return hit
        elif isinstance(o, list):
            for v in o:
                if (hit := find(v)) is not None:
                    return hit
        return None
    hit = find(dump)
    if hit is None and text:
        try:
            hit = find(json.loads(text))
        except ValueError:
            pass
    if hit is None:
        return None
    (a, b, c, d), key = hit
    if max(a, b, c, d) <= 1.0 and not all(float(n).is_integer() for n in (a, b, c, d)):  # normalised
        a, b, c, d = a * w, b * h, c * w, d * h
    xywh = "wh" in key.lower() or c < a or d < b
    return (int(a), int(b), int(c), int(d)) if xywh else (int(a), int(b), int(c - a), int(d - b))


def columns(n):
    cols = ["t", "x", "y", "px", "py", "k"]
    return cols + [f"{c}{i}" for i in range(1, n) for c in ("x", "y", "px", "py")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("-o", "--out", default="track.csv")
    ap.add_argument("--prompt", default="the moving object", help="SAM concept; separate several objects with ';'")
    ap.add_argument("--color", help="colour marker(s), comma separated: " + ",".join(COLORS))
    ap.add_argument("--plan", help="plan.json from see.py: objects and reference picked by the vision model")
    ap.add_argument("--m-per-px", type=float, help="skip auto-scale")
    ap.add_argument("--ref-m", type=float, default=0.297, help="long side of the reference (A4 = 0.297 m)")
    ap.add_argument("--ref-prompt", default="white sheet of paper", help="SAM concept for the reference if OpenCV misses it")
    ap.add_argument("--fps", type=float, help="real capture fps; slow-mo files often report 30, so set this")
    ap.add_argument("--every", type=int, default=1, help="use every Nth frame")
    ap.add_argument("--max-frames", type=int, default=600)
    a = ap.parse_args()
    from app import load_env
    load_env()  # keys from .env

    prompts = [p.strip() for p in a.prompt.split(";")]
    if a.plan:
        plan = json.load(open(a.plan))
        prompts = [o["prompt"] for o in plan["objects"]]
        ref = plan.get("reference") or {}
        a.ref_prompt, a.ref_m = ref.get("prompt", a.ref_prompt), ref.get("size_m", a.ref_m)
        a.fps = a.fps or plan.get("fps")
    colors = a.color.split(",") if a.color else None

    client = None
    if not colors or not a.m_per_px:
        try:
            from openai import OpenAI
            client = OpenAI(base_url=os.environ.get("MODEL_BASE_URL", "https://api.meta.ai/v1"), api_key=os.environ["MODEL_API_KEY"])
        except (ImportError, KeyError):
            if not colors:
                raise SystemExit("SAM needs `pip install openai` and MODEL_API_KEY; or use --color")

    cap = cv2.VideoCapture(a.video)
    fps = a.fps or cap.get(cv2.CAP_PROP_FPS)
    ok, frame = cap.read()
    if not ok:
        raise SystemExit(f"cannot read {a.video}")

    k = a.m_per_px
    if not k:
        side = find_sheet(frame)
        if side is None and client:
            box = by_sam(frame, a.ref_prompt, client)
            side = max(box[2], box[3]) if box else None
        if not side:
            raise SystemExit("no reference found in first frame; pass --m-per-px")
        k = a.ref_m / side
    print(f"scale {k:.6f} m/px, {fps:.1f} fps, tracking {colors or prompts}")

    rows, i, missed = [], 0, 0
    while ok and len(rows) < a.max_frames:
        if i % a.every == 0:
            boxes = [by_color(frame, c) for c in colors] if colors else [by_sam(frame, p, client) for p in prompts]
            if all(boxes):  # ponytail: drop frames where any object is lost; interpolate if gaps matter
                row = [i / fps]
                for j, b in enumerate(boxes):
                    px, py = b[0] + b[2] / 2, b[1] + b[3] / 2
                    row += [px * k, -py * k, px, py] + ([k] if j == 0 else [])
                rows.append(row)
            else:
                missed += 1
        ok, frame = cap.read()
        i += 1

    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(columns(len(colors or prompts)))
        w.writerows(rows)
    print(f"{len(rows)} points -> {a.out}" + (f" ({missed} frames lost the object)" if missed else ""))


if __name__ == "__main__":
    main()
