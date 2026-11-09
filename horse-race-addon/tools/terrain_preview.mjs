// Render a top-down preview of the generated desert and print statistics.
// Usage: node tools/terrain_preview.mjs <out.png> [sizeBlocks=4096] [seed=12345] [blocksPerPixel=4] [centerX=0] [centerZ=0]
import { writeFileSync } from "node:fs";
import { deflateSync } from "node:zlib";
import { FieldGrid, classify, KIND, computeChunk } from "../packs/behavior/scripts/terrain_gen.js";

const out = process.argv[2] ?? "terrain_preview.png";
const size = Number(process.argv[3] ?? 4096);
const seed = Number(process.argv[4] ?? 12345);
const step = Number(process.argv[5] ?? 4); // blocks per pixel
const cxw = Number(process.argv[6] ?? 0);
const czw = Number(process.argv[7] ?? 0);

const W = Math.floor(size / step);
const img = Buffer.alloc(W * W * 3);
const grid = new FieldGrid(seed);
const counts = new Array(6).fill(0);
let steps2 = 0;
let pairs = 0;
let maxH = 0;
const half = size / 2;
const heights = new Float32Array(W * W);
for (let py = 0; py < W; py++) {
  for (let px = 0; px < W; px++) {
    const x = Math.floor(px * step - half + cxw);
    const z = Math.floor(py * step - half + czw);
    const c = classify(grid.at(x, z));
    counts[c.kind]++;
    maxH = Math.max(maxH, c.h);
    heights[py * W + px] = c.h;
    let r, g, b;
    switch (c.kind) {
      case KIND.MESA: {
        const t = Math.min(1, c.h / 16);
        r = 170 + 60 * t;
        g = 80 + 40 * t;
        b = 45;
        break;
      }
      case KIND.WATER:
        r = 40;
        g = 90;
        b = 200;
        break;
      case KIND.OASIS:
        r = 60;
        g = 160;
        b = 60;
        break;
      case KIND.BADLANDS:
        r = 190 - c.h * 6;
        g = 105 - c.h * 4;
        b = 60;
        break;
      default:
        r = 235 - c.h * 9;
        g = 210 - c.h * 9;
        b = 150 - c.h * 8;
    }
    const i = (py * W + px) * 3;
    img[i] = r;
    img[i + 1] = g;
    img[i + 2] = b;
  }
  if (grid.cache.size > 200000) grid.cache.clear();
}
// slope statistic on full-resolution columns along a few rows
const g2 = new FieldGrid(seed);
for (let z = -2000; z < 2000; z += 50) {
  let prev = classify(g2.at(-2000, z));
  for (let x = -1999; x < 2000; x++) {
    const c = classify(g2.at(x, z));
    if (c.kind !== KIND.MESA && prev.kind !== KIND.MESA) {
      pairs++;
      if (Math.abs(c.h - prev.h) >= 2) steps2++;
    }
    prev = c;
  }
  if (g2.cache.size > 200000) g2.cache.clear();
}

const total = W * W;
const names = ["sand", "badlands", "mesa", "water", "oasis", "keep"];
console.log(`area ${size}x${size} blocks, seed ${seed}`);
names.forEach((n, i) => console.log(`  ${n.padEnd(9)} ${((counts[i] / total) * 100).toFixed(2)}%`));
console.log(`  max height ${maxH}, >=2 block steps between neighbours (non-mesa): ${((steps2 / pairs) * 100).toFixed(3)}%`);

// timing of full chunk computation
const t0 = performance.now();
let blocks = 0;
for (let i = 0; i < 400; i++) {
  const lists = computeChunk(i % 20, Math.floor(i / 20), seed, 63, () => false);
  for (const l of lists.values()) blocks += l.length;
}
const dt = performance.now() - t0;
console.log(`  computeChunk: ${(dt / 400).toFixed(2)} ms/chunk (node), avg ${(blocks / 400).toFixed(0)} blocks/chunk`);

// --- tiny PNG encoder
function crc32(buf) {
  let c;
  const table = [];
  for (let n = 0; n < 256; n++) {
    c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c >>> 0;
  }
  let crc = 0xffffffff;
  for (const b of buf) crc = table[(crc ^ b) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const td = Buffer.concat([Buffer.from(type), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(td));
  return Buffer.concat([len, td, crc]);
}
const raw = Buffer.alloc((W * 3 + 1) * W);
for (let y = 0; y < W; y++) {
  raw[y * (W * 3 + 1)] = 0;
  img.copy(raw, y * (W * 3 + 1) + 1, y * W * 3, (y + 1) * W * 3);
}
const ihdr = Buffer.alloc(13);
ihdr.writeUInt32BE(W, 0);
ihdr.writeUInt32BE(W, 4);
ihdr[8] = 8;
ihdr[9] = 2;
const png = Buffer.concat([
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  chunk("IHDR", ihdr),
  chunk("IDAT", deflateSync(raw)),
  chunk("IEND", Buffer.alloc(0)),
]);
writeFileSync(out, png);
console.log(`wrote ${out} (${W}x${W})`);
