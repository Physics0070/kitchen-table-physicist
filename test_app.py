"""The app end to end: upload a clip over HTTP, wait for the lab, read the view; plus the guard rails."""
import json, os, tempfile, threading, time, urllib.error, urllib.request
tmp = tempfile.mkdtemp()
os.environ.update(RUNS_DIR=os.path.join(tmp, "runs"), LAW_LIBRARY=os.path.join(tmp, "laws.jsonl"))
os.environ.pop("MODEL_API_KEY", None)
import app
from sample import render

srv = app.serve("127.0.0.1", 0)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}"


def call(path, data=None, method=None, headers=None):
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


# guard rails
assert call("/api/runs/..%2F..%2Fapp.py")[0] == 404
assert call("/web/..%2Fapp.py")[0] == 404
assert call("/api/runs?name=x.exe", b"x", "POST")[0] == 400
assert call("/api/runs?name=x.mp4", b"x", "POST")[0] == 400  # no key and no colour: refused with a reason
assert b"colour" in call("/api/runs?name=x.mp4", b"x", "POST")[1]
assert call("/api/runs?name=x.mp4&color=green&fps=-3", b"x", "POST")[0] == 400
s, body, h = call("/")
assert s == 200 and b"<main" in body and "script-src 'self'" in h["Content-Security-Policy"]

# upload a rendered pendulum and let the lab run
clip = os.path.join(tmp, "pendulum.webm")
render(clip)
s, body, _ = call("/api/runs?name=pendulum.webm&color=green&fps=120&note=test", open(clip, "rb").read(), "POST",
                  {"Content-Type": "video/webm"})
assert s == 201, body
rid = json.loads(body)["id"]
for _ in range(300):
    st = json.loads(call(f"/api/runs/{rid}")[1])
    if st["state"] not in ("running", "starting"):
        break
    time.sleep(1)
assert st["state"] == "done", st
v = json.loads(call(f"/api/runs/{rid}/file/view.json")[1])
assert len(v["t"]) == len(v["pred_px"]) > 500 and "exp" in v["law"]["expr"] and v["law"]["candidates"], v["law"]
s, part, h = call(f"/api/runs/{rid}/file/clip.webm", headers={"Range": "bytes=0-99"})
assert s == 206 and len(part) == 100 and h["Content-Range"].startswith("bytes 0-99/")
assert call(f"/api/runs/{rid}/file/meta.json")[0] == 404  # only whitelisted files are served
assert len(json.loads(call("/api/library")[1])) == 1
assert call(f"/api/runs/{rid}", method="DELETE")[0] == 200 and call(f"/api/runs/{rid}")[0] == 404
srv.shutdown()
print("ok")
