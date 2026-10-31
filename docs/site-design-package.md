# Showcase site: design package

Audience: hackathon judges and reviewers. One call to action: **see the code** (GitHub).
Hero source: drawn live in the browser from real physics (no video, no generator).
Style: the user's "midnight observatory" reference, adapted to this subject.

## 1. Brand premise

**Prediction.** Anyone can fit a curve to frames they have seen. The site sells one idea: this system finds a law
nobody gave it, then predicts the frames it has never seen, and tries to break its own answer. Every section serves
that idea, and every number on the page came out of the real pipeline.

## 2. Palette

```css
:root{
  --canvas:#070708;        /* near-black, from the reference */
  --panel:#0e0e11;         /* the rare raised surface */
  --accent:#1954ec;        /* cobalt: the LAW and only the law (its curve, its forecast, its numbers' arcs) */
  --accent-hover:#3d72ff;
  --accent-muted:#1954ec33;
  --text-secondary:#8f8f93;
  --text-primary:#ffffff;  /* also the MEASURED points: white dots, achromatic */
}
```
Deviation, said out loud: the app uses green for measured and magenta for the law. The reference allows one chromatic
voice, so here measured is white and the law is cobalt. The meaning stays one colour each.

## 3. Type

- Display: **Cormorant Garamond 300** (high-contrast serif at whisper weight; the reference's Darius substitute).
- Body and UI: **Geist 300 / 400 / 500**.
- Data and micro-labels: **Geist Mono 400**, uppercase labels tracked 0.4em at 10 to 11px.

## 4. Hero band map (the drop)

Scroll drives time. A ball falls down the right column (scroll down = falling down). White dots mark each measured frame.
At 70% of the fall the cobalt law curve continues below the ball into frames not yet "seen". The ball lands on the cobalt
cross the law predicted.

| Band | Range | Physics moment | Copy (verbatim) | Entrance |
|---|---|---|---|---|
| 1 | 0.00 to 0.22 | ball at the top, still | "Drop anything in front of a phone." | settled on load, word rise |
| 2 | 0.24 to 0.46 | falling, white dots stack | "It measures every frame." | drift-down per word |
| 3 | 0.48 to 0.68 | candidate curves flicker, settle on t² | "It finds the law. Nobody told it which." | scatter-assemble |
| 4 | 0.70 to 0.86 | cobalt curve runs ahead of the ball | "Then it predicts what it has not seen." | approach-from-depth |
| 5 | 0.88 to 1.00 | ball lands on the cross | settle: "g = 9.808 ± 0.002 m/s²" / "Found, not given." / CTA | staged rise |

## 5. Static hero (reduced motion)

The landed frame drawn once: full trajectory, cobalt law, the cross. Headline "Found, not given.", the g readout,
subline "A phone video in. A law out, with error bars, tested on frames it never saw.", CTA "See the code".

## 6. Below the fold

1. **Proof** (circle indicators, all real): 67 laws tried on the drop · g within 0.02% of 9.81 · 6 test suites passing ·
   0 formulas given to it.
2. **How it works** (a real sequence, so numbered): Look, Track, Discover, Try to break it, Remember.
3. **It tries to break its own law** (the interactive moment): press and hold "Split the clip". The pendulum's two halves
   are refitted; the frequency reads 4.414 then 4.417 (6.9 sigma apart) and the verdict turns to "Incomplete".
   Enacts the premise: the visitor performs the self-test. Reduced motion: final state shown.
4. **Questions judges ask** (FAQ):
   - "Is anything hardcoded?" No formula families. A search composes laws from generic terms, guided by the data's own
     mean, slope and frequency; the model can propose any other formula on top.
   - "Does the model just recite textbook formulas?" It can't win that way: every law is scored on the 30% of frames it
     never saw, in code, never by the model's say-so.
   - "Is running model-written maths safe?" Each formula is parsed and checked before it runs: arithmetic and a short list
     of functions only, no attributes, no builtins. An independent review tried to break it; the two holes it found are
     closed and tested.
   - "Has it run on real footage?" Not yet. Everything on this page comes from rendered clips with known physics, which is
     how the answers can be checked. Real clips are the next step.
5. **Close**: "See the code" (GitHub) + the one-line run command.
6. **Footer**: name, mark, the honesty line.

## 7. Vector layer

- Fixed background: a slow particle drift (dots in the cobalt gradient) on the right, 60 s cycle, paused off-screen and
  under reduced motion.
- Hairline section dividers (white 12%).
- Circle indicators: SVG arcs that draw on entrance.

## 8. Engineering

One canvas driven by scroll progress with a dt-normalised lerp that rests when converged; band opacity with smoothstep
plateaus; delta-gated DOM writes; legibility scrims behind hero bands; reduced motion live in both directions; complete
with JavaScript off (static hero HTML is the default markup). No video, so no Blob loader and no ffmpeg.

## 9. Copy gate

Every line above ships verbatim. Zero em dashes, zero stock words, body sweep for AI tells before anyone sees it.
