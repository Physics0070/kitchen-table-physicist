"""Save finished runs as recorded demos for the static site: site/lab/recorded/.

  python record_runs.py <run id> [<run id> ...]
The bench on static hosting replays these: real pipeline output, with a light display copy of each clip.
"""
import json, os, re, shutil, sys
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "site", "lab", "recorded")
KEEP = ("view.json", "fit.json", "track.csv", "report.html", "conserved.json")


def display_clip(src, dst, width=480):
    """A small copy for the web (about 2 MB). The overlay is drawn in the original frame's pixels and scaled,
    so any copy with the same aspect ratio and frame rate lines up exactly."""
    cap = cv2.VideoCapture(src)
    fps, w, h = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    size = (width, round(width * h / w / 2) * 2)
    vw = cv2.VideoWriter(dst, cv2.VideoWriter_fourcc(*"VP80"), fps, size)
    ok, f = cap.read()
    while ok:
        vw.write(cv2.resize(cv2.GaussianBlur(f, (5, 5), 0), size, interpolation=cv2.INTER_AREA))
        ok, f = cap.read()
    vw.release()


def scrub(text):
    """No local paths in public files: keep only the part from runs/ onward."""
    return re.sub(r"[A-Za-z]:[\\/][^\"'<>]*?[\\/](runs[\\/])", r"\1", text)


def main():
    ids = sys.argv[1:]
    if not ids:
        raise SystemExit(__doc__)
    sys.path.insert(0, HERE)
    import app
    entries, laws = [], []
    library = [json.loads(l) for l in open(os.path.join(HERE, "laws.jsonl"))] if os.path.exists(os.path.join(HERE, "laws.jsonl")) else []
    for rid in ids:
        src = os.path.join(HERE, "runs", rid)
        st = app.status(rid)
        if st["state"] != "done":
            raise SystemExit(f"{rid} is not finished ({st['state']})")
        dst = os.path.join(OUT, rid)
        os.makedirs(dst, exist_ok=True)
        for f in KEEP:
            if os.path.exists(os.path.join(src, f)):
                open(os.path.join(dst, f), "w", encoding="utf-8").write(scrub(open(os.path.join(src, f), encoding="utf-8").read()))
        display_clip(os.path.join(src, st["video"]), os.path.join(dst, "clip.webm"))
        entries.append({k: st.get(k) for k in ("id", "name", "video", "created", "sample", "state", "stage", "law", "expr", "verdict")} | {"video": "clip.webm"})
        laws += [e for e in library if rid in (e.get("csv") or "")]
    json.dump(sorted(entries, key=lambda e: e["created"], reverse=True), open(os.path.join(OUT, "runs.json"), "w"))
    json.dump([json.loads(scrub(json.dumps(e))) for e in reversed(laws)], open(os.path.join(OUT, "library.json"), "w"))
    mb = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(OUT) for f in fs) / 1e6
    print(f"{len(entries)} runs, {len(laws)} laws -> {OUT} ({mb:.1f} MB)")


if __name__ == "__main__":
    main()
