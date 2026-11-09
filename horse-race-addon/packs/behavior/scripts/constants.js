// Shared identifiers and default settings.

export const ID = {
  config: "hrace:race_config",
  spur: "hrace:spur",
  reins: "hrace:reins",
  merchant: "hrace:merchant",
};

/** Mounts that get the stamina / acceleration system. */
export const HORSE_TYPES = ["minecraft:horse", "minecraft:donkey", "minecraft:mule"];

/** World dynamic property keys (each stores a JSON document, split in parts). */
export const DP = {
  settings: "hrace:settings",
  race: "hrace:race",
  runners: "hrace:runners",
  meta: "hrace:meta",
};

/** Entity dynamic property keys. */
export const EDP = {
  stamina: "hrace:stamina",
  level: "hrace:level",
  owner: "hrace:owner",
  cp: "hrace:cp",
  raceId: "hrace:race",
  shop: "hrace:shop",
};

export const TAG_ADMIN = "hrace_admin";
export const TAG_SPECTATOR = "hrace_watch";

/** Direction presets. angle: degrees, 0 = +X (east), 90 = +Z (south). */
export const DIRECTIONS = [
  { label: "東へ (+X)", angle: 0 },
  { label: "西へ (-X)", angle: 180 },
  { label: "南へ (+Z)", angle: 90 },
  { label: "北へ (-Z)", angle: 270 },
  { label: "ランダム", angle: -1 },
];

/** Speed bonus per acceleration level, in percent (one Speed effect level = 20%). */
export const ACCEL_POWER = [20, 40, 60];

export const DEATH_MODES = ["最後に通過したCPから復帰", "脱落（観戦モードになる）"];

export const DEFAULT_SETTINGS = {
  cpCount: 5, // number of checkpoints including the goal
  legDistance: 800, // average distance between checkpoints
  direction: 0,
  spread: 30, // max sideways deviation per leg (degrees)
  arrivalRadius: 10,
  points: "10,7,5,3,2,1",
  goalMultiplier: 2,
  graceMinutes: 5,
  deathMode: 0,
  killBonus: 3,
  deathPenalty: 1,
  maxAccel: 3,
  accelPower: 1, // index into ACCEL_POWER
  staminaDrain: 100, // percent
  staminaRegen: 100, // percent
  prepSeconds: 45,
  hostJoins: true,
  lateJoin: true,
  clearInventory: false,
  normalizeHorses: true,
  pvp: true,
  terrain: true,
  terrainRadius: 6,
};

/** Stamina drain per second at each acceleration level (index = level). */
export const STAMINA_DRAIN = [0, 1.6, 3.4, 6.5, 10, 15];
export const STAMINA_REGEN_MOVING = 2.5;
export const STAMINA_REGEN_IDLE = 4.0;
export const STAMINA_RECOVER_THRESHOLD = 30; // exhausted until stamina reaches this
export const NORMALIZED_HORSE_SPEED = 0.27; // vanilla range 0.1125 - 0.3375
