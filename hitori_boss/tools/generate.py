# -*- coding: utf-8 -*-
"""電子 独（不具合・Glitch）ボスアドオン生成スクリプト.

使い方: python3 hitori_boss/tools/generate.py [skin.png]
BP / RP を生成し、dist/ に .mcaddon を作ります（Pillow が必要）。
"""
import json
import math
import os
import random
import argparse
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hanims  # noqa: E402
import hfx  # noqa: E402
from cine import (brushup_files, FOE_ANY, RIVAL_FAMILY, Cine, add_arc_trails, add_rival, aim_at_foes, bake_smooth,  # noqa: E402
                  pause_events, split_melee, apply_stance_groups, stance_events, stance_filters, STANCE_ANIM,
                  encounter_cmds, foe_tag_anim, near_filters, rival_target, smooth_client, split_dashes,
                  vectorize_animations)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BP = os.path.join(ROOT, "Hitori_BP")
RP = os.path.join(ROOT, "Hitori_RP")
DIST = os.path.join(ROOT, "dist")

ID = "hitori:denshi_hitori"
NAME = "電子 独"
VERSION = [1, 9, 0]
MIN_ENGINE = [1, 21, 0]
UUID_BP_HEADER = "9b78d68f-ebde-4768-989c-96ab7fa09e02"
UUID_BP_MODULE = "9263edb8-7005-4aa3-82a3-54ec6c07aaf0"
UUID_RP_HEADER = "3afd756a-176b-43ec-a0d3-e9a6d255c62a"
UUID_RP_MODULE = "3d795900-fa4f-42b5-ba52-110c1c66fda3"

HP = 700            # 集団戦向けに強化
PHASE2_HP = 350     # 50%: ↓FREEDOM DiVE↓ 解放
FINAL_HP = 175      # 25%: Re: End of a Dream
GLITCH_LIMIT = {0: 10, 1: 13, 2: 15}   # 何回連続で当てれば Glitch が壊れるか
HIT_COOLDOWN = 0.5   # 連打対策: この間隔より速いヒットは数えない
DECAY = 1.0          # この秒数ごとに負荷が 1 下がる
STUN = 3.5           # 強制解除の時間
REBOOT = 3.0         # 復帰後、負荷を受け付けない時間
OBJ = "hitori_glitch"
OBJ_PLAYERS = "hitori_players"
STUN_V, FINAL_V = 99, 20

# BGM・レコード（音源は著作物なので、公開リポジトリには含めずビルド時に変換して入れる）
BGM_MEMORY = "hitori.bgm.kakuzetsu"       # eight - 隔絶された記憶（通常時）
BGM_DIVE = "hitori.bgm.freedom_dive"      # xi - FREEDOM DiVE（↓FREEDOM DiVE↓ 解放後）
DISC_ID = "hitori:music_disc_kakuzetsu"
DISC_SOUND_EVENT = "11"   # カスタムレコードはバニラのレコード音しか指定できないため「11」を差し替えて使う
SOUND_DIR = "sounds/hitori"
AUDIO = {  # 出力ファイル名: (ステレオ?, 品質)
    "kakuzetsu_bgm": (True, 4),
    "freedom_dive_bgm": (True, 4),
    "kakuzetsu_record": (False, 3),   # ジュークボックス用はモノラル（音が位置で聞こえるように）
}

random.seed(801)  # 誕生日 8/1
BOSS = "@e[type=%s,c=1]" % ID
NEAREST = "@p[r=48,m=!creative]"


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not isinstance(data, str) and os.path.abspath(path).startswith(os.path.abspath(BP) + os.sep):
        add_rival(data, ID)     # プレイヤーへのダメージ命令を、ほかのボスにも当たるように複製する
        aim_at_foes(data, ID)   # 技の狙いを「一番近い敵（プレイヤー・ほかのボス）」に
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(data, str):
            f.write(data)
        elif "/animations/" in path.replace(os.sep, "/"):
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))   # キーが多いので詰めて書く
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# コマンド用ヘルパー
# ---------------------------------------------------------------------------
def say(text):
    return '/tellraw @a[r=48] {"rawtext":[{"text":"%s"}]}' % text.replace('"', '\\"')


def p(r=24, rm=None):
    return "@a[r=%s%s,m=!creative]" % (r, ",rm=%s" % rm if rm is not None else "")


def pt(name, pos="~ ~ ~"):
    return "/particle hitori:%s %s" % (name, pos)


def at_players(r, name, pos="~ ~ ~"):
    return "/execute at %s run particle hitori:%s %s" % (p(r), name, pos)


def at_fam(fam, cmd):
    return "/execute at @e[family=%s] run %s" % (fam, cmd)


def shake(i, sec, r=24):
    return "/camerashake add @a[r=%d] %.2f %.2f positional" % (r, i, sec)


def sound(name, pitch=1.0, r=40, vol=1.0):
    return "/playsound %s @a[r=%d] ~ ~ ~ %.1f %.2f" % (name, r, vol, pitch)


def flash(r, g, b, rad=32, t=(0.05, 0.1, 0.2)):
    return "/camera @a[r=%d] fade time %.2f %.2f %.2f color %d %d %d" % (rad, t[0], t[1], t[2], r, g, b)


def summon_marker(kind, pos="~ ~ ~", at=None):
    cmd = "summon hitori:marker %s hitori:as_%s" % (pos, kind)
    return "/execute at %s run %s" % (at, cmd) if at else "/" + cmd


def behind(dist=1.5):
    return "/execute as %s at @s positioned ^ ^ ^-%.1f run tp %s ~ ~ ~ facing @s" % (NEAREST, dist, BOSS)


def despawn(fam):
    return "/event entity @e[family=%s] hitori:despawn" % fam


SKILLS = {}


def skill(v, name, length, tl):
    SKILLS[v] = (name, length, {"%.2f" % k: c for k, c in sorted(tl.items())})


def add(tl, t, cmds):
    tl.setdefault(round(t, 2), []).extend(cmds)


def rnd_off(r):
    return "~%.1f ~ ~%.1f" % (random.uniform(-r, r), random.uniform(-r, r))


# ---------------------------------------------------------------------------
# 技
# ---------------------------------------------------------------------------
# 1 ラグスパイク: カクカク瞬間移動して背後から突く
tl = {0: [say("§b独§7「……ラグってる？　ごめんね」"), sound("note.bit", 0.5)]}
for t in (0.1, 0.3, 0.5):
    add(tl, t, [pt("afterimage", "~ ~0.9 ~"), "/execute at %s run tp @s %s" % (NEAREST, rnd_off(4)),
                pt("noise_burst", "~ ~1 ~"), sound("note.bit", 1.5 + t, 30)])
add(tl, 0.75, [pt("afterimage", "~ ~0.9 ~"), behind(), flash(0, 0, 0, 16, (0, 0.05, 0.05))])
add(tl, 0.9, ["/damage %s 17 entity_attack entity @s" % p(3.5), at_players(3.5, "noise_burst", "~ ~1 ~"),
              sound("random.glass", 0.6, 30), shake(0.6, 0.3, 10)])
skill(1, "ラグスパイク", 1.2, tl)

# 2 Remake: 位置を記録 → 巻き戻し（ロールバック）
tl = {0: [say("§b【Remake】§7「――最初から、やり直そっか」"), summon_marker("rollback", at=p(48)),
          at_players(48, "error_one", "~ ~2.4 ~"), sound("random.orb", 0.5)]}
for t in (0.3, 0.6, 0.9, 1.2):
    add(tl, t, [at_fam("rollback", "particle hitori:warn_cyan ~ ~0.1 ~"), sound("note.bit", 2.0 - t * 0.6, 40, 0.6)])
add(tl, 1.4, ["/execute as %s at @s run tp @s @e[family=rollback,c=1]" % p(48),
              at_fam("rollback", "damage @a[r=1.6,m=!creative] 16 magic entity %s" % BOSS),
              at_fam("rollback", "particle hitori:noise_big ~ ~1 ~"),
              "/effect %s nausea 5 0 true" % p(48), flash(40, 255, 255, 48), sound("random.glass", 0.5, 48),
              shake(0.7, 0.4, 48)])
add(tl, 1.6, [despawn("rollback")])
skill(2, "Remake", 2.2, tl)

# 3 Missing Texture: ピンクと黒の欠損ブロックが出現して爆発（2 波）
tl = {0: [say("§d【Missing Texture】§7「あれ、テクスチャ読み込めてないや」"), sound("random.glass", 1.5)]}
for fam, t0 in (("missing_a", 0.1), ("missing_b", 0.9)):
    cmds = [summon_marker(fam, at=p(32))]
    for _ in range(4):
        cmds.append(summon_marker(fam, rnd_off(4), at=p(32)))
    add(tl, t0, cmds)
    for dt in (0.05, 0.3, 0.55, 0.8):
        add(tl, t0 + dt, [at_fam(fam, "particle hitori:missing_tex ~ ~0.8 ~"),
                          at_fam(fam, "particle hitori:warn_magenta ~ ~0.1 ~")])
    add(tl, t0 + 1.1, [at_fam(fam, "damage @a[r=2.6,m=!creative] 15 entity_explosion entity %s" % BOSS),
                       at_fam(fam, "particle hitori:missing_burst ~ ~0.8 ~"),
                       at_fam(fam, "particle hitori:noise_burst ~ ~0.8 ~"),
                       at_fam(fam, "playsound random.explode @a[r=24] ~ ~ ~ 0.7 1.6"),
                       shake(0.5, 0.3, 32), despawn(fam)])
skill(3, "Missing Texture", 2.2, tl)

# 4 座標破損 NaN: 浮かされ、座標がガタつき、叩きつけられる
tl = {0: [say("§c【座標破損】§7「x = NaN、y = NaN……あはは」"), "/effect %s levitation 2 3 true" % p(14),
          "/effect %s nausea 6 0 true" % p(14), at_players(14, "noise_big", "~ ~1 ~"), sound("random.glass", 0.4)]}
for i in range(6):
    t = 0.2 + i * 0.2
    add(tl, t, ["/execute as %s at @s run tp @s ~ ~0.35 ~" % p(16), at_players(16, "noise_burst", "~ ~1 ~"),
                sound("note.bit", 0.5 + i * 0.2, 30, 0.6)])
add(tl, 1.6, ["/damage %s 14 magic entity @s" % p(18), at_players(18, "shockwave", "~ ~0.1 ~"),
              "/effect %s slowness 3 2 true" % p(18), flash(255, 0, 80, 24), shake(0.8, 0.4, 24)])
skill(4, "座標破損", 2.2, tl)

# 5 フレーム落ち: 時間が止まったかのように動けず、コマ送りで殴られる
tl = {0: [say("§7【フレーム落ち】§f「カク、カク、カク……」"), "/effect %s slowness 2 255 true" % p(10),
          sound("note.bit", 0.5)]}
for i, (t, side) in enumerate(((0.4, "^1.3 ^ ^"), (0.9, "^-1.3 ^ ^"), (1.4, "^ ^ ^-1.3"))):
    add(tl, t - 0.05, [pt("afterimage", "~ ~0.9 ~"),
                       "/execute as %s at @s positioned %s run tp %s ~ ~ ~ facing @s" % (NEAREST, side, BOSS),
                       flash(0, 0, 0, 16, (0, 0.1, 0.05))])
    add(tl, t, ["/damage %s 9 entity_attack entity @s" % p(3.2), at_players(3.2, "noise_burst", "~ ~1 ~"),
                sound("random.glass", 0.8 + i * 0.2, 30), shake(0.4, 0.2, 10)])
skill(5, "フレーム落ち", 2.0, tl)

# 6 ☂Mebius☂: 操縦権を奪い、ぐるぐる回して放り投げる
tl = {0: [say("§9【☂Mebius☂】§7「操縦権、もらうね」"), sound("beacon.activate", 1.5)]}
for i in range(32):
    t = 0.1 + i * 0.05
    add(tl, t, ["/execute as %s at @s facing entity %s feet run tp @s ^0.55 ^ ^ facing %s" % (p(14), BOSS, BOSS)])
    if i % 4 == 0:
        add(tl, t, [at_players(14, "bit_trail", "~ ~1 ~"), sound("note.bit", 1.0 + i * 0.03, 30, 0.5)])
add(tl, 1.8, ["/damage %s 16 entity_attack entity @s" % p(14), "/effect %s levitation 1 8 true" % p(14),
              pt("shockwave", "~ ~0.1 ~"), at_players(14, "noise_big", "~ ~1 ~"), sound("random.explode", 1.4),
              shake(0.8, 0.4, 16)])
skill(6, "Mebius", 2.2, tl)

# 7 ✮Northern Lights✮: オーロラの輪が 3 回広がる
tl = {0: [say("§a【✮Northern Lights✮】§7「綺麗でしょ？　……見惚れてる場合じゃないよ」"), pt("aurora_sky"),
          sound("beacon.power", 1.2, 48)]}
for t0 in (0.4, 1.0, 1.6):
    add(tl, t0, [pt("aurora_ring", "~ ~0.1 ~"), pt("shockwave", "~ ~0.1 ~"), sound("random.orb", 0.6 + t0 * 0.3)])
    for k in range(14):
        t = t0 + 0.1 * k
        rad = 2 + 13 * 0.1 * k
        add(tl, t, ["/damage %s 12 magic entity @s" % p("%.1f" % (rad + 0.9), "%.1f" % max(0, rad - 0.9))])
skill(7, "Northern Lights", 3.2, tl)

# 8 番狂わせ: 位置を入れ替え、呪いをかける
tl = {0: [say("§e【番狂わせ】§7「入れ替わっちゃった。……どっちが本物？」"), sound("note.bit", 1.8)],
      0.35: [summon_marker("swap_a"), summon_marker("swap_b", at=NEAREST),
             "/tp @s @e[family=swap_b,c=1]",
             "/execute at @e[family=swap_b,c=1] run tp @p[r=3,m=!creative] @e[family=swap_a,c=1]",
             at_fam("swap_a", "particle hitori:noise_big ~ ~1 ~"), at_fam("swap_b", "particle hitori:noise_big ~ ~1 ~"),
             flash(255, 255, 255, 32), sound("mob.endermen.portal", 1.6)],
      0.6: [at_fam("swap_a", "damage @a[r=2.5,m=!creative] 12 magic entity %s" % BOSS),
            at_fam("swap_a", "effect @a[r=2.5,m=!creative] blindness 3 0 true"),
            at_fam("swap_a", "effect @a[r=2.5,m=!creative] poison 4 1 true"),
            at_fam("swap_a", "effect @a[r=2.5,m=!creative] hunger 8 2 true"),
            at_fam("swap_a", "particle hitori:error_popup ~ ~1 ~")],
      0.8: [despawn("swap_a"), despawn("swap_b")]}
skill(8, "番狂わせ", 1.4, tl)

# 9 目を隠す: 姿を消し、背後から二度刺す
tl = {0: [say("§8【目を隠す】§7「……見えないでしょ」"), "/effect @s invisibility 2 0 true",
          "/effect %s darkness 3 0 true" % p(20), "/effect %s blindness 2 0 true" % p(20), pt("afterimage", "~ ~0.9 ~")]}
for t in (0.5, 1.3):
    add(tl, t, [behind(1.3)])
    add(tl, t + 0.15, ["/damage %s 14 entity_attack entity @s" % p(3.2), at_players(3.2, "noise_burst", "~ ~1 ~"),
                       sound("random.glass", 1.2, 20), shake(0.5, 0.2, 8)])
skill(9, "目を隠す", 2.2, tl)

# 10 俯瞰: 空から見下ろし、ノイズの柱を落とす
tl = {0: [say("§f【俯瞰】§7「上から、全部見えてるよ」"), pt("afterimage", "~ ~0.9 ~"), "/tp @s ~ ~9 ~",
          "/effect @s slow_falling 3 0 true", sound("beacon.activate", 0.8)]}
for k, t in enumerate((0.4, 1.0, 1.6, 2.2)):
    fam = "beam_%s" % "ab"[k % 2]
    add(tl, t, [summon_marker(fam, at=p(40))])
    for dt in (0.05, 0.25, 0.45):
        add(tl, t + dt, [at_fam(fam, "particle hitori:beam_warn ~ ~ ~"), at_fam(fam, "particle hitori:warn_red ~ ~0.1 ~")])
    add(tl, t + 0.55, [at_fam(fam, "particle hitori:beam_column ~ ~ ~"), at_fam(fam, "particle hitori:noise_burst ~ ~0.5 ~"),
                       at_fam(fam, "damage @a[r=1.9,m=!creative] 14 magic entity %s" % BOSS),
                       at_fam(fam, "playsound beacon.deactivate @a[r=24] ~ ~ ~ 1 1.8"),
                       shake(0.3, 0.2, 40), despawn(fam)])
skill(10, "俯瞰", 2.8, tl)

# 11 データ弾: ノイズの弾を連射
tl = {0: [say("§d【Bit Shot】§7「バン、バン、バン」")]}
spread = [(-14, 2), (-5, 6), (4, 12), (-10, 9), (0, 14), (10, -2)]
for i, (a1, a2) in enumerate(spread):
    t = 0.35 + i * 0.18
    add(tl, t, ["/summon hitori:bit_bullet ^ ^1.3 ^0.6 hitori:aim_%s" % ("m%d" % -a if a < 0 else a) for a in (a1, a2)]
        + [sound("note.bit", 1.0 + i * 0.15, 30), pt("noise_burst", "^ ^1.3 ^0.8")])
skill(11, "Bit Shot", 1.6, tl)

# 12 フォークボム（第二形態以降）: 自爆する欠片を生む
tl = {0: [say("§c【Fork Bomb】§7「増えて、増えて、弾けて」"), sound("mob.evocation_illager.prepare_summon", 1.6)],
      0.8: ["/summon hitori:fragment ^1.5 ^1 ^", "/summon hitori:fragment ^-1.5 ^1 ^", "/summon hitori:fragment ^ ^1 ^-1.5",
            pt("noise_big", "~ ~1 ~"), sound("random.glass", 1.8)]}
skill(12, "Fork Bomb", 1.4, tl)

# 13 DESTRUCTION 3,2,1（第二形態以降）: 独のそば以外すべてを破壊
tl = {0: ["/title @a[r=48] title §c§lDESTRUCTION", "/title @a[r=48] subtitle §73, 2, 1――",
          "/effect @s slowness 4 255 true", sound("mob.wither.spawn", 1.6, 48)]}
for i, (t, n, pit) in enumerate(((0.5, "3", 0.7), (1.5, "2", 0.9), (2.5, "1", 1.2))):
    add(tl, t, [pt("num_" + n, "~ ~4.5 ~"), sound("note.bit", pit, 48), sound("note.bass", pit, 48),
                "/title @a[r=48] actionbar §a§l安全地帯 → 独のすぐそば（4マス以内）", flash(255, 0, 0, 48, (0, 0.05, 0.2))])
for k in range(7):
    add(tl, 0.2 + k * 0.5, [pt("safe_zone", "~ ~0.1 ~")])
add(tl, 3.5, ["/damage %s 30 entity_explosion entity @s" % p(48, 4.5), pt("destruction", "~ ~1 ~"),
              pt("shockwave_big", "~ ~0.1 ~"), "/particle minecraft:huge_explosion_emitter ~ ~1 ~",
              at_players(48, "noise_big", "~ ~1 ~"), sound("random.explode", 0.5, 64), sound("mob.wither.death", 1.5, 64),
              flash(255, 255, 255, 48, (0, 0.1, 0.5)), shake(2.5, 1.0, 48)])
skill(13, "DESTRUCTION 3,2,1", 4.0, tl)

# 14 ↓Note DiVE↓（FREEDOM DiVE 解放後）: 降ってくるノーツ 8 拍 → 急降下
tl = {0: [say("§b§l【↓Note DiVE↓】§7「――リズム、合わせてね」"), sound("note.bit", 2.0)]}
melody = [1.0, 1.19, 1.5, 1.19, 1.0, 1.5, 1.78, 2.0]
for k in range(8):
    t = 0.6 + k * 0.35
    fam = "note_%d" % (k % 2)
    cmds = [summon_marker(fam, at=p(32))]
    for _ in range(2):
        cmds.append(summon_marker(fam, rnd_off(3), at=p(32)))
    add(tl, t, cmds + [sound("note.bit", melody[k], 48), sound("note.hat", 1.0, 48, 0.6)])
    add(tl, t + 0.02, [at_fam(fam, "particle hitori:note_fall ~ ~ ~"), at_fam(fam, "particle hitori:warn_cyan ~ ~0.1 ~")])
    add(tl, t + 0.3, [at_fam(fam, "particle hitori:warn_cyan ~ ~0.1 ~")])
    add(tl, t + 0.6, [at_fam(fam, "damage @a[r=1.6,m=!creative] 10 magic entity %s" % BOSS),
                      at_fam(fam, "particle hitori:note_hit ~ ~0.2 ~"), despawn(fam)])
add(tl, 3.6, ["/tp @s ~ ~12 ~", pt("afterimage", "~ ~-11 ~"), sound("mob.enderdragon.flap", 1.4)])
add(tl, 3.8, ["/execute at %s run tp @s ~ ~12 ~" % NEAREST, at_players(40, "warn_red", "~ ~0.1 ~")])
add(tl, 4.2, [at_players(40, "warn_red", "~ ~0.1 ~")])
add(tl, 4.7, ["/damage %s 22 entity_attack entity @s" % p(5), pt("noise_big", "~ ~1 ~"), pt("shockwave_big", "~ ~0.1 ~"),
              sound("random.explode", 1.0), sound("note.bit", 0.5, 48), flash(80, 220, 255, 24), shake(1.5, 0.6, 24)])
skill(14, "Note DiVE", 5.0, tl)

# ===========================================================================
# ↓FREEDOM DiVE↓: HP50%で解放される「落下」の能力
# ===========================================================================
# 15 ↓Free Fall↓: 空へ放り上げ、落とす（落下ダメージ）。天井の下・水・落下耐性で防げる
tl = {0: [say("§b【↓Free Fall↓】§7「――落ちる準備、できてる？」"), "/effect %s levitation 2 6 true" % p(16),
          at_players(16, "arrow_up"), pt("shockwave", "~ ~0.1 ~"), sound("beacon.activate", 1.8)]}
for t in (0.4, 0.8, 1.2, 1.6):
    add(tl, t, [at_players(40, "arrow_up"), at_players(40, "noise_burst", "~ ~1 ~")])
for t in (1.0, 1.5):
    add(tl, t, ["/summon hitori:bit_bullet ^ ^1.3 ^0.6 hitori:aim_%s" % a for a in ("m5", "0", "4")]
        + [sound("note.bit", 1.6, 30)])
add(tl, 2.0, ["/title %s actionbar §b§l↓ ↓ ↓  FALL  ↓ ↓ ↓" % p(40), at_players(40, "arrow_down"),
              sound("note.bit", 0.5, 48), flash(0, 200, 255, 40, (0, 0.05, 0.15))])
add(tl, 2.4, [at_players(40, "arrow_down")])
add(tl, 3.0, [at_players(40, "shockwave", "~ ~0.1 ~"), at_players(40, "fall_pixels"), shake(0.6, 0.3, 40)])
skill(15, "Free Fall", 3.4, tl)

# 16 ↓Out of World↓: 床が抜け、奈落に落ちる（防具無視の奈落ダメージ）
tl = {0: [say("§5【↓Out of World↓】§7「足元、ちゃんとある？」"), sound("mob.endermen.portal", 0.5)]}
for fam, t0 in (("void_a", 0.1), ("void_b", 0.9)):
    add(tl, t0, [summon_marker(fam, at=p(32))] + [summon_marker(fam, rnd_off(4), at=p(32)) for _ in range(3)])
    for dt in (0.05, 0.3, 0.55):
        add(tl, t0 + dt, [at_fam(fam, "particle hitori:void_hole ~ ~0.05 ~"),
                          at_fam(fam, "particle hitori:warn_magenta ~ ~0.1 ~"), at_fam(fam, "particle hitori:arrow_down ~ ~ ~")])
    add(tl, t0 + 0.8, [at_fam(fam, "damage @a[r=2.2,m=!creative] 9 void"),
                       at_fam(fam, "effect @a[r=2.2,m=!creative] slowness 2 3 true"),
                       at_fam(fam, "particle hitori:fall_pixels ~ ~ ~"),
                       at_fam(fam, "playsound mob.endermen.portal @a[r=20] ~ ~ ~ 0.8 0.5"),
                       shake(0.4, 0.2, 32), despawn(fam)])
skill(16, "Out of World", 2.6, tl)

# 17 ↓Gravity Cube↓: 空から欠損キューブが落ちてきて、着地で爆発
tl = {0: [say("§d【↓Gravity Cube↓】§7「重力、オンにしとくね」"), sound("random.glass", 0.7)]}
for fam, t0 in (("cube_a", 0.2), ("cube_b", 1.2)):
    cmds = []
    for o in ["~ ~ ~"] + [rnd_off(3) for _ in range(2)]:
        dx, _, dz = o.split()
        cmds.append(summon_marker(fam, o, at=p(32)))
        cmds.append("/execute at %s run summon hitori:gravity_cube %s ~12 %s" % (p(32), dx, dz))
    add(tl, t0, cmds + [sound("beacon.deactivate", 1.6)])
    for dt in (0.05, 0.35, 0.65, 0.95):
        add(tl, t0 + dt, [at_fam(fam, "particle hitori:warn_magenta ~ ~0.1 ~"),
                          at_fam(fam, "particle hitori:arrow_down ~ ~ ~")])
    add(tl, t0 + 1.4, [despawn(fam)])
skill(17, "Gravity Cube", 2.8, tl)

# 18 ↓Triple DiVE↓: 空から3回連続で急降下
tl = {0: [say("§b§l【↓Triple DiVE↓】§7「三連ダイブ。……ついてこれる？」"), sound("note.bit", 2.0)]}
for k in range(3):
    t0 = 0.2 + 1.3 * k
    add(tl, t0, ["/tp @s ~ ~10 ~", pt("afterimage", "~ ~-9 ~"), sound("mob.enderdragon.flap", 1.4 + 0.1 * k)])
    add(tl, t0 + 0.2, ["/execute at %s run tp @s ~ ~10 ~" % NEAREST, at_players(40, "warn_red", "~ ~0.1 ~"),
                       at_players(40, "arrow_down")])
    add(tl, t0 + 0.55, [at_players(40, "warn_red", "~ ~0.1 ~")])
    add(tl, t0 + 1.05, ["/damage %s 16 entity_attack entity @s" % p(4.5), pt("shockwave_big", "~ ~0.1 ~"),
                        pt("noise_big", "~ ~1 ~"), pt("fall_pixels"), sound("random.explode", 1.2 + 0.1 * k),
                        sound("note.bit", 0.5 + 0.3 * k, 48), flash(80, 220, 255, 24, (0, 0.05, 0.15)),
                        shake(1.0, 0.4, 24)])
skill(18, "Triple DiVE", 4.4, tl)


# ===========================================================================
# v1.2 追加技
# ===========================================================================
CINE = Cine("hitori_cine")
FACE = "^ ^1.6 ^"
ANYONE = "@p[r=64]"
BYAKUYA = "@e[family=byakuya,family=boss,c=1]"   # 影分身は除く。白夜のアドオンが無くてもエラーにならない

# 21 BSOD: 画面が青く落ち、その間に背後から 3 回刺される
tl = {0: [say("§9【BSOD】§7「あ、落ちた」"), "/camera %s fade time 0.15 1.8 0.4 color 16 56 190" % p(24),
          "/title %s title §f:(" % p(24), "/title %s subtitle §fGLITCH が発生しました。再起動しています……" % p(24),
          sound("random.glass", 0.4, 30), sound("note.bass", 0.5, 30)]}
for i, t in enumerate((0.3, 0.7, 1.1, 1.5, 1.9)):
    add(tl, t, ["/title %s actionbar §f%d%% 完了" % (p(24), i * 25)])
for i, t in enumerate((0.5, 0.95, 1.4)):
    add(tl, t, [pt("afterimage", "~ ~0.9 ~"), behind(1.4)])
    add(tl, t + 0.1, ["/damage %s 11 entity_attack entity @s" % p(3.2), at_players(3.2, "noise_burst", "~ ~1 ~"),
                      sound("random.glass", 0.9 + i * 0.2, 20), shake(0.4, 0.2, 8)])
add(tl, 2.2, [flash(255, 255, 255, 24, (0, 0.05, 0.2)), pt("noise_big", "~ ~1 ~"), sound("beacon.activate", 1.6, 30)])
skill(21, "BSOD", 2.6, tl)

# 22 ♪Rhythm Line♪（FREEDOM DiVE 解放後）: 拍ごとに広がるリング。拍に合わせてジャンプで避ける
tl = {0: [say("§b【♪Rhythm Line♪】§7「拍に合わせて、跳んでね」"),
          "/title %s actionbar §b§l♪ リングが来たら ジャンプ！ ♪" % p(40), "/effect @s slowness 7 255 true"]}
melody = [1.0, 1.19, 1.5, 1.78, 2.0, 1.78, 1.5, 1.19]
for k in range(8):
    t0 = 0.6 + 0.5 * k
    add(tl, t0, [pt("rhythm_ring"), pt("note_hit", "~ ~0.3 ~"), sound("note.bit", melody[k], 48),
                 sound("note.hat", 1.0, 48, 0.7), shake(0.15, 0.15, 24)])
    for j in range(18):
        rad = 1.5 + 0.9 * j
        add(tl, t0 + 0.1 * j, [
            "/execute as @a[rm=%.1f,r=%.1f,m=!creative] at @s unless block ~ ~-0.3 ~ air run damage @s 8 magic entity %s"
            % (max(0, rad - 0.7), rad + 0.7, BOSS)])
add(tl, 6.0, ["/title %s actionbar §b§lFULL COMBO……？" % p(40), flash(80, 220, 255, 32, (0, 0.05, 0.2))])
skill(22, "Rhythm Line", 6.2, tl)

# 23 Infinite Loop（FREEDOM DiVE 解放後）: 4 体の残像が周りを回り、中心へ収束して爆発
tl = {0: [say("§3【Infinite Loop】§7「ずっと、ずっと、繰り返し」"), summon_marker("loop_center", at=NEAREST),
          sound("beacon.activate", 1.4)] + ["/summon hitori:echo ~ ~ ~ hitori:echo_%d" % k for k in range(4)]}
for t in (0.1, 0.7, 1.3, 1.8):
    add(tl, t, [at_fam("loop_center", "particle hitori:zone_loop ~ ~0.1 ~"),
                at_fam("loop_center", "particle hitori:warn_cyan ~ ~0.1 ~")])
add(tl, 2.15, [at_fam("loop_center", "damage @a[r=3,m=!creative] 14 magic entity %s" % BOSS),
               at_fam("loop_center", "summon hitori:blast ~ ~0.5 ~"),
               at_fam("loop_center", "particle hitori:noise_big ~ ~1 ~"),
               at_fam("loop_center", "particle hitori:shockwave ~ ~0.1 ~"), shake(0.8, 0.4, 24)])
add(tl, 2.5, [despawn("loop_center")])
skill(23, "Infinite Loop", 3.2, tl)

# ===========================================================================
# カットシーン
# ===========================================================================
# 30 登場: ノイズ混じりの細かいカット割り → 名乗り
tl = {}
add(tl, 0, CINE.begin(4.2) + ["/tp @s ~ ~ ~ facing %s" % ANYONE, CINE.cam("^3 ^1 ^3", FACE), CINE.fade(0, 0.1, 0.3),
                              pt("noise_big", "~ ~1 ~"), sound("random.glass", 0.5, 64),
                              "/scoreboard objectives add %s dummy" % OBJ, "/scoreboard players set @s %s 0" % OBJ,
                              "/scoreboard objectives add %s dummy" % OBJ_PLAYERS])
add(tl, 0.3, [CINE.cam("^-2 ^3 ^2", FACE), pt("noise_burst", "~ ~1 ~"), sound("note.bit", 1.5, 64)])
add(tl, 0.6, [CINE.cam("^ ^0.4 ^4", FACE), pt("noise_burst", "~ ~1 ~"), sound("note.bit", 0.7, 64)])
add(tl, 0.9, [CINE.cam("^ ^2 ^9", FACE), CINE.fade(0, 0.05, 0.1, (40, 220, 255))])
add(tl, 1.0, [CINE.cam("^0.5 ^1.65 ^2.2", FACE, 1.8, "in_out_cubic")])
add(tl, 2.9, ["/title @a[r=64] title §b電子 独", "/title @a[r=64] subtitle §7不具合・Glitch ―― 自我の使者",
              pt("noise_big", "~ ~1 ~"), sound("beacon.activate", 0.5, 64), CINE.fade(0, 0.05, 0.25, (40, 220, 255))])
add(tl, 3.2, [say("§b独§7「……あ、見つかっちゃった。じゃあ、遊ぼっか」")])
add(tl, 3.9, CINE.end() + ["/" + 'tellraw @a[r=64] {"rawtext":[{"text":"§8[TIP] §7Glitch 展開中は攻撃が効かない。§b短い間隔で連続ヒット§7させて負荷をかけろ！"}]}'])
skill(30, "登場", 4.0, tl)

# 31 ↓FREEDOM DiVE↓ 解放（HP50%）: 見上げるカット → 真上からの落下視点 → 急降下
tl = {}
add(tl, 0, CINE.begin(5) + ["/tp @s ~ ~ ~ facing %s" % ANYONE, CINE.cam("^ ^0.2 ^4.5", "^ ^2.5 ^"),
                            CINE.fade(0, 0.1, 0.4, (40, 220, 255)), "/title @a[r=64] title §b§l↓FREEDOM DiVE↓",
                            "/title @a[r=64] subtitle §7――『落下』の概念、解放", pt("arrow_rain"),
                            sound("mob.wither.spawn", 1.4, 64), pt("charge", "~ ~3 ~")])
add(tl, 1.0, [CINE.cam("^ ^1 ^7", "^ ^5 ^", 1.0, "in_out_sine"), pt("noise_burst", "~ ~5 ~")])
add(tl, 2.0, [CINE.cam("^0.3 ^12 ^0.3", "^ ^ ^"), sound("note.bit", 2.0, 64), pt("fall_pixels", "~ ~6 ~")])
add(tl, 2.4, [CINE.cam("^ ^3 ^0.6", "^ ^ ^", 0.45, "in_expo"), sound("mob.enderdragon.flap", 1.4, 64)])
add(tl, 2.9, ["/summon hitori:blast ~ ~0.5 ~", pt("shockwave_big", "~ ~0.1 ~"), pt("noise_big", "~ ~1 ~"),
              pt("fall_pixels"), pt("arrow_rain"), sound("random.explode", 1.0, 64), sound("note.bit", 0.5, 64),
              CINE.fade(0, 0.05, 0.3, (255, 255, 255)), shake(1.5, 0.6, 48)])
add(tl, 3.4, [CINE.cam("^0.5 ^1.62 ^1.4", FACE), say("§b独§7「――ここからは、落ちるだけだよ」")])
add(tl, 4.6, CINE.end() + ["/" + 'tellraw @a[r=64] {"rawtext":[{"text":"§8[TIP] §7独が『落下』の能力を解放した。落下技が解禁、Glitch 負荷上限アップ"}]}'])
skill(31, "FREEDOM DiVE 解放", 5.0, tl)

# 32 宿敵（白石白夜側のカットシーンに合わせて、こちらは相手の方を向いて止まる）
tl = {0.05: ["/tp @s ~ ~ ~ facing %s" % BYAKUYA], 2.5: ["/tp @s ~ ~ ~ facing %s" % BYAKUYA],
      6.3: ["/tp @s ~ ~ ~ facing %s" % BYAKUYA], 8.0: [pt("noise_big", "~ ~1 ~")]}
skill(32, "宿敵", 9.0, tl)

# 20 Re: End of a Dream（HP25%で一度だけ）: 顔のアップ → 真上からの俯瞰 → 回転するノイズビーム
tl = {}
add(tl, 0, CINE.begin(2.4) + ["/tp @s ~ ~ ~ facing %s" % ANYONE, CINE.cam("^0.4 ^1.65 ^1.3", "^ ^1.6 ^"),
                              CINE.fade(0, 0.2, 0.8, (255, 255, 255)),
                              "/title @a[r=64] title §b§lRe: End of a Dream", "/title @a[r=64] subtitle §7――夢の終わりを、もう一度",
                              "/effect %s darkness 11 0 true" % p(64), sound("beacon.power", 0.5, 64), pt("charge", "~ ~1 ~")])
add(tl, 0.9, [CINE.cam("^ ^20 ^0.01", "^ ^ ^"), pt("charge", "~ ~1 ~"), sound("beacon.activate", 0.5, 64)])
add(tl, 1.5, [CINE.cam("^ ^14 ^0.01", "^ ^ ^", 0.8, "in_out_sine")])
add(tl, 2.4, [CINE.fade(0, 0.05, 0.2, (255, 255, 255))] + CINE.end()
    + ["/title @a[r=64] actionbar §b§l回転するビームから逃げ続けろ！"])
DREAM_T0 = 2.6
add(tl, DREAM_T0, [pt("dream_arms"), sound("beacon.activate", 0.5, 64)])
add(tl, 3.5, [say("§b独§7「……ねぇ。これが夢なら」")])
add(tl, 6.0, [say("§b独§7「覚めないでほしかったな」")])
t = DREAM_T0
while t <= DREAM_T0 + 6.0 + 1e-6:
    phi = 60 * (t - DREAM_T0)
    cmds = []
    for k in range(3):
        ang = phi + 120 * k
        for d in (2, 4.5, 7, 9.5, 12, 14.5, 17, 19.5):
            cmds.append("/execute at @s rotated %.1f 0 positioned ^ ^1 ^%.1f run damage @a[r=1.6,m=!creative] 13 magic "
                        "entity @s" % (ang, d))
    if abs((t * 2) - round(t * 2)) < 1e-6:
        cmds.append(sound("note.bit", 0.5 + (t - DREAM_T0) * 0.2, 64, 0.7))
    add(tl, t, cmds)
    t = round(t + 0.25, 2)
add(tl, 8.9, [say("§b独§7「――おはよう」"), pt("destruction", "~ ~1 ~"), pt("shockwave_big", "~ ~0.1 ~"),
              "/damage %s 22 magic entity @s" % p(8), "/summon hitori:blast ~ ~0.5 ~ hitori:big",
              flash(255, 255, 255, 64, (0.1, 0.3, 0.8)), shake(2.0, 0.8, 48), sound("random.explode", 0.6, 64)])
skill(FINAL_V, "Re: End of a Dream", 9.6, tl)

# 99 強制解除（スタン）
tl = {0: ["/title @a[r=48] title §c§lFATAL ERROR", "/title @a[r=48] subtitle §7Glitch 強制解除 ―― 今なら攻撃が通る！",
          pt("noise_big", "~ ~1 ~"), pt("error_popup", "~ ~1 ~"), sound("random.glass", 0.5, 48),
          sound("beacon.deactivate", 0.6, 48), flash(255, 255, 255, 32, (0, 0.05, 0.2))]}
for i in range(1, int(STUN) + 1):
    add(tl, float(i), [pt("error_popup", "~ ~1 ~"), sound("note.bit", 0.5, 30, 0.6)])
add(tl, STUN - 1.0, ["/title @a[r=48] actionbar §eGlitch 再起動まで 1秒……"])
skill(STUN_V, "強制解除", STUN, tl)

CINE_V = [FINAL_V, 30, 31, 32]

# 撃破カットシーン（監督役の見えないエンティティが再生する）
DEATH = {}
add(DEATH, 0, CINE.begin(6) + [CINE.cam("~3 ~1.4 ~-3", "~ ~1 ~"), CINE.fade(0, 0.2, 0.8, (40, 220, 255)),
                              pt("noise_big", "~ ~1 ~"), pt("error_popup", "~ ~1 ~"),
                              "/playsound beacon.deactivate @a[r=64] ~ ~ ~ 1 0.5"])
add(DEATH, 0.1, [CINE.cam("~3 ~1.6 ~3", "~ ~1 ~", 1.7, "linear")])
add(DEATH, 0.8, [say("§b独§7「……あーあ。バグ、直されちゃった」")])
add(DEATH, 1.8, [CINE.cam("~-3 ~2 ~3", "~ ~1 ~", 1.7, "linear"), pt("error_popup", "~ ~1 ~")])
add(DEATH, 3.0, [say("§b独§7「……でも、楽しかったよ。また、遊んでね」"), pt("noise_burst", "~ ~1 ~")])
add(DEATH, 3.6, [CINE.cam("~ ~8 ~0.5", "~ ~0.5 ~", 1.2, "in_out_sine")])
add(DEATH, 4.6, [pt("noise_big", "~ ~1 ~"), pt("fall_pixels"), "/playsound random.glass @a[r=64] ~ ~ ~ 1 0.5"])
add(DEATH, 5.3, [CINE.fade(0, 0.1, 0.6, (40, 220, 255))] + CINE.end())
add(DEATH, 5.35, ["/title @a[r=64] title §6§l討伐成功", "/title @a[r=64] subtitle §7電子 独のバグを直した",
                   "/playsound random.levelup @a[r=64] ~ ~ ~ 1 0.8", "/playsound random.totem @a[r=64] ~ ~ ~ 0.5 1.6"])
add(DEATH, 5.5, ["@s hitori:despawn"])
DEATH = {"%.2f" % k: v for k, v in sorted(DEATH.items())}


# ---------------------------------------------------------------------------
# v1.3: 大技のカットイン・着地や叩きつけの土煙
# ---------------------------------------------------------------------------
SMOOTH_STEP = 0.02   # 50 キー/秒（容量より、なめらかさ優先）
for _v in SKILLS:     # 長距離の斬り抜け（一瞬の tp）は、数 tick に分けた高速移動に
    split_dashes(SKILLS[_v][2])


def patch(v, t, cmds):
    tl = SKILLS[v][2]
    key = "%.2f" % t
    tl[key] = tl.get(key, []) + list(cmds)


def cutin_into(v, t, dur, pos, facing, title=None, sub=None):
    tmp = {}
    CINE.cutin(tmp, t, dur, pos, facing, title, sub)
    for k, cmds in tmp.items():
        patch(v, k, cmds)


def impact(pos="~ ~ ~"):
    return [pt("debris", pos), pt("dust_ring", pos)]


# ---------------------------------------------------------------------------
# 立ち回り（ボス同士でも、プレイヤー相手でも）: その場で殴り合うだけにならないように
# ---------------------------------------------------------------------------
# 60 Rollback Step: カクついたコマ送りで後ろへ下がり、データ弾で返す
tl = {0: [pt("noise_burst", "~ ~1 ~"), sound("note.bit", 0.6, 30)]}
for t, d in ((0.05, 2.4), (0.15, 1.4), (0.22, 1.0)):
    add(tl, t, ["/tp @s ^ ^ ^-%g facing %s true" % (d, NEAREST), pt("noise_burst", "~ ~1 ~"),
                pt("afterimage", "~ ~0.9 ~")])
add(tl, 0.22, [pt("step_dust")])
add(tl, 0.5, ["/summon hitori:bit_bullet ^ ^1.3 ^0.6 hitori:aim_%s" % a for a in ("m5", "4")]
    + [sound("note.bit", 1.2, 30), pt("noise_burst", "^ ^1.3 ^0.8")])
add(tl, 0.62, ["/summon hitori:bit_bullet ^ ^1.3 ^0.6 hitori:aim_0", sound("note.bit", 1.4, 30)])
skill(60, "Rollback Step", 1.1, tl)
# 61 / 62 Lag Step: ラグったように不規則なコマで横へ回り込み、ノイズの拳
for v, side in ((61, 1), (62, -1)):
    tl = {0: [pt("noise_burst", "~ ~1 ~"), sound("note.bit", 0.8, 24)]}
    for t in (0.08, 0.12, 0.24, 0.3, 0.4):
        add(tl, t, ["/tp @s ^%g ^ ^0.45 facing %s true" % (-1.5 * side, NEAREST), pt("noise_burst", "~ ~1 ~")])
    add(tl, 0.56, [pt("noise_big", "^ ^1 ^1.6"), sound("random.glass", 0.6, 30), sound("note.bass", 0.5, 30),
                   "/execute positioned ^ ^1 ^1.6 run damage @a[r=2.3,m=!creative] 13 magic entity @s",
                   shake(0.4, 0.25, 10)] + impact("^ ^ ^1.6"))
    skill(v, "Lag Step", 1.3, tl)


cutin_into(13, 0.0, 0.7, "^0.4 ^1.65 ^1.2", "^ ^1.6 ^")
cutin_into(18, 0.42, 0.5, "^ ^-9.5 ^3", "^ ^ ^")
for v, times in ((18, [1.25, 2.55, 3.85]), (14, [4.7]), (31, [2.9]), (13, [3.5])):
    for t in times:
        patch(v, t, impact())
patch(4, 1.6, [at_players(18, "dust_ring"), at_players(18, "debris")])


# ---------------------------------------------------------------------------
# Behavior Pack: 本体
# ---------------------------------------------------------------------------
def manifest(kind):
    if kind == "bp":
        return {"format_version": 2,
                "header": {"name": "電子 独 ボス BP", "description": "ボス「電子 独（不具合・Glitch）」を追加します",
                           "uuid": UUID_BP_HEADER, "version": VERSION, "min_engine_version": MIN_ENGINE},
                "modules": [{"type": "data", "uuid": UUID_BP_MODULE, "version": VERSION}],
                "dependencies": [{"uuid": UUID_RP_HEADER, "version": VERSION}]}
    return {"format_version": 2,
            "header": {"name": "電子 独 ボス RP", "description": "ボス「電子 独（不具合・Glitch）」を追加します",
                       "uuid": UUID_RP_HEADER, "version": VERSION, "min_engine_version": MIN_ENGINE},
            "modules": [{"type": "resources", "uuid": UUID_RP_MODULE, "version": VERSION}]}


def phase_group(skin, speed, dmg, timer):
    return {"minecraft:skin_id": {"value": skin}, "minecraft:movement": {"value": speed},
            "minecraft:attack": {"damage": dmg, "effect_name": "nausea", "effect_duration": 3},
            "minecraft:timer": {"looping": True, "time": timer, "randomInterval": True,
                                "time_down_event": {"event": "hitori:choose_skill", "target": "self"}}}


SENSORS = ["glitch_on", "glitch_cd", "glitch_reboot", "stunned_sensor", "final_guard"]
FOE = FOE_ANY   # プレイヤーと、ほかのボス


def meter(n, limit):
    bar = "§c" + "■" * n + "§8" + "□" * (limit - n)
    return "execute if score @s %s matches %d run title @a[r=32] actionbar §b◆GLITCH 負荷 %s §7(%d/%d)" % (
        OBJ, n, bar, n, limit)


def bp_entity():
    immune = [{"cause": c, "deal_damage": False} for c in ("fall", "suffocation", "fire", "fire_tick", "lava",
                                                           "drowning", "magic", "entity_explosion", "lightning")]
    all_off = {"minecraft:damage_sensor": {"triggers": [{"cause": "all", "deal_damage": False}]}}
    groups = {
        "phase_1": phase_group(0, 0.33, 16, [2.3, 3.6]),
        "phase_2": phase_group(1, 0.37, 20, [1.8, 2.8]),
        "phase_3": phase_group(2, 0.41, 25, [1.4, 2.3]),
        # Glitch 展開中: すべて無効。プレイヤー（と白夜）の攻撃は「負荷」として数える
        "glitch_on": {"minecraft:damage_sensor": {"triggers": [
            {"on_damage": {"filters": FOE, "event": "hitori:glitch_hit"}, "deal_damage": False},
            {"cause": "projectile", "on_damage": {"event": "hitori:glitch_hit"}, "deal_damage": False},
            {"cause": "all", "deal_damage": False}]}},
        # 連打対策のクールダウン中（is_sheared は BP コントローラーで時間を測る目印）
        "glitch_cd": dict(all_off, **{"minecraft:is_sheared": {}}),
        # 強制解除から復帰した直後の再構築中（is_charged が目印）: 負荷を受け付けない
        "glitch_reboot": dict(all_off, **{"minecraft:is_charged": {}}),
        # 強制解除中: ダメージが通る（近接 70%・飛び道具 50%）
        "stunned_sensor": {"minecraft:damage_sensor": {"triggers": immune[:4] + [
            {"cause": "entity_explosion", "deal_damage": False},
            {"cause": "entity_attack", "damage_multiplier": 0.7},
            {"cause": "projectile", "damage_multiplier": 0.5}]}},
        "final_guard": dict(all_off),
        "ai": {
            "minecraft:behavior.float": {"priority": 0},
            "minecraft:behavior.melee_attack": {"priority": 2, "speed_multiplier": 1.3, "track_target": True},
            "minecraft:behavior.hurt_by_target": {"priority": 1},
            "minecraft:behavior.nearest_attackable_target": {
                "priority": 2, "must_see": False, "reselect_targets": True, "within_radius": 48,
                "entity_types": [{"filters": {"test": "is_family", "subject": "other", "value": "player"},
                                  "max_dist": 48},
                                 rival_target("hitori")]},   # ほかのボス（白夜・ソフィア・東雲）
            "minecraft:behavior.random_stroll": {"priority": 6, "speed_multiplier": 0.8},
            "minecraft:behavior.look_at_player": {"priority": 7, "look_distance": 16},
        },
    }
    split_melee(groups, "hitori")   # 近接の構え / 遠距離の構え
    variants = [0] + sorted(SKILLS)
    for v in variants:
        groups["v_%d" % v] = {"minecraft:mark_variant": {"value": v}}
    all_v = ["v_%d" % v for v in variants]

    def set_variant(v, add_=None, remove_=None):
        return {"remove": {"component_groups": [g for g in all_v if g != "v_%d" % v] + (remove_ or [])},
                "add": {"component_groups": ["v_%d" % v] + (add_ or [])}}

    def sensor(name):
        return [s for s in SENSORS if s != name], [name]

    def cine(v, add_=(), remove_=()):
        rm_, ad_ = sensor("final_guard")
        return set_variant(v, ad_ + list(add_), rm_ + ["ai"] + list(remove_))

    busy_v = [STUN_V] + CINE_V
    not_busy = {"all_of": [{"test": "is_mark_variant", "operator": "!=", "value": b} for b in busy_v]}

    rm, ad = sensor("glitch_cd")
    hit_seq = [{"remove": {"component_groups": rm}, "add": {"component_groups": ad},
                "queue_command": {"command": [
                    "scoreboard players add @s %s 1" % OBJ,
                    "particle hitori:noise_burst ~ ~1 ~",
                    "particle hitori:error_one ~ ~2.3 ~",
                    "playsound random.glass @a[r=24] ~ ~ ~ 0.6 1.8",
                    "playsound note.bit @a[r=24] ~ ~ ~ 1 0.6"]}}]
    for skin, limit in GLITCH_LIMIT.items():
        hit_seq.append({"filters": {"test": "is_skin_id", "value": skin}, "queue_command": {"command":
                        [meter(n, limit) for n in range(1, limit)] +
                        ["execute if score @s %s matches %d.. run event entity @s hitori:glitch_break" % (OBJ, limit),
                         # 負荷が上限近くになると、確率で「過負荷放出」して周りを吹き飛ばす
                         "execute if score @s %s matches %d..%d run event entity @s hitori:purge_roll"
                         % (OBJ, limit - 3, limit - 1)]}})

    rm_s, ad_s = sensor("stunned_sensor")
    rm_r, ad_r = sensor("glitch_reboot")
    rm_g, ad_g = sensor("glitch_on")
    stun_n = int(math.ceil(STUN))
    events = {
        "minecraft:entity_spawned": {"add": {"component_groups": ["phase_1", "v_30", "final_guard"]}},
        "hitori:glitch_hit": {"sequence": hit_seq},
        "hitori:cd_end": {"sequence": [{"filters": not_busy, "remove": {"component_groups": ["glitch_cd"]},
                                        "add": {"component_groups": ["glitch_on"]}}]},
        "hitori:purge_roll": {"randomize": [{"weight": 35, "trigger": "hitori:purge"}, {"weight": 65, "queue_command": {
            "command": ["particle hitori:noise_burst ~ ~1.5 ~"]}}]},
        "hitori:purge": {"queue_command": {"command": [
            "scoreboard players remove @s %s 4" % OBJ,
            "summon hitori:blast ~ ~0.8 ~",
            "particle hitori:noise_big ~ ~1 ~", "particle hitori:shockwave ~ ~0.1 ~",
            "playsound beacon.deactivate @a[r=24] ~ ~ ~ 1 1.8",
            "title @a[r=32] actionbar §c§l◆ OVERLOAD PURGE ◆ §7負荷 -4",
            "camerashake add @a[r=12] 0.6 0.3 positional"]}},
        # 強制解除: 周りのプレイヤー人数に応じて、スタン中の被ダメージを軽減（集団戦対策）
        "hitori:glitch_break": dict(set_variant(STUN_V, ad_s, rm_s + ["ai"]), queue_command={"command": [
            "scoreboard players set @s %s 0" % OBJ,
            "scoreboard players set @s %s 0" % OBJ_PLAYERS,
            "execute as @a[r=40,m=!creative] run scoreboard players add %s %s 1" % (BOSS, OBJ_PLAYERS),
            "execute if score @s %s matches 2 run effect @s resistance %d 0 true" % (OBJ_PLAYERS, stun_n),
            "execute if score @s %s matches 3 run effect @s resistance %d 1 true" % (OBJ_PLAYERS, stun_n),
            "execute if score @s %s matches 4.. run effect @s resistance %d 2 true" % (OBJ_PLAYERS, stun_n),
            "execute if score @s %s matches 2.. run title @a[r=48] actionbar §7人数補正：強制解除中の被ダメージ軽減" % OBJ_PLAYERS]}),
        # 復帰: しばらくは再構築中で負荷を受け付けない
        "hitori:glitch_restore": dict(set_variant(0, ad_r + ["ai"], rm_r), queue_command={"command": [
            "scoreboard players set @s %s 0" % OBJ,
            "title @a[r=48] actionbar §c§lGlitch 再構築中…… §7(%d秒間 負荷無効)" % int(REBOOT),
            "particle hitori:noise_big ~ ~1 ~", "particle hitori:shockwave ~ ~0.1 ~",
            "summon hitori:blast ~ ~0.8 ~",
            "playsound beacon.activate @a[r=32] ~ ~ ~ 1 1.5"]}),
        "hitori:reboot_end": {"sequence": [{"filters": not_busy, "remove": {"component_groups": ["glitch_reboot"]},
                                            "add": {"component_groups": ["glitch_on"]},
                                            "queue_command": {"command": [
                                                "title @a[r=48] actionbar §b§lGlitch 再起動完了"]}}]},
        "hitori:skill_end": {"sequence": [{"filters": not_busy, **set_variant(0)}]},
        "hitori:cine_end": dict(set_variant(0, ad_g + ["ai"], rm_g), queue_command={"command": [
            "scoreboard players set @s %s 0" % OBJ]}),
        "hitori:phase2": cine(31, ["phase_2"], ["phase_1"]),
        "hitori:final": cine(FINAL_V, ["phase_3"], ["phase_1", "phase_2"]),
        "hitori:rival_cut": {"sequence": [{"filters": {"test": "is_mark_variant", "value": 0}, **cine(32)}]},
    }
    for v in sorted(SKILLS):
        if v not in busy_v:
            events["hitori:skill_%d" % v] = set_variant(v)

    near1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 21, 60, 60, 61, 62]   # 60〜62: 立ち回り
    far1 = [1, 2, 3, 3, 7, 8, 10, 10, 11, 11, 21, 60]   # 60: 間合いを取って遠距離で返す
    near2 = near1 + [12, 13, 14, 15, 16, 17, 18, 5, 6, 22, 23]
    far2 = far1 + [12, 13, 14, 15, 16, 16, 17, 17, 18, 18, 22, 23]
    near_f, far_f = stance_filters("hitori_near")   # 近接の構えで敵が近い → 近距離の技 / それ以外 → 遠距離の技
    base = [{"test": "is_mark_variant", "value": 0}, {"test": "has_target", "value": True}]
    seq = []
    for skin, near, far in ((0, near1, far1), (1, near2, far2),
                            (2, near2 + [13, 15, 18, 22], far2 + [13, 14, 18, 23])):
        for cond, lst in ((near_f, near), (far_f, far)):
            seq.append({"filters": {"all_of": base + [{"test": "is_skin_id", "value": skin}, cond]},
                        "randomize": [{"weight": 10, "trigger": "hitori:skill_%d" % s} for s in lst]})
    events["hitori:choose_skill"] = {"sequence": seq}

    # ほかのボスの演出（登場など）のあいだは一時停止して、お互いに手出ししない
    events.update(pause_events(not_busy))
    # 間合いの判断: 4 秒ごとに「近接の構え / 遠距離の構え」を選び直す（HP が減ると遠距離寄り）
    events.update(stance_events(not_busy, 50, 50, int(HP * 0.4)))
    apply_stance_groups(events)

    components = {
        "minecraft:type_family": {"family": ["hitori", "boss", RIVAL_FAMILY, "monster", "mob"]},
        "minecraft:health": {"value": HP, "max": HP},
        "minecraft:boss": {"hud_range": 64, "should_darken_sky": True},
        "minecraft:nameable": {"always_show": True, "allow_name_tag_renaming": False},
        "minecraft:persistent": {},
        "minecraft:collision_box": {"width": 0.6, "height": 1.8},
        "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": True},
        "minecraft:knockback_resistance": {"value": 1.0},
        "minecraft:fire_immune": {},
        "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0, "breathes_water": True},
        "minecraft:jump.static": {},
        "minecraft:movement.basic": {},
        "minecraft:movement": {"value": 0.33},
        "minecraft:navigation.walk": {"can_path_over_water": True, "avoid_damage_blocks": True},
        "minecraft:follow_range": {"value": 48, "max": 64},
        "minecraft:attack": {"damage": 16},
        "minecraft:loot": {"table": "loot_tables/entities/denshi_hitori.json"},
        "minecraft:experience_reward": {"on_death": "1200"},
        "minecraft:environment_sensor": {"triggers": [
            {"filters": {"all_of": [{"test": "actor_health", "operator": "<=", "value": PHASE2_HP},
                                    {"test": "is_skin_id", "value": 0}] + not_busy["all_of"]},
             "event": "hitori:phase2"},
            {"filters": {"all_of": [{"test": "actor_health", "operator": "<=", "value": FINAL_HP},
                                    {"test": "is_skin_id", "value": 1}] + not_busy["all_of"]},
             "event": "hitori:final"},
        ]},
    }
    return {"format_version": "1.21.0", "minecraft:entity": {
        "description": {"identifier": ID, "is_spawnable": True, "is_summonable": True, "is_experimental": False,
                        "scripts": {"animate": ["skills", "cooldown", "reboot", "decay", "death", "bgm", "foe_tags", "stance"]},
                        "animations": {"foe_tags": "animation.hitori.foe_tags", "stance": "animation.hitori.stance_loop",
                                       "skills": "controller.animation.hitori.skills",
                                       "cooldown": "controller.animation.hitori.cooldown",
                                       "reboot": "controller.animation.hitori.reboot",
                                       "decay": "animation.hitori.decay",
                                       "death": "controller.animation.hitori.death",
                                       "bgm": "controller.animation.hitori.bgm",
                                       "cd_timer": "animation.hitori.cd_timer",
                                       "reboot_timer": "animation.hitori.reboot_timer",
                                       "idle_loop": "animation.hitori.idle_loop",
                                       **{"skill_%d" % v: "animation.hitori.skill_%d" % v for v in SKILLS}}},
        "component_groups": groups, "components": components, "events": events}}


# ほかのボスと初めて会ったときのひとこと（白夜とは専用のカットシーン）
ENCOUNTER = {'sophia': '§b独§7「……神様、か。バグを直しに来たの？\u3000……させないよ」', 'shinonome': '§b独§7「……ワープホール？\u3000そんなの、仕様にないよ。……面白いね、遊ぼっか」', 'fuuka': '§b独§7「……風花さん。……ごめんね。今日は、本気でいくよ」'}


def bp_animations():
    a = {"animation.hitori.skill_%d" % v: {"animation_length": length, "loop": False, "timeline": tl}
         for v, (name, length, tl) in SKILLS.items()}
    a["animation.hitori.cd_timer"] = {"animation_length": HIT_COOLDOWN, "loop": False}
    a["animation.hitori.reboot_timer"] = {"animation_length": REBOOT, "loop": False}
    a["animation.hitori.decay"] = {"animation_length": DECAY, "loop": True, "timeline": {"%.2f" % (DECAY - 0.05): [
        "/scoreboard players remove @s[scores={%s=1..}] %s 1" % (OBJ, OBJ)]}}
    # 待機中だけ動く: カメラの後片付けと、ほかのボスの発見
    a["animation.hitori.idle_loop"] = {"animation_length": 2.0, "loop": True, "timeline": {
        "1.00": CINE.end(), "1.50": encounter_cmds("hitori", say, ENCOUNTER)}}
    # 常に動く: 敵の目印と「近くに敵がいる」タグ
    a["animation.hitori.stance_loop"] = STANCE_ANIM   # 間合いの判断（4 秒ごと）
    a["animation.hitori.foe_tags"] = foe_tag_anim(ID, "hitori_near")
    return {"format_version": "1.10.0", "animations": a}


def bp_controllers():
    states = {"default": {"animations": ["idle_loop"],
                          "transitions": [{"skill_%d" % v: "q.mark_variant == %d" % v} for v in sorted(SKILLS)]}}
    for v in sorted(SKILLS):
        if v == STUN_V:
            exit_ev = "@s hitori:glitch_restore"
        elif v in CINE_V:
            exit_ev = "@s hitori:cine_end"
        else:
            exit_ev = "@s hitori:skill_end"
        states["skill_%d" % v] = {"animations": ["skill_%d" % v],
                                  "transitions": [{"default": "q.all_animations_finished || q.mark_variant != %d" % v}],
                                  "on_exit": [exit_ev]}
    return {"format_version": "1.10.0", "animation_controllers": {
        "controller.animation.hitori.skills": {"initial_state": "default", "states": states},
        "controller.animation.hitori.cooldown": {"initial_state": "ready", "states": {
            "ready": {"transitions": [{"cd": "q.is_sheared"}]},
            "cd": {"animations": ["cd_timer"], "transitions": [{"ready": "q.all_animations_finished || !q.is_sheared"}],
                   "on_exit": ["@s hitori:cd_end"]}}},
        "controller.animation.hitori.reboot": {"initial_state": "ready", "states": {
            "ready": {"transitions": [{"rb": "q.is_charged"}]},
            "rb": {"animations": ["reboot_timer"],
                   "transitions": [{"ready": "q.all_animations_finished || !q.is_charged"}],
                   "on_exit": ["@s hitori:reboot_end"]}}},
        "controller.animation.hitori.death": {"initial_state": "alive", "states": {
            "alive": {"transitions": [{"dead": "!q.is_alive"}]},
            "dead": {"on_entry": ["/summon hitori:director ~ ~ ~", "/scoreboard players reset @s %s" % OBJ]
                     + CINE.end()}}},
        # BGM: 独がいる間は「隔絶された記憶」、↓FREEDOM DiVE↓ 解放後は「FREEDOM DiVE」
        # （ワールドを読み込み直したときも、初期状態から入り直すので BGM が再開する）
        "controller.animation.hitori.bgm": {"initial_state": "start", "states": {
            "start": {"transitions": [{"dive": "q.skin_id >= 1"}, {"memory": "q.skin_id == 0"}]},
            "memory": {"on_entry": ["/music play %s 0.9 2 loop" % BGM_MEMORY],
                       "transitions": [{"end": "!q.is_alive"}, {"dive": "q.skin_id >= 1"}]},
            "dive": {"on_entry": ["/music play %s 1.0 1 loop" % BGM_DIVE], "transitions": [{"end": "!q.is_alive"}]},
            "end": {"on_entry": ["/music stop 4"]}}},
        # 重力キューブ: 着地した瞬間に爆発
        "controller.animation.hitori.gravity_cube": {"initial_state": "fall", "states": {
            "fall": {"animations": ["life"], "transitions": [{"boom": "q.is_on_ground"}]},
            "boom": {"on_entry": ["/damage @a[r=2.8,m=!creative] 14 entity_explosion",
                                  "/particle hitori:missing_burst ~ ~0.5 ~", "/particle hitori:noise_big ~ ~0.5 ~",
                                  "/particle hitori:shockwave ~ ~0.1 ~", "/particle hitori:fall_pixels ~ ~ ~",
                                  "/playsound random.explode @a[r=24] ~ ~ ~ 0.8 1.4",
                                  "/camerashake add @a[r=10] 0.5 0.3 positional", "@s hitori:despawn"]}}},
        # Infinite Loop の残像: 番号ごとに違う角度から回り始める
        "controller.animation.hitori.echo": {"initial_state": "pick", "states": {
            "pick": {"transitions": [{"o%d" % k: "q.variant == %d" % k} for k in range(4)]},
            **{"o%d" % k: {"animations": ["orbit_%d" % k]} for k in range(4)}}},
    }}


def bp_loot():
    return {"pools": [
        {"rolls": 1, "entries": [{"type": "item", "name": DISC_ID, "weight": 1, "functions": [
            {"function": "set_lore", "lore": ["§7eight - 隔絶された記憶", "§8電子 独の、隔絶された記憶"]}]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:amethyst_shard", "weight": 1, "functions": [
            {"function": "set_count", "count": 16}, {"function": "set_name", "name": "§dノイズの欠片"}]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:netherite_ingot", "weight": 1,
                                  "functions": [{"function": "set_count", "count": {"min": 2, "max": 4}}]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:enchanted_golden_apple", "weight": 1,
                                  "functions": [{"function": "set_count", "count": 2}]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:totem_of_undying", "weight": 1}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:echo_shard", "weight": 1,
                                  "functions": [{"function": "set_count", "count": {"min": 2, "max": 4}}]}]},
    ]}


# ---------------------------------------------------------------------------
# 補助エンティティ（データ弾・目印・フォークボム）
# ---------------------------------------------------------------------------
AIM_ANGLES = sorted({a for pair in spread for a in pair} | {-5, 0, 4})
MARKERS = ["rollback", "missing_a", "missing_b", "swap_a", "swap_b", "beam_a", "beam_b", "note_0", "note_1",
           "void_a", "void_b", "cube_a", "cube_b", "loop_center"]
TICK = 0.05
DESPAWN_G = {"despawn": {"minecraft:instant_despawn": {}}}
DESPAWN_E = {"hitori:despawn": {"add": {"component_groups": ["despawn"]}}}


def fx_base(family, hitbox=0.2, health=1, invulnerable=True):
    c = {"minecraft:type_family": {"family": family}, "minecraft:health": {"value": health, "max": health},
         "minecraft:collision_box": {"width": hitbox, "height": hitbox},
         "minecraft:physics": {"has_gravity": False, "has_collision": False},
         "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
         "minecraft:knockback_resistance": {"value": 1.0}, "minecraft:body_rotation_blocked": {},
         "minecraft:fire_immune": {},
         "minecraft:conditional_bandwidth_optimization": {"default_values": {
             "max_optimized_distance": 0, "max_dropped_ticks": 0, "use_motion_prediction_hints": True}}}
    if invulnerable:
        c["minecraft:damage_sensor"] = {"triggers": [{"cause": "all", "deal_damage": False}]}
    return c


def entity(ident, comps, groups, events, anims_, animate):
    return {"format_version": "1.21.0", "minecraft:entity": {
        "description": {"identifier": ident, "is_spawnable": False, "is_summonable": True, "is_experimental": False,
                        "animations": anims_, "scripts": {"animate": animate}},
        "component_groups": groups, "components": comps, "events": events}}


def ticks(length, fn, end=None):
    n = int(round(length / TICK))
    tl = {"%.2f" % (i * TICK): fn(i) for i in range(n)}
    if end:
        tl["%.2f" % ((n - 1) * TICK)] = tl["%.2f" % ((n - 1) * TICK)] + end
    return tl


def hit_cmds(r, dmg, cause, despawn_=True, extra=()):
    sel = "@a[r=%.1f,m=!creative]" % r
    out = ["/execute if entity %s run damage %s %d %s" % (sel, sel, dmg, cause)]
    for e in extra:
        out.append("/execute if entity %s run %s" % (sel, e))
    if despawn_:
        out.append("/execute if entity %s run event entity @s hitori:despawn" % sel)
    return out


def summons_bp():
    out, anims_bp = {}, {}
    # データ弾
    ev = dict(DESPAWN_E)
    for a in AIM_ANGLES:
        ev["hitori:aim_%s" % ("m%d" % -a if a < 0 else a)] = {"queue_command": {"command": [
            "tp @s ~ ~ ~ facing @p[m=!creative]", "tp @s ~ ~ ~ ~%d ~" % a]}}
    anims_bp["animation.hitori.bullet.fly"] = {"animation_length": 1.55, "loop": False, "timeline": ticks(
        1.5, lambda i: ["/tp @s ^ ^ ^0.8"] + hit_cmds(1.5, 8, "magic", extra=["particle hitori:noise_burst ~ ~ ~"]),
        end=["@s hitori:despawn"])}
    out["bit_bullet"] = entity("hitori:bit_bullet", fx_base(["hitori_fx", "inanimate"]), dict(DESPAWN_G), ev,
                               {"fly": "animation.hitori.bullet.fly"}, ["fly"])
    # 目印
    g, e = dict(DESPAWN_G), dict(DESPAWN_E)
    for k in MARKERS:
        g[k] = {"minecraft:type_family": {"family": ["hitori_marker", k, "inanimate"]}}
        e["hitori:as_" + k] = {"add": {"component_groups": [k]}}
    anims_bp["animation.hitori.marker.life"] = {"animation_length": 4.05, "loop": False,
                                                "timeline": {"4.00": ["@s hitori:despawn"]}}
    out["marker"] = entity("hitori:marker", fx_base(["hitori_marker", "inanimate"], 0.1), g, e,
                           {"life": "animation.hitori.marker.life"}, ["life"])
    # フォークボム（欠片）: 追いかけて自爆。殴れば壊せる
    boom = ["particle hitori:missing_burst ~ ~ ~", "particle hitori:noise_burst ~ ~ ~",
            "playsound random.explode @a[r=24] ~ ~ ~ 0.6 1.8"]
    anims_bp["animation.hitori.fragment.chase"] = {"animation_length": 8.05, "loop": False, "timeline": ticks(
        8.0, lambda i: ["/execute at @s facing entity @p[m=!creative] feet positioned ^ ^ ^0.3 "
                        "run tp @s ~ ~ ~ facing @p[m=!creative]"]
        + (["/execute if entity @a[r=1.4,m=!creative] run damage @a[r=3,m=!creative] 12 entity_explosion"]
           + ["/execute if entity @a[r=1.4,m=!creative] run " + b for b in boom]
           + ["/execute if entity @a[r=1.4,m=!creative] run event entity @s hitori:despawn"]
           if i % 2 == 0 else []),
        end=["/damage @a[r=3,m=!creative] 12 entity_explosion", "/" + boom[0], "/" + boom[2], "@s hitori:despawn"])}
    frag = fx_base(["hitori_fx", "monster"], 0.6, health=4, invulnerable=False)
    out["fragment"] = entity("hitori:fragment", frag, dict(DESPAWN_G), dict(DESPAWN_E),
                             {"chase": "animation.hitori.fragment.chase"}, ["chase"])
    # 重力キューブ: 重力で落ちてきて、着地で爆発（BP コントローラー側で処理）
    cube_c = fx_base(["hitori_fx", "inanimate"], 0.8)
    cube_c["minecraft:physics"] = {"has_gravity": True, "has_collision": True}
    anims_bp["animation.hitori.gravity_cube.life"] = {"animation_length": 4.05, "loop": False,
                                                       "timeline": {"4.00": ["@s hitori:despawn"]}}
    out["gravity_cube"] = entity("hitori:gravity_cube", cube_c, dict(DESPAWN_G), dict(DESPAWN_E),
                                 {"ctrl": "controller.animation.hitori.gravity_cube",
                                  "life": "animation.hitori.gravity_cube.life"}, ["ctrl"])
    # Infinite Loop の残像: 中心の目印のまわりを回り、最後に収束する
    echo_g, echo_e = dict(DESPAWN_G), dict(DESPAWN_E)
    echo_anims = {}
    for k in range(4):
        echo_g["e_%d" % k] = {"minecraft:variant": {"value": k}}
        echo_e["hitori:echo_%d" % k] = {"add": {"component_groups": ["e_%d" % k]}}
        ctr = "@e[family=loop_center,c=1]"

        def orbit(i, k=k, ctr=ctr):
            if i < 36:
                return ["/execute at %s rotated %.1f 0 positioned ^ ^ ^4.5 run tp @s ~ ~ ~ facing %s"
                        % (ctr, k * 90 + i * 16, ctr)]
            return ["/execute at @s facing entity %s feet positioned ^ ^ ^0.7 run tp @s ~ ~ ~" % ctr]
        anims_bp["animation.hitori.echo.orbit_%d" % k] = {"animation_length": 2.2, "loop": False, "timeline": ticks(
            2.15, orbit, end=["/particle hitori:noise_burst ~ ~1 ~", "@s hitori:despawn"])}
        echo_anims["orbit_%d" % k] = "animation.hitori.echo.orbit_%d" % k
    out["echo"] = entity("hitori:echo", fx_base(["hitori_fx", "inanimate"], 0.5), echo_g, echo_e,
                         dict(echo_anims, ctrl="controller.animation.hitori.echo"), ["ctrl"])
    # 見えない爆発（ブロックは壊さない）: 本物の爆風で吹き飛ばす
    blast = fx_base(["hitori_fx", "inanimate"], 0.1)
    ex = {"fuse_length": 0, "fuse_lit": True, "causes_fire": False, "breaks_blocks": False,
          "destroy_affected_by_griefing": False}
    out["blast"] = {"format_version": "1.21.0", "minecraft:entity": {
        "description": {"identifier": "hitori:blast", "is_spawnable": False, "is_summonable": True,
                        "is_experimental": False},
        "component_groups": {"small": {"minecraft:explode": dict(ex, power=2)},
                             "big": {"minecraft:explode": dict(ex, power=4)}},
        "components": blast,
        "events": {"minecraft:entity_spawned": {"add": {"component_groups": ["small"]}},
                   "hitori:big": {"add": {"component_groups": ["big"]}}}}}
    # 撃破カットシーンの監督（独の像として表示）
    anims_bp["animation.hitori.director.death"] = {"animation_length": 5.6, "loop": False, "timeline": DEATH}
    out["director"] = entity("hitori:director", fx_base(["hitori_fx", "inanimate"], 0.1), dict(DESPAWN_G),
                             dict(DESPAWN_E), {"cut": "animation.hitori.director.death"}, ["cut"])
    return out, anims_bp


# ---------------------------------------------------------------------------
# Resource Pack
# ---------------------------------------------------------------------------
def cube(origin, size, uv, inflate=0):
    c = {"origin": origin, "size": size, "uv": uv}
    if inflate:
        c["inflate"] = inflate
    return c


def geo_boss():
    # 細腕（Alex 型）モデル
    bones = [
        {"name": "root", "pivot": [0, 0, 0]},
        {"name": "body", "parent": "root", "pivot": [0, 24, 0], "cubes": [
            cube([-4, 12, -2], [8, 12, 4], [16, 16]), cube([-4, 12, -2], [8, 12, 4], [16, 32], 0.25)],
         "locators": {"body_center": [0, 18, 0]}},
        {"name": "head", "parent": "body", "pivot": [0, 24, 0], "cubes": [
            cube([-4, 24, -4], [8, 8, 8], [0, 0]), cube([-4, 24, -4], [8, 8, 8], [32, 0], 0.5)]},
        {"name": "rightArm", "parent": "body", "pivot": [-5, 21.5, 0], "cubes": [
            cube([-7, 11.5, -2], [3, 12, 4], [40, 16]), cube([-7, 11.5, -2], [3, 12, 4], [40, 32], 0.25)],
         "locators": {"right_hand": [-5.5, 11, 0]}},
        {"name": "leftArm", "parent": "body", "pivot": [5, 21.5, 0], "cubes": [
            cube([4, 11.5, -2], [3, 12, 4], [32, 48]), cube([4, 11.5, -2], [3, 12, 4], [48, 48], 0.25)],
         "locators": {"left_hand": [5.5, 11, 0]}},
        {"name": "rightLeg", "parent": "root", "pivot": [-1.9, 12, 0], "cubes": [
            cube([-3.9, 0, -2], [4, 12, 4], [0, 16]), cube([-3.9, 0, -2], [4, 12, 4], [0, 32], 0.25)],
         "locators": {"right_foot": [-1.9, 0, 0]}},
        {"name": "leftLeg", "parent": "root", "pivot": [1.9, 12, 0], "cubes": [
            cube([-0.1, 0, -2], [4, 12, 4], [16, 48]), cube([-0.1, 0, -2], [4, 12, 4], [0, 48], 0.25)],
         "locators": {"left_foot": [1.9, 0, 0]}},
    ]
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": "geometry.denshi_hitori", "texture_width": 64, "texture_height": 64,
                        "visible_bounds_width": 4, "visible_bounds_height": 14, "visible_bounds_offset": [0, 6, 0]},
        "bones": bones}]}


def geo_cube(ident, size, y):
    h = size / 2
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": ident, "texture_width": 16, "texture_height": 16,
                        "visible_bounds_width": 2, "visible_bounds_height": 2, "visible_bounds_offset": [0, 0.5, 0]},
        "bones": [{"name": "cube", "pivot": [0, y, 0], "locators": {"center": [0, y, 0]},
                   "cubes": [{"origin": [-h, y - h, -h], "size": [size, size, size], "uv": [0, 0]}]}]}]}


def geo_empty():
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": "geometry.hitori_empty", "texture_width": 16, "texture_height": 16},
        "bones": [{"name": "root", "pivot": [0, 0, 0]}]}]}


GLITCH_ON = "q.mark_variant != %d" % STUN_V


def render_controllers():
    flick = "math.mod(math.floor(q.life_time * 9), (q.skin_id >= 1 ? 4 : 7)) == 0"
    shift = "math.mod(math.floor(q.life_time * 11), (q.skin_id >= 1 ? 5 : 9)) == 0"
    return {"format_version": "1.10.0", "render_controllers": {
        "controller.render.denshi_hitori": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"],
            # Glitch 中は時々 RGB ノイズが走り、テクスチャがずれる
            "overlay_color": {"r": "math.random(0, 1) > 0.5 ? 0.0 : 1.0", "g": "math.random(0, 1) > 0.5 ? 1.0 : 0.0",
                              "b": "1.0", "a": "(%s && %s) ? 0.45 : 0.0" % (GLITCH_ON, flick)},
            "uv_anim": {"offset": ["(%s && %s) ? math.random(-0.06, 0.06) : 0.0" % (GLITCH_ON, shift), "0.0"],
                        "scale": [1.0, 1.0]}},
        "controller.render.hitori_echo": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"],
            "overlay_color": {"r": "0.2", "g": "1.0", "b": "1.0", "a": "0.55 + math.random(0, 0.25)"}},
        "controller.render.hitori_simple": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"]},
    }}


def client(ident, tex, geo, material, animations=None, animate=None, particles=None,
           rc="controller.render.hitori_simple", extra=None):
    d = {"identifier": ident, "materials": {"default": material}, "textures": {"default": "textures/entity/" + tex},
         "geometry": {"default": geo}, "render_controllers": [rc]}
    if particles:
        d["particle_effects"] = particles
    if animations:
        d["animations"] = animations
        d["scripts"] = {"animate": animate}
    if extra:
        d.update(extra)
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": d}}


def rp_clients():
    clients = {
        "denshi_hitori": client(ID, "denshi_hitori", "geometry.denshi_hitori", "entity_alphatest",
                                hanims.short_names(sorted(SKILLS)), ["main", "aura_ctrl", "attack_fx"],
                                hanims.PARTICLE_MAP, rc="controller.render.denshi_hitori",
                                extra={"spawn_egg": {"base_color": "#f4f4f4", "overlay_color": "#101018"}}),
        "bit_bullet": client("hitori:bit_bullet", "hitori_missing", "geometry.hitori_bullet", "entity_emissive_alpha",
                             {"fx": "animation.hitori.cube_fx"}, ["fx"], {"trail": "hitori:bit_trail"}),
        "fragment": client("hitori:fragment", "hitori_missing", "geometry.hitori_fragment", "entity_emissive_alpha",
                           {"fx": "animation.hitori.fragment_fx"}, ["fx"], {"trail": "hitori:bit_trail"}),
        "gravity_cube": client("hitori:gravity_cube", "hitori_missing", "geometry.hitori_gravity_cube",
                               "entity_emissive_alpha", {"fx": "animation.hitori.gcube_fx"}, ["fx"],
                               {"trail": "hitori:bit_trail"}),
        "marker": client("hitori:marker", "hitori_empty", "geometry.hitori_empty", "entity_alphatest"),
        "blast": client("hitori:blast", "hitori_empty", "geometry.hitori_empty", "entity_alphatest"),
        "echo": client("hitori:echo", "denshi_hitori", "geometry.denshi_hitori", "entity_alphablend",
                       {"pose": "animation.hitori.echo_pose", "glitch": "animation.hitori.glitch",
                        "fx": "animation.hitori.echo_fx"}, ["pose", "glitch", "fx"],
                       {"trail": "hitori:glitch_aura"}, rc="controller.render.hitori_echo"),
        "director": client("hitori:director", "denshi_hitori", "geometry.denshi_hitori", "entity_alphatest",
                           {"pose": "animation.hitori.director_pose", "glitch": "animation.hitori.glitch"},
                           ["pose", "glitch"], rc="controller.render.denshi_hitori"),
    }
    # 通常攻撃の左右切り替え用の変数
    smooth_client(clients["denshi_hitori"]["minecraft:client_entity"]["description"])
    return clients


def rp_summon_anims():
    jit = "math.random(0, 1) > 0.85 ? math.random(-2, 2) : 0"
    return {
        "animation.hitori.cube_fx": {"loop": True, "animation_length": 0.1,
                                     "bones": {"cube": {"rotation": ["q.life_time * 540", "q.life_time * 720", 0]}},
                                     "particle_effects": {"0.00": [{"effect": "trail", "locator": "center"}]}},
        "animation.hitori.gcube_fx": {"loop": True, "animation_length": 0.1,
                                      "bones": {"cube": {"rotation": [0, "q.life_time * 240", 0]}},
                                      "particle_effects": {"0.00": [{"effect": "trail", "locator": "center"}]}},
        "animation.hitori.fragment_fx": {"loop": True, "animation_length": 0.2,
                                         "bones": {"cube": {"rotation": [0, "q.life_time * 360", 0],
                                                            "position": [jit, "math.sin(q.life_time * 360) * 1.5", jit],
                                                            "scale": "1 + math.sin(q.life_time * 900) * 0.1"}},
                                         "particle_effects": {"0.00": [{"effect": "trail", "locator": "center"}]}},
    }


def lang():
    return "\n".join(["entity.%s.name=%s" % (ID, NAME),
                      "item.spawn_egg.entity.%s.name=%sのスポーンエッグ" % (ID, NAME),
                      "entity.hitori:bit_bullet.name=データ弾", "entity.hitori:fragment.name=フォークボム",
                      "entity.hitori:marker.name=目印", "entity.hitori:gravity_cube.name=重力キューブ",
                      "entity.hitori:echo.name=残像", "entity.hitori:blast.name=衝撃", "entity.hitori:director.name=電子 独",
                      "item.hitori:music_disc_kakuzetsu.name=隔絶された記憶",
                      # 「隔絶された記憶」はジュークボックス上はレコード 11 の音として鳴らす（下の注記参照）
                      "item.record_11.desc=eight - 隔絶された記憶",
                      "pack.name=電子 独 ボス", "pack.description=不具合・Glitch（自我の使者）ボスアドオン", ""])


# ---------------------------------------------------------------------------
# 音源・レコード
# ---------------------------------------------------------------------------
def to_ogg(src, dst, stereo, quality):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", src, "-vn", "-map_metadata", "-1", "-ar", "44100",
           "-c:a", "libvorbis", "-q:a", str(quality)]
    if not stereo:
        cmd += ["-ac", "1"]
    subprocess.run(cmd + [dst], check=True)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def sound_definitions():
    def stream(name, vol):
        return [{"name": "%s/%s" % (SOUND_DIR, name), "stream": True, "volume": vol, "load_on_low_memory": True}]
    return {"format_version": "1.14.0", "sound_definitions": {
        BGM_MEMORY: {"category": "music", "sounds": stream("kakuzetsu_bgm", 0.9)},
        BGM_DIVE: {"category": "music", "sounds": stream("freedom_dive_bgm", 0.9)},
        "record.%s" % DISC_SOUND_EVENT: {"__use_legacy_max_distance": "true", "category": "record",
                                         "max_distance": None, "min_distance": None,
                                         "sounds": stream("kakuzetsu_record", 0.6)},
    }}


def disc_item(length):
    return {"format_version": "1.20.80", "minecraft:item": {
        "description": {"identifier": DISC_ID,
                        "menu_category": {"category": "items", "group": "itemGroup.name.record"}},
        "components": {
            "minecraft:icon": {"texture": "hitori_disc_kakuzetsu"},
            "minecraft:display_name": {"value": "§b隔絶された記憶"},
            "minecraft:max_stack_size": 1,
            "minecraft:record": {"sound_event": DISC_SOUND_EVENT, "duration": math.ceil(length),
                                 "comparator_signal": 11},
        }}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skin", nargs="?", default=os.path.join(RP, "textures/entity/denshi_hitori.png"))
    ap.add_argument("--bgm", help="通常時の BGM（隔絶された記憶）の音声ファイル")
    ap.add_argument("--dive", help="↓FREEDOM DiVE↓ 解放後の BGM（FREEDOM DiVE）の音声ファイル")
    args = ap.parse_args()
    skin_bytes = open(args.skin, "rb").read()
    # 前回ビルドで変換済みの音源は引き継ぐ
    cache = {}
    for name in AUDIO:
        f = os.path.join(RP, SOUND_DIR, name + ".ogg")
        if os.path.exists(f):
            cache[name] = open(f, "rb").read()
    for d in (BP, RP, DIST):
        if os.path.isdir(d):
            shutil.rmtree(d)
    # BP
    write(os.path.join(BP, "manifest.json"), manifest("bp"))
    write(os.path.join(BP, "entities/denshi_hitori.json"), bp_entity())
    sb, sa = summons_bp()
    for name, data in sb.items():
        write(os.path.join(BP, "entities/%s.json" % name), data)
    anims_all = bp_animations()
    anims_all["animations"].update(sa)
    write(os.path.join(BP, "animations/denshi_hitori.animation.json"), anims_all)
    write(os.path.join(BP, "animation_controllers/denshi_hitori.ac.json"), bp_controllers())
    write(os.path.join(BP, "loot_tables/entities/denshi_hitori.json"), bp_loot())
    # RP
    write(os.path.join(RP, "manifest.json"), manifest("rp"))
    os.makedirs(os.path.join(RP, "textures/entity"), exist_ok=True)
    open(os.path.join(RP, "textures/entity/denshi_hitori.png"), "wb").write(skin_bytes)
    for name, data in rp_clients().items():
        write(os.path.join(RP, "entity/%s.entity.json" % name), data)
    write(os.path.join(RP, "models/entity/denshi_hitori.geo.json"), geo_boss())
    write(os.path.join(RP, "models/entity/hitori_bullet.geo.json"), geo_cube("geometry.hitori_bullet", 4, 0))
    write(os.path.join(RP, "models/entity/hitori_fragment.geo.json"), geo_cube("geometry.hitori_fragment", 8, 6))
    write(os.path.join(RP, "models/entity/hitori_empty.geo.json"), geo_empty())
    # 本体のモーションと、召喚物・撃破演出のモーションは別のファイルに分ける
    ra = hanims.all_animations()
    add_arc_trails(ra["animations"], {"hand_noise"}, arc="arc", reach=False)
    bake_smooth(ra["animations"], step=SMOOTH_STEP)
    summ = rp_summon_anims()
    for k in ("animation.hitori.echo_pose", "animation.hitori.echo_fx", "animation.hitori.director_pose"):
        summ[k] = ra["animations"].pop(k)
    vectorize_animations(ra["animations"])
    vectorize_animations(summ)
    write(os.path.join(RP, "animations/denshi_hitori.animation.json"), ra)
    write(os.path.join(RP, "animations/hitori_summons.animation.json"), {"format_version": "1.10.0", "animations": summ})
    write(os.path.join(RP, "animation_controllers/denshi_hitori.ac.json"), hanims.controllers(sorted(SKILLS)))
    write(os.path.join(RP, "render_controllers/denshi_hitori.rc.json"), render_controllers())
    for name, data in hfx.build_particles().items():
        write(os.path.join(RP, "particles/%s.json" % name), data)
    os.makedirs(os.path.join(RP, "textures/particle"), exist_ok=True)
    texs = hfx.build_textures()
    for name, im in texs.items():
        im.save(os.path.join(RP, "textures/particle/%s.png" % name))
    texs["hitori_missing"].save(os.path.join(RP, "textures/entity/hitori_missing.png"))
    hfx.Image.new("RGBA", (16, 16)).save(os.path.join(RP, "textures/entity/hitori_empty.png"))
    write(os.path.join(RP, "models/entity/hitori_gravity_cube.geo.json"), geo_cube("geometry.hitori_gravity_cube", 12, 6))
    # 音源（BGM とレコード）
    srcs = {"kakuzetsu_bgm": args.bgm, "kakuzetsu_record": args.bgm, "freedom_dive_bgm": args.dive}
    for name, (stereo, q) in AUDIO.items():
        dst = os.path.join(RP, SOUND_DIR, name + ".ogg")
        if srcs[name]:
            to_ogg(srcs[name], dst, stereo, q)
        elif name in cache:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, "wb").write(cache[name])
        else:
            print("警告: 音源 %s がありません（--bgm / --dive で指定してください）" % name)
    write(os.path.join(RP, "sounds/sound_definitions.json"), sound_definitions())
    rec = os.path.join(RP, SOUND_DIR, "kakuzetsu_record.ogg")
    write(os.path.join(BP, "items/music_disc_kakuzetsu.json"), disc_item(duration(rec) if os.path.exists(rec) else 177))
    os.makedirs(os.path.join(RP, "textures/items"), exist_ok=True)
    hfx.disc_icon().save(os.path.join(RP, "textures/items/hitori_disc_kakuzetsu.png"))
    write(os.path.join(RP, "textures/item_texture.json"), {
        "resource_pack_name": "hitori", "texture_name": "atlas.items",
        "texture_data": {"hitori_disc_kakuzetsu": {"textures": "textures/items/hitori_disc_kakuzetsu"}}})
    for d in (BP, RP):
        for lc in ("ja_JP", "en_US"):
            write(os.path.join(d, "texts/%s.lang" % lc), lang())
        write(os.path.join(d, "texts/languages.json"), ["ja_JP", "en_US"])
        open(os.path.join(d, "pack_icon.png"), "wb").write(skin_bytes)
    # 声・足音・守りの反応・瀕死の演出
    brushup_files(BP, RP, dict(id=ID, ns="hitori", prop="hitori:react", react_events=["hitori:glitch_hit"], evade_events=["hitori:glitch_hit"], evade_skill=60,
             react_anim={"loop": True, "bones": {   # Glitch が攻撃を飲み込む: 体がブレて、一瞬 T ポーズ
                 "root": {"position": ["v.react * math.random(-1.5, 1.5)", 0, "v.react * math.random(-1.5, 1.5)"]},
                 "head": {"rotation": [0, 0, "v.react * 35"]}, "rightArm": {"rotation": [0, 0, "v.react * 70"]},
                 "leftArm": {"rotation": [0, 0, "-v.react * 70"]}}},
             prefix="animation.hitori", main_ctrl="controller.animation.hitori.main", glow="hitori_glow", pitch=1.05))
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "DenshiHitori_Boss.mcaddon")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for pack, arc in ((BP, "Hitori_BP"), (RP, "Hitori_RP")):
            for dp, _, fs in sorted(os.walk(pack)):
                for f in sorted(fs):
                    full = os.path.join(dp, f)
                    z.write(full, os.path.join(arc, os.path.relpath(full, pack)))
    print("built", out)


if __name__ == "__main__":
    main()
