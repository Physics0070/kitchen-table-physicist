"""The whole lab in one command: see -> track -> discover -> conserve -> remember -> report -> overlay.

  python lab.py clip.mp4                                  # Wonder decides everything (needs MODEL_API_KEY)
  python lab.py clip.mp4 --color green --fps 240 --note "keys on 30 cm string" --offline
  python lab.py clip40.mp4 --verify runs/clip/fit.json    # test the last run's prediction
"""
import argparse, datetime, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
STAGES = ("look", "track", "discover", "conserve", "remember", "report", "done")  # the app reads these markers


def stage(name):
    print(f"== {name}", flush=True)


def step(*args):
    print("$ " + " ".join(args), flush=True)
    if subprocess.run([sys.executable, os.path.join(HERE, args[0]), *args[1:]]).returncode:
        raise SystemExit(f"step failed: {args[0]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", help="run folder (default runs/<clip name>)")
    ap.add_argument("--note", help="setup description; by default the vision model writes it")
    ap.add_argument("--color", help="track colour marker(s) instead of SAM")
    ap.add_argument("--prompt", help="SAM concept(s) instead of letting the vision model choose")
    ap.add_argument("--fps", help="real capture fps (slow-mo files often report 30)")
    ap.add_argument("--m-per-px", help="skip auto-scale")
    ap.add_argument("--ref-m", help="long side of the reference sheet in metres (A4 = 0.297)")
    ap.add_argument("--verify", help="fit.json whose prediction this clip tests")
    ap.add_argument("--offline", action="store_true", help="no vision or reasoning model; tracking still uses SAM unless --color")
    ap.add_argument("--every", default="1", help="use every Nth frame (SAM cost)")
    a = ap.parse_args()
    from app import load_env
    load_env()  # MODEL_API_KEY etc. from .env, for the steps that call the models

    out = a.out or os.path.join("runs", os.path.splitext(os.path.basename(a.video))[0])
    os.makedirs(out, exist_ok=True)
    p = lambda f: os.path.join(out, f)
    if not os.path.exists(p("meta.json")):  # the app writes its own; the CLI gets a minimal one
        json.dump({"id": os.path.basename(out), "name": os.path.basename(a.video), "video": None,
                   "created": datetime.datetime.now().isoformat(timespec="seconds")}, open(p("meta.json"), "w"))
    note = a.note
    track = ["track.py", a.video, "-o", p("track.csv"), "--every", a.every, "--max-frames", "2000"]
    for flag, v in (("--color", a.color), ("--prompt", a.prompt), ("--fps", a.fps), ("--m-per-px", a.m_per_px), ("--ref-m", a.ref_m)):
        track += [flag, v] if v else []
    stage("look")
    if not (a.color or a.prompt or a.offline):
        step("see.py", a.video, "-o", p("plan.json"))
        track += ["--plan", p("plan.json")]
        note = note or json.load(open(p("plan.json"))).get("note")
    stage("track")
    step(*track)
    stage("discover")
    law = ["law.py", p("track.csv"), "-o", p("fit.json"), "--note", note or "unknown setup"]
    step(*law, *(["--offline"] if a.offline else []), *(["--verify", a.verify] if a.verify else []))
    stage("conserve")
    step("conserve.py", p("track.csv"), "-o", p("conserved.json"))
    stage("remember")
    step("library.py", "check", p("track.csv"), "-o", p("library_check.json"))  # which known laws hold here?
    step("library.py", "add", p("fit.json"))
    stage("report")
    step("report.py", p("fit.json"), p("track.csv"), "--conserved", p("conserved.json"), "-o", p("report.html"))
    step("overlay.py", a.video, p("track.csv"), p("fit.json"), p("overlay.webm"), *(["--fps", a.fps] if a.fps else []))
    step("view.py", out)
    stage("done")
    print(f"done -> {out}/report.html, {out}/overlay.webm")


if __name__ == "__main__":
    main()
