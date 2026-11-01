# Council: how to serve the landing page and the live demo

**Question.** Page 1 is a 3D landing that explains the project (static, deployable). Page 2 is the live demo bench (needs
`app.py`, Python, numpy/scipy/opencv, optionally a model key). How should they be served and linked?

Run as a lean council: five advisors in parallel, the chair's synthesis inline, no separate peer-review round.

| Advisor | Position |
|---|---|
| Contrarian | A plus a labelled recording. Warned that probing `/api/health` to detect the mode is fragile (404 noise, wrong-CTA flash) and that `/lab` must fail clearly if dependencies are missing. |
| First Principles | Wrong question: the goal is time-to-seeing-a-real-result for a judge who won't install anything. Ship the real bench replaying saved pipeline output, not a video. |
| Expansionist | Same: one bench, two data sources (live API or baked JSON). Add more canned experiments; Codespaces/Docker later. |
| Outsider | The first screen must say what goes in and what comes out, and that the live demo runs on your machine. Never show a dead button. |
| Executor | A plus a fallback: `/` landing, `/lab` bench, sample clip in one click, test from a fresh clone. |

## Verdict

- **Agreed:** `app.py` serves the landing at `/` and the bench at `/lab/`; the duplicate intro goes; judges must see a
  working demo without installing anything; a sample runs in one click.
- **Clash:** recorded video vs replaying the real bench; detecting the mode by probing vs not.
- **Decision:** one landing whose demo link is simply `lab/`. The bench decides its mode from `mode.js`: the static
  file says `LIVE = false` and replays recorded runs (`record_runs.py`), and `app.py` answers the same path with
  `LIVE = true`. No probing, no console errors, one copy of the bench. Recorded runs are labelled as such.
- **Deferred:** more canned experiments (needs real footage), Codespaces/Docker, a missing-dependency page for `/lab`.
