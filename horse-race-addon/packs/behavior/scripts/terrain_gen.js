// Pure terrain generator for the desert / badlands decoration.
// No Minecraft imports: used both in-game and by tools/terrain_preview.mjs.
import { fbm, rand01, smoothstep } from "./noise.js";

export const KIND = {
  SAND: 0, // desert sand dunes
  BADLANDS: 1, // red sand flats
  MESA: 2, // terracotta plateau
  WATER: 3, // oasis / lake water
  OASIS: 4, // grass ring around water
  KEEP: 5, // protected area (start / checkpoints): untouched
};

/** Terracotta band colours (by height above the base layer). */
export const BANDS = [
  "orange_terracotta",
  "hardened_clay",
  "yellow_terracotta",
  "orange_terracotta",
  "white_terracotta",
  "red_terracotta",
  "orange_terracotta",
  "brown_terracotta",
  "hardened_clay",
  "light_gray_terracotta",
  "orange_terracotta",
  "yellow_terracotta",
  "red_terracotta",
  "hardened_clay",
  "white_terracotta",
  "orange_terracotta",
];

const GRID = 4; // fields are sampled every 4 blocks and interpolated
const NF = 7; // number of noise fields

/**
 * @typedef {{zone:number, mesa:number, mesaH:number, oasis:number, wet:number, dune:number, roll:number}} Fields
 * @typedef {{h:number, kind:number, band:number}} Column
 */

/**
 * Write the 7 noise fields of (x, z) into arr[o..o+6].
 * @param {Float64Array} arr @param {number} o
 * @param {number} x @param {number} z @param {number} seed
 */
function fieldsInto(arr, o, x, z, seed) {
  arr[o] = fbm(x / 900, z / 900, seed + 11, 2); // zone: desert / badlands
  arr[o + 1] = fbm(x / 190, z / 190, seed + 23, 3); // mesa
  arr[o + 2] = fbm(x / 90, z / 90, seed + 31, 2); // mesa height / bands
  arr[o + 3] = fbm(x / 150, z / 150, seed + 41, 2); // oasis
  arr[o + 4] = fbm(x / 700, z / 700, seed + 43, 2); // wet region
  arr[o + 5] = fbm(x / 36, z / 36, seed + 53, 2); // dunes
  arr[o + 6] = fbm(x / 180, z / 180, seed + 59, 2); // rolling hills
}

// outputs of classifyRaw (avoids allocating an object per column)
let outH = 0;
let outBand = 0;

/**
 * Classify a column. Returns the kind; height and band are left in outH / outBand.
 * @param {number} zone @param {number} mesa @param {number} mesaH @param {number} oasis
 * @param {number} wet @param {number} dune @param {number} roll
 */
function classifyRaw(zone, mesa, mesaH, oasis, wet, dune, roll) {
  const bad = smoothstep(0.5, 0.6, zone); // 0 = desert, 1 = badlands
  outBand = Math.floor(mesaH * 4);
  const thr = 0.76 - 0.16 * bad; // mesas: rare in the desert, common in badlands
  if (mesa > thr) {
    const top = 6 + Math.floor(11 * mesaH);
    outH = mesa > thr + 0.03 ? top : Math.max(2, Math.floor(top * 0.45));
    return KIND.MESA;
  }
  // oases only appear in rare "wet" desert regions; bigger when the region is wetter.
  // Thresholds rise smoothly outside those regions so the ponds never get cut off.
  const ot = 0.72 - 0.08 * smoothstep(0.58, 0.75, wet) + 0.4 * (1 - smoothstep(0.5, 0.6, wet)) + 0.4 * smoothstep(0.1, 0.3, bad);
  if (oasis > ot + 0.035) {
    outH = oasis > ot + 0.085 ? -2 : -1;
    return KIND.WATER;
  }
  if (oasis > ot - 0.012) {
    outH = 0;
    return KIND.OASIS;
  }
  const d = Math.max(0, dune - 0.5) * 10 * (1 - 0.6 * bad);
  const r = Math.max(0, roll - 0.5) * 7;
  outH = Math.floor(d + r);
  return bad > 0.5 ? KIND.BADLANDS : KIND.SAND;
}

/**
 * Classify a column from its fields (used by the preview tool).
 * @param {Fields} f
 * @returns {Column}
 */
export function classify(f) {
  const kind = classifyRaw(f.zone, f.mesa, f.mesaH, f.oasis, f.wet, f.dune, f.roll);
  return { h: outH, kind, band: outBand };
}

/** Field sampler with a cache (used by the preview tool). */
export class FieldGrid {
  /** @param {number} seed */
  constructor(seed) {
    this.seed = seed;
    /** @type {Map<string, Float64Array>} */
    this.cache = new Map();
  }
  /** @param {number} gx @param {number} gz */
  point(gx, gz) {
    const k = gx + "," + gz;
    let f = this.cache.get(k);
    if (!f) {
      f = new Float64Array(NF);
      fieldsInto(f, 0, gx * GRID, gz * GRID, this.seed);
      this.cache.set(k, f);
    }
    return f;
  }
  /**
   * Bilinearly interpolated fields at a block column.
   * @param {number} x @param {number} z
   * @returns {Fields}
   */
  at(x, z) {
    const gx = Math.floor(x / GRID);
    const gz = Math.floor(z / GRID);
    const tx = (x - gx * GRID) / GRID;
    const tz = (z - gz * GRID) / GRID;
    const a = this.point(gx, gz);
    const b = this.point(gx + 1, gz);
    const c = this.point(gx, gz + 1);
    const d = this.point(gx + 1, gz + 1);
    const v = new Float64Array(NF);
    for (let i = 0; i < NF; i++) {
      const top = a[i] + (b[i] - a[i]) * tx;
      const bot = c[i] + (d[i] - c[i]) * tx;
      v[i] = top + (bot - top) * tz;
    }
    return { zone: v[0], mesa: v[1], mesaH: v[2], oasis: v[3], wet: v[4], dune: v[5], roll: v[6] };
  }
}

/**
 * @typedef {{x:number, y:number, z:number}} V3
 * @typedef {Map<string, V3[]>} BlockLists  key = logical block name
 */

/**
 * @param {BlockLists} lists
 * @param {string} key
 * @param {number} x @param {number} y @param {number} z
 */
function add(lists, key, x, y, z) {
  let l = lists.get(key);
  if (!l) {
    l = [];
    lists.set(key, l);
  }
  l.push({ x, y, z });
}

const GN = 7; // grid points per axis needed for one chunk plus a 1 block border
const V = new Float64Array(NF);

/** Grid points shared between neighbouring chunks are computed once. */
const pointCache = new Map();
let pointCacheSeed = NaN;

/**
 * Fields of grid point (gx, gz), cached.
 * @param {number} gx @param {number} gz @param {number} seed
 * @returns {Float64Array}
 */
function gridPoint(gx, gz, seed) {
  if (seed !== pointCacheSeed || pointCache.size > 40000) {
    pointCache.clear();
    pointCacheSeed = seed;
  }
  const key = (gx + 16777216) * 33554432 + (gz + 16777216);
  let f = pointCache.get(key);
  if (!f) {
    f = new Float64Array(NF);
    fieldsInto(f, 0, gx * GRID, gz * GRID, seed);
    pointCache.set(key, f);
  }
  return f;
}

/**
 * Compute every block change needed to decorate one chunk.
 * Multi-block features (palms) are kept fully inside the chunk.
 * @param {number} cx chunk x
 * @param {number} cz chunk z
 * @param {number} seed
 * @param {number} base y of the top layer of the flat world
 * @param {((x:number, z:number) => boolean)|null} isProtected
 * @returns {BlockLists}
 */
export function computeChunk(cx, cz, seed, base, isProtected) {
  const x0 = cx * 16;
  const z0 = cz * 16;
  const gx0 = Math.floor((x0 - 1) / GRID);
  const gz0 = Math.floor((z0 - 1) / GRID);
  const grid = new Float64Array(GN * GN * NF);
  for (let j = 0; j < GN; j++) {
    for (let i = 0; i < GN; i++) grid.set(gridPoint(gx0 + i, gz0 + j, seed), (j * GN + i) * NF);
  }
  // 18x18 columns including a one block border
  const H = new Int16Array(324);
  const K = new Int8Array(324);
  const B = new Int8Array(324);
  for (let lz = -1; lz <= 16; lz++) {
    const z = z0 + lz;
    const gz = Math.floor(z / GRID);
    const tz = (z - gz * GRID) / GRID;
    const j = gz - gz0;
    for (let lx = -1; lx <= 16; lx++) {
      const x = x0 + lx;
      const idx = (lz + 1) * 18 + (lx + 1);
      if (isProtected && isProtected(x, z)) {
        K[idx] = KIND.KEEP;
        H[idx] = 0;
        continue;
      }
      const gx = Math.floor(x / GRID);
      const tx = (x - gx * GRID) / GRID;
      const oa = (j * GN + (gx - gx0)) * NF;
      const ob = oa + NF;
      const oc = oa + GN * NF;
      const od = oc + NF;
      for (let f = 0; f < NF; f++) {
        const top = grid[oa + f] + (grid[ob + f] - grid[oa + f]) * tx;
        const bot = grid[oc + f] + (grid[od + f] - grid[oc + f]) * tx;
        V[f] = top + (bot - top) * tz;
      }
      K[idx] = classifyRaw(V[0], V[1], V[2], V[3], V[4], V[5], V[6]);
      H[idx] = outH;
      B[idx] = outBand;
    }
  }

  /** @type {BlockLists} */
  const lists = new Map();
  for (let lz = 0; lz < 16; lz++) {
    for (let lx = 0; lx < 16; lx++) {
      const idx = (lz + 1) * 18 + (lx + 1);
      const kind = K[idx];
      if (kind === KIND.KEEP) continue;
      const h = H[idx];
      const x = x0 + lx;
      const z = z0 + lz;
      // ground layer
      if (kind === KIND.BADLANDS || kind === KIND.MESA) add(lists, "red_sand", x, base, z);
      else if (kind === KIND.OASIS) add(lists, "grass", x, base, z);
      // relief
      if (kind === KIND.MESA) {
        const band = B[idx];
        for (let y = base + 1; y < base + h; y++) add(lists, BANDS[(y - base + band) % BANDS.length], x, y, z);
        add(lists, "red_sand", x, base + h, z);
      } else if (h > 0) {
        const mat = kind === KIND.BADLANDS ? "red_sand" : "sand";
        for (let y = base + 1; y <= base + h; y++) add(lists, mat, x, y, z);
      } else if (h < 0) {
        for (let y = base + h + 1; y <= base; y++) add(lists, "water", x, y, z);
      }
      // features
      const r = rand01(x, z, seed + 101);
      if (r > 0.03 && !(kind === KIND.OASIS && r < 0.63) && !(kind === KIND.OASIS && r > 0.94)) continue;
      const top = base + Math.max(0, h) + 1; // first air block above the column
      const r2 = rand01(x, z, seed + 202);
      const iE = idx + 1;
      const iW = idx - 1;
      const iS = idx + 18;
      const iN = idx - 18;
      const higherNeighbor =
        H[iE] > h || H[iW] > h || H[iS] > h || H[iN] > h || K[iE] === KIND.KEEP || K[iW] === KIND.KEEP || K[iS] === KIND.KEEP || K[iN] === KIND.KEEP;
      const waterNeighbor = K[iE] === KIND.WATER || K[iW] === KIND.WATER || K[iS] === KIND.WATER || K[iN] === KIND.WATER;
      if (kind === KIND.SAND) {
        if (r < 0.003 && !higherNeighbor) {
          const n = 1 + Math.floor(r2 * 3);
          for (let i = 0; i < n; i++) add(lists, "cactus", x, top + i, z);
          if (r2 > 0.8) add(lists, "cactus_flower", x, top + n, z);
        } else if (r < 0.01) add(lists, "deadbush", x, top, z);
        else if (r < 0.024) add(lists, "dry_short", x, top, z);
        else if (r < 0.03) add(lists, "dry_tall", x, top, z);
      } else if (kind === KIND.BADLANDS) {
        if (r < 0.014) add(lists, "deadbush", x, top, z);
        else if (r < 0.0155 && !higherNeighbor) {
          const n = 1 + Math.floor(r2 * 2);
          for (let i = 0; i < n; i++) add(lists, "cactus", x, top + i, z);
        }
      } else if (kind === KIND.MESA) {
        if (r < 0.012) add(lists, "deadbush", x, top, z);
      } else if (kind === KIND.OASIS) {
        const interior = lx >= 3 && lx <= 12 && lz >= 3 && lz <= 12;
        if (waterNeighbor && r < 0.35) {
          const n = 1 + Math.floor(r2 * 3);
          for (let i = 0; i < n; i++) add(lists, "reeds", x, top + i, z);
        } else if (interior && r > 0.94) {
          addPalm(lists, x, top, z, 5 + Math.floor(r2 * 3), r2 > 0.5);
        } else if (r < 0.55) add(lists, "short_grass", x, top, z);
        else if (r < 0.63) add(lists, "fern", x, top, z);
      }
    }
  }
  return lists;
}

/**
 * @param {BlockLists} lists
 * @param {number} x @param {number} y @param {number} z
 * @param {number} height
 * @param {boolean} flip
 */
function addPalm(lists, x, y, z, height, flip) {
  for (let i = 0; i < height; i++) add(lists, "log", x, y + i, z);
  const t = y + height - 1; // top log
  add(lists, "leaves", x, t + 1, z);
  const dirs = flip
    ? [
        [1, 0],
        [-1, 0],
        [0, 1],
        [0, -1],
      ]
    : [
        [1, 1],
        [-1, -1],
        [1, -1],
        [-1, 1],
      ];
  for (const [dx, dz] of [
    [1, 0],
    [-1, 0],
    [0, 1],
    [0, -1],
  ]) {
    add(lists, "leaves", x + dx, t + 1, z + dz);
  }
  for (const [dx, dz] of dirs) {
    add(lists, "leaves", x + dx, t, z + dz);
    add(lists, "leaves", x + 2 * dx, t, z + 2 * dz);
    add(lists, "leaves", x + 3 * dx, t - 1, z + 3 * dz);
  }
}

/** Order in which block lists are written (supports before plants). */
export const FILL_ORDER = [
  "sand",
  "red_sand",
  "grass",
  ...new Set(BANDS),
  "water",
  "log",
  "leaves",
  "cactus",
  "cactus_flower",
  "reeds",
  "short_grass",
  "fern",
  "deadbush",
  "dry_short",
  "dry_tall",
];
