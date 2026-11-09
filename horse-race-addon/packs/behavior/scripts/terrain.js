// Turns a flat world into a desert / badlands landscape chunk by chunk around
// players. Works on the classic "Flat" world (grass) and on the bundled desert
// flat world template. Normal worlds are left untouched.
import { system, world, BlockVolume, ListBlockVolume } from "@minecraft/server";
import { S, markDirty } from "./state.js";
import { overworld, perm, safe } from "./util.js";
import { computeChunk, FILL_ORDER } from "./terrain_gen.js";

/** @typedef {import("@minecraft/server").Dimension} Dimension */
/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").BlockPermutation} BlockPermutation */

/** Logical block names used by terrain_gen.js -> real block ids (with fallbacks). */
const BLOCKS = {
  sand: { ids: ["minecraft:sand"] },
  red_sand: { ids: ["minecraft:red_sand", "minecraft:sand"] },
  grass: { ids: ["minecraft:grass_block", "minecraft:grass"] },
  water: { ids: ["minecraft:water"] },
  log: { ids: ["minecraft:jungle_log"], states: { pillar_axis: "y" } },
  leaves: { ids: ["minecraft:jungle_leaves"], states: { persistent_bit: true } },
  cactus: { ids: ["minecraft:cactus"] },
  cactus_flower: { ids: ["minecraft:cactus_flower"] },
  reeds: { ids: ["minecraft:reeds"] },
  short_grass: { ids: ["minecraft:short_grass", "minecraft:tallgrass"] },
  fern: { ids: ["minecraft:fern", "minecraft:short_grass"] },
  deadbush: { ids: ["minecraft:deadbush"] },
  dry_short: { ids: ["minecraft:short_dry_grass", "minecraft:deadbush"] },
  dry_tall: { ids: ["minecraft:tall_dry_grass", "minecraft:deadbush"] },
  orange_terracotta: { ids: ["minecraft:orange_terracotta", "minecraft:hardened_clay"] },
  hardened_clay: { ids: ["minecraft:hardened_clay"] },
  yellow_terracotta: { ids: ["minecraft:yellow_terracotta", "minecraft:hardened_clay"] },
  white_terracotta: { ids: ["minecraft:white_terracotta", "minecraft:hardened_clay"] },
  red_terracotta: { ids: ["minecraft:red_terracotta", "minecraft:hardened_clay"] },
  brown_terracotta: { ids: ["minecraft:brown_terracotta", "minecraft:hardened_clay"] },
  light_gray_terracotta: { ids: ["minecraft:light_gray_terracotta", "minecraft:hardened_clay"] },
};

/** @param {string} key */
function blockFor(key) {
  const b = /** @type {Record<string, {ids:string[], states?:Record<string, string|number|boolean>}>} */ (BLOCKS)[key];
  if (!b) return undefined;
  return perm(b.ids, b.states);
}

/**
 * Marker written into the bedrock layer of decorated chunks: bedrock with the
 * (otherwise unused) infiniburn bit, or a barrier block as a fallback.
 */
function markerPerm() {
  return perm("minecraft:bedrock", { infiniburn_bit: true }) ?? perm("minecraft:barrier");
}

/** @param {BlockPermutation} p */
function isMarker(p) {
  if (p.type.id === "minecraft:barrier") return true;
  if (p.type.id !== "minecraft:bedrock") return false;
  try {
    return p.getState("infiniburn_bit") === true;
  } catch {
    return false;
  }
}

/** @type {Set<string>} chunks known to be decorated (this session) */
const done = new Set();
/** @type {{cx:number, cz:number, pri:number}[]} */
let queue = [];
/** @type {Set<string>} */
const queued = new Set();
let jobRunning = false;
export const terrainStats = { decorated: 0, skipped: 0, msTotal: 0, lastMs: 0 };

export function terrainActive() {
  const t = S.meta.terrain;
  return !!(S.settings.terrain && t && t.mode === "flat");
}

/**
 * Detect whether the world is a flat world we can decorate. Called until it succeeds.
 * @param {Player} player
 * @returns {boolean} true when detection finished (either way)
 */
export function detectTerrain(player) {
  if (S.meta.terrain) return true;
  if (player.dimension.id !== "minecraft:overworld") return false;
  return detectTerrainAt(player.dimension, player.location);
}

/**
 * @param {Dimension} dim
 * @param {{x:number, z:number}} loc
 * @returns {boolean} true when detection finished
 */
export function detectTerrainAt(dim, loc) {
  const px = Math.floor(loc.x);
  const pz = Math.floor(loc.z);
  /** @type {number[]} */
  const tops = [];
  /** @type {string[]} */
  const types = [];
  for (const [dx, dz] of [
    [0, 0],
    [8, 0],
    [0, 8],
    [-8, 0],
    [0, -8],
    [12, 12],
    [-12, -12],
  ]) {
    let b;
    try {
      b = dim.getTopmostBlock({ x: px + dx, z: pz + dz });
    } catch {
      return false;
    }
    if (!b) return false;
    tops.push(b.y);
    types.push(b.typeId);
  }
  const minY = dim.heightRange.min;
  // the most common height (players may stand next to a few placed blocks)
  /** @type {Map<number, number>} */
  const freq = new Map();
  for (const y of tops) freq.set(y, (freq.get(y) ?? 0) + 1);
  let y = tops[0];
  let best = 0;
  for (const [h, n] of freq) {
    if (n > best) {
      best = n;
      y = h;
    }
  }
  const sameTypes = types.filter((_, i) => tops[i] === y);
  let mode = /** @type {"flat"|"none"} */ ("none");
  let classic = false;
  if (best >= 5 && y < minY + 200) {
    if (sameTypes.every((t) => t === "minecraft:grass_block" || t === "minecraft:grass")) {
      mode = "flat";
      classic = true;
    } else if (sameTypes.every((t) => t === "minecraft:sand")) {
      mode = "flat";
    }
  }
  // a classic flat world has dirt right below the grass and bedrock 3 blocks down
  if (mode === "flat" && classic) {
    try {
      const below = dim.getBlock({ x: px, y: y - 1, z: pz });
      if (below && below.typeId !== "minecraft:dirt") mode = "none";
    } catch {
      /* ignore */
    }
  }
  S.meta.terrain = { mode, baseY: y, classic, seed: (Math.random() * 0x7fffffff) | 0 };
  markDirty("meta");
  console.warn(`[hrace] terrain detection: mode=${mode} baseY=${y} classic=${classic} tops=${tops.join(",")}`);
  return true;
}

/** Protected areas (start + checkpoints) are never decorated. */
function protectedAreas() {
  /** @type {{x:number, z:number, r2:number}[]} */
  const list = [];
  const r = S.race;
  if (r.start) list.push({ x: r.start.x, z: r.start.z, r2: 20 * 20 });
  else if (S.meta.start) list.push({ x: S.meta.start.x, z: S.meta.start.z, r2: 20 * 20 });
  for (const cp of r.checkpoints) list.push({ x: cp.x, z: cp.z, r2: 16 * 16 });
  return list;
}

/**
 * Queue chunks around players. Call every ~10 ticks.
 */
export function scheduleTerrain() {
  if (!terrainActive()) return;
  const radius = Math.max(2, Math.min(10, S.settings.terrainRadius | 0));
  let added = false;
  for (const p of world.getAllPlayers()) {
    if (p.dimension.id !== "minecraft:overworld") continue;
    const pcx = Math.floor(p.location.x / 16);
    const pcz = Math.floor(p.location.z / 16);
    const v = p.getVelocity();
    const sp = Math.hypot(v.x, v.z);
    const dx = sp > 0.05 ? v.x / sp : 0;
    const dz = sp > 0.05 ? v.z / sp : 0;
    for (let oz = -radius; oz <= radius; oz++) {
      for (let ox = -radius; ox <= radius; ox++) {
        const d2 = ox * ox + oz * oz;
        if (d2 > radius * radius + 1) continue;
        const cx = pcx + ox;
        const cz = pcz + oz;
        const key = cx + "," + cz;
        if (done.has(key) || queued.has(key)) continue;
        // chunks ahead of a moving player first
        const ahead = (ox * dx + oz * dz) / (Math.sqrt(d2) || 1);
        queue.push({ cx, cz, pri: Math.sqrt(d2) - ahead * 2.5 });
        queued.add(key);
        added = true;
      }
    }
  }
  if (added) queue.sort((a, b) => a.pri - b.pri);
  if (queue.length > 1500) {
    for (const q of queue.splice(1500)) queued.delete(q.cx + "," + q.cz);
  }
  if (done.size > 250000) done.clear();
  if (!jobRunning && queue.length) {
    jobRunning = true;
    system.runJob(terrainJob());
  }
}

function* terrainJob() {
  try {
    while (queue.length) {
      const item = /** @type {{cx:number, cz:number, pri:number}} */ (queue.shift());
      const key = item.cx + "," + item.cz;
      queued.delete(key);
      if (!terrainActive()) break;
      yield* processChunk(item.cx, item.cz);
      yield;
    }
  } finally {
    jobRunning = false;
  }
}

/**
 * @param {number} cx @param {number} cz
 */
function* processChunk(cx, cz) {
  const key = cx + "," + cz;
  const dim = overworld();
  const t = /** @type {import("./state.js").TerrainInfo} */ (S.meta.terrain);
  const minY = dim.heightRange.min;
  let markerBlock;
  try {
    markerBlock = dim.getBlock({ x: cx * 16, y: minY, z: cz * 16 });
  } catch {
    markerBlock = undefined;
  }
  if (!markerBlock) return; // not loaded; will be queued again later
  const marker = markerPerm();
  if (isMarker(markerBlock.permutation)) {
    done.add(key);
    terrainStats.skipped++;
    return;
  }
  const t0 = Date.now();
  const ok = yield* decorateChunk(dim, cx, cz, t);
  if (!ok) return;
  try {
    const mb = dim.getBlock({ x: cx * 16, y: minY, z: cz * 16 });
    if (mb && marker) mb.setPermutation(marker);
  } catch {
    return;
  }
  done.add(key);
  const ms = Date.now() - t0;
  terrainStats.decorated++;
  terrainStats.msTotal += ms;
  terrainStats.lastMs = ms;
}

/**
 * Decorate one chunk. Yields between fill operations.
 * @param {Dimension} dim
 * @param {number} cx @param {number} cz
 * @param {import("./state.js").TerrainInfo} t
 * @returns {Generator<void, boolean, void>}
 */
export function* decorateChunk(dim, cx, cz, t) {
  const x0 = cx * 16;
  const z0 = cz * 16;
  const base = t.baseY;
  try {
    if (t.classic) {
      // grass/dirt flat world -> sand over sandstone
      dim.fillBlocks(new BlockVolume({ x: x0, y: base - 2, z: z0 }, { x: x0 + 15, y: base - 1, z: z0 + 15 }), "minecraft:sandstone", {
        blockFilter: { includeTypes: ["minecraft:dirt"] },
      });
      dim.fillBlocks(new BlockVolume({ x: x0, y: base, z: z0 }, { x: x0 + 15, y: base, z: z0 + 15 }), "minecraft:sand", {
        blockFilter: { includeTypes: ["minecraft:grass_block", "minecraft:dirt"] },
      });
      yield;
    }
    // only protected circles that touch this chunk matter
    const prot = protectedAreas().filter((p) => {
      const nx = Math.max(x0 - 1, Math.min(p.x, x0 + 16));
      const nz = Math.max(z0 - 1, Math.min(p.z, z0 + 16));
      return (nx - p.x) ** 2 + (nz - p.z) ** 2 <= p.r2;
    });
    const lists = computeChunk(
      cx,
      cz,
      t.seed,
      base,
      prot.length === 0
        ? null
        : (x, z) => {
            for (const p of prot) {
              const dx = x - p.x;
              const dz = z - p.z;
              if (dx * dx + dz * dz <= p.r2) return true;
            }
            return false;
          },
    );
    yield;
    for (const key of FILL_ORDER) {
      const list = lists.get(key);
      if (!list || list.length === 0) continue;
      const block = blockFor(key);
      if (!block) continue;
      dim.fillBlocks(new ListBlockVolume(list), block);
      yield;
    }
  } catch (e) {
    console.warn(`[hrace] decorate ${cx},${cz} failed: ${e}`);
    return false;
  }
  // un-bury players standing in a chunk that just got dunes
  for (const p of dim.getPlayers()) {
    const l = p.location;
    if (Math.floor(l.x / 16) !== cx || Math.floor(l.z / 16) !== cz) continue;
    safe("unbury", () => {
      const feet = dim.getBlock({ x: Math.floor(l.x), y: Math.floor(l.y), z: Math.floor(l.z) });
      if (feet && !feet.isAir && !feet.isLiquid) {
        const top = dim.getTopmostBlock({ x: l.x, z: l.z });
        if (top) p.teleport({ x: l.x, y: top.y + 1, z: l.z });
      }
    });
  }
  return true;
}

/**
 * Ground height for a column. Uses the flat base when decoration is active.
 * @param {Dimension} dim
 * @param {number} x @param {number} z
 */
export function groundY(dim, x, z) {
  const top = dim.getTopmostBlock({ x, z });
  if (!top) return undefined;
  const t = S.meta.terrain;
  if (terrainActive() && t) return t.baseY;
  return top.y;
}

/** Forget cached chunk state (e.g. after changing settings). */
export function resetTerrainCache() {
  done.clear();
  queue = [];
  queued.clear();
}
