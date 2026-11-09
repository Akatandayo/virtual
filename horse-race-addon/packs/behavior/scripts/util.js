// Generic helpers.
import { world, system, ItemStack, ItemLockMode, BlockPermutation, PlayerPermissionLevel } from "@minecraft/server";
import { ID, TAG_ADMIN } from "./constants.js";
import { S } from "./state.js";

/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server").Container} Container */
/** @typedef {import("@minecraft/server").Vector3} Vector3 */
/** @typedef {import("@minecraft/server").RawMessage} RawMessage */

export const overworld = () => world.getDimension("overworld");

/**
 * Simulated players used by the headless test (/scriptevent hrace:sim). Empty in normal play.
 * @type {Player[]}
 */
export const simPlayers = [];

/** All online players (plus simulated test players, if any). */
export function allPlayers() {
  const list = world.getAllPlayers();
  return simPlayers.length ? list.concat(simPlayers) : list;
}

/** @param {string} id */
export function playerById(id) {
  return allPlayers().find((p) => p.id === id);
}

/** @param {Player} player @param {string|RawMessage} msg */
export function tell(player, msg) {
  try {
    player.sendMessage(msg);
  } catch {
    /* player left */
  }
}

/** @param {string} msg */
export function broadcast(msg) {
  world.sendMessage(msg);
}

/**
 * @param {Player} player
 * @param {string} sound
 * @param {number} [pitch]
 * @param {number} [volume]
 */
export function sound(player, sound, pitch = 1, volume = 1) {
  try {
    player.playSound(sound, { pitch, volume });
  } catch {
    /* ignore */
  }
}

/** @param {string} sound @param {number} [pitch] */
export function soundAll(sound, pitch = 1) {
  for (const p of allPlayers()) {
    try {
      p.playSound(sound, { pitch, volume: 0.8 });
    } catch {
      /* ignore */
    }
  }
}

/** @param {Player} player */
export function isAdmin(player) {
  if (!player) return false;
  if (S.meta.owner === player.id) return true;
  if (player.hasTag(TAG_ADMIN)) return true;
  try {
    return player.playerPermissionLevel === PlayerPermissionLevel.Operator;
  } catch {
    return false;
  }
}

/** @param {{x:number,z:number}} a @param {{x:number,z:number}} b */
export function dist2D(a, b) {
  const dx = a.x - b.x;
  const dz = a.z - b.z;
  return Math.sqrt(dx * dx + dz * dz);
}

/** @param {number} sec */
export function fmtTime(sec) {
  sec = Math.max(0, Math.floor(sec));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m);
  return (h > 0 ? `${h}:` : "") + `${mm}:${String(s).padStart(2, "0")}`;
}

/** @param {number} v @param {number} lo @param {number} hi */
export function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

const ARROWS = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"];
/**
 * Arrow showing where `target` is relative to the player's facing direction.
 * @param {Player} player
 * @param {{x:number,z:number}} target
 */
export function arrowTo(player, target) {
  const loc = player.location;
  const yaw = player.getRotation().y; // 0 = +Z, 90 = -X (clockwise seen from above)
  const targetYaw = (Math.atan2(-(target.x - loc.x), target.z - loc.z) * 180) / Math.PI;
  let rel = targetYaw - yaw;
  rel = ((((rel + 180) % 360) + 360) % 360) - 180; // -180..180, positive = to the right
  const idx = Math.round(rel / 45);
  return ARROWS[(idx + 8) % 8];
}

/** @param {Player} player */
export function inventoryOf(player) {
  return player.getComponent("minecraft:inventory")?.container;
}

/**
 * Give an item, dropping it at the player's feet when the inventory is full.
 * @param {Player} player
 * @param {ItemStack} stack
 */
export function giveItem(player, stack) {
  const inv = inventoryOf(player);
  const left = inv ? inv.addItem(stack) : stack;
  if (left) {
    try {
      player.dimension.spawnItem(left, player.location);
    } catch {
      /* ignore */
    }
  }
}

/**
 * @param {Container} inv
 * @param {(item: ItemStack) => boolean} pred
 */
export function countMatching(inv, pred) {
  let n = 0;
  for (let i = 0; i < inv.size; i++) {
    const it = inv.getItem(i);
    if (it && pred(it)) n += it.amount;
  }
  return n;
}

/**
 * Remove `amount` items matching `pred`. Returns true when enough were removed.
 * @param {Container} inv
 * @param {(item: ItemStack) => boolean} pred
 * @param {number} amount
 */
export function removeMatching(inv, pred, amount) {
  if (countMatching(inv, pred) < amount) return false;
  let left = amount;
  for (let i = 0; i < inv.size && left > 0; i++) {
    const it = inv.getItem(i);
    if (!it || !pred(it)) continue;
    if (it.amount <= left) {
      left -= it.amount;
      inv.setItem(i, undefined);
    } else {
      it.amount -= left;
      left = 0;
      inv.setItem(i, it);
    }
  }
  return true;
}

/** @param {Player} player @param {string} typeId */
export function hasItem(player, typeId) {
  const inv = inventoryOf(player);
  if (!inv) return false;
  return countMatching(inv, (it) => it.typeId === typeId) > 0;
}

/**
 * Display text (RawMessage) for an item stack: custom name or translated name.
 * @param {ItemStack} item
 * @returns {RawMessage}
 */
export function itemLabel(item) {
  if (item.nameTag) return { text: `§o${item.nameTag}§r` };
  try {
    return { translate: item.localizationKey };
  } catch {
    return { text: item.typeId.replace("minecraft:", "") };
  }
}

/**
 * Create a race tool item (spur / reins / config book) that is kept on death and
 * cannot be dropped.
 * @param {string} typeId
 */
export function makeToolItem(typeId) {
  const it = new ItemStack(typeId, 1);
  if (typeId === ID.spur) {
    it.setLore(["§7馬に乗っている時に使う(右クリック/長押し)", "§a加速レベル +1", "§7加速中はスタミナを消費します"]);
  } else if (typeId === ID.reins) {
    it.setLore(["§7馬に乗っている時に使う(右クリック/長押し)", "§c加速レベル -1", "§7加速レベル0で走るとスタミナ回復"]);
  } else if (typeId === ID.config) {
    it.setLore(["§7使う: レースのメニューを開く", "§7チェストに使う: ショップ/支給品/報酬の登録"]);
  }
  try {
    it.keepOnDeath = true;
    it.lockMode = ItemLockMode.inventory;
  } catch {
    /* ignore */
  }
  return it;
}

/** @type {Map<string, BlockPermutation|null>} */
const permCache = new Map();
/**
 * Resolve the first block id that exists in this game version.
 * @param {string|string[]} ids
 * @param {Record<string, string|number|boolean>} [states]
 * @returns {BlockPermutation|undefined}
 */
export function perm(ids, states) {
  const list = Array.isArray(ids) ? ids : [ids];
  const key = list.join("|") + (states ? JSON.stringify(states) : "");
  if (permCache.has(key)) return permCache.get(key) ?? undefined;
  /** @type {BlockPermutation|null} */
  let found = null;
  for (const id of list) {
    try {
      found = BlockPermutation.resolve(id, states);
      break;
    } catch {
      try {
        found = BlockPermutation.resolve(id);
        break;
      } catch {
        /* try next */
      }
    }
  }
  permCache.set(key, found);
  return found ?? undefined;
}

/**
 * Run fn, logging errors instead of throwing.
 * @template T
 * @param {string} label
 * @param {() => T} fn
 * @returns {T|undefined}
 */
export function safe(label, fn) {
  try {
    return fn();
  } catch (e) {
    console.warn(`[hrace] ${label}: ${e}${e instanceof Error && e.stack ? "\n" + e.stack : ""}`);
    return undefined;
  }
}

/** @param {number} ticks */
export function sleep(ticks) {
  return new Promise((resolve) => system.runTimeout(() => resolve(undefined), ticks));
}

/** @type {Map<string, {text: string, until: number}>} */
export const flashes = new Map();

/**
 * Show a short message as an extra line of the action bar HUD.
 * @param {Player} player
 * @param {string} text
 * @param {number} [ticks]
 */
export function flash(player, text, ticks = 40) {
  flashes.set(player.id, { text, until: system.currentTick + ticks });
  try {
    player.onScreenDisplay.setActionBar(text);
  } catch {
    /* ignore */
  }
}

/** @param {Vector3} v */
export function floorVec(v) {
  return { x: Math.floor(v.x), y: Math.floor(v.y), z: Math.floor(v.z) };
}
