// Race flow: start, checkpoints, points, deaths, finish.
import {
  world,
  system,
  BlockVolume,
  DisplaySlotId,
  GameMode,
  ItemStack,
  ObjectiveSortOrder,
} from "@minecraft/server";
import { DIRECTIONS, EDP, ID, TAG_SPECTATOR } from "./constants.js";
import { S, markDirty, newRace } from "./state.js";
import { allPlayers, broadcast, clamp, dist2D, floorVec, fmtTime, giveItem, hasItem, inventoryOf, isAdmin, makeToolItem, overworld, perm, playerById, safe, sound, soundAll, tell } from "./util.js";
import { clearShopCache, giveKit, giveReward, readItems } from "./shop.js";
import { groundY, terrainActive } from "./terrain.js";
import { recentHorseOf } from "./horse.js";

/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").Dimension} Dimension */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("./state.js").Runner} Runner */
/** @typedef {import("./state.js").Checkpoint} Checkpoint */

const OBJECTIVE = "hrace_pts";

export function isRacing() {
  return S.race.phase === "prep" || S.race.phase === "running";
}

/** Parse "10,7,5" into [10, 7, 5]. */
export function pointsTable() {
  return String(S.settings.points)
    .split(/[,、\s]+/)
    .map((s) => parseInt(s, 10))
    .filter((n) => Number.isFinite(n) && n >= 0);
}

/** Runners sorted by ranking. */
export function standings() {
  return Object.entries(S.runners)
    .map(([id, r]) => ({ id, ...r }))
    .sort((a, b) => {
      if (b.points !== a.points) return b.points - a.points;
      if (a.finished !== b.finished) return a.finished ? -1 : 1;
      if (a.finished && b.finished && a.finishTime !== b.finishTime) return a.finishTime - b.finishTime;
      if (b.cp !== a.cp) return b.cp - a.cp;
      return a.deaths - b.deaths;
    });
}

/** @type {Map<string, number>} */
let rankCache = new Map();
export function rankOf(/** @type {string} */ id) {
  return rankCache.get(id) ?? 0;
}
function refreshRanks() {
  rankCache = new Map(standings().map((r, i) => [r.id, i + 1]));
}

// ---------------------------------------------------------------------------
// Scoreboard

function objective() {
  return world.scoreboard.getObjective(OBJECTIVE);
}

function setupScoreboard() {
  const sb = world.scoreboard;
  const old = sb.getObjective(OBJECTIVE);
  if (old) sb.removeObjective(old);
  const obj = sb.addObjective(OBJECTIVE, "§6§lレースポイント");
  sb.setObjectiveAtDisplaySlot(DisplaySlotId.Sidebar, { objective: obj, sortOrder: ObjectiveSortOrder.Descending });
  for (const r of Object.values(S.runners)) obj.setScore(r.name, r.points);
}

/** @param {Runner} r */
function updateScore(r) {
  safe("score", () => objective()?.setScore(r.name, r.points));
}

// ---------------------------------------------------------------------------
// Building

/**
 * @param {Dimension} dim
 * @param {{x:number,y:number,z:number}} a
 * @param {{x:number,y:number,z:number}} b
 * @param {string|string[]} block
 * @param {Record<string, string|number|boolean>} [states]
 */
function fill(dim, a, b, block, states) {
  const p = perm(block, states);
  if (!p) return;
  dim.fillBlocks(new BlockVolume(a, b), p, { ignoreChunkBoundErrors: true });
}

/**
 * Checkpoint / start / goal platform with a beacon beam that can be seen from far away.
 * @param {Dimension} dim
 * @param {number} x @param {number} g ground y @param {number} z
 * @param {"start"|"cp"|"goal"} kind
 * @param {string} label
 */
function buildPlatform(dim, x, g, z, kind, label) {
  const color = kind === "goal" ? "red" : kind === "start" ? "white" : "yellow";
  fill(dim, { x: x - 6, y: g + 1, z: z - 6 }, { x: x + 6, y: g + 26, z: z + 6 }, "minecraft:air");
  fill(dim, { x: x - 6, y: g - 1, z: z - 6 }, { x: x + 6, y: g - 1, z: z + 6 }, ["minecraft:sandstone"]);
  fill(dim, { x: x - 6, y: g, z: z - 6 }, { x: x + 6, y: g, z: z + 6 }, ["minecraft:cut_red_sandstone", "minecraft:red_sandstone"]);
  fill(dim, { x: x - 5, y: g, z: z - 5 }, { x: x + 5, y: g, z: z + 5 }, ["minecraft:smooth_sandstone", "minecraft:sandstone"]);
  fill(dim, { x: x - 1, y: g, z: z - 1 }, { x: x + 1, y: g, z: z + 1 }, kind === "goal" ? "minecraft:gold_block" : "minecraft:iron_block");
  fill(dim, { x, y: g + 1, z }, { x, y: g + 1, z }, "minecraft:beacon");
  fill(dim, { x, y: g + 2, z }, { x, y: g + 2, z }, [`minecraft:${color}_stained_glass`, "minecraft:glass"]);
  for (const [dx, dz] of [
    [-5, -5],
    [5, -5],
    [-5, 5],
    [5, 5],
  ]) {
    fill(dim, { x: x + dx, y: g + 1, z: z + dz }, { x: x + dx, y: g + 3, z: z + dz }, "minecraft:oak_fence");
    fill(dim, { x: x + dx, y: g + 4, z: z + dz }, { x: x + dx, y: g + 4, z: z + dz }, [`minecraft:${color}_wool`, "minecraft:white_wool"]);
    fill(dim, { x: x + dx, y: g + 5, z: z + dz }, { x: x + dx, y: g + 5, z: z + dz }, "minecraft:lantern");
  }
  safe("sign", () => {
    for (const [dx, dz, dir] of [
      [0, 3, 0],
      [0, -3, 8],
      [3, 0, 4],
      [-3, 0, 12],
    ]) {
      const loc = { x: x + dx, y: g + 1, z: z + dz };
      const b = dim.getBlock(loc);
      const sp = perm("minecraft:standing_sign", { ground_sign_direction: dir });
      if (!b || !sp) continue;
      b.setPermutation(sp);
      b.getComponent("minecraft:sign")?.setText(label);
    }
  });
}

/**
 * @param {Dimension} dim
 * @param {{x:number,y:number,z:number}} loc
 * @param {number} cpIndex
 */
function spawnMerchant(dim, loc, cpIndex) {
  safe("merchant", () => {
    const m = dim.spawnEntity(ID.merchant, loc);
    m.nameTag = cpIndex < 0 ? "§6街道の商人 §7(スタート)" : `§6街道の商人 §7(CP${cpIndex + 1})`;
    m.setDynamicProperty(EDP.cp, Math.max(0, cpIndex));
    m.setDynamicProperty(EDP.raceId, S.race.id);
    m.setRotation({ x: 0, y: 90 });
  });
}

/** @param {Dimension} dim @param {number} x @param {number} z */
function chunkLoaded(dim, x, z) {
  try {
    return !!dim.getBlock({ x, y: dim.heightRange.min, z });
  } catch {
    return false;
  }
}

/** @param {Dimension} dim @param {number} x @param {number} z @param {number} fallback */
function groundAt(dim, x, z, fallback) {
  try {
    const g = groundY(dim, x, z);
    return g ?? fallback;
  } catch {
    return fallback;
  }
}

/** Build the start area when its chunk is loaded. */
function tryBuildStart() {
  const r = S.race;
  const start = r.start;
  if (!start || r.startBuilt) return;
  const dim = overworld();
  if (!chunkLoaded(dim, start.x, start.z)) return;
  const g = groundAt(dim, start.x, start.z, start.y);
  start.y = g;
  safe("build start", () => {
    buildPlatform(dim, start.x, g, start.z, "start", "§l§0START\n§r§8大陸横断レース");
    spawnMerchant(dim, { x: start.x + 3.5, y: g + 1, z: start.z + 0.5 }, -1);
  });
  r.startBuilt = true;
  markDirty("race");
}

/**
 * Build checkpoint `i` if its chunk is loaded (or `force`).
 * @param {number} i
 */
function tryBuildCheckpoint(i) {
  const cp = S.race.checkpoints[i];
  if (!cp || cp.built) return true;
  const dim = overworld();
  if (!chunkLoaded(dim, cp.x, cp.z)) return false;
  const top = dim.getTopmostBlock({ x: cp.x, z: cp.z });
  if (!top) return false;
  const g = groundAt(dim, cp.x, cp.z, top.y);
  const total = S.race.checkpoints.length;
  const isGoal = i === total - 1;
  safe("build cp", () => {
    buildPlatform(dim, cp.x, g, cp.z, isGoal ? "goal" : "cp", isGoal ? "§l§4GOAL\n§r§8ゴール地点" : `§l§6CHECKPOINT\n§r§0${i + 1} / ${total}`);
    spawnMerchant(dim, { x: cp.x + 3.5, y: g + 1, z: cp.z + 0.5 }, i);
  });
  cp.y = g;
  cp.built = true;
  markDirty("race");
  return true;
}

// ---------------------------------------------------------------------------
// Race start

/**
 * @param {{x:number,z:number}} start
 * @returns {Checkpoint[]}
 */
function generateCheckpoints(start) {
  const st = S.settings;
  const preset = DIRECTIONS[st.direction] ?? DIRECTIONS[0];
  const base = preset.angle < 0 ? Math.random() * 360 : preset.angle;
  const cps = [];
  let x = start.x;
  let z = start.z;
  const n = clamp(st.cpCount | 0, 1, 30);
  for (let i = 0; i < n; i++) {
    const ang = ((base + (Math.random() * 2 - 1) * st.spread) * Math.PI) / 180;
    const d = st.legDistance * (0.8 + Math.random() * 0.4);
    x += Math.cos(ang) * d;
    z += Math.sin(ang) * d;
    cps.push({ x: Math.round(x), z: Math.round(z), y: null, built: false, arrivals: [] });
  }
  return cps;
}

/** @param {Player} p @param {(Player|undefined)} starter */
function isParticipant(p, starter) {
  if (p.hasTag(TAG_SPECTATOR)) return false;
  if (starter && p.id === starter.id && !S.settings.hostJoins) return false;
  return true;
}

/**
 * Start a race from the admin's settings.
 * @param {Player} admin
 * @returns {string|undefined} error message
 */
export function startRace(admin) {
  if (isRacing()) return "§cすでにレース中です";
  if (admin.dimension.id !== "minecraft:overworld" && !S.meta.start) return "§cオーバーワールドで開始してください";
  const players = allPlayers().filter((p) => isParticipant(p, admin));
  if (players.length === 0) return "§c参加者がいません（全員が観戦に設定されています）";
  const dim = overworld();
  const st = S.meta.start ?? floorVec(admin.location);
  const g = groundAt(dim, st.x, st.z, st.y - 1);
  const race = newRace();
  race.phase = "prep";
  S.meta.raceSerial = (S.meta.raceSerial ?? 0) + 1;
  race.id = S.meta.raceSerial;
  race.start = { x: st.x, y: g, z: st.z };
  race.timer = clamp(S.settings.prepSeconds | 0, 10, 600);
  race.checkpoints = generateCheckpoints(race.start);
  S.race = race;
  S.runners = {};
  // read the registered chests once now (the organizer's area is loaded), so
  // kits and rewards never depend on far away chunks being loaded
  clearShopCache();
  safe("prefetch chests", () => {
    const c = S.meta.chests;
    if (c.kit) readItems(c.kit.id, admin.dimension, admin.location);
    if (c.reward) readItems(c.reward.id, admin.dimension, admin.location);
    for (const sh of c.shops) if (sh) readItems(sh.id, admin.dimension, admin.location);
  });
  removeOldMerchants();
  tryBuildStart();
  players.forEach((p, i) => registerRunner(p, i, players.length));
  safe("scoreboard", setupScoreboard);
  safe("gamerules", () => {
    world.gameRules.pvp = !!S.settings.pvp;
    world.gameRules.doWeatherCycle = false;
    overworld().runCommand("weather clear");
    world.setDefaultSpawnLocation({ x: race.start?.x ?? st.x, y: g + 1, z: race.start?.z ?? st.z });
  });
  const total = race.checkpoints.reduce(
    (acc, cp, i) => acc + dist2D(i === 0 ? /** @type {{x:number,z:number}} */ (race.start) : race.checkpoints[i - 1], cp),
    0,
  );
  broadcast(`§6§l=== 大陸横断ホースレース 開催！ ===`);
  broadcast(
    `§fチェックポイント §e${race.checkpoints.length}§f か所 / 総距離 約§e${Math.round(total)}§fブロック / 参加者 §e${players.length}§f人`,
  );
  broadcast(`§7準備時間は${race.timer}秒。スポーンエッグで馬を出し、鞍をつけて待機してください。`);
  soundAll("raid.horn", 1);
  markDirty("race", "runners", "meta");
  return undefined;
}

/**
 * @param {Player} p
 * @param {number} slot position index on the start platform
 * @param {number} count number of runners on the platform
 */
function registerRunner(p, slot, count) {
  S.runners[p.id] = {
    name: p.name,
    cp: 0,
    points: 0,
    finished: false,
    finishTime: -1,
    eliminated: false,
    kills: 0,
    deaths: 0,
    respawn: null,
    needHorse: false,
    pendingEggs: 0,
  };
  const r = S.race;
  const start = r.start;
  if (!start) return;
  const ang = (slot / Math.max(1, count)) * Math.PI * 2;
  const rad = count > 1 ? 4 : 3;
  const loc = { x: start.x + 0.5 + Math.cos(ang) * rad, y: start.y + 1, z: start.z + 0.5 + Math.sin(ang) * rad };
  const firstCp = r.checkpoints[0];
  safe("prepare runner", () => {
    if (p.getGameMode() !== GameMode.Survival && p.getGameMode() !== GameMode.Adventure) p.setGameMode(GameMode.Survival);
    p.teleport(loc, { dimension: overworld(), facingLocation: firstCp ? { x: firstCp.x, y: loc.y, z: firstCp.z } : undefined });
    p.setSpawnPoint({ dimension: overworld(), x: loc.x, y: loc.y, z: loc.z });
  });
  system.runTimeout(() => {
    if (!p.isValid) return;
    safe("kit", () => {
      if (S.settings.clearInventory) {
        inventoryOf(p)?.clearAll();
        if (isAdmin(p)) giveItem(p, makeToolItem(ID.config));
      }
      giveItem(p, new ItemStack("minecraft:horse_spawn_egg", 1));
      giveItem(p, new ItemStack("minecraft:saddle", 1));
      ensureTools(p);
      giveKit(p);
    });
    p.onScreenDisplay.setTitle("§6§lレース準備", {
      subtitle: "§f馬を出して鞍をつけよう",
      fadeInDuration: 5,
      stayDuration: 50,
      fadeOutDuration: 10,
    });
  }, 10);
  updateScore(S.runners[p.id]);
}

/** Give the spur and reins if missing. @param {Player} p */
export function ensureTools(p) {
  if (!hasItem(p, ID.spur)) giveItem(p, makeToolItem(ID.spur));
  if (!hasItem(p, ID.reins)) giveItem(p, makeToolItem(ID.reins));
}

function removeOldMerchants() {
  for (const m of overworld().getEntities({ type: ID.merchant })) {
    const id = m.getDynamicProperty(EDP.raceId);
    if (typeof id === "number" && id !== S.race.id) safe("despawn", () => m.remove());
  }
}

// ---------------------------------------------------------------------------
// Ticking

/** Every 5 ticks: arrivals. */
export function raceTickFast() {
  if (S.race.phase !== "running") return;
  const rad = Math.max(2, S.settings.arrivalRadius);
  for (const p of allPlayers()) {
    const r = S.runners[p.id];
    if (!r || r.finished || r.eliminated) continue;
    if (p.dimension.id !== "minecraft:overworld") continue;
    const cp = S.race.checkpoints[r.cp];
    if (!cp) continue;
    const dx = p.location.x - (cp.x + 0.5);
    const dz = p.location.z - (cp.z + 0.5);
    if (dx * dx + dz * dz <= rad * rad) arrive(p, r);
  }
}

/** Every second: timers, building, end conditions. */
export function raceTickSecond() {
  const r = S.race;
  if (r.phase === "prep") {
    tryBuildStart();
    holdAtStart();
    r.timer--;
    if (r.timer <= 5 && r.timer > 0) {
      for (const p of allPlayers()) {
        p.onScreenDisplay.setTitle(`§e§l${r.timer}`, { fadeInDuration: 0, stayDuration: 18, fadeOutDuration: 2 });
        sound(p, "note.pling", 0.8);
      }
    }
    if (r.timer <= 0) go();
    markDirty("race");
    return;
  }
  if (r.phase !== "running") return;
  r.elapsed++;
  // build checkpoints whose chunks got loaded
  for (let i = 0; i < r.checkpoints.length; i++) {
    if (!r.checkpoints[i].built) tryBuildCheckpoint(i);
  }
  refreshRanks();
  if (r.firstFinishAt >= 0) {
    const left = S.settings.graceMinutes * 60 - (r.elapsed - r.firstFinishAt);
    if (left > 0 && left % 60 === 0) broadcast(`§6レース終了まで残り §e${left / 60}分`);
    else if (left === 30 || left === 10) broadcast(`§6レース終了まで残り §e${left}秒`);
  }
  checkEnd();
  if (r.elapsed % 5 === 0) markDirty("race");
}

/** Keep runners on the start platform during the preparation time. */
function holdAtStart() {
  const start = S.race.start;
  if (!start) return;
  for (const p of allPlayers()) {
    const rn = S.runners[p.id];
    if (!rn) continue;
    if (p.dimension.id !== "minecraft:overworld" || dist2D(p.location, start) > 24) {
      safe("hold", () => p.teleport({ x: start.x + 0.5, y: start.y + 1, z: start.z + 0.5 }, { dimension: overworld() }));
      tell(p, "§eスタートの合図まで、スタート地点から離れないでください");
    }
  }
}

function go() {
  const r = S.race;
  r.phase = "running";
  r.elapsed = 0;
  const cp = r.checkpoints[0];
  for (const p of allPlayers()) {
    p.onScreenDisplay.setTitle("§a§lGO!!", {
      subtitle: cp ? `§fCP1 → X:${cp.x} Z:${cp.z}` : "",
      fadeInDuration: 0,
      stayDuration: 40,
      fadeOutDuration: 10,
    });
  }
  soundAll("raid.horn", 1.4);
  soundAll("random.explode", 1.6);
  if (cp) broadcast(`§a§lスタート！ §r§f最初のチェックポイント: §eX:${cp.x} Z:${cp.z} §7(画面上部の矢印の方向へ)`);
  markDirty("race");
}

/**
 * @param {Player} p
 * @param {Runner} r
 */
function arrive(p, r) {
  const race = S.race;
  const idx = r.cp;
  const cp = race.checkpoints[idx];
  if (!cp.built) tryBuildCheckpoint(idx);
  const total = race.checkpoints.length;
  const isGoal = idx === total - 1;
  cp.arrivals.push(p.id);
  const rank = cp.arrivals.length;
  const table = pointsTable();
  let pts = rank <= table.length ? table[rank - 1] : 0;
  if (isGoal) pts *= Math.max(1, S.settings.goalMultiplier);
  r.points += pts;
  r.cp++;
  const y = (cp.y ?? Math.floor(p.location.y) - 1) + 1;
  r.respawn = { x: cp.x - 1.5, y, z: cp.z - 1.5 };
  safe("spawnpoint", () => p.setSpawnPoint({ dimension: overworld(), x: cp.x - 1.5, y, z: cp.z - 1.5 }));
  const rewards = safe("reward", () => giveReward(p, rank)) ?? 0;
  const time = fmtTime(race.elapsed);
  if (isGoal) {
    r.finished = true;
    r.finishTime = race.elapsed;
    broadcast(`§c§l[GOAL] §r§b${p.name}§f が §6${rank}位§f でゴール！ §a+${pts}pt §7(${time})`);
    p.onScreenDisplay.setTitle("§6§lGOAL!!", {
      subtitle: `§f${rank}位 §a+${pts}pt §7(合計 ${r.points}pt)`,
      fadeInDuration: 5,
      stayDuration: 60,
      fadeOutDuration: 20,
    });
    soundAll("random.levelup", 1);
    safe("firework", () => p.dimension.spawnEntity("minecraft:fireworks_rocket", p.location));
    if (race.firstFinishAt < 0) {
      race.firstFinishAt = race.elapsed;
      if (S.settings.graceMinutes > 0) broadcast(`§6最初のゴール者が出ました！ §fあと §e${S.settings.graceMinutes}分§f でレース終了です`);
    }
  } else {
    const next = race.checkpoints[r.cp];
    broadcast(`§e[CP${idx + 1}/${total}] §b${p.name}§f が §6${rank}位§f で通過 §a+${pts}pt §7(${time})`);
    p.onScreenDisplay.setTitle(`§e§lCP${idx + 1} 通過`, {
      subtitle: `§f${rank}位 §a+${pts}pt${rewards ? " §d+報酬" : ""}`,
      fadeInDuration: 5,
      stayDuration: 40,
      fadeOutDuration: 10,
    });
    sound(p, "random.levelup", 1.2);
    const nextIsGoal = r.cp === total - 1;
    tell(p, `§f次の${nextIsGoal ? "§cゴール" : `§eCP${r.cp + 1}`}§f: §eX:${next.x} Z:${next.z} §7(約${Math.round(dist2D(cp, next))}ブロック)`);
  }
  updateScore(r);
  refreshRanks();
  markDirty("race", "runners");
  checkEnd();
}

function checkEnd() {
  const race = S.race;
  if (race.phase !== "running") return;
  const all = Object.values(S.runners);
  const active = all.filter((r) => !r.finished && !r.eliminated);
  if (all.length > 0 && active.length === 0) {
    endRace(all.some((r) => r.finished) ? "全員がゴールしました" : "全員が脱落しました");
    return;
  }
  if (race.firstFinishAt >= 0 && race.elapsed - race.firstFinishAt >= S.settings.graceMinutes * 60) {
    endRace("最初のゴールから制限時間が経過しました");
  }
}

/** @param {string} reason */
export function endRace(reason) {
  const race = S.race;
  if (race.phase === "idle" || race.phase === "finished") return;
  race.phase = "finished";
  race.endReason = reason;
  const list = standings();
  race.results = list.map((r) => ({ name: r.name, points: r.points, finished: r.finished, cp: r.cp }));
  broadcast(`§6§l=== レース終了 === §r§7(${reason})`);
  list.slice(0, 10).forEach((r, i) => {
    const color = i === 0 ? "§6§l" : i === 1 ? "§f§l" : i === 2 ? "§c§l" : "§7";
    const status = r.finished ? `§aゴール ${fmtTime(r.finishTime)}` : r.eliminated ? "§c脱落" : `§7CP${r.cp}/${race.checkpoints.length}`;
    broadcast(`${color}${i + 1}位§r §b${r.name} §e${r.points}pt §8| ${status} §8| §7撃破${r.kills} 死亡${r.deaths}`);
  });
  const winner = list[0];
  for (const p of allPlayers()) {
    p.onScreenDisplay.setTitle(winner ? `§6§l優勝 ${winner.name}` : "§6§lレース終了", {
      subtitle: winner ? `§e${winner.points}pt` : reason,
      fadeInDuration: 10,
      stayDuration: 100,
      fadeOutDuration: 20,
    });
  }
  soundAll("random.totem", 1);
  if (winner) {
    const wp = playerById(winner.id);
    if (wp) {
      for (let i = 0; i < 5; i++) {
        system.runTimeout(() => {
          if (wp.isValid) safe("fw", () => wp.dimension.spawnEntity("minecraft:fireworks_rocket", wp.location));
        }, i * 10);
      }
    }
  }
  // eliminated players get back to survival
  for (const p of allPlayers()) {
    const r = S.runners[p.id];
    if (r?.eliminated) safe("gm", () => p.setGameMode(GameMode.Survival));
  }
  markDirty("race", "runners");
}

/** Clear the race completely (settings and registered chests are kept). */
export function resetRace() {
  for (const p of allPlayers()) {
    const r = S.runners[p.id];
    if (r?.eliminated) safe("gm", () => p.setGameMode(GameMode.Survival));
  }
  safe("merchants", () => {
    for (const m of overworld().getEntities({ type: ID.merchant })) {
      if (typeof m.getDynamicProperty(EDP.raceId) === "number") m.remove();
    }
  });
  safe("scoreboard", () => {
    const o = objective();
    if (o) world.scoreboard.removeObjective(o);
  });
  S.race = newRace();
  S.runners = {};
  rankCache.clear();
  markDirty("race", "runners");
}

// ---------------------------------------------------------------------------
// Players

/**
 * Player joined the world (first spawn of the session).
 * @param {Player} p
 */
export function onJoin(p) {
  const r = S.runners[p.id];
  if (r) {
    r.name = p.name;
    if (r.pendingEggs > 0) {
      for (let i = 0; i < r.pendingEggs; i++) {
        giveItem(p, new ItemStack("minecraft:horse_spawn_egg", 1));
        giveItem(p, new ItemStack("minecraft:saddle", 1));
      }
      r.pendingEggs = 0;
      markDirty("runners");
    }
    if (isRacing()) {
      ensureTools(p);
      const cp = S.race.checkpoints[r.cp];
      if (cp && S.race.phase === "running" && !r.finished && !r.eliminated) {
        tell(p, `§eレースに復帰しました。§f次の目標: §eX:${cp.x} Z:${cp.z}`);
      }
    }
    return;
  }
  if (isRacing() && S.settings.lateJoin && !p.hasTag(TAG_SPECTATOR)) {
    registerRunner(p, Math.floor(Math.random() * 8), 8);
    broadcast(`§b${p.name}§f が途中参加しました（スタート地点から出発）`);
    markDirty("runners");
  }
}

/**
 * A player died.
 * @param {Player} victim
 * @param {(Entity|undefined)} killerEntity
 */
export function onPlayerDeath(victim, killerEntity) {
  if (S.race.phase !== "running") return;
  const r = S.runners[victim.id];
  if (!r || r.finished || r.eliminated) return;
  r.deaths++;
  const killer = killerEntity && killerEntity.typeId === "minecraft:player" ? /** @type {Player} */ (killerEntity) : undefined;
  const kr = killer && killer.id !== victim.id ? S.runners[killer.id] : undefined;
  const penalty = Math.min(r.points, Math.max(0, S.settings.deathPenalty | 0));
  r.points -= penalty;
  if (kr && killer && !kr.eliminated && !kr.finished) {
    kr.kills++;
    kr.points += Math.max(0, S.settings.killBonus | 0);
    updateScore(kr);
    broadcast(
      `§c⚔ §b${killer.name}§f が §b${victim.name}§f を倒した！ §a+${S.settings.killBonus}pt` +
        (penalty > 0 ? ` §7(${victim.name} -${penalty}pt)` : ""),
    );
  } else if (penalty > 0) {
    broadcast(`§7☠ ${victim.name} が力尽きた (-${penalty}pt)`);
  }
  updateScore(r);
  // the horse goes back to the stable; a new one is issued on respawn
  const horse = recentHorseOf(victim);
  if (horse) safe("remove horse", () => horse.remove());
  r.needHorse = true;
  if (S.settings.deathMode === 1) {
    r.eliminated = true;
    broadcast(`§c${victim.name} は脱落しました`);
  }
  markDirty("runners");
  checkEnd();
}

/**
 * Player respawned after death.
 * @param {Player} p
 */
export function onRespawn(p) {
  const r = S.runners[p.id];
  if (!r || !isRacing()) return;
  system.runTimeout(() => {
    if (!p.isValid) return;
    if (r.eliminated) {
      safe("spectate", () => p.setGameMode(GameMode.Spectator));
      tell(p, "§7あなたは脱落しました。観戦モードでレースを見守りましょう。");
      return;
    }
    const target = r.respawn ?? (S.race.start ? { x: S.race.start.x + 0.5, y: S.race.start.y + 1, z: S.race.start.z + 0.5 } : null);
    if (target && dist2D(p.location, target) > 6) {
      safe("respawn tp", () => p.teleport(target, { dimension: overworld() }));
    }
    if (r.needHorse) {
      giveItem(p, new ItemStack("minecraft:horse_spawn_egg", 1));
      giveItem(p, new ItemStack("minecraft:saddle", 1));
      r.needHorse = false;
      tell(p, "§e新しい馬のスポーンエッグと鞍が支給されました。");
      markDirty("runners");
    }
    ensureTools(p);
  }, 4);
}

/**
 * Is this block inside a protected platform (start / built checkpoints)?
 * @param {{x:number, y:number, z:number}} loc
 */
export function isProtectedBlock(loc) {
  const race = S.race;
  if (race.phase === "idle") return false;
  /** @param {{x:number, z:number}} c @param {number|null|undefined} y */
  const near = (c, y) =>
    Math.abs(loc.x - c.x) <= 6 && Math.abs(loc.z - c.z) <= 6 && (y === null || y === undefined || (loc.y >= y - 1 && loc.y <= y + 6));
  if (race.start && race.startBuilt && near(race.start, race.start.y)) return true;
  for (const cp of race.checkpoints) if (cp.built && near(cp, cp.y)) return true;
  return false;
}

/** Teleport an admin next to a runner's next checkpoint (debug / testing). @param {Player} p */
export function teleportToNext(p) {
  const r = S.runners[p.id];
  const cp = r ? S.race.checkpoints[r.cp] : S.race.checkpoints[0];
  if (!cp) return false;
  const dim = overworld();
  p.teleport({ x: cp.x + 0.5, y: (cp.y ?? (terrainActive() && S.meta.terrain ? S.meta.terrain.baseY : 100)) + 2, z: cp.z - 14.5 }, { dimension: dim });
  return true;
}

/**
 * Dev helper: build a platform on the ground at x,z (used by /scriptevent hrace:platform).
 * @param {number} x @param {number} z @param {"start"|"cp"|"goal"} kind
 */
export function devBuildPlatform(x, z, kind) {
  const dim = overworld();
  const top = dim.getTopmostBlock({ x, z });
  if (!top) return -1;
  const g = groundAt(dim, x, z, top.y);
  buildPlatform(dim, x, g, z, kind, kind === "goal" ? "§l§4GOAL\n§r§8テスト" : "§l§6CHECKPOINT\n§r§0テスト");
  spawnMerchant(dim, { x: x + 3.5, y: g + 1, z: z + 0.5 }, 0);
  return g;
}
