"""Personal library of discovered laws: remembers them, searches them, and re-tests them on new clips.

  python library.py add fit.json
  python library.py search pendulum damping
  python library.py check track40.csv --about pendulum --mark   # does this clip break a law I believed?
"""
import argparse, datetime, json, os
from law import load, fit, falsify, discover

LIB = os.environ.get("LAW_LIBRARY", "laws.jsonl")
KEEP = ("law", "axis", "expr", "params", "sigma", "derived", "explanation", "next_experiment", "prediction",
        "measured", "falsify", "holdout_rmse", "note", "csv", "report")


def entries():
    return [json.loads(l) for l in open(LIB)] if os.path.exists(LIB) else []


def save(es):
    with open(LIB, "w") as f:
        f.writelines(json.dumps(e) + "\n" for e in es)


def add(r):
    es = entries()
    e = {"id": len(es) + 1, "date": datetime.date.today().isoformat(), **{k: r.get(k) for k in KEEP},
         "status": "falsified by its own clip" if r["falsify"]["verdict"].startswith("FALSIFIED") else "standing"}
    if (r.get("measured") or {}).get("verdict"):
        e["tested_prediction"] = r["measured"]["verdict"]
    save(es + [e])
    return e


def search(words):
    ws = [w.lower() for w in words]
    return [e for e in entries() if all(w in json.dumps(e).lower() for w in ws)]


def check(data, laws, ratio=2.0):
    """Refit each old law's form on new data. It breaks if it predicts the unseen part much worse
    than the best law found fresh on this clip, or if it fails its own self-test here."""
    axes_best = {}
    out = []
    for e in laws:
        if e["axis"] not in data:
            continue
        if e["axis"] not in axes_best:
            axes_best[e["axis"]] = discover(data, e["axis"])[0]
        best, r = axes_best[e["axis"]], fit(data, e["axis"], e["expr"], list(e["params"]), list(e["params"].values()))
        if "error" in r:
            out.append({"id": e["id"], "broken": True, "why": r["error"]})
            continue
        worse = r["holdout_rmse"] / best["holdout_rmse"]
        fz = falsify(data, e["axis"], r)["verdict"]
        out.append({"id": e["id"], "broken": worse > ratio or fz != "survived", "worse": worse, "self_test": fz,
                    "why": f"holdout error {worse:.1f}x the best fresh law ({best['expr']}); self-test: {fz}"})
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("add").add_argument("fit_json")
    sub.add_parser("search").add_argument("words", nargs="*")
    c = sub.add_parser("check")
    c.add_argument("csv")
    c.add_argument("--about", nargs="*", default=[], help="only laws matching these words")
    c.add_argument("--ratio", type=float, default=2.0, help="holdout error vs best fresh law that counts as broken")
    c.add_argument("--mark", action="store_true", help="record broken laws in the library")
    a = ap.parse_args()

    if a.cmd == "add":
        e = add(json.load(open(a.fit_json)))
        print(f"law #{e['id']} saved ({e['status']}) -> {LIB}")
    elif a.cmd == "search":
        for e in search(a.words):
            print(f"#{e['id']} {e['date']} [{e['status']}] {e['axis']}(t) = {e['expr']}  | {e.get('law')} | {e.get('note')}")
    else:
        laws = search(a.about)
        res = check(load(a.csv), [e for e in laws if e["status"] == "standing"], a.ratio)
        for r in res:
            print(f"#{r['id']} {'BROKEN' if r['broken'] else 'holds '}  {r['why']}")
        if a.mark:
            es, broken = entries(), {r["id"] for r in res if r["broken"]}
            for e in es:
                if e["id"] in broken:
                    e["status"] = f"broken by {a.csv}"
            save(es)


if __name__ == "__main__":
    main()
