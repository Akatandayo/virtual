# -*- coding: utf-8 -*-
"""ソフィア・ハート ボスアドオン生成スクリプト.

使い方: python3 sophia_boss/tools/generate.py [skin.png]
BP / RP を生成し、dist/ に .mcaddon を作ります（Pillow が必要）。
"""
import json
import math
import os
import random
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sanims  # noqa: E402
import sfx  # noqa: E402
from cine import Cine  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BP = os.path.join(ROOT, "Sophia_BP")
RP = os.path.join(ROOT, "Sophia_RP")
DIST = os.path.join(ROOT, "dist")

ID = "sophia:sophia_heart"
NAME = "ソフィア・ハート"
VERSION = [1, 0, 1]
MIN_ENGINE = [1, 21, 0]
UUID_BP_HEADER = "61396506-b3f5-4a1b-92f6-8e34dc87c6de"
UUID_BP_MODULE = "c8d8c5f1-e6b7-46bb-8808-2e50aa8d0842"
UUID_RP_HEADER = "502f1414-a2c9-49ee-8bdb-79966f922bb5"
UUID_RP_MODULE = "d8ae333b-f7d5-4efb-a2f8-0aaf05f49c02"

HP = 2400
ADAPT_HP = 1440      # 60%: 適応
UNIVERSE_HP = 720    # 30%: 内なる宇宙
REVIVE_HP = 150      # ほぼ倒れたとき: 再臨（一度だけ・HP 約50%で復活）
BARRIER_HITS = 6     # リフバリアΩ が受け止める回数
BARRIER_TIME = 8.0
OBJ = "sophia_barrier"
OBJ_PLAYERS = "sophia_players"

random.seed(1129)
BOSS = "@e[type=%s,c=1]" % ID
NEAREST = "@p[r=48,m=!creative]"
ANYONE = "@p[r=64]"
FACE = "^ ^1.5 ^"
CINE = Cine("sophia_cine")


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# コマンド用ヘルパー
# ---------------------------------------------------------------------------
def say(text):
    return '/tellraw @a[r=48] {"rawtext":[{"text":"%s"}]}' % text.replace('"', '\\"')


def act(text):
    """技名をアクションバーに出す（手数が多いので、チャットは大技だけ）"""
    return "/title @a[r=40] actionbar %s" % text


def p(r=24, rm=None):
    return "@a[r=%s%s,m=!creative]" % (r, ",rm=%s" % rm if rm is not None else "")


def pt(name, pos="~ ~ ~"):
    return "/particle sophia:%s %s" % (name, pos)


def at_players(r, name, pos="~ ~ ~"):
    return "/execute at %s run particle sophia:%s %s" % (p(r), name, pos)


def at_fam(fam, cmd):
    return "/execute at @e[family=%s] run %s" % (fam, cmd)


def shake(i, sec, r=24):
    return "/camerashake add @a[r=%d] %.2f %.2f positional" % (r, i, sec)


def sound(name, pitch=1.0, r=40, vol=1.0):
    return "/playsound %s @a[r=%d] ~ ~ ~ %.1f %.2f" % (name, r, vol, pitch)


def flash(r, g, b, rad=32, t=(0.05, 0.1, 0.2)):
    return "/camera @a[r=%d] fade time %.2f %.2f %.2f color %d %d %d" % (rad, t[0], t[1], t[2], r, g, b)


def marker(kind, pos="~ ~ ~", at=None):
    cmd = "summon sophia:marker %s sophia:as_%s" % (pos, kind)
    return "/execute at %s run %s" % (at, cmd) if at else "/" + cmd


def despawn(fam):
    return "/event entity @e[family=%s] sophia:despawn" % fam


def rnd_off(r):
    return "~%.1f ~ ~%.1f" % (random.uniform(-r, r), random.uniform(-r, r))


def ring_pts(radius, n, y=0.2, phase=0.0):
    for i in range(n):
        a = 2 * math.pi * i / n + phase
        yield "~%.2f ~%.2f ~%.2f" % (radius * math.cos(a), y, radius * math.sin(a))


def face_nearest():
    return "/tp @s ~ ~ ~ facing %s" % NEAREST


def line(cmd_fmt, dists, y=1.0):
    """自分の正面の直線上で cmd を実行"""
    return ["/execute at @s positioned ^ ^%.1f ^%.1f run %s" % (y, d, cmd_fmt) for d in dists]


def front_of_nearest(d=1.5):
    """一番近いプレイヤーの目の前（こちら側）へ瞬間移動"""
    return "/execute as %s at @s facing entity %s feet positioned ^ ^ ^%.1f run tp %s ~ ~ ~ facing @s" % (
        NEAREST, BOSS, d, BOSS)


SKILLS = {}


def skill(v, name, length, tl):
    SKILLS[v] = (name, length, {"%.2f" % k: c for k, c in sorted(tl.items())})


def add(tl, t, cmds):
    tl.setdefault(round(t, 2), []).extend(cmds)


# 弾幕（オーブ）: 向きと速さの組み合わせごとにイベントを作る
ORB_EVENTS = {}
ORB_SPEED = {"slow": (1, 0.25, 4.0, "pink"), "normal": (2, 0.5, 3.0, "gold"), "fast": (3, 0.9, 1.6, "blue")}


def orb(deg, speed="normal", mode="aim", pos="~ ~1.2 ~"):
    deg = int(round(deg)) % 360 if mode == "abs" else int(round(deg))
    name = "sophia:o_%s_%s_%s" % (mode, ("m%d" % -deg) if deg < 0 else deg, speed)
    ORB_EVENTS[name] = (mode, deg, speed)
    return "/summon sophia:orb %s %s" % (pos, name)


# ===========================================================================
# 技（第一形態から）
# ===========================================================================
PATH = [1.5 * k for k in range(1, 12)]

# 1 一閃: 予告線 → 相手を斬り抜けて背後へ
tl = {0: [act("§e◆ 一閃"), face_nearest()] + line("particle sophia:beam_warn ~ ~ ~", PATH, 0.3)}
add(tl, 0.3, line("damage @a[r=1.6,m=!creative] 12 entity_attack entity %s" % BOSS, PATH)
    + line("particle sophia:beam_gold ~ ~ ~", PATH, 1.1)
    + [pt("afterimage", "~ ~0.9 ~"),
       "/execute as %s at @s facing entity %s feet positioned ^ ^ ^-3 run tp %s ~ ~ ~ facing @s" % (NEAREST, BOSS, BOSS),
       sound("game.player.attack.strong", 1.2, 30), sound("item.trident.riptide_1", 1.6, 30, 0.6), shake(0.4, 0.2, 10)])
add(tl, 0.35, [pt("slash_gold", "~ ~1.2 ~"), pt("spark_burst", "~ ~1 ~")])
skill(1, "一閃", 1.0, tl)

# 2 三段蹴り: 目の前に詰めて三連蹴り（最後は打ち上げ）
tl = {0: [act("§e◆ 三段蹴り")], 0.1: [pt("afterimage", "~ ~0.9 ~"), front_of_nearest(1.5)]}
for i, (t, dmg) in enumerate(((0.35, 6), (0.6, 6), (0.95, 9))):
    cmds = ["/damage %s %d entity_attack entity @s" % (p(3), dmg), pt("spark_burst", "^ ^1 ^1.2"),
            pt("shockwave_gold", "^ ^1 ^1"), sound("game.player.attack.strong", 0.9 + i * 0.2, 30), shake(0.3, 0.15, 8)]
    if i == 2:
        cmds += ["/effect %s levitation 1 6 true" % p(3), pt("shockwave_white", "~ ~0.1 ~")]
    add(tl, t, cmds)
skill(2, "三段蹴り", 1.4, tl)

# 3 一閃連撃・改: 5 連撃
tl = {0: [act("§e◆ 一閃連撃・改"), front_of_nearest(1.8)]}
for i, t in enumerate((0.3, 0.6, 0.9, 1.2, 1.5)):
    add(tl, t, ["/damage %s 5 entity_attack entity @s" % p(3.2), pt("slash_gold" if i % 2 else "slash_blue", "^ ^1.2 ^1.3"),
                at_players(3.2, "spark_burst", "~ ~1 ~"), sound("game.player.attack.sweep", 0.9 + i * 0.1, 30)])
skill(3, "一閃連撃・改", 1.8, tl)

# 4 ガーラ: 周囲に電流を放つ（短いスタン）
tl = {0: [act("§b◆ ガーラ"), pt("charge_blue", "~ ~1 ~"), sound("mob.evocation_illager.prepare_attack", 1.6)],
      0.5: ["/damage %s 8 magic entity @s" % p(5), "/effect %s slowness 1 255 true" % p(5), pt("electric_ring"),
            pt("shockwave_blue", "~ ~0.1 ~"), at_players(5, "electric", "~ ~1 ~"), sound("random.fizz", 0.6, 30),
            sound("ambient.weather.thunder", 1.8, 30, 0.6), shake(0.4, 0.2, 10)]}
skill(4, "ガーラ", 1.2, tl)

# 5 ヴァルガーラ: 予兆の後、雷を 3 回落とす（麻痺）
tl = {0: [act("§b◆ ヴァルガーラ")]}
for k, t in enumerate((0.55, 1.05, 1.55)):
    fam = "volt_%d" % k
    add(tl, t - 0.45, [marker(fam, at=p(32)), sound("random.orb", 1.5, 30)])
    add(tl, t - 0.4, [at_fam(fam, "particle sophia:warn_blue ~ ~0.1 ~")])
    add(tl, t - 0.15, [at_fam(fam, "particle sophia:warn_blue ~ ~0.1 ~")])
    add(tl, t, [at_fam(fam, "particle sophia:thunder ~ ~ ~"), at_fam(fam, "particle sophia:electric ~ ~0.5 ~"),
                at_fam(fam, "damage @a[r=2,m=!creative] 10 magic entity %s" % BOSS),
                at_fam(fam, "effect @a[r=2,m=!creative] slowness 1 255 true"),
                at_fam(fam, "playsound ambient.weather.thunder @a[r=32] ~ ~ ~ 0.8 1.6"), despawn(fam)])
skill(5, "ヴァルガーラ", 2.0, tl)

# 6 ヴァーラ: 正面に突風（本物の爆風で吹き飛ばす）
tl = {0: [act("§f◆ ヴァーラ"), face_nearest()],
      0.4: ["/summon sophia:blast ^ ^1 ^1.2", "/damage %s 4 entity_attack entity @s" % p(5),
            pt("wind", "^ ^1 ^1.5"), pt("shockwave_white", "^ ^1 ^1"), sound("mob.enderdragon.flap", 1.2, 30)]}
skill(6, "ヴァーラ", 1.2, tl)

# 7 竜巻: 追いかけてくる竜巻を生む（巻き上げ + 落下）
tl = {0: [act("§f◆ 竜巻"), sound("elytra.loop", 0.6, 30, 0.6)],
      0.6: ["/summon sophia:tornado ^ ^ ^2.5", pt("dust", "^ ^ ^2.5")]}
skill(7, "竜巻", 1.0, tl)

# 8 岩槍: 地面を叩くと、プレイヤーに向かって岩の槍が走る
tl = {0: [act("§6◆ 土魔法・岩槍"), face_nearest()] + line("particle sophia:warn_gold ~ ~ ~", PATH[::2], 0.1)}
for k, d in enumerate(PATH):
    add(tl, 0.35 + 0.06 * k, ["/execute at @s positioned ^ ^ ^%.1f run particle sophia:earth_spike ~ ~ ~" % d,
                              "/execute at @s positioned ^ ^ ^%.1f run particle sophia:dust ~ ~ ~" % d,
                              "/execute at @s positioned ^ ^ ^%.1f run damage @a[r=1.6,m=!creative] 9 entity_attack "
                              "entity @s" % d,
                              "/execute at @s positioned ^ ^ ^%.1f run effect @a[r=1.6,m=!creative] levitation 1 3 true" % d]
        + ([sound("dig.stone", 0.6, 30)] if k % 3 == 0 else []))
skill(8, "岩槍", 1.6, tl)

# 9 通常弾幕: 全方位の輪を 3 回（向きをずらして）
tl = {0: [act("§e◆ 通常弾幕")]}
for i, (t, n, spd) in enumerate(((0.3, 12, "normal"), (0.8, 12, "normal"), (1.2, 16, "slow"))):
    add(tl, t, [orb(360 / n * k + i * 15, spd, "abs") for k in range(n)]
        + [pt("magic_circle", "~ ~0.1 ~"), sound("random.orb", 0.8 + i * 0.3, 30)])
skill(9, "通常弾幕", 1.6, tl)

# 10 高速弾幕: 狙い撃ちの扇形 × 3
tl = {0: [act("§b◆ 高速弾幕")]}
for i, t in enumerate((0.3, 0.6, 0.9)):
    add(tl, t, [orb(a + (i - 1) * 4, "fast") for a in (-20, -10, 0, 10, 20)] + [sound("random.bow", 1.6, 30)])
skill(10, "高速弾幕", 1.4, tl)

# 11 神滅: 予告線つきの狙撃 × 3
tl = {0: [act("§c◆ 神滅")]}
for k, t in enumerate((0.5, 1.0, 1.5)):
    fam = "aim_%d" % k
    ln = "/execute at @s anchored eyes facing entity @e[family=%s,c=1] feet positioned ^ ^ ^%.1f run %s"
    add(tl, t - 0.4, [marker(fam, "~ ~1 ~", at=NEAREST)])
    for dt in (0.35, 0.2, 0.05):
        add(tl, t - dt, [ln % (fam, d, "particle sophia:beam_warn ~ ~ ~") for d in range(2, 32, 3)])
    add(tl, t, [ln % (fam, d * 1.5, "damage @a[r=1.5,m=!creative] 10 entity_attack entity %s" % BOSS)
                for d in range(1, 21)]
        + [ln % (fam, d * 1.5, "particle sophia:beam_gold ~ ~ ~") for d in range(1, 21)]
        + [sound("random.explode", 2.0, 40, 0.5), sound("fireworks.blast", 0.8, 40), despawn(fam)])
skill(11, "神滅", 2.0, tl)

# 12 投擲「退勤届け」: 当たると強制退勤（吹き飛ばし）
tl = {0: [act("§f◆ 投擲「退勤届け」")], 0.35: ["/summon sophia:letter ^ ^1.4 ^0.8", sound("random.bow", 1.4, 30)]}
skill(12, "退勤届け", 1.0, tl)

# 13 フランスパン: ポコッ（ダメージは小さいが大きく吹き飛ぶ）
tl = {0: [act("§6◆ フランスパン")], 0.15: [front_of_nearest(1.6)],
      0.45: ["/damage %s 4 entity_attack entity @s" % p(3), "/summon sophia:blast ^ ^1 ^0.6", pt("bread", "^ ^1.3 ^1"),
             "/title %s actionbar §6フランスパンで殴られた！" % p(4), sound("random.pop", 0.6, 30)]}
skill(13, "フランスパン", 0.9, tl)

# 14 リフバリアΩ: 6 回まで攻撃を受け止める障壁（8 秒）
tl = {0: [act("§e◆ リフバリアΩ §7（%d回まで攻撃を防ぐ）" % BARRIER_HITS), pt("hex_barrier", "~ ~1 ~"),
          sound("beacon.activate", 1.6, 30)]}
skill(14, "リフバリアΩ", 1.0, tl)

# 15 次元斬: 空間の裂け目が現れ、少し遅れて斬れる
tl = {0: [act("§5◆ 次元斬")]}
add(tl, 0.1, [marker("rift", at=p(32))] + [marker("rift", rnd_off(3), at=p(32)) for _ in range(2)])
for dt in (0.15, 0.45, 0.75):
    add(tl, dt, [at_fam("rift", "particle sophia:rift ~ ~1.2 ~"), at_fam("rift", "particle sophia:warn_purple ~ ~0.1 ~")])
add(tl, 0.95, [at_fam("rift", "damage @a[r=2.2,m=!creative] 11 entity_attack entity %s" % BOSS),
               at_fam("rift", "particle sophia:big_slash_purple ~ ~1.2 ~"), at_fam("rift", "particle sophia:spark_burst ~ ~1 ~"),
               sound("item.trident.hit", 0.6, 40), shake(0.4, 0.2, 24), despawn("rift")])
skill(15, "次元斬", 1.8, tl)

# 16 宇宙CQC: 掴んで、叩きつけて、投げる
tl = {0: [act("§e◆ 宇宙CQC")],
      0.2: ["/execute as @p[r=6,m=!creative] run tp @s ^ ^ ^1.3", sound("armor.equip_leather", 0.6, 20)],
      0.7: ["/damage %s 10 entity_attack entity @s" % p(2.5), "/effect %s slowness 1 4 true" % p(2.5),
            pt("shockwave_gold", "~ ~0.1 ~"), pt("dust", "^ ^ ^1"), sound("random.anvil_land", 0.6, 30), shake(0.5, 0.2, 8)],
      1.05: ["/summon sophia:blast ^ ^1 ^0.4", "/effect %s levitation 1 4 true" % p(3), pt("spark_burst", "^ ^1 ^1")]}
skill(16, "宇宙CQC", 1.5, tl)

# 17 芸術：宇宙猫: 困惑させ、向きをくるっと反対にする
tl = {0: [act("§d◆ 芸術：宇宙猫"), pt("cat", "~ ~1.5 ~"), sound("mob.cat.meow", 1.0, 30)],
      0.6: ["/effect %s nausea 6 0 true" % p(16), "/execute as %s at @s run tp @s ~ ~ ~ ~180 ~" % p(16),
            "/damage %s 4 magic entity @s" % p(16), at_players(16, "cat", "~ ~1.5 ~"),
            "/title %s actionbar §d……？　（宇宙猫の顔）" % p(16), sound("mob.cat.purreow", 1.0, 30)]}
skill(17, "宇宙猫", 1.5, tl)

# 18 目を合わせる: 目が合った者は動けなくなる（目を逸らせば避けられる）
GAZE = "sophia_gazed"
tl = {0: [act("§c§l◆ 目を合わせる §r§c―― 目を逸らせ！"), "/tag @a remove %s" % GAZE, pt("eye_big", "~ ~3 ~"),
          sound("mob.evocation_illager.prepare_summon", 0.5, 30)],
      0.8: [pt("eye_big", "~ ~3 ~"), sound("note.bass", 0.5, 30)]}
add(tl, 1.5, ["/execute as %s at @s anchored eyes positioned ^ ^ ^%d positioned ~ ~-1.2 ~ if entity @e[type=%s,r=%.1f] "
              "run tag @s add %s" % (p(24), k, ID, 1.2 + k * 0.18, GAZE) for k in range(2, 24, 2)]
    + ["/effect @a[tag=%s] slowness 2 255 true" % GAZE, "/effect @a[tag=%s] darkness 3 0 true" % GAZE,
       "/damage @a[tag=%s] 12 magic entity @s" % GAZE, "/execute at @a[tag=%s] run particle sophia:eye_big ~ ~2.5 ~" % GAZE,
       "/title @a[tag=%s] actionbar §c目が合った……" % GAZE, sound("mob.warden.sonic_charge", 1.6, 30),
       "/tag @a remove %s" % GAZE])
skill(18, "目を合わせる", 2.2, tl)

# ===========================================================================
# 技（適応 = HP60% から）
# ===========================================================================
# 19 ヴァルドガーラ: 黒い雷（範囲大・予兆長め）
tl = {0: [act("§5§l◆ ヴァルドガーラ"), marker("black", at=NEAREST), sound("ambient.weather.thunder", 0.5, 48)]}
for dt in (0.1, 0.4, 0.7, 1.0, 1.2):
    add(tl, dt, [at_fam("black", "particle sophia:warn_purple ~ ~0.1 ~")] +
        ["/execute at @e[family=black] run particle sophia:warn_black %s" % q for q in ring_pts(3, 6, 0.1)])
add(tl, 1.45, [at_fam("black", "particle sophia:thunder_black ~ ~ ~"), at_fam("black", "particle sophia:shockwave_big_purple ~ ~0.1 ~"),
               at_fam("black", "damage @a[r=4.5,m=!creative] 20 magic entity %s" % BOSS),
               at_fam("black", "effect @a[r=4.5,m=!creative] slowness 2 255 true"),
               at_fam("black", "playsound ambient.weather.thunder @a[r=48] ~ ~ ~ 1 0.5"), shake(1.2, 0.5, 32),
               flash(60, 0, 90, 24, (0, 0.05, 0.2)), despawn("black")])
skill(19, "ヴァルドガーラ", 2.2, tl)

# 21 抜刀隊（ソードファンネル）: 6 本の刀が浮かび、順に追いかけてくる
tl = {0: [act("§b◆ 抜刀隊（ソードファンネル）"), sound("random.anvil_use", 1.6, 30)]}
for i, (x, y, z) in enumerate([(-1.8, 2.2, 0), (1.8, 2.2, 0), (-1.2, 3.0, -0.6), (1.2, 3.0, -0.6), (-0.6, 3.6, -1),
                               (0.6, 3.6, -1)]):
    add(tl, 0.3 + i * 0.1, ["/summon sophia:funnel ^%.1f ^%.1f ^%.1f" % (x, y, z), pt("spark_burst", "^%.1f ^%.1f ^%.1f" % (x, y, z)),
                            sound("random.anvil_use", 1.4 + i * 0.1, 30, 0.5)])
skill(21, "抜刀隊", 1.4, tl)

# 22 低速弾幕: 三重螺旋
tl = {0: [act("§d◆ 低速弾幕"), "/effect @s slowness 3 255 true"]}
for i in range(14):
    a = i * 17
    add(tl, 0.3 + i * 0.15, [orb(a + k * 120, "slow", "abs") for k in range(3)] + ([sound("random.orb", 1.2, 30, 0.6)] if i % 2 == 0 else []))
skill(22, "低速弾幕", 3.0, tl)

# 23 魔力砲: カットイン → 溜め → 120° の薙ぎ払いレーザー
tl = {}
CINE.cutin(tl, 0.0, 0.7, "^1 ^1.4 ^1.8", "^ ^1.3 ^1", "§e§l魔力砲", "§7――込めた魔力のぶんだけ")
add(tl, 0, [face_nearest(), "/effect @s slowness 4 255 true", sound("beacon.power", 1.4, 40)])
for i in range(4):
    add(tl, 0.8 + i * 0.2, [pt("charge_gold", "^ ^1.3 ^1"), sound("note.pling", 0.6 + i * 0.2, 40)])
add(tl, 1.55, ["/tp @s ~ ~ ~ ~-60 ~", act("§c§l◆ 魔力砲 §r§c―― 後ろか、遠くへ！")])
for s in range(14):
    add(tl, 1.65 + s * 0.1, (["/tp @s ~ ~ ~ ~9 ~"] if s else [])
        + line("damage @a[r=1.6,m=!creative] 9 magic entity %s" % BOSS, range(2, 24, 2), 1.3)
        + line("particle sophia:beam_gold ~ ~ ~", range(2, 24, 2), 1.3) + [sound("beacon.ambient", 1.8, 40, 0.5)])
add(tl, 3.1, [face_nearest(), shake(0.5, 0.2, 24)])
skill(23, "魔力砲", 3.2, tl)

# 24 不可逆「entropy」: ブラックホール（吸い込み → 収縮して爆発）
tl = {0: [act("§5◆ 不可逆「entropy」 §7―― 走って離れろ！")], 0.4: ["/execute at %s run summon sophia:blackhole ~ ~0.5 ~" % NEAREST,
                                                           sound("mob.warden.sonic_charge", 0.6, 40)]}
skill(24, "entropy", 1.0, tl)

# 25 自動回復システム: 回復する機体を 3 つ呼ぶ（壊せる）
tl = {0: [act("§a◆ 自動回復システム §7―― 浮いている機体を壊せ！")],
      0.35: ["/summon sophia:drone ^2 ^1.6 ^0.5", "/summon sophia:drone ^-2 ^1.6 ^0.5", "/summon sophia:drone ^ ^1.6 ^-2",
             pt("heal", "~ ~1 ~"), sound("beacon.activate", 1.8, 30)]}
skill(25, "自動回復システム", 1.2, tl)

# 26 影分身・改: 一度殴られると消える分身を 3 体
tl = {0: [act("§7◆ 影分身・改")],
      0.35: ["/summon sophia:clone ^2 ^ ^", "/summon sophia:clone ^-2 ^ ^", "/summon sophia:clone ^ ^ ^-2",
             pt("afterimage", "^2 ^0.9 ^"), pt("afterimage", "^-2 ^0.9 ^"), pt("afterimage", "^ ^0.9 ^-2"),
             sound("mob.endermen.portal", 1.4, 30)]}
skill(26, "影分身・改", 1.2, tl)

# 27 戦争（砲撃支援）: 無線で要請 → 予兆の位置に砲弾が降る（3 波）
tl = {0: [act("§c◆ 戦争（砲撃支援）"), say("§eソフィア§7「こちらソフィア。座標送るね、全部撃って」"),
          sound("random.click", 0.6, 30)]}
for w, t0 in enumerate((0.8, 1.4, 2.0)):
    fam = "shell_%d" % w
    add(tl, t0, [marker(fam, at=p(40))] + [marker(fam, rnd_off(5), at=p(40)) for _ in range(3)]
        + [sound("random.fuse", 1.6, 40, 0.6)])
    add(tl, t0 + 0.05, [at_fam(fam, "particle sophia:warn_red ~ ~0.1 ~")])
    add(tl, t0 + 0.3, [at_fam(fam, "particle sophia:shell_fall ~ ~ ~"), at_fam(fam, "particle sophia:warn_red ~ ~0.1 ~")])
    add(tl, t0 + 0.85, [at_fam(fam, "summon sophia:blast ~ ~0.3 ~"), at_fam(fam, "particle sophia:dust ~ ~ ~"),
                        shake(0.5, 0.3, 40), despawn(fam)])
skill(27, "砲撃支援", 3.0, tl)

# 28 次元斬・紅: カットイン → 大きな紅の裂け目
tl = {}
CINE.cutin(tl, 0.0, 0.6, "^0.9 ^1.3 ^1.5", "^ ^1.2 ^0.3", "§4§l次元斬・紅")
add(tl, 0.65, [marker("rift_red", at=p(32))] + [marker("rift_red", rnd_off(4), at=p(32)) for _ in range(3)]
    + [sound("mob.warden.sonic_charge", 1.2, 40)])
for dt in (0.7, 1.0, 1.3):
    add(tl, dt, [at_fam("rift_red", "particle sophia:rift_big ~ ~1.3 ~"), at_fam("rift_red", "particle sophia:warn_red ~ ~0.1 ~")])
add(tl, 1.6, [at_fam("rift_red", "damage @a[r=3,m=!creative] 16 entity_attack entity %s" % BOSS),
              at_fam("rift_red", "particle sophia:big_slash_red ~ ~1.2 ~"), at_fam("rift_red", "particle sophia:shockwave_red ~ ~0.1 ~"),
              flash(255, 30, 40, 32, (0, 0.05, 0.2)), sound("random.anvil_land", 0.5, 40), shake(0.9, 0.4, 32),
              despawn("rift_red")])
skill(28, "次元斬・紅", 2.4, tl)

# 29 天道・大審判: 光の柱が降り注ぐ（4 波）
tl = {0: [act("§e§l◆ 天道・大審判"), sound("beacon.power", 0.8, 48)]}
for w, t0 in enumerate((0.3, 0.8, 1.3, 1.8)):
    fam = "pillar_%d" % (w % 2)
    add(tl, t0, [marker(fam, at=p(40))] + [marker(fam, rnd_off(6), at=p(40)) for _ in range(3)])
    add(tl, t0 + 0.05, [at_fam(fam, "particle sophia:warn_gold ~ ~0.1 ~")])
    add(tl, t0 + 0.35, [at_fam(fam, "particle sophia:warn_gold ~ ~0.1 ~")])
    add(tl, t0 + 0.65, [at_fam(fam, "particle sophia:light_pillar ~ ~ ~"),
                        at_fam(fam, "damage @a[r=1.8,m=!creative] 11 magic entity %s" % BOSS),
                        at_fam(fam, "playsound beacon.deactivate @a[r=24] ~ ~ ~ 0.8 1.8"), despawn(fam)])
skill(29, "天道・大審判", 3.0, tl)

# ===========================================================================
# 技（再臨後・神核融解）
# ===========================================================================
# 40 一閃神速: カットイン → 一閃 × 5
tl = {}
CINE.cutin(tl, 0.0, 0.7, "^0.4 ^1.5 ^1.1", FACE, "§e§l一閃神速")
for k, t in enumerate((0.9, 1.25, 1.6, 1.95, 2.3)):
    add(tl, t - 0.12, ["/execute at %s rotated %d 0 positioned ^ ^ ^-6 run tp @s ~ ~ ~ facing %s" % (NEAREST, k * 151 % 360, NEAREST),
                       pt("afterimage", "~ ~0.9 ~")] + line("particle sophia:beam_warn ~ ~ ~", PATH[:8], 0.3))
    add(tl, t, line("damage @a[r=1.6,m=!creative] 10 entity_attack entity %s" % BOSS, PATH[:8])
        + line("particle sophia:beam_gold ~ ~ ~", PATH[:8], 1.1) + ["/tp @s ^ ^ ^12", sound("game.player.attack.strong", 1.2, 30),
                                                                    shake(0.3, 0.15, 12)])
add(tl, 2.6, [sound("random.anvil_land", 2.0, 40), pt("spark_burst", "~ ~1 ~")])
skill(40, "一閃神速", 2.8, tl)

# 41 クロノスピア: 時を止め、光の槍で囲んで貫く
TS = "sophia_stopped"
tl = {0: ["/tag @a remove %s" % TS]}
CINE.cutin(tl, 0.0, 0.6, "^0.6 ^1.4 ^1.2", "^-0.2 ^1.5 ^0.4", "§b§lクロノスピア", "§7――止まれ")
add(tl, 0.6, ["/tag %s add %s" % (p(24), TS), "/effect @a[tag=%s] slowness 3 255 true" % TS,
              "/effect @a[tag=%s] mining_fatigue 3 4 true" % TS, pt("clock", "~ ~0.1 ~"),
              "/execute at @a[tag=%s] run particle sophia:clock ~ ~0.1 ~" % TS, sound("random.anvil_use", 0.4, 40),
              flash(200, 210, 255, 24, (0, 0.05, 0.3))])
for i in range(3):
    add(tl, 0.9 + i * 0.4, ["/execute at @a[tag=%s] run particle sophia:spear_ring ~ ~ ~" % TS,
                            sound("random.anvil_use", 1.4 + i * 0.2, 30, 0.5)])
add(tl, 2.2, ["/damage @a[tag=%s] 18 entity_attack entity @s" % TS, "/execute at @a[tag=%s] run particle sophia:spark_burst ~ ~1 ~" % TS,
              "/execute at @a[tag=%s] run particle sophia:shockwave_blue ~ ~0.1 ~" % TS, sound("item.trident.hit", 0.8, 40),
              shake(0.8, 0.3, 24), "/tag @a remove %s" % TS])
skill(41, "クロノスピア", 3.2, tl)

# ===========================================================================
# カットシーン
# ===========================================================================
# 34 おすわり（東雲 永々のアドオンを一緒に入れたときだけ）: 東雲に「おすわり」と言われると土下座してしまう
tl = {0: [say("§eソフィア§7「ぎゃっ！？」"), "/effect @s slowness 3 255 true", pt("shockwave_white", "~ ~0.1 ~"),
          sound("random.anvil_land", 1.4, 30), shake(0.3, 0.2, 12)],
      1.6: [say("§eソフィア§7「……東雲、あとで覚えてなさい」")]}
skill(34, "おすわり", 3.0, tl)

# 30 登場: 光の柱の中を舞い降りる
tl = {}
add(tl, 0, CINE.begin(4.6) + [face_nearest().replace(NEAREST, ANYONE), CINE.cam("^ ^1.5 ^6", "^ ^5 ^"),
                              CINE.fade(0, 0.2, 0.8, (255, 250, 220)), pt("light_pillar_huge"), sound("beacon.power", 1.2, 64),
                              "/scoreboard objectives add %s dummy" % OBJ, "/scoreboard objectives add %s dummy" % OBJ_PLAYERS])
add(tl, 0.1, [CINE.cam("^1 ^2 ^4", "^ ^1.5 ^", 2.3, "in_out_cubic")])
add(tl, 2.6, [pt("shockwave_gold", "~ ~0.1 ~"), pt("magic_circle"), sound("random.levelup", 1.4, 64), shake(0.3, 0.2, 16)])
add(tl, 3.0, [CINE.cam("^0.3 ^1.52 ^1.0", FACE), "/title @a[r=64] title §eソフィア・ハート",
              "/title @a[r=64] subtitle §7――多分、神様"])
add(tl, 3.4, [say("§eソフィア§7「……ふふ。お客さん？　いいよ、遊んであげる」")])
add(tl, 3.9, [CINE.cam("^ ^2 ^6", FACE, 0.5, "out_expo")])
add(tl, 4.5, [CINE.fade(0, 0.05, 0.3, (255, 250, 220))] + CINE.end())
skill(30, "登場", 4.6, tl)

# 31 適応（HP60%）
tl = {}
add(tl, 0, CINE.begin(4.6) + [face_nearest().replace(NEAREST, ANYONE), CINE.cam("^2 ^1.2 ^2.5", FACE),
                              CINE.fade(0, 0.1, 0.3, (255, 240, 180)), sound("beacon.deactivate", 0.6, 64)])
add(tl, 0.3, [say("§eソフィア§7「……なるほどね」")])
add(tl, 1.6, [CINE.cam("^0.25 ^1.5 ^0.9", FACE), pt("eye_big", "~ ~3 ~"), sound("mob.evocation_illager.cast_spell", 1.2, 64)])
add(tl, 1.8, [pt("magic_circle_big", "~ ~0.1 ~"), pt("electric_ring"), "/summon sophia:blast ~ ~0.5 ~",
              "/title @a[r=64] title §b§l適応", "/title @a[r=64] subtitle §7――もう、効かないよ",
              CINE.cam("^ ^7 ^5", "^ ^1 ^", 1.8, "in_out_sine"), sound("ambient.weather.thunder", 1.2, 64), shake(1.0, 0.5, 32)])
add(tl, 3.6, [say("§eソフィア§7「もう『適応』したよ。次は、こっちの番」")])
add(tl, 4.4, [CINE.fade(0, 0.05, 0.3, (120, 200, 255))] + CINE.end())
skill(31, "適応", 4.6, tl)

# 32 内なる宇宙（HP30%）: 宇宙を広げ、鎖で縛り、最後に収束させる
tl = {}
add(tl, 0, CINE.begin(5.5) + [face_nearest().replace(NEAREST, ANYONE), "/fog @a[r=64] push sophia:universe sophia_universe",
                              CINE.cam("^0.8 ^1.3 ^1.6", "^-0.3 ^2.3 ^0.4"), CINE.fade(0, 0.3, 1.0),
                              "/title @a[r=64] title §5§l内なる宇宙", "/title @a[r=64] subtitle §7――無限無窮を、ここに",
                              pt("stars"), sound("mob.wither.spawn", 1.6, 64), sound("beacon.power", 0.5, 64)])
add(tl, 1.2, [CINE.cam("^4 ^0.5 ^6", "^ ^2 ^"), pt("galaxy"), pt("magic_circle_big", "~ ~0.1 ~"), at_players(48, "chain", "~ ~ ~")])
add(tl, 2.6, [CINE.cam("^ ^12 ^8", "^ ^1 ^", 1.4, "in_out_sine"), pt("stars"), at_players(48, "chain", "~ ~ ~")])
add(tl, 4.0, [CINE.cam("^0.3 ^1.9 ^1.0", "^ ^1.9 ^"), say("§eソフィア§7「ここでは……因果さえ、鎖に囚われる」")])
add(tl, 5.2, [CINE.fade(0, 0.05, 0.3, (120, 60, 200))] + CINE.end()
    + ["/effect %s slowness 5 1 true" % p(48), "/title @a[r=64] actionbar §d§l鎖に縛られている……！ 14マスの外へ逃げろ！",
       pt("stars"), pt("galaxy")])
for i, t in enumerate((5.6, 6.6, 7.6, 8.6)):
    add(tl, t, ["/damage %s 3 magic entity @s" % p(48), at_players(48, "chain", "~ ~ ~"), sound("random.chestclosed", 0.5, 48)]
        + ([pt("stars")] if i % 2 else []))
add(tl, 9.0, [pt("charge_purple", "~ ~1.5 ~")] + [pt("warn_purple", q) for q in ring_pts(14, 18, 0.1)])
add(tl, 9.4, [pt("warn_purple", q) for q in ring_pts(14, 18, 0.1)])
add(tl, 9.8, ["/damage %s 24 magic entity @s" % p(14), "/summon sophia:blast ~ ~0.5 ~ sophia:big",
              pt("shockwave_big_purple", "~ ~0.1 ~"), pt("galaxy"), pt("big_slash_purple", "~ ~1.5 ~"),
              flash(150, 60, 255, 48, (0, 0.1, 0.5)), shake(2.0, 0.8, 48), sound("random.explode", 0.6, 64)])
add(tl, 10.6, ["/fog @a[r=64] remove sophia_universe", say("§eソフィア§7「……ふふ。まだ立ってる？」")])
skill(32, "内なる宇宙", 11.0, tl)

# 33 再臨（ほぼ倒れたとき・一度だけ）: 光の柱の中で立ち上がり、HP 約50%で復活
tl = {}
add(tl, 0, CINE.begin(6) + [face_nearest().replace(NEAREST, ANYONE), CINE.cam("^1.6 ^0.6 ^1.6", "^ ^0.6 ^"),
                            CINE.fade(0, 0.3, 0.8), sound("beacon.deactivate", 0.5, 64)])
add(tl, 1.0, [say("§eソフィア§7「……あれ。わたし、負けちゃう……？」")])
add(tl, 2.2, [CINE.cam("^ ^14 ^4", "^ ^ ^"), pt("light_pillar_huge"), sound("beacon.power", 1.0, 64),
              "/effect @s instant_health 1 7 true", "/effect @s regeneration 12 4 true"])
add(tl, 2.5, ["/effect @s instant_health 1 7 true"])
add(tl, 3.0, [CINE.cam("^0.4 ^1.6 ^1.4", "^ ^1.6 ^"), "/title @a[r=64] title §e§l再臨",
              "/title @a[r=64] subtitle §7――神核融解", say("§eソフィア§7「――なんてね。まだ、終わらせないよ」")])
add(tl, 4.5, ["/summon sophia:blast ~ ~0.5 ~ sophia:big", pt("shockwave_big_gold", "~ ~0.1 ~"), pt("magic_circle_big", "~ ~0.1 ~"),
              CINE.cam("^ ^4 ^7", "^ ^1.5 ^", 1.0, "out_expo"), flash(255, 220, 120, 48, (0, 0.05, 0.4)), shake(1.5, 0.6, 48),
              sound("random.totem", 1.0, 64)])
add(tl, 5.8, CINE.end())
skill(33, "再臨", 6.0, tl)

CINE_V = [30, 31, 32, 33]

# 撃破カットシーン（監督役の見えないエンティティが再生する）
DEATH = {}
add(DEATH, 0, CINE.begin(6) + [CINE.cam("~2.5 ~1.2 ~2.5", "~ ~0.8 ~"), CINE.fade(0, 0.3, 1.0, (255, 250, 220)),
                              pt("sparkle", "~ ~0.5 ~"), "/playsound random.totem @a[r=64] ~ ~ ~ 1 1.4"])
add(DEATH, 0.1, [CINE.cam("~-2.5 ~1.4 ~2.5", "~ ~0.8 ~", 1.8, "linear")])
add(DEATH, 0.9, [say("§eソフィア§7「……ふふ。楽しかった」")])
add(DEATH, 1.9, [CINE.cam("~-2.5 ~1.8 ~-2.5", "~ ~0.8 ~", 1.8, "linear"), pt("cat", "~ ~1 ~")])
add(DEATH, 2.9, [say("§eソフィア§7「……猫たちのところ、帰らなきゃ。また、遊ぼうね」")])
add(DEATH, 3.7, [CINE.cam("~ ~7 ~-1", "~ ~0.5 ~", 1.3, "in_out_sine")])
add(DEATH, 4.6, [pt("sparkle", "~ ~0.5 ~"), pt("afterimage", "~ ~0.5 ~"), pt("light_pillar")])
add(DEATH, 5.3, [CINE.fade(0, 0.1, 0.6, (255, 250, 220))] + CINE.end())
add(DEATH, 5.5, ["@s sophia:despawn"])
DEATH = {"%.2f" % k: v for k, v in sorted(DEATH.items())}


# ---------------------------------------------------------------------------
# Behavior Pack: 本体
# ---------------------------------------------------------------------------
def manifest(kind):
    if kind == "bp":
        return {"format_version": 2,
                "header": {"name": "ソフィア・ハート ボス BP", "description": "ボス「ソフィア・ハート」を追加します",
                           "uuid": UUID_BP_HEADER, "version": VERSION, "min_engine_version": MIN_ENGINE},
                "modules": [{"type": "data", "uuid": UUID_BP_MODULE, "version": VERSION}],
                "dependencies": [{"uuid": UUID_RP_HEADER, "version": VERSION}]}
    return {"format_version": 2,
            "header": {"name": "ソフィア・ハート ボス RP", "description": "ボス「ソフィア・ハート」を追加します",
                       "uuid": UUID_RP_HEADER, "version": VERSION, "min_engine_version": MIN_ENGINE},
            "modules": [{"type": "resources", "uuid": UUID_RP_MODULE, "version": VERSION}]}


def phase_group(skin, speed, dmg, timer):
    return {"minecraft:skin_id": {"value": skin}, "minecraft:movement": {"value": speed},
            "minecraft:attack": {"damage": dmg},
            "minecraft:timer": {"looping": True, "time": timer, "randomInterval": True,
                                "time_down_event": {"event": "sophia:choose_skill", "target": "self"}}}


SENSORS = ["sensor_normal", "barrier", "barrier_cd", "cine_guard"]
IMMUNE = ("fall", "fire", "fire_tick", "lava", "lightning", "drowning", "suffocation", "magic", "entity_explosion",
          "block_explosion")
FOE = {"any_of": [{"test": "is_family", "subject": "other", "value": "player"},
                  {"test": "is_family", "subject": "other", "value": "byakuya"},
                  {"test": "is_family", "subject": "other", "value": "hitori"}]}


def bp_entity():
    all_off = {"minecraft:damage_sensor": {"triggers": [{"cause": "all", "deal_damage": False}]}}
    normal = [{"cause": "entity_attack", "damage_multiplier": 0.9,
               "on_damage": {"filters": FOE, "event": "sophia:on_hit"}},
              {"cause": "projectile", "damage_multiplier": 0.7}] + [{"cause": c, "deal_damage": False} for c in IMMUNE]
    groups = {
        "phase_1": phase_group(0, 0.36, 12, [1.6, 2.8]),
        "phase_2": phase_group(1, 0.40, 15, [1.3, 2.4]),
        "phase_3": phase_group(2, 0.44, 18, [1.1, 2.0]),
        "phase_4": phase_group(3, 0.48, 22, [0.9, 1.7]),
        "sensor_normal": {"minecraft:damage_sensor": {"triggers": normal}},
        # リフバリアΩ: 攻撃を受け止めて数える（is_charged = バリアの時間を測る目印）
        "barrier": {"minecraft:is_charged": {}, "minecraft:damage_sensor": {"triggers": [
            {"on_damage": {"filters": FOE, "event": "sophia:barrier_hit"}, "deal_damage": False},
            {"cause": "projectile", "on_damage": {"event": "sophia:barrier_hit"}, "deal_damage": False},
            {"cause": "all", "deal_damage": False}]}},
        "barrier_cd": dict(all_off, **{"minecraft:is_charged": {}, "minecraft:is_sheared": {}}),
        "cine_guard": dict(all_off),
        "ai": {
            "minecraft:behavior.float": {"priority": 0},
            "minecraft:behavior.melee_attack": {"priority": 2, "speed_multiplier": 1.35, "track_target": True},
            "minecraft:behavior.hurt_by_target": {"priority": 1},
            "minecraft:behavior.nearest_attackable_target": {
                "priority": 2, "must_see": False, "reselect_targets": True, "within_radius": 48,
                "entity_types": [{"filters": {"test": "is_family", "subject": "other", "value": "player"},
                                  "max_dist": 48}]},
            "minecraft:behavior.random_stroll": {"priority": 6, "speed_multiplier": 0.8},
            "minecraft:behavior.look_at_player": {"priority": 7, "look_distance": 16},
        },
    }
    variants = [0] + sorted(SKILLS)
    for v in variants:
        groups["v_%d" % v] = {"minecraft:mark_variant": {"value": v}}
    all_v = ["v_%d" % v for v in variants]

    def set_variant(v, add_=None, remove_=None):
        return {"remove": {"component_groups": [g for g in all_v if g != "v_%d" % v] + (remove_ or [])},
                "add": {"component_groups": ["v_%d" % v] + (add_ or [])}}

    def cine(v, add_=(), remove_=()):
        return set_variant(v, ["cine_guard"] + list(add_), [s for s in SENSORS if s != "cine_guard"] + ["ai"]
                           + list(remove_))

    not_cine = {"all_of": [{"test": "is_mark_variant", "operator": "!=", "value": c} for c in CINE_V]}
    in_barrier = {"all_of": [{"test": "has_component", "value": "minecraft:is_charged"}] + not_cine["all_of"]}

    def meter(n):
        return "execute if score @s %s matches %d run title @a[r=24] actionbar §e◆ リフバリアΩ §6%s§8%s" % (
            OBJ, n, "◆" * (BARRIER_HITS - n), "◇" * n)

    events = {
        "minecraft:entity_spawned": {"add": {"component_groups": ["phase_1", "v_30", "cine_guard"]}},
        # 技の終わり: 一定確率でそのまま次の行動へ（バースト制御アーツ:終式）
        "sophia:skill_end": {"sequence": [{"filters": not_cine, **set_variant(0),
                                           "queue_command": {"command": ["event entity @s sophia:combo_roll"]}}]},
        "sophia:combo_roll": {"sequence": [
            {"filters": {"test": "is_skin_id", "value": skin}, "randomize": [
                {"weight": w, "trigger": "sophia:choose_skill",
                 "queue_command": {"command": ["title @a[r=24] actionbar §6§l連続行動！"]}},
                {"weight": 100 - w, "queue_command": {"command": ["particle sophia:sparkle ~ ~0.5 ~"]}}]}
            for skin, w in ((0, 30), (1, 38), (2, 45), (3, 55))]},
        "sophia:cine_end": dict(set_variant(0, ["sensor_normal", "ai"], ["cine_guard", "barrier", "barrier_cd"]),
                                queue_command={"command": ["scoreboard players set @s %s 0" % OBJ]}),
        # 殴られたとき: 12% で「MISS」（ひらりと横に避け、1 秒間無敵）
        "sophia:on_hit": {"randomize": [
            {"weight": 6, "queue_command": {"command": [
                "effect @s resistance 1 4 true", "particle sophia:afterimage ~ ~0.9 ~", "tp @s ^1.8 ^ ^",
                "title @a[r=12] actionbar §7§lMISS", "playsound mob.endermen.portal @a[r=16] ~ ~ ~ 0.5 1.8"]}},
            {"weight": 6, "queue_command": {"command": [
                "effect @s resistance 1 4 true", "particle sophia:afterimage ~ ~0.9 ~", "tp @s ^-1.8 ^ ^",
                "title @a[r=12] actionbar §7§lMISS", "playsound mob.endermen.portal @a[r=16] ~ ~ ~ 0.5 1.8"]}},
            {"weight": 88, "queue_command": {"command": ["particle sophia:spark_burst ~ ~1 ~"]}}]},
        # リフバリアΩ
        "sophia:barrier_hit": {"sequence": [
            {"remove": {"component_groups": ["barrier"]}, "add": {"component_groups": ["barrier_cd"]},
             "queue_command": {"command": [
                 "scoreboard players add @s %s 1" % OBJ, "particle sophia:hex_barrier ~ ~1 ~",
                 "playsound random.anvil_land @a[r=20] ~ ~ ~ 0.5 2.0"] + [meter(n) for n in range(1, BARRIER_HITS)]
                + ["execute if score @s %s matches %d.. run event entity @s sophia:barrier_break" % (OBJ, BARRIER_HITS)]}}]},
        "sophia:barrier_cd_end": {"sequence": [{"filters": in_barrier, "remove": {"component_groups": ["barrier_cd"]},
                                                "add": {"component_groups": ["barrier"]}}]},
        "sophia:barrier_end": {"sequence": [{"filters": in_barrier,
                                             "remove": {"component_groups": ["barrier", "barrier_cd"]},
                                             "add": {"component_groups": ["sensor_normal"]},
                                             "queue_command": {"command": ["scoreboard players set @s %s 0" % OBJ,
                                                                           "particle sophia:spark_burst ~ ~1 ~"]}}]},
        "sophia:barrier_break": {"sequence": [{"filters": not_cine,
                                               "remove": {"component_groups": ["barrier", "barrier_cd"]},
                                               "add": {"component_groups": ["sensor_normal"]},
                                               "queue_command": {"command": [
                                                   "scoreboard players set @s %s 0" % OBJ,
                                                   "title @a[r=24] actionbar §c§l◆ BARRIER BREAK ◆",
                                                   "effect @s slowness 2 255 true",
                                                   "particle sophia:shockwave_gold ~ ~0.1 ~",
                                                   "particle sophia:spark_burst ~ ~1 ~",
                                                   "playsound random.glass @a[r=24] ~ ~ ~ 1 0.8"]}}]},
        "sophia:osuwari": {"sequence": [{"filters": {"test": "is_mark_variant", "value": 0}, **set_variant(34)}]},
        "sophia:adapt": cine(31, ["phase_2"], ["phase_1"]),
        "sophia:universe": cine(32, ["phase_3"], ["phase_1", "phase_2"]),
        "sophia:revive": cine(33, ["phase_4"], ["phase_1", "phase_2", "phase_3"]),
    }
    for v in sorted(SKILLS):
        if v in CINE_V:
            continue
        if v == 14:
            ev = set_variant(14, ["barrier"], ["sensor_normal", "barrier_cd"])
            ev["queue_command"] = {"command": ["scoreboard players set @s %s 0" % OBJ]}
            events["sophia:skill_14"] = ev
        else:
            events["sophia:skill_%d" % v] = set_variant(v)

    near1 = [1, 1, 2, 2, 3, 4, 6, 13, 14, 15, 16, 17, 18, 12]
    far1 = [1, 5, 5, 7, 8, 9, 10, 11, 11, 12, 15, 17, 18]
    near2 = near1 + [19, 21, 23, 24, 25, 26, 28, 29]
    far2 = far1 + [19, 21, 22, 23, 24, 25, 27, 28, 29]
    near3 = near2 + [22, 27, 28]
    far3 = far2 + [22, 27, 29]
    near4 = near3 + [40, 40, 41, 41]
    far4 = far3 + [40, 40, 41, 41]
    NEAR = {"test": "distance_to_nearest_player", "operator": "<=", "value": 7}
    FAR = {"test": "distance_to_nearest_player", "operator": ">", "value": 7}
    base = [{"test": "is_mark_variant", "value": 0}, {"test": "has_target", "value": True}]
    seq = []
    for skin, near, far in ((0, near1, far1), (1, near2, far2), (2, near3, far3), (3, near4, far4)):
        for cond, lst in ((NEAR, near), (FAR, far)):
            seq.append({"filters": {"all_of": base + [{"test": "is_skin_id", "value": skin}, cond]},
                        "randomize": [{"weight": 10, "trigger": "sophia:skill_%d" % s} for s in lst]})
    events["sophia:choose_skill"] = {"sequence": seq}

    components = {
        "minecraft:type_family": {"family": ["sophia", "boss", "monster", "mob"]},
        "minecraft:health": {"value": HP, "max": HP},
        "minecraft:boss": {"hud_range": 64, "should_darken_sky": False},
        "minecraft:nameable": {"always_show": True, "allow_name_tag_renaming": False},
        "minecraft:persistent": {},
        "minecraft:collision_box": {"width": 0.6, "height": 1.6},
        "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": True},
        "minecraft:knockback_resistance": {"value": 1.0},
        "minecraft:fire_immune": {},
        "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0, "breathes_water": True},
        "minecraft:jump.static": {},
        "minecraft:movement.basic": {},
        "minecraft:movement": {"value": 0.36},
        "minecraft:navigation.walk": {"can_path_over_water": True, "avoid_damage_blocks": True},
        "minecraft:follow_range": {"value": 48, "max": 64},
        "minecraft:attack": {"damage": 12},
        "minecraft:equipment": {"table": "loot_tables/entities/sophia_equipment.json",
                                "slot_drop_chance": [{"slot": "slot.weapon.mainhand", "drop_chance": 0}]},
        "minecraft:loot": {"table": "loot_tables/entities/sophia_heart.json"},
        "minecraft:experience_reward": {"on_death": "1500"},
        "minecraft:environment_sensor": {"triggers": [
            {"filters": {"all_of": [{"test": "actor_health", "operator": "<=", "value": ADAPT_HP},
                                    {"test": "is_skin_id", "value": 0}] + not_cine["all_of"]}, "event": "sophia:adapt"},
            {"filters": {"all_of": [{"test": "actor_health", "operator": "<=", "value": UNIVERSE_HP},
                                    {"test": "is_skin_id", "value": 1}] + not_cine["all_of"]}, "event": "sophia:universe"},
            {"filters": {"all_of": [{"test": "actor_health", "operator": "<=", "value": REVIVE_HP},
                                    {"test": "is_skin_id", "value": 2}] + not_cine["all_of"]}, "event": "sophia:revive"},
        ]},
    }
    anims = {"skills": "controller.animation.sophia.skills", "barrier_cd": "controller.animation.sophia.barrier_cd",
             "barrier_time": "controller.animation.sophia.barrier_time", "death": "controller.animation.sophia.death",
             "upkeep": "animation.sophia.upkeep", "idle_loop": "animation.sophia.idle_loop",
             "cd_timer": "animation.sophia.cd_timer", "barrier_timer": "animation.sophia.barrier_timer",
             **{"skill_%d" % v: "animation.sophia.skill_%d" % v for v in SKILLS}}
    return {"format_version": "1.21.0", "minecraft:entity": {
        "description": {"identifier": ID, "is_spawnable": True, "is_summonable": True, "is_experimental": False,
                        "scripts": {"animate": ["skills", "barrier_cd", "barrier_time", "upkeep", "death"]},
                        "animations": anims},
        "component_groups": groups, "components": components, "events": events}}


def bp_animations():
    a = {"animation.sophia.skill_%d" % v: {"animation_length": length, "loop": False, "timeline": tl}
         for v, (name, length, tl) in SKILLS.items()}
    a["animation.sophia.cd_timer"] = {"animation_length": 0.4, "loop": False}
    # バリア中はキラキラした六角形が回る
    a["animation.sophia.barrier_timer"] = {"animation_length": BARRIER_TIME, "loop": False, "timeline": {
        "%.2f" % (i * 0.5): ["/particle sophia:hex_barrier ~ ~1 ~"] for i in range(int(BARRIER_TIME / 0.5))}}
    a["animation.sophia.upkeep"] = {"animation_length": 5.0, "loop": True, "timeline": {"0.50": [
        "/scoreboard players set @s %s 0" % OBJ_PLAYERS,
        "/execute as @a[r=40,m=!creative] run scoreboard players add %s %s 1" % (BOSS, OBJ_PLAYERS),
        "/execute if score @s %s matches 2 run effect @s resistance 6 0 true" % OBJ_PLAYERS,
        "/execute if score @s %s matches 3 run effect @s resistance 6 1 true" % OBJ_PLAYERS,
        "/execute if score @s %s matches 4.. run effect @s resistance 6 2 true" % OBJ_PLAYERS]}}
    a["animation.sophia.idle_loop"] = {"animation_length": 2.0, "loop": True, "timeline": {"1.00": CINE.end()}}
    return {"format_version": "1.10.0", "animations": a}


def bp_controllers():
    states = {"default": {"animations": ["idle_loop"],
                          "transitions": [{"skill_%d" % v: "q.mark_variant == %d" % v} for v in sorted(SKILLS)]}}
    for v in sorted(SKILLS):
        states["skill_%d" % v] = {"animations": ["skill_%d" % v],
                                  "transitions": [{"default": "q.all_animations_finished || q.mark_variant != %d" % v}],
                                  "on_exit": ["@s sophia:%s" % ("cine_end" if v in CINE_V else "skill_end")]}
    return {"format_version": "1.10.0", "animation_controllers": {
        "controller.animation.sophia.skills": {"initial_state": "default", "states": states},
        "controller.animation.sophia.barrier_cd": {"initial_state": "ready", "states": {
            "ready": {"transitions": [{"cd": "q.is_sheared"}]},
            "cd": {"animations": ["cd_timer"], "transitions": [{"ready": "q.all_animations_finished || !q.is_sheared"}],
                   "on_exit": ["@s sophia:barrier_cd_end"]}}},
        "controller.animation.sophia.barrier_time": {"initial_state": "off", "states": {
            "off": {"transitions": [{"on": "q.is_charged"}]},
            "on": {"animations": ["barrier_timer"], "transitions": [{"off": "q.all_animations_finished || !q.is_charged"}],
                   "on_exit": ["@s sophia:barrier_end"]}}},
        "controller.animation.sophia.death": {"initial_state": "alive", "states": {
            "alive": {"transitions": [{"dead": "!q.is_alive"}]},
            "dead": {"on_entry": ["/summon sophia:director ~ ~ ~", "/fog @a[r=64] remove sophia_universe",
                                  "/tag @a remove %s" % TS, "/tag @a remove %s" % GAZE] + CINE.end()}}},
    }}


def bp_loot():
    drop = {"pools": [
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:diamond_sword", "weight": 1, "functions": [
            {"function": "set_name", "name": "§9§l霊刀 紺碧刀"},
            {"function": "set_lore", "lore": ["§7ダメージを与えられない敵にも、ダメージを与えられる……らしい"]},
            {"function": "specific_enchants", "enchants": [
                {"id": "sharpness", "level": 5}, {"id": "unbreaking", "level": 3}, {"id": "looting", "level": 3},
                {"id": "knockback", "level": 1}, {"id": "mending", "level": 1}]}]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:bread", "weight": 1, "functions": [
            {"function": "set_count", "count": 16}, {"function": "set_name", "name": "§6フランスパン"}]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:nether_star", "weight": 1, "functions": [
            {"function": "set_name", "name": "§8邪神の石"}, {"function": "set_lore", "lore": ["§7全ての光を吸収する……ような気がする"]}]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:enchanted_golden_apple", "weight": 1,
                                  "functions": [{"function": "set_count", "count": 2}]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:totem_of_undying", "weight": 1}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:netherite_ingot", "weight": 1,
                                  "functions": [{"function": "set_count", "count": {"min": 2, "max": 4}}]}]},
    ]}
    equip = {"pools": [{"rolls": 1, "entries": [{"type": "item", "name": "minecraft:diamond_sword", "weight": 1,
                                                 "functions": [{"function": "set_name", "name": "§9紺碧刀"},
                                                               {"function": "specific_enchants",
                                                                "enchants": [{"id": "sharpness", "level": 5}]}]}]}]}
    return drop, equip


# ---------------------------------------------------------------------------
# 補助エンティティ
# ---------------------------------------------------------------------------
TICK = 0.05
MARKERS = ["volt_0", "volt_1", "volt_2", "aim_0", "aim_1", "aim_2", "rift", "rift_red", "black", "shell_0", "shell_1",
           "shell_2", "pillar_0", "pillar_1"]
DESPAWN_G = {"despawn": {"minecraft:instant_despawn": {}}}
DESPAWN_E = {"sophia:despawn": {"add": {"component_groups": ["despawn"]}}}


def fx_base(family, hitbox=0.2, health=1, invulnerable=True, gravity=False):
    c = {"minecraft:type_family": {"family": family}, "minecraft:health": {"value": health, "max": health},
         "minecraft:collision_box": {"width": hitbox, "height": hitbox},
         "minecraft:physics": {"has_gravity": gravity, "has_collision": gravity},
         "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
         "minecraft:knockback_resistance": {"value": 1.0}, "minecraft:body_rotation_blocked": {},
         "minecraft:fire_immune": {},
         "minecraft:conditional_bandwidth_optimization": {"default_values": {
             "max_optimized_distance": 0, "max_dropped_ticks": 0, "use_motion_prediction_hints": True}}}
    if invulnerable:
        c["minecraft:damage_sensor"] = {"triggers": [{"cause": "all", "deal_damage": False}]}
    return c


def entity(ident, comps, groups, events, anims_, animate):
    d = {"identifier": ident, "is_spawnable": False, "is_summonable": True, "is_experimental": False}
    if anims_:
        d["animations"] = anims_
        d["scripts"] = {"animate": animate}
    return {"format_version": "1.21.0", "minecraft:entity": {
        "description": d, "component_groups": groups, "components": comps, "events": events}}


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
        out.append("/execute %sif entity %s run event entity @s sophia:despawn" % (pos, sel))
    return out


def summons_bp():
    out, A, C = {}, {}, {}
    # 弾幕のオーブ
    g, e = dict(DESPAWN_G), dict(DESPAWN_E)
    for spd, (var, step, life, col) in ORB_SPEED.items():
        g["spd_" + spd] = {"minecraft:variant": {"value": var}}
        A["animation.sophia.orb.%s" % spd] = {"animation_length": life + 0.05, "loop": False, "timeline": ticks(
            life, lambda i, step=step: ["/tp @s ^ ^ ^%.2f" % step] + hit(1.1, 6, dy=-1.0), end=["@s sophia:despawn"])}
    for name, (mode, deg, spd) in ORB_EVENTS.items():
        rot = ["tp @s ~ ~ ~ facing @p[m=!creative]", "tp @s ~ ~ ~ ~%d 0" % deg] if mode == "aim" else [
            "tp @s ~ ~ ~ %d 0" % deg]
        e[name] = {"add": {"component_groups": ["spd_" + spd]}, "queue_command": {"command": rot}}
    C["controller.animation.sophia.orb"] = {"initial_state": "pick", "states": {
        "pick": {"transitions": [{spd: "q.variant == %d" % var} for spd, (var, *_r) in ORB_SPEED.items()]},
        **{spd: {"animations": [spd]} for spd in ORB_SPEED}}}
    out["orb"] = entity("sophia:orb", fx_base(["sophia_fx", "inanimate"]), g, e,
                        dict({spd: "animation.sophia.orb.%s" % spd for spd in ORB_SPEED},
                             ctrl="controller.animation.sophia.orb"), ["ctrl"])
    # 抜刀隊の刀
    A["animation.sophia.funnel.hover"] = {"animation_length": 0.8, "loop": False, "timeline": ticks(
        0.8, lambda i: ["/tp @s ~ ~ ~ facing @p[m=!creative]"])}
    A["animation.sophia.funnel.home"] = {"animation_length": 0.8, "loop": False, "timeline": ticks(
        0.8, lambda i: ["/execute at @s facing entity @p[m=!creative] feet positioned ^ ^ ^0.55 run tp @s ~ ~ ~ facing "
                        "@p[m=!creative]"] + hit(1.8, 7, "entity_attack", extra=["particle sophia:spark_burst ~ ~ ~"]))}
    A["animation.sophia.funnel.fly"] = {"animation_length": 1.25, "loop": False, "timeline": ticks(
        1.2, lambda i: ["/tp @s ^ ^ ^0.6"] + hit(1.8, 7, "entity_attack"), end=["@s sophia:despawn"])}
    C["controller.animation.sophia.funnel"] = {"initial_state": "hover", "states": {
        "hover": {"animations": ["hover"], "transitions": [{"home": "q.all_animations_finished"}]},
        "home": {"animations": ["home"], "transitions": [{"fly": "q.all_animations_finished"}],
                 "on_entry": ["/playsound item.trident.throw @a[r=30] ~ ~ ~ 0.6 1.6"]},
        "fly": {"animations": ["fly"]}}}
    out["funnel"] = entity("sophia:funnel", fx_base(["sophia_fx", "inanimate"]), dict(DESPAWN_G), dict(DESPAWN_E),
                           {"hover": "animation.sophia.funnel.hover", "home": "animation.sophia.funnel.home",
                            "fly": "animation.sophia.funnel.fly", "ctrl": "controller.animation.sophia.funnel"}, ["ctrl"])
    # 退勤届
    retire = ["title @a[r=1.4,m=!creative] title §f退勤届、受理しました", "title @a[r=1.4,m=!creative] subtitle §7お疲れ様でした",
              "summon sophia:blast ~ ~ ~", "effect @a[r=1.4,m=!creative] slowness 3 2 true",
              "playsound random.levelup @a[r=16] ~ ~ ~ 1 0.6"]
    A["animation.sophia.letter.fly"] = {"animation_length": 2.25, "loop": False, "timeline": ticks(
        2.2, lambda i: (["/execute at @s facing entity @p[m=!creative] eyes positioned ^ ^ ^0.42 run tp @s ~ ~ ~ facing "
                         "@p[m=!creative]"] if i < 24 else ["/tp @s ^ ^ ^0.5"])
        + hit(1.6, 8, "entity_attack", extra=retire, dy=-1.0), end=["@s sophia:despawn"])}
    out["letter"] = entity("sophia:letter", fx_base(["sophia_fx", "inanimate"]), dict(DESPAWN_G), dict(DESPAWN_E),
                           {"fly": "animation.sophia.letter.fly"}, ["fly"])
    # 竜巻: ゆっくり追いかけ、巻き込んだ相手を浮かせる
    A["animation.sophia.tornado.life"] = {"animation_length": 6.05, "loop": False, "timeline": ticks(
        6.0, lambda i: ["/execute at @s facing entity @p[m=!creative] feet positioned ^ ^ ^0.13 run tp @s ~ ~ ~"]
        + (["/effect @a[r=2.5,m=!creative] levitation 1 3 true", "/damage @a[r=2.5,m=!creative] 4 magic",
            "/playsound elytra.loop @a[r=16] ~ ~ ~ 0.3 1.4"] if i % 10 == 0 else []),
        end=["/particle sophia:dust ~ ~ ~", "@s sophia:despawn"])}
    out["tornado"] = entity("sophia:tornado", fx_base(["sophia_fx", "inanimate"]), dict(DESPAWN_G), dict(DESPAWN_E),
                            {"life": "animation.sophia.tornado.life"}, ["life"])
    # ブラックホール: 吸い込み → 収縮して爆発
    bh = "@e[type=sophia:blackhole,c=1]"
    A["animation.sophia.blackhole.life"] = {"animation_length": 3.6, "loop": False, "timeline": ticks(
        3.5, lambda i: ["/execute as @a[r=12,m=!creative] at @s facing entity %s feet run tp @s ^ ^ ^0.17" % bh]
        + (["/particle sophia:blackhole ~ ~ ~", "/particle sophia:accretion ~ ~ ~"] if i % 6 == 0 else []),
        end=["/damage @a[r=4,m=!creative] 14 magic", "/summon sophia:blast ~ ~ ~", "/particle sophia:shockwave_big_purple ~ ~ ~",
             "/particle sophia:galaxy ~ ~-1 ~", "/playsound mob.warden.sonic_boom @a[r=32] ~ ~ ~ 1 1.2",
             "/camerashake add @a[r=16] 0.8 0.4 positional", "@s sophia:despawn"])}
    out["blackhole"] = entity("sophia:blackhole", fx_base(["sophia_fx", "inanimate"]), dict(DESPAWN_G), dict(DESPAWN_E),
                              {"life": "animation.sophia.blackhole.life"}, ["life"])
    # 自動回復システムの機体（壊せる・HP20）
    drone = fx_base(["sophia_drone", "monster"], 0.7, health=20, invulnerable=False)
    drone["minecraft:damage_sensor"] = {"triggers": [{"cause": "fall", "deal_damage": False}]}
    drone["minecraft:nameable"] = {"always_show": False}
    A["animation.sophia.drone.life"] = {"animation_length": 20.0, "loop": False, "timeline": {
        **{"%.2f" % (1.0 + i * 1.5): ["/effect %s instant_health 1 1 true" % BOSS, "/particle sophia:heal ~ ~ ~",
                                      "/execute at %s run particle sophia:heal ~ ~1 ~" % BOSS] for i in range(12)},
        "19.90": ["/particle sophia:spark_burst ~ ~ ~", "@s sophia:despawn"]}}
    out["drone"] = entity("sophia:drone", drone, dict(DESPAWN_G), dict(DESPAWN_E),
                          {"life": "animation.sophia.drone.life"}, ["life"])
    # 影分身: 一度でも殴られると消える
    clone = {
        "minecraft:type_family": {"family": ["sophia_clone", "monster", "mob"]},
        "minecraft:health": {"value": 20, "max": 20},
        "minecraft:collision_box": {"width": 0.6, "height": 1.6}, "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
        "minecraft:movement": {"value": 0.38}, "minecraft:movement.basic": {}, "minecraft:jump.static": {},
        "minecraft:navigation.walk": {"can_path_over_water": True}, "minecraft:attack": {"damage": 7},
        "minecraft:follow_range": {"value": 40, "max": 40},
        "minecraft:damage_sensor": {"triggers": [{"cause": "all", "deal_damage": False,
                                                  "on_damage": {"event": "sophia:vanish", "target": "self"}}]},
        "minecraft:equipment": {"table": "loot_tables/entities/sophia_equipment.json",
                                "slot_drop_chance": [{"slot": "slot.weapon.mainhand", "drop_chance": 0}]},
        "minecraft:behavior.melee_attack": {"priority": 2, "speed_multiplier": 1.4, "track_target": True},
        "minecraft:behavior.nearest_attackable_target": {"priority": 1, "must_see": False, "within_radius": 40,
                                                         "entity_types": [{"filters": {"test": "is_family", "subject": "other",
                                                                                       "value": "player"}, "max_dist": 40}]},
        "minecraft:behavior.random_stroll": {"priority": 6},
        "minecraft:timer": {"looping": False, "time": 15, "time_down_event": {"event": "sophia:vanish", "target": "self"}},
    }
    out["clone"] = entity("sophia:clone", clone, dict(DESPAWN_G), {
        "sophia:vanish": {"add": {"component_groups": ["despawn"]}, "queue_command": {"command": [
            "particle sophia:afterimage ~ ~0.9 ~", "playsound mob.endermen.portal @a[r=16] ~ ~ ~ 0.6 1.6"]}}}, None, None)
    # 目印
    g, e = dict(DESPAWN_G), dict(DESPAWN_E)
    for k in MARKERS:
        g[k] = {"minecraft:type_family": {"family": ["sophia_marker", k, "inanimate"]}}
        e["sophia:as_" + k] = {"add": {"component_groups": [k]}}
    A["animation.sophia.marker.life"] = {"animation_length": 4.05, "loop": False, "timeline": {"4.00": ["@s sophia:despawn"]}}
    out["marker"] = entity("sophia:marker", fx_base(["sophia_marker", "inanimate"], 0.1), g, e,
                           {"life": "animation.sophia.marker.life"}, ["life"])
    # 爆風（ブロックは壊さない）
    ex = {"fuse_length": 0, "fuse_lit": True, "causes_fire": False, "breaks_blocks": False,
          "destroy_affected_by_griefing": False}
    out["blast"] = {"format_version": "1.21.0", "minecraft:entity": {
        "description": {"identifier": "sophia:blast", "is_spawnable": False, "is_summonable": True, "is_experimental": False},
        "component_groups": {"small": {"minecraft:explode": dict(ex, power=2)}, "big": {"minecraft:explode": dict(ex, power=4)}},
        "components": fx_base(["sophia_fx", "inanimate"], 0.1),
        "events": {"minecraft:entity_spawned": {"add": {"component_groups": ["small"]}},
                   "sophia:big": {"add": {"component_groups": ["big"]}}}}}
    # 撃破カットシーンの監督
    A["animation.sophia.director.death"] = {"animation_length": 5.6, "loop": False, "timeline": DEATH}
    director = fx_base(["sophia_fx", "inanimate"], 0.1)
    out["director"] = entity("sophia:director", director, dict(DESPAWN_G), dict(DESPAWN_E),
                             {"cut": "animation.sophia.director.death"}, ["cut"])
    return out, A, C


# ---------------------------------------------------------------------------
# Resource Pack
# ---------------------------------------------------------------------------
def cube(origin, size, uv, inflate=0):
    c = {"origin": origin, "size": size, "uv": uv}
    if inflate:
        c["inflate"] = inflate
    return c


def geo_boss():
    """細腕（Alex 型）。HD スキン（128x128）でも UV は 64 基準のまま縮尺で合う"""
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
        {"name": "rightItem", "parent": "rightArm", "pivot": [-5.5, 14.5, 1]},
        {"name": "leftArm", "parent": "body", "pivot": [5, 21.5, 0], "cubes": [
            cube([4, 11.5, -2], [3, 12, 4], [32, 48]), cube([4, 11.5, -2], [3, 12, 4], [48, 48], 0.25)],
         "locators": {"left_hand": [5.5, 11, 0]}},
        {"name": "rightLeg", "parent": "root", "pivot": [-1.9, 12, 0], "cubes": [
            cube([-3.9, 0, -2], [4, 12, 4], [0, 16]), cube([-3.9, 0, -2], [4, 12, 4], [0, 32], 0.25)],
         "locators": {"right_foot": [-2, 0, 0]}},
        {"name": "leftLeg", "parent": "root", "pivot": [1.9, 12, 0], "cubes": [
            cube([-0.1, 0, -2], [4, 12, 4], [16, 48]), cube([-0.1, 0, -2], [4, 12, 4], [0, 48], 0.25)],
         "locators": {"left_foot": [2, 0, 0]}},
    ]
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": "geometry.sophia_heart", "texture_width": 64, "texture_height": 64,
                        "visible_bounds_width": 4, "visible_bounds_height": 10, "visible_bounds_offset": [0, 3, 0]},
        "bones": bones}]}


def geo_simple():
    sword_face = {"uv": [0, 0], "uv_size": [16, 64]}
    return {
        "geometry.sophia_empty": [{"name": "root", "pivot": [0, 0, 0], "locators": {"center": [0, 0, 0]}}],
        "geometry.sophia_funnel": [
            {"name": "roll", "pivot": [0, 8, 0], "locators": {"center": [0, 8, 0]}},
            {"name": "blade", "parent": "roll", "pivot": [0, 8, 0], "rotation": [90, 0, 0], "cubes": [
                {"origin": [-2, 0, 0], "size": [4, 16, 0], "uv": {"north": sword_face, "south": sword_face}},
                {"origin": [0, 0, -2], "size": [0, 16, 4], "uv": {"east": sword_face, "west": sword_face}}]}],
        "geometry.sophia_drone": [{"name": "cube", "pivot": [0, 0, 0], "locators": {"center": [0, 0, 0]},
                                   "cubes": [{"origin": [-4, -4, -4], "size": [8, 8, 8], "uv": {
                                       f: {"uv": [0, 0], "uv_size": [16, 16]} for f in
                                       ("north", "south", "east", "west", "up", "down")}}]}],
        "geometry.sophia_letter": [{"name": "card", "pivot": [0, 0, 0], "locators": {"center": [0, 0, 0]},
                                    "cubes": [{"origin": [-3, -2, 0], "size": [6, 4, 0], "uv": {
                                        "north": {"uv": [0, 0], "uv_size": [24, 16]},
                                        "south": {"uv": [0, 0], "uv_size": [24, 16]}}}]}],
    }


def geo_files():
    tw = {"geometry.sophia_funnel": (16, 64), "geometry.sophia_drone": (16, 16), "geometry.sophia_letter": (24, 16),
          "geometry.sophia_empty": (16, 16)}
    out = {}
    for ident, bones in geo_simple().items():
        w, h = tw[ident]
        out[ident] = {"format_version": "1.12.0", "minecraft:geometry": [{
            "description": {"identifier": ident, "texture_width": w, "texture_height": h,
                            "visible_bounds_width": 3, "visible_bounds_height": 3, "visible_bounds_offset": [0, 0.5, 0]},
            "bones": bones}]}
    return out


def render_controllers():
    return {"format_version": "1.10.0", "render_controllers": {
        "controller.render.sophia_heart": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"],
            # 神核融解（再臨後）は紫の炎のように脈打つ
            "overlay_color": {"r": "0.7", "g": "0.25", "b": "1.0",
                              "a": "q.skin_id >= 3 ? 0.18 + math.sin(q.life_time * 300) * 0.07 : 0.0"}},
        "controller.render.sophia_simple": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"]},
        "controller.render.sophia_clone": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"],
            "overlay_color": {"r": "0.4", "g": "0.6", "b": "1.0", "a": "0.45 + math.sin(q.life_time * 400) * 0.1"}},
    }}


def client(ident, tex, geo, material, animations=None, animate=None, particles=None,
           rc="controller.render.sophia_simple", extra=None):
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


def rp_summon_anims():
    def emit(effect, every, loc="center", bones=None):
        a = {"loop": True, "animation_length": every,
             "particle_effects": {"0.00": [{"effect": effect, "locator": loc}]}}
        if bones:
            a["bones"] = bones
        return a
    return {
        "animation.sophia.orb_fx": emit("orb", 0.05),
        "animation.sophia.funnel_fx": emit("trail", 0.1, bones={"roll": {"rotation": [0, 0, "q.life_time * 540"]}}),
        "animation.sophia.letter_fx": emit("trail", 0.1, bones={"card": {"rotation": [0, "q.life_time * 720", 0]}}),
        "animation.sophia.tornado_fx": emit("tornado", 0.2),
        "animation.sophia.drone_fx": emit("heal", 0.5, bones={"cube": {
            "rotation": [0, "q.life_time * 180", 0], "position": [0, "math.sin(q.life_time * 200) * 1.5", 0]}}),
        "animation.sophia.clone_fx": emit("afterimage", 0.6, "body_center"),
    }


def rp_clients():
    boss_anims = sanims.short_names(sorted(SKILLS))
    orb_map = {"orb": "sophia:orb_gold"}
    clients = {
        "sophia_heart": client(ID, "sophia_heart", "geometry.sophia_heart", "entity_alphatest", boss_anims,
                               ["main", "aura_ctrl", "attack_fx"], sanims.PARTICLE_MAP, rc="controller.render.sophia_heart",
                               extra={"enable_attachables": True,
                                      "spawn_egg": {"base_color": "#f2d25a", "overlay_color": "#2a2a40"}}),
        "funnel": client("sophia:funnel", "sophia_funnel", "geometry.sophia_funnel", "entity_alphatest",
                         {"fx": "animation.sophia.funnel_fx"}, ["fx"], {"trail": "sophia:letter_trail"}),
        "letter": client("sophia:letter", "sophia_letter_e", "geometry.sophia_letter", "entity_alphatest",
                         {"fx": "animation.sophia.letter_fx"}, ["fx"], {"trail": "sophia:letter_trail"}),
        "tornado": client("sophia:tornado", "sophia_empty", "geometry.sophia_empty", "entity_alphatest",
                          {"fx": "animation.sophia.tornado_fx"}, ["fx"], {"tornado": "sophia:tornado"}),
        "blackhole": client("sophia:blackhole", "sophia_empty", "geometry.sophia_empty", "entity_alphatest"),
        "drone": client("sophia:drone", "sophia_drone", "geometry.sophia_drone", "entity_alphatest",
                        {"fx": "animation.sophia.drone_fx"}, ["fx"], {"heal": "sophia:heal"}),
        "clone": client("sophia:clone", "sophia_heart", "geometry.sophia_heart", "entity_alphablend",
                        dict(boss_anims, fx="animation.sophia.clone_fx"), ["main", "attack_fx", "fx"],
                        dict(sanims.PARTICLE_MAP, afterimage="sophia:afterimage"), rc="controller.render.sophia_clone",
                        extra={"enable_attachables": True}),
        "marker": client("sophia:marker", "sophia_empty", "geometry.sophia_empty", "entity_alphatest"),
        "blast": client("sophia:blast", "sophia_empty", "geometry.sophia_empty", "entity_alphatest"),
        "director": client("sophia:director", "sophia_heart", "geometry.sophia_heart", "entity_alphatest",
                           {"pose": "animation.sophia.director_pose"}, ["pose"]),
    }
    # オーブは速さで色を変える（BP の variant がクライアントにも届く）
    clients["orb"] = client("sophia:orb", "sophia_empty", "geometry.sophia_empty", "entity_alphatest",
                            {"fx_slow": "animation.sophia.orb_fx", "fx_normal": "animation.sophia.orb_fx_normal",
                             "fx_fast": "animation.sophia.orb_fx_fast"},
                            [{"fx_slow": "q.variant == 1"}, {"fx_normal": "q.variant == 2"}, {"fx_fast": "q.variant == 3"}],
                            {"orb": "sophia:orb_pink", "orb_n": "sophia:orb_gold", "orb_f": "sophia:orb_blue"})
    return clients


def lang():
    names = {ID: NAME, "sophia:orb": "弾幕", "sophia:funnel": "抜刀隊の刀", "sophia:letter": "退勤届",
             "sophia:tornado": "竜巻", "sophia:blackhole": "entropy", "sophia:drone": "自動回復システム",
             "sophia:clone": "ソフィアの分身", "sophia:marker": "目印", "sophia:blast": "衝撃", "sophia:director": NAME}
    lines = ["entity.%s.name=%s" % kv for kv in names.items()]
    lines += ["item.spawn_egg.entity.%s.name=%sのスポーンエッグ" % (ID, NAME),
              "pack.name=ソフィア・ハート ボス", "pack.description=多分神様「ソフィア・ハート」ボスアドオン", ""]
    return "\n".join(lines)


def main():
    skin = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RP, "textures/entity/sophia_heart.png")
    skin_bytes = open(skin, "rb").read()
    for d in (BP, RP, DIST):
        if os.path.isdir(d):
            shutil.rmtree(d)
    # BP
    write(os.path.join(BP, "manifest.json"), manifest("bp"))
    write(os.path.join(BP, "entities/sophia_heart.json"), bp_entity())
    sb, sa, sc = summons_bp()
    for name, data in sb.items():
        write(os.path.join(BP, "entities/%s.json" % name), data)
    anims_all = bp_animations()
    anims_all["animations"].update(sa)
    write(os.path.join(BP, "animations/sophia_heart.animation.json"), anims_all)
    ctrls = bp_controllers()
    ctrls["animation_controllers"].update(sc)
    write(os.path.join(BP, "animation_controllers/sophia_heart.ac.json"), ctrls)
    drop, equip = bp_loot()
    write(os.path.join(BP, "loot_tables/entities/sophia_heart.json"), drop)
    write(os.path.join(BP, "loot_tables/entities/sophia_equipment.json"), equip)
    # RP
    write(os.path.join(RP, "manifest.json"), manifest("rp"))
    os.makedirs(os.path.join(RP, "textures/entity"), exist_ok=True)
    open(os.path.join(RP, "textures/entity/sophia_heart.png"), "wb").write(skin_bytes)
    for name, im in sfx.entity_textures().items():
        im.save(os.path.join(RP, "textures/entity/%s.png" % name))
    for name, data in rp_clients().items():
        write(os.path.join(RP, "entity/%s.entity.json" % name), data)
    write(os.path.join(RP, "models/entity/sophia_heart.geo.json"), geo_boss())
    for ident, data in geo_files().items():
        write(os.path.join(RP, "models/entity/%s.geo.json" % ident.split(".")[1]), data)
    ra = sanims.all_animations()
    ra["animations"].update(rp_summon_anims())
    ra["animations"]["animation.sophia.orb_fx_normal"] = {"loop": True, "animation_length": 0.05, "particle_effects": {
        "0.00": [{"effect": "orb_n", "locator": "center"}]}}
    ra["animations"]["animation.sophia.orb_fx_fast"] = {"loop": True, "animation_length": 0.05, "particle_effects": {
        "0.00": [{"effect": "orb_f", "locator": "center"}]}}
    write(os.path.join(RP, "animations/sophia_heart.animation.json"), ra)
    write(os.path.join(RP, "animation_controllers/sophia_heart.ac.json"), sanims.controllers(sorted(SKILLS)))
    write(os.path.join(RP, "render_controllers/sophia_heart.rc.json"), render_controllers())
    for name, data in sfx.build_particles().items():
        write(os.path.join(RP, "particles/%s.json" % name), data)
    os.makedirs(os.path.join(RP, "textures/particle"), exist_ok=True)
    for name, im in sfx.build_textures().items():
        im.save(os.path.join(RP, "textures/particle/%s.png" % name))
    for name, data in sfx.build_fogs().items():
        write(os.path.join(RP, "fogs/%s.json" % name), data)
    for d in (BP, RP):
        for lc in ("ja_JP", "en_US"):
            write(os.path.join(d, "texts/%s.lang" % lc), lang())
        write(os.path.join(d, "texts/languages.json"), ["ja_JP", "en_US"])
        # パックアイコンは顔部分を拡大
        im = sfx.Image.open(skin).convert("RGBA")
        s = im.width // 64
        face = im.crop((8 * s, 8 * s, 16 * s, 16 * s)).resize((128, 128), sfx.Image.NEAREST)
        hat = im.crop((40 * s, 8 * s, 48 * s, 16 * s)).resize((128, 128), sfx.Image.NEAREST)
        face.alpha_composite(hat)
        face.save(os.path.join(d, "pack_icon.png"))
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "SophiaHeart_Boss.mcaddon")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for pack, arc in ((BP, "Sophia_BP"), (RP, "Sophia_RP")):
            for dp, _, fs in sorted(os.walk(pack)):
                for f in sorted(fs):
                    full = os.path.join(dp, f)
                    z.write(full, os.path.join(arc, os.path.relpath(full, pack)))
    print("built", out)


if __name__ == "__main__":
    main()
