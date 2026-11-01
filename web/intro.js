"use strict";
// The app's intro: the showcase's 3D drop, scrubbed by scroll, then the bench. It runs only while the intro is on screen.
// ponytail: band timing mirrors site/assets/site.js; share one module if a third page ever needs it.
(() => {
  const D = window.KTP && window.KTP.drop, sec = document.getElementById("intro");
  if (!D || !sec) { if (sec) sec.hidden = true; return; }
  const root = document.documentElement, RM = matchMedia("(prefers-reduced-motion: reduce)");
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const sstep = (p, a, b) => { const t = clamp((p - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  const len = (mm) => (mm < 10 ? `${mm.toFixed(1)} mm` : mm < 1000 ? `${Math.round(mm / 10)} cm` : `${(mm / 1000).toFixed(1)} m`);
  const n = D.t.length, tEnd = D.t[n - 1], tSplit = D.t[Math.floor(n * 0.7)];
  const timeAt = (p) => p < 0.03 ? 0 : p < 0.44 ? tSplit * (p - 0.03) / 0.41 : p < 0.70 ? tSplit : p < 0.89 ? tSplit + (tEnd - tSplit) * (p - 0.70) / 0.19 : tEnd;

  document.getElementById("ig").textContent = `g = ${D.g.toFixed(3)} ± ${D.sg.toFixed(3)} m/s²`;
  const k = (D.expr.match(/c\d+/g) || []).length;
  const list = document.getElementById("irivals");
  D.rivals.concat([{ kind: `t², ${k} constants`, mm: D.holdout_mm, win: true }]).forEach((r) => {
    const li = document.createElement("li");
    li.className = r.win ? "winner" : "";
    li.append(Object.assign(document.createElement("span"), { textContent: r.kind }), Object.assign(document.createElement("span"), { textContent: `${len(r.mm)} off` }));
    list.append(li);
  });
  const lis = [...list.children];
  const bands = [...sec.querySelectorAll(".iband")].map((el) => ({ el, a: +el.dataset.a, b: +el.dataset.b, o: -1, y: -1 }));

  let gl = window.KTP3D || null, target = 0, shown = 0, raf = 0, last = 0, last3d = 0, on = true, t0 = performance.now();
  const progress = () => { const r = sec.getBoundingClientRect(); return clamp(-r.top / (r.height - innerHeight), 0, 1); };

  function paint(p, now) {
    bands.forEach((b, i) => {
      const f = Math.min(0.02, (b.b - b.a) / 3);
      let o = (i === 0 ? 1 : sstep(p, b.a, b.a + f)) * (i === bands.length - 1 ? 1 : 1 - sstep(p, b.b - f, b.b));
      if (i === 0) o = Math.min(o, sstep(now - t0, 0, 900));
      const y = (1 - (i === 0 ? sstep(now - t0, 0, 900) : sstep(p, b.a, b.a + 0.025))) * 26;
      if (Math.abs(o - b.o) > 0.004) { b.el.style.opacity = o.toFixed(3); b.o = o; }
      if (Math.abs(y - b.y) > 0.2) { b.el.style.translate = `0 ${y.toFixed(1)}px`; b.y = y; }
      b.el.toggleAttribute("aria-hidden", o < 0.5);
    });
    lis.forEach((li, q) => {
      const a0 = 0.47 + q * 0.03, win = li.classList.contains("winner");
      li.classList.toggle("on", win ? p >= 0.585 : p >= a0 && p < a0 + 0.022);
      li.classList.toggle("out", !win && p >= a0 + 0.022);
    });
  }

  function frame(now) {
    raf = 0;
    const dt = Math.min(100, now - (last || now)); last = now;
    shown += (target - shown) * (1 - Math.pow(1 - 0.14, dt / 16.667));
    let busy = Math.abs(target - shown) > 0.0004 || now - t0 < 950;
    if (!busy) shown = target;
    if (gl && (busy || now - last3d > 33)) { gl.render(shown, timeAt(shown), now); last3d = now; }
    paint(shown, now);
    if (on && !document.hidden) raf = requestAnimationFrame(frame); else last = 0;  // the camera breathes while in view
  }
  const wake = () => { if (!raf && on && !document.hidden) raf = requestAnimationFrame(frame); };

  function still() {  // reduced motion: the landed frame, every line readable, no scrub
    root.classList.add("intro-still");
    bands.forEach((b) => { b.el.style.opacity = ""; b.el.style.translate = ""; b.el.removeAttribute("aria-hidden"); });
    if (gl) gl.render(1, tEnd, 0);
  }
  function mode() { if (RM.matches) { still(); cancelAnimationFrame(raf); raf = 0; } else { root.classList.remove("intro-still"); target = shown = progress(); wake(); } }

  addEventListener("scroll", () => { target = progress(); wake(); }, { passive: true });
  addEventListener("ktp3d", () => { gl = window.KTP3D; RM.matches ? still() : wake(); });
  document.addEventListener("visibilitychange", wake);
  RM.addEventListener("change", mode);
  function where() {  // is any of the intro showing below the header? (a touching edge does not count)
    const was = on;
    on = sec.getBoundingClientRect().bottom > 90;
    if (on !== was) { root.classList.toggle("at-intro", on); if (on) wake(); }
  }
  addEventListener("scroll", where, { passive: true });
  on = !on; where();
  mode();
})();
