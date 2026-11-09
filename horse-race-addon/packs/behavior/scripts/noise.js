// Seeded 2D gradient noise. Pure JavaScript (no Minecraft imports) so it can be
// unit-tested / previewed with Node.js.

/**
 * 32-bit integer hash of a lattice point.
 * @param {number} ix @param {number} iz @param {number} seed
 */
function hash(ix, iz, seed) {
  let h = Math.imul(ix | 0, 0x27d4eb2d) ^ Math.imul(iz | 0, 0x165667b1) ^ Math.imul(seed | 0, 0x9e3779b1);
  h = Math.imul(h ^ (h >>> 15), 0x85ebca6b);
  h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35);
  h ^= h >>> 16;
  return h >>> 0;
}

/**
 * Uniform random number in [0, 1) for a lattice point.
 * @param {number} ix @param {number} iz @param {number} seed
 */
export function rand01(ix, iz, seed) {
  return hash(ix, iz, seed) / 4294967296;
}

/** @type {[number, number][]} */
const GRAD = [];
for (let i = 0; i < 16; i++) {
  const a = (i / 16) * Math.PI * 2;
  GRAD.push([Math.cos(a), Math.sin(a)]);
}

/** @param {number} t */
function fade(t) {
  return t * t * t * (t * (t * 6 - 15) + 10);
}

/**
 * Perlin-style gradient noise, roughly in [-0.7, 0.7].
 * @param {number} x @param {number} z @param {number} seed
 */
export function perlin(x, z, seed) {
  const x0 = Math.floor(x);
  const z0 = Math.floor(z);
  const fx = x - x0;
  const fz = z - z0;
  const g00 = GRAD[hash(x0, z0, seed) & 15];
  const g10 = GRAD[hash(x0 + 1, z0, seed) & 15];
  const g01 = GRAD[hash(x0, z0 + 1, seed) & 15];
  const g11 = GRAD[hash(x0 + 1, z0 + 1, seed) & 15];
  const n00 = g00[0] * fx + g00[1] * fz;
  const n10 = g10[0] * (fx - 1) + g10[1] * fz;
  const n01 = g01[0] * fx + g01[1] * (fz - 1);
  const n11 = g11[0] * (fx - 1) + g11[1] * (fz - 1);
  const u = fade(fx);
  const v = fade(fz);
  const a = n00 + (n10 - n00) * u;
  const b = n01 + (n11 - n01) * u;
  return a + (b - a) * v;
}

/**
 * Fractal noise normalised to roughly [0, 1] (mean 0.5).
 * @param {number} x @param {number} z @param {number} seed @param {number} [octaves]
 */
export function fbm(x, z, seed, octaves = 2) {
  let sum = 0;
  let amp = 1;
  let norm = 0;
  let f = 1;
  for (let i = 0; i < octaves; i++) {
    sum += amp * perlin(x * f, z * f, seed + i * 1013);
    norm += amp;
    amp *= 0.5;
    f *= 2.03;
  }
  const v = 0.5 + (sum / norm) * 0.75;
  return v < 0 ? 0 : v > 1 ? 1 : v;
}

/** @param {number} e0 @param {number} e1 @param {number} x */
export function smoothstep(e0, e1, x) {
  const t = Math.max(0, Math.min(1, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
}
