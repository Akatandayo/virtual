#!/usr/bin/env node
// 承太郎ボットを統合版サーバー(Bedrock Dedicated Server)に組み込む。
//   node tools/install.mjs "<サーバーフォルダ>" [--addon "<スタンドアドオンの.mcaddon>"]
// やること:
//   1. ビヘイビアーパックとリソースパックをサーバーへコピー
//   2. スクリプトに外部通信(@minecraft/server-net)を許可
//   3. ワールドにパックを登録
//   4. ワールドの「ベータAPI」実験機能を有効化
// --addon を付けると、スタンドアドオンの展開と登録も一緒に行う。
// サーバーを止めてから実行すること。
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const project = path.resolve(here, "..");

const args = process.argv.slice(2);
const addonAt = args.indexOf("--addon");
const addon = addonAt >= 0 ? args.splice(addonAt, 2)[1] : undefined;
const serverDir = args[0] && path.resolve(args[0]);

function fail(message) {
  console.error(`エラー: ${message}`);
  process.exit(1);
}

if (!serverDir) fail('サーバーフォルダを指定してください。例: node tools/install.mjs "C:\\bedrock-server"');
if (!fs.existsSync(path.join(serverDir, "server.properties"))) fail(`${serverDir} に server.properties がありません。サーバーフォルダの場所を確認してください。`);

const properties = fs.readFileSync(path.join(serverDir, "server.properties"), "utf8");
const levelName = /^level-name=(.*)$/m.exec(properties)?.[1].trim() || "Bedrock level";
const worldDir = path.join(serverDir, "worlds", levelName);
if (!fs.existsSync(path.join(worldDir, "level.dat"))) {
  fail(`ワールド「${levelName}」がまだありません。サーバーを一度起動してワールドを作り、止めてからやり直してください。`);
}

// フォルダを丸ごとコピーする。Windows では fs.cpSync が無言で落ちることがあるため、1ファイルずつ写す
function copyDir(from, to) {
  fs.mkdirSync(to, { recursive: true });
  for (const entry of fs.readdirSync(from, { withFileTypes: true })) {
    const src = path.join(from, entry.name);
    const dst = path.join(to, entry.name);
    if (entry.isDirectory()) copyDir(src, dst);
    else if (entry.isFile()) fs.copyFileSync(src, dst);
  }
}

const readManifest = (dir) => JSON.parse(fs.readFileSync(path.join(dir, "manifest.json"), "utf8").replace(/^\uFEFF/, ""));

// パックをサーバーへコピーし、ワールドに登録する
function installPack(source, folderName) {
  const manifest = readManifest(source);
  const isResource = manifest.modules.some((m) => m.type === "resources");
  const target = path.join(serverDir, isResource ? "resource_packs" : "behavior_packs", folderName);
  console.log(`  コピー中: ${folderName} ...`);
  copyDir(source, target);

  const listFile = path.join(worldDir, isResource ? "world_resource_packs.json" : "world_behavior_packs.json");
  let list = [];
  try { list = JSON.parse(fs.readFileSync(listFile, "utf8")); } catch { /* まだ無ければ新規作成 */ }
  list = list.filter((p) => p.pack_id !== manifest.header.uuid);
  list.push({ pack_id: manifest.header.uuid, version: manifest.header.version });
  fs.writeFileSync(listFile, JSON.stringify(list, null, 2));
  console.log(`  ${isResource ? "リソース" : "ビヘイビアー"}パックを登録: ${folderName}`);
  return manifest;
}

console.log(`サーバー: ${serverDir}`);
console.log(`ワールド: ${levelName}`);

if (addon) {
  if (!fs.existsSync(addon)) fail(`アドオンのファイルが見つかりません: ${addon}`);
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "jobot-addon-"));
  const zip = path.join(temp, "addon.zip");
  fs.copyFileSync(addon, zip);
  const out = path.join(temp, "out");
  fs.mkdirSync(out);
  // .mcaddon の中身は zip。Windows は標準の tar、それ以外は unzip で展開する
  if (process.platform === "win32") execFileSync("tar", ["-xf", zip, "-C", out]);
  else execFileSync("unzip", ["-q", zip, "-d", out]);
  const packs = fs.readdirSync(out).filter((name) => fs.existsSync(path.join(out, name, "manifest.json")));
  if (packs.length === 0) fail("アドオンの中にパックが見つかりませんでした。");
  console.log("スタンドアドオン:");
  for (const name of packs) installPack(path.join(out, name), `stand_${name}`);
  fs.rmSync(temp, { recursive: true, force: true });
}

console.log("承太郎ボット:");
const behavior = installPack(path.join(project, "behavior_pack"), "jotaro_bot");
installPack(path.join(project, "resource_pack"), "jotaro_bot");

const scriptModule = behavior.modules.find((m) => m.type === "script");
const configDir = path.join(serverDir, "config", scriptModule.uuid);
fs.mkdirSync(configDir, { recursive: true });
fs.copyFileSync(path.join(project, "server_config", "permissions.json"), path.join(configDir, "permissions.json"));
console.log("  スクリプトに外部通信を許可しました");

execFileSync(process.execPath, [path.join(here, "enable-beta-apis.mjs"), worldDir], { stdio: "inherit" });

if (!/^texturepack-required=true$/m.test(properties)) {
  console.log("\n注意: server.properties の texturepack-required を true にすると、参加者全員に承太郎の見た目が確実に表示されます。");
}
console.log("\n完了しました。次は start-brain.bat で頭脳プログラムを起動し、サーバーを起動してください。");
