// 承太郎ボットの「体」。模擬プレイヤーを出現させ、頭脳プログラム(brain)から
// 届いた行動を実行し、周囲の状況と出来事を頭脳へ送り返す。
import { world, system, GameMode, ItemStack } from "@minecraft/server";
import { spawnSimulatedPlayer, SimulatedPlayer } from "@minecraft/server-gametest";
import { http, HttpRequest, HttpRequestMethod, HttpHeader } from "@minecraft/server-net";
import { CONFIG } from "./config.js";
import { craft } from "./craft.js";

const SAVE_KEY = "jobot:save";
const HAT = "jobot:hat";
const LOCKED = '{"minecraft:item_lock":{"mode":"lock_in_slot"},"minecraft:keep_on_death":{}}';
// アドオンがホットバーに置く操作用アイテム。保存や整理の対象から外す。
const STAND_ITEMS = new Set([
  "jjba:sp_active_control", "jjba:sp_disabled_control", "jjba:sp_pb_control",
  "jjba:sp_sf", "jjba:sp_di", "jjba:sp_ts", "jjba:s_cd",
]);
const STAND_SLOTS = [0, 5, 6, 7, 8];
const DISC = "jjba:sp_stand_disc";
// スタープラチナの技。アイテム使用で発動しなかった場合は cmd を直接実行する。
const SKILLS = {
  rush: { slot: 5, item: "jjba:sp_pb_control", cmd: "execute as @s[tag=!unable_skills] run function sp_pb_active" },
  star_finger: { slot: 6, item: "jjba:sp_sf", cmd: "execute as @s[tag=!unable_skills] run function sp_sf" },
  star_suck: { slot: 7, item: "jjba:sp_di", cmd: "execute as @s[tag=!unable_skills] at @s run function sp_di" },
  time_stop: { slot: 8, item: "jjba:sp_ts", cmd: "execute as @s[tag=!unable_skills,tag=!sp_ts_cd] at @s run function sp_ts_r" },
};

/** @type {SimulatedPlayer | undefined} */
let bot;
let spawning = false;
let events = [];
let results = [];
let queue = [];
let current = null; // { action, cancelled }
let followName = null;
let inFlight = false;
let lastBrainError = 0;
let lastMelee = 0;
let lastPlace = 0;

const log = (...a) => console.warn("[jobot]", ...a);
const round = (n) => Math.round(n * 10) / 10;
const pos = (l) => ({ x: round(l.x), y: round(l.y), z: round(l.z) });
const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
const short = (id) => (id ?? "").replace(/^minecraft:/, "");
const alive = () => bot !== undefined && bot.isValid;
const container = () => bot.getComponent("minecraft:inventory").container;
const health = (e) => {
  try { return Math.round(e.getComponent("minecraft:health").currentValue); } catch { return undefined; }
};
const realPlayers = () => world.getAllPlayers().filter((p) => !(p instanceof SimulatedPlayer));
const pushEvent = (e) => { if (events.length < 50) events.push(e); };
const slotItem = (i) => container().getItem(i)?.typeId;

function isHostile(e) {
  try { return e.matches({ families: ["monster"] }); } catch { return false; }
}

// ───────── 出現・退出・保存 ─────────

function loadSave() {
  try { return JSON.parse(world.getDynamicProperty(SAVE_KEY) ?? "null"); } catch { return null; }
}

function save() {
  if (!alive()) return;
  const inv = [];
  const c = container();
  for (let i = 0; i < c.size; i++) {
    const it = c.getItem(i);
    if (it && !STAND_ITEMS.has(it.typeId) && it.typeId !== DISC) inv.push([i, it.typeId, it.amount]);
  }
  const data = { pos: pos(bot.location), dim: bot.dimension.id, inv };
  try { world.setDynamicProperty(SAVE_KEY, JSON.stringify(data)); } catch (e) { log("保存に失敗", String(e)); }
}

// 出現・復活の直後は、地形の読み込み待ちで落下死しないよう一時的に無敵にする
function protect() {
  try { bot.addEffect("resistance", 300, { amplifier: 255, showParticles: false }); } catch { /* 無視 */ }
}

// 高さが分からない場所に出たとき、地形の読み込みを待って地表に降ろす
async function placeOnSurface(at) {
  for (let i = 0; i < 60 && alive(); i++) {
    let top;
    try { top = bot.dimension.getTopmostBlock({ x: at.x, z: at.z }); } catch { /* 未読み込み */ }
    if (top) {
      const y = top.location.y + 1;
      bot.teleport({ x: Math.floor(at.x) + 0.5, y, z: Math.floor(at.z) + 0.5 });
      await system.waitTicks(5);
      if (alive() && Math.abs(bot.location.y - y) < 3) return;
    }
    await system.waitTicks(10);
  }
}

async function spawnBot(near) {
  if (alive() || spawning) return;
  spawning = true;
  try {
    const saved = loadSave();
    const dimension = world.getDimension(saved?.dim ?? near?.dimension.id ?? "overworld");
    let at = saved?.pos ?? near?.location;
    const unknownHeight = !at;
    if (unknownHeight) at = { ...world.getDefaultSpawnLocation(), y: 200 };
    bot = spawnSimulatedPlayer({ dimension, x: at.x, y: at.y, z: at.z }, CONFIG.botName, GameMode.Survival);
    protect();
    await system.waitTicks(10);
    if (unknownHeight) await placeOnSurface(at);
    const c = container();
    // サーバー側に持ち物が残っていなければ、保存しておいた持ち物を戻す
    if (saved?.inv && c.emptySlotsCount === c.size) {
      for (const [i, id, n] of saved.inv) {
        try { c.setItem(i, new ItemStack(id, n)); } catch { /* 無くなったアイテムは無視 */ }
      }
    }
    if (CONFIG.wearSkin) bot.runCommand(`replaceitem entity @s slot.armor.head 0 ${HAT} 1 0 ${LOCKED}`);
    if (CONFIG.giveStand && !bot.hasTag("sp_user") && !hasItem(DISC)) bot.runCommand(`give @s ${DISC}`);
    pushEvent({ type: "spawned" });
    log("出現しました", JSON.stringify(pos(bot.location)));
  } catch (e) {
    log("出現に失敗", String(e));
    bot = undefined;
  } finally {
    spawning = false;
  }
}

function despawnBot() {
  if (!alive()) return;
  try {
    cancelAll("退出");
    if (standOut()) bot.runCommand("execute as @s run function sp_disabled");
    save();
    bot.disconnect();
  } catch (e) { log("退出に失敗", String(e)); }
  bot = undefined;
}

// ───────── 持ち物の補助 ─────────

function hasItem(id) { return findSlot(id) >= 0; }

function findSlot(query) {
  const c = container();
  const q = query.includes(":") ? query : `minecraft:${query}`;
  for (let i = 0; i < c.size; i++) if (c.getItem(i)?.typeId === q) return i;
  for (let i = 0; i < c.size; i++) if (c.getItem(i)?.typeId.includes(query)) return i;
  return -1;
}

// 指定アイテムを手に持てるホットバー枠(1〜4)へ移し、その枠番号を返す
function toHotbar(slot) {
  const c = container();
  if (slot >= 1 && slot <= 4) return slot;
  let target = [1, 2, 3, 4].find((i) => !c.getItem(i)) ?? 1;
  c.swapItems(slot, target, c);
  return target;
}

// スタンドを出すとホットバーの 0,5〜8 が上書きされるので、先に退避しておく
function stashStandSlots() {
  const c = container();
  for (const s of STAND_SLOTS) {
    const it = c.getItem(s);
    if (!it || STAND_ITEMS.has(it.typeId) || it.typeId === DISC) continue;
    for (let i = 9; i < c.size; i++) {
      if (!c.getItem(i)) { c.swapItems(s, i, c); break; }
    }
  }
}

// ───────── スタンド ─────────

const standOut = () => alive() && (bot.hasTag("sp_active") || bot.hasTag("sp_pb_active"));
const skillReady = (name) => slotItem(SKILLS[name].slot) === SKILLS[name].item
  && !bot.hasTag("unable_skills") && !(name === "time_stop" && bot.hasTag("sp_ts_cd"));

function standState() {
  return {
    owned: bot.hasTag("sp_user") || hasItem(DISC),
    out: standOut(),
    rush_ready: standOut() && skillReady("rush"),
    star_finger_ready: standOut() && skillReady("star_finger"),
    star_suck_ready: standOut() && skillReady("star_suck"),
    time_stop_ready: standOut() && skillReady("time_stop"),
    time_stopped: bot.hasTag("sp_ts"),
  };
}

async function useSlot(slot) {
  bot.useItemInSlot(slot);
  await system.waitTicks(3);
  try { bot.stopUsingItem(); } catch { /* 使用中でなければ何もしない */ }
}

async function summonStand() {
  if (standOut()) return { ok: true, note: "すでに出している" };
  stashStandSlots();
  if (!bot.hasTag("sp_user")) {
    const disc = findSlot(DISC);
    if (disc < 0) return { ok: false, error: "スタンドディスクを持っていない" };
    await useSlot(toHotbar(disc));
    if (!standOut()) bot.runCommand("execute as @s[tag=!stand_user] at @s run function sp_stand_up");
  } else {
    if (slotItem(0) === "jjba:sp_active_control") await useSlot(0);
    if (!standOut()) bot.runCommand("execute as @s[tag=!unable_skills] at @s run function sp_active");
  }
  await system.waitTicks(2);
  return standOut() ? { ok: true } : { ok: false, error: "スタンドを出せなかった" };
}

async function retractStand() {
  if (!standOut()) return { ok: true, note: "出していない" };
  if (slotItem(0) === "jjba:sp_disabled_control") await useSlot(0);
  if (standOut()) bot.runCommand("execute as @s[tag=!unable_skills] run function sp_disabled");
  await system.waitTicks(2);
  return standOut() ? { ok: false, error: "今はしまえない" } : { ok: true };
}

async function useSkill(name) {
  const skill = SKILLS[name];
  if (!standOut()) {
    const r = await summonStand();
    if (!r.ok) return r;
  }
  if (!skillReady(name)) return { ok: false, error: "クールダウン中、または今は技を出せない" };
  await useSlot(skill.slot);
  if (slotItem(skill.slot) === skill.item && !(name === "time_stop" && bot.hasTag("sp_ts_cd"))) bot.runCommand(skill.cmd);
  return { ok: true };
}

// ───────── 移動 ─────────

async function waitGround() {
  for (let i = 0; i < 20 && !bot.isOnGround; i++) await system.waitTicks(1);
}

// target は座標を返す関数。reach 以内に入るか、時間切れ・立ち往生で終わる。
async function walkTo(target, ctl, reach = 1.8, timeout = 600) {
  let lastPos = bot.location, lastMove = 0, retried = 0;
  for (let t = 0; t < timeout; t += 5) {
    if (ctl.cancelled) return { ok: false, error: "中断" };
    if (!alive()) return { ok: false, error: "死亡" };
    const goal = target();
    if (!goal) return { ok: false, error: "目標を見失った" };
    if (dist(bot.location, goal) <= reach) { bot.stopMoving(); return { ok: true }; }
    if (t % 20 === 0) {
      await waitGround();
      try { bot.navigateToLocation(goal, 1); } catch { /* 経路なし。下の立ち往生判定に任せる */ }
    }
    await system.waitTicks(5);
    if (dist(bot.location, lastPos) > 0.4) { lastPos = bot.location; lastMove = t; }
    else if (t - lastMove >= 60) {
      if (retried++ >= 1) { bot.stopMoving(); return { ok: false, error: "道が見つからず進めない", at: pos(bot.location) }; }
      bot.jump();
      lastMove = t;
    }
  }
  bot.stopMoving();
  return { ok: false, error: "時間切れ", at: pos(bot.location) };
}

function findPlayer(name) {
  const players = realPlayers();
  return players.find((p) => p.name === name) ?? players.find((p) => p.name.toLowerCase().includes(String(name).toLowerCase()));
}

function findEntity(id) {
  try { return world.getEntity(String(id)); } catch { return undefined; }
}

function nearestHostile(max = 16) {
  return bot.dimension.getEntities({ location: bot.location, maxDistance: max, families: ["monster"] })
    .filter((e) => e.isValid && !e.hasTag("stand"))
    .sort((a, b) => dist(a.location, bot.location) - dist(b.location, bot.location))[0];
}

// ───────── 戦闘 ─────────

async function fight(target, useStand, ctl, timeout = 500) {
  const name = short(target.typeId);
  if (useStand && !standOut() && (bot.hasTag("sp_user") || hasItem(DISC))) await summonStand();
  for (let t = 0; t < timeout; t += 4) {
    if (ctl.cancelled) return { ok: false, error: "中断" };
    if (!alive()) return { ok: false, error: "自分が倒された" };
    if (!target.isValid || health(target) === 0) { bot.stopMoving(); return { ok: true, result: `${name} を倒した` }; }
    const d = dist(bot.location, target.location);
    if (d > 32) { bot.stopMoving(); return { ok: false, error: "相手に逃げられた" }; }
    bot.lookAtEntity(target);
    if (d > 3) {
      if (t % 20 === 0) { await waitGround(); try { bot.navigateToEntity(target, 1); } catch { /* 経路なし */ } }
    } else bot.stopMoving();
    if (useStand && standOut()) {
      if (d <= 4.5 && skillReady("rush")) await useSkill("rush");
      else if (d <= 5.5 && d >= 2 && skillReady("star_finger")) await useSkill("star_finger");
    }
    if (d <= 3.2 && system.currentTick - lastMelee >= 12) {
      try { bot.attackEntity(target); } catch { /* 相手が消えた */ }
      lastMelee = system.currentTick;
    }
    await system.waitTicks(4);
  }
  bot.stopMoving();
  return { ok: false, error: "時間切れで決着がつかなかった" };
}

// ───────── ブロック ─────────

const FACES = [
  [{ x: 0, y: -1, z: 0 }, "Up"], [{ x: 0, y: 0, z: 1 }, "North"], [{ x: 0, y: 0, z: -1 }, "South"],
  [{ x: 1, y: 0, z: 0 }, "West"], [{ x: -1, y: 0, z: 0 }, "East"], [{ x: 0, y: 1, z: 0 }, "Down"],
];
const blockLoc = (a) => ({ x: Math.floor(a.x), y: Math.floor(a.y), z: Math.floor(a.z) });
const center = (l) => ({ x: l.x + 0.5, y: l.y, z: l.z + 0.5 });

async function approachBlock(loc, ctl) {
  if (dist(bot.getHeadLocation(), center(loc)) <= 4.5) return { ok: true };
  return walkTo(() => center(loc), ctl, 3.5, 400);
}

async function mine(loc, ctl) {
  const block = bot.dimension.getBlock(loc);
  if (!block || block.isAir) return { ok: false, error: "そこにブロックがない" };
  const typeId = block.typeId; // block は生きた参照なので、壊す前の種類を控えておく
  const id = short(typeId);
  const near = await approachBlock(loc, ctl);
  if (!near.ok) return near;
  // 足が地面についていないと採掘が進まないので、止まって着地を待つ
  bot.stopMoving();
  await waitGround();
  bot.lookAtBlock(loc);
  await system.waitTicks(2);
  bot.breakBlock(loc);
  for (let t = 0; t < 300; t += 5) {
    if (ctl.cancelled) { bot.stopBreakingBlock(); return { ok: false, error: "中断" }; }
    await system.waitTicks(5);
    const now = bot.dimension.getBlock(loc);
    if (!now || now.typeId !== typeId) {
      await walkTo(() => center(loc), ctl, 1.2, 60); // 落ちたアイテムを拾いに行く
      return { ok: true, result: `${id} を壊した` };
    }
  }
  bot.stopBreakingBlock();
  return { ok: false, error: `${id} を壊せなかった(道具が合わない可能性)` };
}

async function place(itemQuery, loc, ctl) {
  let slot = findSlot(itemQuery);
  if (slot < 0) return { ok: false, error: `${itemQuery} を持っていない` };
  const dim = bot.dimension;
  const here = dim.getBlock(loc);
  if (here && !here.isAir && !here.isLiquid) return { ok: false, error: "そこはすでに埋まっている" };
  const support = FACES.map(([o, face]) => [{ x: loc.x + o.x, y: loc.y + o.y, z: loc.z + o.z }, face])
    .find(([l]) => { const b = dim.getBlock(l); return b && !b.isAir && !b.isLiquid; });
  if (!support) return { ok: false, error: "隣に支えになるブロックがない" };
  const near = await approachBlock(loc, ctl);
  if (!near.ok) return near;
  slot = toHotbar(slot);
  bot.lookAtBlock(loc);
  // 連続して置くと失敗するので、前回から少し間を空ける
  const rest = 10 - (system.currentTick - lastPlace);
  if (rest > 0) await system.waitTicks(rest);
  const done = bot.useItemInSlotOnBlock(slot, support[0], support[1]);
  lastPlace = system.currentTick;
  await system.waitTicks(3);
  const after = dim.getBlock(loc);
  return after && !after.isAir ? { ok: true } : { ok: false, error: done ? "置けなかった" : "アイテムを使えなかった" };
}

function findBlocks(query, radius) {
  const r = Math.min(Math.max(radius ?? 8, 1), 10);
  const o = blockLoc(bot.location);
  const dim = bot.dimension;
  const found = [];
  for (let x = -r; x <= r; x++) for (let z = -r; z <= r; z++) for (let y = -6; y <= 6; y++) {
    const l = { x: o.x + x, y: o.y + y, z: o.z + z };
    let b;
    try { b = dim.getBlock(l); } catch { continue; }
    if (b && !b.isAir && b.typeId.includes(query)) found.push({ id: short(b.typeId), ...l, d: round(dist(l, o)) });
  }
  found.sort((a, b) => a.d - b.d);
  return { ok: true, count: found.length, blocks: found.slice(0, 12) };
}

// ───────── 行動の一覧 ─────────

const ACTIONS = {
  async say(a) {
    for (const line of String(a.message ?? "").split("\n").filter(Boolean)) bot.chat(line.slice(0, 200));
    return { ok: true };
  },
  async go_to(a, ctl) {
    followName = null;
    const goal = { x: a.x, y: a.y, z: a.z };
    return walkTo(() => goal, ctl);
  },
  async go_to_player(a, ctl) {
    followName = null;
    const p = findPlayer(a.name);
    if (!p) return { ok: false, error: "そのプレイヤーが見つからない" };
    if (p.dimension.id !== bot.dimension.id) return { ok: false, error: "別のディメンションにいる" };
    return walkTo(() => (p.isValid ? p.location : undefined), ctl, 2.5);
  },
  async follow(a) {
    const p = findPlayer(a.name);
    if (!p) return { ok: false, error: "そのプレイヤーが見つからない" };
    followName = p.name;
    return { ok: true, result: `${p.name} について行く(stop で止まる)` };
  },
  async look_at(a) {
    if (a.entity_id !== undefined) {
      const e = findEntity(a.entity_id);
      if (!e) return { ok: false, error: "相手が見つからない" };
      bot.lookAtEntity(e);
    } else if (a.player) {
      const p = findPlayer(a.player);
      if (!p) return { ok: false, error: "そのプレイヤーが見つからない" };
      bot.lookAtEntity(p);
    } else bot.lookAtLocation({ x: a.x, y: a.y, z: a.z });
    return { ok: true };
  },
  async fight(a, ctl) {
    followName = null;
    const target = a.entity_id !== undefined ? findEntity(a.entity_id) : a.player ? findPlayer(a.player) : nearestHostile();
    if (!target || !target.isValid) return { ok: false, error: "戦う相手が見つからない" };
    return fight(target, a.use_stand !== false, ctl);
  },
  async stand(a) {
    const face = a.target_id !== undefined ? findEntity(a.target_id) : a.target_player ? findPlayer(a.target_player) : undefined;
    if (face?.isValid) { bot.lookAtEntity(face); await system.waitTicks(3); }
    if (a.action === "summon") return summonStand();
    if (a.action === "retract") return retractStand();
    if (SKILLS[a.action]) return useSkill(a.action);
    return { ok: false, error: "知らない技" };
  },
  async mine_block(a, ctl) { followName = null; return mine(blockLoc(a), ctl); },
  async place_block(a, ctl) { return place(String(a.item), blockLoc(a), ctl); },
  async find_blocks(a) { return findBlocks(String(a.block), a.radius); },
  async interact_block(a, ctl) {
    const loc = blockLoc(a);
    const near = await approachBlock(loc, ctl);
    if (!near.ok) return near;
    bot.lookAtBlock(loc);
    return { ok: bot.interactWithBlock(loc) };
  },
  async equip(a) {
    const slot = findSlot(String(a.item));
    if (slot < 0) return { ok: false, error: `${a.item} を持っていない` };
    const c = container();
    const it = c.getItem(slot);
    const armor = [["_chestplate", "Chest"], ["_leggings", "Legs"], ["_boots", "Feet"], ["elytra", "Chest"]]
      .find(([suffix]) => it.typeId.endsWith(suffix));
    if (armor) {
      const eq = bot.getComponent("minecraft:equippable");
      const old = eq.getEquipment(armor[1]);
      eq.setEquipment(armor[1], it);
      c.setItem(slot, old);
      return { ok: true, result: `${short(it.typeId)} を装備した` };
    }
    bot.selectedSlotIndex = toHotbar(slot);
    return { ok: true, result: `${short(it.typeId)} を手に持った` };
  },
  async use_item(a) {
    const slot = findSlot(String(a.item));
    if (slot < 0) return { ok: false, error: `${a.item} を持っていない` };
    const hot = toHotbar(slot);
    bot.selectedSlotIndex = hot;
    const used = bot.useItemInSlot(hot);
    await system.waitTicks(Math.min(Math.max(a.hold_ticks ?? 40, 1), 100));
    try { bot.stopUsingItem(); } catch { /* 使用中でなければ何もしない */ }
    return { ok: used };
  },
  async give_item(a) {
    const p = findPlayer(a.player);
    if (!p) return { ok: false, error: "そのプレイヤーが見つからない" };
    if (dist(p.location, bot.location) > 5) return { ok: false, error: "遠すぎる。先に近づく" };
    const slot = findSlot(String(a.item));
    if (slot < 0) return { ok: false, error: `${a.item} を持っていない` };
    const c = container();
    const it = c.getItem(slot);
    if (STAND_ITEMS.has(it.typeId) || it.typeId === HAT) return { ok: false, error: "それは渡せない" };
    const n = Math.min(a.count ?? it.amount, it.amount);
    const gift = it.clone();
    gift.amount = n;
    if (n >= it.amount) c.setItem(slot, undefined);
    else { it.amount -= n; c.setItem(slot, it); }
    bot.lookAtEntity(p);
    p.dimension.spawnItem(gift, p.location);
    return { ok: true, result: `${short(gift.typeId)} x${n} を渡した` };
  },
  async craft(a) { return craft(bot, String(a.item), a.count ?? 1); },
  async jump() { return { ok: bot.jump() }; },
  async sneak(a) { bot.isSneaking = a.on !== false; return { ok: true }; },
  async wait(a, ctl) {
    const ticks = Math.min(Math.max((a.seconds ?? 1) * 20, 1), 600);
    for (let t = 0; t < ticks && !ctl.cancelled; t += 5) await system.waitTicks(5);
    return { ok: true };
  },
};

function cancelAll(reason) {
  if (current) current.cancelled = true;
  for (const a of queue) results.push({ id: a.id, ok: false, error: `取り消し(${reason})` });
  queue = [];
  followName = null;
  if (alive()) { try { bot.stopMoving(); bot.stopBreakingBlock(); } catch { /* 無視 */ } }
}

async function pump() {
  if (current) return;
  while (queue.length && alive()) {
    const action = queue.shift();
    current = { action, cancelled: false };
    let res;
    try {
      const fn = ACTIONS[action.type];
      res = fn ? await fn(action, current) : { ok: false, error: `未対応の行動: ${action.type}` };
    } catch (e) {
      res = { ok: false, error: String(e) };
    }
    results.push({ id: action.id, ...res });
    current = null;
  }
}

function accept(actions) {
  for (const a of actions ?? []) {
    if (a.type === "stop") { cancelAll("stop"); results.push({ id: a.id, ok: true }); }
    else queue.push(a);
  }
  pump();
}

// ───────── 状況の報告 ─────────

function snapshot() {
  const here = bot.location;
  const dim = bot.dimension;
  const c = container();
  const inventory = [];
  for (let i = 0; i < c.size; i++) {
    const it = c.getItem(i);
    if (it && !STAND_ITEMS.has(it.typeId)) inventory.push(`${short(it.typeId)} x${it.amount}`);
  }
  const eq = bot.getComponent("minecraft:equippable");
  const players = realPlayers().filter((p) => p.dimension.id === dim.id).map((p) => ({
    name: p.name, ...pos(p.location), dist: round(dist(p.location, here)), hp: health(p),
  }));
  const entities = dim.getEntities({ location: here, maxDistance: 24, excludeTypes: ["minecraft:player", "minecraft:item", "minecraft:xp_orb"] })
    .filter((e) => e.isValid && !e.hasTag("stand") && !e.typeId.startsWith("jjba:"))
    .map((e) => ({ id: e.id, type: short(e.typeId), ...pos(e.location), dist: round(dist(e.location, here)), hp: health(e), hostile: isHostile(e) || undefined }))
    .sort((a, b) => a.dist - b.dist).slice(0, 14);
  const items = dim.getEntities({ location: here, maxDistance: 12, type: "minecraft:item" }).slice(0, 6).map((e) => {
    let id = "item";
    try { id = short(e.getComponent("minecraft:item").itemStack.typeId); } catch { /* 無視 */ }
    return { item: id, ...pos(e.location) };
  });
  let below;
  try { below = short(dim.getBlock({ x: here.x, y: here.y - 1, z: here.z })?.typeId); } catch { /* 未読み込み */ }
  const time = world.getTimeOfDay();
  return {
    name: bot.name,
    ...pos(here),
    dimension: short(dim.id),
    hp: health(bot),
    time_of_day: time,
    night: time >= 13000 && time < 23000,
    standing_on: below,
    in_water: bot.isInWater || undefined,
    holding: short(c.getItem(bot.selectedSlotIndex)?.typeId) || null,
    armor: ["Chest", "Legs", "Feet"].map((s) => short(eq.getEquipment(s)?.typeId)).filter(Boolean),
    inventory,
    stand: standState(),
    doing: current ? current.action.type : followName ? `follow ${followName}` : "idle",
    players,
    entities,
    dropped_items: items,
  };
}

async function poll() {
  if (inFlight || !alive()) return;
  inFlight = true;
  const body = { state: snapshot(), events, results };
  events = [];
  results = [];
  try {
    const req = new HttpRequest(`${CONFIG.brainUrl}/tick`);
    req.method = HttpRequestMethod.Post;
    req.headers = [new HttpHeader("Content-Type", "application/json")];
    req.body = JSON.stringify(body);
    req.timeout = 5;
    const res = await http.request(req);
    if (res.status !== 200) throw new Error(`HTTP ${res.status}`);
    accept(JSON.parse(res.body).actions);
  } catch (e) {
    // 送れなかった分は次回に回す
    events = body.events.concat(events).slice(-50);
    results = body.results.concat(results);
    if (system.currentTick - lastBrainError > 1200) {
      lastBrainError = system.currentTick;
      log("頭脳プログラムに接続できません。brain を起動してください:", String(e));
    }
  } finally {
    inFlight = false;
  }
}

// ───────── 常時動く処理 ─────────

system.runInterval(() => { poll(); }, CONFIG.pollTicks);

system.runInterval(() => {
  if (!alive()) return;
  if (followName && !current) {
    const p = findPlayer(followName);
    if (p?.isValid && p.dimension.id === bot.dimension.id) {
      const d = dist(p.location, bot.location);
      if (d > 3.5 && bot.isOnGround) { try { bot.navigateToEntity(p, 1); } catch { /* 経路なし */ } }
      else if (d <= 2.5) bot.stopMoving();
    }
  }
}, 20);

system.runInterval(() => {
  save();
  if (CONFIG.despawnWhenEmpty && alive() && realPlayers().length === 0) despawnBot();
}, 200);

world.afterEvents.playerSpawn.subscribe((ev) => {
  if (ev.player instanceof SimulatedPlayer) return;
  if (ev.initialSpawn) pushEvent({ type: "player_join", name: ev.player.name });
  if (!alive()) system.runTimeout(() => spawnBot(ev.player), 40);
});

world.afterEvents.playerLeave.subscribe((ev) => {
  if (ev.playerName !== CONFIG.botName) pushEvent({ type: "player_leave", name: ev.playerName });
});

world.afterEvents.chatSend.subscribe((ev) => {
  const sender = ev.sender;
  if (!sender || sender instanceof SimulatedPlayer) return;
  const text = ev.message.trim();
  if (text.startsWith("!jotaro")) {
    const cmd = text.split(/\s+/)[1];
    if (cmd === "here" && alive()) { cancelAll("here"); bot.teleport(sender.location, { dimension: sender.dimension }); }
    else if (cmd === "spawn") spawnBot(sender);
    else if (cmd === "remove") despawnBot();
    else if (cmd === "stop" && alive()) cancelAll("stop");
    else sender.sendMessage("§7!jotaro here / spawn / remove / stop");
    return;
  }
  pushEvent({ type: "chat", from: sender.name, text: text.slice(0, 300) });
});

world.afterEvents.entityHurt.subscribe((ev) => {
  if (!alive() || ev.hurtEntity.id !== bot.id) return;
  const attacker = ev.damageSource.damagingEntity;
  pushEvent({
    type: "hurt", damage: round(ev.damage), cause: ev.damageSource.cause, hp: health(bot),
    by: attacker ? (attacker.typeId === "minecraft:player" ? attacker.name : short(attacker.typeId)) : undefined,
    by_id: attacker && attacker.typeId !== "minecraft:player" ? attacker.id : undefined,
  });
  if (CONFIG.autoDefend && attacker?.isValid && attacker.typeId !== "minecraft:player" && !current && queue.length === 0) {
    pushEvent({ type: "auto_defend", target: short(attacker.typeId) });
    accept([{ id: `auto-${system.currentTick}`, type: "fight", entity_id: attacker.id }]);
  }
});

world.afterEvents.entityDie.subscribe((ev) => {
  if (!bot || ev.deadEntity.id !== bot.id) return;
  cancelAll("死亡");
  pushEvent({ type: "died", cause: ev.damageSource.cause });
  system.runTimeout(async () => {
    try {
      if (!bot?.isValid) return;
      bot.respawn();
      await system.waitTicks(5);
      protect();
      // 仲間がいればそのそばに、いなければ初期スポーンの地表に戻る
      const friend = realPlayers()[0];
      if (friend) bot.teleport(friend.location, { dimension: friend.dimension });
      else await placeOnSurface(bot.location);
      pushEvent({ type: "respawned" });
    } catch (e) { log("復活に失敗", String(e)); }
  }, 60);
});

// サーバーのコンソールからの操作:
//   scriptevent jobot:spawn / scriptevent jobot:remove / scriptevent jobot:chat <話しかける内容>
system.afterEvents.scriptEventReceive.subscribe((ev) => {
  if (ev.id === "jobot:spawn") spawnBot(realPlayers()[0]);
  else if (ev.id === "jobot:remove") despawnBot();
  else if (ev.id === "jobot:chat") pushEvent({ type: "chat", from: "サーバー管理者", text: ev.message.slice(0, 300) });
});

world.afterEvents.worldLoad.subscribe(() => {
  log(`準備完了。人間のプレイヤーが入ると ${CONFIG.botName} が出現します`);
  const p = realPlayers()[0];
  if (p) spawnBot(p);
});
