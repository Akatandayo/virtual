// 模擬プレイヤーは作業台の画面を操作できないので、材料を消費して完成品を
// 渡す形でクラフトを代用する。レシピは基本的な道具と設備だけ。
import { ItemStack } from "@minecraft/server";

const MATERIALS = { wooden: "planks", stone: "cobblestone", iron: "iron_ingot", golden: "gold_ingot", diamond: "diamond" };
const TOOLS = { pickaxe: [3, 2], axe: [3, 2], shovel: [1, 2], hoe: [2, 2], sword: [2, 1] };
const ARMOR = { helmet: 5, chestplate: 8, leggings: 7, boots: 4 };

// 材料名: "planks" は板材ならどれでも、"log" は原木ならどれでも、"fuel" は石炭か木炭
const RECIPES = {
  stick: { needs: { planks: 2 }, makes: 4 },
  crafting_table: { needs: { planks: 4 }, makes: 1 },
  torch: { needs: { fuel: 1, stick: 1 }, makes: 4 },
  furnace: { needs: { cobblestone: 8 }, makes: 1, table: true },
  chest: { needs: { planks: 8 }, makes: 1, table: true },
  bread: { needs: { wheat: 3 }, makes: 1, table: true },
  bucket: { needs: { iron_ingot: 3 }, makes: 1, table: true },
  shield: { needs: { planks: 6, iron_ingot: 1 }, makes: 1, table: true },
  ladder: { needs: { stick: 7 }, makes: 3, table: true },
  bed: { needs: { wool: 3, planks: 3 }, makes: 1, table: true },
};
for (const [prefix, material] of Object.entries(MATERIALS)) {
  for (const [tool, [n, sticks]] of Object.entries(TOOLS)) {
    RECIPES[`${prefix}_${tool}`] = { needs: { [material]: n, stick: sticks }, makes: 1, table: true };
  }
  if (prefix === "wooden" || prefix === "stone") continue;
  for (const [piece, n] of Object.entries(ARMOR)) {
    RECIPES[`${prefix}_${piece}`] = { needs: { [material]: n }, makes: 1, table: true };
  }
}

const short = (id) => id.replace(/^minecraft:/, "");
const isLog = (id) => /(_log|_stem)$/.test(id) && !id.includes("stripped_bamboo");

function matches(id, material) {
  if (material === "planks") return id.endsWith("_planks");
  if (material === "log") return isLog(id);
  if (material === "fuel") return id === "coal" || id === "charcoal";
  if (material === "wool") return id.endsWith("_wool");
  return id === material;
}

function count(container, material) {
  let n = 0;
  for (let i = 0; i < container.size; i++) {
    const it = container.getItem(i);
    if (it && matches(short(it.typeId), material)) n += it.amount;
  }
  return n;
}

function take(container, material, n) {
  for (let i = 0; i < container.size && n > 0; i++) {
    const it = container.getItem(i);
    if (!it || !matches(short(it.typeId), material)) continue;
    const used = Math.min(n, it.amount);
    n -= used;
    if (used >= it.amount) container.setItem(i, undefined);
    else { it.amount -= used; container.setItem(i, it); }
  }
}

function give(bot, container, id, n) {
  while (n > 0) {
    const stack = new ItemStack(`minecraft:${id}`, Math.min(n, 64));
    n -= stack.amount;
    const left = container.addItem(stack);
    if (left) bot.dimension.spawnItem(left, bot.location);
  }
}

function tableNearby(bot) {
  const o = bot.location;
  for (let x = -4; x <= 4; x++) for (let y = -2; y <= 2; y++) for (let z = -4; z <= 4; z++) {
    try {
      if (bot.dimension.getBlock({ x: o.x + x, y: o.y + y, z: o.z + z })?.typeId === "minecraft:crafting_table") return true;
    } catch { /* 未読み込み */ }
  }
  return false;
}

export function craft(bot, item, times) {
  const container = bot.getComponent("minecraft:inventory").container;
  const id = short(item);
  times = Math.min(Math.max(Math.floor(times), 1), 64);

  // 原木 → 板材(木の種類を引き継ぐ)
  if (id.endsWith("planks")) {
    for (let i = 0; i < container.size; i++) {
      const it = container.getItem(i);
      if (!it || !isLog(short(it.typeId))) continue;
      const used = Math.min(times, it.amount);
      const wood = short(it.typeId).replace(/^stripped_/, "").replace(/(_log|_stem)$/, "");
      take(container, short(it.typeId), used);
      give(bot, container, `${wood}_planks`, used * 4);
      return { ok: true, result: `${wood}_planks x${used * 4} を作った` };
    }
    return { ok: false, error: "原木を持っていない" };
  }

  const recipe = RECIPES[id];
  if (!recipe) return { ok: false, error: `作り方を知らない: ${id}`, craftable: ["planks", ...Object.keys(RECIPES)] };
  if (recipe.table && !tableNearby(bot)) return { ok: false, error: "近く(4ブロック以内)に作業台が必要" };
  for (const [material, n] of Object.entries(recipe.needs)) {
    const have = count(container, material);
    if (have < n * times) return { ok: false, error: `材料不足: ${material} が ${n * times} 個必要(所持 ${have})` };
  }
  for (const [material, n] of Object.entries(recipe.needs)) take(container, material, n * times);
  give(bot, container, id, recipe.makes * times);
  return { ok: true, result: `${id} x${recipe.makes * times} を作った` };
}
