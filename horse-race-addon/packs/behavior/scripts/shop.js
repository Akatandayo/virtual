// Chest based configuration: shops, start kit and arrival rewards.
// A registered chest is saved as a structure (so the exact items, enchantments,
// names etc. are kept). When the items are needed the structure is placed for a
// moment at the bottom of the world under the player, read, and removed again.
import { world, StructureSaveMode } from "@minecraft/server";
import { ActionFormData } from "@minecraft/server-ui";
import { EDP } from "./constants.js";
import { S, markDirty } from "./state.js";
import { countMatching, giveItem, inventoryOf, itemLabel, removeMatching, safe, sound, tell } from "./util.js";

/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server").Block} Block */
/** @typedef {import("@minecraft/server").ItemStack} ItemStack */
/** @typedef {import("@minecraft/server").Dimension} Dimension */
/** @typedef {import("@minecraft/server").RawMessage} RawMessage */
/** @typedef {{product: ItemStack, prices: ItemStack[]}} Trade */

export const CONTAINER_BLOCKS = ["minecraft:chest", "minecraft:trapped_chest", "minecraft:barrel"];

/** @type {Map<string, (ItemStack|undefined)[]>} structure id -> items */
const cache = new Map();

/** @param {"shop"|"kit"|"reward"} role @param {number} [index] */
export function structureId(role, index = 0) {
  return role === "shop" ? `hrace:shop_${index + 1}` : `hrace:${role}`;
}

/**
 * A position at the bottom of the world inside the chunk of `loc`, with room for
 * three blocks along x.
 * @param {Dimension} dim
 * @param {{x:number, z:number}} loc
 */
function storageBase(dim, loc) {
  const cx = Math.floor(Math.floor(loc.x) / 16) * 16;
  return { x: cx + 4, y: dim.heightRange.min + 1, z: Math.floor(loc.z) };
}

/**
 * Remember the blocks of a 3x1x1 area so they can be put back.
 * @param {Dimension} dim
 * @param {{x:number,y:number,z:number}} base
 */
function saveArea(dim, base) {
  /** @type {{loc: {x:number,y:number,z:number}, perm: import("@minecraft/server").BlockPermutation}[]} */
  const saved = [];
  for (let dx = 0; dx < 3; dx++) {
    const loc = { x: base.x + dx, y: base.y, z: base.z };
    const b = dim.getBlock(loc);
    if (!b) return undefined;
    saved.push({ loc, perm: b.permutation });
  }
  return saved;
}

/**
 * @param {Dimension} dim
 * @param {{loc: {x:number,y:number,z:number}, perm: import("@minecraft/server").BlockPermutation}[]} saved
 */
function restoreArea(dim, saved) {
  for (const s of saved) {
    safe("clear storage", () => dim.getBlock(s.loc)?.getComponent("minecraft:inventory")?.container?.clearAll());
  }
  for (const s of saved) safe("restore block", () => dim.getBlock(s.loc)?.setPermutation(s.perm));
}

/**
 * Save the contents of a chest (single or double) as a structure. The items are
 * copied into one or two separate single chests (27 slots each) at the bottom of
 * the world, which are saved together and removed again.
 * @param {Block} block
 * @param {"shop"|"kit"|"reward"} role
 * @param {number} [index] shop index
 * @returns {string} result message
 */
export function registerChest(block, role, index = 0) {
  const inv = block.getComponent("minecraft:inventory")?.container;
  if (!inv) return "§cこのブロックはチェストではありません";
  const dim = block.dimension;
  /** @type {(ItemStack|undefined)[]} */
  const items = [];
  for (let i = 0; i < inv.size; i++) items.push(inv.getItem(i));
  const halves = Math.min(2, Math.ceil(items.length / 27));
  const base = storageBase(dim, block.location);
  const saved = saveArea(dim, base);
  if (!saved) return "§c登録に失敗しました（範囲が読み込まれていません）";
  const id = structureId(role, index);
  const sm = world.structureManager;
  try {
    for (let h = 0; h < halves; h++) {
      const b = dim.getBlock({ x: base.x + 2 * h, y: base.y, z: base.z });
      if (!b) throw new Error("storage block not loaded");
      b.setType("minecraft:chest");
      const c = b.getComponent("minecraft:inventory")?.container;
      if (!c) throw new Error("no storage container");
      for (let i = 0; i < 27; i++) c.setItem(i, items[h * 27 + i]);
    }
    if (sm.get(id)) sm.delete(id);
    sm.createFromWorld(id, dim, base, { x: base.x + 2 * (halves - 1), y: base.y, z: base.z }, {
      includeBlocks: true,
      includeEntities: false,
      saveMode: StructureSaveMode.World,
    });
  } catch (e) {
    console.warn(`[hrace] register chest: ${e}`);
    return "§c登録に失敗しました";
  } finally {
    restoreArea(dim, saved);
  }
  cache.set(id, items);
  const info = { id, slots: inv.size, trades: role === "shop" ? parseTrades(items).length : items.filter(Boolean).length };
  if (role === "shop") {
    S.meta.chests.shops[index] = info;
  } else if (role === "kit") {
    S.meta.chests.kit = info;
  } else {
    S.meta.chests.reward = info;
  }
  markDirty("meta");
  if (role === "shop") return `§aショップ${index + 1}を登録しました（取引 ${info.trades}件）`;
  if (role === "kit") return `§aスタート支給品を登録しました（${info.trades}スタック）`;
  return "§a到達報酬を登録しました";
}

/** @param {"shop"|"kit"|"reward"} role @param {number} [index] */
export function unregister(role, index = 0) {
  const id = structureId(role, index);
  safe("delete structure", () => {
    if (world.structureManager.get(id)) world.structureManager.delete(id);
  });
  cache.delete(id);
  if (role === "shop") S.meta.chests.shops[index] = null;
  else if (role === "kit") S.meta.chests.kit = null;
  else S.meta.chests.reward = null;
  markDirty("meta");
}

/**
 * Read the items of a registered chest. Places the structure for a moment at
 * the bottom of the world below `anchor` (which must be in a loaded chunk).
 * @param {string} id
 * @param {Dimension} dim
 * @param {{x:number, z:number}} anchor
 * @returns {(ItemStack|undefined)[]|undefined}
 */
export function readItems(id, dim, anchor) {
  const cached = cache.get(id);
  if (cached) return cached;
  const sm = world.structureManager;
  const st = sm.get(id);
  if (!st) return undefined;
  const base = storageBase(dim, anchor);
  const saved = saveArea(dim, base);
  if (!saved) return undefined;
  /** @type {(ItemStack|undefined)[]} */
  const items = [];
  try {
    sm.place(st, dim, base, { includeEntities: false });
    for (let dx = 0; dx < st.size.x; dx += 2) {
      const c = dim.getBlock({ x: base.x + dx, y: base.y, z: base.z })?.getComponent("minecraft:inventory")?.container;
      if (!c) continue;
      for (let i = 0; i < c.size; i++) items.push(c.getItem(i));
    }
  } catch (e) {
    console.warn(`[hrace] read chest ${id}: ${e}`);
    return undefined;
  } finally {
    restoreArea(dim, saved);
  }
  cache.set(id, items);
  return items;
}

/**
 * Shop chest layout: each column is one trade.
 * row 1 = item sold, row 2 = price, row 3 = optional second price.
 * A double chest holds two such blocks (18 trades).
 * @param {(ItemStack|undefined)[]} items
 * @returns {Trade[]}
 */
export function parseTrades(items) {
  /** @type {Trade[]} */
  const trades = [];
  for (let blockStart = 0; blockStart + 27 <= items.length; blockStart += 27) {
    for (let c = 0; c < 9; c++) {
      const product = items[blockStart + c];
      if (!product) continue;
      /** @type {ItemStack[]} */
      const prices = [];
      const p1 = items[blockStart + 9 + c];
      const p2 = items[blockStart + 18 + c];
      if (p1) prices.push(p1);
      if (p2) prices.push(p2);
      trades.push({ product, prices });
    }
  }
  return trades;
}

/**
 * Does an inventory item pay for a price item? Custom-named currency must match the name.
 * @param {ItemStack} price
 */
function priceMatcher(price) {
  return (/** @type {ItemStack} */ it) => it.typeId === price.typeId && (!price.nameTag || it.nameTag === price.nameTag);
}

/**
 * @param {Trade} t
 * @returns {RawMessage}
 */
function tradeLabel(t) {
  /** @type {RawMessage[]} */
  const parts = [{ text: "§l" }, itemLabel(t.product), { text: `§r §8×${t.product.amount}\n§r` }];
  if (t.prices.length === 0) {
    parts.push({ text: "§2無料" });
  } else {
    parts.push({ text: "§4代金: §r" });
    t.prices.forEach((p, i) => {
      if (i > 0) parts.push({ text: " §8+ §r" });
      parts.push(itemLabel(p), { text: ` §8×${p.amount}` });
    });
  }
  return { rawtext: parts };
}

/**
 * Shop index used by a merchant.
 * @param {Entity} merchant
 */
function shopIndexOf(merchant) {
  const shops = S.meta.chests.shops;
  const valid = shops.map((s, i) => (s ? i : -1)).filter((i) => i >= 0);
  if (valid.length === 0) return -1;
  const fixed = merchant.getDynamicProperty(EDP.shop);
  if (typeof fixed === "number" && shops[fixed]) return fixed;
  const cp = merchant.getDynamicProperty(EDP.cp);
  const n = typeof cp === "number" ? cp : 0;
  return valid[n % valid.length];
}

/**
 * Open the trade menu of a merchant.
 * @param {Player} player
 * @param {Entity} merchant
 */
export async function openShop(player, merchant) {
  const idx = shopIndexOf(merchant);
  if (idx < 0) {
    tell(player, "§6商人§f「悪いね、今日は売り物が無いんだ」 §7(主催者がショップ用チェストを登録していません)");
    return;
  }
  const info = S.meta.chests.shops[idx];
  if (!info) return;
  const items = readItems(info.id, player.dimension, player.location);
  if (!items) {
    tell(player, "§cショップのデータを読み込めませんでした。主催者にチェストを再登録してもらってください。");
    return;
  }
  const trades = parseTrades(items);
  const inv = inventoryOf(player);
  if (!inv) return;
  // summary of currencies the player owns
  const seen = new Set();
  /** @type {RawMessage[]} */
  const body = [{ text: "§7欲しい品物を選んでください。何度でも買えます。\n§7所持している代金:\n" }];
  for (const t of trades) {
    for (const p of t.prices) {
      const key = p.typeId + "|" + (p.nameTag ?? "");
      if (seen.has(key)) continue;
      seen.add(key);
      body.push({ text: " §e• §r" }, itemLabel(p), { text: ` §f${countMatching(inv, priceMatcher(p))}個\n` });
    }
  }
  if (trades.length === 0) body.push({ text: "\n§c(取引が設定されていません)" });
  const form = new ActionFormData()
    .title(`§l街道の商人 §r§8(ショップ${idx + 1})`)
    .body({ rawtext: body });
  for (const t of trades) form.button(tradeLabel(t));
  form.button("§l閉じる");
  const res = await form.show(player);
  if (res.canceled || res.selection === undefined || res.selection >= trades.length) return;
  const t = trades[res.selection];
  if (buy(player, t)) {
    await openShop(player, merchant);
  }
}

/**
 * @param {Player} player
 * @param {Trade} t
 */
function buy(player, t) {
  const inv = inventoryOf(player);
  if (!inv) return false;
  for (const p of t.prices) {
    if (countMatching(inv, priceMatcher(p)) < p.amount) {
      tell(player, { rawtext: [{ text: "§c代金が足りません: " }, itemLabel(p), { text: ` §c×${p.amount} が必要です` }] });
      sound(player, "note.bass", 0.7);
      return false;
    }
  }
  for (const p of t.prices) removeMatching(inv, priceMatcher(p), p.amount);
  giveItem(player, t.product.clone());
  tell(player, { rawtext: [{ text: "§a購入しました: " }, itemLabel(t.product), { text: ` §a×${t.product.amount}` }] });
  sound(player, "random.orb", 1.1);
  return true;
}

/**
 * Give the registered start kit.
 * @param {Player} player
 */
export function giveKit(player) {
  const info = S.meta.chests.kit;
  if (!info) return 0;
  const items = readItems(info.id, player.dimension, player.location);
  if (!items) return 0;
  let n = 0;
  for (const it of items) {
    if (!it) continue;
    giveItem(player, it.clone());
    n++;
  }
  return n;
}

/**
 * Give the arrival reward for a rank: column N of the reward chest is for rank N
 * (the last column is used for rank 9 and below).
 * @param {Player} player
 * @param {number} rank 1-based
 */
export function giveReward(player, rank) {
  const info = S.meta.chests.reward;
  if (!info) return 0;
  const items = readItems(info.id, player.dimension, player.location);
  if (!items) return 0;
  const col = Math.min(Math.max(rank, 1), 9) - 1;
  let n = 0;
  for (const slot of [col, col + 9, col + 18]) {
    const it = items[slot];
    if (!it) continue;
    giveItem(player, it.clone());
    n++;
  }
  return n;
}

export function clearShopCache() {
  cache.clear();
}
