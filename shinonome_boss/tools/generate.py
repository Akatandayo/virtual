# -*- coding: utf-8 -*-
"""東雲 永々（しののめ とあ）ボスアドオン生成スクリプト.

使い方: python3 shinonome_boss/tools/generate.py [skin.png] [--classic]
スキンを省略すると、前回のスキン（なければ仮のスキン）を使います。腕の太さはスキンから自動で判定します。
"""
import argparse
import json
import math
import os
import random
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xanims  # noqa: E402
import xfx  # noqa: E402
from cine import (brushup_files, FOE_ANY, RIVAL_FAMILY, Cine, add_arc_trails, add_rival, aim_at_foes, bake_smooth,  # noqa: E402
                  pause_events, split_melee, apply_stance_groups, stance_events, stance_filters, STANCE_ANIM,
                  encounter_cmds, foe_tag_anim, footwork_steps, near_filters, rival_target, smooth_client,
                  split_dashes, vectorize_animations)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BP = os.path.join(ROOT, "Shinonome_BP")
RP = os.path.join(ROOT, "Shinonome_RP")
DIST = os.path.join(ROOT, "dist")

ID = "shinonome:toa"
NAME = "東雲 永々"
VERSION = [1, 8, 0]
MIN_ENGINE = [1, 21, 0]
UUID_BP_HEADER = "a694ca4a-12aa-4554-8bdb-12089cc1e7f6"
UUID_BP_MODULE = "f1947c40-91af-45a7-8801-580cb386961f"
UUID_RP_HEADER = "318594ae-9cab-43a7-b7d6-a2fd008b0011"
UUID_RP_MODULE = "93d636bd-b3bb-4fcd-be95-b8078e80415c"

HP = 2000
POSSESS_HP = 1300    # 65%: シニスターの憑依
TIMESTOP_HP = 700    # 35%: 全時間停止 → 狂化が解禁
OBJ_PLAYERS = "toa_players"
OILED = "toa_oiled"

random.seed(137)
BOSS = "@e[type=%s,c=1]" % ID
NEAREST = "@p[r=48,m=!creative]"
ANYONE = "@p[r=64]"
FACE = "^ ^1.3 ^"   # 背が低い（137cm）
CINE = Cine("toa_cine")


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


def act(text):
    return "/title @a[r=40] actionbar %s" % text


def p(r=24, rm=None):
    return "@a[r=%s%s,m=!creative]" % (r, ",rm=%s" % rm if rm is not None else "")


def pt(name, pos="~ ~ ~"):
    return "/particle shinonome:%s %s" % (name, pos)


def at_players(r, name, pos="~ ~ ~"):
    return "/execute at %s run particle shinonome:%s %s" % (p(r), name, pos)


def at_fam(fam, cmd):
    return "/execute at @e[family=%s] run %s" % (fam, cmd)


def shake(i, sec, r=24):
    return "/camerashake add @a[r=%d] %.2f %.2f positional" % (r, i, sec)


def sound(name, pitch=1.0, r=40, vol=1.0):
    return "/playsound %s @a[r=%d] ~ ~ ~ %.1f %.2f" % (name, r, vol, pitch)


def flash(r, g, b, rad=32, t=(0.05, 0.1, 0.2)):
    return "/camera @a[r=%d] fade time %.2f %.2f %.2f color %d %d %d" % (rad, t[0], t[1], t[2], r, g, b)


def marker(kind, pos="~ ~ ~", at=None):
    cmd = "summon shinonome:marker %s shinonome:as_%s" % (pos, kind)
    return "/execute at %s run %s" % (at, cmd) if at else "/" + cmd


def despawn(fam):
    return "/event entity @e[family=%s] shinonome:despawn" % fam


def rnd_off(r, rmin=0.0):
    a = random.uniform(0, 2 * math.pi)
    d = random.uniform(rmin, r)
    return "~%.1f ~ ~%.1f" % (d * math.cos(a), d * math.sin(a))


def ring_pts(radius, n, y=0.2, phase=0.0):
    for i in range(n):
        a = 2 * math.pi * i / n + phase
        yield "~%.2f ~%.2f ~%.2f" % (radius * math.cos(a), y, radius * math.sin(a))


def face_nearest():
    return "/tp @s ~ ~ ~ facing %s" % NEAREST


def line(cmd, dists, y=1.0):
    return ["/execute at @s positioned ^ ^%.1f ^%.1f run %s" % (y, d, cmd) for d in dists]


def front_of_nearest(d=1.5):
    return "/execute as %s at @s facing entity %s feet positioned ^ ^ ^%.1f run tp %s ~ ~ ~ facing @s" % (
        NEAREST, BOSS, d, BOSS)


def behind_nearest(d=1.6):
    return "/execute as %s at @s positioned ^ ^ ^-%.1f run tp %s ~ ~ ~ facing @s" % (NEAREST, d, BOSS)


def fire_damage(sel_cmd_prefix, r, dmg):
    """炎ダメージ（オイルで可燃状態の相手には2倍）"""
    return ["%s damage @a[r=%s,m=!creative] %d fire entity %s" % (sel_cmd_prefix, r, dmg, BOSS),
            "%s damage @a[r=%s,m=!creative,tag=%s] %d fire entity %s" % (sel_cmd_prefix, r, OILED, dmg, BOSS)]


SKILLS = {}


def skill(v, name, length, tl):
    SKILLS[v] = (name, length, {"%.2f" % k: c for k, c in sorted(tl.items())})


def add(tl, t, cmds):
    tl.setdefault(round(t, 2), []).extend(cmds)


# 星弾（重力・軽で使う）: 向きと速さの組み合わせごとにイベントを作る
STAR_EVENTS = {}


def star(deg, speed="normal"):
    name = "shinonome:s_%s_%s" % (("m%d" % -deg) if deg < 0 else deg, speed)
    STAR_EVENTS[name] = (deg, speed)
    return "/summon shinonome:star ~ ~1.1 ~ %s" % name


# ===========================================================================
# 技（第一形態から）
# ===========================================================================
# 1 / 51 / 52（第一形態）・53 / 54 / 55（憑依後）分身！！: 分身と入れ替わりながら紛れる。本物は左目が金色に光る
def clone_skill(v, with_window):
    tl = {0: [act("§f§l◆ 分身！！ §r§7―― 本物は左目が金色に光る"), say("§f東雲§7「分身！！」"),
              sound("mob.evocation_illager.prepare_summon", 1.6)]}
    add(tl, 0.25, [pt("smoke", "~ ~0.8 ~")] + ["/summon shinonome:clone ~ ~ ~ shinonome:c%d" % k for k in range(1, 5)])
    if with_window:
        add(tl, 0.3, ["/event entity @e[family=toa_clone,r=8] shinonome:with_window"])
    for t in (0.55, 1.15):
        spots = [rnd_off(5, 2.5) for _ in range(5)]
        cmds = ["/execute at %s run tp @s %s" % (NEAREST, spots[0])]
        cmds += ["/execute at %s run tp @e[family=toa_c%d,c=1] %s" % (NEAREST, k, spots[k]) for k in range(1, 5)]
        cmds += ["/execute at @e[family=toa_clone] run particle shinonome:smoke ~ ~0.8 ~", pt("smoke", "~ ~0.8 ~"),
                 sound("mob.endermen.portal", 1.8, 30, 0.6)]
        add(tl, t, cmds)
    add(tl, 1.3, [say("§f東雲§7「どーれだ？」")])
    skill(v, "分身", 1.4, tl)


for v, ww in ((1, False), (51, False), (52, False), (53, True), (54, True), (55, True)):
    clone_skill(v, ww)

# 2 ワープホール斬り: ワープホールに消え、背後から 3 回斬る
tl = {0: [act("§5◆ ワープホール斬り")], 0.2: [pt("portal", "~ ~1 ~"), sound("mob.endermen.portal", 0.8, 30)]}
for i, t in enumerate((0.75, 1.45, 2.15)):
    add(tl, t - 0.35, ["/execute as %s at @s positioned ^ ^1 ^-2 run particle shinonome:portal ~ ~ ~" % NEAREST,
                       sound("mob.shulker.teleport", 1.2, 30)])
    add(tl, t - 0.1, [pt("portal", "~ ~1 ~"), behind_nearest(1.6)])
    add(tl, t, ["/damage %s 9 entity_attack entity @s" % p(3), pt("slash_purple", "^ ^1 ^1.2"),
                at_players(3, "spark", "~ ~1 ~"), sound("game.player.attack.strong", 1.0 + i * 0.15, 30), shake(0.3, 0.15, 8)])
skill(2, "ワープホール斬り", 2.6, tl)

# 3 斬撃の檻: 足元に斬撃の檻が現れ、閉じる
tl = {0: [act("§f◆ 斬撃の檻"), marker("cage", at=p(32))]}
for t in (0.15, 0.45, 0.75):
    add(tl, t, [at_fam("cage", "particle shinonome:warn_white ~ ~0.1 ~")]
        + ["/execute at @e[family=cage] run particle shinonome:slash_white %s" % q for q in ring_pts(2.6, 6, 1.0, t)])
add(tl, 1.0, [at_fam("cage", "damage @a[r=2.8,m=!creative] 10 entity_attack entity %s" % BOSS),
              at_fam("cage", "particle shinonome:big_slash_white ~ ~1 ~"), at_fam("cage", "particle shinonome:spark ~ ~1 ~"),
              sound("item.trident.hit", 0.8, 40), despawn("cage")])
skill(3, "斬撃の檻", 1.6, tl)

# 4 重力操作・重: 体が重くなり、重力が落ちてくる
tl = {0: [act("§5◆ 重力操作・重"), "/effect %s slowness 3 2 true" % p(24), at_players(24, "gravity_down", "~ ~ ~"),
          sound("mob.warden.sonic_charge", 0.5, 40)],
      0.3: [marker("crush", at=p(32))] + [marker("crush", rnd_off(3.5), at=p(32)) for _ in range(2)]}
for t in (0.35, 0.65, 0.95):
    add(tl, t, [at_fam("crush", "particle shinonome:warn_purple ~ ~0.1 ~"), at_fam("crush", "particle shinonome:gravity_down ~ ~ ~")])
add(tl, 1.3, [at_fam("crush", "damage @a[r=2,m=!creative] 11 entity_attack entity %s" % BOSS),
              at_fam("crush", "particle shinonome:shockwave_purple ~ ~0.1 ~"), at_fam("crush", "particle shinonome:hole_core ~ ~0.5 ~"),
              sound("random.anvil_land", 0.4, 40), shake(0.6, 0.3, 32), despawn("crush")])
add(tl, 1.8, ["/damage %s 8 entity_attack entity @s" % p(4), pt("shockwave_big_purple", "~ ~0.1 ~"), sound("random.explode", 1.2)])
skill(4, "重力操作・重", 2.6, tl)

# 5 重力操作・軽: 体がふわっと浮き、宙で星弾を撃ち込まれる
tl = {0: [act("§b◆ 重力操作・軽"), "/effect %s levitation 2 0 true" % p(24), "/effect %s slow_falling 4 0 true" % p(24),
          at_players(24, "gravity_up", "~ ~ ~"), sound("beacon.activate", 1.8, 40)]}
for i, t in enumerate((0.6, 1.1, 1.6)):
    add(tl, t, [star(a, "normal") for a in (-16, -8, 0, 8, 16)] + [sound("random.orb", 1.2 + i * 0.2, 30)])
skill(5, "重力操作・軽", 2.6, tl)

# 6 引力: 引き寄せて、吹き飛ばす
tl = {0: [act("§5◆ 引力 §7―― 離れろ！"), pt("charge_purple", "~ ~1 ~"), sound("mob.warden.sonic_charge", 0.8, 40)]}
for i in range(26):
    add(tl, 0.2 + i * 0.05, ["/execute as %s at @s facing entity %s feet run tp @s ^ ^ ^0.25" % (p(16, 2.5), BOSS)]
        + ([pt("hole", "~ ~1 ~")] if i % 5 == 0 else []))
add(tl, 1.6, ["/summon shinonome:blast ~ ~0.5 ~ shinonome:big", "/damage %s 8 entity_attack entity @s" % p(5),
              pt("shockwave_big_purple", "~ ~0.1 ~"), shake(1.0, 0.4, 24)])
skill(6, "引力", 2.0, tl)

# 7 ドリルフランス: 回転するフランスパンを 3 本（貫通）
tl = {0: [act("§6◆ ドリルフランス")]}
for i, (t, a) in enumerate(((0.4, -6), (0.75, 6), (1.1, 0))):
    add(tl, t, ["/summon shinonome:bread ~ ~1.2 ~ shinonome:b_%s" % ("m%d" % -a if a < 0 else a), sound("random.bow", 1.4, 30)])
skill(7, "ドリルフランス", 1.5, tl)

# 8 オイルフランス: 当たると「可燃」状態（炎のダメージが2倍）
tl = {0: [act("§6◆ オイルフランス"), marker("oil", at=NEAREST)], 0.2: [at_fam("oil", "particle shinonome:warn_gold ~ ~0.1 ~")],
      0.6: [at_fam("oil", "particle shinonome:oil ~ ~1 ~"), at_fam("oil", "particle shinonome:bread_burst ~ ~1 ~"),
            at_fam("oil", "tag @a[r=3,m=!creative] add %s" % OILED),
            at_fam("oil", "damage @a[r=3,m=!creative] 3 entity_attack entity %s" % BOSS),
            "/title @a[tag=%s] actionbar §6§l可燃状態！ §r§6炎のダメージが2倍" % OILED, sound("random.splash", 0.6, 30),
            despawn("oil")]}
skill(8, "オイルフランス", 1.2, tl)

# 9 火稲: 頭上に小さな太陽を作り、落とす（炎・可燃状態なら2倍）
tl = {0: [act("§c◆ 火稲（かとう） §7―― 炎耐性があると防げる")]}
for i in range(12):
    add(tl, 0.3 + i * 0.1, [pt("sun", "~ ~3.6 ~")] + ([pt("charge_gold", "~ ~3.6 ~")] if i % 4 == 0 else []))
add(tl, 0.9, [marker("sun", at=NEAREST), sound("mob.blaze.shoot", 0.5, 40)])
for t in (0.95, 1.25, 1.55):
    add(tl, t, ["/execute at @e[family=sun] run particle shinonome:warn_red %s" % q for q in ring_pts(4, 8, 0.1)]
        + [at_fam("sun", "particle shinonome:warn_red ~ ~0.1 ~")])
add(tl, 1.8, fire_damage("/execute at @e[family=sun] run", 4, 14)
    + [at_fam("sun", "particle shinonome:fire_burst ~ ~0.5 ~"), at_fam("sun", "particle shinonome:shockwave_red ~ ~0.1 ~"),
       at_fam("sun", "particle shinonome:sun ~ ~0.5 ~"), at_fam("sun", "playsound random.explode @a[r=32] ~ ~ ~ 1 0.8"),
       shake(0.8, 0.4, 32), despawn("sun")])
skill(9, "火稲", 2.4, tl)

# 10 銀の光線: 当たった相手の効果（ポーションなど）を全部消す
SB = range(2, 16, 2)
tl = {0: [act("§7◆ 銀の光線 §r§7―― 当たるとポーション効果が消える"), face_nearest()]}
for t in (0.2, 0.4, 0.6):
    add(tl, t, line("particle shinonome:beam_warn ~ ~ ~", SB, 1.0))
add(tl, 0.85, line("effect @a[r=1.5,m=!creative] clear", SB) + line("damage @a[r=1.5,m=!creative] 6 magic entity %s" % BOSS, SB)
    + line("particle shinonome:silver_beam ~ ~ ~", SB) + [sound("beacon.deactivate", 1.8, 40)])
skill(10, "銀の光線", 1.6, tl)

# 11 束縛の鎖: 一番近い相手を鎖で縛り、3 回斬る
CH = "toa_chained"
tl = {0: [act("§7◆ 束縛の鎖"), "/tag @a remove %s" % CH],
      0.2: ["/tag %s add %s" % (NEAREST, CH), "/effect @a[tag=%s] slowness 3 255 true" % CH,
            "/title @a[tag=%s] actionbar §7§l鎖に縛られた！" % CH, sound("random.chestclosed", 0.5, 30)],
      0.6: [front_of_nearest(1.5)]}
for t in (0.25, 0.55, 0.85, 1.15, 1.45):
    add(tl, t, ["/execute at @a[tag=%s] run particle shinonome:chain ~ ~ ~" % CH])
for i, t in enumerate((1.0, 1.4, 1.8)):
    add(tl, t, ["/damage %s 7 entity_attack entity @s" % p(3), pt("slash_purple", "^ ^1 ^1.2"),
                sound("game.player.attack.strong", 1.0 + i * 0.2, 30)])
add(tl, 2.1, ["/tag @a remove %s" % CH])
skill(11, "束縛の鎖", 2.2, tl)

# 12 ハンテン: 触れたもの全部を裏返す（前後も上下も）
tl = {0: [act("§d◆ ハンテン"), pt("charge_white", "~ ~1 ~")],
      0.6: ["/execute as %s at @s run tp @s ~ ~ ~ ~180 ~" % p(12), "/effect %s levitation 1 10 true" % p(12),
            "/damage %s 5 magic entity @s" % p(12), "/title %s actionbar §d§lハンテン！ §r§d前も後ろも、上も下も" % p(12),
            pt("shockwave_white", "~ ~0.1 ~"), sound("random.pop", 0.5, 30)]}
skill(12, "ハンテン", 1.6, tl)

# 13 おやつタイム: 座ってハンバーガーを食べる（少し回復する。今が攻めどき）
tl = {0: [act("§a◆ おやつタイム！ §r§7―― 今がチャンス！"), say("§f東雲§7「ちょっと休憩〜。もぐもぐ」"),
          "/effect @s slowness 3 255 true", sound("random.eat", 1.0, 30)]}
for i in range(5):
    add(tl, 0.5 + i * 0.5, [sound("random.eat", 0.9 + i * 0.05, 30, 0.8)])
add(tl, 2.8, ["/effect @s instant_health 1 2 true", "/effect @s regeneration 3 1 true", sound("random.burp", 1.2, 30),
              pt("spark", "~ ~1 ~")])
skill(13, "おやつタイム", 3.0, tl)

# 14 黒胎刀・連斬: 黒い刀で 4 連撃
tl = {0: [act("§8◆ 黒胎刀・連斬"), front_of_nearest(1.8)]}
for i, t in enumerate((0.3, 0.6, 0.9, 1.2)):
    add(tl, t, ["/damage %s 6 entity_attack entity @s" % p(3.2), pt("slash_purple" if i % 2 else "slash_white", "^ ^1 ^1.2"),
                at_players(3.2, "spark", "~ ~1 ~"), sound("game.player.attack.strong", 0.8 + i * 0.1, 30)])
skill(14, "黒胎刀・連斬", 1.6, tl)

# ===========================================================================
# 技（シニスターの憑依 = HP65% から）
# ===========================================================================
# 15 虚無重核: 3 つのブラックホールが周りを回り、相手のところで潰れる
tl = {0: [act("§5§l◆ 虚無重核 §r§7―― ブラックホールから離れろ"), sound("mob.warden.sonic_charge", 0.5, 40)],
      0.2: ["/summon shinonome:hole ~ ~1 ~ shinonome:h%d" % k for k in range(3)]}
skill(15, "虚無重核", 2.6, tl)

# 16 炎龍: 黒胎刀から炎の龍を放つ（炎・可燃状態なら2倍）
tl = {0: [act("§c§l◆ 炎龍"), sound("mob.blaze.shoot", 0.4, 40)],
      1.15: ["/summon shinonome:dragon ^ ^1.4 ^1", "/tp @e[type=shinonome:dragon,c=1] ~ ~1.4 ~ facing %s" % NEAREST,
             pt("fire_burst", "^ ^1.4 ^1"), sound("mob.enderdragon.growl", 1.6, 48), shake(0.5, 0.3, 24)]}
skill(16, "炎龍", 1.6, tl)

# 17 マルチバースソード: 空から巨大な剣が 3 本落ちてくる
tl = {0: [act("§b§l◆ マルチバースソード"), say("§f東雲§7「どーん！」")]}
for k, t in enumerate((1.0, 1.8, 2.6)):
    fam = "sword_%d" % (k % 2)
    add(tl, t - 0.9, [marker(fam, at=NEAREST)])
    for dt in (0.85, 0.6, 0.35):
        add(tl, t - dt, ["/execute at @e[family=%s] run particle shinonome:warn_cyan %s" % (fam, q) for q in ring_pts(2.6, 6, 0.1)]
            + [at_fam(fam, "particle shinonome:warn_cyan ~ ~0.1 ~")])
    add(tl, t - 0.3, [at_fam(fam, "particle shinonome:big_sword ~ ~ ~"), at_fam(fam, "playsound item.trident.throw @a[r=32] ~ ~ ~ 1 0.5")])
    add(tl, t, [at_fam(fam, "damage @a[r=3.2,m=!creative] 18 entity_attack entity %s" % BOSS),
                at_fam(fam, "particle shinonome:shockwave_big_cyan ~ ~0.1 ~"), at_fam(fam, "particle shinonome:spark ~ ~0.5 ~"),
                at_fam(fam, "playsound random.anvil_land @a[r=32] ~ ~ ~ 1 0.5"), shake(0.9, 0.4, 32), despawn(fam)])
skill(17, "マルチバースソード", 3.2, tl)

# 18 クロノスピア: 背中の窓から光線を 4 本（予告線つき）
tl = {0: [act("§b§l◆ クロノスピア"), sound("beacon.power", 1.6, 40)]}
for k, t in enumerate((0.8, 1.1, 1.4, 1.7)):
    fam = "aim_%d" % (k % 2)
    ln = "/execute at @s positioned ^ ^2.6 ^-0.4 facing entity @e[family=%s,c=1] feet positioned ^ ^ ^%.1f run %s"
    add(tl, t - 0.5, [marker(fam, "~ ~1 ~", at=NEAREST)])
    for dt in (0.45, 0.3, 0.15):
        add(tl, t - dt, [ln % (fam, d, "particle shinonome:beam_warn ~ ~ ~") for d in range(2, 30, 3)])
    add(tl, t, [ln % (fam, d * 1.5, "damage @a[r=1.5,m=!creative] 9 magic entity %s" % BOSS) for d in range(1, 20)]
        + [ln % (fam, d * 1.5, "particle shinonome:beam_cyan ~ ~ ~") for d in range(1, 20)]
        + [sound("beacon.deactivate", 1.8, 40), despawn(fam)])
skill(18, "クロノスピア", 2.4, tl)

# 19 アストラル無限刃: 斬撃が 1 → 2 → 4 → 8 と増えていく
tl = {0: [act("§b◆ アストラル無限刃")]}
for k in range(4):
    t = 0.5 + 0.5 * k
    offs = ["~ ~ ~"] if k == 0 else [rnd_off(3.2) for _ in range(2 ** k)]
    add(tl, t - 0.35, ["/execute at %s run particle shinonome:warn_cyan %s" % (p(32), o.replace("~ ~ ~", "~ ~0.1 ~") if o == "~ ~ ~"
                       else o.split()[0] + " ~0.1 " + o.split()[2]) for o in offs])
    add(tl, t, ["/execute at %s positioned %s run damage @a[r=1.6,m=!creative] 7 entity_attack entity %s" % (p(32), o, BOSS)
                for o in offs]
        + ["/execute at %s run particle shinonome:slash_cyan %s" % (p(32), o.split()[0] + " ~1 " + o.split()[2]) for o in offs]
        + [sound("item.trident.hit", 1.0 + k * 0.2, 40)])
skill(19, "アストラル無限刃", 2.4, tl)

# 20 混沌の体: 6 秒間、水の体になる（近接は効かない。飛び道具なら 1.5 倍）
tl = {0: [act("§b§l◆ 混沌の体 §r§b―― 近接は効かない、飛び道具で撃て！"), say("§f東雲§7「ぷるぷる〜」"),
          pt("water", "~ ~1 ~"), sound("random.splash", 1.2, 30)]}
skill(20, "混沌の体", 6.0, tl)

# 21 エンディング・タイム・フランス: 8 本のフランスパンが、8 通りの攻撃で襲いかかる
tl = {0: [act("§6§l◆ エンディング・タイム・フランス"), say("§f東雲§7「いっけー、フランスパン部隊！」"),
          pt("bread_burst", "~ ~1.5 ~")]}
STRIKES = [("big_slash_gold", "大槍"), ("silver_beam", "レーザー"), ("claw", "噛みつき"), ("big_slash_white", "斧"),
           ("slash_white", "ナイフ"), ("shockwave_gold", "こぶし"), ("bread_burst", "ドリル"), ("bread_rain", "大槍・二")]
for i, (eff, nm) in enumerate(STRIKES):
    t = 0.7 + 0.4 * i
    fam = "bread_%d" % (i % 2)
    add(tl, t - 0.35, [marker(fam, at=NEAREST), at_fam(fam, "particle shinonome:bread_ring ~ ~ ~")])
    add(tl, t - 0.3, [at_fam(fam, "particle shinonome:warn_gold ~ ~0.1 ~")])
    add(tl, t, [at_fam(fam, "damage @a[r=1.8,m=!creative] 6 entity_attack entity %s" % BOSS),
                at_fam(fam, "particle shinonome:%s ~ ~1 ~" % eff), at_fam(fam, "particle shinonome:bread_burst ~ ~1 ~"),
                "/title %s actionbar §6%d本目：%s" % (p(32), i + 1, nm), sound("random.pop", 0.6 + i * 0.1, 30), despawn(fam)])
add(tl, 4.0, [pt("bread_burst", "~ ~1.5 ~"), say("§f東雲§7「おかえり〜」")])
skill(21, "エンディング・タイム・フランス", 4.2, tl)

# 22 告死の輪光: 頭上に輪が浮かぶ。立ち止まっていると……
tl = {0: [act("§e§l◆ 告死の輪光 §r§e―― 動き続けろ！"), say("§f東雲§7「――止まってたら、死んじゃうよ？」")],
      0.2: [marker("halo_a", at=p(32))], 2.4: [marker("halo_b", at=p(32))]}
for i in range(9):
    add(tl, 0.2 + i * 0.5, [at_players(32, "halo", "~ ~2.2 ~"), sound("note.pling", 1.6, 30, 0.4)])
for fam, t in (("halo_a", 2.3), ("halo_b", 4.4)):
    add(tl, t, [at_fam(fam, "damage @a[r=2.5,m=!creative] 16 magic entity %s" % BOSS),
                at_fam(fam, "particle shinonome:shockwave_gold ~ ~0.1 ~"), at_fam(fam, "particle shinonome:spark ~ ~1 ~"),
                sound("block.bell.hit", 0.6, 40), despawn(fam)])
skill(22, "告死の輪光", 4.6, tl)

# 23 ねこぉ: 猫になって素早く引っかく × 3
tl = {0: [act("§6◆ ねこぉ"), say("§f東雲§7「にゃー！」"), "/effect @s speed 5 3 true", sound("mob.cat.meow", 1.4, 30)]}
for i, t in enumerate((1.2, 2.4, 3.6)):
    add(tl, t - 0.1, [front_of_nearest(1.2), pt("smoke", "~ ~0.5 ~")])
    add(tl, t, ["/damage %s 6 entity_attack entity @s" % p(2.5), pt("claw", "^ ^0.8 ^1"), at_players(2.5, "cat_paw", "~ ~1 ~"),
                sound("mob.cat.hiss", 1.2 + i * 0.1, 30)])
skill(23, "ねこぉ", 5.0, tl)

# 24 狂化（全時間停止のあと）: 8 秒間暴れ回り、そのあと 4 秒気絶する
tl = {0: [act("§c§l◆ 狂化 §r§c―― 終わると気絶する！"), say("§f東雲§7「あはっ、あはは、あはははは！」"),
          "/effect @s speed 8 2 true", sound("mob.ravager.roar", 1.6, 48)]}
for i in range(15):
    t = 0.4 + i * 0.5
    cmds = ["/damage %s 5 entity_attack entity @s" % p(3.5), pt("slash_red", "^ ^1 ^1.2"), sound("game.player.attack.strong", 1.4, 30)]
    if i % 3 == 0:
        cmds.insert(0, behind_nearest(1.5))
    add(tl, t, cmds)
add(tl, 7.9, ["@s shinonome:faint"])
skill(24, "狂化", 8.0, tl)

# 25 気絶（狂化のあと）: ダメージ 1.5 倍
tl = {0: [act("§e§l◆ 気絶中！ §r§e今のうちに！（ダメージ1.5倍）"), say("§f東雲§7「ふにゃ〜……」"), sound("random.pop", 0.5, 30)]}
skill(25, "気絶", 4.0, tl)

# ===========================================================================
# カットシーン
# ===========================================================================
# 30 登場: 空のワープホールから落ちてくる
tl = {}
add(tl, 0, CINE.begin(4.6) + [face_nearest().replace(NEAREST, ANYONE), CINE.cam("^ ^0.5 ^6", "^ ^8 ^"),
                              CINE.fade(0, 0.2, 0.6, (60, 0, 90)), pt("portal_flat", "~ ~8 ~"), pt("stars"),
                              sound("mob.endermen.portal", 0.5, 64), "/scoreboard objectives add %s dummy" % OBJ_PLAYERS])
add(tl, 0.7, [pt("portal_flat", "~ ~8 ~")])
add(tl, 1.6, [CINE.cam("^1 ^1.5 ^3.5", "^ ^1 ^", 0.7, "in_expo"), sound("mob.enderdragon.flap", 1.6, 64)])
add(tl, 2.3, [pt("smoke", "~ ~0.5 ~"), pt("shockwave_purple", "~ ~0.1 ~"), sound("random.pop", 0.5, 64), shake(0.4, 0.2, 16)])
add(tl, 2.9, [CINE.cam("^0.25 ^1.3 ^1.0", FACE), "/title @a[r=64] title §f東雲 永々",
              "/title @a[r=64] subtitle §7――年齢？ んー、分かんない。数億？"])
add(tl, 3.3, [say("§f東雲§7「ねえねえ、遊ぼ！」")])
add(tl, 3.9, [CINE.cam("^ ^2 ^6", FACE, 0.5, "out_expo")])
add(tl, 4.5, [CINE.fade(0, 0.05, 0.3, (60, 0, 90))] + CINE.end())
skill(30, "登場", 4.6, tl)

# 31 シニスターの憑依（HP65%）: 背中にクロノスピアの窓が現れる
tl = {}
add(tl, 0, CINE.begin(5) + [face_nearest().replace(NEAREST, ANYONE), CINE.cam("^-1.5 ^1.8 ^-3", "^ ^1.2 ^"),
                            CINE.fade(0, 0.2, 0.5), sound("mob.wither.spawn", 1.4, 64), pt("charge_purple", "~ ~1 ~")])
add(tl, 0.4, [say("§f東雲§7「……えへへ。ちょっとだけ、本気出しちゃおっかな」")])
add(tl, 1.2, [CINE.cam("^1.5 ^2 ^-2.5", "^ ^2.2 ^0.3", 1.2, "in_out_sine"), pt("stars")])
add(tl, 2.4, [CINE.cam("^ ^1.6 ^4.5", "^ ^1.6 ^"), "/title @a[r=64] title §5§lシニスターの憑依",
              "/title @a[r=64] subtitle §7――クロノスピア、展開", "/summon shinonome:blast ~ ~0.5 ~",
              pt("shockwave_big_purple", "~ ~0.1 ~"), pt("charge_cyan", "~ ~2.5 ~"), sound("beacon.activate", 0.6, 64),
              shake(1.2, 0.6, 48)])
add(tl, 3.4, [CINE.cam("^ ^9 ^6", "^ ^1 ^", 1.2, "in_out_sine")])
add(tl, 4.8, [CINE.fade(0, 0.05, 0.3, (120, 60, 200))] + CINE.end())
skill(31, "シニスターの憑依", 5.0, tl)

# 32 全時間停止（HP35%）: 時を止め、止まった相手の周りにフランスパンを並べ、時が動き出す
FROZEN = "toa_frozen"
tl = {}
add(tl, 0, CINE.begin(5.4) + ["/tag @a remove %s" % FROZEN, face_nearest().replace(NEAREST, ANYONE),
                              CINE.cam("^0.6 ^1.2 ^1.2", "^-0.3 ^1.3 ^0.4"), CINE.fade(0, 0.2, 0.5)])
add(tl, 0.45, ["/title @a[r=64] title §f§l全時間停止", "/title @a[r=64] subtitle §7――Absolute Time Stop",
               "/fog @a[r=64] push shinonome:timestop toa_timestop", pt("clock", "~ ~0.1 ~"), "/tag %s add %s" % (p(48), FROZEN),
               sound("random.anvil_use", 0.4, 64), flash(220, 220, 230, 64, (0, 0.1, 0.4))])
add(tl, 1.2, [CINE.cam("^ ^6 ^7", "^ ^1 ^", 1.6, "in_out_sine"), say("§f東雲§7「ぜーんぶ、止まっちゃえ」")])
for i in range(5):
    add(tl, 1.4 + i * 0.8, ["/execute at @a[tag=%s] run particle shinonome:bread_ring ~ ~ ~" % FROZEN,
                            "/execute at @a[tag=%s] run particle shinonome:clock ~ ~0.1 ~" % FROZEN] if i % 2 == 0 else
        ["/execute at @a[tag=%s] run particle shinonome:bread_ring ~ ~ ~" % FROZEN])
add(tl, 3.0, [CINE.cam("^ ^1.8 ^-2.5", "^ ^1.3 ^2", run_as="@p[tag=%s]" % FROZEN)])
add(tl, 4.3, [CINE.cam("^0.3 ^1.3 ^1.0", FACE), say("§f東雲§7「……じゃ、動き出すよ」")])
add(tl, 5.2, CINE.end() + ["/effect @a[tag=%s] slowness 1 255 true" % FROZEN,
                           "/title @a[tag=%s] actionbar §c§l時が動き出す――！" % FROZEN, sound("random.anvil_use", 1.6, 64)])
add(tl, 5.9, ["/damage @a[tag=%s] 16 entity_attack entity @s" % FROZEN,
              "/execute at @a[tag=%s] run particle shinonome:bread_burst ~ ~1 ~" % FROZEN,
              "/execute at @a[tag=%s] run particle shinonome:spark ~ ~1 ~" % FROZEN, "/fog @a[r=64] remove toa_timestop",
              flash(255, 255, 255, 64, (0, 0.05, 0.3)), shake(1.5, 0.6, 48), "/tag @a remove %s" % FROZEN])
add(tl, 6.3, [say("§f東雲§7「えへへ、びっくりした？」")])
skill(32, "全時間停止", 6.6, tl)

CINE_V = [30, 31, 32]
FAINT_V = 25

# 撃破カットシーン
DEATH = {}
add(DEATH, 0, CINE.begin(6) + [CINE.cam("~2.4 ~1.1 ~2.4", "~ ~0.6 ~"), CINE.fade(0, 0.3, 0.8, (60, 0, 90)),
                              pt("smoke", "~ ~0.5 ~"), "/playsound random.pop @a[r=64] ~ ~ ~ 1 0.6"])
add(DEATH, 0.1, [CINE.cam("~-2.4 ~1.3 ~2.4", "~ ~0.6 ~", 1.8, "linear")])
add(DEATH, 0.9, [say("§f東雲§7「ちぇー、負けちゃった」")])
add(DEATH, 1.9, [CINE.cam("~-2.4 ~1.6 ~-2.4", "~ ~0.6 ~", 1.8, "linear")])
add(DEATH, 2.6, [say("§f東雲§7「……おなかすいた。ハンバーガー食べに行こーっと。ばいばーい！」")])
add(DEATH, 3.7, [CINE.cam("~ ~5 ~-3", "~ ~1 ~", 1.0, "in_out_sine"), pt("portal", "~ ~1 ~")])
add(DEATH, 4.4, [pt("portal", "~ ~1 ~"), pt("smoke", "~ ~0.6 ~"), "/playsound mob.endermen.portal @a[r=32] ~ ~ ~ 1 1.2"])
add(DEATH, 5.3, [CINE.fade(0, 0.1, 0.6, (60, 0, 90))] + CINE.end())
add(DEATH, 5.35, ["/title @a[r=64] title §6§l討伐成功", "/title @a[r=64] subtitle §7東雲 永々を倒した",
                   "/playsound random.levelup @a[r=64] ~ ~ ~ 1 0.8", "/playsound random.totem @a[r=64] ~ ~ ~ 0.5 1.6"])
add(DEATH, 5.5, ["@s shinonome:despawn"])
DEATH = {"%.2f" % k: v for k, v in sorted(DEATH.items())}


# ---------------------------------------------------------------------------
# v1.2: 大技のカットイン・着地や叩きつけの土煙
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
# 60 ぴょーん: 後ろへぴょんと跳んで、星弾で返す
tl = {0: [act("§b◆ ぴょーん"), pt("smoke", "~ ~0.2 ~"), sound("mob.slime.big", 1.6, 30, 0.6)]}
footwork_steps(lambda t, c: add(tl, t, c), 0.05, 3, "^ ^0.35 ^-1.5", NEAREST, [pt("stars", "~ ~1 ~")])
add(tl, 0.22, [pt("step_dust"), pt("dust_ring", "~ ~0.1 ~")])
add(tl, 0.5, [star(-12), star(0), star(12), sound("random.orb", 1.6, 30), pt("spark", "^ ^1.2 ^0.8")])
skill(60, "ぴょーん", 1.1, tl)
# 61 / 62 くるっと回り込み: 相手の右・左へ回り込みながら間合いを詰め、横から斬る
for v, side in ((61, 1), (62, -1)):
    tl = {0: [act("§b◆ くるっと回り込み"), pt("smoke", "~ ~0.2 ~"), sound("mob.slime.small", 1.8, 24, 0.5)]}
    footwork_steps(lambda t, c: add(tl, t, c), 0.08, 7, "^%g ^ ^0.3" % (-1.3 * side), NEAREST,
                   [pt("spark", "~ ~0.9 ~")])
    add(tl, 0.56, [pt("slash_purple", "^ ^1.1 ^1.3"), pt("spark", "^ ^1 ^1.6"),
                   sound("game.player.attack.strong", 1.0, 30), sound("item.trident.riptide_1", 1.9, 30, 0.5),
                   "/execute positioned ^ ^1 ^1.6 run damage @a[r=2.3,m=!creative] 11 entity_attack entity @s",
                   shake(0.4, 0.25, 10)] + impact("^ ^ ^1.6"))
    skill(v, "くるっと回り込み", 1.3, tl)


cutin_into(17, 0.0, 0.8, "^ ^0.3 ^2", "^ ^12 ^6")
cutin_into(16, 0.3, 0.6, "^0.9 ^1.3 ^1.2", "^-0.3 ^1.5 ^0.2")
for v, t in ((30, 2.3), (6, 1.6), (4, 1.8), (31, 2.4), (12, 0.6), (32, 5.9)):
    patch(v, t, impact())
patch(4, 1.3, [at_fam("crush", "particle shinonome:debris ~ ~ ~"), at_fam("crush", "particle shinonome:dust_ring ~ ~ ~")])
for k, t in enumerate((1.0, 1.8, 2.6)):
    fam = "sword_%d" % (k % 2)
    patch(17, t, [at_fam(fam, "particle shinonome:debris ~ ~ ~"), at_fam(fam, "particle shinonome:dust_ring ~ ~ ~")])


# ---------------------------------------------------------------------------
# Behavior Pack: 本体
# ---------------------------------------------------------------------------
def manifest(kind):
    if kind == "bp":
        return {"format_version": 2,
                "header": {"name": "東雲 永々 ボス BP", "description": "ボス「東雲 永々」を追加します",
                           "uuid": UUID_BP_HEADER, "version": VERSION, "min_engine_version": MIN_ENGINE},
                "modules": [{"type": "data", "uuid": UUID_BP_MODULE, "version": VERSION}],
                "dependencies": [{"uuid": UUID_RP_HEADER, "version": VERSION}]}
    return {"format_version": 2,
            "header": {"name": "東雲 永々 ボス RP", "description": "ボス「東雲 永々」を追加します",
                       "uuid": UUID_RP_HEADER, "version": VERSION, "min_engine_version": MIN_ENGINE},
            "modules": [{"type": "resources", "uuid": UUID_RP_MODULE, "version": VERSION}]}


def phase_group(skin, speed, dmg, timer):
    return {"minecraft:skin_id": {"value": skin}, "minecraft:movement": {"value": speed},
            "minecraft:attack": {"damage": dmg},
            "minecraft:timer": {"looping": True, "time": timer, "randomInterval": True,
                                "time_down_event": {"event": "shinonome:choose_skill", "target": "self"}}}


SENSORS = ["sensor_normal", "water", "fainted", "cine_guard"]
IMMUNE = ("fall", "fire", "fire_tick", "lava", "drowning", "suffocation", "magic", "entity_explosion", "block_explosion",
          "wither", "lightning")
FOE = FOE_ANY   # プレイヤーと、ほかのボス


def bp_entity():
    imm = [{"cause": c, "deal_damage": False} for c in IMMUNE]
    groups = {
        "phase_1": phase_group(0, 0.37, 11, [1.8, 3.0]),
        "phase_2": phase_group(1, 0.41, 14, [1.5, 2.6]),
        "phase_3": phase_group(2, 0.45, 17, [1.2, 2.2]),
        "sensor_normal": {"minecraft:damage_sensor": {"triggers": [
            {"cause": "entity_attack", "on_damage": {"filters": FOE, "event": "shinonome:on_hit"}},
            {"cause": "projectile", "damage_multiplier": 0.8}] + imm}},
        # 混沌の体: 近接は無効（ぷるん）、飛び道具は 1.5 倍
        "water": {"minecraft:damage_sensor": {"triggers": [
            {"cause": "entity_attack", "deal_damage": False, "on_damage": {"event": "shinonome:splash"}},
            {"cause": "projectile", "damage_multiplier": 1.5}] + imm}},
        # 気絶: ダメージ 1.5 倍
        "fainted": {"minecraft:damage_sensor": {"triggers": [
            {"cause": "entity_attack", "damage_multiplier": 1.5},
            {"cause": "projectile", "damage_multiplier": 1.2}] + imm}},
        "cine_guard": {"minecraft:damage_sensor": {"triggers": [{"cause": "all", "deal_damage": False}]}},
        "ai": {
            "minecraft:behavior.float": {"priority": 0},
            "minecraft:behavior.melee_attack": {"priority": 2, "speed_multiplier": 1.4, "track_target": True},
            "minecraft:behavior.hurt_by_target": {"priority": 1},
            "minecraft:behavior.nearest_attackable_target": {
                "priority": 2, "must_see": False, "reselect_targets": True, "within_radius": 48,
                "entity_types": [{"filters": {"test": "is_family", "subject": "other", "value": "player"}, "max_dist": 48},
                                 rival_target("shinonome")]},   # ほかのボス（白夜・独・ソフィア）
            "minecraft:behavior.random_stroll": {"priority": 6, "speed_multiplier": 0.9},
            "minecraft:behavior.look_at_player": {"priority": 7, "look_distance": 16},
        },
    }
    split_melee(groups, "shinonome")   # 近接の構え / 遠距離の構え
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
        rm, ad = sensor("cine_guard")
        return set_variant(v, ad + list(add_), rm + ["ai"] + list(remove_))

    busy = CINE_V + [FAINT_V]
    not_busy = {"all_of": [{"test": "is_mark_variant", "operator": "!=", "value": c} for c in busy]}
    rm_n, ad_n = sensor("sensor_normal")

    events = {
        "minecraft:entity_spawned": {"add": {"component_groups": ["phase_1", "v_30", "cine_guard"]}},
        # 技の終わり: 一定確率でそのまま次の行動へ（バースト制御アーツ:終式）
        "shinonome:skill_end": {"sequence": [{"filters": not_busy, **set_variant(0, ad_n, rm_n),
                                              "queue_command": {"command": ["event entity @s shinonome:combo_roll"]}}]},
        "shinonome:combo_roll": {"sequence": [
            {"filters": {"test": "is_skin_id", "value": skin}, "randomize": [
                {"weight": w, "trigger": "shinonome:choose_skill",
                 "queue_command": {"command": ["title @a[r=24] actionbar §d§l連続行動！"]}},
                {"weight": 100 - w, "queue_command": {"command": ["particle shinonome:spark ~ ~0.5 ~"]}}]}
            for skin, w in ((0, 35), (1, 42), (2, 50))]},
        "shinonome:cine_end": set_variant(0, ad_n + ["ai"], rm_n),
        # 本体に当たったとき、分身がいれば「見つかった」
        "shinonome:on_hit": {"queue_command": {"command": [
            "particle shinonome:spark ~ ~1 ~",
            "execute if entity @e[family=toa_clone,r=48] run event entity @s shinonome:found"]}},
        "shinonome:found": {"queue_command": {"command": [
            "event entity @e[family=toa_clone,r=48] shinonome:poof", "effect @s slowness 2 255 true",
            "title @a[r=32] actionbar §e§l本物発見！ §r§e分身が消えた",
            'tellraw @a[r=48] {"rawtext":[{"text":"§f東雲§7「わっ、見つかっちゃった！」"}]}',
            "particle shinonome:smoke ~ ~1 ~", "playsound random.levelup @a[r=24] ~ ~ ~ 0.6 1.6"]}},
        "shinonome:splash": {"queue_command": {"command": [
            "particle shinonome:water ~ ~1 ~", "playsound random.splash @a[r=16] ~ ~ ~ 0.5 1.6",
            "title @a[r=12] actionbar §b水の体には近接攻撃が効かない！ 飛び道具で撃て！"]}},
        "shinonome:faint": set_variant(FAINT_V, ["fainted"], ["sensor_normal", "water"]),
        "shinonome:possess": cine(31, ["phase_2"], ["phase_1"]),
        "shinonome:timestop": cine(32, ["phase_3"], ["phase_1", "phase_2"]),
        # ソフィアが近くにいると「おすわり」（一度だけ）
        "shinonome:osuwari": {"queue_command": {"command": [
            "tag @s add toa_osuwari",
            'tellraw @a[r=48] {"rawtext":[{"text":"§f東雲§7「あっ、ソフィアだ！ ……おすわり！」"}]}',
            "event entity @e[family=sophia,r=24] sophia:osuwari", "particle shinonome:spark ~ ~1.5 ~"]}},
    }
    for v in sorted(SKILLS):
        if v in busy:
            continue
        if v == 20:
            events["shinonome:skill_20"] = set_variant(20, ["water"], ["sensor_normal", "fainted"])
        else:
            events["shinonome:skill_%d" % v] = set_variant(v)

    near1 = [1, 51, 52, 2, 3, 4, 6, 8, 11, 12, 13, 14, 14, 9, 60, 60, 61, 62]   # 60〜62: 立ち回り
    far1 = [1, 51, 52, 2, 3, 4, 5, 5, 7, 7, 8, 9, 10, 10, 60]   # 60: 間合いを取って遠距離で返す
    late_clone = [53, 54, 55]
    near2 = [s for s in near1 if s not in (1, 51, 52)] + late_clone + [15, 16, 17, 18, 19, 20, 21, 22, 23]
    far2 = [s for s in far1 if s not in (1, 51, 52)] + late_clone + [15, 16, 17, 18, 18, 19, 21, 22]
    near3 = near2 + [24, 24, 16, 22]
    far3 = far2 + [24, 17, 18, 22]
    NEAR, FAR = stance_filters("shinonome_near")   # 近接の構えで敵が近い → 近距離の技 / それ以外 → 遠距離の技
    base = [{"test": "is_mark_variant", "value": 0}, {"test": "has_target", "value": True}]
    seq = []
    for skin, near, far in ((0, near1, far1), (1, near2, far2), (2, near3, far3)):
        for cond, lst in ((NEAR, near), (FAR, far)):
            seq.append({"filters": {"all_of": base + [{"test": "is_skin_id", "value": skin}, cond]},
                        "randomize": [{"weight": 10, "trigger": "shinonome:skill_%d" % s} for s in lst]})
    events["shinonome:choose_skill"] = {"sequence": seq}

    # ほかのボスの演出（登場など）のあいだは一時停止して、お互いに手出ししない
    events.update(pause_events(not_busy))
    # 間合いの判断: 4 秒ごとに「近接の構え / 遠距離の構え」を選び直す（HP が減ると遠距離寄り）
    events.update(stance_events(not_busy, 60, 40, int(HP * 0.4)))
    apply_stance_groups(events)

    components = {
        "minecraft:type_family": {"family": ["shinonome", "boss", RIVAL_FAMILY, "monster", "mob"]},
        "minecraft:health": {"value": HP, "max": HP},
        "minecraft:boss": {"hud_range": 64, "should_darken_sky": True},
        "minecraft:nameable": {"always_show": True, "allow_name_tag_renaming": False},
        "minecraft:persistent": {},
        "minecraft:scale": {"value": 0.85},
        "minecraft:collision_box": {"width": 0.6, "height": 1.6},
        "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": True},
        "minecraft:knockback_resistance": {"value": 1.0},
        "minecraft:fire_immune": {},
        "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0, "breathes_water": True},
        "minecraft:jump.static": {},
        "minecraft:movement.basic": {},
        "minecraft:movement": {"value": 0.37},
        "minecraft:navigation.walk": {"can_path_over_water": True, "avoid_damage_blocks": True},
        "minecraft:follow_range": {"value": 48, "max": 64},
        "minecraft:attack": {"damage": 11},
        "minecraft:equipment": {"table": "loot_tables/entities/toa_equipment.json",
                                "slot_drop_chance": [{"slot": "slot.weapon.mainhand", "drop_chance": 0}]},
        "minecraft:loot": {"table": "loot_tables/entities/toa.json"},
        "minecraft:experience_reward": {"on_death": "1500"},
        "minecraft:environment_sensor": {"triggers": [
            {"filters": {"all_of": [{"test": "actor_health", "operator": "<=", "value": POSSESS_HP},
                                    {"test": "is_skin_id", "value": 0}] + not_busy["all_of"]}, "event": "shinonome:possess"},
            {"filters": {"all_of": [{"test": "actor_health", "operator": "<=", "value": TIMESTOP_HP},
                                    {"test": "is_skin_id", "value": 1}] + not_busy["all_of"]}, "event": "shinonome:timestop"},
        ]},
    }
    anims = {"skills": "controller.animation.toa.skills", "death": "controller.animation.toa.death",
             "upkeep": "animation.toa.upkeep", "idle_loop": "animation.toa.idle_loop",
             "foe_tags": "animation.toa.foe_tags", "stance": "animation.toa.stance_loop",
             **{"skill_%d" % v: "animation.toa.skill_%d" % v for v in SKILLS}}
    return {"format_version": "1.21.0", "minecraft:entity": {
        "description": {"identifier": ID, "is_spawnable": True, "is_summonable": True, "is_experimental": False,
                        "scripts": {"animate": ["skills", "upkeep", "death", "foe_tags", "stance"]}, "animations": anims},
        "component_groups": groups, "components": components, "events": events}}


# ほかのボスと初めて会ったときのひとこと（ソフィアには「おすわり」も）
ENCOUNTER = {'byakuya': '§f東雲§7「ねえねえ、キセルのひと！\u3000その刀かっこいいね！\u3000遊ぼ！」', 'hitori': '§f東雲§7「あっ、カクカクしてる！\u3000バグってるの？\u3000えへへ、遊ぼ遊ぼ！」', 'sophia': '§f東雲§7「あ、ソフィアだ！\u3000えへへ……今日は本気で遊んじゃおっかな！」', 'fuuka': '§f東雲§7「あっ、風花ちゃんだ！ 今日は敵だね、えへへ……遊ぼ！」'}


def bp_animations():
    a = {"animation.toa.skill_%d" % v: {"animation_length": length, "loop": False, "timeline": tl}
         for v, (name, length, tl) in SKILLS.items()}
    a["animation.toa.upkeep"] = {"animation_length": 8.0, "loop": True, "timeline": {
        "0.50": ["/scoreboard players set @s %s 0" % OBJ_PLAYERS,
                 "/execute as @a[r=40,m=!creative] run scoreboard players add %s %s 1" % (BOSS, OBJ_PLAYERS),
                 "/execute if score @s %s matches 2 run effect @s resistance 9 0 true" % OBJ_PLAYERS,
                 "/execute if score @s %s matches 3 run effect @s resistance 9 1 true" % OBJ_PLAYERS,
                 "/execute if score @s %s matches 4.. run effect @s resistance 9 2 true" % OBJ_PLAYERS],
        "2.00": ["/execute at @a[tag=%s] run particle shinonome:oil_drip ~ ~ ~" % OILED],
        "4.00": ["/execute at @a[tag=%s] run particle shinonome:oil_drip ~ ~ ~" % OILED],
        "7.90": ["/tag @a remove %s" % OILED]}}
    a["animation.toa.idle_loop"] = {"animation_length": 2.0, "loop": True, "timeline": {"1.00": CINE.end() + [
        "/execute if entity @s[tag=!toa_osuwari] if entity @e[family=sophia,r=16] run event entity @s shinonome:osuwari"],
        "1.50": encounter_cmds("shinonome", say, ENCOUNTER)}}   # ほかのボスの発見
    # 常に動く: 敵の目印と「近くに敵がいる」タグ
    a["animation.toa.stance_loop"] = STANCE_ANIM   # 間合いの判断（4 秒ごと）
    a["animation.toa.foe_tags"] = foe_tag_anim(ID, "shinonome_near")
    return {"format_version": "1.10.0", "animations": a}


def bp_controllers():
    states = {"default": {"animations": ["idle_loop"],
                          "transitions": [{"skill_%d" % v: "q.mark_variant == %d" % v} for v in sorted(SKILLS)]}}
    for v in sorted(SKILLS):
        states["skill_%d" % v] = {"animations": ["skill_%d" % v],
                                  "transitions": [{"default": "q.all_animations_finished || q.mark_variant != %d" % v}],
                                  "on_exit": ["@s shinonome:%s" % ("cine_end" if v in CINE_V else "skill_end")]}
    # 気絶の終わりは通常の技の終わりと同じ扱い（skill_end は気絶中は動かないので、専用に戻す）
    states["skill_%d" % FAINT_V]["on_exit"] = ["@s shinonome:cine_end"]
    return {"format_version": "1.10.0", "animation_controllers": {
        "controller.animation.toa.skills": {"initial_state": "default", "states": states},
        "controller.animation.toa.death": {"initial_state": "alive", "states": {
            "alive": {"transitions": [{"dead": "!q.is_alive"}]},
            "dead": {"on_entry": ["/summon shinonome:director ~ ~ ~", "/fog @a[r=64] remove toa_timestop",
                                  "/tag @a remove %s" % FROZEN, "/tag @a remove %s" % CH, "/tag @a remove %s" % OILED,
                                  "/event entity @e[family=toa_clone] shinonome:poof"] + CINE.end()}}},
    }}


def bp_loot():
    drop = {"pools": [
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:netherite_sword", "weight": 1, "functions": [
            {"function": "set_name", "name": "§8§l黒胎刀"},
            {"function": "set_lore", "lore": ["§7宇宙から来た子の刀", "§8ダメージ：無限……？"]},
            {"function": "specific_enchants", "enchants": [
                {"id": "sharpness", "level": 5}, {"id": "unbreaking", "level": 3}, {"id": "fire_aspect", "level": 2},
                {"id": "looting", "level": 3}, {"id": "mending", "level": 1}]}]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:bread", "weight": 1, "functions": [
            {"function": "set_count", "count": 32}, {"function": "set_name", "name": "§6フランスパン（東雲製）"}]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:cooked_beef", "weight": 1, "functions": [
            {"function": "set_count", "count": 8}, {"function": "set_name", "name": "§eハンバーガー"}]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:nether_star", "weight": 1, "functions": [
            {"function": "set_name", "name": "§5虚無重核のかけら"}]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:totem_of_undying", "weight": 1}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:netherite_ingot", "weight": 1,
                                  "functions": [{"function": "set_count", "count": {"min": 2, "max": 4}}]}]},
    ]}
    equip = {"pools": [{"rolls": 1, "entries": [{"type": "item", "name": "minecraft:netherite_sword", "weight": 1,
                                                 "functions": [{"function": "set_name", "name": "§8黒胎刀"}]}]}]}
    return drop, equip


# ---------------------------------------------------------------------------
# 補助エンティティ
# ---------------------------------------------------------------------------
TICK = 0.05
MARKERS = ["cage", "crush", "oil", "sun", "sword_0", "sword_1", "aim_0", "aim_1", "bread_0", "bread_1", "halo_a", "halo_b"]
DESPAWN_G = {"despawn": {"minecraft:instant_despawn": {}}}
DESPAWN_E = {"shinonome:despawn": {"add": {"component_groups": ["despawn"]}}}


def fx_base(family, hitbox=0.2):
    return {"minecraft:type_family": {"family": family}, "minecraft:health": {"value": 1, "max": 1},
            "minecraft:collision_box": {"width": hitbox, "height": hitbox},
            "minecraft:physics": {"has_gravity": False, "has_collision": False},
            "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
            "minecraft:knockback_resistance": {"value": 1.0}, "minecraft:body_rotation_blocked": {},
            "minecraft:fire_immune": {}, "minecraft:damage_sensor": {"triggers": [{"cause": "all", "deal_damage": False}]},
            "minecraft:conditional_bandwidth_optimization": {"default_values": {
                "max_optimized_distance": 0, "max_dropped_ticks": 0, "use_motion_prediction_hints": True}}}


def entity(ident, comps, groups, events, anims_=None, animate=None):
    d = {"identifier": ident, "is_spawnable": False, "is_summonable": True, "is_experimental": False}
    if anims_:
        d["animations"] = anims_
        d["scripts"] = {"animate": animate}
    return {"format_version": "1.21.0", "minecraft:entity": {"description": d, "component_groups": groups,
                                                              "components": comps, "events": events}}


def ticks(length, fn, end=None):
    n = int(round(length / TICK))
    tl = {"%.2f" % (i * TICK): fn(i) for i in range(n)}
    if end:
        tl["%.2f" % ((n - 1) * TICK)] = tl["%.2f" % ((n - 1) * TICK)] + end
    return tl


def hit(r, dmg, cause="magic", despawn_=True, extra=(), dy=0.0):
    pos = "positioned ~ ~%.1f ~ " % dy if dy else ""
    sel = "@a[r=%.1f,m=!creative]" % r
    out = ["/execute %sif entity %s run damage %s %d %s" % (pos, sel, sel, dmg, cause)]
    out += ["/execute %sif entity %s run %s" % (pos, sel, e) for e in extra]
    if despawn_:
        out.append("/execute %sif entity %s run event entity @s shinonome:despawn" % (pos, sel))
    return out


def summons_bp():
    out, A, C = {}, {}, {}
    # 分身: 殴るとハズレ（爆風で吹き飛ばされる）
    clone_g = dict(DESPAWN_G, window={"minecraft:skin_id": {"value": 1}})
    clone_e = {
        "shinonome:pop": {"add": {"component_groups": ["despawn"]}, "queue_command": {"command": [
            "summon shinonome:blast ~ ~0.8 ~", "particle shinonome:smoke ~ ~0.8 ~",
            "title @a[r=8] actionbar §c§lハズレ！ §r§7本物は左目が金色に光っている",
            'tellraw @a[r=24] {"rawtext":[{"text":"§f東雲§7「ざんねーん、ハズレ！」"}]}']}},
        "shinonome:poof": {"add": {"component_groups": ["despawn"]},
                           "queue_command": {"command": ["particle shinonome:smoke ~ ~0.8 ~"]}},
        "shinonome:with_window": {"add": {"component_groups": ["window"]}},
    }
    for k in range(1, 5):
        clone_g["c%d" % k] = {"minecraft:type_family": {"family": ["toa_clone", "toa_c%d" % k, "monster", "mob"]}}
        clone_e["shinonome:c%d" % k] = {"add": {"component_groups": ["c%d" % k]}}
    clone = {
        "minecraft:type_family": {"family": ["toa_clone", "monster", "mob"]},
        "minecraft:health": {"value": 20, "max": 20}, "minecraft:scale": {"value": 0.85},
        "minecraft:collision_box": {"width": 0.6, "height": 1.6}, "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
        "minecraft:movement": {"value": 0.36}, "minecraft:movement.basic": {}, "minecraft:jump.static": {},
        "minecraft:navigation.walk": {"can_path_over_water": True}, "minecraft:attack": {"damage": 6},
        "minecraft:follow_range": {"value": 40, "max": 40},
        "minecraft:nameable": {"always_show": True, "allow_name_tag_renaming": False},
        # 爆風では割れない（連鎖しないように）。それ以外のダメージで「ハズレ」
        "minecraft:damage_sensor": {"triggers": [
            {"cause": "entity_explosion", "deal_damage": False}, {"cause": "fall", "deal_damage": False},
            {"cause": "all", "deal_damage": False, "on_damage": {"event": "shinonome:pop", "target": "self"}}]},
        "minecraft:equipment": {"table": "loot_tables/entities/toa_equipment.json",
                                "slot_drop_chance": [{"slot": "slot.weapon.mainhand", "drop_chance": 0}]},
        "minecraft:behavior.melee_attack": {"priority": 2, "speed_multiplier": 1.4, "track_target": True},
        "minecraft:behavior.nearest_attackable_target": {"priority": 1, "must_see": False, "within_radius": 40,
                                                         "entity_types": [{"filters": {"test": "is_family", "subject": "other",
                                                                                       "value": "player"}, "max_dist": 40}]},
        "minecraft:behavior.random_stroll": {"priority": 6},
        "minecraft:behavior.look_at_player": {"priority": 7, "look_distance": 16},
        "minecraft:timer": {"looping": False, "time": 14, "time_down_event": {"event": "shinonome:poof", "target": "self"}},
    }
    out["clone"] = entity("shinonome:clone", clone, clone_g, clone_e)
    # 星弾
    g, e = dict(DESPAWN_G), dict(DESPAWN_E)
    g["spd"] = {"minecraft:variant": {"value": 1}}
    A["animation.toa.star.fly"] = {"animation_length": 2.55, "loop": False, "timeline": ticks(
        2.5, lambda i: ["/tp @s ^ ^ ^0.6"] + hit(1.2, 6, dy=-1.0, extra=[
            "particle shinonome:spark ~ ~1 ~", "playsound random.orb @a[r=12] ~ ~ ~ 0.7 1.4"]),
        end=["@s shinonome:despawn"])}
    for name, (deg, spd) in STAR_EVENTS.items():
        e[name] = {"add": {"component_groups": ["spd"]}, "queue_command": {"command": [
            "tp @s ~ ~ ~ facing @p[m=!creative]", "tp @s ~ ~ ~ ~%d ~" % deg]}}
    out["star"] = entity("shinonome:star", fx_base(["toa_fx", "inanimate"]), g, e, {"fly": "animation.toa.star.fly"}, ["fly"])
    # ドリルフランス（貫通）
    g, e = dict(DESPAWN_G), dict(DESPAWN_E)
    for a in (-6, 0, 6):
        e["shinonome:b_%s" % ("m%d" % -a if a < 0 else a)] = {"queue_command": {"command": [
            "tp @s ~ ~ ~ facing @p[m=!creative]", "tp @s ~ ~ ~ ~%d ~" % a]}}
    A["animation.toa.bread.fly"] = {"animation_length": 1.55, "loop": False, "timeline": ticks(
        1.5, lambda i: ["/tp @s ^ ^ ^0.85"] + hit(1.4, 8, "entity_attack", despawn_=False, dy=-0.8),
        end=["/particle shinonome:bread_burst ~ ~ ~", "@s shinonome:despawn"])}
    out["bread"] = entity("shinonome:bread", fx_base(["toa_fx", "inanimate"]), g, e, {"fly": "animation.toa.bread.fly"}, ["fly"])
    # ブラックホール × 3: 周りを回り、相手のところで潰れる
    g, e = dict(DESPAWN_G), dict(DESPAWN_E)
    hole_anims = {}
    for k in range(3):
        g["h%d" % k] = {"minecraft:variant": {"value": k + 1}}
        e["shinonome:h%d" % k] = {"add": {"component_groups": ["h%d" % k]}}

        def hole(i, k=k):
            if i < 40:
                cmds = ["/execute at %s rotated %d 0 positioned ^ ^1 ^4 run tp @s ~ ~ ~" % (BOSS, k * 120 + i * 9)]
            else:
                cmds = ["/execute at @s facing entity @p[m=!creative] feet positioned ^ ^ ^0.5 run tp @s ~ ~ ~"]
            cmds.append("/execute as @a[r=3.5,m=!creative] at @s facing entity @e[type=shinonome:hole,c=1] feet run tp @s ^ ^ ^0.1")
            if i % 10 == 0:
                cmds.append("/damage @a[r=2,m=!creative] 3 magic")
            return cmds
        A["animation.toa.hole.o%d" % k] = {"animation_length": 2.65, "loop": False, "timeline": ticks(
            2.6, hole, end=["/damage @a[r=3,m=!creative] 12 magic", "/summon shinonome:blast ~ ~ ~",
                            "/particle shinonome:shockwave_big_purple ~ ~ ~", "/playsound mob.warden.sonic_boom @a[r=32] ~ ~ ~ 0.8 1.4",
                            "@s shinonome:despawn"])}
        hole_anims["o%d" % k] = "animation.toa.hole.o%d" % k
    C["controller.animation.toa.hole"] = {"initial_state": "pick", "states": {
        "pick": {"transitions": [{"o%d" % k: "q.variant == %d" % (k + 1)} for k in range(3)]},
        **{"o%d" % k: {"animations": ["o%d" % k]} for k in range(3)}}}
    out["hole"] = entity("shinonome:hole", fx_base(["toa_fx", "inanimate"]), g, e,
                         dict(hole_anims, ctrl="controller.animation.toa.hole"), ["ctrl"])
    # 炎龍: 螺旋を描いて昇り → 相手を追い → 突っ込んで爆発
    def dragon(i):
        if i < 24:
            cmds = ["/tp @s ^0.55 ^0.12 ^0.3 ~15 ~"]
        elif i < 48:
            cmds = ["/execute at @s facing entity @p[m=!creative] feet positioned ^ ^ ^0.6 run tp @s ~ ~ ~ facing @p[m=!creative]"]
        else:
            cmds = ["/tp @s ^ ^ ^0.8"]
        if i % 2 == 0:
            cmds += fire_damage("/execute positioned ~ ~-0.8 ~ run", 2.2, 6)
        return cmds
    A["animation.toa.dragon.fly"] = {"animation_length": 3.05, "loop": False, "timeline": ticks(
        3.0, dragon, end=fire_damage("/execute run", 3.5, 12) + [
            "/particle shinonome:fire_burst ~ ~ ~", "/particle shinonome:shockwave_red ~ ~-0.5 ~", "/summon shinonome:blast ~ ~ ~",
            "@s shinonome:despawn"])}
    out["dragon"] = entity("shinonome:dragon", fx_base(["toa_fx", "inanimate"]), dict(DESPAWN_G), dict(DESPAWN_E),
                           {"fly": "animation.toa.dragon.fly"}, ["fly"])
    # 目印
    g, e = dict(DESPAWN_G), dict(DESPAWN_E)
    for k in MARKERS:
        g[k] = {"minecraft:type_family": {"family": ["toa_marker", k, "inanimate"]}}
        e["shinonome:as_" + k] = {"add": {"component_groups": [k]}}
    A["animation.toa.marker.life"] = {"animation_length": 5.05, "loop": False, "timeline": {"5.00": ["@s shinonome:despawn"]}}
    out["marker"] = entity("shinonome:marker", fx_base(["toa_marker", "inanimate"], 0.1), g, e,
                           {"life": "animation.toa.marker.life"}, ["life"])
    # 爆風
    ex = {"fuse_length": 0, "fuse_lit": True, "causes_fire": False, "breaks_blocks": False,
          "destroy_affected_by_griefing": False}
    out["blast"] = {"format_version": "1.21.0", "minecraft:entity": {
        "description": {"identifier": "shinonome:blast", "is_spawnable": False, "is_summonable": True,
                        "is_experimental": False},
        "component_groups": {"small": {"minecraft:explode": dict(ex, power=2)}, "big": {"minecraft:explode": dict(ex, power=4)}},
        "components": fx_base(["toa_fx", "inanimate"], 0.1),
        "events": {"minecraft:entity_spawned": {"add": {"component_groups": ["small"]}},
                   "shinonome:big": {"add": {"component_groups": ["big"]}}}}}
    # 撃破カットシーンの監督
    A["animation.toa.director.death"] = {"animation_length": 5.6, "loop": False, "timeline": DEATH}
    out["director"] = entity("shinonome:director", fx_base(["toa_fx", "inanimate"], 0.1), dict(DESPAWN_G), dict(DESPAWN_E),
                             {"cut": "animation.toa.director.death"}, ["cut"])
    return out, A, C


# ---------------------------------------------------------------------------
# Resource Pack
# ---------------------------------------------------------------------------
def cube(origin, size, uv, inflate=0):
    c = {"origin": origin, "size": size, "uv": uv}
    if inflate:
        c["inflate"] = inflate
    return c


def geo_boss(slim):
    aw, ax = (3, 7) if slim else (4, 8)
    ay = 11.5 if slim else 12
    piv = 21.5 if slim else 22
    bones = [
        {"name": "root", "pivot": [0, 0, 0]},
        {"name": "body", "parent": "root", "pivot": [0, 24, 0], "cubes": [
            cube([-4, 12, -2], [8, 12, 4], [16, 16]), cube([-4, 12, -2], [8, 12, 4], [16, 32], 0.25)],
         "locators": {"body_center": [0, 18, 0], "window_center": [0, 27, 7]}},
        {"name": "head", "parent": "body", "pivot": [0, 24, 0], "cubes": [
            cube([-4, 24, -4], [8, 8, 8], [0, 0]), cube([-4, 24, -4], [8, 8, 8], [32, 0], 0.5)],
         "locators": {"eye": [2, 28, -4.6], "head_top": [0, 33, 0]}},
        {"name": "rightArm", "parent": "body", "pivot": [-5, piv, 0], "cubes": [
            cube([-ax, ay, -2], [aw, 12, 4], [40, 16]), cube([-ax, ay, -2], [aw, 12, 4], [40, 32], 0.25)],
         "locators": {"right_hand": [-ax + aw / 2, ay - 0.5, 0], "reach": [-ax + aw / 2, ay - 7, -1.5]}},
        {"name": "rightItem", "parent": "rightArm", "pivot": [-ax + aw / 2, ay + 3, 1]},
        {"name": "leftArm", "parent": "body", "pivot": [5, piv, 0], "cubes": [
            cube([4, ay, -2], [aw, 12, 4], [32, 48]), cube([4, ay, -2], [aw, 12, 4], [48, 48], 0.25)],
         "locators": {"left_hand": [4 + aw / 2, ay - 0.5, 0]}},
        {"name": "rightLeg", "parent": "root", "pivot": [-1.9, 12, 0], "cubes": [
            cube([-3.9, 0, -2], [4, 12, 4], [0, 16]), cube([-3.9, 0, -2], [4, 12, 4], [0, 32], 0.25)],
         "locators": {"right_foot": [-2, 0, 0]}},
        {"name": "leftLeg", "parent": "root", "pivot": [1.9, 12, 0], "cubes": [
            cube([-0.1, 0, -2], [4, 12, 4], [16, 48]), cube([-0.1, 0, -2], [4, 12, 4], [0, 48], 0.25)],
         "locators": {"left_foot": [2, 0, 0]}},
    ]
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": "geometry.toa", "texture_width": 64, "texture_height": 64,
                        "visible_bounds_width": 4, "visible_bounds_height": 14, "visible_bounds_offset": [0, 6, 0]},
        "bones": bones}]}


def geo_window():
    """背中に浮かぶ「窓」の武装（クロノスピア）。体の動きに合わせて動く"""
    gold = {f: {"uv": [0, 0], "uv_size": [16, 16]} for f in ("north", "south", "east", "west", "up", "down")}
    pane = {"north": {"uv": [16, 0], "uv_size": [16, 32]}, "south": {"uv": [16, 0], "uv_size": [16, 32]}}
    frame = [([-10, 36, 6], [20, 2, 1]), ([-10, 14, 6], [20, 2, 1]), ([-10, 14, 6], [2, 24, 1]), ([8, 14, 6], [2, 24, 1]),
             ([-1, 16, 6], [2, 20, 1]), ([-8, 25, 6], [16, 2, 1])]
    cubes = [{"origin": o, "size": s, "uv": gold} for o, s in frame]
    cubes.append({"origin": [-8, 16, 6.5], "size": [16, 20, 0], "uv": pane})
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": "geometry.toa_window", "texture_width": 32, "texture_height": 32,
                        "visible_bounds_width": 4, "visible_bounds_height": 14, "visible_bounds_offset": [0, 6, 0]},
        "bones": [{"name": "root", "pivot": [0, 0, 0]}, {"name": "body", "parent": "root", "pivot": [0, 24, 0]},
                  {"name": "window", "parent": "body", "pivot": [0, 26, 6], "cubes": cubes}]}]}


def geo_small():
    face = {"uv": [0, 0], "uv_size": [32, 8]}
    bread_uv = {f: face for f in ("north", "south", "east", "west", "up", "down")}
    return {
        "geometry.toa_empty": [{"name": "root", "pivot": [0, 0, 0], "locators": {"center": [0, 0, 0]}}],
        # 星弾: 発光する芯 + 半透明の外殻
        "geometry.toa_star": [
            {"name": "orb", "pivot": [0, 0, 0], "locators": {"center": [0, 0, 0]},
             "cubes": [{"origin": [-1.5, -1.5, -1.5], "size": [3, 3, 3], "uv": {
                 f: {"uv": [0, 0], "uv_size": [8, 8]} for f in ("north", "south", "east", "west", "up", "down")}}]},
            {"name": "shell", "parent": "orb", "pivot": [0, 0, 0],
             "cubes": [{"origin": [-3, -3, -3], "size": [6, 6, 6], "uv": {
                 f: {"uv": [8, 0], "uv_size": [8, 8]} for f in ("north", "south", "east", "west", "up", "down")}}]}],
        # 前（-Z）を向いた細長いフランスパン。くるくる回る（ドリル）
        "geometry.toa_bread": [{"name": "roll", "pivot": [0, 0, 0], "locators": {"center": [0, 0, 0]},
                                "cubes": [{"origin": [-1.5, -1.5, -8], "size": [3, 3, 16], "uv": bread_uv}]}],
    }


def geo_files():
    sizes = {"geometry.toa_empty": (16, 16), "geometry.toa_bread": (32, 8), "geometry.toa_star": (16, 16)}
    out = {}
    for ident, bones in geo_small().items():
        w, h = sizes[ident]
        out[ident] = {"format_version": "1.12.0", "minecraft:geometry": [{
            "description": {"identifier": ident, "texture_width": w, "texture_height": h,
                            "visible_bounds_width": 3, "visible_bounds_height": 3, "visible_bounds_offset": [0, 0.5, 0]},
            "bones": bones}]}
    return out


def render_controllers():
    water = "q.mark_variant == 20"
    return {"format_version": "1.10.0", "render_controllers": {
        "controller.render.toa": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"],
            # 混沌の体（水）・狂化・気絶で色が変わる
            "overlay_color": {"r": "%s ? 0.3 : (q.mark_variant == 24 ? 1.0 : 0.9)" % water,
                              "g": "%s ? 0.7 : (q.mark_variant == 24 ? 0.1 : 0.9)" % water,
                              "b": "%s ? 1.0 : (q.mark_variant == 24 ? 0.1 : 0.3)" % water,
                              "a": "%s ? 0.45 + math.sin(q.life_time * 500) * 0.1 : (q.mark_variant == 24 ? "
                                   "0.25 + math.sin(q.life_time * 900) * 0.1 : (q.mark_variant == 25 ? 0.2 : 0.0))" % water}},
        "controller.render.toa_window": {
            "geometry": "Geometry.window", "materials": [{"*": "Material.window"}], "textures": ["Texture.window"]},
        "controller.render.toa_star": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}, {"shell": "Material.shell"}],
            "textures": ["Texture.default"]},
        "controller.render.toa_simple": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"]},
    }}


def client(ident, tex, geo, material, animations=None, animate=None, particles=None, rc="controller.render.toa_simple",
           extra=None):
    d = {"identifier": ident, "materials": {"default": material}, "textures": {"default": "textures/entity/" + tex},
         "geometry": {"default": geo}, "render_controllers": rc if isinstance(rc, list) else [rc]}
    if particles:
        d["particle_effects"] = particles
    if animations:
        d["animations"] = animations
        d["scripts"] = {"animate": animate}
    if extra:
        for k, v in extra.items():
            if isinstance(v, dict) and isinstance(d.get(k), dict):
                d[k].update(v)
            else:
                d[k] = v
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": d}}


def rp_summon_anims():
    def emit(effect, every, loc="center", bones=None):
        a = {"loop": True, "animation_length": every, "particle_effects": {"0.00": [{"effect": effect, "locator": loc}]}}
        if bones:
            a["bones"] = bones
        return a
    return {
        "animation.toa.star_fx": emit("star", 0.05),
        "animation.toa.bread_fx": emit("trail", 0.1, bones={"roll": {"rotation": [0, 0, "q.life_time * 1440"]}}),
        "animation.toa.hole_fx": emit("hole", 0.15),
        "animation.toa.hole_core": emit("core", 0.25),
        "animation.toa.dragon_fx": emit("dragon", 0.05),
        "animation.toa.dragon_head": emit("head", 0.1),
    }


def rp_clients():
    boss_anims = xanims.short_names(sorted(SKILLS))
    window_rc = {"controller.render.toa_window": "q.skin_id >= 1"}
    window_extra = {"materials": {"window": "entity_alphablend"}, "textures": {"window": "textures/entity/toa_window"},
                    "geometry": {"window": "geometry.toa_window"}, "enable_attachables": True}
    clients = {
        "toa": client(ID, "toa", "geometry.toa", "entity_alphatest", boss_anims,
                      ["main", "aura_ctrl", "attack_fx", "window", "gold_eye"], xanims.PARTICLE_MAP,
                      rc=["controller.render.toa", window_rc],
                      extra=dict(window_extra, spawn_egg={"base_color": "#f4f4f8", "overlay_color": "#2a1840"})),
        # 分身: 見た目は本物と同じ（ただし左目は光らない）
        "clone": client("shinonome:clone", "toa", "geometry.toa", "entity_alphatest",
                        dict(boss_anims), ["main", "attack_fx", "window"], xanims.PARTICLE_MAP,
                        rc=["controller.render.toa_simple", window_rc], extra=window_extra),
        "star": client("shinonome:star", "toa_star_e", "geometry.toa_star", "entity_emissive_alpha",
                       {"fx": "animation.toa.star_fx", "spin": "animation.toa.star_spin"}, ["fx", "spin"],
                       {"star": "shinonome:star_trail"}, rc="controller.render.toa_star",
                       extra={"materials": {"shell": "entity_alphablend"}}),
        "bread": client("shinonome:bread", "toa_bread_e", "geometry.toa_bread", "entity_alphatest",
                        {"fx": "animation.toa.bread_fx"}, ["fx"], {"trail": "shinonome:spark"}),
        "hole": client("shinonome:hole", "toa_empty", "geometry.toa_empty", "entity_alphatest",
                       {"fx": "animation.toa.hole_fx", "core": "animation.toa.hole_core"}, ["fx", "core"],
                       {"hole": "shinonome:hole", "core": "shinonome:hole_core"}),
        "dragon": client("shinonome:dragon", "toa_empty", "geometry.toa_empty", "entity_alphatest",
                         {"fx": "animation.toa.dragon_fx", "head": "animation.toa.dragon_head"}, ["fx", "head"],
                         {"dragon": "shinonome:dragon", "head": "shinonome:dragon_head"}),
        "marker": client("shinonome:marker", "toa_empty", "geometry.toa_empty", "entity_alphatest"),
        "blast": client("shinonome:blast", "toa_empty", "geometry.toa_empty", "entity_alphatest"),
        "director": client("shinonome:director", "toa", "geometry.toa", "entity_alphatest",
                           {"pose": "animation.toa.director_pose"}, ["pose"], {"burger": "shinonome:burger"}),
    }
    for key in ('toa', 'clone'):   # 通常攻撃の切り替え用の変数
        smooth_client(clients[key]["minecraft:client_entity"]["description"])
    return clients


def lang():
    names = {ID: NAME, "shinonome:clone": NAME, "shinonome:star": "星弾", "shinonome:bread": "ドリルフランス",
             "shinonome:hole": "ブラックホール", "shinonome:dragon": "炎龍", "shinonome:marker": "目印",
             "shinonome:blast": "衝撃", "shinonome:director": NAME}
    lines = ["entity.%s.name=%s" % kv for kv in names.items()]
    lines += ["item.spawn_egg.entity.%s.name=%sのスポーンエッグ" % (ID, NAME), "pack.name=東雲 永々 ボス",
              "pack.description=宇宙から来た「東雲 永々」ボスアドオン", ""]
    return "\n".join(lines)


def placeholder_skin():
    """スキン画像が無いときの仮スキン（白髪・黒い目・白い肌・黒い服）"""
    im = xfx.Image.new("RGBA", (64, 64))
    d = xfx.ImageDraw.Draw(im)
    skin, hair, cloth, dark = (250, 240, 235, 255), (245, 245, 250, 255), (40, 38, 50, 255), (20, 18, 26, 255)
    d.rectangle([0, 0, 31, 15], fill=hair)
    d.rectangle([8, 8, 15, 15], fill=skin)            # 顔
    d.rectangle([8, 8, 15, 9], fill=hair)             # 前髪
    d.point((9, 12), fill=(10, 10, 10, 255)); d.point((10, 12), fill=(10, 10, 10, 255))
    d.point((13, 12), fill=(10, 10, 10, 255)); d.point((14, 12), fill=(240, 200, 60, 255))  # 片目は金色
    d.point((11, 14), fill=(230, 150, 150, 255)); d.point((12, 14), fill=(230, 150, 150, 255))
    d.rectangle([16, 16, 39, 31], fill=cloth)         # 胴
    d.rectangle([20, 20, 27, 21], fill=(240, 240, 245, 255))
    d.rectangle([40, 16, 53, 31], fill=cloth)         # 右腕（細腕）
    d.rectangle([44, 28, 50, 31], fill=skin)
    d.rectangle([0, 16, 15, 31], fill=dark)           # 右脚
    d.rectangle([16, 48, 31, 63], fill=dark)          # 左脚
    d.rectangle([32, 48, 45, 63], fill=cloth)         # 左腕（細腕）
    d.rectangle([36, 60, 42, 63], fill=skin)
    d.rectangle([32, 0, 63, 7], fill=(0, 0, 0, 0))
    d.rectangle([40, 8, 47, 9], fill=hair)            # 帽子レイヤー: 前髪
    d.rectangle([48, 8, 63, 15], fill=hair)           # 後ろ髪
    return im


def is_slim(path):
    im = xfx.Image.open(path).convert("RGBA")
    s = im.width // 64
    return all(im.getpixel((x * s, y * s))[3] == 0 for x in (54, 55) for y in (20, 25, 31))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skin", nargs="?")
    args = ap.parse_args()
    kept = os.path.join(RP, "textures/entity/toa.png")
    tmp = os.path.join(ROOT, ".skin_cache.png")
    if args.skin:
        shutil.copyfile(args.skin, tmp)
    elif os.path.exists(kept):
        shutil.copyfile(kept, tmp)
    else:
        placeholder_skin().save(tmp)
        print("スキン画像が指定されていないので、仮のスキンを使います")
    slim = is_slim(tmp)
    for d in (BP, RP, DIST):
        if os.path.isdir(d):
            shutil.rmtree(d)
    # BP
    write(os.path.join(BP, "manifest.json"), manifest("bp"))
    write(os.path.join(BP, "entities/toa.json"), bp_entity())
    sb, sa, sc = summons_bp()
    for name, data in sb.items():
        write(os.path.join(BP, "entities/%s.json" % name), data)
    anims_all = bp_animations()
    anims_all["animations"].update(sa)
    write(os.path.join(BP, "animations/toa.animation.json"), anims_all)
    ctrls = bp_controllers()
    ctrls["animation_controllers"].update(sc)
    write(os.path.join(BP, "animation_controllers/toa.ac.json"), ctrls)
    drop, equip = bp_loot()
    write(os.path.join(BP, "loot_tables/entities/toa.json"), drop)
    write(os.path.join(BP, "loot_tables/entities/toa_equipment.json"), equip)
    # RP
    write(os.path.join(RP, "manifest.json"), manifest("rp"))
    os.makedirs(os.path.join(RP, "textures/entity"), exist_ok=True)
    shutil.copyfile(tmp, kept)
    for name, im in xfx.entity_textures().items():
        im.save(os.path.join(RP, "textures/entity/%s.png" % name))
    for name, data in rp_clients().items():
        write(os.path.join(RP, "entity/%s.entity.json" % name), data)
    write(os.path.join(RP, "models/entity/toa.geo.json"), geo_boss(slim))
    write(os.path.join(RP, "models/entity/toa_window.geo.json"), geo_window())
    for ident, data in geo_files().items():
        write(os.path.join(RP, "models/entity/%s.geo.json" % ident.split(".")[1]), data)
    # 本体のモーションと、召喚物・撃破演出のモーションは別のファイルに分ける
    ra = xanims.all_animations()
    add_arc_trails(ra["animations"], {"trail"}, arc="arc")
    bake_smooth(ra["animations"], step=SMOOTH_STEP)
    summ = rp_summon_anims()
    summ["animation.toa.director_pose"] = ra["animations"].pop("animation.toa.director_pose")
    summ["animation.toa.star_spin"] = {"loop": True, "bones": {
        "orb": {"rotation": ["q.life_time * 400", "q.life_time * 650", 0]},
        "shell": {"scale": ["1 + math.sin(q.life_time * 1500) * 0.12"] * 3}}}
    vectorize_animations(ra["animations"])
    vectorize_animations(summ)
    write(os.path.join(RP, "animations/toa.animation.json"), ra)
    write(os.path.join(RP, "animations/toa_summons.animation.json"), {"format_version": "1.10.0", "animations": summ})
    write(os.path.join(RP, "animation_controllers/toa.ac.json"), xanims.controllers(sorted(SKILLS)))
    write(os.path.join(RP, "render_controllers/toa.rc.json"), render_controllers())
    for name, data in xfx.build_particles().items():
        write(os.path.join(RP, "particles/%s.json" % name), data)
    os.makedirs(os.path.join(RP, "textures/particle"), exist_ok=True)
    for name, im in xfx.build_textures().items():
        im.save(os.path.join(RP, "textures/particle/%s.png" % name))
    for name, data in xfx.build_fogs().items():
        write(os.path.join(RP, "fogs/%s.json" % name), data)
    im = xfx.Image.open(tmp).convert("RGBA")
    s = im.width // 64
    face = im.crop((8 * s, 8 * s, 16 * s, 16 * s)).resize((128, 128), xfx.Image.NEAREST)
    face.alpha_composite(im.crop((40 * s, 8 * s, 48 * s, 16 * s)).resize((128, 128), xfx.Image.NEAREST))
    for d in (BP, RP):
        for lc in ("ja_JP", "en_US"):
            write(os.path.join(d, "texts/%s.lang" % lc), lang())
        write(os.path.join(d, "texts/languages.json"), ["ja_JP", "en_US"])
        face.save(os.path.join(d, "pack_icon.png"))
    os.remove(tmp)
    # 声・足音・守りの反応・瀕死の演出
    brushup_files(BP, RP, dict(id=ID, ns="shinonome", prop="shinonome:react", react_events=["shinonome:splash"], evade_events=["shinonome:on_hit"], evade_skill=60,
             react_anim={"loop": True, "bones": {   # 混沌の体（水）: ぷるんと揺れる
                 "root": {"scale": ["1 + v.react * 0.18", "1 - v.react * 0.22", "1 + v.react * 0.18"]}}},
             prefix="animation.toa", main_ctrl="controller.animation.toa.main", glow="toa_glow", pitch=1.5))
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "ShinonomeToa_Boss.mcaddon")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for pack, arc in ((BP, "Shinonome_BP"), (RP, "Shinonome_RP")):
            for dp, _, fs in sorted(os.walk(pack)):
                for f in sorted(fs):
                    full = os.path.join(dp, f)
                    z.write(full, os.path.join(arc, os.path.relpath(full, pack)))
    print("built", out, "(細腕)" if slim else "(普通の腕)")


if __name__ == "__main__":
    main()
