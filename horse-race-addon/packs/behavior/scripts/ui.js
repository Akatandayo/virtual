// Forms: organizer menu, settings, chest registration, standings.
import { system, world, GameMode } from "@minecraft/server";
import { ActionFormData, FormCancelationReason, MessageFormData, ModalFormData } from "@minecraft/server-ui";
import { ACCEL_POWER, DEATH_MODES, DIRECTIONS, EDP, TAG_SPECTATOR } from "./constants.js";
import { S, markDirty } from "./state.js";
import { clamp, dist2D, floorVec, fmtTime, isAdmin, safe, sleep, sound, tell } from "./util.js";
import { endRace, isRacing, pointsTable, resetRace, standings, startRace, teleportToNext } from "./race.js";
import { CONTAINER_BLOCKS, openShop, registerChest, unregister } from "./shop.js";
import { detectTerrainAt, resetTerrainCache, terrainActive, terrainStats } from "./terrain.js";

/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").Block} Block */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server-ui").ActionFormResponse} ActionFormResponse */

/** @type {Map<string, number>} player -> tick of last opened menu */
const lastOpen = new Map();

/**
 * Show a form, retrying while the player is busy (e.g. chat still open).
 * @template {{show(player: Player): Promise<any>}} F
 * @param {Player} player
 * @param {F} form
 * @returns {Promise<Awaited<ReturnType<F["show"]>>|undefined>}
 */
async function show(player, form) {
  for (let i = 0; i < 40; i++) {
    if (!player.isValid) return undefined;
    const res = await form.show(player);
    if (res.canceled && res.cancelationReason === FormCancelationReason.UserBusy) {
      await sleep(5);
      continue;
    }
    return res;
  }
  return undefined;
}

/**
 * @param {Player} player
 * @param {string} title
 * @param {string} body
 */
async function confirm(player, title, body) {
  const res = await show(player, new MessageFormData().title(title).body(body).button1("§lはい").button2("いいえ"));
  return !!res && !res.canceled && res.selection === 0;
}

/** Open the main menu (organizer or participant view). @param {Player} player */
export function openMenu(player) {
  const now = system.currentTick;
  if (now - (lastOpen.get(player.id) ?? -100) < 10) return;
  lastOpen.set(player.id, now);
  if (isAdmin(player)) adminMenu(player).catch((e) => console.warn(`[hrace] menu: ${e}`));
  else standingsMenu(player).catch((e) => console.warn(`[hrace] menu: ${e}`));
}

function statusText() {
  const r = S.race;
  const phaseName = { idle: "§7待機中", prep: "§e準備中", running: "§aレース中", finished: "§6終了" }[r.phase];
  const shops = S.meta.chests.shops.filter(Boolean).length;
  const t = S.meta.terrain;
  const terr = !t
    ? "§7判定待ち"
    : t.mode === "flat"
      ? S.settings.terrain
        ? `§a砂漠化ON §7(基準Y=${t.baseY}${t.classic ? ", 草原フラット" : ""})`
        : "§7砂漠化OFF"
      : "§7通常ワールド(地形はそのまま)";
  const start = S.meta.start ? `§fX:${S.meta.start.x} Z:${S.meta.start.z}` : "§7(開始時の主催者の位置)";
  return [
    `状態: ${phaseName}`,
    `スタート地点: ${start}`,
    `CP数: §e${S.settings.cpCount}§f / 1区間 約§e${S.settings.legDistance}§fブロック / 方向: §e${(DIRECTIONS[S.settings.direction] ?? DIRECTIONS[0]).label}`,
    `ショップ: §e${shops}§f件 / 支給品: ${S.meta.chests.kit ? "§a登録済" : "§7なし"} §f/ 到達報酬: ${S.meta.chests.reward ? "§a登録済" : "§7なし"}`,
    `地形: ${terr}`,
  ].join("\n§f");
}

/** @param {Player} player */
async function adminMenu(player) {
  /** @type {[string, () => Promise<unknown>|unknown][]} */
  const items = [];
  const racing = isRacing();
  if (!racing) {
    items.push(["§2§lレース開始", () => startFlow(player)]);
    items.push(["§lレースの設定", () => raceSettingsForm(player)]);
    items.push(["§l馬・スタミナの設定", () => horseSettingsForm(player)]);
    items.push(["§lスタート地点を現在地にする", () => setStart(player)]);
    items.push(["§l参加者の設定", () => participantsForm(player)]);
    items.push(["§lチェストの登録状況", () => chestStatusMenu(player)]);
    items.push(["§l地形(砂漠化)の設定", () => terrainMenu(player)]);
    if (S.race.phase === "finished") {
      items.push(["§l前回の結果", () => standingsMenu(player)]);
      items.push(["§c§l結果をリセット", () => resetFlow(player)]);
    }
    items.push(["§l遊び方", () => helpMenu(player)]);
  } else {
    items.push(["§l順位表", () => standingsMenu(player)]);
    items.push(["§lチェックポイント一覧", () => checkpointsMenu(player)]);
    items.push(["§lCPへテレポート(テスト用)", () => teleportFlow(player)]);
    items.push(["§6§lレースを終了して結果発表", () => finishFlow(player)]);
    items.push(["§4§lレースを中止(リセット)", () => resetFlow(player)]);
  }
  const form = new ActionFormData().title("§l大陸横断ホースレース").body(statusText());
  for (const [label] of items) form.button(label);
  form.button("閉じる");
  const res = await show(player, form);
  if (!res || res.canceled || res.selection === undefined || res.selection >= items.length) return;
  await items[res.selection][1]();
}

/** @param {Player} player */
async function startFlow(player) {
  const n = world.getAllPlayers().filter((p) => !p.hasTag(TAG_SPECTATOR) && (p.id !== player.id || S.settings.hostJoins)).length;
  const shops = S.meta.chests.shops.filter(Boolean).length;
  const warn = shops === 0 ? "\n§c※ショップ用チェストが未登録です（商人は何も売りません）" : "";
  const ok = await confirm(
    player,
    "レース開始",
    `参加者 ${n}人 でレースを開始します。\n参加者はスタート地点に集められ、馬のスポーンエッグ・鞍・拍車・手綱が配られます。${warn}\n\nよろしいですか？`,
  );
  if (!ok) return;
  const err = startRace(player);
  if (err) tell(player, err);
}

/** @param {Player} player */
async function resetFlow(player) {
  if (!(await confirm(player, "リセット", "レースの記録とチェックポイントを消去します。\n(設定と登録したチェストは残ります)\n\nよろしいですか？")))
    return;
  resetRace();
  tell(player, "§aレースをリセットしました");
}

/** @param {Player} player */
async function finishFlow(player) {
  if (!(await confirm(player, "レース終了", "今の順位でレースを終了し、結果を発表します。よろしいですか？"))) return;
  endRace("主催者がレースを終了しました");
}

/** @param {Player} player */
async function teleportFlow(player) {
  if (!teleportToNext(player)) tell(player, "§cチェックポイントがありません");
}

/** @param {Player} player */
function setStart(player) {
  if (player.dimension.id !== "minecraft:overworld") {
    tell(player, "§cオーバーワールドで設定してください");
    return;
  }
  S.meta.start = floorVec(player.location);
  markDirty("meta");
  tell(player, `§aスタート地点を X:${S.meta.start.x} Z:${S.meta.start.z} に設定しました`);
  sound(player, "random.orb");
}

/**
 * Read a ModalForm response; labels are not used so indices map 1:1 to inputs.
 * @param {(boolean|number|string|undefined)[]} values
 * @param {number} i
 * @param {number} fallback
 */
function num(values, i, fallback) {
  const v = values[i];
  return typeof v === "number" ? v : fallback;
}

/** @param {Player} player */
async function raceSettingsForm(player) {
  const s = S.settings;
  const form = new ModalFormData()
    .title("レースの設定")
    .slider("チェックポイント数（ゴールを含む）", 1, 20, { defaultValue: clamp(s.cpCount, 1, 20), valueStep: 1 })
    .slider("1区間の平均距離（ブロック）", 100, 5000, {
      defaultValue: clamp(Math.round(s.legDistance / 100) * 100, 100, 5000),
      valueStep: 100,
      tooltip: "チェックポイント同士の距離。実際は±20%でランダムに変わります",
    })
    .dropdown(
      "レースが進む方向",
      DIRECTIONS.map((d) => d.label),
      { defaultValueIndex: clamp(s.direction, 0, DIRECTIONS.length - 1) },
    )
    .slider("左右のブレ（度）", 0, 80, { defaultValue: clamp(s.spread, 0, 80), valueStep: 5, tooltip: "大きいほどジグザグなコースになります" })
    .slider("到達判定の半径（ブロック）", 4, 30, { defaultValue: clamp(s.arrivalRadius, 4, 30), valueStep: 1 })
    .textField("順位ごとのポイント（1位,2位,3位…）", "10,7,5,3,2,1", { defaultValue: String(s.points) })
    .slider("ゴールのポイント倍率", 1, 5, { defaultValue: clamp(s.goalMultiplier, 1, 5), valueStep: 1 })
    .slider("最初のゴール後、レース終了までの時間（分）", 0, 30, { defaultValue: clamp(s.graceMinutes, 0, 30), valueStep: 1 })
    .dropdown("ランナーが死亡したとき", DEATH_MODES, { defaultValueIndex: clamp(s.deathMode, 0, DEATH_MODES.length - 1) })
    .slider("撃破ボーナス（倒した側が得るポイント）", 0, 20, { defaultValue: clamp(s.killBonus, 0, 20), valueStep: 1 })
    .slider("死亡ペナルティ（倒された側が失うポイント）", 0, 20, { defaultValue: clamp(s.deathPenalty, 0, 20), valueStep: 1 })
    .slider("スタート前の準備時間（秒）", 10, 180, { defaultValue: clamp(s.prepSeconds, 10, 180), valueStep: 5 })
    .toggle("PvP（プレイヤー同士の攻撃）を有効にする", { defaultValue: !!s.pvp })
    .toggle("主催者（あなた）もレースに参加する", { defaultValue: !!s.hostJoins })
    .toggle("レース中の途中参加を許可する", { defaultValue: !!s.lateJoin })
    .toggle("開始時に参加者のインベントリを空にする", { defaultValue: !!s.clearInventory })
    .submitButton("保存");
  const res = await show(player, form);
  if (!res || res.canceled || !res.formValues) return;
  const v = res.formValues;
  s.cpCount = num(v, 0, s.cpCount);
  s.legDistance = num(v, 1, s.legDistance);
  s.direction = num(v, 2, s.direction);
  s.spread = num(v, 3, s.spread);
  s.arrivalRadius = num(v, 4, s.arrivalRadius);
  const pts = typeof v[5] === "string" ? v[5] : s.points;
  s.points = pts;
  if (pointsTable().length === 0) s.points = "10,7,5,3,2,1";
  s.goalMultiplier = num(v, 6, s.goalMultiplier);
  s.graceMinutes = num(v, 7, s.graceMinutes);
  s.deathMode = num(v, 8, s.deathMode);
  s.killBonus = num(v, 9, s.killBonus);
  s.deathPenalty = num(v, 10, s.deathPenalty);
  s.prepSeconds = num(v, 11, s.prepSeconds);
  s.pvp = v[12] === true;
  s.hostJoins = v[13] === true;
  s.lateJoin = v[14] === true;
  s.clearInventory = v[15] === true;
  markDirty("settings");
  tell(player, `§aレース設定を保存しました §7(順位ポイント: ${pointsTable().join(", ")})`);
}

/** @param {Player} player */
async function horseSettingsForm(player) {
  const s = S.settings;
  const form = new ModalFormData()
    .title("馬・スタミナの設定")
    .slider("最大加速レベル", 1, 5, { defaultValue: clamp(s.maxAccel, 1, 5), valueStep: 1 })
    .dropdown(
      "加速1レベルあたりの最高速度アップ",
      ACCEL_POWER.map((p) => `+${p}%`),
      { defaultValueIndex: clamp(s.accelPower, 0, ACCEL_POWER.length - 1) },
    )
    .slider("スタミナ消費の速さ（%）", 25, 300, { defaultValue: clamp(s.staminaDrain, 25, 300), valueStep: 25, tooltip: "100%が標準" })
    .slider("スタミナ回復の速さ（%）", 25, 300, { defaultValue: clamp(s.staminaRegen, 25, 300), valueStep: 25, tooltip: "100%が標準" })
    .toggle("馬の基本速度を全頭同じにする（公平モード）", { defaultValue: !!s.normalizeHorses })
    .submitButton("保存");
  const res = await show(player, form);
  if (!res || res.canceled || !res.formValues) return;
  const v = res.formValues;
  s.maxAccel = num(v, 0, s.maxAccel);
  s.accelPower = num(v, 1, s.accelPower);
  s.staminaDrain = num(v, 2, s.staminaDrain);
  s.staminaRegen = num(v, 3, s.staminaRegen);
  s.normalizeHorses = v[4] === true;
  markDirty("settings");
  tell(player, "§a馬の設定を保存しました");
}

/** @param {Player} player */
async function participantsForm(player) {
  const players = world.getAllPlayers();
  const form = new ModalFormData().title("参加者の設定");
  for (const p of players) {
    form.toggle(`${p.name}${p.id === player.id ? " §7(あなた)" : ""}`, {
      defaultValue: !p.hasTag(TAG_SPECTATOR) && (p.id !== player.id || !!S.settings.hostJoins),
      tooltip: "オンにするとランナーとして参加、オフは観戦",
    });
  }
  form.submitButton("保存");
  const res = await show(player, form);
  if (!res || res.canceled || !res.formValues) return;
  players.forEach((p, i) => {
    if (!p.isValid) return;
    const on = res.formValues?.[i] === true;
    if (p.id === player.id) {
      S.settings.hostJoins = on;
      markDirty("settings");
    }
    if (on) p.removeTag(TAG_SPECTATOR);
    else if (p.id !== player.id) p.addTag(TAG_SPECTATOR);
  });
  tell(player, "§a参加者の設定を保存しました");
}

/** @param {Player} player */
async function chestStatusMenu(player) {
  const c = S.meta.chests;
  /** @type {[string, () => void][]} */
  const actions = [];
  const lines = [
    "§e設定アイテムを持ってチェストをタップ（右クリック）§fすると、そのチェストの中身を登録できます。",
    "",
    "§6ショップ用チェストの並べ方",
    "§f・各「列」が1つの取引です",
    "§f・上段 = 売る品物 / 中段 = 代金 / 下段 = 2つ目の代金(任意)",
    "§f・個数がそのまま交換レートになります（例: 上段 金リンゴ1個、中段 エメラルド8個）",
    "§f・ラージチェストなら18取引まで",
    "§f・CPごとにショップ1,2,3…が順番に割り当てられます",
    "",
    "§6到達報酬チェスト: §f左の列から1位,2位…の報酬（右端の列は9位以下）",
    "§6スタート支給品チェスト: §f中身すべてが全員に配られます",
    "",
    "§6登録状況",
  ];
  c.shops.forEach((s, i) => {
    if (!s) return;
    lines.push(`§f・ショップ${i + 1}: 取引${s.trades}件`);
    actions.push([`§cショップ${i + 1}の登録を削除`, () => unregister("shop", i)]);
  });
  if (c.kit) {
    lines.push(`§f・スタート支給品: ${c.kit.trades}スタック`);
    actions.push(["§cスタート支給品の登録を削除", () => unregister("kit")]);
  }
  if (c.reward) {
    lines.push("§f・到達報酬: 登録済み");
    actions.push(["§c到達報酬の登録を削除", () => unregister("reward")]);
  }
  if (actions.length === 0) lines.push("§7(まだ何も登録されていません)");
  const form = new ActionFormData().title("チェストの登録").body(lines.join("\n"));
  for (const [label] of actions) form.button(label);
  form.button("閉じる");
  const res = await show(player, form);
  if (!res || res.canceled || res.selection === undefined || res.selection >= actions.length) return;
  actions[res.selection][1]();
  tell(player, "§a登録を削除しました");
}

/**
 * Organizer tapped a chest with the config book.
 * @param {Player} player
 * @param {Block} block
 */
export async function chestMenu(player, block) {
  const dim = block.dimension;
  const loc = block.location;
  const shops = S.meta.chests.shops;
  let free = shops.findIndex((s) => !s);
  if (free < 0) free = shops.length;
  /** @type {[string, (() => string)|null][]} */
  const opts = [];
  if (free < 9) opts.push([`§2新しいショップ${free + 1}として登録`, () => registerChest(/** @type {Block} */ (dim.getBlock(loc)), "shop", free)]);
  shops.forEach((s, i) => {
    if (s) opts.push([`ショップ${i + 1}を上書き`, () => registerChest(/** @type {Block} */ (dim.getBlock(loc)), "shop", i)]);
  });
  opts.push(["スタート支給品として登録", () => registerChest(/** @type {Block} */ (dim.getBlock(loc)), "kit")]);
  opts.push(["到達報酬として登録", () => registerChest(/** @type {Block} */ (dim.getBlock(loc)), "reward")]);
  opts.push(["§7キャンセル", null]);
  const form = new ActionFormData()
    .title("チェストの登録")
    .body(
      "このチェストの中身を何として登録しますか？\n\n§6ショップ: §f各列が1取引（上段=商品 / 中段=代金 / 下段=代金2）\n§6スタート支給品: §f中身が参加者全員に配られます\n§6到達報酬: §f左の列から1位,2位…の報酬（右端は9位以下）\n\n§7登録後にチェストの中身を変えた場合は、もう一度登録してください。",
    );
  for (const [label] of opts) form.button(label);
  const res = await show(player, form);
  if (!res || res.canceled || res.selection === undefined) return;
  const fn = opts[res.selection]?.[1];
  if (!fn) return;
  const b = dim.getBlock(loc);
  if (!b || !CONTAINER_BLOCKS.includes(b.typeId)) {
    tell(player, "§cチェストが見つかりません");
    return;
  }
  const msg = safe("register chest", fn) ?? "§c登録に失敗しました";
  tell(player, msg);
  sound(player, "random.orb");
}

/** @param {Player} player */
async function terrainMenu(player) {
  const t = S.meta.terrain;
  const lines = [
    "§fフラットワールド（草原タイプのフラット、または付属の砂漠テンプレート）で遊ぶと、",
    "§fプレイヤーの周りの地形が自動で §e砂丘・メサ・オアシス§f のある乾燥地帯に変わります。",
    "§7通常のワールドでは地形は変更しません。",
    "",
    `§f判定結果: ${!t ? "§7まだ判定していません" : t.mode === "flat" ? `§aフラットワールド (基準Y=${t.baseY})` : "§7通常ワールド"}`,
    `§f状態: ${terrainActive() ? "§a有効" : "§7無効"} §f/ 生成範囲: 半径${S.settings.terrainRadius}チャンク`,
    `§7このセッションで加工したチャンク: ${terrainStats.decorated} (平均${terrainStats.decorated ? Math.round(terrainStats.msTotal / terrainStats.decorated) : 0}ms)`,
  ];
  const form = new ActionFormData()
    .title("地形(砂漠化)の設定")
    .body(lines.join("\n"))
    .button(S.settings.terrain ? "§c砂漠化を無効にする" : "§2砂漠化を有効にする")
    .button("生成範囲を変更")
    .button("ワールドの種類を判定し直す")
    .button("閉じる");
  const res = await show(player, form);
  if (!res || res.canceled) return;
  if (res.selection === 0) {
    S.settings.terrain = !S.settings.terrain;
    markDirty("settings");
    tell(player, S.settings.terrain ? "§a砂漠化を有効にしました" : "§7砂漠化を無効にしました");
  } else if (res.selection === 1) {
    const f = new ModalFormData()
      .title("生成範囲")
      .slider("プレイヤーの周り何チャンクを加工するか", 3, 10, {
        defaultValue: clamp(S.settings.terrainRadius, 3, 10),
        valueStep: 1,
        tooltip: "大きいほど遠くまで加工しますが重くなります（おすすめ: 5〜7）",
      })
      .submitButton("保存");
    const r = await show(player, f);
    if (!r || r.canceled || !r.formValues) return;
    S.settings.terrainRadius = num(r.formValues, 0, S.settings.terrainRadius);
    markDirty("settings");
  } else if (res.selection === 2) {
    S.meta.terrain = undefined;
    resetTerrainCache();
    const ok = detectTerrainAt(player.dimension, player.location);
    const nt = /** @type {import("./state.js").TerrainInfo|undefined} */ (S.meta.terrain);
    tell(player, ok && nt ? `§a判定しました: ${nt.mode === "flat" ? `フラット (基準Y=${nt.baseY})` : "通常ワールド"}` : "§c判定できませんでした");
  }
}

/** @param {Player} player */
async function standingsMenu(player) {
  const race = S.race;
  const list = standings();
  const lines = [];
  if (race.phase === "idle") lines.push("§7レースはまだ始まっていません。");
  else {
    lines.push(`§f経過時間 ${fmtTime(race.elapsed)} / CP ${race.checkpoints.length}か所`);
    if (race.phase === "finished") lines.push(`§6レース終了: ${race.endReason}`);
    lines.push("");
    list.forEach((r, i) => {
      const status = r.finished ? `§aゴール(${fmtTime(r.finishTime)})` : r.eliminated ? "§c脱落" : `§7CP${r.cp}/${race.checkpoints.length}通過`;
      lines.push(`§e${i + 1}位 §b${r.name} §f${r.points}pt §8| ${status} §8| §7撃破${r.kills} 死亡${r.deaths}`);
    });
    const me = S.runners[player.id];
    const cp = me ? race.checkpoints[me.cp] : undefined;
    if (me && cp && race.phase === "running" && !me.finished && !me.eliminated) {
      lines.push("", `§f次の目標: §eX:${cp.x} Z:${cp.z} §7(あと約${Math.round(dist2D(player.location, cp))}ブロック)`);
    }
  }
  await show(player, new ActionFormData().title("順位表").body(lines.join("\n")).button("閉じる"));
}

/** @param {Player} player */
async function checkpointsMenu(player) {
  const race = S.race;
  const lines = [
    `§fスタート: X:${race.start?.x} Z:${race.start?.z}`,
    ...race.checkpoints.map(
      (cp, i) =>
        `${i === race.checkpoints.length - 1 ? "§cGOAL" : `§eCP${i + 1}`} §fX:${cp.x} Z:${cp.z} §7${cp.built ? "設置済" : "未設置(近づくと出現)"} / 通過${cp.arrivals.length}人`,
    ),
  ];
  await show(player, new ActionFormData().title("チェックポイント一覧").body(lines.join("\n")).button("閉じる"));
}

/** @param {Player} player */
async function helpMenu(player) {
  const lines = [
    "§6■ 準備（主催者）",
    "§f1. 設定アイテムでチェストをタップしてショップ・支給品・報酬を登録",
    "§f2. 「レースの設定」「馬・スタミナの設定」を調整",
    "§f3. スタート地点に立って「レース開始」",
    "",
    "§6■ レース",
    "§f・準備時間にスポーンエッグで馬を出し、鞍をつけて乗ります",
    "§f・画面上部の矢印と距離を頼りにチェックポイント(光の柱)を目指します",
    "§f・到達順にポイント獲得。ゴールはポイント倍率つき",
    "§f・ゴール時点で最もポイントが高い人が優勝",
    "§f・他のランナーを倒すと撃破ボーナス！",
    "",
    "§6■ 馬の操作",
    "§f・拍車(緑の矢印)を使う: 加速レベル+1（速くなるがスタミナ消費）",
    "§f・手綱(赤の矢印)を使う: 加速レベル-1",
    "§f・加速レベル0で走るとスタミナが回復",
    "§f・スタミナ0で馬が疲労し、しばらく加速できません",
    "§f・馬は死にません",
    "",
    "§6■ コマンド",
    "§f/hrace:menu …メニュー（参加者は順位表）",
    "§f/hrace:book …設定アイテムを再入手（主催者/OPのみ）",
  ];
  await show(player, new ActionFormData().title("遊び方").body(lines.join("\n")).button("閉じる"));
}

/**
 * Interaction with a merchant NPC.
 * @param {Player} player
 * @param {Entity} merchant
 * @param {boolean} holdingBook
 */
export async function merchantInteract(player, merchant, holdingBook) {
  if (holdingBook && isAdmin(player)) {
    const shops = S.meta.chests.shops;
    const form = new ActionFormData()
      .title("商人の管理")
      .body("この商人の設定を変更します。")
      .button("取引画面を開く")
      .button("売るショップを選ぶ")
      .button("§cこの商人を撤去する")
      .button("閉じる");
    const res = await show(player, form);
    if (!res || res.canceled) return;
    if (res.selection === 0) await openShop(player, merchant);
    else if (res.selection === 1) {
      const labels = ["CPの番号で自動"];
      /** @type {number[]} */
      const idx = [-1];
      shops.forEach((s, i) => {
        if (s) {
          labels.push(`ショップ${i + 1}（取引${s.trades}件）`);
          idx.push(i);
        }
      });
      const r = await show(player, new ModalFormData().title("ショップの選択").dropdown("この商人が売る品物", labels).submitButton("決定"));
      if (!r || r.canceled || !r.formValues) return;
      const sel = idx[num(r.formValues, 0, 0)];
      merchant.setDynamicProperty(EDP.shop, sel >= 0 ? sel : undefined);
      tell(player, "§a設定しました");
    } else if (res.selection === 2) {
      merchant.remove();
      tell(player, "§7商人を撤去しました");
    }
    return;
  }
  await openShop(player, merchant);
}

/** Give a player back to survival when they were left in spectator by an old race. @param {Player} p */
export function fixGameMode(p) {
  if (!isRacing() && p.getGameMode() === GameMode.Spectator && S.runners[p.id]?.eliminated) {
    safe("gm", () => p.setGameMode(GameMode.Survival));
  }
}

