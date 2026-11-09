// Persistent game state stored in world dynamic properties.
import { world } from "@minecraft/server";
import { DEFAULT_SETTINGS, DP } from "./constants.js";

const PART = 8000; // characters per dynamic property part (multi-byte safe)

/**
 * @typedef {{x:number, z:number, y:(number|null), built:boolean, arrivals:string[]}} Checkpoint
 * @typedef {{
 *   phase: "idle"|"prep"|"running"|"finished",
 *   id: number,
 *   start: ({x:number,y:number,z:number}|null),
 *   startBuilt: boolean,
 *   checkpoints: Checkpoint[],
 *   timer: number,
 *   elapsed: number,
 *   firstFinishAt: number,
 *   results: (Array<{name:string, points:number, finished:boolean, cp:number}>|null),
 *   endReason: string
 * }} Race
 * @typedef {{
 *   name: string, cp: number, points: number, finished: boolean, finishTime: number,
 *   eliminated: boolean, kills: number, deaths: number,
 *   respawn: ({x:number,y:number,z:number}|null), needHorse: boolean, pendingEggs: number
 * }} Runner
 * @typedef {{id:string, slots:number, trades:number}} ChestInfo
 * @typedef {{mode:("flat"|"none"), baseY:number, classic:boolean, seed:number}} TerrainInfo
 * @typedef {{
 *   owner: (string|undefined), ownerName: (string|undefined),
 *   terrain: (TerrainInfo|undefined),
 *   chests: {shops: (ChestInfo|null)[], kit: (ChestInfo|null), reward: (ChestInfo|null)},
 *   start: ({x:number,y:number,z:number}|undefined),
 *   raceSerial: number,
 *   givenBook: string[]
 * }} Meta
 */

/** @returns {Race} */
export function newRace() {
  return {
    phase: "idle",
    id: 0,
    start: null,
    startBuilt: false,
    checkpoints: [],
    timer: 0,
    elapsed: 0,
    firstFinishAt: -1,
    results: null,
    endReason: "",
  };
}

/** @returns {Meta} */
function newMeta() {
  return {
    owner: undefined,
    ownerName: undefined,
    terrain: undefined,
    chests: { shops: [], kit: null, reward: null },
    start: undefined,
    raceSerial: 0,
    givenBook: [],
  };
}

export const S = {
  settings: { ...DEFAULT_SETTINGS },
  race: newRace(),
  /** @type {Record<string, Runner>} */
  runners: {},
  meta: newMeta(),
};

/** @type {Set<"settings"|"race"|"runners"|"meta">} */
const dirty = new Set();

/** @param {...("settings"|"race"|"runners"|"meta")} parts */
export function markDirty(...parts) {
  for (const p of parts) dirty.add(p);
}

/**
 * @param {string} key
 * @param {unknown} value
 */
function saveJson(key, value) {
  const s = JSON.stringify(value);
  const n = Math.max(1, Math.ceil(s.length / PART));
  const prev = world.getDynamicProperty(key + "#n");
  const prevN = typeof prev === "number" ? prev : 0;
  for (let i = 0; i < n; i++) world.setDynamicProperty(`${key}#${i}`, s.slice(i * PART, (i + 1) * PART));
  for (let i = n; i < prevN; i++) world.setDynamicProperty(`${key}#${i}`, undefined);
  world.setDynamicProperty(key + "#n", n);
}

/** @param {string} key */
function loadJson(key) {
  const n = world.getDynamicProperty(key + "#n");
  if (typeof n !== "number") return undefined;
  let s = "";
  for (let i = 0; i < n; i++) {
    const p = world.getDynamicProperty(`${key}#${i}`);
    if (typeof p !== "string") return undefined;
    s += p;
  }
  try {
    return JSON.parse(s);
  } catch {
    return undefined;
  }
}

export function flush() {
  for (const p of dirty) {
    try {
      saveJson(DP[p], S[p]);
    } catch (e) {
      console.warn(`[hrace] failed to save ${p}: ${e}`);
    }
  }
  dirty.clear();
}

export function loadState() {
  const st = loadJson(DP.settings);
  if (st && typeof st === "object") S.settings = { ...DEFAULT_SETTINGS, ...st };
  const r = loadJson(DP.race);
  if (r && typeof r === "object") S.race = { ...newRace(), ...r };
  const rn = loadJson(DP.runners);
  if (rn && typeof rn === "object") S.runners = rn;
  const m = loadJson(DP.meta);
  if (m && typeof m === "object") {
    const base = newMeta();
    S.meta = { ...base, ...m, chests: { ...base.chests, ...(m.chests ?? {}) } };
    if (!Array.isArray(S.meta.givenBook)) S.meta.givenBook = [];
    if (!Array.isArray(S.meta.chests.shops)) S.meta.chests.shops = [];
  }
}
