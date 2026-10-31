"""Local web app: drop a clip, watch the lab work, read the law.

  python app.py                 # http://127.0.0.1:8000
  python app.py --port 9000
"""
import argparse, datetime, http.server, json, os, re, shutil, subprocess, sys, threading, time, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.abspath(os.environ.get("RUNS_DIR", os.path.join(HERE, "runs")))
WEB = os.path.join(HERE, "web")
MAX_UPLOAD = 2 << 30  # 2 GB: a minute of 4K slow-mo
ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
COLORS = {"green", "blue", "yellow", "orange"}
FILES = {"overlay.webm", "report.html", "track.csv", "fit.json", "view.json"}  # plus the run's own clip
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".json": "application/json",
         ".csv": "text/csv", ".webm": "video/webm", ".mp4": "video/mp4", ".mov": "video/quicktime", ".m4v": "video/mp4",
         ".mkv": "video/x-matroska", ".avi": "video/x-msvideo", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon"}
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src https://fonts.gstatic.com; img-src 'self' data:; media-src 'self'; frame-src 'self'; frame-ancestors 'self'")
jobs, lock = {}, threading.Lock()


def read_json(path, default=None):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return default


def run_dir(run_id):
    if not ID.match(run_id or ""):
        return None
    d = os.path.join(RUNS, run_id)
    return d if os.path.isdir(d) else None


def status(run_id, log=False):
    d = run_dir(run_id)
    meta = read_json(os.path.join(d, "meta.json"), {})
    text = open(os.path.join(d, "log.txt"), errors="replace").read() if os.path.exists(os.path.join(d, "log.txt")) else ""
    stages = re.findall(r"^== (\w+)", text, re.M)
    p = jobs.get(run_id)
    if stages[-1:] == ["done"] and os.path.exists(os.path.join(d, "view.json")):
        state = "done"
    elif p is not None and p.poll() is None:
        state = "running"
    elif p is None and not text:
        state = "starting"  # clip still uploading or rendering
    else:
        state = "failed" if p is not None else "interrupted"
    s = {**meta, "id": run_id, "state": state, "stage": stages[-1] if stages else None}
    if state == "done":
        fit = read_json(os.path.join(d, "fit.json"), {})
        s.update(law=fit.get("law"), expr=fit.get("expr"), verdict=(fit.get("falsify") or {}).get("verdict"))
    if log or state in ("failed", "interrupted"):
        lines = [l for l in text.splitlines() if l.strip() and not l.startswith("$ ")]
        s["log"] = lines[-14:]
        errs = [l for l in lines if re.search(r"step failed|Error|SystemExit|no reference|cannot read", l)]
        s["error"] = errs[-1] if errs else None
    return s


def number(v, lo, hi):
    x = float(v)
    if not lo <= x <= hi:
        raise ValueError(f"{v} is outside {lo}..{hi}")
    return str(x)


def options(q):
    """Validated lab.py flags from the query string; raises ValueError with a readable message."""
    g = lambda k: (q.get(k) or [""])[0].strip()
    args = []
    if g("color"):
        cs = g("color").split(",")
        if not set(cs) <= COLORS:
            raise ValueError("colour must be one of " + ", ".join(sorted(COLORS)))
        args += ["--color", ",".join(cs)]
    if g("prompt"):
        args += ["--prompt", g("prompt")[:200]]
    for k, flag, lo, hi in (("fps", "--fps", 1, 10000), ("m_per_px", "--m-per-px", 1e-7, 1), ("ref_m", "--ref-m", 0.005, 10)):
        if g(k):
            args += [flag, number(g(k), lo, hi)]
    if g("note"):
        args += ["--note", g("note")[:400]]
    if g("verify"):
        v = run_dir(g("verify"))
        if not v or not os.path.exists(os.path.join(v, "fit.json")):
            raise ValueError("the run to verify against has no law yet")
        args += ["--verify", os.path.join(v, "fit.json")]
    if g("offline") in ("1", "true", "on") or not os.environ.get("MODEL_API_KEY"):
        args.append("--offline")
    if not g("color") and not os.environ.get("MODEL_API_KEY"):
        raise ValueError("without MODEL_API_KEY the app can only track a colour marker: pick its colour")
    return args


def start(run_id, video, args):
    d = os.path.join(RUNS, run_id)
    log = open(os.path.join(d, "log.txt"), "w")
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "lab.py"), video, "--out", d, *args],
                         cwd=HERE, stdout=log, stderr=subprocess.STDOUT, env=env)
    with lock:
        jobs[run_id] = p


def new_run(name, extra=None):
    base = re.sub(r"[^a-z0-9]+", "-", os.path.splitext(os.path.basename(name))[0].lower()).strip("-")[:40] or "clip"
    run_id = f"{base}-{datetime.datetime.now():%Y%m%d-%H%M%S}"
    d = os.path.join(RUNS, run_id)
    os.makedirs(d)
    ext = os.path.splitext(name)[1].lower()
    meta = {"id": run_id, "name": os.path.basename(name)[:120], "video": "clip" + ext,
            "created": datetime.datetime.now().isoformat(timespec="seconds"), **(extra or {})}
    json.dump(meta, open(os.path.join(d, "meta.json"), "w"))
    return run_id, os.path.join(d, "clip" + ext)


def sample():
    from sample import render, FPS
    run_id, path = new_run("sample-pendulum.webm", {"sample": True})
    render(path)
    start(run_id, path, ["--color", "green", "--fps", str(FPS), "--offline",
                         "--note", "Sample: rendered pendulum, 0.5 m string, released at 15 degrees"])
    return run_id


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "KitchenTablePhysicist"

    def log_message(self, fmt, *a):
        if not self.path.startswith("/api/runs/") or "/file/" not in self.path:
            sys.stderr.write(f"{self.command} {self.path.split('?')[0]} {a[1] if len(a) > 1 else ''}\n")

    def head(self, code, ctype, length=None, extra=()):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Cache-Control", "no-store" if ctype.startswith("application/json") else "no-cache")
        if length is not None:
            self.send_header("Content-Length", str(length))
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()

    def json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.head(code, "application/json", len(body))
        self.wfile.write(body)

    def fail(self, code, msg):
        self.json({"error": msg}, code)

    def file(self, path):
        if not os.path.isfile(path):
            return self.fail(404, "not found")
        size, ctype = os.path.getsize(path), TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
        start, end = 0, size - 1
        m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", ""))
        if m and (m[1] or m[2]):  # video scrubbing needs byte ranges
            start, end = (int(m[1]), int(m[2]) if m[2] else size - 1) if m[1] else (size - int(m[2]), size - 1)
            if start >= size or start > end:
                return self.head(416, ctype, 0, [("Content-Range", f"bytes */{size}")])
            end = min(end, size - 1)
            self.head(206, ctype, end - start + 1, [("Content-Range", f"bytes {start}-{end}/{size}"), ("Accept-Ranges", "bytes")])
        else:
            self.head(200, ctype, size, [("Accept-Ranges", "bytes")])
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        parts = [urllib.parse.unquote(p) for p in u.path.strip("/").split("/") if p]
        if not parts or parts == ["index.html"]:
            return self.file(os.path.join(WEB, "index.html"))
        if parts[0] == "web" and len(parts) == 2 and re.match(r"^[\w.-]+$", parts[1]) and ".." not in parts[1]:
            return self.file(os.path.join(WEB, parts[1]))
        if parts[0] == "favicon.ico":
            return self.file(os.path.join(WEB, "icon.svg"))
        if parts[:2] == ["api", "health"]:
            try:
                import openai  # noqa: F401
                has_sdk = True
            except ImportError:
                has_sdk = False
            return self.json({"key": bool(os.environ.get("MODEL_API_KEY")), "sdk": has_sdk})
        if parts[:2] == ["api", "runs"] and len(parts) == 2:
            runs = [status(r) for r in os.listdir(RUNS) if run_dir(r)] if os.path.isdir(RUNS) else []
            return self.json(sorted(runs, key=lambda s: s.get("created", ""), reverse=True))
        if parts[:2] == ["api", "runs"] and len(parts) >= 3:
            d = run_dir(parts[2])
            if not d:
                return self.fail(404, "no such run")
            if len(parts) == 3:
                return self.json(status(parts[2], log=True))
            if len(parts) == 5 and parts[3] == "file":
                meta = read_json(os.path.join(d, "meta.json"), {})
                if parts[4] in FILES or parts[4] == meta.get("video"):
                    return self.file(os.path.join(d, parts[4]))
            return self.fail(404, "not found")
        if parts[:2] == ["api", "library"]:
            import library
            words = urllib.parse.parse_qs(u.query).get("q", [""])[0].split()
            return self.json(list(reversed(library.search(words))))
        self.fail(404, "not found")

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/api/sample":
            return self.json({"id": sample()}, 201)
        if u.path != "/api/runs":
            return self.fail(404, "not found")
        name = (q.get("name") or [""])[0]
        if os.path.splitext(name)[1].lower() not in VIDEO_EXT:
            return self.fail(400, "that file is not a video: use mp4, mov, m4v, webm, mkv or avi")
        n = int(self.headers.get("Content-Length") or 0)
        if not 0 < n <= MAX_UPLOAD:
            return self.fail(413, "the clip is empty or bigger than 2 GB: trim it first")
        try:
            args = options(q)
        except ValueError as e:
            return self.fail(400, str(e))
        run_id, path = new_run(name, {"options": {k: v[0] for k, v in q.items() if k != "name"}})
        with open(path, "wb") as f:
            left = n
            while left > 0:
                chunk = self.rfile.read(min(1 << 20, left))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        if left:
            shutil.rmtree(os.path.dirname(path), ignore_errors=True)
            return self.fail(400, "the upload was cut off: try again")
        start(run_id, path, args)
        self.json({"id": run_id}, 201)

    def do_DELETE(self):
        parts = [p for p in urllib.parse.urlparse(self.path).path.strip("/").split("/") if p]
        d = run_dir(parts[2]) if parts[:2] == ["api", "runs"] and len(parts) == 3 else None
        if not d:
            return self.fail(404, "no such run")
        p = jobs.get(parts[2])
        if p is not None and p.poll() is None:
            return self.fail(409, "this run is still working: wait for it to finish")
        shutil.rmtree(d, ignore_errors=True)
        self.json({"deleted": parts[2]})


def serve(host="127.0.0.1", port=8000):
    os.makedirs(RUNS, exist_ok=True)
    return http.server.ThreadingHTTPServer((host, port), Handler)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1", help="no login: keep it on localhost unless the network is yours")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    srv = serve(a.host, a.port)
    if not any(run_dir(r) for r in os.listdir(RUNS)):
        threading.Thread(target=sample, daemon=True).start()  # first launch opens on a working example
    print(f"Kitchen-Table Physicist on http://{a.host}:{a.port}" + ("" if os.environ.get("MODEL_API_KEY") else "  (offline: no MODEL_API_KEY)"))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
