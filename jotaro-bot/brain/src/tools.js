// Claude に渡す道具(行動)の定義。名前は体側(behavior_pack/scripts/main.js)の
// ACTIONS と一致させる。observe / remember / set_goal は頭脳側だけで処理する。

const xyz = {
  x: { type: "number" },
  y: { type: "number" },
  z: { type: "number" },
};

const tool = (name, description, properties = {}, required = []) => ({
  name,
  description,
  input_schema: { type: "object", properties, required },
});

export const TOOLS = [
  tool("say", "チャットで発言する。承太郎の口調で短く。", { message: { type: "string" } }, ["message"]),
  tool("observe", "最新の状況(自分の位置・体力・持ち物、周囲のプレイヤーと生き物、スタンドの状態)を取得する。"),
  tool("go_to", "指定した座標まで歩く。着くか、進めなくなるまで待つ。", xyz, ["x", "y", "z"]),
  tool("go_to_player", "プレイヤーのそばまで歩く。", { name: { type: "string" } }, ["name"]),
  tool(
    "follow",
    "プレイヤーについて歩き続ける。stop か別の移動・戦闘を始めるまで続く。",
    { name: { type: "string" } },
    ["name"],
  ),
  tool("stop", "いま実行中の行動と追従をすべて止める。"),
  tool("look_at", "相手や場所のほうを向く。entity_id、player、座標のどれかを指定する。", {
    entity_id: { type: "string" },
    player: { type: "string" },
    ...xyz,
  }),
  tool(
    "fight",
    "相手を倒すまで戦う(接近・殴る・スタンドのラッシュとスターフィンガーを自動で使う)。" +
      "entity_id か player を指定する。どちらも省くと一番近い敵対モブを狙う。" +
      "プレイヤーを狙うのは、相手から手合わせを頼まれたときか、攻撃されたときだけ。",
    {
      entity_id: { type: "string" },
      player: { type: "string" },
      use_stand: { type: "boolean", description: "スタンドを使うか。省略すると使う。" },
    },
  ),
  tool(
    "stand",
    "スタープラチナを操作する。summon=出す、retract=しまう、rush=オラオララッシュ(正面2.5ブロック先を約2秒殴り続ける)、" +
      "star_finger=スターフィンガー(正面3.5ブロック先を突く)、star_suck=吸い込み(周囲5ブロックの相手を引き寄せる)、" +
      "time_stop=時止め(発動まで約2秒、その後約3.5秒自分以外が止まる。再使用まで約30秒)。" +
      "技は自分が向いている方向に出るので、target_id か target_player を指定して相手のほうを向く。" +
      "ラッシュと吸い込みは範囲内の味方プレイヤーにも当たる。",
    {
      action: { type: "string", enum: ["summon", "retract", "rush", "star_finger", "star_suck", "time_stop"] },
      target_id: { type: "string" },
      target_player: { type: "string" },
    },
    ["action"],
  ),
  tool("find_blocks", "近くにあるブロックを種類名の一部で探す(例: log、iron_ore、crafting_table)。", {
    block: { type: "string" },
    radius: { type: "integer", description: "探す半径。最大10。" },
  }, ["block"]),
  tool("mine_block", "指定座標のブロックを壊して拾う。届かなければ先に近づく。", xyz, ["x", "y", "z"]),
  tool("place_block", "持っているブロックを指定座標に置く。隣に支えになるブロックが必要。", {
    item: { type: "string", description: "置くアイテム名(例: cobblestone、torch、crafting_table)" },
    ...xyz,
  }, ["item", "x", "y", "z"]),
  tool("interact_block", "ドア・ボタン・レバーなどを操作する。", xyz, ["x", "y", "z"]),
  tool("equip", "アイテムを手に持つ。防具(胸・脚・足)なら装備する。頭は帽子で埋まっている。", {
    item: { type: "string" },
  }, ["item"]),
  tool("use_item", "アイテムを使う(食べ物を食べる、など)。", {
    item: { type: "string" },
    hold_ticks: { type: "integer", description: "使い続ける長さ。20で1秒。食べ物は40程度。" },
  }, ["item"]),
  tool("give_item", "近く(5ブロック以内)のプレイヤーにアイテムを渡す。", {
    player: { type: "string" },
    item: { type: "string" },
    count: { type: "integer" },
  }, ["player", "item"]),
  tool(
    "craft",
    "材料からアイテムを作る。作れるもの: planks、stick、crafting_table、torch、furnace、chest、bread、bucket、shield、ladder、bed、" +
      "木・石・鉄・金・ダイヤの道具と剣(例: stone_pickaxe)、鉄・金・ダイヤの防具。" +
      "planks・stick・crafting_table・torch 以外は近くに作業台が必要。かまどでの精錬はできない。",
    { item: { type: "string" }, count: { type: "integer", description: "作る回数。省略すると1回。" } },
    ["item"],
  ),
  tool("jump", "その場でジャンプする。"),
  tool("sneak", "しゃがむ/立つ。", { on: { type: "boolean" } }, ["on"]),
  tool("wait", "何もせず待つ。", { seconds: { type: "number" } }, ["seconds"]),
  tool("remember", "後々まで覚えておくべきことをメモに残す(拠点の座標、約束、相手の好みなど)。", {
    note: { type: "string" },
  }, ["note"]),
  tool("set_goal", "いま取り組んでいる目標を書き換える。誰にも頼まれていないときに自分で何をするかの指針になる。", {
    goal: { type: "string" },
  }, ["goal"]),
];

export const LOCAL_TOOLS = new Set(["observe", "remember", "set_goal"]);
