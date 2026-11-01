"use strict";
// One clock: the replay time drives the overlay, the chart, the readouts and the phase chip together.

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const STAGES = [["look", "Look"], ["track", "Track"], ["discover", "Discover"], ["conserve", "Conserve"], ["remember", "Remember"], ["report", "Report"]];
const STAGE_NOTE = {
  null: "Getting the clip ready.",
  look: "Deciding what to watch and what sets the scale.",
  track: "Following the object frame by frame and turning pixels into metres.",
  discover: "Trying candidate laws on the first 70% of the clip and scoring each on the rest.",
  conserve: "Looking for combinations of position and speed that stay constant.",
  remember: "Checking this clip against every law already in your library.",
  report: "Writing the lab report and the overlay video.",
};

// LIVE is set by mode.js: app.py serves "true"; the static copy is "false" and the bench replays recorded runs,
// real pipeline output saved by record_runs.py, from the recorded/ folder beside this file.
const LIVE = window.LIVE !== false;
const fileUrl = (id, f) => (LIVE ? `/api/runs/${id}/file/${f}` : `recorded/${id}/${f}`);
const json = async (u) => { const r = await fetch(u); if (!r.ok) throw new Error(`Not found (${r.status})`); return r.json(); };

async function recorded(path) {
  const u = new URL(path, location.href), p = u.pathname.split("/").filter(Boolean).slice(-5);
  const at = p.indexOf("api"), q = p.slice(at + 1);  // e.g. ["runs", id, "file", "view.json"]
  if (q[0] === "health") return { key: false, recorded: true };
  if (q[0] === "library") {
    const words = (u.searchParams.get("q") || "").toLowerCase().split(/\s+/).filter(Boolean);
    return (await json("recorded/library.json")).filter((e) => words.every((w) => JSON.stringify(e).toLowerCase().includes(w)));
  }
  const all = await json("recorded/runs.json");
  if (q.length === 1) return all;
  if (q.length === 2) { const r = all.find((x) => x.id === q[1]); if (!r) throw new Error("No such recorded run"); return r; }
  return json(fileUrl(q[1], q[3]));
}

async function api(path, opts) {
  if (!LIVE) {
    if (opts && opts.method && opts.method !== "GET") throw new Error("This is a recorded demo. Run the app on your computer to do that.");
    return recorded(path);
  }
  const r = await fetch(path, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `The server answered ${r.status}`);
  return body;
}
const num = (v, p = 4) => (v == null || !isFinite(v) ? "n/a" : Number(v).toPrecision(p).replace(/\.?0+(e|$)/, "$1"));
const pm = (v, s) => (s == null ? num(v) : `${num(v)} ± ${num(s, 2)}`);
const when = (iso) => (iso ? new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }) : "");
const unit = (u) => String(u || "").replace("^2", "²");

let runs = [], current = null, view = null, pollTimer = null, health = { key: false };

/* ---------- routing ---------- */
function route() {
  const h = location.hash.slice(1);
  const lib = h === "library";
  $("#bench-view").hidden = lib;
  $("#library-view").hidden = !lib;
  $$("[data-nav]").forEach((a) => a.toggleAttribute("aria-current", false));
  $(`[data-nav="${lib ? "library" : "bench"}"]`).setAttribute("aria-current", "page");
  if (lib) { player.pause(); return loadLibrary(); }
  const m = h.match(/^run=([a-z0-9-]+)$/);
  openRun(m ? m[1] : runs[0]?.id);
}

async function loadRuns() {
  runs = await api("/api/runs").catch(() => []);
  const sel = $("#run-select");
  sel.innerHTML = runs.map((r) => `<option value="${esc(r.id)}">${esc(r.law || r.name)} · ${esc(when(r.created))}</option>`).join("");
  sel.disabled = !runs.length;
  if (current) sel.value = current;
}

/* ---------- a run ---------- */
async function openRun(id) {
  clearTimeout(pollTimer);
  const panels = { progress: $("#progress"), failed: $("#failed"), empty: $("#empty"), bench: $("#bench") };
  const show = (k) => Object.entries(panels).forEach(([n, el]) => (el.hidden = n !== k));
  if (!id) {
    current = null; player.pause();
    $("#run-title").textContent = "Your bench is empty";
    $("#run-meta").textContent = "No experiments yet";
    return show("empty");
  }
  if (id !== current) { view = null; player.pause(); }
  current = id;
  if (!runs.some((r) => r.id === id)) await loadRuns();
  $("#run-select").value = id;
  let st;
  try { st = await api(`/api/runs/${id}`); } catch (e) {
    $("#run-title").textContent = "That experiment is gone";
    $("#failed").innerHTML = `<h2>Not found</h2><p>${esc(e.message)}. Pick another experiment from the list.</p>`;
    return show("failed");
  }
  if (id !== current) return;
  $("#run-title").textContent = st.law || (st.state === "done" ? st.name : `Analysing ${st.name}`);
  $("#run-meta").textContent = [st.sample ? "Sample" : null, when(st.created), st.name].filter(Boolean).join(" · ");
  if (st.state === "running" || st.state === "starting") {
    show("progress");
    renderProgress(st);
    pollTimer = setTimeout(() => openRun(id), 1000);
    return;
  }
  if (st.state === "done") {
    show("bench");
    if (!view || view.id !== id) {
      view = await api(`/api/runs/${id}/file/view.json`);
      view.id = id;
      renderBench(view);
      loadRuns();
    }
    return;
  }
  show("failed");
  renderFailed(st);
}

function renderProgress(st) {
  const at = STAGES.findIndex(([k]) => k === st.stage);
  $("#steps").innerHTML = STAGES.map(([k, label], i) =>
    `<li class="${i < at ? "done" : i === at ? "now" : ""}" ${i === at ? 'aria-current="step"' : ""}>${label}</li>`).join("");
  $("#progress-note").textContent = STAGE_NOTE[st.stage] || STAGE_NOTE.null;
  const log = $("#log");
  log.textContent = (st.log || []).join("\n");
  log.scrollTop = log.scrollHeight;
}

function renderFailed(st) {
  const e = st.error || "";
  const hint = /no reference/.test(e) ? "No A4 sheet was found in the first frame. Put the sheet flat in the plane of motion, or give the real size of whatever reference is in view."
    : /cannot read/.test(e) ? "The video could not be opened. Export it again as MP4 (H.264) and retry."
    : /MODEL_API_KEY|openai/.test(e) ? "This needs the model API. Set MODEL_API_KEY, or track a coloured sticker instead."
    : st.state === "interrupted" ? "The app was closed while this experiment was running. Start it again from the clip."
    : "The log below shows the last thing the lab did.";
  const stage = STAGES.find(([k]) => k === st.stage)?.[1];
  $("#failed").innerHTML = `<h2>${stage ? `The lab stopped at ${esc(stage.toLowerCase())}` : "The lab stopped"}</h2>
    <p>${esc(hint)}</p>${e ? `<p class="mono small muted">${esc(e)}</p>` : ""}
    <pre class="log mono">${esc((st.log || []).join("\n"))}</pre>
    <div class="row"><button class="btn primary" type="button" data-act="new">Try another clip</button>
    <button class="btn" type="button" data-act="delete">Delete this experiment</button></div>`;
}

/* ---------- the bench ---------- */
let C = {};
function readColors() {
  const s = getComputedStyle(document.documentElement);
  for (const k of ["ink", "muted", "line", "measured", "law", "surface", "ground"]) C[k] = s.getPropertyValue(`--${k}`).trim();
}

function renderBench(v) {
  readColors();
  const [w, h] = v.frame[0] ? v.frame : guessFrame(v);
  v.W = w; v.H = h;
  $("#stage").style.setProperty("--ar", `${w} / ${h}`);
  $("#stage").style.setProperty("--arn", w / h);
  const n = v.t.length;
  v.split = v.law.split || 0.7;
  v.T0 = v.t[0]; v.T1 = v.t[n - 1]; v.Ts = v.t[Math.floor(n * v.split)];
  const sp = `${(100 * (v.Ts - v.T0)) / (v.T1 - v.T0)}%`;
  $(".scrub").style.setProperty("--split", sp);
  $("#scrub").style.setProperty("--split", sp);
  const ax = v.law.axis;
  $("#chart-title").textContent = `${ax} against time`;
  $("#chart-desc").textContent = `Green dots are the measured ${ax} position; the magenta line is the law. The law never saw anything after ${num(v.Ts, 3)} s (shaded): the dots land on a line that was already drawn.`;
  renderNotebook(v);
  player.load(v);
}

function guessFrame(v) {
  const xs = v.objects[0].px, ys = v.objects[0].py;
  return [Math.max(...xs) * 1.25 + 40, Math.max(...ys) * 1.25 + 40];
}

function renderNotebook(v) {
  const L = v.law, mm = (L.holdout_rmse || 0) * 1000;
  const sec = (cls, title, body) => `<section class="nb ${cls}"><h3 class="h-sm">${title}</h3>${body}</section>`;
  const derived = (L.derived || []).filter((d) => d.value != null);
  const facts = derived.length ? derived.map((d) => `<div class="fact"><span>${esc(d.name)}</span><b>${esc(num(d.value))} <span class="sig">± ${esc(num(d.sigma, 2))} ${esc(unit(d.unit))}</span></b><span>${esc(d.meaning || "")}</span></div>`)
    : Object.entries(L.params).slice(0, 4).map(([k, val]) => `<div class="fact"><span>${esc(k)}</span><b>${esc(pm(val, L.sigma?.[k]))}</b></div>`);

  const cands = L.candidates || [];
  const lo = Math.log10(Math.max(1e-4, Math.min(...cands.map((c) => c.holdout_rmse)) * 0.5));
  const hi = Math.log10(Math.max(...cands.map((c) => c.holdout_rmse), 1e-3) * 1.2);
  const ladder = cands.map((c) => {
    const f = Math.max(0.04, (Math.log10(c.holdout_rmse) - lo) / (hi - lo || 1));
    return `<li class="${c.expr === L.expr ? "chosen" : ""}"><span class="k">${c.k}</span><span class="ex" title="${esc(c.expr)}">${esc(c.expr)}</span>
      <span class="bar" aria-label="${num(c.holdout_rmse * 1000, 3)} millimetres off on unseen frames"><i style="width:${(f * 100).toFixed(1)}%"></i><em>${num(c.holdout_rmse * 1000, 2)} mm</em></span></li>`;
  }).join("");

  const fz = L.falsify || { verdict: "not run", drift: [] };
  const ok = fz.verdict === "survived";
  const breakIt = `<span class="verdict ${ok ? "v-good" : "v-warn"}">${ok ? "Survived" : "Incomplete: constants drift"}</span>` + (ok
    ? `<p>Refitted on each half of the clip separately, every constant stayed within 3 sigma of itself.</p>`
    : `<ul>${fz.drift.map((d) => `<li><code>${esc(d.param)}</code> moved from ${num(d.first)} to ${num(d.second)} between the two halves (${num(d.z, 2)} sigma). The law is missing something.</li>`).join("")}</ul>`);

  const cons = (v.conserved || []);
  const real = cons.filter((c) => c.terms.length > 1), still = cons.filter((c) => c.terms.length === 1);
  const sup = (s) => s.replace(/\^2/g, "²").replace(/\*/g, "·");
  const pretty = (c) => c.terms.map((term, i) => {
    const w = c.weights[i], a = Math.abs(w), coef = Math.abs(a - 1) < 5e-4 ? "" : `${num(a, 4)}·`;
    return `${i ? (w < 0 ? " − " : " + ") : w < 0 ? "−" : ""}${coef}${sup(term)}`;
  }).join("") + " = constant";
  const consBody = (real.length ? `<ul>${real.map((c) => `<li><code>${esc(pretty(c))}</code> <span class="muted">within ${num(c.spread * 100, 2)}%</span></li>`).join("")}</ul>`
    : `<p class="muted">Nothing built from position and speed stayed constant within 5%.</p>`)
    + (still.length ? `<p class="muted small">Not moving: ${still.map((c) => esc(c.terms[0])).join(", ")}.</p>` : "");

  const lib = v.library || [];
  const libBody = lib.length ? `<ul>${lib.map((r) => `<li><span class="verdict ${r.broken ? "v-bad" : "v-good"}">#${r.id} ${r.broken ? "breaks here" : "holds"}</span> ${esc(r.law || r.expr)}</li>`).join("")}</ul>`
    : `<p class="muted">No standing law in your library to test this clip against yet. Laws that failed their own self-test are not used.</p>`;

  const P = L.prediction, M = L.measured;
  const next = L.next_experiment ? `<p>${esc(L.next_experiment)}</p>` + (P && P.value != null ? `<div class="fact"><span>Predicted ${esc(P.quantity)}</span><b>${esc(pm(P.value, P.sigma))} ${esc(unit(P.unit))}</b><span>${esc(P.measure || "")}</span></div>` : "")
    + (M && M.verdict ? `<span class="verdict ${M.verdict === "CONFIRMED" ? "v-good" : "v-bad"}">${M.verdict === "CONFIRMED" ? "Prediction confirmed" : "Prediction refuted"}: measured ${esc(pm(M.value, M.sigma))}, ${num(M.rel_error * 100, 2)}% off</span>` : "")
    : `<p class="muted">With a model key, the agent proposes the experiment that would best tell this law from its rival, and predicts the number you should measure.</p>`;

  const base = fileUrl(v.id, "");
  $("#notebook").innerHTML =
    sec("nb-law", "The law", `<h2>${esc(L.law)}</h2>
      <span class="verdict ${ok ? "v-good" : "v-warn"}">${ok ? "Predicts unseen frames and survives its self-test" : "Predicts unseen frames, but is incomplete"}</span>
      <p class="formula">${esc(L.axis)}(t) = ${esc(L.expr)}</p>
      <p class="muted">Fitted on the first ${Math.round(v.split * 100)}% of the clip. On the part it never saw, it was typically ${num(mm, 2)} mm off.${ok ? "" : " Its constants still drift between the two halves of the clip, so something real is missing (see below)."}</p>
      ${L.explanation ? `<p>${esc(L.explanation)}</p>` : ""}`)
    + sec("", derived.length ? "What the numbers mean" : "Constants", `<div class="facts">${facts.join("")}</div>`)
    + (cands.length ? sec("", "How it found the law", `<p class="muted small">${L.tried || cands.length} laws tried, nobody named a formula. Best law at each number of constants, and how far off it was on unseen frames:</p><ol class="ladder">${ladder}</ol>`) : "")
    + sec("", "Trying to break it", breakIt)
    + sec("", "What stayed constant", consBody)
    + sec("", "Against your library", libBody)
    + sec("", "Next experiment", next)
    + sec("", "Files", `<div class="files"><a href="${base}report.html" target="_blank" rel="noopener">Lab report</a>${LIVE ? `<a href="${base}overlay.webm" target="_blank" rel="noopener">Overlay video</a>` : ""}<a href="${base}track.csv" download>Track CSV</a><a href="${base}fit.json" download>Law JSON</a></div>`);
}

/* ---------- player: one clock for overlay + chart ---------- */
const player = (() => {
  const video = $("#video"), cvs = $("#overlay"), chart = $("#chart"), stage = $("#stage");
  let v = null, t = 0, playing = false, rate = 0.5, traceOnly = false, raf = 0, last = 0, hover = null;

  const idx = (time) => { let lo = 0, hi = v.t.length - 1; while (lo < hi) { const m = (lo + hi) >> 1; v.t[m] < time ? (lo = m + 1) : (hi = m); } return lo; };
  const scale = () => v.time_scale || 1;
  const now = () => (traceOnly ? t : video.currentTime * scale());

  function load(nv) {
    pause();
    v = nv; traceOnly = !v.video;
    stage.classList.toggle("trace-only", traceOnly);
    if (!traceOnly) {
      video.src = fileUrl(v.id, v.video);
      video.onerror = () => { traceOnly = true; stage.classList.add("trace-only"); draw(); };
      video.onloadeddata = () => draw();
    } else video.removeAttribute("src");
    seek(v.T0 + 0.82 * (v.T1 - v.T0));  // open on the predicting part: the interesting frame
    if (!reduced) setTimeout(() => v === nv && play(), 700);
  }

  function seek(time) {
    t = Math.min(Math.max(time, v.T0), v.T1);
    if (!traceOnly && video.src) { try { video.currentTime = t / scale(); } catch (e) { /* not loaded yet */ } }
    draw(t);
  }

  function play() {
    if (!v) return;
    playing = true;
    $("#play").setAttribute("aria-label", "Pause");
    $("#play-glyph").setAttribute("d", "M7 5h4v14H7zM13 5h4v14h-4z");
    if (!traceOnly) {
      video.playbackRate = Math.min(16, Math.max(0.0625, rate / scale()));
      video.play().catch(() => { traceOnly = true; stage.classList.add("trace-only"); });
    }
    last = performance.now();
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(tick);
  }

  function pause() {
    playing = false;
    cancelAnimationFrame(raf);
    if (!video.paused) video.pause();
    $("#play").setAttribute("aria-label", "Play");
    $("#play-glyph").setAttribute("d", "M8 5v14l11-7z");
  }

  function tick(ms) {
    if (!playing) return;
    const dt = (ms - last) / 1000; last = ms;
    if (traceOnly) { t += dt * rate; if (t > v.T1) t = v.T0; }
    else { t = now(); if (video.ended || t >= v.T1) { t = v.T0; video.currentTime = t / scale(); video.play().catch(() => {}); } }
    draw(t);
    raf = requestAnimationFrame(tick);
  }

  function fit(canvas) {
    const r = canvas.getBoundingClientRect(), d = devicePixelRatio || 1;
    if (canvas.width !== Math.round(r.width * d) || canvas.height !== Math.round(r.height * d)) { canvas.width = Math.round(r.width * d); canvas.height = Math.round(r.height * d); }
    const ctx = canvas.getContext("2d"); ctx.setTransform(d, 0, 0, d, 0, 0);
    return [ctx, r.width, r.height];
  }

  function draw(time = t) {
    if (!v) return;
    const j = idx(time), n = v.t.length, predicting = time >= v.Ts;
    drawStage(j, n);
    drawChart(j, time);
    const ph = $("#phase");
    ph.textContent = predicting ? "Predicting: the law never saw these frames" : "Fitting: the law learns from these frames";
    ph.classList.toggle("predicting", predicting);
    $("#clock").textContent = `${time.toFixed(3)} s`;
    if (document.activeElement !== $("#scrub")) $("#scrub").value = Math.round((1000 * (time - v.T0)) / (v.T1 - v.T0));
    const off = Math.abs(v.measured[j] - v.predicted[j]) * 1000;
    $("#readout").textContent = `measured ${num(v.measured[j], 4)} m · law ${num(v.predicted[j], 4)} m · ${num(off, 2)} mm apart`;
  }

  function drawStage(j, n) {
    const [ctx, w, h] = fit(cvs);
    ctx.clearRect(0, 0, w, h);
    const s = Math.min(w / v.W, h / v.H), ox = (w - v.W * s) / 2, oy = (h - v.H * s) / 2;
    const X = (px) => ox + px * s, Y = (py) => oy + py * s;
    const span = (sec) => Math.max(2, Math.round(sec / ((v.T1 - v.T0) / n)));
    const r = Math.max(7, 14 * s);
    if (traceOnly) {  // no playable video: draw the whole measured path as context
      ctx.strokeStyle = "#ffffff22"; ctx.lineWidth = 1; ctx.beginPath();
      v.objects[0].px.forEach((x, i) => (i ? ctx.lineTo(X(x), Y(v.objects[0].py[i])) : ctx.moveTo(X(x), Y(v.objects[0].py[i]))));
      ctx.stroke();
    }
    for (const o of v.objects) {  // measured: recent trail + ring
      ctx.strokeStyle = "#3dcb8666"; ctx.lineWidth = 2; ctx.beginPath();
      for (let i = Math.max(0, j - span(0.35)); i <= j; i++) (i === Math.max(0, j - span(0.35)) ? ctx.moveTo : ctx.lineTo).call(ctx, X(o.px[i]), Y(o.py[i]));
      ctx.stroke();
      ctx.strokeStyle = "#3dcb86"; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(X(o.px[j]), Y(o.py[j]), r, 0, 7); ctx.stroke();
    }
    ctx.strokeStyle = "#ff5aaecc"; ctx.lineWidth = 2.5; ctx.beginPath();  // law: recent trail
    for (let i = Math.max(0, j - span(0.6)); i <= j; i++) (i === Math.max(0, j - span(0.6)) ? ctx.moveTo : ctx.lineTo).call(ctx, X(v.pred_px[i]), Y(v.pred_py[i]));
    ctx.stroke();
    if ($("#forecast").checked) {  // forecast: where the law puts it next, along the axis it predicts
      const xAxis = v.law.axis[0] === "x", ahead = span(0.5), step = Math.max(1, Math.round(ahead / 9));
      for (let k = step, q = 1; k <= ahead && j + k < n; k += step, q++) {
        const px = xAxis ? v.pred_px[j + k] : v.pred_px[j], py = xAxis ? v.pred_py[j] : v.pred_py[j + k];
        ctx.fillStyle = `rgba(255, 90, 174, ${0.9 - q * 0.08})`;
        ctx.beginPath(); ctx.arc(X(px), Y(py), Math.max(2, 3.5 * s * 1.4 - q * 0.15), 0, 7); ctx.fill();
      }
    }
    ctx.fillStyle = "#ff5aae"; ctx.strokeStyle = "#000a"; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(X(v.pred_px[j]), Y(v.pred_py[j]), Math.max(4, 6 * s), 0, 7); ctx.fill(); ctx.stroke();
  }

  let geo = null;
  function drawChart(j, time) {
    const [ctx, w, h] = fit(chart);
    const pad = { l: 56, r: 12, t: 22, b: 26 };
    let lo = Infinity, hi = -Infinity;
    for (const a of [v.measured, v.predicted]) for (const y of a) { if (y < lo) lo = y; if (y > hi) hi = y; }
    const m = (hi - lo) * 0.08 || 0.01; lo -= m; hi += m;
    const X = (tt) => pad.l + ((tt - v.T0) / (v.T1 - v.T0)) * (w - pad.l - pad.r);
    const Y = (y) => pad.t + (1 - (y - lo) / (hi - lo)) * (h - pad.t - pad.b);
    geo = { X, Y, pad, w, h };
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = C.law + "14"; ctx.fillRect(X(v.Ts), pad.t, X(v.T1) - X(v.Ts), h - pad.t - pad.b);
    ctx.font = "500 11px 'IBM Plex Mono', monospace"; ctx.fillStyle = C.muted; ctx.textBaseline = "middle";
    ctx.fillText("fitted on", X(v.T0) + 4, 10); ctx.fillText("never seen", X(v.Ts) + 6, 10);
    ctx.strokeStyle = C.line; ctx.lineWidth = 1; ctx.textAlign = "right";
    for (const y of ticks(lo, hi, 4)) { ctx.beginPath(); ctx.moveTo(pad.l, Y(y)); ctx.lineTo(w - pad.r, Y(y)); ctx.stroke(); ctx.fillText(num(y, 3), pad.l - 8, Y(y)); }
    ctx.textAlign = "center"; ctx.textBaseline = "top";
    for (const tt of ticks(v.T0, v.T1, 6)) ctx.fillText(`${num(tt, 3)} s`, X(tt), h - pad.b + 8);
    ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
    ctx.strokeStyle = C.law; ctx.lineWidth = 2; ctx.beginPath();
    v.t.forEach((tt, i) => (i ? ctx.lineTo(X(tt), Y(v.predicted[i])) : ctx.moveTo(X(tt), Y(v.predicted[i]))));
    ctx.stroke();
    ctx.fillStyle = C.measured;
    for (let i = 0; i <= j; i += 1) { ctx.beginPath(); ctx.arc(X(v.t[i]), Y(v.measured[i]), 1.8, 0, 7); ctx.fill(); }
    ctx.strokeStyle = C.ink; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(X(time), pad.t); ctx.lineTo(X(time), h - pad.b); ctx.stroke();
    ctx.fillStyle = C.law; ctx.strokeStyle = C.surface; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(X(time), Y(v.predicted[j]), 4.5, 0, 7); ctx.fill(); ctx.stroke();
    if (hover != null) {
      const i = hover, tip = $("#tip");
      tip.hidden = false;
      tip.style.left = `${X(v.t[i])}px`; tip.style.top = `${Y(v.measured[i])}px`;
      tip.innerHTML = `${num(v.t[i], 4)} s<br>measured ${num(v.measured[i], 4)} m<br>law ${num(v.predicted[i], 4)} m`;
    }
  }

  function ticks(a, b, count) {
    const raw = (b - a) / count, mag = 10 ** Math.floor(Math.log10(raw)), f = raw / mag;
    const step = (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * mag, out = [];
    for (let x = Math.ceil(a / step) * step; x <= b + 1e-12; x += step) out.push(+x.toPrecision(12));
    return out;
  }

  const timeAt = (e) => { const r = chart.getBoundingClientRect(); return v.T0 + ((e.clientX - r.left - geo.pad.l) / (geo.w - geo.pad.l - geo.pad.r)) * (v.T1 - v.T0); };
  chart.addEventListener("pointermove", (e) => { if (!v || !geo) return; hover = idx(timeAt(e)); if (e.buttons) seek(timeAt(e)); else draw(); });
  chart.addEventListener("pointerleave", () => { hover = null; $("#tip").hidden = true; v && draw(); });
  chart.addEventListener("pointerdown", (e) => { if (v && geo) { pause(); seek(timeAt(e)); } });
  $("#play").addEventListener("click", () => (playing ? pause() : play()));
  $("#scrub").addEventListener("input", (e) => { if (!v) return; pause(); seek(v.T0 + (e.target.value / 1000) * (v.T1 - v.T0)); });
  $$(".seg button").forEach((b) => b.addEventListener("click", () => {
    rate = +b.dataset.rate;
    $$(".seg button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    if (playing) play();
  }));
  $("#forecast").addEventListener("change", () => draw());
  document.addEventListener("visibilitychange", () => document.hidden && pause());
  new ResizeObserver(() => v && draw()).observe(stage);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { readColors(); v && draw(); });
  return { load, pause, draw };
})();

/* ---------- library ---------- */
let libTimer = 0;
async function loadLibrary() {
  const q = $("#lib-q").value.trim();
  const laws = await api(`/api/library?q=${encodeURIComponent(q)}`).catch(() => []);
  const chip = (s) => (s === "standing" ? ["v-good", "Standing"] : /broken/.test(s) ? ["v-bad", "Broken by a later clip"] : ["v-warn", "Incomplete: constants drift"]);
  $("#laws").innerHTML = laws.length ? laws.map((e) => {
    const run = (String(e.csv || "").match(/runs[\\/]+([a-z0-9-]+)[\\/]/) || [])[1];
    const [cls, label] = chip(e.status || "");
    return `<li><span class="num">#${e.id}</span><div style="min-width:0"><h3>${esc(e.law || e.expr)}</h3><code>${esc(e.axis)}(t) = ${esc(e.expr)}</code>
      <p class="muted small">${esc(e.note || "")} · ${esc(e.date || "")}</p></div>
      <div class="side"><span class="verdict ${cls}">${label}</span>${run ? `<a class="open" href="#run=${esc(run)}">Open the bench</a>` : ""}</div></li>`;
  }).join("") : `<li><div><h3>${q ? "No law matches that search" : "No laws yet"}</h3><p class="muted">${q ? "Try a shorter word, like the object or a term such as damped." : "Every experiment adds the law it found here."}</p></div></li>`;
  if (!q) $("#laws").insertAdjacentHTML("beforeend", `<li class="lib-cta"><div><h3>Test it on something new</h3><p class="muted">A second clip either agrees with these laws or breaks them, and the library records which.</p></div><div class="side"><button class="btn primary" type="button" data-act="new">New experiment</button></div></li>`);
}
$("#lib-q").addEventListener("input", () => { clearTimeout(libTimer); libTimer = setTimeout(loadLibrary, 200); });

/* ---------- new experiment ---------- */
const dlg = $("#dlg"), form = $("#form");
let file = null;
function openDialog() {
  $("#form").hidden = !LIVE;
  $("#rec-note").hidden = LIVE;
  $("#verify").innerHTML = `<option value="">Nothing, this is a new experiment</option>` +
    runs.filter((r) => r.state === "done").map((r) => `<option value="${esc(r.id)}">${esc(r.law || r.name)} · ${esc(when(r.created))}</option>`).join("");
  $("#form-error").hidden = true;
  dlg.showModal();
}
function setFile(f) {
  file = f || null;
  $("#drop").classList.toggle("has", !!file);
  $("#drop-title").textContent = file ? file.name : "Drop a clip here, or choose one";
  $("#drop-sub").textContent = file ? `${(file.size / 1e6).toFixed(1)} MB, ready` : "Phone static, square to the motion, a sheet of A4 paper in the same plane";
}
function syncTrack() { $("#swatches").setAttribute("aria-disabled", String($("#track-auto").checked)); }
$("#file").addEventListener("change", (e) => setFile(e.target.files[0]));
const drop = $("#drop");
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => setFile(e.dataTransfer.files[0]));
$$('input[name="track"]').forEach((r) => r.addEventListener("change", syncTrack));
$("#dlg-close").addEventListener("click", () => dlg.close());
$("[data-close]").addEventListener("click", () => dlg.close());

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const err = (m) => { const el = $("#form-error"); el.textContent = m; el.hidden = false; };
  if (!file) return err("Choose a clip first.");
  if (!/\.(mp4|mov|m4v|webm|mkv|avi)$/i.test(file.name)) return err("That file is not a video. Use MP4, MOV, M4V, WebM, MKV or AVI.");
  const fps = $("#fps").value.trim(), ref = $("#ref").value.trim();
  if (fps && !(+fps > 0)) return err("The frame rate must be a positive number, like 240.");
  if (ref && !(+ref > 0)) return err("The reference size must be in metres, like 0.297 for A4.");
  const q = new URLSearchParams({ name: file.name });
  if ($("#track-color").checked) q.set("color", form.color.value);
  if (fps) q.set("fps", fps);
  if (ref) q.set("ref_m", ref);
  if ($("#note").value.trim()) q.set("note", $("#note").value.trim());
  if ($("#verify").value) q.set("verify", $("#verify").value);
  const xhr = new XMLHttpRequest();
  $("#upload").hidden = false; $("#submit").disabled = true;
  xhr.upload.onprogress = (ev) => { const p = ev.lengthComputable ? Math.round((100 * ev.loaded) / ev.total) : 0; $("#upload-bar").style.width = `${p}%`; $("#upload-pct").textContent = `${p}%`; };
  xhr.onload = async () => {
    $("#submit").disabled = false; $("#upload").hidden = true;
    let body = {}; try { body = JSON.parse(xhr.responseText); } catch (x) { /* empty */ }
    if (xhr.status !== 201) return err(body.error || `The upload failed (${xhr.status}).`);
    dlg.close(); setFile(null); form.reset(); syncTrack();
    await loadRuns(); location.hash = `run=${body.id}`;
  };
  xhr.onerror = () => { $("#submit").disabled = false; $("#upload").hidden = true; err("The upload stopped. Check that the app is still running and try again."); };
  xhr.open("POST", `/api/runs?${q}`);
  xhr.send(file);
});

/* ---------- actions ---------- */
document.addEventListener("click", async (e) => {
  const act = e.target.closest("[data-act]")?.dataset.act;
  if (!act) return;
  if (act === "new") openDialog();
  if (act === "sample") {
    e.target.disabled = true;
    try { const { id } = await api("/api/sample", { method: "POST" }); dlg.open && dlg.close(); await loadRuns(); location.hash = `run=${id}`; }
    catch (x) { alert(x.message); } finally { e.target.disabled = false; }
  }
  if (act === "delete" && current) {
    await api(`/api/runs/${current}`, { method: "DELETE" }).catch(() => {});
    current = null; await loadRuns(); location.hash = runs[0] ? `run=${runs[0].id}` : "bench"; route();
  }
});
$("#new").addEventListener("click", openDialog);
$("#run-select").addEventListener("change", (e) => (location.hash = `run=${e.target.value}`));
const toBench = () => $("#main").scrollIntoView({ behavior: reduced ? "auto" : "smooth" });  // past the intro
window.addEventListener("hashchange", () => { route(); toBench(); });
document.addEventListener("click", (e) => {
  if (!e.target.closest('a[href="#bench"]')) return;
  e.preventDefault();
  if (location.hash !== "#bench") history.pushState(null, "", "#bench");
  route(); toBench();
});

(async function init() {
  health = await api("/api/health").catch(() => ({ key: false }));
  if (!LIVE) {  // static hosting: say plainly what this is, and how to run it for real
    document.documentElement.classList.add("recorded");
    $("#mode").textContent = "Recorded runs";
    $("#mode").className = "pill on";
    $("#mode").title = "Real pipeline output, replayed in your browser. Run the app to analyse your own clips.";
    await loadRuns();
    return route();
  }
  const mode = $("#mode");
  mode.textContent = health.key ? `Models: ${health.provider}` : "Offline mode";
  mode.className = `pill ${health.key ? "on" : "off"}`;
  mode.title = health.key ? `The agent and vision model run on ${health.provider}${health.sam ? ", with SAM tracking" : ""}` : "No key in .env: the lab tracks a coloured sticker and finds laws without a model";
  if (!health.key || !health.sam) {
    $("#track-auto").disabled = true;
    $("#auto-note").textContent = health.key ? `Needs SAM, which ${health.provider} doesn't offer: use a sticker` : "Needs a model key in .env";
  }
  syncTrack();
  await loadRuns();
  route();
})();
