// Renders docs/media/src/*.html to PNGs and the demo GIF/MP4.
// Needs: Node 18+, playwright (with Chromium), ffmpeg on PATH, and network
// access to Google Fonts (Barlow Condensed, IBM Plex Sans, IBM Plex Mono).
// Usage, from the repository root:
//   node docs/media/render-media.mjs            # everything
//   node docs/media/render-media.mjs hero demo  # selected pages
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import { mkdirSync, rmSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const media = path.resolve('docs/media');
const src = path.join(media, 'src');
const stills = [
  ['hero', 1280, 640],
  ['workflow', 1280, 600],
  ['checks', 1280, 700],
  ['families', 1280, 640],
  ['bundle', 1280, 640],
];
const only = process.argv.slice(2);
const want = (name) => only.length === 0 || only.includes(name);
const FPS = 12;
const proxy = process.env.HTTPS_PROXY || process.env.https_proxy;
const browser = await chromium.launch(proxy ? { proxy: { server: proxy } } : {});

async function open(name, width, height, scale, hash = '') {
  const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: scale });
  await page.goto(pathToFileURL(path.join(src, `${name}.html`)).href + hash, { waitUntil: 'networkidle' });
  const fonts = await page.evaluate(async () => {
    await document.fonts.ready;
    return ["600 20px 'Barlow Condensed'", "16px 'IBM Plex Sans'", "16px 'IBM Plex Mono'"].every((f) => document.fonts.check(f));
  });
  if (!fonts) throw new Error(`${name}: web fonts did not load; check network access to Google Fonts`);
  return page;
}

for (const [name, w, h] of stills) {
  if (!want(name)) continue;
  const page = await open(name, w, h, 2);
  await page.screenshot({ path: path.join(media, `${name}.png`) });
  await page.close();
}

if (want('demo')) {
  const frames = path.join(media, '.frames');
  rmSync(frames, { recursive: true, force: true });
  mkdirSync(frames);
  const page = await open('demo', 960, 540, 1, '#static');
  const duration = await page.evaluate(() => window.DURATION);
  const total = Math.round((duration + 1.5) * FPS);
  for (let i = 0; i < total; i++) {
    await page.evaluate((t) => window.render(Math.min(t, window.DURATION)), i / FPS);
    await page.screenshot({ path: path.join(frames, `f${String(i).padStart(4, '0')}.png`) });
  }
  const palette = path.join(frames, 'palette.png');
  const input = ['-framerate', String(FPS), '-i', path.join(frames, 'f%04d.png')];
  execFileSync('ffmpeg', ['-y', ...input, '-vf', 'palettegen=max_colors=64:stats_mode=diff', palette], { stdio: 'ignore' });
  execFileSync('ffmpeg', ['-y', ...input, '-i', palette, '-lavfi', 'paletteuse=dither=none:diff_mode=rectangle', '-loop', '0', path.join(media, 'demo.gif')], { stdio: 'ignore' });
  execFileSync('ffmpeg', ['-y', ...input, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '22', '-movflags', '+faststart', path.join(media, 'demo.mp4')], { stdio: 'ignore' });
  rmSync(frames, { recursive: true, force: true });
}
await browser.close();
