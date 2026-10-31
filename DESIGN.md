# Design

**Brief.** A local tool for one curious person with a phone: drop a clip, watch the lab work, read the law.
Job: make "my phone just did science" legible in three seconds, then let them check every number.

**Concepts considered.**
1. *Oscilloscope beside a notebook*: the clip is the scope screen, the reasoning is the notebook. Signature: the forecast. Originality 4, fit 5, feasible 5, portable 2.
2. *Galileo's ramp*: brass and ruled vellum. Fit 3, cliché risk (cream serif), portable 3.
3. *Darkroom contact sheet*: frames as strips. Fit 2: the science is the point, not the film.
Picked 1: the subject already has two inks, measured and predicted, so the identity comes from the data itself.

```
Idea:        The law draws where the object will be next, and the object follows it there.
Metaphor:    a scope screen (traces) next to a lab notebook (reasoning)
Signature:   the forecast: magenta marks run 0.5 s ahead of the green ring; after the 70% line
             the chart's law line is already drawn and the measured dots land on it
Emotion:     "it knows where the bob is going"
Motion verb: settle like a damped swing (fast out, small overshoot, rest)
Screenshot:  frame with green ring, magenta forecast ahead of it, PREDICTING chip, chart below
```

**System.**
- Ground `#EDF0F2`, surface `#F8FAFB`, ink `#10181F`, muted `#56636D`, line `#D3DADF`,
  measured `#0F8A55`, law/accent `#C0177A`. Dark: `#0C1216 / #121A20 / #E4EBEF / #93A0A9 / #23313A / #3DCB86 / #FF5AAE`.
  Green and magenta are information (measured vs law) and are never used for anything else.
- Type: Schibsted Grotesk (UI and headings, tight negative tracking on display), IBM Plex Mono (every number, formula, time).
- Grid: 12 columns, bench = 7 / 5, stacks under 1000 px. Radius 10 px on panels, 999 px on chips.
- Motion: `cubic-bezier(.2,.9,.3,1.12)` 260 ms for panels and toggles; the replay is the idle motion.
  Reduced motion: no autoplay, no overshoot.

**Genericness check.** A default build would be a dark dashboard with cards. Changed: cool paper ground in light mode,
the two data inks as the only colours, the replay as the hero rather than stat tiles.
