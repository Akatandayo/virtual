// Claude Code(claude コマンド)を使って考える方式。
// APIキーの代わりに、Claude Code にログインしている Pro / Max プランの利用枠を使う。
// 1回の呼び出しで「次に実行する行動の一覧」を JSON で受け取る。
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

// プランの利用上限に達したときのエラー
export class UsageLimitError extends Error {}

// Claude Code が余計な設定やファイルを読み込まないよう、空のフォルダで実行する
const workDir = path.join(os.tmpdir(), "jotaro-bot-claude-code");
fs.mkdirSync(workDir, { recursive: true });

export function describeTools(tools) {
  return tools.map((t) => {
    const props = Object.entries(t.input_schema.properties ?? {}).map(([name, p]) => {
      const required = t.input_schema.required?.includes(name) ? "必須" : "任意";
      const kind = p.enum ? p.enum.join(" | ") : p.type;
      return `    - ${name} (${kind}、${required})${p.description ? `: ${p.description}` : ""}`;
    });
    return `- ${t.name}: ${t.description}${props.length ? `\n${props.join("\n")}` : ""}`;
  }).join("\n");
}

export function planSchema(tools) {
  return JSON.stringify({
    type: "object",
    properties: {
      actions: {
        type: "array",
        items: {
          type: "object",
          properties: {
            tool: { type: "string", enum: tools.map((t) => t.name) },
            input: { type: "object" },
          },
          required: ["tool", "input"],
        },
      },
      continue: { type: "boolean" },
    },
    required: ["actions", "continue"],
  });
}

export function askClaudeCode({ system, prompt, schema, model, effort }) {
  const args = [
    "-p",
    "--output-format", "json",
    "--tools", "", // ファイル操作などの組み込み機能は使わせない
    "--disable-slash-commands",
    "--strict-mcp-config",
    "--no-session-persistence",
    "--setting-sources", "",
    "--system-prompt", system,
    "--json-schema", schema,
  ];
  if (model) args.push("--model", model);
  if (effort) args.push("--effort", effort);

  // APIキーが設定されていると従量課金になってしまうので、子プロセスには渡さない
  const env = { ...process.env };
  delete env.ANTHROPIC_API_KEY;
  delete env.ANTHROPIC_AUTH_TOKEN;

  return new Promise((resolve, reject) => {
    const child = spawn("claude", args, { cwd: workDir, env, stdio: ["pipe", "pipe", "pipe"] });
    let out = "";
    let err = "";
    const timer = setTimeout(() => child.kill(), 120_000);
    child.stdout.on("data", (d) => { out += d; });
    child.stderr.on("data", (d) => { err += d; });
    child.on("error", (e) => {
      clearTimeout(timer);
      reject(e.code === "ENOENT"
        ? new Error("claude コマンドが見つかりません。Claude Code をインストールして、一度 claude を起動してログインしてください。")
        : e);
    });
    child.on("close", () => {
      clearTimeout(timer);
      let reply;
      try { reply = JSON.parse(out); } catch {
        reject(new Error(`Claude Code から読み取れない応答が返りました: ${(out || err).slice(0, 300)}`));
        return;
      }
      if (reply.is_error || !reply.structured_output) {
        const message = String(reply.result ?? err ?? "応答がありません");
        const limited = reply.api_error_status === 429 || /limit|上限/i.test(message);
        reject(limited ? new UsageLimitError(message) : new Error(`Claude Code がエラーを返しました: ${message.slice(0, 300)}`));
        return;
      }
      resolve(reply.structured_output);
    });
    child.stdin.end(prompt);
  });
}
