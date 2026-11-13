#!/usr/bin/env node
// ワールドの level.dat を書き換えて「ベータAPI」実験機能を有効にする。
// 使い方: node enable-beta-apis.mjs "<サーバーフォルダ>/worlds/<ワールド名>"
// 元のファイルは level.dat.bak として残す。サーバーを止めてから実行すること。
import fs from "node:fs";
import path from "node:path";

const T = { END: 0, BYTE: 1, SHORT: 2, INT: 3, LONG: 4, FLOAT: 5, DOUBLE: 6, BYTES: 7, STRING: 8, LIST: 9, COMPOUND: 10, INTS: 11, LONGS: 12 };
const FIXED = { [T.BYTE]: 1, [T.SHORT]: 2, [T.INT]: 4, [T.LONG]: 8, [T.FLOAT]: 4, [T.DOUBLE]: 8 };

// 値は生のバイト列のまま保持し、構造(複合タグ・リスト)だけを解釈する。
function readPayload(buf, pos, type) {
  if (FIXED[type]) return [buf.subarray(pos, pos + FIXED[type]), pos + FIXED[type]];
  if (type === T.STRING) {
    const len = buf.readUInt16LE(pos);
    return [buf.subarray(pos, pos + 2 + len), pos + 2 + len];
  }
  if (type === T.BYTES || type === T.INTS || type === T.LONGS) {
    const width = type === T.BYTES ? 1 : type === T.INTS ? 4 : 8;
    const len = buf.readInt32LE(pos);
    return [buf.subarray(pos, pos + 4 + len * width), pos + 4 + len * width];
  }
  if (type === T.LIST) {
    const itemType = buf.readUInt8(pos);
    const len = buf.readInt32LE(pos + 1);
    pos += 5;
    const items = [];
    for (let i = 0; i < len; i++) {
      let v;
      [v, pos] = readPayload(buf, pos, itemType);
      items.push(v);
    }
    return [{ list: itemType, items }, pos];
  }
  if (type === T.COMPOUND) {
    const entries = [];
    for (;;) {
      const t = buf.readUInt8(pos++);
      if (t === T.END) break;
      const nameLen = buf.readUInt16LE(pos);
      const name = buf.toString("utf8", pos + 2, pos + 2 + nameLen);
      pos += 2 + nameLen;
      let value;
      [value, pos] = readPayload(buf, pos, t);
      entries.push({ type: t, name, value });
    }
    return [{ compound: entries }, pos];
  }
  throw new Error(`未対応のNBTタグ: ${type}`);
}

function nameBytes(name) {
  const n = Buffer.from(name, "utf8");
  const len = Buffer.alloc(2);
  len.writeUInt16LE(n.length);
  return Buffer.concat([len, n]);
}

function writePayload(value) {
  if (Buffer.isBuffer(value)) return value;
  if (value.items) {
    const head = Buffer.alloc(5);
    head.writeUInt8(value.list, 0);
    head.writeInt32LE(value.items.length, 1);
    return Buffer.concat([head, ...value.items.map(writePayload)]);
  }
  const parts = [];
  for (const e of value.compound) parts.push(Buffer.from([e.type]), nameBytes(e.name), writePayload(e.value));
  parts.push(Buffer.from([T.END]));
  return Buffer.concat(parts);
}

function setByte(compound, name, n) {
  const found = compound.compound.find((e) => e.name === name);
  if (found) {
    found.type = T.BYTE;
    found.value = Buffer.from([n]);
  } else compound.compound.push({ type: T.BYTE, name, value: Buffer.from([n]) });
}

const worldDir = process.argv[2];
if (!worldDir) {
  console.error('使い方: node enable-beta-apis.mjs "<サーバーフォルダ>/worlds/<ワールド名>"');
  process.exit(1);
}
const file = path.join(worldDir, "level.dat");
const raw = fs.readFileSync(file);
const version = raw.readInt32LE(0);
const body = raw.subarray(8, 8 + raw.readInt32LE(4));
if (body.readUInt8(0) !== T.COMPOUND) throw new Error("level.dat の形式が想定と違います");
const rootNameLen = body.readUInt16LE(1);
const rootName = body.subarray(1, 3 + rootNameLen);
const [root] = readPayload(body, 3 + rootNameLen, T.COMPOUND);

let experiments = root.compound.find((e) => e.name === "experiments");
if (!experiments) {
  experiments = { type: T.COMPOUND, name: "experiments", value: { compound: [] } };
  root.compound.push(experiments);
}
setByte(experiments.value, "gametest", 1);
setByte(experiments.value, "experiments_ever_used", 1);
setByte(experiments.value, "saved_with_toggled_experiments", 1);

const newBody = Buffer.concat([Buffer.from([T.COMPOUND]), rootName, writePayload(root)]);
const header = Buffer.alloc(8);
header.writeInt32LE(version, 0);
header.writeInt32LE(newBody.length, 4);
fs.copyFileSync(file, file + ".bak");
fs.writeFileSync(file, Buffer.concat([header, newBody]));
console.log(`ベータAPIを有効にしました: ${file}（元のファイルは level.dat.bak）`);
