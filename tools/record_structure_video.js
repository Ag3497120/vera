#!/usr/bin/env node
/*
 * Record the two three.js pages of the Vera structure as short videos.
 *
 *   v1  a single stereo cross (a self-contained page)
 *   v2  the whole-structure overview (built by tools/build_structure_overview.py)
 *
 * Each page is driven in headless Chrome (puppeteer-core). The camera is set
 * programmatically for every frame (no real-time capture, so the result does
 * not depend on how fast the machine renders), a PNG is saved per frame, and
 * ffmpeg turns the frames into an H.264 mp4 and a palette-optimised GIF. A
 * combined mp4 (v1, cross-fade, v2) is made too.
 *
 *   NODE_PATH=<dir with node_modules/puppeteer-core> \
 *   node tools/record_structure_video.js \
 *       --v1 path/to/stereo-cross/index.html \
 *       --v2 path/to/structure-overview/index.html \
 *       [--out docs/media] [--only v1|v2|combine] [--fps 24] [--software]
 *
 * Options
 *   --out DIR        output directory (default docs/media next to this script's repo root)
 *   --chrome PATH    Chrome binary (default: Google Chrome.app on macOS)
 *   --only WHAT      v1, v2 or combine (default: all three; combine needs both mp4s)
 *   --fps N          capture frame rate (default 24); the GIF is always N/2
 *   --seconds-v1 N   length of the v1 clip (default 16)
 *   --seconds-v2 N   length of the v2 clip (default 18)
 *   --crf N          x264 quality for the mp4s (default 23; 28 is about half the size)
 *   --software       force software WebGL (--use-angle=swiftshader), slower
 *   --keep-ui        keep the page's own panels (default: hide them, show a caption)
 *   --frames DIR     keep the PNG frames in DIR (default: a temp dir, emptied afterwards)
 *
 * The pages need the network once for their CDN scripts (three.js).
 * ffmpeg must be on PATH (or /opt/homebrew/bin).
 */
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const puppeteer = require('puppeteer-core');

// ---------------------------------------------------------------- arguments
const argv = process.argv.slice(2);
const opt = {};
for (let i = 0; i < argv.length; i++) {
  if (!argv[i].startsWith('--')) continue;
  const k = argv[i].slice(2);
  const nxt = argv[i + 1];
  if (nxt === undefined || nxt.startsWith('--')) opt[k] = true; else { opt[k] = nxt; i++; }
}
const REPO = path.resolve(__dirname, '..');
const OUT = path.resolve(opt.out || path.join(REPO, 'docs', 'media'));
const CHROME = opt.chrome || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const FPS = Number(opt.fps || 24);
const W = 1280, H = 720;
const CRF = Number(opt.crf || 23);
const ONLY = opt.only || 'all';
const SEC = { v1: Number(opt['seconds-v1'] || 16), v2: Number(opt['seconds-v2'] || 18) };
const FFMPEG = process.env.FFMPEG || (fs.existsSync('/opt/homebrew/bin/ffmpeg') ? '/opt/homebrew/bin/ffmpeg' : 'ffmpeg');
fs.mkdirSync(OUT, { recursive: true });

const ease = x => { x = Math.min(1, Math.max(0, x)); return x * x * (3 - 2 * x); };
const lerp = (a, b, s) => a + (b - a) * s;
const sleep = ms => new Promise(r => setTimeout(r, ms));

// ---------------------------------------------------------------- page helpers
const CAPTION_CSS = `
#vcap{box-sizing:border-box;position:fixed;right:20px;bottom:18px;max-width:420px;text-align:right;pointer-events:none;z-index:99;
  font:600 22px/1.35 -apple-system,"Helvetica Neue",Arial,sans-serif;color:#e6edf6;
  background:rgba(8,12,20,.74);border:1px solid rgba(160,180,210,.28);border-radius:8px;padding:10px 16px;
  transition:none}
#vcap small{display:block;font:400 16px/1.4 -apple-system,"Helvetica Neue",Arial,sans-serif;color:#aab6c8;margin-top:3px}
`;
async function setCaption(page, head, sub) {
  await page.evaluate((h, s) => {
    let el = document.getElementById('vcap');
    if (!el) { el = document.createElement('div'); el.id = 'vcap'; document.body.appendChild(el); }
    el.innerHTML = '';
    el.appendChild(document.createTextNode(h));
    if (s) { const sm = document.createElement('small'); sm.textContent = s; el.appendChild(sm); }
  }, head, sub || '');
}
const raf2 = page => page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));

async function launch() {
  const args = ['--no-sandbox', '--hide-scrollbars', '--mute-audio', `--window-size=${W},${H}`];
  if (opt.software) args.push('--use-angle=swiftshader', '--enable-unsafe-swiftshader');
  else args.push('--ignore-gpu-blocklist', '--enable-webgl');
  return puppeteer.launch({ executablePath: CHROME, headless: true, args, defaultViewport: { width: W, height: H, deviceScaleFactor: 1 } });
}

function makeFrameDir(tag) {
  const base = opt.frames ? path.resolve(opt.frames) : fs.mkdtempSync(path.join(os.tmpdir(), 'vera-frames-'));
  const d = path.join(base, tag);
  fs.mkdirSync(d, { recursive: true });
  for (const f of fs.readdirSync(d)) if (f.endsWith('.png')) fs.unlinkSync(path.join(d, f));
  return d;
}
function cleanFrames(d) {
  if (opt.frames) return;
  for (const f of fs.readdirSync(d)) fs.unlinkSync(path.join(d, f));
  fs.rmdirSync(d);
  try { fs.rmdirSync(path.dirname(d)); } catch (e) { /* not empty */ }
}

function encode(frameDir, base) {
  const mp4 = path.join(OUT, base + '.mp4'), gif = path.join(OUT, base + '.gif');
  const inp = ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', path.join(frameDir, 'f_%05d.png')];
  execFileSync(FFMPEG, [...inp, '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', String(CRF), '-pix_fmt', 'yuv420p',
    '-vf', `scale=${W}:${H}`, '-movflags', '+faststart', mp4], { stdio: 'inherit' });
  // 640 px wide, 12 fps (every other frame), one global palette
  const gvf = `fps=${FPS / 2},scale=640:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle`;
  execFileSync(FFMPEG, [...inp, '-filter_complex', gvf, '-loop', '0', gif], { stdio: 'inherit' });
  return { mp4, gif };
}

// ---------------------------------------------------------------- v1: one stereo cross
// The page keeps its state in a closure, so a copy of its HTML is patched on
// load: it exposes the camera/toggle state as window.__v1 and lets us step the
// animation by an explicit dt (so frame N always shows time N / fps).
function patchV1(html) {
  const mark = '  // re-tint when the theme flips';
  if (html.split(mark).length !== 2) throw new Error('v1 page changed: re-tint marker not found exactly once');
  html = html.replace(mark, `  window.__v1 = { THREE, camera, groups, toggles, applyToggles, pickables,
    setPose: p => { orbit.theta = p.theta; orbit.phi = p.phi; orbit.r = p.r; target.set(p.tx, p.ty, p.tz); } };\n` + mark);
  const dtOld = 'const dt = Math.min(0.05, (now - t0)/1000); t0 = now;';
  if (!html.includes(dtOld)) throw new Error('v1 page changed: dt line not found');
  html = html.replace(dtOld, 'const dt = window.__dtq || 0; window.__dtq = 0; t0 = now;');
  return html;
}

// scene = what is switched on + where the camera looks (target tx,ty,tz and orbit radius r)
const V1_SCENES = [
  { t: 0.0, on: ['window', 'axes'], cap: ['One stereo cross', 'a centre and six arms, each arm a row of seats (real data: sentences 85-86)'], tg: [0, 0, 0], r: 13.5 },
  { t: 4.0, on: ['window', 'axes'], cap: ['A seat has provenance', 'gold = the accepted answer; hover shows its source sentence'], tg: [0, 0, 0], r: 11, hover: true },
  { t: 7.0, on: ['window', 'axes', 'flow'], cap: ['Edge flow', 'evidence counted along each inner edge'], tg: [0, 0, 0], r: 13.5 },
  { t: 9.5, on: ['window', 'axes', 'walk'], cap: ['Section walk', 'a walker steps through the cross, seat by seat'], tg: [0, 0, 0], r: 13.5 },
  { t: 12.0, on: ['window', 'axes', 'grammar'], cap: ['Grammar layer', 'particles as a cross of their own'], tg: [0, 2.0, 0], r: 14.5 },
  { t: 14.5, on: ['window', 'axes', 'layer'], cap: ['Nested layer', 'unstable crosses packed into a larger one'], tg: [3.5, 0.2, -1.0], r: 15.5 },
];
function v1Pose(t, T) {
  // pick the scene and cross-fade the target/radius between neighbours over 1.2 s
  const sc = V1_SCENES.map(x => ({ ...x, t: x.t * T / 17 }));      // scene times are written for 17 s
  let i = 0; while (i + 1 < sc.length && t >= sc[i + 1].t) i++;
  const cur = sc[i], prev = sc[Math.max(0, i - 1)];
  const s = i === 0 ? 1 : ease((t - cur.t) / 1.2);
  const tg = [0, 1, 2].map(k => lerp(prev.tg[k], cur.tg[k], s));
  const r = lerp(prev.r, cur.r, s);
  const ph = 2 * Math.PI * t / T;                      // one full turn, so the GIF loops
  return { theta: 0.55 + ph, phi: 1.05 + 0.16 * Math.sin(ph), r, tx: tg[0], ty: tg[1], tz: tg[2], scene: cur, idx: i };
}

async function recordV1(browser) {
  const src = path.resolve(opt.v1);
  const patched = path.join(path.dirname(src), '.record_v1.html');   // beside the source so relative assets work
  fs.writeFileSync(patched, patchV1(fs.readFileSync(src, 'utf8')));
  const page = await browser.newPage();
  const dir = makeFrameDir('v1');
  try {
    await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'dark' }]);
    await page.evaluateOnNewDocument(() => {            // deterministic walker start phases
      let s = 12345; Math.random = () => (s = (s * 1664525 + 1013904223) % 4294967296) / 4294967296;
    });
    await page.goto('file://' + patched, { waitUntil: 'networkidle0', timeout: 90000 });
    await page.waitForFunction('!!window.__v1', { timeout: 30000 });
    if (!opt['keep-ui']) await page.addStyleTag({ content: `.app{grid-template-columns:minmax(0,1fr)!important;grid-template-rows:minmax(0,1fr)!important;height:100vh!important}.stage{overflow:hidden}.panel{display:none!important}.hud .sub{display:none!important}` });
    await page.evaluate(() => window.dispatchEvent(new Event('resize')));
    await page.addStyleTag({ content: CAPTION_CSS });
    await sleep(500);

    const n = Math.round(SEC.v1 * FPS);
    let lastScene = -1;
    for (let f = 0; f < n; f++) {
      const t = f / FPS, p = v1Pose(t, SEC.v1);
      if (p.idx !== lastScene) {
        lastScene = p.idx;
        await page.evaluate(on => { const v = window.__v1; for (const k in v.toggles) v.toggles[k] = on.includes(k); v.applyToggles(); }, p.scene.on);
        await setCaption(page, p.scene.cap[0], p.scene.cap[1]);
      }
      await page.evaluate((pp) => { window.__v1.setPose(pp); window.__dtq = 1 / 24; }, p);
      await raf2(page);
      // hover the gold seat during the "provenance" scene so its tooltip shows
      let hx = 2, hy = 2;
      if (p.scene.hover) {
        const pos = await page.evaluate(() => {
          const v = window.__v1, m = v.pickables.find(o => o.userData && o.userData.gold);
          if (!m) return null;
          const c = document.getElementById('c').getBoundingClientRect();
          const q = new v.THREE.Vector3(); m.getWorldPosition(q); q.project(v.camera);
          return { x: c.left + (q.x + 1) / 2 * c.width, y: c.top + (1 - q.y) / 2 * c.height };
        });
        if (pos) { hx = pos.x; hy = pos.y; }
      }
      await page.mouse.move(hx, hy);
      await page.screenshot({ path: path.join(dir, `f_${String(f + 1).padStart(5, '0')}.png`), type: 'png' });
      if (f % 60 === 0) console.log(`v1 frame ${f}/${n}`);
    }
    const out = encode(dir, 'stereo_cross_v1');
    return out;
  } finally {
    await page.close();
    try { fs.unlinkSync(patched); } catch (e) { /* ignore */ }
    cleanFrames(dir);
  }
}

// ---------------------------------------------------------------- v2: whole-structure overview
// The page exposes window.__overview = {camera, controls, preset, ...}; each
// preset is a button of the page (Overview, Top down, RUN, Nests, Slide, Grammar).
const V2_SCENES = [
  { key: 'over', t: 0.0, cap: ['The whole structure', '592 sentences: RUN / WORD / CHAR crosses, nests, windows, grammar layer'] },
  { key: 'top', t: 2.5, cap: ['Top down', 'three sovereign tiers, the carry tower, the sliding windows'] },
  { key: 'RUN', t: 4.5, cap: ['RUN sovereign', 'one cross per unit, each placed to a stable state'] },
  { key: 'nest', t: 7.3, cap: ['Layer-1 nests', 'wireframe = a larger cross around its member crosses'] },
  { key: 'nestzoom', t: 9.3, cap: ['One nest, close up', 'the larger cross (wireframe) over the lower crosses it packs'] },
  { key: 'slide', t: 12.0, cap: ['Sliding windows', 'two neighbouring sentences of one article, read together'] },
  { key: 'gram', t: 14.8, cap: ['Grammar layer', 'particles around a centre, shared by all sentences'] },
  { key: 'over', t: 17.3, cap: ['The whole structure', 'same corpus + same question = same bytes'] },
];
function v2Pose(t, T, poses) {
  const sc = V2_SCENES.map(s => ({ ...s, t: s.t * T / 20 }));
  let i = 0; while (i + 1 < sc.length && t >= sc[i + 1].t) i++;
  const cur = poses[sc[i].key], prev = poses[sc[Math.max(0, i - 1)].key];
  const s = i === 0 ? 1 : ease((t - sc[i].t) / 1.4);
  const tg = [0, 1, 2].map(k => lerp(prev.tg[k], cur.tg[k], s));
  const r = Math.exp(lerp(Math.log(prev.r), Math.log(cur.r), s));
  const pitch = lerp(prev.pitch, cur.pitch, s);
  const sway = 12 * Math.sin(2 * Math.PI * t / T);       // yaw sway, zero at both ends so the loop closes
  const yaw = lerp(prev.yaw, cur.yaw, s) + sway;
  return { tg, r, pitch, yaw, near: lerp(prev.near, cur.near, s), far: lerp(prev.far, cur.far, s), scene: sc[i], idx: i };
}

async function recordV2(browser) {
  const page = await browser.newPage();
  const dir = makeFrameDir('v2');
  try {
    await page.goto('file://' + path.resolve(opt.v2), { waitUntil: 'networkidle0', timeout: 180000 });
    await page.waitForFunction('window.__ready === true', { timeout: 120000 });
    if (!opt['keep-ui']) await page.addStyleTag({ content: `#side,#controls,#legend,#stats,#hover{display:none!important}#app{grid-template-columns:1fr!important}` });
    await page.addStyleTag({ content: CAPTION_CSS });
    await sleep(800);                                      // ResizeObserver -> new aspect
    // read the camera pose of each preset once, after the layout is final
    const poses = await page.evaluate(keys => {
      const o = window.__overview, out = {};
      for (const k of keys) {
        if (k === 'nestzoom') {            // frame one RUN nest the way the page's #sel-<id> link does (box 30, pitch 40, yaw 10)
          const it = o.batches.find(b => b.name === 'nest-RUN').items[0], c0 = o.camera;
          const fov = c0.fov * Math.PI / 180, dist = 26 / Math.sin(Math.min(fov / 2, Math.atan(Math.tan(fov / 2) * c0.aspect)));
          const pt = 40 * Math.PI / 180, yw = 10 * Math.PI / 180;
          out[k] = { tg: it.pos.slice ? [...it.pos] : [it.pos.x, it.pos.y, it.pos.z], r: dist, pitch: pt, yaw: yw, near: Math.max(0.5, dist / 500), far: dist * 20 };
          continue;
        }
        o.preset[k]();
        const c = o.camera, tg = o.controls.target, dx = c.position.x - tg.x, dy = c.position.y - tg.y, dz = c.position.z - tg.z;
        const r = Math.hypot(dx, dy, dz);
        out[k] = { tg: [tg.x, tg.y, tg.z], r, pitch: Math.asin(dy / r), yaw: Math.atan2(dx, dz), near: c.near, far: c.far };
      }
      return out;
    }, [...new Set(V2_SCENES.map(s => s.key))]);

    poses.over.r *= 0.88;                                  // the page's Overview preset leaves a wide margin; fill more of the frame
    const n = Math.round(SEC.v2 * FPS);
    let lastScene = -1;
    for (let f = 0; f < n; f++) {
      const t = f / FPS, p = v2Pose(t, SEC.v2, poses);
      if (p.idx !== lastScene) { lastScene = p.idx; await setCaption(page, p.scene.cap[0], p.scene.cap[1]); }
      await page.evaluate(pp => {
        const o = window.__overview, c = o.camera;
        o.controls.target.set(pp.tg[0], pp.tg[1], pp.tg[2]);
        c.position.set(pp.tg[0] + pp.r * Math.cos(pp.pitch) * Math.sin(pp.yaw), pp.tg[1] + pp.r * Math.sin(pp.pitch), pp.tg[2] + pp.r * Math.cos(pp.pitch) * Math.cos(pp.yaw));
        c.near = pp.near; c.far = pp.far; c.updateProjectionMatrix();
        o.controls.update();
        o.renderer.render(o.scene, c);
      }, p);
      await raf2(page);
      await page.screenshot({ path: path.join(dir, `f_${String(f + 1).padStart(5, '0')}.png`), type: 'png' });
      if (f % 60 === 0) console.log(`v2 frame ${f}/${n}`);
    }
    return encode(dir, 'structure_overview_v2');
  } finally {
    await page.close();
    cleanFrames(dir);
  }
}

// ---------------------------------------------------------------- combined
function combine() {
  const a = path.join(OUT, 'stereo_cross_v1.mp4'), b = path.join(OUT, 'structure_overview_v2.mp4'), out = path.join(OUT, 'vera_structure.mp4');
  const dur = f => Number(execFileSync(FFMPEG.replace(/ffmpeg$/, 'ffprobe'),
    ['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', f]).toString());
  const xf = 0.6, d1 = dur(a);
  execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-i', a, '-i', b, '-filter_complex',
    `[0:v][1:v]xfade=transition=fade:duration=${xf}:offset=${(d1 - xf).toFixed(3)},format=yuv420p[v]`,
    '-map', '[v]', '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', String(CRF), '-movflags', '+faststart', out], { stdio: 'inherit' });
  return out;
}

// ---------------------------------------------------------------- main
(async () => {
  const todo1 = ONLY === 'all' || ONLY === 'v1', todo2 = ONLY === 'all' || ONLY === 'v2', todoC = ONLY === 'all' || ONLY === 'combine';
  if ((todo1 && !opt.v1) || (todo2 && !opt.v2)) { console.error('need --v1 and --v2 page paths'); process.exit(2); }
  if (todo1 || todo2) {
    const browser = await launch();
    try {
      console.log('chrome', await browser.version(), opt.software ? '(software WebGL)' : '');
      if (todo1) console.log(await recordV1(browser));
      if (todo2) console.log(await recordV2(browser));
    } finally { await browser.close(); }
  }
  if (todoC) console.log(combine());
})().catch(e => { console.error(e); process.exit(1); });
