// 承太郎ボットの「頭脳」。
// 体側(サーバー内スクリプト)が 0.5 秒ごとに状況を送ってくるので、それを受け取り、
// 出来事があったとき・しばらく何もないときに Claude へ次の行動を決めさせる。
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Anthropic from "@anthropic-ai/sdk";
import { TOOLS, LOCAL_TOOLS } from "./tools.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
try { process.loadEnvFile(path.join(root, ".env")); } catch { /* .env が無ければ環境変数だけを使う */ }

const MODEL = process.env.MODEL || "claude-opus-5-5";
const EFFORT = process.env.EFFORT || "low";
const PORT = Number(process.env.PORT || 3920);
const IDLE_MS = Number(process.env.IDLE_SECONDS || 60) * 1000;
const MAX_CALLS_PER_HOUR = Number(process.env.MAX_CALLS_PER_HOUR || 300);
const MAX_STEPS = 12; // 1回の思考で道具を使える回数の上限
const MEMORY_FILE = path.join(root, "memory.json");

const client = new Anthropic();
const persona = fs.readFileSync(path.join(root, "persona.md"), "utf8");

const SYSTEM = `${persona}

## この世界での動き方
あなたは道具(tool)を使ってゲーム内の体を動かす。発言は必ず say で行う。say 以外の出力は誰にも見えない。
- 状況は JSON で渡される。座標は x・y・z(y が高さ)。entities の id は fight や look_at にそのまま使える。
- 話しかけられたら応じる。自分宛てでない雑談には、毎回は口を挟まない。
- 頼みごとは、できる範囲で実際に体を動かしてやり遂げる。できないことは短くそう言う。
- 誰にも頼まれていないときは、目標やメモを手がかりに自分で動く。仲間の近くにいる、周囲を警戒する、夜は敵を片づける、資材を集める、など。何もする必要がなければ道具を使わずに終えてよい。同じ独り言を繰り返さない。
- 敵対モブが仲間や自分に近いときは fight で片づける。体力が少ないときは距離を取るか食べ物を使う。
- スタンドの技は周囲の味方にも当たる。仲間のすぐそばではラッシュ・吸い込み・時止めを使わない。手合わせを頼まれた場合は別。
- 一度に長く考え込まない。数手で区切りをつけ、続きは次の機会に回す。
- かまどやチェストの画面、エンチャント、取引は扱えない。`;

// ───────── 記憶 ─────────

let memory = { goal: "仲間のそばにいて、危険があれば片づける。", notes: [] };
try { memory = { ...memory, ...JSON.parse(fs.readFileSync(MEMORY_FILE, "utf8")) }; } catch { /* 初回は既定値 */ }
const saveMemory = () => fs.writeFileSync(MEMORY_FILE, JSON.stringify(memory, null, 2));

const journal = []; // 直近の出来事と自分の行動
function note(line) {
  const time = new Date().toLocaleTimeString("ja-JP", { hour12: false });
  journal.push(`[${time}] ${line}`);
  if (journal.length > 40) journal.shift();
  console.log(`[${time}] ${line}`);
}

// ───────── 体との通信 ─────────

let state = null;
let lastTick = 0;
let outbox = [];
let nextId = 1;
const pending = new Map(); // 行動ID → 結果を待っている resolve
let fresh = []; // 思考の途中で届いた出来事
let triggers = [];
let wake = null;
const lastTrigger = {};
let knownHostiles = new Set();

function trigger(reason, throttleMs = 0) {
  const now = Date.now();
  if (throttleMs && now - (lastTrigger[reason] ?? 0) < throttleMs) return;
  lastTrigger[reason] = now;
  triggers.push(reason);
  wake?.();
}

function describe(ev) {
  switch (ev.type) {
    case "chat": return `${ev.from} の発言: 「${ev.text}」`;
    case "hurt": return `ダメージを受けた(${ev.damage}、原因 ${ev.by ?? ev.cause}、残り体力 ${ev.hp})`;
    case "died": return `倒されてしまった(原因 ${ev.cause})`;
    case "respawned": return "復活した";
    case "spawned": return "サーバーに入った";
    case "player_join": return `${ev.name} がサーバーに入ってきた`;
    case "player_leave": return `${ev.name} がサーバーから出ていった`;
    case "auto_defend": return `${ev.target} に殴られたので反撃を始めた`;
    default: return JSON.stringify(ev);
  }
}

function onTick(body) {
  state = body.state;
  lastTick = Date.now();
  for (const r of body.results ?? []) {
    const resolve = pending.get(r.id);
    if (resolve) { pending.delete(r.id); resolve(r); }
    else if (String(r.id).startsWith("auto-")) note(`自動反撃の結果: ${r.result ?? r.error ?? (r.ok ? "完了" : "失敗")}`);
  }
  for (const ev of body.events ?? []) {
    const line = describe(ev);
    note(line);
    fresh.push(line);
    if (ev.type === "chat") trigger("話しかけられた、または近くで会話があった");
    else if (ev.type === "hurt") trigger("攻撃を受けた", 8000);
    else if (ev.type === "died" || ev.type === "auto_defend") { /* 記録だけ */ }
    else trigger(line);
  }
  const hostiles = new Set((state.entities ?? []).filter((e) => e.hostile && e.dist <= 10).map((e) => e.id));
  if ([...hostiles].some((id) => !knownHostiles.has(id)) && state.doing !== "fight") trigger("敵対モブが近くに現れた", 15000);
  knownHostiles = hostiles;
  const actions = outbox;
  outbox = [];
  return { actions };
}

function act(type, params) {
  const id = `a${nextId++}`;
  outbox.push({ id, type, ...params });
  return new Promise((resolve) => {
    pending.set(id, resolve);
    setTimeout(() => {
      if (pending.delete(id)) resolve({ ok: false, error: "体から応答がない(時間切れ)" });
    }, 90_000);
  });
}

http.createServer((req, res) => {
  if (req.method !== "POST" || req.url !== "/tick") { res.writeHead(404).end(); return; }
  let raw = "";
  req.on("data", (chunk) => { raw += chunk; });
  req.on("end", () => {
    try {
      const reply = onTick(JSON.parse(raw));
      res.writeHead(200, { "Content-Type": "application/json" }).end(JSON.stringify(reply));
    } catch (e) {
      console.error("受信データを処理できませんでした:", e);
      res.writeHead(400).end();
    }
  });
}).listen(PORT, "127.0.0.1", () => {
  console.log(`頭脳を起動しました。127.0.0.1:${PORT} で体からの接続を待っています(モデル: ${MODEL}、effort: ${EFFORT})`);
});

// ───────── Claude ─────────

const calls = []; // 直近1時間の呼び出し時刻
const usage = { input: 0, output: 0, cached: 0 };

let useFallbacks = true;

async function ask(messages) {
  const params = {
    model: MODEL,
    max_tokens: 16000,
    system: [{ type: "text", text: SYSTEM, cache_control: { type: "ephemeral" } }],
    tools: TOOLS,
    messages,
    output_config: { effort: EFFORT },
  };
  let response;
  if (useFallbacks) {
    try {
      // モデルが応答を断ったとき、同じ依頼を代わりのモデルで自動的にやり直す設定つきで呼ぶ
      response = await client.beta.messages.create({
        ...params,
        betas: ["server-side-fallback-2026-07-01"],
        fallbacks: "default",
      });
    } catch (e) {
      if (!(e instanceof Anthropic.BadRequestError)) throw e;
      console.warn(`代替モデルの設定がこのモデルでは使えないようです。設定なしで続けます。(${e.message})`);
      useFallbacks = false;
    }
  }
  response ??= await client.messages.create(params);
  calls.push(Date.now());
  usage.input += response.usage.input_tokens;
  usage.output += response.usage.output_tokens;
  usage.cached += response.usage.cache_read_input_tokens ?? 0;
  return response;
}

async function runTool(name, input) {
  if (name === "observe") return state;
  if (name === "remember") {
    memory.notes.push(String(input.note));
    if (memory.notes.length > 30) memory.notes.shift();
    saveMemory();
    return { ok: true };
  }
  if (name === "set_goal") {
    memory.goal = String(input.goal);
    saveMemory();
    return { ok: true };
  }
  if (name === "say") note(`承太郎: 「${input.message}」`);
  const result = await act(name, input);
  if (name !== "say") note(`行動 ${name} ${JSON.stringify(input)} → ${result.result ?? result.error ?? (result.ok ? "完了" : "失敗")}`);
  const { id, ...rest } = result;
  return rest;
}

async function think(reason) {
  fresh = [];
  const messages = [{
    role: "user",
    content: [
      `【きっかけ】${reason}`,
      `【現在の目標】${memory.goal}`,
      `【メモ】${memory.notes.length ? memory.notes.map((n) => `\n- ${n}`).join("") : "なし"}`,
      `【直近の出来事と自分の行動】\n${journal.slice(-25).join("\n") || "なし"}`,
      `【現在の状況】\n${JSON.stringify(state)}`,
    ].join("\n\n"),
  }];

  for (let step = 0; step < MAX_STEPS; step++) {
    const response = await ask(messages);
    if (response.stop_reason === "refusal") { console.warn("モデルが応答を断りました。この回は何もしません。"); return; }
    if (response.stop_reason === "max_tokens") { console.warn("応答が長すぎて途中で切れました。この回は打ち切ります。"); return; }
    messages.push({ role: "assistant", content: response.content });
    const uses = response.content.filter((b) => b.type === "tool_use");
    if (response.stop_reason === "pause_turn") continue;
    if (uses.length === 0) return;

    const content = [];
    for (const use of uses) {
      let result;
      try {
        if (!TOOLS.some((t) => t.name === use.name)) result = { ok: false, error: "その道具は無い" };
        else result = await runTool(use.name, use.input ?? {});
      } catch (e) {
        result = { ok: false, error: String(e) };
      }
      content.push({
        type: "tool_result",
        tool_use_id: use.id,
        content: JSON.stringify(result),
        is_error: result?.ok === false && !LOCAL_TOOLS.has(use.name),
      });
    }
    if (fresh.length) {
      content.push({ type: "text", text: `【この間に起きたこと】\n${fresh.join("\n")}` });
      fresh = [];
      triggers = [];
    }
    messages.push({ role: "user", content });
  }
}

// ───────── 主ループ ─────────

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const connected = () => state && Date.now() - lastTick < 5000;

function waitForTrigger(ms) {
  if (triggers.length) return Promise.resolve();
  return new Promise((resolve) => {
    const timer = setTimeout(done, ms);
    function done() { clearTimeout(timer); wake = null; resolve(); }
    wake = done;
  });
}

async function main() {
  let wasConnected = false;
  for (;;) {
    await waitForTrigger(IDLE_MS);
    if (!connected()) {
      if (wasConnected) console.log("体との接続が切れました。再接続を待ちます。");
      wasConnected = false;
      triggers = [];
      await sleep(1000);
      continue;
    }
    if (!wasConnected) console.log(`体と接続しました: ${state.name}`);
    wasConnected = true;

    const hourAgo = Date.now() - 3_600_000;
    while (calls.length && calls[0] < hourAgo) calls.shift();
    if (calls.length >= MAX_CALLS_PER_HOUR) {
      console.warn("1時間あたりの呼び出し上限に達しました。しばらく休みます。");
      triggers = [];
      await sleep(60_000);
      continue;
    }

    const reason = triggers.length ? [...new Set(triggers)].join(" / ") : "しばらく何も起きていない。自分で次にすることを決める。";
    triggers = [];
    try {
      await think(reason);
      console.log(`  (累計トークン: 入力 ${usage.input} / うちキャッシュ ${usage.cached} / 出力 ${usage.output})`);
    } catch (e) {
      if (e instanceof Anthropic.AuthenticationError) {
        console.error("APIキーが正しくありません。brain/.env の ANTHROPIC_API_KEY を確認してください。");
        await sleep(30_000);
      } else if (e instanceof Anthropic.RateLimitError) {
        console.warn("APIの利用制限に達しました。30秒待ちます。");
        await sleep(30_000);
      } else if (e instanceof Anthropic.APIConnectionError) {
        console.warn("APIに接続できませんでした。10秒後にやり直します。");
        await sleep(10_000);
      } else if (e instanceof Anthropic.APIError) {
        console.error(`APIエラー (${e.status}): ${e.message}`);
        await sleep(10_000);
      } else {
        console.error("思考中にエラー:", e);
        await sleep(5_000);
      }
    }
    await sleep(1500);
  }
}

main();
