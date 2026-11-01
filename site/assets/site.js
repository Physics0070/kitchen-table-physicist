"use strict";
// One clock (a single rAF loop) drives the drop, the hold-to-split figure and the particle field.
// Every number and curve comes from window.KTP, written by site/make_data.py from the real pipeline.
(() => {
  const D = window.KTP, $ = (s) => document.querySelector(s), $$ = (s) => [...document.querySelectorAll(s)];
  const root = document.documentElement, RM = matchMedia("(prefers-reduced-motion: reduce)");
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const sstep = (p, a, b) => { const t = clamp((p - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  const css = (n) => getComputedStyle(root).getPropertyValue(n).trim();
  const fmtLen = (mm) => (mm < 10 ? `${mm.toFixed(1)} mm` : mm < 1000 ? `${Math.round(mm / 10)} cm` : `${(mm / 1000).toFixed(1)} m`);
  if (!D) return;

  /* ---------- real numbers into the page ---------- */
  const dr = D.drop, n = dr.t.length, tEnd = dr.t[n - 1], iSplit = Math.floor(n * 0.7), tSplit = dr.t[iSplit];
  const k = (dr.expr.match(/c\d+/g) || []).length;
  $("#g-readout").innerHTML = `g = <b>${dr.g.toFixed(3)}</b> ± ${dr.sg.toFixed(3)} m/s²`;
  $("#s-tried").textContent = dr.tried;
  $("#s-err").textContent = `${(Math.abs(dr.g - 9.81) / 9.81 * 100).toFixed(2)}%`;
  const rivals = $("#rivals");
  rivals.innerHTML = dr.rivals.map((r) => `<li><span>${r.kind}</span><span>${fmtLen(r.mm)} off</span></li>`).join("")
    + `<li class="winner"><span>t², ${k} constants</span><span>${fmtLen(dr.holdout_mm)} off</span></li>`;
  const rivalLis = [...rivals.children];

  /* ---------- the drop: scroll progress -> fall time ---------- */
  const hero = $(".drop"), cvs = $("#drop"), bands = $$(".band").map((el) => ({ el, a: +el.dataset.a, b: +el.dataset.b, o: -1, y: -1 }));
  const STEP = 8;  // 240 fps track, a flash every 8 frames = 30 flashes a second
  const timeAt = (p) => p < 0.03 ? 0 : p < 0.44 ? tSplit * (p - 0.03) / 0.41 : p < 0.70 ? tSplit : p < 0.89 ? tSplit + (tEnd - tSplit) * (p - 0.70) / 0.19 : tEnd;
  const idx = (t) => clamp(Math.round(t * 240), 0, n - 1);
  let target = 0, shown = 0, scrub = false, last = 0;

  function heroProgress() {
    const r = hero.getBoundingClientRect();
    return clamp(-r.top / (r.height - innerHeight), 0, 1);
  }

  function fit(c) {
    const r = c.getBoundingClientRect(), d = Math.min(2, devicePixelRatio || 1);
    if (c.width !== Math.round(r.width * d) || c.height !== Math.round(r.height * d)) { c.width = Math.round(r.width * d); c.height = Math.round(r.height * d); }
    const g = c.getContext("2d"); g.setTransform(d, 0, 0, d, 0, 0);
    return [g, r.width, r.height];
  }

  function drawDrop(p) {
    const [g, W, H] = fit(cvs);
    g.clearRect(0, 0, W, H);
    const L = Math.max(W * 0.12, 70), R = W * 0.9, T = H * 0.14, B = H * 0.86, tStep = W < 560 ? 0.2 : 0.1;
    const yMax = dr.y[0] + 0.15, yMin = Math.min(...dr.law) - 0.2;
    const X = (t) => L + (t / tEnd) * (R - L), Y = (y) => T + (yMax - y) / (yMax - yMin) * (B - T);
    const rad = clamp(W * 0.011, 6, 11), cob = css("--accent"), cobH = css("--accent-hover");
    const tc = timeAt(p), j = idx(tc);

    // ruler (metres) and time axis: the instrument's own scales
    g.strokeStyle = "rgba(255,255,255,.18)"; g.fillStyle = "rgba(143,143,147,.9)"; g.lineWidth = 1;
    g.font = "400 10px 'Geist Mono', monospace"; g.textAlign = "right"; g.textBaseline = "middle";
    g.beginPath(); g.moveTo(L - 22, T); g.lineTo(L - 22, B); g.stroke();
    for (let m = Math.ceil(yMin * 2) / 2; m <= yMax; m += 0.5) {
      g.beginPath(); g.moveTo(L - 28, Y(m)); g.lineTo(L - 22, Y(m)); g.stroke();
      g.fillText(`${m.toFixed(1)} m`, L - 34, Y(m));
    }
    g.textAlign = "center"; g.textBaseline = "top";
    for (let s = 0; s <= tEnd + 1e-9; s += tStep) g.fillText(`${s.toFixed(1)} s`, X(s), B + 18);

    // the 70% line: fitted on the left, never seen on the right
    if (tc >= tSplit - 1e-6) {
      const a = sstep(p, 0.42, 0.46);
      g.globalAlpha = a; g.setLineDash([2, 5]); g.strokeStyle = "rgba(255,255,255,.35)";
      g.beginPath(); g.moveTo(X(tSplit), T - 30); g.lineTo(X(tSplit), B + 8); g.stroke(); g.setLineDash([]);
      g.textBaseline = "bottom"; g.textAlign = "right"; g.fillText("FITTED", X(tSplit) - 10, T - 16);
      g.textAlign = "left"; g.fillStyle = cobH; g.fillText("NEVER SEEN", X(tSplit) + 10, T - 16); g.globalAlpha = 1;
    }

    const path = (ys, from, to) => { g.beginPath(); for (let i = from; i <= to; i++) i === from ? g.moveTo(X(dr.t[i]), Y(ys[i])) : g.lineTo(X(dr.t[i]), Y(ys[i])); };
    // rival laws: each appears, fails against the flashes, and fades
    dr.rivals.forEach((r, q) => {
      const a0 = 0.47 + q * 0.03, on = sstep(p, a0, a0 + 0.012), off = sstep(p, a0 + 0.022, a0 + 0.03);
      const alpha = on * (1 - 0.85 * off) * (1 - sstep(p, 0.84, 0.9));
      if (alpha <= 0.01) return;
      g.globalAlpha = alpha; g.strokeStyle = "rgba(255,255,255,.55)"; g.lineWidth = 1;
      path(r.y, 0, iSplit); g.stroke();
      g.setLineDash([3, 4]); path(r.y, iSplit, n - 1); g.stroke(); g.setLineDash([]);
      g.globalAlpha = 1;
    });
    // the law: draws itself over the fitted part, then reaches ahead
    const lawIn = sstep(p, 0.585, 0.63), lawOut = sstep(p, 0.63, 0.67);
    if (lawIn > 0) {
      g.strokeStyle = cob; g.lineWidth = 2; path(dr.law, 0, Math.round(iSplit * lawIn)); g.stroke();
    }
    if (lawOut > 0) {
      g.strokeStyle = cobH; g.lineWidth = 1.5; g.setLineDash([5, 5]);
      path(dr.law, iSplit, iSplit + Math.round((n - 1 - iSplit) * lawOut)); g.stroke(); g.setLineDash([]);
    }
    // ghosts: where the law says the ball will be, drawn before it gets there
    const ghostIn = sstep(p, 0.64, 0.71), future = [];
    for (let i = iSplit + STEP; i < n; i += STEP) future.push(i);
    future.push(n - 1);
    future.forEach((i, q) => {
      const a = clamp(ghostIn * future.length - q, 0, 1);
      if (a <= 0) return;
      g.globalAlpha = a; g.strokeStyle = cobH; g.lineWidth = 1.5;
      g.beginPath(); g.arc(X(dr.t[i]), Y(dr.law[i]), rad + 3, 0, 7); g.stroke(); g.globalAlpha = 1;
    });
    if (ghostIn > 0) {  // the predicted landing
      const x = X(tEnd), y = Y(dr.law[n - 1]), s = rad * 2.2;
      g.globalAlpha = ghostIn; g.strokeStyle = cobH; g.lineWidth = 1;
      g.beginPath(); g.moveTo(x - s, y); g.lineTo(x + s, y); g.moveTo(x, y - s); g.lineTo(x, y + s); g.stroke();
      g.fillStyle = cobH; g.textAlign = "right"; g.textBaseline = "top"; g.fillText("PREDICTED LANDING", x - s - 6, y + 8); g.globalAlpha = 1;
    }
    // the flashes: every measured exposure up to now, then the ball itself
    for (let i = 0; i < j; i += STEP) {
      g.fillStyle = "rgba(255,255,255,.62)"; g.beginPath(); g.arc(X(dr.t[i]), Y(dr.y[i]), rad, 0, 7); g.fill();
    }
    g.fillStyle = "#fff"; g.beginPath(); g.arc(X(dr.t[j]), Y(dr.y[j]), rad + 1.5, 0, 7); g.fill();
    g.strokeStyle = "rgba(255,255,255,.25)"; g.beginPath(); g.arc(X(dr.t[j]), Y(dr.y[j]), rad + 8, 0, 7); g.stroke();
  }

  function drawBands(p, now) {
    bands.forEach((b, i) => {
      const f = Math.min(0.02, (b.b - b.a) / 3);
      let o = (i === 0 ? 1 : sstep(p, b.a, b.a + f)) * (i === bands.length - 1 ? 1 : 1 - sstep(p, b.b - f, b.b));
      if (i === 0) o = Math.min(o, sstep(now - t0, 0, 900));  // band one assembles once on load
      const y = (1 - (i === 0 ? sstep(now - t0, 0, 900) : sstep(p, b.a, b.a + 0.025))) * 26;
      if (Math.abs(o - b.o) > 0.004) { b.el.style.opacity = o.toFixed(3); b.o = o; }
      if (Math.abs(y - b.y) > 0.2) { b.el.style.translate = `0 ${y.toFixed(1)}px`; b.y = y; }
      b.el.toggleAttribute("aria-hidden", o < 0.5);
    });
    rivalLis.forEach((li, q) => {
      const a0 = 0.47 + q * 0.03;
      const win = li.classList.contains("winner");
      li.classList.toggle("on", win ? p >= 0.585 : p >= a0 && p < a0 + 0.022);
      li.classList.toggle("out", !win && p >= a0 + 0.022);
      li.classList.toggle("win", win && p >= 0.585);
    });
    root.classList.toggle("scrolled", p > 0.01);
  }

  /* ---------- the self-test figure ---------- */
  const pd = D.pend, sc = $("#split"), out = $("#split-out"), hold = $("#hold");
  let h = 0, holding = false, doneSaid = false;
  // A number line of swing frequency: the first half's estimate and the zone a complete law would keep the second
  // half inside (±3 sigma). Holding fits the second half; its estimate slides to where the data puts it.
  function drawSplit() {
    const [g, W, H] = fit(sc);
    g.clearRect(0, 0, W, H);
    const span = Math.abs(pd.w2 - pd.w1) + 6 * Math.max(pd.s1, pd.s2), mid = (pd.w1 + pd.w2) / 2;
    const lo = mid - span * 0.75, hi = mid + span * 0.75, L = 28, R = W - 28;
    const X = (w) => L + (w - lo) / (hi - lo) * (R - L), cy = H * 0.52, e = sstep(h, 0, 1);
    const cob = css("--accent"), cobH = css("--accent-hover");
    g.font = "400 10px 'Geist Mono', monospace"; g.textBaseline = "top"; g.textAlign = "center";
    // axis with ticks in rad/s
    g.strokeStyle = "rgba(255,255,255,.18)"; g.fillStyle = "rgba(143,143,147,.9)"; g.lineWidth = 1;
    g.beginPath(); g.moveTo(L, H - 46); g.lineTo(R, H - 46); g.stroke();
    const tick = 0.001;
    for (let w = Math.ceil(lo / tick) * tick; w <= hi; w += tick) { g.beginPath(); g.moveTo(X(w), H - 50); g.lineTo(X(w), H - 42); g.stroke(); g.fillText(w.toFixed(3), X(w), H - 34); }
    g.fillText("SWING FREQUENCY, RAD/S", (L + R) / 2, H - 18);
    // where a complete law keeps the second half: first-half estimate ± 3 sigma
    g.fillStyle = "rgba(255,255,255,.06)"; g.fillRect(X(pd.w1 - 3 * pd.s1), 30, X(pd.w1 + 3 * pd.s1) - X(pd.w1 - 3 * pd.s1), H - 84);
    g.fillStyle = "rgba(143,143,147,.9)"; g.fillText("A COMPLETE LAW LANDS HERE", X(pd.w1), 40);
    const est = (w, s, y, col, label) => {
      g.strokeStyle = col; g.fillStyle = col; g.lineWidth = 1.5;
      g.beginPath(); g.moveTo(X(w - s), y); g.lineTo(X(w + s), y); g.moveTo(X(w - s), y - 7); g.lineTo(X(w - s), y + 7); g.moveTo(X(w + s), y - 7); g.lineTo(X(w + s), y + 7); g.stroke();
      g.beginPath(); g.arc(X(w), y, 6, 0, 7); g.fill();
      g.fillText(label, X(w), y + 16);
    };
    est(pd.w1, pd.s1, cy - 26, "#fff", "FIRST HALF");
    if (h > 0) {
      g.globalAlpha = sstep(h, 0, 0.15);
      est(pd.w1 + (pd.w2 - pd.w1) * e, pd.s2, cy + 26, cobH, "SECOND HALF");
      g.globalAlpha = 1;
    }
    if (h >= 1) {  // the gap, in sigma
      g.strokeStyle = cob; g.setLineDash([2, 4]); g.lineWidth = 1;
      g.beginPath(); g.moveTo(X(pd.w1), cy - 2); g.lineTo(X(pd.w2), cy - 2); g.stroke(); g.setLineDash([]);
      g.fillStyle = "#fff"; g.textBaseline = "bottom"; g.fillText(`${pd.z.toFixed(1)} σ APART`, (X(pd.w1) + X(pd.w2)) / 2, cy - 8);
    }
  }
  function sayHold() {
    hold.style.setProperty("--h", h.toFixed(3));
    const done = h >= 1;
    hold.classList.toggle("done", done);
    if (done !== doneSaid) {
      doneSaid = done;
      out.innerHTML = done
        ? `<b>Incomplete.</b> First half swings at ${pd.w1.toFixed(4)} ± ${pd.s1.toFixed(4)} rad/s, second half at ${pd.w2.toFixed(4)} ± ${pd.s2.toFixed(4)}: ${pd.z.toFixed(1)} sigma apart. The swing speeds up as it shrinks, and a constant-frequency law can't follow it.`
        : "The same law, fitted on each half of the clip. Hold to fit the second half.";
    }
  }
  const press = (e) => { if (e.type === "keydown" && (e.repeat || (e.key !== " " && e.key !== "Enter"))) return; e.preventDefault(); holding = true; if (RM.matches) { h = 1; sayHold(); drawSplit(); } wake(); };
  const release = (e) => { if (e.type === "keyup" && e.key !== " " && e.key !== "Enter") return; holding = false; wake(); };
  hold.addEventListener("pointerdown", press);
  ["pointerup", "pointerleave", "pointercancel"].forEach((ev) => hold.addEventListener(ev, release));
  hold.addEventListener("keydown", press);
  hold.addEventListener("keyup", release);
  hold.addEventListener("click", (e) => e.preventDefault());

  /* ---------- the particle field: a slow cobalt stream on the right ---------- */
  const fc = $("#field"), parts = [];
  let seed = 7; const rnd = () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296;
  for (let i = 0; i < 620; i++) parts.push({ u: rnd(), v: rnd() - 0.5, s: 0.4 + rnd() * 1.3, a: 0.12 + rnd() * 0.5, ph: rnd() * 6.28 });
  let fieldOn = true, lastField = 0;
  function drawField(now) {
    const [g, W, H] = fit(fc);
    g.clearRect(0, 0, W, H);
    const phase = (now / 60000) * Math.PI * 2;
    for (const q of parts) {
      const cx = W * (0.8 + 0.13 * Math.sin(q.u * 4 + 0.5 + phase * 0.5)), cy = H * (q.u * 1.2 - 0.1);
      const x = cx + q.v * W * (0.08 + 0.12 * q.u) + Math.sin(phase + q.ph) * 10, y = cy + Math.cos(phase + q.ph) * 8;
      const c = q.u < 0.5 ? [0 + 24 * q.u * 2, 204 - 58 * q.u * 2, 255 - 9 * q.u * 2] : [12 + 13 * (q.u - 0.5) * 2, 146 - 62 * (q.u - 0.5) * 2, 246 - 10 * (q.u - 0.5) * 2];
      g.fillStyle = `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${q.a})`;
      g.fillRect(x, y, q.s, q.s);
    }
  }

  /* ---------- the one clock ---------- */
  let raf = 0, t0 = performance.now(), gl = null, last3d = 0, heroOn = true, eTarget = 0, eShown = 0;
  function epilogue() {  // 0..1 through everything after the hero: the 3D keeps moving to the last section
    const end = hero.offsetTop + hero.offsetHeight - innerHeight;
    return clamp((scrollY - end) / Math.max(1, root.scrollHeight - innerHeight - end), 0, 1);
  }
  const hero2d = (p) => (gl ? gl.render(p, timeAt(p), performance.now()) : drawDrop(p));
  function frame(now) {
    raf = 0;
    const dt = Math.min(100, now - (last || now)); last = now;
    let busy = false;
    if (scrub) {
      shown += (target - shown) * (1 - Math.pow(1 - 0.14, dt / 16.667));
      if (Math.abs(target - shown) < 0.0004) shown = target; else busy = true;
      eShown += (eTarget - eShown) * (1 - Math.pow(1 - 0.1, dt / 16.667));
      if (Math.abs(eTarget - eShown) < 0.0004) eShown = eTarget; else busy = true;
      if (!gl) { if (heroOn) drawDrop(shown); }
      else if (busy || now - last3d > 33) { gl.render(shown, timeAt(shown), now, eShown); last3d = now; }
      drawBands(shown, now);
      if (now - t0 < 950) busy = true;
    }
    const hTarget = holding ? 1 : 0, hPrev = h;
    if (!RM.matches && h !== hTarget) { h = clamp(h + (holding ? dt / 2200 : -dt / 900), 0, 1); busy = true; }
    if (h !== hPrev || busy) { sayHold(); drawSplit(); }
    if (fieldOn && !RM.matches && now - lastField > 40) { drawField(now); lastField = now; }
    if (busy || (fieldOn && !RM.matches)) raf = requestAnimationFrame(frame); else last = 0;
  }
  const wake = () => { if (!raf && !document.hidden) raf = requestAnimationFrame(frame); };

  function applyMode() {
    scrub = !RM.matches;
    root.classList.toggle("scrub", scrub);
    bands.forEach((b) => { b.o = -1; b.y = -1; b.el.style.opacity = ""; b.el.style.translate = ""; b.el.removeAttribute("aria-hidden"); });
    if (!scrub) { hero2d(1); h = holding ? 1 : h; drawField(0); } else { target = shown = heroProgress(); eTarget = eShown = epilogue(); t0 = performance.now() - (shown > 0.02 ? 2000 : 0); }
    sayHold(); drawSplit(); wake();
  }
  addEventListener("scroll", () => { if (scrub) { target = heroProgress(); eTarget = epilogue(); wake(); } }, { passive: true });
  addEventListener("resize", () => { if (!scrub) hero2d(1); drawSplit(); wake(); });
  addEventListener("ktp3d", () => { gl = window.KTP3D; applyMode(); });  // the WebGL scene is ready: it takes over the hero
  new IntersectionObserver(([e]) => { heroOn = e.isIntersecting; root.classList.toggle("in-hero", heroOn); if (heroOn) wake(); }).observe(hero);
  if (window.KTP3D) gl = window.KTP3D;
  RM.addEventListener("change", applyMode);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) wake(); });
  new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && e.target.classList.add("in")), { threshold: 0.2 }).observe($("#proof"));
  $$(".sec").forEach((s) => new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && e.target.classList.add("in")), { threshold: 0.15 }).observe(s));
  if (RM.matches) h = 1;
  applyMode();
})();
