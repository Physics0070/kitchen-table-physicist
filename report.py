"""One-page lab report: the law, its error bars, the self-test, the prediction, and the figure.

  python report.py fit.json track.csv [--conserved conserved.json] -o report.html
"""
import argparse, base64, html, io, json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from law import compile_law, load, pm

INK, MUTED, GRID, DATA, LAW, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6", "#eb6834", "#fcfcfb"


def figure(d, r):
    t, y = d["t"], d[r["axis"]]
    f = compile_law(r["expr"], list(r["params"]))
    yhat = f(t, *r["params"].values())
    ts = t[int(len(t) * r["split"])]
    fig, (a, b) = plt.subplots(2, 1, figsize=(9, 5.2), sharex=True, gridspec_kw={"height_ratios": [3, 1]}, facecolor=SURFACE)
    for ax in (a, b):
        ax.set_facecolor(SURFACE)
        ax.axvspan(ts, t[-1], color=GRID, alpha=0.6, lw=0)
        ax.grid(color=GRID, lw=0.6)
        ax.tick_params(colors=MUTED, labelsize=9)
        for s in ax.spines.values():
            s.set_visible(False)
    a.plot(t, y, "o", ms=2.5, color=DATA, label="measured")
    a.plot(t, yhat, lw=2, color=LAW, label="law")
    a.text(ts, a.get_ylim()[1], "  unseen: predicted, not fitted", va="top", color=MUTED, fontsize=9)
    a.set_ylabel(f"{r['axis']} (m)", color=MUTED)
    a.legend(frameon=False, loc="lower left", bbox_to_anchor=(0, 1), ncol=2, fontsize=9, labelcolor=INK)
    b.plot(t, (y - yhat) * 1000, lw=1, color=DATA)
    b.set_ylabel("residual (mm)", color=MUTED, fontsize=9)
    b.set_xlabel("t (s)", color=MUTED)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, facecolor=SURFACE)
    return base64.b64encode(buf.getvalue()).decode()


def page(r, img, conserved):
    e = lambda s: html.escape(str(s)) if s is not None else ""
    rows = "".join(f"<tr><td>{e(k)}</td><td>{e(pm(v, r['sigma'][k]))}</td></tr>" for k, v in r["params"].items())
    rows += "".join(f"<tr><td>{e(x['name'])}</td><td>{e(pm(x['value'], x['sigma']))} {e(x.get('unit'))}"
                    f"<small>{e(x.get('meaning'))}</small></td></tr>" for x in r.get("derived", []) if "value" in x)
    p, m, fz = r.get("prediction") or {}, r.get("measured") or {}, r["falsify"]
    block = lambda h, body: f"<section><h2>{h}</h2>{body}</section>" if body else ""
    pred = (f"<p><b>{e(p['quantity'])} = {e(pm(p['value'], p['sigma']))} {e(p.get('unit'))}</b></p><p>{e(r.get('next_experiment'))}</p>"
            f"<p class=muted>{e(p.get('measure'))}</p>") if "value" in p else ""
    test = (f"<p class=verdict>{e(m['verdict'])}: measured {e(pm(m['value'], m['sigma']))}, predicted {m['predicted']:.4g} "
            f"({m['rel_error']:.1%} off)</p>") if "verdict" in m else ""
    cons = "".join(f"<li><code>{e(c['law'])}</code> <span class=muted>within {c['spread']:.1%}</span></li>" for c in conserved)
    drift = "".join(f"<li>{e(x['param'])}: {x['first']:.4g} in the first half vs {x['second']:.4g} in the second ({x['z']:.0f}σ)</li>" for x in fz["drift"])
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Lab report</title><style>
:root{{--bg:#fcfcfb;--ink:#0b0b0b;--muted:#52514e;--line:#e4e3df;--accent:#eb6834}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1a1a19;--ink:#f0efec;--muted:#c3c2b7;--line:#33332f;--accent:#d95926}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}
main{{max-width:760px;margin:0 auto;padding:48px 16px}}
h1{{font-size:28px;line-height:1.2;margin:0 0 8px}} h2{{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:40px 0 8px}}
code,.law{{font-family:ui-monospace,Consolas,monospace}} .law{{font-size:18px;padding:16px;border-left:3px solid var(--accent);background:color-mix(in srgb,var(--line) 40%,transparent);overflow-x:auto}}
.muted,small{{color:var(--muted)}} small{{display:block;font-size:13px}}
table{{border-collapse:collapse;width:100%}} td{{padding:8px 0;border-bottom:1px solid var(--line);vertical-align:top}} td:first-child{{font-family:ui-monospace,monospace;width:30%}}
img{{width:100%;border-radius:8px;margin-top:24px}} .verdict{{font-weight:600}}
</style></head><body><main>
<p class=muted>{e(r.get('note'))}</p><h1>{e(r.get('law'))}</h1>
<div class=law>{e(r['axis'])}(t) = {e(r['expr'])}</div>
<p class=muted>Fitted on the first {r['split']:.0%} of the clip; error on the unseen rest {r['holdout_rmse'] * 1000:.2g} mm.</p>
<img src="data:image/png;base64,{img}" alt="Measured {e(r['axis'])} against time with the fitted law; the shaded part was predicted, not fitted.">
{block("What it means", f"<p>{e(r.get('explanation'))}</p>" if r.get('explanation') else "")}
{block("Constants, with one-sigma error bars", f"<table>{rows}</table>")}
{block("Trying to break it", f"<p class=verdict>{e(fz['verdict'])}</p><p class=muted>Refitted on each half of the clip separately; a true law keeps its constants.</p><ul>{drift}</ul>")}
{block("Conserved", f"<ul>{cons}</ul>")}
{block("Rival law", f"<p>{e(r.get('rival'))}</p>" if r.get('rival') else "")}
{block("Next experiment", pred)}
{block("Prediction check", test)}
</main></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fit_json")
    ap.add_argument("csv")
    ap.add_argument("--conserved")
    ap.add_argument("-o", "--out", default="report.html")
    a = ap.parse_args()
    r, d = json.load(open(a.fit_json)), load(a.csv)
    cons = json.load(open(a.conserved)) if a.conserved else []
    open(a.out, "w", encoding="utf-8").write(page(r, figure(d, r), cons))
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
