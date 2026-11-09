// Horse stamina / acceleration system, invulnerable horses and auto taming.
import { system, world, ItemStack, EntityInitializationCause } from "@minecraft/server";
import {
  ACCEL_POWER,
  EDP,
  HORSE_TYPES,
  NORMALIZED_HORSE_SPEED,
  STAMINA_DRAIN,
  STAMINA_RECOVER_THRESHOLD,
  STAMINA_REGEN_IDLE,
  STAMINA_REGEN_MOVING,
} from "./constants.js";
import { S } from "./state.js";
import { allPlayers, clamp, flash, giveItem, playerById, safe, sound, tell } from "./util.js";

/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server").Player} Player */
/**
 * @typedef {{stamina:number, level:number, exhausted:boolean, lastTick:number, savedAt:number,
 *   applied:string, held:boolean, penaltyUntil:number, bps:number,
 *   lastPos:({x:number, z:number}|undefined)}} HorseState
 */

/** @type {Map<string, HorseState>} */
const states = new Map();
/** @type {Map<string, string>} playerId -> horseId currently ridden */
const mounted = new Map();
/** @type {Map<string, {horseId:string, tick:number}>} playerId -> last ridden horse */
const lastRidden = new Map();
/** @type {Map<string, number>} */
const lastLevelChange = new Map();
/** @type {Map<string, string>} horseId -> owner playerId */
const ownerCache = new Map();
/** @type {{playerId:string, tick:number, x:number, z:number}[]} recent spawn egg uses */
const eggUses = [];

/**
 * Remember who used a horse spawn egg, so the new horse is tamed to them.
 * @param {Player} player
 * @param {{x:number, z:number}} where
 */
export function noteEggUse(player, where) {
  eggUses.push({ playerId: player.id, tick: system.currentTick, x: where.x, z: where.z });
  if (eggUses.length > 32) eggUses.shift();
}

/** @param {Entity} e */
export function isHorse(e) {
  return HORSE_TYPES.includes(e.typeId);
}

/** @param {Player} player */
export function ridingHorse(player) {
  try {
    const m = player.getComponent("minecraft:riding")?.entityRidingOn;
    return m && m.isValid && isHorse(m) ? m : undefined;
  } catch {
    return undefined;
  }
}

/** @param {Entity} horse */
function stateOf(horse) {
  let s = states.get(horse.id);
  if (!s) {
    let st;
    try {
      st = horse.getDynamicProperty(EDP.stamina);
    } catch {
      st = undefined;
    }
    s = {
      stamina: typeof st === "number" ? st : 100,
      level: 0,
      exhausted: false,
      lastTick: system.currentTick,
      savedAt: system.currentTick,
      applied: "",
      held: false,
      penaltyUntil: 0,
      bps: 0,
      lastPos: undefined,
    };
    states.set(horse.id, s);
  }
  return s;
}

/**
 * The single speed / slowness effect that gives a horse its current speed:
 * acceleration level, fairness normalisation (all horses get the same base speed)
 * and the short penalty after exhaustion are combined into one multiplier.
 * Speed adds 20% per effect level, slowness removes 15% per level.
 * @param {Entity} horse
 * @param {HorseState} s
 * @returns {{type:"speed"|"slowness", amp:number}|undefined}
 */
function desiredEffect(horse, s) {
  const pct = (ACCEL_POWER[S.settings.accelPower] ?? 40) / 100;
  let mult = 1 + pct * Math.max(0, s.level);
  if (S.settings.normalizeHorses && horse.typeId === "minecraft:horse") {
    const base = horse.getComponent("minecraft:movement")?.defaultValue ?? NORMALIZED_HORSE_SPEED;
    if (base > 0.01) mult *= NORMALIZED_HORSE_SPEED / base;
  }
  if (system.currentTick < s.penaltyUntil) mult *= 0.7;
  if (mult >= 1) {
    const n = Math.round((mult - 1) / 0.2);
    return n > 0 ? { type: "speed", amp: n - 1 } : undefined;
  }
  const n = Math.round((1 - mult) / 0.15);
  return n > 0 ? { type: "slowness", amp: n - 1 } : undefined;
}

/** @param {Entity} horse @param {HorseState} s */
function applySpeed(horse, s) {
  if (s.held) {
    horse.removeEffect("slowness");
    s.held = false;
  }
  const eff = desiredEffect(horse, s);
  const key = eff ? `${eff.type}:${eff.amp}` : "";
  if (s.applied && s.applied !== key) {
    // drop the previous effect when the type or strength changes
    horse.removeEffect(s.applied.startsWith("speed") ? "speed" : "slowness");
  }
  if (eff) horse.addEffect(eff.type, 30, { amplifier: eff.amp, showParticles: false });
  s.applied = key;
}

/** @param {Entity} horse @param {HorseState} s */
function save(horse, s) {
  s.savedAt = system.currentTick;
  safe("save stamina", () => horse.setDynamicProperty(EDP.stamina, Math.round(s.stamina * 10) / 10));
}

/** @param {string} horseId */
function onDismount(horseId) {
  const s = states.get(horseId);
  if (!s) return;
  s.level = 0;
  const horse = world.getEntity(horseId);
  if (horse && horse.isValid) {
    safe("dismount", () => {
      applySpeed(horse, s);
      save(horse, s);
    });
  }
}

/** @param {Player} player @param {Entity} horse @param {HorseState} s */
function exhaust(player, horse, s) {
  s.stamina = 0;
  s.level = 0;
  s.exhausted = true;
  s.penaltyUntil = system.currentTick + 80;
  safe("exhaust", () => applySpeed(horse, s));
  player.onScreenDisplay.setTitle("§c馬が疲れ切った！", {
    subtitle: `§7スタミナが${STAMINA_RECOVER_THRESHOLD}%に回復するまで加速できません`,
    fadeInDuration: 2,
    stayDuration: 30,
    fadeOutDuration: 8,
  });
  sound(player, "mob.horse.breathe", 0.8);
}

/** Update every rider. Call every 4 ticks. */
export function tickRiders() {
  const now = system.currentTick;
  const drainMul = S.settings.staminaDrain / 100;
  const regenMul = S.settings.staminaRegen / 100;
  const maxLevel = clamp(S.settings.maxAccel | 0, 1, 5);
  for (const p of allPlayers()) {
    const horse = ridingHorse(p);
    const prev = mounted.get(p.id);
    if (prev && (!horse || horse.id !== prev)) {
      onDismount(prev);
      mounted.delete(p.id);
    }
    if (!horse) continue;
    mounted.set(p.id, horse.id);
    lastRidden.set(p.id, { horseId: horse.id, tick: now });
    const s = stateOf(horse);
    let dt = (now - s.lastTick) / 20;
    if (dt < 0) dt = 0;
    s.lastTick = now;
    // speed from the distance travelled (ridden mounts often report no velocity)
    const loc = horse.location;
    let bps = 0;
    if (s.lastPos && dt > 0 && dt <= 1.5) {
      bps = Math.hypot(loc.x - s.lastPos.x, loc.z - s.lastPos.z) / dt;
      if (bps > 80) bps = 0; // teleported
    }
    s.lastPos = { x: loc.x, z: loc.z };
    s.bps = s.bps * 0.4 + bps * 0.6;
    if (dt > 1.5) {
      // the horse rested while nobody was riding it
      s.stamina += STAMINA_REGEN_IDLE * regenMul * Math.min(dt, 600);
      dt = 0.2;
    }
    const moving = s.bps > 1.5;
    if (s.level > maxLevel) s.level = maxLevel;
    if (s.level > 0) {
      if (moving) s.stamina -= STAMINA_DRAIN[Math.min(s.level, STAMINA_DRAIN.length - 1)] * drainMul * dt;
      if (s.stamina <= 0) exhaust(p, horse, s);
    } else {
      s.stamina += (moving ? STAMINA_REGEN_MOVING : STAMINA_REGEN_IDLE) * regenMul * dt;
    }
    s.stamina = clamp(s.stamina, 0, 100);
    if (s.exhausted && s.stamina >= STAMINA_RECOVER_THRESHOLD) {
      s.exhausted = false;
      sound(p, "random.orb", 1.2);
    }
    if (S.race.phase === "prep") {
      // horses are held at the start line until GO
      s.level = 0;
      s.applied = "";
      s.held = true;
      safe("hold", () => {
        horse.removeEffect("speed");
        horse.addEffect("slowness", 30, { amplifier: 255, showParticles: false });
      });
    } else {
      safe("speed", () => applySpeed(horse, s));
    }
    if (now - s.savedAt >= 40) save(horse, s);
  }
}

/**
 * Raise / lower the acceleration level of the ridden horse.
 * @param {Player} player
 * @param {number} delta
 */
export function changeLevel(player, delta) {
  const now = system.currentTick;
  const last = lastLevelChange.get(player.id) ?? -100;
  if (now - last < 4) return;
  lastLevelChange.set(player.id, now);
  const horse = ridingHorse(player);
  if (!horse) {
    flash(player, "§c馬に乗っている時だけ使えます");
    sound(player, "note.bass", 0.8);
    return;
  }
  const s = stateOf(horse);
  const max = clamp(S.settings.maxAccel | 0, 1, 5);
  if (delta > 0) {
    if (S.race.phase === "prep") {
      flash(player, "§eスタートの合図まで加速できません");
      sound(player, "note.bass", 0.8);
      return;
    }
    if (s.exhausted) {
      flash(player, `§c疲労中… スタミナが${STAMINA_RECOVER_THRESHOLD}%まで回復すると加速できます`);
      sound(player, "note.bass", 0.7);
      return;
    }
    if (s.level >= max) {
      flash(player, `§6加速レベルは最大(${max})です`);
      sound(player, "note.bass", 1.2);
      return;
    }
    s.level++;
    sound(player, "mob.horse.gallop", 1.0 + 0.1 * s.level);
    sound(player, "note.pling", 0.8 + 0.2 * s.level, 0.6);
  } else {
    if (s.level <= 0) {
      flash(player, "§7加速レベルは0です（スタミナ回復中）");
      return;
    }
    s.level--;
    sound(player, "note.pling", 0.6 + 0.15 * s.level, 0.6);
  }
  safe("speed", () => applySpeed(horse, s));
}

/**
 * HUD info for the horse a player is riding.
 * @param {Player} player
 */
export function horseHud(player) {
  const horse = ridingHorse(player);
  if (!horse) return undefined;
  const s = stateOf(horse);
  return {
    level: s.level,
    max: clamp(S.settings.maxAccel | 0, 1, 5),
    stamina: s.stamina,
    exhausted: s.exhausted,
    kmh: Math.round(s.bps * 3.6),
  };
}

/** Make every loaded horse invulnerable. Call every ~2 seconds. */
export function protectHorses() {
  for (const dimId of ["overworld", "nether", "the_end"]) {
    const dim = world.getDimension(dimId);
    for (const type of HORSE_TYPES) {
      /** @type {Entity[]} */
      let list = [];
      try {
        list = dim.getEntities({ type });
      } catch {
        continue;
      }
      for (const h of list) safe("protect", () => protect(h));
    }
  }
}

/** @param {Entity} h */
function protect(h) {
  /** @type {[string, number][]} */
  const effects = [
    ["resistance", 255],
    ["fire_resistance", 0],
    ["water_breathing", 0],
  ];
  for (const [eff, amp] of effects) {
    const e = h.getEffect(eff);
    if (!e || e.duration < 200) h.addEffect(eff, 1200, { amplifier: amp, showParticles: false });
  }
}

/** Heal horses immediately when they take damage. @param {Entity} h */
export function onHorseHurt(h) {
  safe("heal horse", () => {
    h.getComponent("minecraft:health")?.resetToMaxValue();
    h.extinguishFire(false);
  });
}

/** @param {string} horseId @param {(string|undefined)} ownerId */
export function onHorseDied(horseId, ownerId) {
  const owner = ownerId ?? ownerCache.get(horseId);
  states.delete(horseId);
  if (!owner) return;
  const p = playerById(owner);
  if (p) {
    giveItem(p, new ItemStack("minecraft:horse_spawn_egg", 1));
    giveItem(p, new ItemStack("minecraft:saddle", 1));
    tell(p, "§e愛馬がいなくなってしまった… 新しい馬のスポーンエッグと鞍を支給しました。");
  } else {
    const r = S.runners[owner];
    if (r) r.pendingEggs = (r.pendingEggs ?? 0) + 1;
  }
}

/**
 * Owner of a horse (player id) if known.
 * @param {Entity} h
 */
export function ownerOf(h) {
  const c = ownerCache.get(h.id);
  if (c) return c;
  try {
    const o = h.getDynamicProperty(EDP.owner);
    if (typeof o === "string") {
      ownerCache.set(h.id, o);
      return o;
    }
  } catch {
    /* ignore */
  }
  return undefined;
}

/**
 * The horse a player rode during the last few seconds (if still loaded).
 * @param {Player} player
 */
export function recentHorseOf(player) {
  const r = lastRidden.get(player.id);
  if (!r || system.currentTick - r.tick > 100) return undefined;
  const h = world.getEntity(r.horseId);
  return h && h.isValid ? h : undefined;
}

/**
 * A freshly spawned horse (e.g. from a spawn egg) is grown up and tamed to the
 * nearest player so it can be saddled right away.
 * @param {Entity} entity
 * @param {EntityInitializationCause} cause
 */
export function onEntitySpawn(entity, cause) {
  if (entity.typeId !== "minecraft:horse") return;
  if (cause === EntityInitializationCause.Loaded || cause === EntityInitializationCause.Born) return;
  system.runTimeout(() => {
    if (!entity.isValid) return;
    safe("setup horse", () => {
      if (ownerOf(entity)) return;
      // prefer the player who just used a spawn egg here, else the nearest player
      const now = system.currentTick;
      const loc = entity.location;
      const egg = eggUses
        .filter((e) => now - e.tick < 40 && Math.hypot(e.x - loc.x, e.z - loc.z) < 8)
        .sort((a, b) => Math.hypot(a.x - loc.x, a.z - loc.z) - Math.hypot(b.x - loc.x, b.z - loc.z))[0];
      const p = (egg && playerById(egg.playerId)) || entity.dimension.getPlayers({ location: loc, maxDistance: 8, closest: 1 })[0];
      if (!p) return;
      if (entity.getComponent("minecraft:is_baby")) entity.triggerEvent("minecraft:ageable_grow_up");
      entity.setDynamicProperty(EDP.owner, p.id);
      ownerCache.set(entity.id, p.id);
      system.runTimeout(() => {
        if (!entity.isValid) return;
        safe("tame horse", () => {
          const tm = entity.getComponent("minecraft:tamemount");
          if (tm) tm.tameToPlayer(true, p);
          protect(entity);
        });
        tell(p, "§a馬を手懐けました！ §f鞍を持って馬を使う(右クリック/長押し)と装着できます。");
      }, 2);
    });
  }, 2);
}
