// Test / debug hooks, triggered with /scriptevent hrace:<name> <args>.
// Mostly used to test the add-on on a dedicated server without players.
import { world, system, BlockPermutation, GameMode } from "@minecraft/server";
import { S, markDirty } from "./state.js";
import { overworld, perm, simPlayers, sleep } from "./util.js";
import { decorateChunk, detectTerrainAt, resetTerrainCache, terrainStats } from "./terrain.js";
import { computeChunk, FILL_ORDER } from "./terrain_gen.js";
import { parseTrades, readItems, registerChest, clearShopCache, structureId } from "./shop.js";
import { devBuildPlatform, onPlayerDeath, resetRace, standings, startRace } from "./race.js";
import { updateHud } from "./hud.js";

/** @typedef {import("@minecraft/server").ScriptEventCommandMessageAfterEvent} ScriptEvent */

/** @param {string} msg */
function log(msg) {
  console.warn(`[hrace:test] ${msg}`);
}

/** @param {ScriptEvent} ev */
export function handleDevEvent(ev) {
  const name = ev.id.slice("hrace:".length);
  const args = ev.message.trim().split(/\s+/).filter(Boolean);
  const n = (/** @type {number} */ i, /** @type {number} */ d = 0) => {
    const v = Number(args[i]);
    return Number.isFinite(v) ? v : d;
  };
  const dim = overworld();
  switch (name) {
    case "status": {
      log(`phase=${S.race.phase} cps=${S.race.checkpoints.length} runners=${Object.keys(S.runners).length}`);
      log(`terrain=${JSON.stringify(S.meta.terrain)} stats=${JSON.stringify(terrainStats)}`);
      log(`chests=${JSON.stringify(S.meta.chests)} owner=${S.meta.ownerName}`);
      log(`settings=${JSON.stringify(S.settings)}`);
      break;
    }
    case "detect": {
      S.meta.terrain = undefined;
      resetTerrainCache();
      const ok = detectTerrainAt(dim, { x: n(0), z: n(1) });
      log(`detect ok=${ok} -> ${JSON.stringify(S.meta.terrain)}`);
      break;
    }
    case "blocks": {
      const ids = [
        "minecraft:sand",
        "minecraft:red_sand",
        "minecraft:grass_block",
        "minecraft:water",
        "minecraft:jungle_log",
        "minecraft:jungle_leaves",
        "minecraft:cactus",
        "minecraft:cactus_flower",
        "minecraft:reeds",
        "minecraft:short_grass",
        "minecraft:fern",
        "minecraft:deadbush",
        "minecraft:short_dry_grass",
        "minecraft:tall_dry_grass",
        "minecraft:orange_terracotta",
        "minecraft:hardened_clay",
        "minecraft:yellow_terracotta",
        "minecraft:white_terracotta",
        "minecraft:red_terracotta",
        "minecraft:brown_terracotta",
        "minecraft:light_gray_terracotta",
        "minecraft:smooth_sandstone",
        "minecraft:cut_red_sandstone",
        "minecraft:iron_block",
        "minecraft:gold_block",
        "minecraft:beacon",
        "minecraft:yellow_stained_glass",
        "minecraft:red_stained_glass",
        "minecraft:white_stained_glass",
        "minecraft:oak_fence",
        "minecraft:yellow_wool",
        "minecraft:red_wool",
        "minecraft:white_wool",
        "minecraft:lantern",
        "minecraft:standing_sign",
        "minecraft:sandstone",
      ];
      const bad = ids.filter((id) => {
        try {
          BlockPermutation.resolve(id);
          return false;
        } catch {
          return true;
        }
      });
      log(`unresolvable blocks: ${bad.length ? bad.join(", ") : "none"}`);
      log(`marker=${perm("minecraft:bedrock", { infiniburn_bit: true })?.type.id} leaves=${perm("minecraft:jungle_leaves", { persistent_bit: true })?.getState("persistent_bit")}`);
      break;
    }
    case "bench": {
      const seed = 12345;
      const t0 = Date.now();
      let blocks = 0;
      const count = n(0, 20);
      for (let i = 0; i < count; i++) {
        const lists = computeChunk(i, 7, seed, 63, () => false);
        for (const l of lists.values()) blocks += l.length;
      }
      log(`computeChunk x${count}: ${((Date.now() - t0) / count).toFixed(2)} ms/chunk, ${Math.round(blocks / count)} blocks/chunk`);
      break;
    }
    case "decorate": {
      const cx0 = n(0);
      const cz0 = n(1);
      const size = n(2, 1);
      const t = S.meta.terrain;
      if (!t) {
        log("no terrain info; run hrace:detect first");
        break;
      }
      system.runJob(
        (function* () {
          const t0 = Date.now();
          let ok = 0;
          for (let dz = 0; dz < size; dz++)
            for (let dx = 0; dx < size; dx++) {
              const r = yield* decorateChunk(dim, cx0 + dx, cz0 + dz, t);
              if (r) ok++;
            }
          log(`decorated ${ok}/${size * size} chunks in ${Date.now() - t0} ms (wall, incl. yields)`);
        })(),
      );
      break;
    }
    case "decorate_sync": {
      // decorate without yielding, to measure the raw cost per chunk
      const t = S.meta.terrain;
      if (!t) break;
      const cx0 = n(0);
      const cz0 = n(1);
      const size = n(2, 1);
      const t0 = Date.now();
      for (let dz = 0; dz < size; dz++)
        for (let dx = 0; dx < size; dx++) {
          const g = decorateChunk(dim, cx0 + dx, cz0 + dz, t);
          let r = g.next();
          while (!r.done) r = g.next();
        }
      log(`decorate_sync ${size * size} chunks: ${((Date.now() - t0) / (size * size)).toFixed(1)} ms/chunk`);
      break;
    }
    case "column": {
      // print the blocks of a column, e.g. /scriptevent hrace:column x z y0 y1
      const x = n(0);
      const z = n(1);
      const out = [];
      for (let y = n(3, 80); y >= n(2, 55); y--) {
        const b = dim.getBlock({ x, y, z });
        out.push(`${y}:${b ? b.typeId.replace("minecraft:", "") : "?"}`);
      }
      log(`column ${x},${z}: ${out.join(" ")}`);
      break;
    }
    case "surface": {
      // summary of the top blocks in an area
      const x0 = n(0);
      const z0 = n(1);
      const w = n(2, 64);
      /** @type {Record<string, number>} */
      const counts = {};
      /** @type {Record<number, number>} */
      const heights = {};
      for (let z = z0; z < z0 + w; z++)
        for (let x = x0; x < x0 + w; x++) {
          const b = dim.getTopmostBlock({ x, z });
          if (!b) continue;
          counts[b.typeId] = (counts[b.typeId] ?? 0) + 1;
          heights[b.y] = (heights[b.y] ?? 0) + 1;
        }
      log(`surface types: ${JSON.stringify(counts)}`);
      log(`surface heights: ${JSON.stringify(heights)}`);
      break;
    }
    case "register": {
      const b = dim.getBlock({ x: n(0), y: n(1), z: n(2) });
      if (!b) {
        log("block not loaded");
        break;
      }
      const role = /** @type {"shop"|"kit"|"reward"} */ (args[3] ?? "shop");
      log(registerChest(b, role, n(4, 0)));
      break;
    }
    case "read": {
      const role = /** @type {"shop"|"kit"|"reward"} */ (args[0] ?? "shop");
      clearShopCache();
      const items = readItems(structureId(role, n(1, 0)), dim, { x: n(2), z: n(3) });
      if (!items) {
        log("no items (structure missing or area not loaded)");
        break;
      }
      log(`slots=${items.length} filled=${items.filter(Boolean).length}`);
      log(
        `items: ${items
          .map((it, i) => (it ? `${i}:${it.typeId.replace("minecraft:", "")}x${it.amount}${it.nameTag ? `(${it.nameTag})` : ""}` : null))
          .filter(Boolean)
          .join(" ")}`,
      );
      if (role === "shop") {
        log(
          `trades: ${parseTrades(items)
            .map((t) => `${t.product.typeId}x${t.product.amount} <- ${t.prices.map((p) => `${p.typeId}x${p.amount}`).join("+") || "free"}`)
            .join(" | ")}`,
        );
        log(`localizationKey of first item: ${items.find(Boolean)?.localizationKey}`);
      }
      break;
    }
    case "platform": {
      const x = n(0);
      const z = n(1);
      const kind = /** @type {"start"|"cp"|"goal"} */ (args[2] ?? "cp");
      log(`platform at ground y=${devBuildPlatform(x, z, kind)}`);
      break;
    }
    case "horse": {
      const loc = { x: n(0) + 0.5, y: n(1), z: n(2) + 0.5 };
      const h = dim.spawnEntity("minecraft:horse", loc);
      const mv = h.getComponent("minecraft:movement");
      log(`horse movement current=${mv?.currentValue} default=${mv?.defaultValue} min=${mv?.effectiveMin} max=${mv?.effectiveMax}`);
      system.runTimeout(() => {
        const mv2 = h.getComponent("minecraft:movement");
        log(`after 10 ticks: current=${mv2?.currentValue} default=${mv2?.defaultValue} effects=${h.getEffects().map((e) => `${e.typeId}:${e.amplifier}`).join(",")}`);
        h.addEffect("speed", 100, { amplifier: 1, showParticles: false });
        log(`with speed II: current=${h.getComponent("minecraft:movement")?.currentValue}`);
        h.removeEffect("speed");
        const ok = h.getComponent("minecraft:movement")?.setCurrentValue(0.27);
        log(`setCurrentValue(0.27) ok=${ok} -> current=${h.getComponent("minecraft:movement")?.currentValue} default=${h.getComponent("minecraft:movement")?.defaultValue}`);
        h.addEffect("speed", 100, { amplifier: 1, showParticles: false });
        log(`after set + speed II: current=${h.getComponent("minecraft:movement")?.currentValue}`);
        const hp = h.getComponent("minecraft:health");
        h.applyDamage(5);
        log(`hp after 5 damage: ${hp?.currentValue}/${hp?.effectiveMax} tamemount=${!!h.getComponent("minecraft:tamemount")} baby=${!!h.getComponent("minecraft:is_baby")}`);
      }, 10);
      system.runTimeout(() => {
        if (!h.isValid) {
          log("horse no longer valid after 50 ticks");
          return;
        }
        const hp = h.getComponent("minecraft:health");
        log(`after 50 ticks: hp=${hp?.currentValue} resistance=${h.getEffect("resistance")?.amplifier} current speed=${h.getComponent("minecraft:movement")?.currentValue}`);
        h.applyDamage(1000);
        system.runTimeout(() => {
          log(`after 1000 damage: valid=${h.isValid} hp=${h.isValid ? h.getComponent("minecraft:health")?.currentValue : "-"}`);
        }, 2);
      }, 50);
      break;
    }
    case "sim": {
      runSimulation().catch((e) => log(`SIM ERROR: ${e}\n${e instanceof Error ? e.stack : ""}`));
      break;
    }
    case "order": {
      log(`fill order: ${FILL_ORDER.join(",")}`);
      break;
    }
    case "reset_terrain_flag": {
      S.meta.terrain = undefined;
      markDirty("meta");
      break;
    }
    default:
      log(`unknown test command ${name}`);
  }
  void world;
}

/**
 * A stand-in for a Player with just the members the race code uses.
 * @param {string} name
 * @param {number} x @param {number} z
 */
function makeSimPlayer(name, x, z) {
  const tags = new Set();
  /** @type {(import("@minecraft/server").ItemStack|undefined)[]} */
  const items = new Array(36).fill(undefined);
  let gm = GameMode.Survival;
  const container = {
    size: 36,
    getItem: (/** @type {number} */ i) => items[i],
    setItem: (/** @type {number} */ i, /** @type {any} */ it) => {
      items[i] = it;
    },
    addItem: (/** @type {any} */ it) => {
      const i = items.findIndex((v) => v === undefined);
      if (i >= 0) items[i] = it;
      return undefined;
    },
    clearAll: () => items.fill(undefined),
  };
  /** @type {any} */
  const mock = {
    id: `sim-${name}`,
    name,
    typeId: "minecraft:player",
    isValid: true,
    location: { x, y: 64, z },
    dimension: overworld(),
    playerPermissionLevel: 0,
    lastActionBar: "",
    items,
    hasTag: (/** @type {string} */ t) => tags.has(t),
    addTag: (/** @type {string} */ t) => (tags.add(t), true),
    removeTag: (/** @type {string} */ t) => tags.delete(t),
    getGameMode: () => gm,
    setGameMode: (/** @type {any} */ g) => {
      gm = g;
    },
    teleport(/** @type {any} */ loc) {
      mock.location = { x: loc.x, y: loc.y, z: loc.z };
    },
    setSpawnPoint(/** @type {any} */ sp) {
      mock.spawn = sp;
    },
    onScreenDisplay: {
      setTitle: (/** @type {string} */ t, /** @type {any} */ o) => log(`  [${name}] TITLE ${t} ${o?.subtitle ?? ""}`),
      setActionBar: (/** @type {string} */ t) => {
        mock.lastActionBar = t;
      },
    },
    sendMessage: (/** @type {any} */ m) => log(`  [${name}] MSG ${typeof m === "string" ? m : JSON.stringify(m)}`),
    playSound: () => {},
    getComponent: (/** @type {string} */ id) => (id === "minecraft:inventory" ? { container } : undefined),
    getRotation: () => ({ x: 0, y: -90 }),
    getVelocity: () => ({ x: 0, y: 0, z: 0 }),
  };
  return mock;
}

/** @param {string} label @param {boolean} ok */
function check(label, ok) {
  log(`${ok ? "PASS" : "FAIL"} ${label}`);
  return ok;
}

/**
 * Headless end-to-end run of a race with three simulated players.
 * Needs the area around 0,0 loaded (e.g. a ticking area).
 */
async function runSimulation() {
  log("SIM start");
  resetRace();
  simPlayers.length = 0;
  const A = makeSimPlayer("Alice", 2, 2);
  const B = makeSimPlayer("Bob", 3, 2);
  const C = makeSimPlayer("Carol", 4, 2);
  simPlayers.push(A, B, C);
  const savedOwner = S.meta.owner;
  const savedSettings = { ...S.settings };
  S.meta.owner = A.id;
  S.meta.start = { x: 0, y: 64, z: 0 };
  Object.assign(S.settings, {
    cpCount: 3,
    legDistance: 160,
    direction: 0,
    spread: 0,
    prepSeconds: 10,
    graceMinutes: 1,
    points: "10,7,5,3,2,1",
    goalMultiplier: 2,
    killBonus: 3,
    deathPenalty: 1,
    deathMode: 0,
    hostJoins: true,
  });
  try {
    const err = startRace(A);
    check(`startRace returned no error (${err ?? "ok"})`, !err);
    check(`phase is prep (${S.race.phase})`, S.race.phase === "prep");
    check(`3 checkpoints generated: ${S.race.checkpoints.map((c) => `${c.x},${c.z}`).join(" / ")}`, S.race.checkpoints.length === 3);
    check(`3 runners registered`, Object.keys(S.runners).length === 3);
    check(`scoreboard objective exists`, !!world.scoreboard.getObjective("hrace_pts"));
    await sleep(15);
    check(`kit given to Bob: ${B.items.filter(Boolean).map((/** @type {any} */ i) => i.typeId).join(",")}`, B.items.some((/** @type {any} */ i) => i?.typeId === "minecraft:horse_spawn_egg"));
    await sleep(20 * 11);
    check(`phase is running after prep (${S.race.phase})`, S.race.phase === "running");
    updateHud();
    log(`  HUD Bob: ${JSON.stringify(B.lastActionBar)}`);
    check("HUD shows CP1 for Bob", String(B.lastActionBar).includes("CP1"));
    const cps = S.race.checkpoints;
    const dim = overworld();
    const order = [
      [B, A, C],
      [A, B, C],
      [B, C, A],
    ];
    for (let i = 0; i < cps.length; i++) {
      const cp = cps[i];
      dim.runCommand(`tickingarea add circle ${cp.x} 64 ${cp.z} 1 hrace_sim_${i}`);
      await sleep(60);
      check(`CP${i + 1} built (y=${cp.y})`, cp.built);
      for (const p of order[i]) {
        p.teleport({ x: cp.x + 1, y: 65, z: cp.z + 1 });
        await sleep(8);
      }
      if (i === 0) {
        onPlayerDeath(C, A);
        log(`  after kill: A=${S.runners[A.id].points} C=${S.runners[C.id].points}`);
      }
      const merchants = dim.getEntities({ type: "hrace:merchant", location: { x: cp.x, y: 64, z: cp.z }, maxDistance: 8 });
      check(`merchant at CP${i + 1}`, merchants.length === 1);
    }
    await sleep(25);
    const pts = (/** @type {any} */ p) => S.runners[p.id]?.points;
    check(`Alice points 30 (got ${pts(A)})`, pts(A) === 30);
    check(`Bob points 37 (got ${pts(B)})`, pts(B) === 37);
    check(`Carol points 23 (got ${pts(C)})`, pts(C) === 23);
    check(`race finished (${S.race.phase}: ${S.race.endReason})`, S.race.phase === "finished");
    check(`winner is Bob (${standings()[0]?.name})`, standings()[0]?.name === "Bob");
    const sc = world.scoreboard.getObjective("hrace_pts");
    check(`scoreboard Bob=${sc?.getScore("Bob")}`, sc?.getScore("Bob") === 37);
    for (let i = 0; i < cps.length; i++) dim.runCommand(`tickingarea remove hrace_sim_${i}`);
  } finally {
    simPlayers.length = 0;
    S.meta.owner = savedOwner;
    Object.assign(S.settings, savedSettings);
    markDirty("meta", "settings");
    log("SIM end");
  }
}
