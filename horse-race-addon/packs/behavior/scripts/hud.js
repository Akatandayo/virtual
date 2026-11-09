// Action bar HUD: next checkpoint, direction, distance, acceleration level and stamina.
import { system, world } from "@minecraft/server";
import { S } from "./state.js";
import { allPlayers, arrowTo, dist2D, flashes, fmtTime } from "./util.js";
import { horseHud } from "./horse.js";
import { rankOf } from "./race.js";

/** @param {number} stamina 0..100 */
function staminaBar(stamina) {
  const n = 20;
  const filled = Math.round((stamina / 100) * n);
  const color = stamina >= 60 ? "§a" : stamina >= 30 ? "§e" : "§c";
  return `${color}${"|".repeat(filled)}§8${"|".repeat(n - filled)}`;
}

/** @param {number} level @param {number} max */
function levelBar(level, max) {
  let s = "";
  for (let i = 1; i <= max; i++) s += i <= level ? (i >= 3 ? "§c▶" : i === 2 ? "§6▶" : "§e▶") : "§8▷";
  return s;
}

/** Update every player's action bar. Call every 4 ticks. */
export function updateHud() {
  const race = S.race;
  for (const p of allPlayers()) {
    /** @type {string[]} */
    const lines = [];
    const fl = flashes.get(p.id);
    if (fl) {
      if (fl.until >= system.currentTick) lines.push(fl.text);
      else flashes.delete(p.id);
    }
    const r = S.runners[p.id];
    if (race.phase === "prep") {
      lines.push(`§6§l準備中 §r§f残り §e${race.timer}§f秒 §7| 馬を出して鞍をつけよう`);
    } else if (race.phase === "running" && r) {
      if (r.eliminated) {
        lines.push("§c§l脱落 §r§7観戦中");
      } else if (r.finished) {
        lines.push(`§a§lゴール済み §r§e${r.points}pt §7| 現在${rankOf(p.id)}位`);
      } else {
        const total = race.checkpoints.length;
        const cp = race.checkpoints[r.cp];
        if (cp) {
          const isGoal = r.cp === total - 1;
          const target = { x: cp.x + 0.5, z: cp.z + 0.5 };
          const d = Math.round(dist2D(p.location, target));
          const head = isGoal ? "§c§lGOAL" : `§e§lCP${r.cp + 1}§r§7/${total}`;
          lines.push(`${head} §r§f§l${arrowTo(p, target)} §r§b${d}m §7(X:${cp.x} Z:${cp.z})`);
        }
        lines.push(`§d${r.points}pt §7${rankOf(p.id)}位 | ${fmtTime(race.elapsed)}`);
      }
    }
    const h = horseHud(p);
    if (h) {
      const lv = `§6加速 ${levelBar(h.level, h.max)} §fLv${h.level}`;
      const st = `§fスタミナ ${staminaBar(h.stamina)} §f${Math.floor(h.stamina)}%`;
      lines.push(`${lv} §8| ${st}${h.exhausted ? " §c§l疲労" : ""} §8| §7${h.kmh}km/h`);
    }
    if (lines.length) {
      try {
        p.onScreenDisplay.setActionBar(lines.join("\n"));
      } catch {
        /* ignore */
      }
    }
  }
}
