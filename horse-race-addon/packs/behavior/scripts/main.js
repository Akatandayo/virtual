// Entry point: event wiring, loops and custom commands.
import { world, system, CommandPermissionLevel, CustomCommandStatus, GameMode } from "@minecraft/server";
import { HORSE_TYPES, ID } from "./constants.js";
import { S, flush, loadState, markDirty } from "./state.js";
import { flash, giveItem, hasItem, isAdmin, makeToolItem, safe, tell } from "./util.js";
import { changeLevel, isHorse, noteEggUse, onEntitySpawn, onHorseDied, onHorseHurt, ownerOf, protectHorses, tickRiders } from "./horse.js";
import { isProtectedBlock, isRacing, onJoin, onPlayerDeath, onRespawn, raceTickFast, raceTickSecond } from "./race.js";
import { updateHud } from "./hud.js";
import { chestMenu, fixGameMode, merchantInteract, openMenu } from "./ui.js";
import { CONTAINER_BLOCKS } from "./shop.js";
import { detectTerrain, scheduleTerrain } from "./terrain.js";
import { handleDevEvent } from "./devtools.js";

let ready = false;

// ---------------------------------------------------------------------------
// Custom commands (usable without cheats)

system.beforeEvents.startup.subscribe((ev) => {
  const reg = ev.customCommandRegistry;
  reg.registerCommand(
    {
      name: "hrace:menu",
      description: "ホースレースのメニューを開きます（参加者は順位表）",
      permissionLevel: CommandPermissionLevel.Any,
      cheatsRequired: false,
    },
    (origin) => {
      const p = origin.sourceEntity;
      if (!p || p.typeId !== "minecraft:player") return { status: CustomCommandStatus.Failure, message: "プレイヤーが実行してください" };
      system.run(() => openMenu(/** @type {import("@minecraft/server").Player} */ (p)));
      return { status: CustomCommandStatus.Success };
    },
  );
  reg.registerCommand(
    {
      name: "hrace:book",
      description: "レース設定の書をもらいます（主催者・OPのみ）",
      permissionLevel: CommandPermissionLevel.Any,
      cheatsRequired: false,
    },
    (origin) => {
      const p = origin.sourceEntity;
      if (!p || p.typeId !== "minecraft:player") return { status: CustomCommandStatus.Failure, message: "プレイヤーが実行してください" };
      const player = /** @type {import("@minecraft/server").Player} */ (p);
      system.run(() => {
        if (!isAdmin(player)) {
          tell(player, "§cこのアイテムは主催者（ワールドの最初のプレイヤー）とOPだけが使えます");
          return;
        }
        if (!hasItem(player, ID.config)) giveItem(player, makeToolItem(ID.config));
        tell(player, "§aレース設定の書を渡しました");
      });
      return { status: CustomCommandStatus.Success };
    },
  );
});

// ---------------------------------------------------------------------------
// Player lifecycle

/** @param {import("@minecraft/server").Player} p */
function onFirstSeen(p) {
  if (!S.meta.owner) {
    S.meta.owner = p.id;
    S.meta.ownerName = p.name;
    markDirty("meta");
  }
  if (S.meta.owner === p.id && !S.meta.givenBook.includes(p.id)) {
    giveItem(p, makeToolItem(ID.config));
    S.meta.givenBook.push(p.id);
    markDirty("meta");
    system.runTimeout(() => {
      tell(p, "§6§l[大陸横断ホースレース]§r §fあなたはこのワールドの主催者です。");
      tell(p, "§f「§eレース設定の書§f」を使うとレースの設定・開始ができます。チェストに使うとショップ等を登録できます。");
      tell(p, "§7(なくしたら /hrace:book で再入手できます)");
    }, 60);
  }
  safe("join", () => onJoin(p));
  safe("gamemode", () => fixGameMode(p));
}

world.afterEvents.playerSpawn.subscribe(({ player, initialSpawn }) => {
  if (!ready) return;
  if (initialSpawn) onFirstSeen(player);
  else safe("respawn", () => onRespawn(player));
});

// ---------------------------------------------------------------------------
// Items

world.afterEvents.itemUse.subscribe(({ source, itemStack }) => {
  if (!ready || source.typeId !== "minecraft:player") return;
  switch (itemStack.typeId) {
    case ID.spur:
      changeLevel(source, +1);
      break;
    case ID.reins:
      changeLevel(source, -1);
      break;
    case ID.config:
      if (isAdmin(source)) openMenu(source);
      else {
        tell(source, "§cレース設定の書は主催者だけが使えます");
        openMenu(source);
      }
      break;
  }
});

world.beforeEvents.playerInteractWithBlock.subscribe((ev) => {
  if (!ready) return;
  const { player, block, itemStack } = ev;
  if (itemStack?.typeId === ID.config && CONTAINER_BLOCKS.includes(block.typeId)) {
    ev.cancel = true;
    if (!ev.isFirstEvent) return;
    const loc = block.location;
    const dim = block.dimension;
    system.run(() => {
      if (!isAdmin(player)) {
        tell(player, "§cチェストの登録は主催者だけができます");
        return;
      }
      const b = dim.getBlock(loc);
      if (b) chestMenu(player, b).catch((e) => console.warn(`[hrace] chest menu: ${e}`));
    });
  }
});

world.afterEvents.playerInteractWithBlock.subscribe(({ player, beforeItemStack, block }) => {
  if (ready && beforeItemStack?.typeId === "minecraft:horse_spawn_egg") noteEggUse(player, block.location);
});

world.afterEvents.playerInteractWithEntity.subscribe(({ player, target, beforeItemStack }) => {
  if (!ready || target.typeId !== ID.merchant) return;
  const holdingBook = beforeItemStack?.typeId === ID.config;
  merchantInteract(player, target, holdingBook).catch((e) => console.warn(`[hrace] merchant: ${e}`));
});

// ---------------------------------------------------------------------------
// Protection of start / checkpoint platforms

world.beforeEvents.playerBreakBlock.subscribe((ev) => {
  if (!ready || !isProtectedBlock(ev.block.location)) return;
  const p = ev.player;
  if (isAdmin(p) && p.getGameMode() === GameMode.Creative) return;
  ev.cancel = true;
  system.run(() => flash(p, "§cチェックポイントは壊せません"));
});

// (placing has no cancelable event in the stable API: undo it right after)
world.afterEvents.playerPlaceBlock.subscribe(({ block, player }) => {
  if (!ready || !isProtectedBlock(block.location)) return;
  if (isAdmin(player) && player.getGameMode() === GameMode.Creative) return;
  safe("undo place", () => {
    const item = block.getItemStack(1, true);
    block.setType("minecraft:air");
    if (item && player.getGameMode() !== GameMode.Creative) giveItem(player, item);
    flash(player, "§cチェックポイントにはブロックを置けません");
  });
});

world.beforeEvents.explosion.subscribe((ev) => {
  if (!ready || S.race.phase === "idle") return;
  const blocks = ev.getImpactedBlocks();
  const keep = blocks.filter((b) => !isProtectedBlock(b.location));
  if (keep.length !== blocks.length) ev.setImpactedBlocks(keep);
});

// ---------------------------------------------------------------------------
// Entities

world.afterEvents.entitySpawn.subscribe(({ entity, cause }) => {
  if (!ready) return;
  safe("spawn", () => onEntitySpawn(entity, cause));
});

world.afterEvents.entityHurt.subscribe(
  ({ hurtEntity }) => {
    if (isHorse(hurtEntity)) onHorseHurt(hurtEntity);
  },
  { entityTypes: HORSE_TYPES },
);

world.afterEvents.entityDie.subscribe(({ deadEntity, damageSource }) => {
  if (!ready) return;
  if (deadEntity.typeId === "minecraft:player") {
    safe("death", () => onPlayerDeath(/** @type {import("@minecraft/server").Player} */ (deadEntity), damageSource.damagingEntity));
  } else if (isHorse(deadEntity)) {
    const id = deadEntity.id;
    const owner = safe("owner", () => ownerOf(deadEntity));
    safe("horse died", () => onHorseDied(id, owner));
  }
});

// ---------------------------------------------------------------------------
// Debug / test hooks (/scriptevent hrace:...)

system.afterEvents.scriptEventReceive.subscribe((ev) => {
  if (!ready || !ev.id.startsWith("hrace:")) return;
  safe("scriptevent", () => handleDevEvent(ev));
});

// ---------------------------------------------------------------------------
// Loops

function init() {
  loadState();
  ready = true;
  system.runInterval(() => {
    safe("riders", tickRiders);
    safe("hud", updateHud);
  }, 4);
  system.runInterval(() => safe("arrivals", raceTickFast), 5);
  system.runInterval(() => {
    for (const p of world.getAllPlayers()) {
      if (!S.meta.terrain) safe("detect", () => detectTerrain(p));
    }
    safe("terrain", scheduleTerrain);
  }, 10);
  system.runInterval(() => {
    safe("race", raceTickSecond);
    safe("flush", flush);
  }, 20);
  system.runInterval(() => safe("protect horses", protectHorses), 40);
  // players that are already online (e.g. after /reload)
  for (const p of world.getAllPlayers()) onFirstSeen(p);
  if (isRacing()) console.warn(`[hrace] race in progress restored (phase=${S.race.phase})`);
  console.warn("[hrace] Trans-Continental Horse Race loaded");
}

world.afterEvents.worldLoad.subscribe(() => {
  try {
    init();
  } catch (e) {
    console.error(`[hrace] init failed: ${e}`);
  }
});
