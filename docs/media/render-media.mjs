// Renders docs/media/src/*.html to PNGs and the demo GIF.
// Needs: Node 18+, playwright (with Chromium), and ffmpeg on PATH.
// Usage: node docs/media/render-media.mjs   (from the repository root)
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import { mkdirSync, rmSync, readdirSync } from 'node:fs';
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
const FPS = 12;
const browser = await chromium.launch();

for (const [name, w, h] of stills) {
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2 });
  await page.goto(pathToFileURL(path.join(src, `${name}.html`)).href);
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: path.join(media, `${name}.png`) });
  await page.close();
}

const frames = path.join(media, '.frames');
rmSync(frames, { recursive: true, force: true });
mkdirSync(frames);
const page = await browser.newPage({ viewport: { width: 960, height: 540 }, deviceScaleFactor: 1 });
await page.goto(pathToFileURL(path.join(src, 'demo.html')).href + '#static');
await page.evaluate(() => document.fonts.ready);
const duration = await page.evaluate(() => window.DURATION);
const total = Math.round((duration + 1.5) * FPS);
for (let i = 0; i < total; i++) {
  await page.evaluate((t) => window.render(Math.min(t, window.DURATION)), i / FPS);
  await page.screenshot({ path: path.join(frames, `f${String(i).padStart(4, '0')}.png`) });
}
await browser.close();

const palette = path.join(frames, 'palette.png');
const input = ['-framerate', String(FPS), '-i', path.join(frames, 'f%04d.png')];
execFileSync('ffmpeg', ['-y', ...input, '-vf', 'palettegen=max_colors=96:stats_mode=diff', palette], { stdio: 'ignore' });
execFileSync('ffmpeg', ['-y', ...input, '-i', palette, '-lavfi', 'paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle', '-loop', '0', path.join(media, 'demo.gif')], { stdio: 'ignore' });
execFileSync('ffmpeg', ['-y', ...input, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '24', '-movflags', '+faststart', path.join(media, 'demo.mp4')], { stdio: 'ignore' });
rmSync(frames, { recursive: true, force: true });
console.log(readdirSync(media).join('\n'));
