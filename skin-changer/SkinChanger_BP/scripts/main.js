import { world, system } from "@minecraft/server";

// アイテムID -> スキン番号 (0 = 元のスキン)
const SKIN_ITEMS = {
  "skin_changer:skin_1": 1,
  "skin_changer:skin_2": 2,
  "skin_changer:skin_3": 3,
  "skin_changer:skin_4": 4,
  "skin_changer:skin_5": 5,
  "skin_changer:reset": 0
};
const SKIN_NAMES = {
  "1": "スキン1",
  "2": "スキン2",
  "3": "スキン3",
  "4": "スキン4",
  "5": "スキン5",
  "0": "元のスキン"
};
const PROPERTY = "skin_changer:skin";

// 連打防止 (プレイヤーごとに 10 tick = 0.5秒)
const lastUse = new Map();

world.afterEvents.itemUse.subscribe((ev) => {
  const player = ev.source;
  const skin = SKIN_ITEMS[ev.itemStack.typeId];
  if (skin === undefined) return;

  const now = system.currentTick;
  if (now - (lastUse.get(player.id) ?? -100) < 10) return;
  lastUse.set(player.id, now);

  if (player.getProperty(PROPERTY) === skin) {
    player.onScreenDisplay.setActionBar(`§eすでに「${SKIN_NAMES[skin]}」です`);
    return;
  }
  player.setProperty(PROPERTY, skin);
  player.onScreenDisplay.setActionBar(`§aスキンを「${SKIN_NAMES[skin]}」に変更しました!`);
  player.playSound("random.orb", { pitch: 1.2 });
  player.dimension.spawnParticle("minecraft:villager_happy", {
    x: player.location.x,
    y: player.location.y + 1,
    z: player.location.z,
  });
});

world.afterEvents.playerLeave.subscribe((ev) => lastUse.delete(ev.playerId));
