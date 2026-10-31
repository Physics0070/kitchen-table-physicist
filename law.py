"""Find the law behind a tracked trajectory, with error bars, and propose the next experiment.

  python law.py track.csv --note "keys on a ~25 cm charger cable"
  python law.py track40.csv --note "same pendulum, 40 cm" --verify fit.json
  python law.py track.csv --offline          # symbolic search only, no API key needed
"""
import argparse, ast, csv, json, os, re, warnings
import numpy as np
from scipy.optimize import curve_fit

SPLIT = 0.7  # fit on the first 70% of samples, score on the unseen rest
NS = {k: getattr(np, k) for k in ("sin", "cos", "exp", "sqrt", "log", "tanh", "abs", "pi")}
SAFE = re.compile(r"^[\w\s.+\-*/(),]+$", re.ASCII)
META = {"t", "px", "py", "k"}  # CSV columns that are not measured coordinates


def load(path):
    rows = list(csv.DictReader(open(path)))
    return {k: np.array([float(r[k]) for r in rows]) for k in rows[0]}


def axes(data):
    return [k for k in data if k not in META and not re.match(r"p[xy]\d+$", k)]


NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Load, ast.Constant,
         ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd)


def compile_law(expr, params):
    # Model-written code: ASCII whitelist, then only arithmetic, whitelisted calls and names in the
    # syntax tree (no attributes, so no ndarray methods), no builtins.
    if not SAFE.match(expr) or "__" in expr:
        raise ValueError("expression not allowed")
    tree = ast.parse(expr, mode="eval")
    for n in ast.walk(tree):
        if not isinstance(n, NODES):
            raise ValueError(f"{type(n).__name__} not allowed")
        if isinstance(n, ast.Constant):
            if type(n.value) not in (int, float):
                raise ValueError("only numbers allowed")
            n.value = float(n.value)  # float powers overflow with an error; int powers like 9**9**9 hang
        if isinstance(n, ast.Call) and (not isinstance(n.func, ast.Name) or n.func.id not in NS or n.keywords):
            raise ValueError("only calls to " + " ".join(NS) + " allowed")
    unknown = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} - set(NS) - set(params) - {"t"}
    if unknown:
        raise ValueError(f"unknown names {sorted(unknown)}")
    code = compile(tree, "<law>", "eval")
    return lambda t, *p: eval(code, {"__builtins__": {}, **NS, "t": t, **dict(zip(params, p))}) * np.ones_like(t)


def _curve(f, t, y, p0, maxfev=20000):
    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore")
        popt, pcov = curve_fit(f, t, y, p0=p0, maxfev=maxfev)
    return popt, pcov


def fit(data, axis, expr, params, p0=None, maxfev=20000):
    """Fit on the first SPLIT of samples. Returns params +/- sigma, AIC/BIC on the fit part,
    RMSE and a BIC-style score on the unseen part (lower score = better law)."""
    try:
        f = compile_law(expr, params)
        t, y = data["t"], data[axis]
        n = int(len(t) * SPLIT)
        popt, pcov = _curve(f, t[:n], y[:n], p0 or [1.0] * len(params), maxfev)
    except Exception as e:
        return {"error": str(e)}
    with np.errstate(all="ignore"):
        r = f(t, *popt) - y
    if not np.all(np.isfinite(r)):
        return {"error": "law diverges on this data"}
    mse = lambda s: float(np.mean(r[s] ** 2)) + 1e-300
    k, nh = len(params), len(t) - n
    sig = np.sqrt(np.abs(np.diag(pcov)))
    ok = bool(np.all(np.isfinite(pcov)))
    return {"expr": expr, "params": dict(zip(params, map(float, popt))),
            "sigma": {p: float(s) if np.isfinite(s) else None for p, s in zip(params, sig)},
            "cov": pcov.tolist() if ok else None,
            "train_rmse": mse(slice(0, n)) ** 0.5, "holdout_rmse": mse(slice(n, None)) ** 0.5,
            "aic": n * np.log(mse(slice(0, n))) + 2 * k, "bic": n * np.log(mse(slice(0, n))) + k * np.log(n),
            "score": nh * np.log(mse(slice(n, None))) + k * np.log(nh)}


def derive(expr, res):
    """Value +/- sigma of any expression in a fitted law's params (e.g. g = L*w**2), sandboxed."""
    names, p = list(res["params"]), np.array(list(res["params"].values()))
    f = compile_law(expr, names)
    val = lambda q: float(f(np.zeros(1), *q)[0])
    v = val(p)
    if res.get("cov") is None:
        return v, None
    g = np.array([(val(p + h * np.eye(len(p))[i]) - v) / h
                  for i, h in enumerate(1e-6 * np.maximum(np.abs(p), 1e-3))])
    return v, float(np.sqrt(max(g @ np.array(res["cov"]) @ g, 0)))


def falsify(data, axis, res, z=3.0):
    """Try to break a law: refit it on each half of the clip. A true law keeps its constants;
    a constant that drifts by more than z sigma means the law is missing something."""
    names, p0 = list(res["params"]), list(res["params"].values())
    f, t, y = compile_law(res["expr"], names), data["t"], data[axis]
    h = len(t) // 2
    try:
        (a, ca), (b, cb) = _curve(f, t[:h], y[:h], p0), _curve(f, t[h:], y[h:], p0)
    except Exception as e:
        return {"verdict": f"could not refit halves: {e}", "drift": []}
    s = np.sqrt(np.abs(np.diag(ca)) + np.abs(np.diag(cb))) + 1e-300
    drift = [{"param": n, "first": float(x), "second": float(w), "z": float(abs(x - w) / q)}
             for n, x, w, q in zip(names, a, b, s) if abs(x - w) / q > z]
    return {"verdict": "survived" if not drift else "FALSIFIED: " + ", ".join(d["param"] for d in drift) + " drift",
            "drift": drift}


# Symbolic search: sums of generic building blocks, grown greedily from the residual.
# Guesses come from the data (mean, slope, FFT peak), never from the expected answer.
TERMS = (("{}", ("mean",)), ("{}*t", ("slope",)), ("{}*t**2", (0.0,)),
         ("{}*cos({}*t+{})", ("amp", "w", "phase")), ("{}*exp(-{}*t)", ("amp", "rate")))
MODS = (("({})*exp(-{}*t)", ("rate",)),)  # wrap an existing term: decay, damping


def _seeds(t, r):
    dt = np.median(np.diff(t))
    spec = np.abs(np.fft.rfft(r - r.mean()))
    w = 2 * np.pi * np.fft.rfftfreq(len(r), dt)[1:][spec[1:].argmax()] if len(r) > 4 else 1.0
    return {"mean": float(r.mean()), "slope": float(np.polyfit(t, r, 1)[0]),
            "amp": float(r.std() * 2 ** 0.5) or 1e-3, "w": float(w), "rate": 1 / float(t[-1] - t[0] or 1)}


def _starts(base, guess, s):
    phases = (0, np.pi / 2, np.pi, -np.pi / 2) if "phase" in guess else (0,)
    return [base + [ph if g == "phase" else s[g] if isinstance(g, str) else g for g in guess] for ph in phases]


def discover(data, axis, depth=4, beam=4, max_terms=4):
    """Beam search over laws. Beam kept by BIC on the fit part; final rank by holdout score."""
    t, y = data["t"], data[axis]
    n = int(len(t) * SPLIT)
    seen, done = set(), []

    def run(terms, names, starts):
        key = tuple(sorted(re.sub(r"c\d+", "c", s) for s in terms))
        if key in seen:
            return None
        seen.add(key)
        rs = [fit(data, axis, " + ".join(terms), names, p, maxfev=3000) for p in starts]
        best = min(rs, key=lambda r: r.get("train_rmse", np.inf))
        if "error" in best:
            return None
        best["terms"] = terms
        done.append(best)
        return best

    frontier = [run(["c0"], ["c0"], [[float(y[:n].mean())]])]
    for _ in range(depth):
        kids = []
        for par in filter(None, frontier):
            terms, names, p = par["terms"], list(par["params"]), list(par["params"].values())
            s = _seeds(t[:n], y[:n] - compile_law(par["expr"], names)(t[:n], *p))
            new = lambda k: [f"c{len(names) + i}" for i in range(k)]
            if len(terms) < max_terms:
                for tmpl, guess in TERMS:
                    nn = new(len(guess))
                    kids.append(run(terms + [tmpl.format(*nn)], names + nn, _starts(p, guess, s)))
            for tmpl, guess in MODS:
                for j, term in enumerate(terms):
                    nn = new(len(guess))
                    kids.append(run(terms[:j] + [tmpl.format(term, *nn)] + terms[j + 1:], names + nn, _starts(p, guess, s)))
        frontier = sorted(filter(None, kids), key=lambda r: r["bic"])[:beam]
        if not frontier:
            break
    return sorted(done, key=lambda r: r["score"])


def brief(r):
    return {k: v for k, v in r.items() if k not in ("cov", "terms")}


TOOLS = [{"type": "function", "function": {
    "name": "search",
    "description": "Automatic symbolic search over sums of terms (constants, powers of t, waves, decays, damped terms) on one axis. Returns the top laws ranked by score on the unseen last 30%.",
    "parameters": {"type": "object", "required": ["axis"], "properties": {"axis": {"type": "string"}}}}},
    {"type": "function", "function": {
    "name": "fit",
    "description": "Least-squares fit of any law you propose on the first 70% of samples; returns params +/- sigma, AIC/BIC, holdout RMSE and score (lower is better) on the unseen last 30%.",
    "parameters": {"type": "object", "required": ["axis", "expr", "params"], "properties": {
        "axis": {"type": "string"},
        "expr": {"type": "string", "description": "numpy expression in t, e.g. A*exp(-b*t)*cos(w*t+p)+c. Allowed: sin cos exp sqrt log tanh abs pi"},
        "params": {"type": "array", "items": {"type": "string"}},
        "p0": {"type": "array", "items": {"type": "number"}, "description": "initial guesses, same order as params"}}}}}]

SYSTEM = """You are an experimental physicist agent. You get trajectories tracked from a phone video (metres, seconds, y points up; columns x,y for object 0, x1,y1 for object 1, ...).
Find the law that best predicts the UNSEEN part of the data. Run search on every axis that moves, then propose your own forms with fit, including ones search cannot express. The holdout score decides, never your expectation; report terms you did not expect (damping, drift, offsets).
Every number you report must be an expression in the final law's params so code can compute it with error bars; never do arithmetic yourself.
When done, reply with ONLY this JSON:
{"law": "one line in words", "axis": "...", "expr": "...", "params": {"name": value},
 "derived": [{"name": "g", "expr": "0.30*c3**2", "unit": "m/s^2", "meaning": "what it is physically"}],
 "explanation": "2-3 plain sentences for a curious non-physicist",
 "rival": "the strongest competing law and where it disagrees with yours",
 "next_experiment": "the household experiment that best tells your law from its rival",
 "prediction": {"quantity": "...", "expr": "expression in params giving the number to expect", "unit": "...", "measure": "how to read it off the next clip"},
 "measured": null}
If a prediction to verify is given, set "measured" to {"expr": "expression in THIS law's params for that same quantity", "unit": "..."}."""


def summary(d, note, verify):
    idx = np.linspace(0, len(d["t"]) - 1, min(40, len(d["t"]))).astype(int)
    ax = axes(d)
    table = "\n".join(",".join(f"{d[a][i]:.4f}" for a in ["t"] + ax) for i in idx)
    stats = ", ".join(f"{a}: {d[a].min():.4f}..{d[a].max():.4f} m" for a in ax)
    pred = f"Prediction to verify: {json.dumps(verify)}\n" if verify else ""
    return (f"Setup: {note}\n{len(d['t'])} samples over {d['t'][-1] - d['t'][0]:.2f} s. {stats}\n"
            f"{pred}Sample ({','.join(['t'] + ax)}):\n{table}")


def agent(data, note, verify, turns):
    from openai import OpenAI
    client = OpenAI(base_url=os.environ.get("MODEL_BASE_URL", "https://api.meta.ai/v1"), api_key=os.environ["MODEL_API_KEY"])
    model = os.environ.get("MUSE_MODEL", "muse-spark-1.3")
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": summary(data, note, verify)}]
    for _ in range(turns):
        m = client.chat.completions.create(model=model, messages=msgs, tools=TOOLS).choices[0].message
        msgs.append(m.model_dump(exclude_none=True))
        if not m.tool_calls:
            break
        for c in m.tool_calls:
            a = json.loads(c.function.arguments)
            if a.get("axis") not in data:
                r = {"error": f"axis must be one of {axes(data)}"}
            elif c.function.name == "search":
                r = [brief(x) for x in discover(data, a["axis"])[:5]]
            else:
                r = brief(fit(data, a["axis"], a["expr"], a["params"], a.get("p0")))
            print(f"{c.function.name} {a}\n    -> {str(r)[:300]}")
            msgs.append({"role": "tool", "tool_call_id": c.id, "content": json.dumps(r)})
    else:
        raise SystemExit("agent ran out of turns")
    text = m.content or ""
    return json.loads(text[text.find("{"): text.rfind("}") + 1])


def offline(data):
    """No model: search every axis, keep the one whose motion the best law explains most."""
    if not axes(data):
        raise SystemExit("no coordinate columns in the CSV")
    ax = max(axes(data), key=lambda a: data[a].std())
    found = discover(data, ax)
    if not found:
        raise SystemExit(f"no law fits {ax}(t)")
    best = found[0]
    return {"law": best["expr"], "axis": ax, "expr": best["expr"], "params": best["params"],
            "derived": [], "explanation": None, "prediction": None, "measured": None}


def finish(data, r, verify=None, tol=0.05):
    """Recompute everything the model claimed, in code: params +/- sigma, derived numbers, verdicts."""
    res = fit(data, r["axis"], r["expr"], list(r["params"]), list(r["params"].values()))
    if "error" in res:
        raise SystemExit(f"final law does not fit: {res['error']}")
    r.update({k: res[k] for k in ("params", "sigma", "cov", "train_rmse", "holdout_rmse", "aic", "bic", "score")})

    def num(d):
        try:
            d["value"], d["sigma"] = derive(d["expr"], res)
        except Exception as e:
            d["error"] = str(e)
        return d
    r["derived"] = [num(d) for d in r.get("derived") or []]
    if r.get("prediction") and r["prediction"].get("expr"):
        num(r["prediction"])
    if verify and r.get("measured"):
        m, p = num(r["measured"]), verify
        if "value" in m and p.get("value"):
            rel = abs(m["value"] - p["value"]) / abs(p["value"])
            m.update(predicted=p["value"], rel_error=rel, verdict="CONFIRMED" if rel <= tol else "REFUTED")
    r["falsify"] = falsify(data, r["axis"], res)
    r["split"] = SPLIT
    return r


def pm(v, s):
    return f"{v:.4g} +/- {s:.2g}" if s is not None else f"{v:.4g}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--note", default="unknown setup")
    ap.add_argument("--verify", help="fit.json of an earlier run whose prediction this clip tests")
    ap.add_argument("--offline", action="store_true", help="symbolic search only, no API")
    ap.add_argument("--tol", type=float, default=0.05, help="relative error allowed for a prediction to count")
    ap.add_argument("-o", "--out", default="fit.json")
    ap.add_argument("--turns", type=int, default=16)
    a = ap.parse_args()

    data = load(a.csv)
    verify = (json.load(open(a.verify)).get("prediction") or None) if a.verify else None
    r = offline(data) if a.offline else agent(data, a.note, verify, a.turns)
    r = finish(data, r, verify, a.tol)
    r.update(note=a.note, csv=a.csv)
    json.dump(r, open(a.out, "w"), indent=2)

    print(f"\nLAW  {r['axis']}(t) = {r['expr']}   holdout RMSE {r['holdout_rmse']:.2g} m")
    for k, v in r["params"].items():
        print(f"     {k} = {pm(v, r['sigma'][k])}")
    for d in r["derived"]:
        print(f"     {d['name']} = {pm(d['value'], d['sigma'])} {d.get('unit', '')}" if "value" in d else f"     {d['name']}: {d['error']}")
    if r.get("prediction") and "value" in r["prediction"]:
        p = r["prediction"]
        print(f"NEXT {r.get('next_experiment')}\n     predict {p['quantity']} = {pm(p['value'], p['sigma'])} {p.get('unit', '')}")
    if r.get("measured") and "verdict" in r["measured"]:
        m = r["measured"]
        print(f"TEST measured {pm(m['value'], m['sigma'])} vs predicted {m['predicted']:.4g}: {m['verdict']} ({m['rel_error']:.1%} off)")
    print(f"SELF-TEST {r['falsify']['verdict']}\n-> {a.out}")


if __name__ == "__main__":
    main()
