/* Ordered-dither renderer for the hero.
 *
 * Frames are pre-extracted at 11fps and 384px wide (see build-frames.sh). All the
 * per-pixel work happens on a downscaled buffer whose cells map 1:1 to output
 * dots, so cost tracks dot count, not canvas pixels.
 */

const FRAME_COUNT = 66;
const FRAME_SRC = (i) => `frames/${String(i + 1).padStart(3, '0')}.webp`;

const CFG = {
  fps: 11,
  pixelSize: 0, // 0 = pick from viewport width in resize()
  zoom: 1.7,
  focusX: 0.78, // crop past the bright wall so it is not behind the headline
  focusY: 0.5,
  spacing: 0.3, // fraction of each cell left as gap
  dotScale: 0.97, // dot radius as fraction of the remaining cell
  levels: 5,
  gamma: 1, // <1 lifts shadows, >1 deepens them; tuning knob for other sources
  contrast: 38,
  brightness: 8,
  invert: false, // source is light pages on a dark ground, so dots land on the pages
  floor: 0.02, // tones below this go to zero, killing background haze
  colorMix: 0.3, // weight of the sampled source colour vs. the scheme ink
  ink: [232, 220, 195],
  fadeFrames: 9, // length of the wrap crossfade
  warpRadius: 0.6, // fraction of the canvas diagonal-ish extent
  lean: 3.4, // horizontal displacement at full strength, in cells
  lift: 2.1,
};

/* 8x8 Bayer, built by recursing the 2x2 into each quadrant twice. */
function bayer(n) {
  let m = [[0, 2], [3, 1]];
  while (m.length < n) {
    const s = m.length;
    const next = Array.from({ length: s * 2 }, () => new Array(s * 2));
    for (let y = 0; y < s; y++) {
      for (let x = 0; x < s; x++) {
        const v = m[y][x] * 4;
        next[y][x] = v;
        next[y][x + s] = v + 2;
        next[y + s][x] = v + 3;
        next[y + s][x + s] = v + 1;
      }
    }
    m = next;
  }
  return m;
}

const BAYER = bayer(8);
const BAYER_N = 64;

/* Any numeric CFG key can be overridden from the query string while tuning,
 * e.g. ?gamma=0.7&pixelSize=11&invert=1 */
const QS = new URLSearchParams(location.search);
if (QS.get('bare') === '1') document.documentElement.classList.add('is-bare');
for (const [k, v] of QS) {
  if (!(k in CFG)) continue;
  if (typeof CFG[k] === 'boolean') CFG[k] = v === '1' || v === 'true';
  else if (typeof CFG[k] === 'number' && v !== '' && !Number.isNaN(Number(v))) CFG[k] = Number(v);
}

const smoothstep = (t) => t * t * (3 - 2 * t);
const clamp01 = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);

function loadFrames() {
  return Promise.all(
    Array.from({ length: FRAME_COUNT }, (_, i) => new Promise((resolve) => {
      const img = new Image();
      img.decoding = 'async';
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      img.src = FRAME_SRC(i);
    })),
  ).then((frames) => frames.filter(Boolean));
}

/* Cover-fit source rect: which part of the frame to sample so it fills the
 * target aspect without distortion. zoom > 1 crops in; focus picks which part of
 * the frame survives the crop, so the busiest area can be kept clear of the type. */
function coverRect(sw, sh, tw, th) {
  const scale = Math.max(tw / sw, th / sh) * CFG.zoom;
  const w = Math.min(sw, tw / scale);
  const h = Math.min(sh, th / scale);
  return [(sw - w) * CFG.focusX, (sh - h) * CFG.focusY, w, h];
}

/* Auto-levels computed once, off a fixed small render, then pinned for the whole
 * sequence. Recomputing per frame makes the dot density pulse. */
function pinLevels(frames) {
  // Sample the same crop the renderer will show, or the percentiles come from
  // pixels that get cropped away and the whole field renders too dark.
  const W = 192;
  const H = 108;
  const c = document.createElement('canvas');
  c.width = W;
  c.height = H;
  const ctx = c.getContext('2d', { willReadFrequently: true });
  const hist = new Float64Array(256);
  let total = 0;

  const sampleAt = [0, 0.25, 0.5, 0.75, 0.95];
  for (const t of sampleAt) {
    const f = frames[Math.min(frames.length - 1, Math.round(t * (frames.length - 1)))];
    const [sx, sy, sw, sh] = coverRect(f.naturalWidth, f.naturalHeight, W, H);
    ctx.drawImage(f, sx, sy, sw, sh, 0, 0, W, H);
    const d = ctx.getImageData(0, 0, W, H).data;
    for (let i = 0; i < d.length; i += 4) {
      const l = 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
      hist[Math.round(l)] += 1;
      total += 1;
    }
  }

  const pct = (p) => {
    const want = total * p;
    let acc = 0;
    for (let i = 0; i < 256; i++) {
      acc += hist[i];
      if (acc >= want) return i / 255;
    }
    return 1;
  };

  const lo = pct(0.02);
  const hi = pct(0.98);
  return { lo, span: Math.max(1e-3, hi - lo) };
}

function start(frames) {
  const canvas = document.getElementById('dither');
  const ctx = canvas.getContext('2d', { alpha: false });
  const buf = document.createElement('canvas');
  const bctx = buf.getContext('2d', { willReadFrequently: true });

  const levels = pinLevels(frames);
  const contrastFactor = Math.pow((CFG.contrast + 100) / 100, 2);
  const brightness = CFG.brightness / 100;
  const ground = getComputedStyle(document.documentElement)
    .getPropertyValue('--ground').trim() || '#0c0a08';

  let cols = 0;
  let rows = 0;
  let cell = 0;
  let dpr = 1;
  let pixelSize = 9;
  let pixels = null;
  let dirty = true;

  const pointer = { x: -1e4, y: -1e4, tx: -1e4, ty: -1e4, active: false };

  function resize() {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (!w || !h) return;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    // Finer grid on narrow viewports, or the subject stops reading as itself.
    pixelSize = CFG.pixelSize || (w < 640 ? 5 : w < 1100 ? 7 : 8);
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    cell = pixelSize * dpr;
    cols = Math.ceil(canvas.width / cell);
    rows = Math.ceil(canvas.height / cell);
    buf.width = cols;
    buf.height = rows;
    dirty = true;
  }

  function readFrame(index, blendIndex, blendAlpha) {
    const f = frames[index];
    const [sx, sy, sw, sh] = coverRect(f.naturalWidth, f.naturalHeight, cols, rows);
    bctx.globalAlpha = 1;
    bctx.drawImage(f, sx, sy, sw, sh, 0, 0, cols, rows);
    if (blendAlpha > 0 && blendIndex != null) {
      const g = frames[blendIndex];
      bctx.globalAlpha = blendAlpha;
      bctx.drawImage(g, sx, sy, sw, sh, 0, 0, cols, rows);
      bctx.globalAlpha = 1;
    }
    pixels = bctx.getImageData(0, 0, cols, rows).data;
  }

  function draw() {
    if (!pixels) return;
    ctx.fillStyle = ground;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const radiusPx = Math.max(canvas.width, canvas.height) * CFG.warpRadius;
    const radiusCells = radiusPx / cell;
    const px = pointer.x / cell;
    const py = pointer.y / cell;
    const warping = pointer.active;

    const maxR = (cell * (1 - CFG.spacing)) / 2 * CFG.dotScale;
    const buckets = new Map();

    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        let sxc = x;
        let syc = y;

        if (warping) {
          const ddx = x - px;
          const ddy = y - py;
          const d = Math.hypot(ddx, ddy);
          if (d < radiusCells) {
            const f = smoothstep(1 - d / radiusCells);
            // Horizontal lean away from the pointer, plus a slight lift. Sampling
            // coords move, not the drawn output, so the warp is free per frame.
            const ux = Math.max(-1, Math.min(1, ddx / (radiusCells * 0.35)));
            sxc = x - ux * f * CFG.lean;
            syc = y + f * CFG.lift;
          }
        }

        const bx = Math.max(0, Math.min(cols - 1, Math.round(sxc)));
        const by = Math.max(0, Math.min(rows - 1, Math.round(syc)));
        const i = (by * cols + bx) * 4;
        const r = pixels[i];
        const g = pixels[i + 1];
        const b = pixels[i + 2];

        let v = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
        v = clamp01((v - levels.lo) / levels.span);
        if (CFG.gamma !== 1) v = Math.pow(v, CFG.gamma);
        v = (v - 0.5) * contrastFactor + 0.5 + brightness;
        if (CFG.invert) v = 1 - v;
        v = clamp01(v);
        if (v < CFG.floor) continue;

        const t = (BAYER[y & 7][x & 7] + 0.5) / BAYER_N - 0.5;
        const lvl = Math.min(CFG.levels - 1, Math.round(v * (CFG.levels - 1) + t));
        if (lvl <= 0) continue;

        const m = CFG.colorMix;
        const cr = (r * m + CFG.ink[0] * (1 - m)) & 0xf8;
        const cg = (g * m + CFG.ink[1] * (1 - m)) & 0xf8;
        const cb = (b * m + CFG.ink[2] * (1 - m)) & 0xf8;
        const key = (lvl << 24) | (cr << 16) | (cg << 8) | cb;

        let bucket = buckets.get(key);
        if (!bucket) {
          bucket = [];
          buckets.set(key, bucket);
        }
        bucket.push(x, y);
      }
    }

    for (const [key, cellsList] of buckets) {
      const lvl = key >>> 24;
      const cr = (key >> 16) & 0xff;
      const cg = (key >> 8) & 0xff;
      const cb = key & 0xff;
      const radius = maxR * (lvl / (CFG.levels - 1));
      if (radius < 0.25) continue;
      ctx.fillStyle = `rgb(${cr},${cg},${cb})`;
      ctx.beginPath();
      for (let i = 0; i < cellsList.length; i += 2) {
        const cx = cellsList[i] * cell + cell / 2;
        const cy = cellsList[i + 1] * cell + cell / 2;
        ctx.moveTo(cx + radius, cy);
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      }
      ctx.fill();
    }
  }

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const frameMs = 1000 / CFG.fps;
  // The played range starts after the crossfade head: frames [0, fadeFrames) only
  // ever appear blended into the tail, which is what makes the wrap invisible.
  const fade = frames.length > CFG.fadeFrames * 2 ? CFG.fadeFrames : 0;
  const loopStart = fade;
  const loopLen = frames.length - loopStart;
  const tailStart = frames.length - fade;
  let frameIndex = loopStart;
  let lastAdvance = performance.now();
  let lastDrawn = -1;

  function tick(now) {
    if (!reduced && now - lastAdvance >= frameMs) {
      const steps = Math.floor((now - lastAdvance) / frameMs);
      frameIndex = loopStart + ((frameIndex - loopStart + steps) % loopLen);
      lastAdvance += steps * frameMs;
      dirty = true;
    }

    // Ease the pointer so the field lags slightly behind the cursor.
    if (pointer.active) {
      const nx = pointer.x + (pointer.tx - pointer.x) * 0.12;
      const ny = pointer.y + (pointer.ty - pointer.y) * 0.12;
      if (Math.abs(nx - pointer.x) > 0.3 || Math.abs(ny - pointer.y) > 0.3) dirty = true;
      pointer.x = nx;
      pointer.y = ny;
    }

    if (dirty) {
      if (frameIndex !== lastDrawn) {
        // Turbulent motion has no true loop point, so dissolve the tail back
        // into the opening frames instead of hunting for a seam.
        let blendIndex = null;
        let blendAlpha = 0;
        if (fade && frameIndex >= tailStart) {
          const k = frameIndex - tailStart;
          blendIndex = k;
          blendAlpha = (k + 1) / fade;
        }
        readFrame(frameIndex, blendIndex, blendAlpha);
        lastDrawn = frameIndex;
      }
      draw();
      dirty = false;
    }
    requestAnimationFrame(tick);
  }

  const onMove = (e) => {
    const rect = canvas.getBoundingClientRect();
    pointer.tx = (e.clientX - rect.left) * dpr;
    pointer.ty = (e.clientY - rect.top) * dpr;
    if (!pointer.active) {
      pointer.x = pointer.tx;
      pointer.y = pointer.ty;
      pointer.active = true;
    }
    dirty = true;
  };

  window.addEventListener('pointermove', (e) => {
    if (e.pointerType === 'touch') return;
    onMove(e);
  }, { passive: true });

  window.addEventListener('pointerleave', () => {
    pointer.active = false;
    dirty = true;
  }, { passive: true });

  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      resize();
      lastDrawn = -1;
    }, 120);
  });

  resize();
  readFrame(loopStart, null, 0);
  lastDrawn = loopStart;
  draw();
  canvas.classList.add('is-ready');
  requestAnimationFrame(tick);
}

loadFrames().then((frames) => {
  if (frames.length) start(frames);
});
