// The drop in 3D. No loop of its own: site.js's single clock calls KTP3D.render(p, t, now).
// Same data, same meanings: white = measured, cobalt = the law. Falls back to the 2D canvas if WebGL is unavailable.
// jsDelivr's +esm builds point every addon at the same three build, so no import map is needed (the app's CSP allows it).
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/+esm";
import { EffectComposer } from "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/postprocessing/EffectComposer.js/+esm";
import { RenderPass } from "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/postprocessing/RenderPass.js/+esm";
import { UnrealBloomPass } from "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/postprocessing/UnrealBloomPass.js/+esm";
import { OutputPass } from "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/postprocessing/OutputPass.js/+esm";

const D = window.KTP && window.KTP.drop;
const canvas = document.getElementById("gl"), lens = document.getElementById("lens");
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const sstep = (p, a, b) => { const t = clamp((p - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const COB = new THREE.Color("#1954ec"), COBH = new THREE.Color("#3d72ff"), CYAN = new THREE.Color("#00ccff");

async function init() {
  if (!D || !canvas) return;
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" }); }
  catch (e) { return; }  // no WebGL: the 2D hero stays
  await document.fonts.ready;
  renderer.setPixelRatio(Math.min(1.75, devicePixelRatio || 1));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;

  const n = D.t.length, tEnd = D.t[n - 1], iSplit = Math.floor(n * 0.7), STEP = 8;
  const X = (t) => -3 + (6 * t) / tEnd, Y = (y) => clamp(y * 1.25, -3.6, 2.8);
  const P = (i, ys) => new THREE.Vector3(X(D.t[i]), Y(ys[i]), 0);
  const floorY = Y(D.law[n - 1]) - 0.09;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#070708");
  scene.fog = new THREE.FogExp2("#070708", 0.05);
  const camera = new THREE.PerspectiveCamera(38, 1, 0.05, 80);

  const label = (text, color, h = 0.13) => {  // crisp mono text as a sprite
    const c = document.createElement("canvas"), g = c.getContext("2d"), fs = 64;
    g.font = `400 ${fs}px 'Geist Mono', monospace`;
    c.width = Math.ceil(g.measureText(text).width) + 16; c.height = fs + 24;
    g.font = `400 ${fs}px 'Geist Mono', monospace`; g.fillStyle = color; g.textBaseline = "middle"; g.fillText(text, 8, c.height / 2);
    const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, fog: true }));
    s.scale.set((h * c.width) / c.height, h, 1);
    return s;
  };
  const line = (pts, color, opacity) => new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color, transparent: true, opacity, fog: true }));

  // the instrument: a metre ruler, a time floor, a grid
  const ruler = new THREE.Group();
  ruler.add(line([new THREE.Vector3(-3.6, Y(1.75), 0), new THREE.Vector3(-3.6, Y(-2.5), 0)], 0xffffff, 0.3));
  for (let m = -2.5; m <= 1.5 + 1e-9; m += 0.5) {
    ruler.add(line([new THREE.Vector3(-3.72, Y(m), 0), new THREE.Vector3(-3.6, Y(m), 0)], 0xffffff, 0.4));
    const l = label(`${m.toFixed(1)} m`, "#8f8f93", 0.11); l.position.set(-4.05, Y(m), 0); ruler.add(l);
  }
  for (let s = 0; s <= tEnd + 1e-9; s += 0.1) {
    const l = label(`${s.toFixed(1)} s`, "#8f8f93", 0.1); l.position.set(X(s), floorY + 0.02, 1.15); ruler.add(l);
  }
  scene.add(ruler);
  const grid = new THREE.GridHelper(16, 32, 0x2a2a33, 0x16161c);
  grid.position.y = floorY; grid.material.transparent = true; grid.material.opacity = 0.6;
  scene.add(grid);

  // measured flashes, every 1/30 s of the real track
  const S = []; for (let i = 0; i < n; i += STEP) S.push(i);
  const flashes = new THREE.InstancedMesh(new THREE.SphereGeometry(0.062, 20, 14),
    new THREE.MeshBasicMaterial({ color: 0xb9bdc8, transparent: true, opacity: 0.8 }), S.length);
  const m4 = new THREE.Matrix4();
  S.forEach((i, k) => flashes.setMatrixAt(k, m4.makeTranslation(X(D.t[i]), Y(D.y[i]), 0)));
  flashes.count = 0; scene.add(flashes);
  const ball = new THREE.Mesh(new THREE.SphereGeometry(0.078, 32, 20), new THREE.MeshBasicMaterial({ color: 0xffffff }));
  scene.add(ball);

  // the 70% wall: fitted on one side, never seen on the other
  const xs = X(D.t[iSplit]);
  const wall = new THREE.Group();
  const wallMat = new THREE.MeshBasicMaterial({ color: COB, transparent: true, opacity: 0.05, side: THREE.DoubleSide, depthWrite: false });
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(4, 6.2), wallMat); plane.rotation.y = Math.PI / 2; wall.add(plane);
  const edge = new THREE.LineSegments(new THREE.EdgesGeometry(plane.geometry), new THREE.LineBasicMaterial({ color: COBH, transparent: true, opacity: 0.4 }));
  edge.rotation.y = Math.PI / 2; wall.add(edge);
  const lf = label("FITTED", "#8f8f93", 0.12); lf.position.set(-0.45, 2.45, 0); wall.add(lf);
  const ln = label("NEVER SEEN", "#3d72ff", 0.12); ln.position.set(0.6, 2.45, 0); wall.add(ln);
  wall.position.set(xs, -0.5, 0); scene.add(wall);

  // laws as tubes: the rivals in white, the winner in cobalt; predicted part as a dotted trail
  const tube = (ys, from, to, r, mat) => {
    const pts = []; for (let i = from; i <= to; i += 2) pts.push(P(i, ys));
    return new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), Math.max(8, pts.length * 2), r, 8), mat);
  };
  const rivals = D.rivals.map((r) => { const m = tube(r.y, 0, n - 1, 0.006, new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0 })); scene.add(m); return m; });
  const law = tube(D.law, 0, iSplit, 0.016, new THREE.MeshBasicMaterial({ color: COBH }));
  law.geometry.setDrawRange(0, 0); scene.add(law);
  const dots = []; for (let i = iSplit; i < n; i += 3) dots.push(P(i, D.law));
  const ahead = new THREE.Points(new THREE.BufferGeometry().setFromPoints(dots),
    new THREE.PointsMaterial({ color: COBH, size: 0.035, transparent: true, opacity: 0.9 }));
  ahead.geometry.setDrawRange(0, 0); scene.add(ahead);

  // ghosts: rings where the law puts the ball, hung before it gets there
  const ghostIdx = S.filter((i) => i > iSplit).concat([n - 1]);
  const ringGeo = new THREE.TorusGeometry(0.115, 0.007, 8, 64), ringMat = new THREE.MeshBasicMaterial({ color: COBH });
  const ghosts = ghostIdx.map((i) => { const g = new THREE.Mesh(ringGeo, ringMat); g.position.copy(P(i, D.law)); g.scale.setScalar(0); scene.add(g); return g; });
  const landing = new THREE.Group();
  const lmat = new THREE.MeshBasicMaterial({ color: COBH, transparent: true, opacity: 0 });
  const bar = new THREE.BoxGeometry(0.5, 0.004, 0.012);
  const b1 = new THREE.Mesh(bar, lmat), b2 = new THREE.Mesh(bar, lmat); b2.rotation.y = Math.PI / 2; landing.add(b1, b2);
  const disc = new THREE.Mesh(new THREE.RingGeometry(0.16, 0.172, 64), lmat); disc.rotation.x = -Math.PI / 2; landing.add(disc);
  const ll = label("PREDICTED LANDING", "#3d72ff", 0.1); ll.position.set(0, 0.16, 0.45); landing.add(ll);
  landing.position.set(X(tEnd), floorY + 0.005, 0); scene.add(landing);

  // the observatory: a slow cobalt stream of particles around the scene
  const N = 5200, pos = new Float32Array(N * 3), col = new Float32Array(N * 3);
  let seed = 11; const rnd = () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296;
  for (let i = 0; i < N; i++) {
    const u = rnd(), a = u * 9 + rnd() * 0.6, r = 7 + (rnd() - 0.5) * 3.2;
    pos.set([Math.cos(a) * r + 2.5, (u - 0.5) * 16 + (rnd() - 0.5) * 1.5, Math.sin(a) * r - 5], i * 3);
    const c = CYAN.clone().lerp(COB, u); col.set([c.r, c.g, c.b], i * 3);
  }
  const pg = new THREE.BufferGeometry();
  pg.setAttribute("position", new THREE.BufferAttribute(pos, 3)); pg.setAttribute("color", new THREE.BufferAttribute(col, 3));
  const stream = new THREE.Points(pg, new THREE.PointsMaterial({ size: 0.045, vertexColors: true, transparent: true, opacity: 0.7, blending: THREE.AdditiveBlending, depthWrite: false }));
  scene.add(stream);

  // camera: one path through the story, keyed to scroll progress
  const xl = X(tEnd), yl = Y(D.law[n - 1]), ys = Y(D.y[iSplit]);
  const keys = [
    [0.00, [-2.2, 2.3, 2.6], [-3.0, 2.0, 0]],
    [0.15, [-1.7, 2.2, 3.7], [-2.5, 1.7, 0]],
    [0.44, [0.3, 0.5, 4.4], [0.7, 0.0, 0]],
    [0.57, [-2.2, 1.7, 10.5], [-0.2, -0.4, 0]],
    [0.66, [-0.4, 0.3, 3.0], [xs + 0.7, ys - 0.7, 0]],
    [0.75, [1.9, -0.7, 2.5], [xl, yl + 0.7, 0]],
    [0.87, [3.7, -1.4, 3.3], [xl, yl, 0]],
    [0.95, [-1.7, 0.8, 11.2], [0.3, -0.5, 0]],
    [1.00, [-1.6, 0.75, 10.8], [0.3, -0.5, 0]],
  ];
  const posPath = new THREE.CatmullRomCurve3(keys.map((k) => new THREE.Vector3(...k[1])), false, "centripetal");
  const tgtPath = new THREE.CatmullRomCurve3(keys.map((k) => new THREE.Vector3(...k[2])), false, "centripetal");
  const along = (p) => {
    let i = 0; while (i < keys.length - 2 && p > keys[i + 1][0]) i++;
    const u = clamp((p - keys[i][0]) / (keys[i + 1][0] - keys[i][0]), 0, 1);
    return (i + u * u * (3 - 2 * u)) / (keys.length - 1);
  };

  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.8, 0.45, 0.32);  // only bright things glow, not the labels
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  let W = 0, H = 0, lastLens = -1;
  function size() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (w === W && h === H) return;
    W = w; H = h;
    renderer.setSize(w, h, false); composer.setSize(w, h);
    camera.aspect = w / h;
    if (w > 860) camera.setViewOffset(w, h, -w * 0.2, 0, w, h);  // action on the right, words on the left
    else camera.setViewOffset(w, h, 0, -h * 0.17, w, h);       // phones: words on top, action below
    camera.updateProjectionMatrix();
  }

  const v = new THREE.Vector3(), tg = new THREE.Vector3(), UP = new THREE.Vector3(0, 1, 0);
  // p: the story (0..1 through the hero). e: the epilogue (0..1 through the rest of the page), a slow orbit of the result.
  function render(p, tc, now = 0, e = 0) {
    size();
    const j = clamp(Math.round(tc * 240), 0, n - 1);
    ball.position.set(X(D.t[j]), Y(D.y[j]), 0);
    let k = 0; while (k < S.length && S[k] < j) k++;
    if (flashes.count !== k) flashes.count = k;
    D.rivals.forEach((r, q) => {
      const a0 = 0.47 + q * 0.03;
      const a = sstep(p, a0, a0 + 0.012) * (1 - 0.85 * sstep(p, a0 + 0.022, a0 + 0.03)) * (1 - sstep(p, 0.84, 0.9));
      rivals[q].material.opacity = 0.55 * a; rivals[q].visible = a > 0.01;
    });
    law.geometry.setDrawRange(0, Math.floor(law.geometry.index.count * sstep(p, 0.585, 0.63) / 3) * 3);
    ahead.geometry.setDrawRange(0, Math.round(dots.length * sstep(p, 0.63, 0.67)));
    const wa = sstep(p, 0.42, 0.46);
    wallMat.opacity = 0.05 * wa; edge.material.opacity = 0.4 * wa; lf.material.opacity = ln.material.opacity = wa;
    const gi = sstep(p, 0.64, 0.71);
    ghosts.forEach((g, q) => { g.scale.setScalar(clamp(gi * ghosts.length - q, 0, 1)); g.lookAt(camera.position); });
    lmat.opacity = gi; ll.material.opacity = gi;
    stream.rotation.y = now * 0.0000105;  // one turn every ten minutes
    posPath.getPoint(along(p), v); tgtPath.getPoint(along(p), tg);
    const drift = Math.sin(now / 4200) * 0.06;  // the camera breathes at rest
    const back = camera.aspect < 1 ? Math.min(2.4, 1.1 / camera.aspect) : 1;  // portrait screens: pull back so the arc fits
    v.sub(tg).multiplyScalar(back);
    if (e > 0) { v.applyAxisAngle(UP, e * Math.PI * 1.15); v.y += e * 2.2; v.multiplyScalar(1 + e * 0.2); }
    v.add(tg);
    renderer.toneMappingExposure = 1 - 0.45 * sstep(e, 0, 0.06);  // dims behind the sections so words stay readable
    camera.position.set(v.x + drift, v.y + drift * 0.5, v.z);
    camera.lookAt(tg);
    const flash = clamp(1 - Math.abs(camera.position.x - xs) / 0.4, 0, 1) * sstep(p, 0.66, 0.7) * (1 - sstep(p, 0.76, 0.8));
    bloom.strength = 0.8 + flash * 0.9;
    if (lens && Math.abs(flash - lastLens) > 0.01) { lens.style.opacity = (flash * 0.28).toFixed(3); lastLens = flash; }
    composer.render();
  }

  window.KTP3D = { render };
  document.documentElement.classList.add("gl");
  dispatchEvent(new Event("ktp3d"));
}
init().catch(() => {});  // any failure leaves the 2D hero in place
