# -*- coding: utf-8 -*-
"""白石白夜 ボスアドオン生成スクリプト.

使い方: python3 byakuya_boss/tools/generate.py [skin.png]
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
import anims  # noqa: E402
import fx  # noqa: E402
import summons  # noqa: E402
from cine import (brushup_files, FOE_ANY, RIVAL_FAMILY, Cine, add_arc_trails, add_rival, aim_at_foes, bake_smooth,  # noqa: E402
                  pause_events, split_melee, apply_stance_groups, stance_events, stance_filters, STANCE_ANIM,
                  encounter_cmds, foe_tag_anim, footwork_steps, near_filters, rival_target, smooth_client,
                  split_dashes, vectorize_animations)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BP = os.path.join(ROOT, "Byakuya_BP")
RP = os.path.join(ROOT, "Byakuya_RP")
DIST = os.path.join(ROOT, "dist")

ID = "byakuya:shiraishi_byakuya"
NAME = "白石白夜"
VERSION = [1, 9, 0]
MIN_ENGINE = [1, 21, 0]

UUID_BP_HEADER = "293c6dbc-978c-4439-aa05-c2fa6e63c99d"
UUID_BP_MODULE = "82d49302-2ab7-4291-a50c-143a1fe02427"
UUID_RP_HEADER = "7a4ebd1f-167b-4145-a8ef-20e335975e29"
UUID_RP_MODULE = "05d778a7-bb90-40f4-8dd9-6e63d1913bf0"

HP = 3500
PHASE2_HP = 2100  # 60% で終焉化
FINAL_HP = 875    # 25% で最終演技

random.seed(1201)  # 誕生日 12/1


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
BOSS = "@e[type=%s,c=1]" % ID


def say(text):
    return '/tellraw @a[r=48] {"rawtext":[{"text":"%s"}]}' % text.replace('"', '\\"')


def p(r=24):
    """サバイバル/アドベンチャーのプレイヤー"""
    return "@a[r=%d,m=!creative]" % r


def pt(name, pos="~ ~ ~"):
    return "/particle byakuya:%s %s" % (name, pos)


def at_players(r, name, pos="~ ~ ~"):
    return "/execute at %s run particle byakuya:%s %s" % (p(r), name, pos)


def shake(intensity, sec, r=24):
    return "/camerashake add @a[r=%d] %.2f %.2f positional" % (r, intensity, sec)


def sound(name, pitch=1.0, r=40, vol=1.0):
    return "/playsound %s @a[r=%d] ~ ~ ~ %.1f %.1f" % (name, r, vol, pitch)


def ring_pts(radius, n, y=0.2):
    for i in range(n):
        a = 2 * math.pi * i / n
        yield "~%.2f ~%.2f ~%.2f" % (radius * math.cos(a), y, radius * math.sin(a))


def behind_slash(dmg, color="white", r=4):
    """一番近いプレイヤーの背後へ瞬間移動して斬る（2 段階）"""
    return (
        [sound("mob.endermen.portal", 0.6), pt("afterimage", "~ ~0.9 ~"),
         "/execute as @p[r=40,m=!creative] at @s positioned ^ ^ ^-2 run tp %s ~ ~ ~ facing @s" % BOSS,
         pt("afterimage", "~ ~0.9 ~")],
        [sound("game.player.attack.strong", 0.5, 30), sound("item.trident.riptide_1", 1.6, 30, 0.6),
         pt("slash_flat_" + color, "~ ~1.1 ~"), pt("slash_" + color, "^ ^1.2 ^1.2"),
         pt("slash_" + color, "^ ^1 ^1.5"),
         at_players(r, "spark_burst", "~ ~1 ~"),
         "/damage %s %d entity_attack entity @s" % (p(r), dmg), shake(0.5, 0.3, 10)],
    )


# ---------------------------------------------------------------------------
# スキル定義:  variant -> (名前, 長さ, timeline)
# ---------------------------------------------------------------------------
SKILLS = {}


def skill(v, name, length, timeline):
    SKILLS[v] = (name, length, {"%.2f" % k: v_ for k, v_ in sorted(timeline.items())})


def add(tl, t, cmds):
    tl.setdefault(round(t, 2), []).extend(cmds)


# 1 瞬閃
a, b = behind_slash(14)
skill(1, "瞬閃", 1.0, {
    0.0: [say("§f白石白夜§7「遅いよ、お前さん」"), pt("charge_white", "~ ~1 ~")],
    0.15: a,
    0.45: b,
})

# 2 天地雷鳴（予兆リング → 落雷）
tl = {}
add(tl, 0, [say("§e【天地雷鳴】§7――天よ、地よ、鳴り響け"), sound("ambient.weather.thunder", 0.6, 48),
            pt("charge_yellow", "~ ~3 ~"), pt("shockwave_yellow", "~ ~0.1 ~")])
for t in (0.6, 1.2, 1.8):
    add(tl, t - 0.35, [at_players(32, "warn_yellow", "~ ~0.1 ~"), at_players(32, "charge_yellow", "~ ~6 ~")])
    add(tl, t, ["/execute at %s run summon lightning_bolt ~ ~ ~" % p(32),
                at_players(32, "shockwave_yellow", "~ ~0.1 ~"), at_players(32, "spark_burst", "~ ~0.5 ~"),
                shake(0.6, 0.3, 32)])
add(tl, 2.3, ["/execute at %s run summon lightning_bolt ~2 ~ ~2" % p(32),
              "/execute at %s run summon lightning_bolt ~-2 ~ ~-2" % p(32),
              pt("shockwave_big_yellow", "~ ~0.1 ~"), shake(1.0, 0.5, 32)])
skill(2, "天地雷鳴", 2.6, tl)

# 3 火炎の狂滅（回転しながら炎の輪）
tl = {}
add(tl, 0, [say("§c【火炎の狂滅】§7「炎はわしの得意分野でね」"), sound("mob.blaze.shoot", 0.5),
            pt("fire_pillar"), pt("charge_red", "~ ~1 ~")])
for i, rad in enumerate((2, 3.5, 5, 6.5)):
    add(tl, 0.2 + i * 0.2, [pt("shockwave_red", "~ ~0.2 ~")] + [pt("ember_burst", q) for q in ring_pts(rad, 6)])
add(tl, 1.2, ["/damage %s 9 fire entity @s" % p(8), sound("mob.ghast.fireball", 0.6),
              shake(0.6, 0.4, 16)] + [pt("fire_pillar", q) for q in ring_pts(4, 8, 0)])
add(tl, 1.8, ["/damage %s 9 fire entity @s" % p(8), sound("random.explode", 0.8),
              pt("shockwave_big_red", "~ ~0.2 ~"), pt("ember_burst", "~ ~1 ~"),
              "/particle minecraft:huge_explosion_emitter ~ ~1 ~", shake(1.0, 0.5, 16)]
    + [pt("fire_pillar", q) for q in ring_pts(7, 10, 0)])
skill(3, "火炎の狂滅", 2.2, tl)

# 4 水没の重滅
tl = {}
add(tl, 0, [say("§9【水没の重滅】§7「沈め」"), sound("random.splash", 0.5),
            "/effect %s levitation 2 4 true" % p(18), at_players(18, "water_pillar"),
            pt("shockwave_blue", "~ ~0.1 ~")])
for t in (0.4, 0.9, 1.4):
    add(tl, t, [at_players(18, "water_spiral", "~ ~-0.5 ~"), sound("bubble.upinside", 0.8, 30)])
add(tl, 1.8, [pt("charge_blue", "~ ~1.5 ~")])
add(tl, 2.0, ["/effect %s slowness 6 3 true" % p(18), "/effect %s mining_fatigue 6 2 true" % p(18),
              sound("random.explode", 0.5), pt("water_burst", "~ ~0.2 ~"), pt("shockwave_big_blue", "~ ~0.1 ~"),
              shake(0.8, 0.4, 20)])
add(tl, 2.6, ["/damage %s 8 drowning entity @s" % p(18), at_players(18, "water_burst", "~ ~0.2 ~"),
              at_players(18, "shockwave_blue", "~ ~0.1 ~"), sound("random.splash", 0.4)])
skill(4, "水没の重滅", 3.0, tl)

# 5 樹海の誘滅（引き寄せ → 斬撃）
tl = {}
add(tl, 0, [say("§2【樹海の誘滅】§7「こっちへおいで」"), sound("mob.evocation_illager.cast_spell", 0.6),
            pt("leaf_swirl"), pt("shockwave_green", "~ ~0.1 ~")])
for i in range(15):
    t = 0.1 + i * 0.1
    add(tl, t, ["/execute as @a[r=22,rm=2.5,m=!creative] at @s facing entity %s feet run tp @s ^ ^ ^0.9" % BOSS])
    if i % 3 == 0:
        add(tl, t, [at_players(22, "leaf_burst", "~ ~0.6 ~"), sound("block.sweet_berry_bush.hurt", 0.7, 30)])
add(tl, 1.7, ["/damage %s 12 entity_attack entity @s" % p(4), "/effect %s poison 5 1 true" % p(6),
              sound("game.player.attack.strong", 0.5, 30), pt("slash_flat_green", "~ ~1 ~"),
              pt("slash_green", "^ ^1.2 ^1.3"), pt("leaf_burst", "~ ~1 ~"), at_players(4, "spark_burst", "~ ~1 ~"),
              shake(0.6, 0.3, 10)])
skill(5, "樹海の誘滅", 2.0, tl)

# 6 スコーピオン（地面から刃と牙）
tl = {}
add(tl, 0, [say("§d【スコーピオン】§7足元にご注意を"), sound("mob.evocation_illager.prepare_attack", 1.0)])
add(tl, 0.1, [at_players(28, "warn_purple", "~ ~0.1 ~")])
add(tl, 0.35, [pt("shockwave_purple", "~ ~0.1 ~"), pt("ground_blade"), sound("random.anvil_land", 0.6, 30),
               shake(0.4, 0.2, 12)])
add(tl, 0.4, ["/execute at %s run summon evocation_fang ~ ~ ~" % p(28), at_players(28, "ground_blade")])
for t, rr in ((0.8, 1.5), (1.2, 2.5)):
    cmds = [at_players(28, "warn_purple", "~ ~0.1 ~")]
    for k in range(6):
        ang = 2 * math.pi * k / 6 + rr
        off = "~%.1f ~ ~%.1f" % (rr * math.cos(ang), rr * math.sin(ang))
        cmds.append("/execute at %s run summon evocation_fang %s" % (p(28), off))
        cmds.append(at_players(28, "ground_blade", off))
    add(tl, t, cmds)
skill(6, "スコーピオン", 1.8, tl)

# 7 千本投擲（頭上に刃の輪 → 刃の雨）
tl = {}
add(tl, 0, [say("§6【千本投擲】§7投擲は昔から得意なんだ"), sound("item.trident.throw", 0.6),
            at_players(32, "warn_white", "~ ~0.1 ~")])
add(tl, 0.2, [at_players(32, "blade_halo", "~ ~9 ~")])
for i in range(7):
    t = 0.5 + i * 0.25
    cmds = [at_players(32, "blade_rain", "~ ~9 ~"), sound("item.trident.throw", 1.2 + i * 0.05, 30, 0.6)]
    for _ in range(3):
        cmds.append("/execute at %s run summon arrow ~%.1f ~12 ~%.1f" % (p(32), random.uniform(-1.5, 1.5),
                                                                          random.uniform(-1.5, 1.5)))
    add(tl, t, cmds)
skill(7, "千本投擲", 2.4, tl)

# 8 ホッパー（反射障壁）
tl = {}
add(tl, 0, [say("§b【ホッパー】§7反射板展開――叩いても無駄だよ"), sound("random.anvil_land", 1.5),
            pt("shockwave_cyan", "~ ~0.1 ~")])
for i in range(9):
    add(tl, 0.1 + i * 0.43, [pt("hopper_panel", "~ ~1 ~")])
skill(8, "ホッパー", 4.0, tl)

# 9 武装を解除する程度の能力（成功時）
tl = {0: [say("§7【武装を解除する程度の能力】§f「その刀、預かっておくよ」")],
      0.3: [sound("random.break", 0.6), "/effect %s weakness 8 255 true" % p(14),
            "/effect %s mining_fatigue 8 2 true" % p(14),
            at_players(14, "shatter", "~ ~1.2 ~"), at_players(14, "slash_white", "~ ~1.2 ~"),
            at_players(14, "spark_burst", "~ ~1.2 ~")]}
skill(9, "武装解除", 1.2, tl)

# 10 鋼糸（糸で縛る → 背後から斬る）
a, b = behind_slash(12)
tl = {0: [say("§7【鋼糸】§f「動けないだろう？」"), sound("random.bow", 0.5)]}
for t in (0.2, 0.5, 0.8, 1.1):
    add(tl, t, ["/execute at %s facing entity %s eyes run particle byakuya:wire ^ ^1 ^%d" % (p(18), BOSS, k)
                for k in range(1, 10)])
add(tl, 0.35, ["/effect %s slowness 3 255 true" % p(18), sound("random.anvil_use", 1.8, 30),
               at_players(18, "spark_burst", "~ ~1 ~")])
add(tl, 1.3, a)
add(tl, 1.7, b)
skill(10, "鋼糸", 2.0, tl)

# 11 集散（第二形態以降）
tl = {0: [say("§4【集散】§7二十の刃よ――集い、散れ"), sound("mob.wither.shoot", 0.5), pt("charge_red", "~ ~1 ~")]}
for i in range(6):
    t = 0.4 + i * 0.5
    cmds = ["/damage %s 5 entity_attack entity @s" % p(8),
            sound("game.player.attack.strong", 0.6 + i * 0.1, 30), pt("slash_flat_red", "~ ~1 ~"),
            at_players(8, "spark_burst", "~ ~1 ~"), shake(0.3, 0.2, 10)]
    for _ in range(4):
        cmds.append(pt("slash_red", "~%.1f ~%.1f ~%.1f" % (random.uniform(-4, 4), random.uniform(0.5, 2.5),
                                                          random.uniform(-4, 4))))
    add(tl, t, cmds)
add(tl, 3.0, [pt("shockwave_big_red", "~ ~0.2 ~")])
skill(11, "集散", 3.2, tl)

# 12 無刀 無残（第二形態以降）
tl = {0: [say("§0§l【無刀 無残】"), "/effect %s darkness 4 0 true" % p(24), "/effect %s slowness 2 2 true" % p(24),
          sound("mob.warden.sonic_charge", 0.7), pt("charge_purple", "~ ~1 ~")]}
for t in (0.3, 0.7, 1.1):
    add(tl, t, [pt("warn_purple", "~ ~0.1 ~"), pt("charge_purple", "~ ~1 ~")])
add(tl, 1.5, [sound("mob.warden.sonic_boom", 0.6, 48), "/damage %s 16 entity_attack entity @s" % p(10),
              "/effect %s wither 5 1 true" % p(10), pt("big_slash_purple", "~ ~1.2 ~"), pt("big_slash_white", "~ ~1.2 ~"),
              pt("shockwave_big_purple", "~ ~0.1 ~"), at_players(10, "spark_burst", "~ ~1 ~"),
              shake(1.5, 0.6, 24)] + ["/particle minecraft:sonic_explosion %s" % q for q in ring_pts(4, 8, 1)])
skill(12, "無刀 無残", 2.4, tl)

# ---------------------------------------------------------------------------
# 遠距離技・追加技
# ---------------------------------------------------------------------------
def waves(*angles, y=1.1):
    return ["/summon byakuya:slash_wave ~ ~%.1f ~ %s" % (y, summons.aim_event(a)) for a in angles]


AIM = "@e[family=aim_mark,c=1]"
NEAREST = "@p[r=48,m=!creative]"

# 13 飛燕斬月（斬撃を飛ばす）
skill(13, "飛燕斬月", 1.2, {
    0: [say("§c【飛燕斬月】§7「届かないと思ったかい？」"), pt("charge_red", "~ ~1 ~")],
    0.3: waves(-20, 0, 20) + [sound("mob.wither.shoot", 1.4), sound("item.trident.riptide_1", 1.2),
                              pt("slash_flat_red", "~ ~1.1 ~"), shake(0.3, 0.2, 12)],
    0.8: waves(-30, -10, 10, 30) + [sound("mob.wither.shoot", 1.2), sound("item.trident.riptide_1", 1.0),
                                    pt("slash_flat_red", "~ ~1.1 ~"), shake(0.3, 0.2, 12)],
})

# 14 追刃（宙に浮かぶ刀が追いかけてくる）
tl = {}
add(tl, 0, [say("§b【追刃・燕】§7「逃げても無駄さ。刃が覚えている」"), sound("mob.evocation_illager.prepare_summon", 1.2)])
for i, (x, y, z) in enumerate([(-2, 2.5, 0), (2, 2.5, 0), (-1.2, 3.3, -0.5), (1.2, 3.3, -0.5), (0, 3.8, -1)]):
    add(tl, 0.2 + i * 0.1, ["/summon byakuya:homing_blade ^%.1f ^%.1f ^%.1f" % (x, y, z),
                            pt("spark_burst", "^%.1f ^%.1f ^%.1f" % (x, y, z)), sound("random.anvil_use", 1.6 + i * 0.1, 30, 0.5)])
skill(14, "追刃", 1.2, tl)

# 15 遠当て（狙いを定め、一直線に斬り抜くビーム）
tl = {}
add(tl, 0, [say("§c【遠当て・一閃】§7「……狙いは付けた」"),
            "/execute at %s run summon byakuya:marker ~ ~1 ~ byakuya:as_aim_mark" % NEAREST,
            "/effect @s slowness 2 255 true", sound("mob.warden.sonic_charge", 1.4, 48)])
LINE = "/execute at @s anchored eyes facing entity %s feet positioned ^ ^ ^%s run " % (AIM, "%.1f")
for t in (0.1, 0.35, 0.6, 0.85, 1.05):
    add(tl, t, [LINE % k + "particle byakuya:beam_warn ~ ~ ~" for k in range(2, 42, 2)]
        + ["/tp @s ~ ~ ~ facing %s" % AIM])
add(tl, 1.2, [sound("mob.warden.sonic_boom", 1.3, 64), sound("game.player.attack.strong", 0.5, 48),
              pt("slash_flat_red", "~ ~1.4 ~"), shake(0.8, 0.4, 32)]
    + [LINE % (k * 1.5) + "particle byakuya:beam_seg ~ ~ ~" for k in range(1, 28)]
    + [LINE % (k * 1.5) + "damage @a[r=1.7,m=!creative] 18 entity_attack entity @s" for k in range(1, 28)]
    + [LINE % (k * 6.0) + "particle byakuya:spark_burst ~ ~ ~" for k in range(1, 7)])
add(tl, 1.4, ["/event entity @e[family=aim_mark] byakuya:despawn"])
skill(15, "遠当て", 2.1, tl)

# 16 流星刀（予兆リングの位置に刀が降り注ぐ・3 波）
tl = {}
add(tl, 0, [say("§6【流星刀】§7「天から降る刃を、見切れるかな」"), pt("charge_red", "~ ~3 ~"),
            sound("mob.evocation_illager.cast_spell", 0.5)])
for wave, (t0, n) in zip("abc", ((0.3, 4), (0.9, 5), (1.5, 6))):
    fam = "@e[family=meteor_%s]" % wave
    cmds = ["/execute at %s run summon byakuya:marker ~ ~ ~ byakuya:as_meteor_%s" % (p(40), wave)]
    for _ in range(n):
        cmds.append("/execute at %s run summon byakuya:marker ~%.1f ~ ~%.1f byakuya:as_meteor_%s"
                    % (p(40), random.uniform(-5, 5), random.uniform(-5, 5), wave))
    add(tl, t0, cmds + [sound("random.orb", 0.5, 40)])
    for dt in (0.05, 0.35, 0.65):
        add(tl, t0 + dt, ["/execute at %s run particle byakuya:warn_red ~ ~0.1 ~" % fam])
    add(tl, t0 + 0.7, ["/execute at %s run particle byakuya:blade_rain ~ ~9 ~" % fam])
    add(tl, t0 + 1.0, ["/execute at %s run damage @a[r=2.5,m=!creative] 12 entity_explosion entity @s" % fam,
                       "/execute at %s run particle byakuya:meteor_impact ~ ~0.2 ~" % fam,
                       "/execute at %s run particle byakuya:shockwave_red ~ ~0.1 ~" % fam,
                       "/execute at %s run particle byakuya:ground_blade ~ ~ ~" % fam,
                       "/execute at %s run playsound random.explode @a[r=24] ~ ~ ~ 0.8 1.2" % fam,
                       shake(0.5, 0.3, 40),
                       "/event entity %s byakuya:despawn" % fam])
skill(16, "流星刀", 2.8, tl)

# 17 三段斬り（踏み込み三連撃 → 唐竹割り）
tl = {0: [say("§f【三段斬り】§7「一つ、二つ、三つ――」")]}
for i, t in enumerate((0.3, 0.65, 1.0)):
    add(tl, t - 0.05, ["/execute at @s facing entity %s feet rotated ~ 0 positioned ^ ^ ^2.5 run tp @s ~ ~ ~ facing %s"
                       % (NEAREST, NEAREST), pt("afterimage", "~ ~0.9 ~")])
    add(tl, t, ["/damage %s 8 entity_attack entity @s" % p(3), sound("game.player.attack.strong", 0.8 + i * 0.2, 30),
                pt("slash_white", "^ ^1.2 ^1.2"), pt("slash_flat_white", "~ ~1 ~"),
                at_players(3, "spark_burst", "~ ~1 ~"), shake(0.3, 0.2, 8)])
add(tl, 1.4, ["/damage %s 13 entity_attack entity @s" % p(4), sound("random.anvil_land", 0.5, 30),
              pt("big_slash_red", "^ ^1.5 ^1"), pt("shockwave_red", "~ ~0.1 ~"), at_players(4, "spark_burst", "~ ~1 ~"),
              shake(0.7, 0.3, 10)])
skill(17, "三段斬り", 1.7, tl)

# 18 兜割り（跳躍 → プレイヤーの頭上から叩き割る）
tl = {0: [say("§c【兜割り】§7「上だよ、お前さん」"), sound("mob.ravager.roar", 1.4)]}
add(tl, 0.3, ["/tp @s ~ ~6 ~", pt("afterimage", "~ ~-5 ~"), pt("shockwave_white", "~ ~-5.9 ~"), sound("mob.enderdragon.flap", 0.8)])
add(tl, 0.55, ["/execute at %s run tp @s ~ ~7 ~" % NEAREST, pt("afterimage", "~ ~0.9 ~"),
               at_players(40, "warn_red", "~ ~0.1 ~")])
add(tl, 0.9, [at_players(40, "warn_red", "~ ~0.1 ~")])
add(tl, 1.3, ["/damage %s 15 entity_attack entity @s" % p(5), "/effect %s slowness 3 2 true" % p(5),
              sound("random.explode", 0.6), sound("random.anvil_land", 0.4),
              pt("shockwave_big_red", "~ ~0.1 ~"), pt("ground_blade", "~ ~ ~"), pt("meteor_impact", "~ ~0.2 ~"),
              "/particle minecraft:huge_explosion_emitter ~ ~0.5 ~", shake(1.2, 0.5, 20)]
    + [pt("ground_blade", q) for q in ring_pts(3, 6, 0)])
skill(18, "兜割り", 1.8, tl)

# 19 見切り（カウンター構え）
tl = {0: [say("§7【見切り】§f「……打ってきな」"), sound("random.anvil_use", 0.5), pt("shockwave_white", "~ ~0.1 ~")]}
for i in range(5):
    add(tl, 0.3 + i * 0.45, [pt("warn_white", "~ ~0.1 ~")])
add(tl, 2.4, [say("§f白石白夜§7「来ないのかい。賢いねぇ」")])
skill(19, "見切り", 2.5, tl)

# 21 影分身（第二形態以降）
tl = {0: [say("§8【影分身】§7「わしが何人いると思う？」"), sound("mob.evocation_illager.prepare_summon", 0.6)]}
add(tl, 0.6, ["/summon byakuya:shadow ^2 ^ ^-1", "/summon byakuya:shadow ^-2 ^ ^-1",
              pt("afterimage", "^2 ^0.9 ^-1"), pt("afterimage", "^-2 ^0.9 ^-1"), pt("shockwave_purple", "~ ~0.1 ~"),
              sound("mob.endermen.portal", 0.5)])
skill(21, "影分身", 1.2, tl)

# 22 燕返し（打ち上げ → 返す刀で二連撃）
tl = {0: [say("§f【燕返し】§7「飛んでる燕も落とせるよ」")]}
add(tl, 0.32, ["/damage %s 7 entity_attack entity @s" % p(4), "/effect %s levitation 1 12 true" % p(4),
               sound("game.player.attack.strong", 1.2, 30), pt("slash_white", "^ ^1.5 ^1"),
               at_players(4, "spark_burst", "~ ~1 ~")])
add(tl, 0.95, ["/damage %s 9 entity_attack entity @s" % p(7), sound("game.player.attack.strong", 0.8, 30),
               at_players(7, "slash_white", "~ ~1 ~"), at_players(7, "spark_burst", "~ ~1 ~")])
add(tl, 1.25, ["/damage %s 9 entity_attack entity @s" % p(7), sound("random.anvil_land", 0.6, 30),
               at_players(7, "slash_red", "~ ~1 ~"), at_players(7, "spark_burst", "~ ~1 ~"), shake(0.6, 0.3, 10)])
skill(22, "燕返し", 1.5, tl)

# 23 森羅万象（最終形態のみ・全方位の斬撃波）
tl = {0: [say("§4§l【森羅万象】§7「――全部、斬る」"), "/effect %s darkness 3 0 true" % p(32),
          pt("charge_red", "~ ~1 ~"), sound("mob.wither.spawn", 1.5, 48)]}
for k, t in enumerate((0.6, 1.2, 1.8, 2.4)):
    off = 15 if k % 2 else 0
    add(tl, t, waves(*[(a + off) % 360 for a in range(0, 360, 30)], y=0.6 if k % 2 else 1.4)
        + [pt("shockwave_red", "~ ~0.1 ~"), sound("mob.wither.shoot", 0.8 + k * 0.1, 48), shake(0.4, 0.3, 24)])
skill(23, "森羅万象", 3.0, tl)

# ===========================================================================
# v1.3 追加技
# ===========================================================================
CINE = Cine("byakuya_cine")
FACE = "^ ^1.6 ^"
ANYONE = "@p[r=64]"
HITORI = "@e[family=hitori,c=1]"   # 独のアドオンが無くてもエラーにならないよう family で

# 24 地走り・波紋: 地面を走る波紋。リングが来たらジャンプで避ける
tl = {0: [say("§c【地走り・波紋】§7「跳べるかい？　お前さん」"),
          "/title %s actionbar §e§l波紋が来たら ジャンプ！" % p(40), "/effect @s slowness 3 255 true"]}
for t0 in (0.5, 1.1, 1.7, 2.3):
    add(tl, t0, [pt("ripple_ring"), pt("shockwave_red", "~ ~0.1 ~"), sound("random.anvil_land", 0.6 + t0 * 0.2),
                 sound("game.player.attack.strong", 0.5, 30), shake(0.3, 0.2, 16)])
    for k in range(18):
        rad = 1.5 + k
        add(tl, t0 + 0.1 * k, [
            "/execute as @a[rm=%.1f,r=%.1f,m=!creative] at @s unless block ~ ~-0.3 ~ air run damage @s 10 "
            "entity_attack entity %s" % (max(0, rad - 0.7), rad + 0.7, BOSS)])
skill(24, "地走り・波紋", 4.4, tl)

# 25 百花繚乱: カットイン → 6 回の斬り抜け（予告線あり）→ 花が散る
tl = {}
CINE.cutin(tl, 0.0, 0.8, "^0.7 ^1.6 ^1.5", "^ ^1.55 ^", "§d§l百花繚乱", "§7――咲いて、散れ")
add(tl, 0, [pt("petal_storm"), pt("charge_red", "~ ~1 ~"), sound("mob.evocation_illager.cast_spell", 0.6)])
PATH = (1, 2.5, 4, 5.5, 7, 8.5, 10)
for k in range(6):
    t = 1.0 + 0.5 * k
    ang = (k * 137) % 360
    add(tl, t, ["/execute at %s rotated %d 0 positioned ^ ^ ^-5 run tp @s ~ ~ ~ facing %s" % (NEAREST, ang, NEAREST),
                pt("afterimage", "~ ~0.9 ~"), sound("mob.endermen.portal", 1.4, 30, 0.6)]
        + ["/execute at @s positioned ^ ^0.4 ^%.1f run particle byakuya:beam_warn ~ ~ ~" % d for d in PATH])
    add(tl, t + 0.25, ["/execute at @s positioned ^ ^1 ^%.1f run damage @a[r=1.7,m=!creative] 9 entity_attack entity @s"
                       % d for d in PATH]
        + ["/execute at @s positioned ^ ^1 ^%.1f run particle byakuya:petal_burst ~ ~ ~" % d for d in (2, 5, 8)]
        + ["/execute at @s positioned ^ ^1.1 ^%.1f run particle byakuya:beam_seg ~ ~ ~" % d for d in PATH]
        + [pt("slash_flat_red", "^ ^1 ^5"), pt("slash_red", "^ ^1.2 ^5"), "/tp @s ^ ^ ^10",
           sound("game.player.attack.strong", 0.7 + 0.1 * k, 30), sound("item.trident.riptide_1", 1.4, 30, 0.6),
           shake(0.3, 0.2, 12)])
add(tl, 3.9, [say("§f白石白夜§7「――散れ」"), pt("petal_storm")] + [pt("warn_red", q) for q in ring_pts(8, 12, 0.1)])
add(tl, 4.4, ["/damage %s 14 entity_attack entity @s" % p(8), pt("petal_burst", "~ ~1 ~"), pt("shockwave_big_red", "~ ~0.1 ~"),
              at_players(8, "big_slash_red", "~ ~1 ~"), at_players(8, "petal_burst", "~ ~1 ~"),
              sound("random.anvil_land", 0.5), shake(0.8, 0.4, 16)])
skill(25, "百花繚乱", 4.8, tl)

# 26 鞘鳴り: 赤い円の中にいる者の時を止め、鞘に納めた瞬間に斬る
TS = "byakuya_sayanari"
tl = {0: ["/tag @a remove %s" % TS, say("§f【鞘鳴り】§7「……少し、時間を止めようか」"), "/effect @s slowness 5 255 true",
          pt("zone_12"), "/title %s actionbar §c§l赤い円（12マス）の外へ逃げろ！" % p(40), sound("block.bell.hit", 0.5, 48)]}
add(tl, 0.6, [pt("zone_12")])
add(tl, 1.2, ["/tag %s add %s" % (p(12), TS), "/effect @a[tag=%s] slowness 3 255 true" % TS,
              "/effect @a[tag=%s] mining_fatigue 3 4 true" % TS, "/effect @a[tag=%s] darkness 3 0 true" % TS,
              pt("time_stop", "~ ~0.1 ~"), sound("random.anvil_use", 0.5, 48)])
CINE.cutin(tl, 1.2, 0.9, "^0.9 ^1.3 ^1.4", "^-0.2 ^1.1 ^0.2", "§f§l鞘鳴り")
for i in range(13):
    cmds = ["/execute at @a[tag=%s] run particle byakuya:slash_white ~%.1f ~%.1f ~%.1f" %
            (TS, random.uniform(-2, 2), random.uniform(0.3, 2.2), random.uniform(-2, 2)) for _ in range(2)]
    add(tl, 2.1 + i * 0.1, cmds + [sound("item.trident.hit", 1.0 + i * 0.07, 30, 0.5)])
add(tl, 3.6, [sound("random.anvil_land", 2.0, 48), sound("note.pling", 2.0, 48),
              "/damage @a[tag=%s] 20 entity_attack entity @s" % TS,
              "/execute at @a[tag=%s] run particle byakuya:big_slash_white ~ ~1 ~" % TS,
              "/execute at @a[tag=%s] run particle byakuya:spark_burst ~ ~1 ~" % TS,
              "/camera @a[tag=%s] fade time 0 0.1 0.3 color 255 255 255" % TS, shake(1.0, 0.4, 24),
              "/tag @a remove %s" % TS])
skill(26, "鞘鳴り", 4.2, tl)

# 27 業火螺旋: 3 本の炎の腕が渦を巻いて広がる
tl = {0: [say("§c【業火螺旋】§7「燃え尽きな」"), "/effect @s slowness 3 255 true", pt("charge_red", "~ ~1 ~"),
          sound("mob.blaze.shoot", 0.5)]}
for i in range(18):
    rad = 1.5 + i * 0.75
    cmds = []
    for arm in (0, 120, 240):
        a = math.radians(arm + i * 32)
        pos = "~%.2f ~ ~%.2f" % (rad * math.cos(a), rad * math.sin(a))
        cmds += [pt("fire_jet", pos), "/execute positioned %s run damage @a[r=1.6,m=!creative] 8 fire entity @s" % pos]
    if i % 3 == 0:
        cmds.append(sound("mob.ghast.fireball", 0.6 + i * 0.03, 40, 0.7))
    add(tl, 0.4 + i * 0.08, cmds)
add(tl, 2.0, ["/damage %s 12 fire entity @s" % p(5), "/summon byakuya:blast ~ ~0.5 ~", pt("shockwave_big_red", "~ ~0.1 ~"),
              pt("ember_burst", "~ ~1 ~"), pt("fire_pillar"), shake(1.0, 0.4, 20)])
skill(27, "業火螺旋", 2.6, tl)

# ===========================================================================
# カットシーン
# ===========================================================================
# 30 登場
tl = {}
add(tl, 0, CINE.begin(4.5) + ["/tp @s ~ ~ ~ facing %s" % ANYONE, CINE.cam("^ ^5 ^16", "^ ^1.5 ^"),
                              CINE.fade(0, 0.2, 0.9), pt("petal_storm"), sound("mob.wither.spawn", 0.8, 64),
                              "/scoreboard objectives add byakuya_players dummy"])
add(tl, 0.1, [CINE.cam("^1.2 ^1.7 ^3.2", FACE, 2.5, "in_out_cubic")])
add(tl, 2.7, ["/title @a[r=64] title §f白石白夜", "/title @a[r=64] subtitle §7『わしはしがない刀鍛冶さ』",
              CINE.cam("^0.35 ^1.66 ^1.15", "^ ^1.63 ^"), pt("ember_burst", "~ ~1 ~"),
              sound("random.anvil_land", 0.5, 64), sound("game.player.attack.strong", 0.5, 64)])
add(tl, 3.3, [say("§f白石白夜§7「……さて。少し、付き合ってもらおうか」")])
add(tl, 3.9, [CINE.cam("^ ^2 ^6", FACE, 0.4, "out_expo")])
add(tl, 4.3, [CINE.fade(0, 0.05, 0.3, (255, 255, 255))] + CINE.end())
skill(30, "登場", 4.4, tl)

# 31 終焉化（HP60%）
tl = {}
add(tl, 0, CINE.begin(5) + ["/tp @s ~ ~ ~ facing %s" % ANYONE, CINE.cam("^2.6 ^0.3 ^3", "^ ^1.4 ^"),
                            CINE.fade(0, 0.1, 0.4, (120, 0, 0)), sound("mob.wither.spawn", 0.6, 64),
                            pt("charge_red", "~ ~1 ~"), "/effect @s regeneration 10 2 true"])
for i in range(5):
    add(tl, 0.2 + i * 0.45, [pt("fire_jet", q) for q in ring_pts(3, 8, 0)]
        + [sound("note.bass", 0.5 + 0.1 * i, 64), shake(0.1 + 0.05 * i, 0.4, 32)])
add(tl, 1.2, [CINE.cam("^-2.6 ^0.7 ^3", "^ ^1.4 ^", 1.5, "in_out_sine")])
add(tl, 2.8, [CINE.cam("^ ^9 ^3.5", "^ ^0.5 ^"), "/title @a[r=64] title §4§l終焉化",
              "/title @a[r=64] subtitle §7――今まで斬ってきた全てを、この身に", "/summon byakuya:blast ~ ~0.5 ~",
              pt("shockwave_big_red", "~ ~0.1 ~"), pt("ember_burst", "~ ~1 ~"),
              "/particle minecraft:huge_explosion_emitter ~ ~1 ~", sound("mob.enderdragon.growl", 0.7, 64),
              shake(1.5, 0.8, 48)] + [pt("fire_pillar", q) for q in ring_pts(6, 10, 0)])
add(tl, 3.8, [CINE.cam("^0.5 ^1.62 ^1.3", "^ ^1.6 ^"), say("§f白石白夜§7「……ここからは、手加減なしだ」")])
add(tl, 4.8, [CINE.fade(0, 0.05, 0.3, (255, 80, 40))] + CINE.end())
skill(31, "終焉化", 5.0, tl)

# 32 宿敵（電子 独と出会ったとき・一度だけ）: 切り返しの会話カット
tl = {}
add(tl, 0, CINE.begin(9) + ["/tag @s add byakuya_met", "/tp @s ~ ~ ~ facing %s" % HITORI,
                            "/event entity %s hitori:rival_cut" % HITORI,
                            CINE.cam("^-1 ^2.1 ^-2.8", HITORI), CINE.fade(0, 0.2, 0.6),
                            "/title @a[r=64] title §c§l宿 敵", "/title @a[r=64] subtitle §f白石白夜 §7VS §b電子 独",
                            sound("mob.wither.spawn", 1.2, 64), sound("random.glass", 0.5, 64)])
add(tl, 1.2, [say("§f白石白夜§7「……妙な気配だと思ったら。独、お前さんか」")])
add(tl, 2.6, [CINE.cam("^1 ^2 ^-2.6", BOSS, run_as=HITORI), say("§b電子 独§7「あ、白夜さん。……ごめんね。今日は“敵”なんだ」"),
              "/execute as %s at @s run particle hitori:noise_burst ~ ~1 ~" % HITORI])
add(tl, 4.6, [CINE.cam("^0.6 ^1.7 ^1.5", FACE), sound("random.anvil_use", 0.6, 48),
              say("§f白石白夜§7「バグだか何だか知らないが……わしの刀で、直してやるよ」")])
add(tl, 6.4, [CINE.cam("^-0.5 ^1.7 ^1.4", "^ ^1.6 ^", run_as=HITORI),
              say("§b電子 独§7「直せるなら、やってみなよ。――ついてこれる？」"),
              "/execute as %s at @s run particle hitori:noise_big ~ ~1 ~" % HITORI])
add(tl, 8.0, [CINE.cam("^3 ^9 ^-5", HITORI), "/title @a[r=64] title §c§lFIGHT!", pt("shockwave_big_red", "~ ~0.1 ~"),
              "/execute at %s run particle hitori:shockwave_big ~ ~0.1 ~" % HITORI, sound("random.explode", 0.8, 64),
              shake(1.0, 0.5, 48)])
add(tl, 8.9, [CINE.fade(0, 0.05, 0.3, (255, 255, 255))] + CINE.end())
skill(32, "宿敵", 9.0, tl)

# 20 最終演技（HP25%で一度だけ）: カメラワーク付き
tl = {}
add(tl, 0, CINE.begin(6) + ["/tp @s ~ ~ ~ facing %s" % ANYONE, CINE.cam("^0.35 ^1.66 ^1.2", "^ ^1.62 ^"),
                            CINE.fade(0, 0.3, 1.0), "/title @a[r=64] title §4§l最終演技",
                            "/title @a[r=64] subtitle §7――彼の全てを賭けた技", "/effect %s darkness 11 0 true" % p(48),
                            sound("mob.wither.spawn", 0.5, 64), "/fog @a[r=64] push byakuya:final_fog byakuya_final",
                            pt("petal_storm"), pt("shockwave_big_red", "~ ~0.1 ~")])
add(tl, 1.4, [CINE.cam("^3 ^0.4 ^1.3", "^ ^0.9 ^"), say("§f白石白夜§7「わしは……どこまでいっても『人間』でね」")])
add(tl, 2.4, [CINE.cam("^-3 ^1.4 ^2.4", FACE, 1.6, "in_out_sine")])
add(tl, 3.6, [say("§f白石白夜§7「だからこそ、届く刃がある」")])
add(tl, 4.2, [CINE.cam("^ ^14 ^7", "^ ^1 ^")] + [pt("ember_burst", q) for q in ring_pts(8, 8, 0.5)])
add(tl, 5.2, [CINE.cam("^ ^2.3 ^2.4", "^ ^2.1 ^", 0.5, "in_expo")])
add(tl, 5.8, [CINE.fade(0, 0.05, 0.25, (255, 255, 255))] + CINE.end()
    + ["/title @a[r=64] actionbar §c§l16ブロック以上離れろ……！", say("§f白石白夜§7「――受けてみな、お前さん」")])
for i in range(7):
    t = 6.0 + i * 0.5
    add(tl, t, [pt("ember_burst", q) for q in ring_pts(9 - i * 1.0, 6, 0.5)]
        + [sound("note.bass", 0.5 + i * 0.12, 48), pt("charge_red", "~ ~1.5 ~"), at_players(48, "warn_red", "~ ~0.1 ~"),
           shake(0.1 + i * 0.05, 0.5, 48)])
add(tl, 8.5, [pt("charge_white", "~ ~2 ~"), sound("mob.warden.sonic_charge", 0.5, 64)])
add(tl, 9.3, [sound("random.explode", 0.4, 64), sound("mob.enderdragon.growl", 0.6, 64),
              "/damage %s 32 entity_attack entity @s" % p(16), "/summon byakuya:blast ~ ~0.5 ~ byakuya:big",
              pt("big_slash_red", "~ ~1.5 ~"), pt("big_slash_white", "~ ~1.5 ~"), pt("big_slash_red", "~ ~1.5 ~"),
              pt("shockwave_big_red", "~ ~0.1 ~"), pt("shockwave_big_white", "~ ~0.1 ~"),
              "/particle minecraft:huge_explosion_emitter ~ ~1 ~", shake(2.5, 1.2, 64)]
    + [pt("fire_pillar", q) for q in ring_pts(6, 10, 0)]
    + ["/particle minecraft:huge_explosion_emitter %s" % q for q in ring_pts(12, 10, 1)])
add(tl, 9.35, CINE.begin(1.1, lock=False) + [CINE.cam("^ ^11 ^11", "^ ^ ^")])
add(tl, 9.6, [pt("ember_burst", q) for q in ring_pts(14, 12, 1)])
add(tl, 10.4, CINE.end())
add(tl, 10.5, [say("§f白石白夜§7「……まだ立ってるのかい。いいねぇ」"), "/fog @a[r=64] remove byakuya_final"])
skill(20, "最終演技", 10.8, tl)

CINE_V = [20, 30, 31, 32]

# 撃破カットシーン（監督役の見えないエンティティが再生する）
DEATH = {}
add(DEATH, 0, CINE.begin(6) + [CINE.cam("~3 ~1.3 ~3", "~ ~1 ~"), CINE.fade(0, 0.3, 1.0, (255, 255, 255)),
                              pt("petal_storm"), "/playsound random.totem @a[r=64] ~ ~ ~ 1 0.8",
                              "/fog @a[r=64] remove byakuya_final"])
add(DEATH, 0.1, [CINE.cam("~-3 ~1.6 ~3", "~ ~1 ~", 1.8, "linear")])
add(DEATH, 0.8, [say("§f白石白夜§7「……いい腕だ。人間の意地、確かに見せてもらったよ、お前さん」")])
add(DEATH, 1.9, [CINE.cam("~-3 ~2.2 ~-3", "~ ~1 ~", 1.8, "linear")])
add(DEATH, 3.0, [say("§f白石白夜§7「……さて。帰って、団子でも食うかね」"), pt("petal_burst", "~ ~1 ~")])
add(DEATH, 3.7, [CINE.cam("~ ~7 ~-2", "~ ~0.5 ~", 1.4, "in_out_sine")])
add(DEATH, 4.6, [pt("petal_storm"), pt("petal_burst", "~ ~1 ~"), pt("afterimage", "~ ~0.9 ~")])
add(DEATH, 5.3, [CINE.fade(0, 0.1, 0.6, (255, 255, 255))] + CINE.end())
add(DEATH, 5.35, ["/title @a[r=64] title §6§l討伐成功", "/title @a[r=64] subtitle §7白石白夜を倒した",
                   "/playsound random.levelup @a[r=64] ~ ~ ~ 1 0.8", "/playsound random.totem @a[r=64] ~ ~ ~ 0.5 1.6"])
add(DEATH, 5.5, ["@s byakuya:despawn"])
DEATH = {"%.2f" % k: v for k, v in sorted(DEATH.items())}


# ---------------------------------------------------------------------------
# v1.4: 大技のカットイン・着地や叩きつけの土煙
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
# 60 縮地・退: 後ろへ跳んで間合いを取り、飛ぶ斬撃で返す
tl = {0: [sound("mob.endermen.portal", 1.7, 30, 0.5), pt("afterimage", "~ ~0.9 ~")]}
footwork_steps(lambda t, c: add(tl, t, c), 0.05, 3, "^ ^ ^-1.7", NEAREST, [pt("afterimage", "~ ~0.9 ~")])
add(tl, 0.17, [pt("step_dust"), pt("dust_ring", "~ ~0.1 ~")])
add(tl, 0.5, waves(-10, 0, 10) + [sound("item.trident.riptide_1", 1.4, 30, 0.7),
                                  sound("game.player.attack.strong", 0.8, 30)])
skill(60, "縮地・退", 1.1, tl)
# 61 / 62 回り込み: 相手の右・左へ回り込みながら間合いを詰め、横から斬る
for v, side in ((61, 1), (62, -1)):
    tl = {0: [sound("mob.endermen.portal", 1.9, 24, 0.4), pt("afterimage", "~ ~0.9 ~")]}
    footwork_steps(lambda t, c: add(tl, t, c), 0.08, 7, "^%g ^ ^0.3" % (-1.25 * side), NEAREST,
                   [pt("afterimage", "~ ~0.9 ~")])
    add(tl, 0.56, [pt("slash_flat_white", "^ ^1.1 ^1.2"), pt("slash_white", "^ ^1.2 ^1.5"),
                   sound("game.player.attack.strong", 0.6, 30), sound("item.trident.riptide_1", 1.7, 30, 0.5),
                   "/execute positioned ^ ^1 ^1.6 run damage @a[r=2.3,m=!creative] 12 entity_attack entity @s",
                   shake(0.4, 0.25, 10)] + impact("^ ^ ^1.6"))
    skill(v, "回り込み", 1.3, tl)


cutin_into(12, 0.0, 0.8, "^0.8 ^1.3 ^1.3", "^-0.2 ^1.2 ^0.2", "§0§l無刀 無残")
cutin_into(23, 0.0, 0.7, "^ ^8 ^4", "^ ^1 ^", "§4§l森羅万象")
for v, times in ((18, [1.3]), (24, [0.5, 1.1, 1.7, 2.3]), (20, [9.3]), (31, [2.8]), (6, [0.35]), (25, [4.4]),
                 (17, [1.4]), (4, [2.0]), (30, [2.7])):
    for t in times:
        patch(v, t, impact())
patch(18, 1.3, [pt("debris", q) for q in ring_pts(2.5, 4, 0)])


# ---------------------------------------------------------------------------
# Behavior Pack
# ---------------------------------------------------------------------------
def bp_manifest():
    return {
        "format_version": 2,
        "header": {"name": "白石白夜 ボス BP", "description": "ボス「白石白夜」を追加します（ビヘイビアパック）",
                   "uuid": UUID_BP_HEADER, "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "data", "uuid": UUID_BP_MODULE, "version": VERSION}],
        "dependencies": [{"uuid": UUID_RP_HEADER, "version": VERSION}],
    }


IMMUNE = ("fall", "fire", "fire_tick", "lava", "lightning", "drowning", "suffocation", "magic", "thorns",
          "block_explosion", "entity_explosion")
FOE = FOE_ANY   # プレイヤーと、ほかのボス


def damage_sensor():
    """通常時: 刀で受けて近接ダメージ 75%、飛び道具 40%。殴られるたびに受け流しの抽選"""
    triggers = [{"cause": "entity_attack", "damage_multiplier": 0.75,
                 "on_damage": {"filters": FOE, "event": "byakuya:on_hit"}}]
    triggers += [{"cause": c, "deal_damage": False} for c in IMMUNE]
    triggers.append({"cause": "projectile", "damage_multiplier": 0.4})
    return {"triggers": triggers}


def phase_group(skin, speed, dmg, timer):
    return {
        "minecraft:skin_id": {"value": skin},
        "minecraft:movement": {"value": speed},
        "minecraft:attack": {"damage": dmg, "effect_name": "slowness", "effect_duration": 2},
        "minecraft:timer": {"looping": True, "time": timer, "randomInterval": True,
                            "time_down_event": {"event": "byakuya:choose_skill", "target": "self"}},
    }


SENSORS = ["sensor_normal", "hopper_guard", "mikiri_guard", "cine_guard"]


def bp_entity():
    groups = {
        "phase_1": phase_group(0, 0.34, 14, [2.5, 4.0]),
        "phase_2": phase_group(1, 0.41, 18, [1.8, 3.0]),
        "phase_3": phase_group(2, 0.46, 24, [1.2, 2.2]),
        "sensor_normal": {"minecraft:damage_sensor": damage_sensor()},
        "hopper_guard": {"minecraft:damage_sensor": {"triggers": [
            {"cause": "all", "deal_damage": False, "on_damage": {"event": "byakuya:counter", "target": "self"}}]}},
        "cine_guard": {"minecraft:damage_sensor": {"triggers": [{"cause": "all", "deal_damage": False}]}},
        "mikiri_guard": {"minecraft:damage_sensor": {"triggers": [
            {"cause": "all", "deal_damage": False, "on_damage": {"event": "byakuya:mikiri_counter", "target": "self"}}]}},
        # AI（カットシーン中は外して、その場に止める）
        "ai": {
            "minecraft:behavior.float": {"priority": 0},
            "minecraft:behavior.melee_attack": {"priority": 2, "speed_multiplier": 1.3, "track_target": True,
                                                "reach_multiplier": 1.6},
            "minecraft:behavior.hurt_by_target": {"priority": 1},
            "minecraft:behavior.nearest_attackable_target": {
                "priority": 2, "must_see": False, "reselect_targets": True, "within_radius": 48,
                "entity_types": [
                    {"filters": {"test": "is_family", "subject": "other", "value": "player"}, "max_dist": 48},
                    rival_target("byakuya"),   # ほかのボス（独・ソフィア・東雲）
                    {"filters": {"test": "is_family", "subject": "other", "value": "irongolem"}, "max_dist": 24},
                ]},
            "minecraft:behavior.random_stroll": {"priority": 6, "speed_multiplier": 0.8},
            "minecraft:behavior.look_at_player": {"priority": 7, "look_distance": 16},
            "minecraft:behavior.random_look_around": {"priority": 8},
        },
    }
    split_melee(groups, "byakuya")   # 近接の構え / 遠距離の構え
    variants = [0] + sorted(SKILLS)
    for v in variants:
        groups["v_%d" % v] = {"minecraft:mark_variant": {"value": v}}
    all_v = ["v_%d" % v for v in variants]

    def set_variant(v, extra_add=None, extra_remove=None):
        return {"remove": {"component_groups": [g for g in all_v if g != "v_%d" % v] + (extra_remove or [])},
                "add": {"component_groups": ["v_%d" % v] + (extra_add or [])}}

    def cine(v, add_=(), remove_=()):
        """カットシーン開始: 無敵・AI 停止"""
        return set_variant(v, ["cine_guard"] + list(add_), [s for s in SENSORS if s != "cine_guard"] + ["ai"]
                           + list(remove_))

    not_cine = {"all_of": [{"test": "is_mark_variant", "operator": "!=", "value": c} for c in CINE_V]}

    events = {
        "minecraft:entity_spawned": {"add": {"component_groups": ["phase_1", "v_30", "cine_guard"]}},
        # 技が終わったとき（カットシーンに割り込まれたときは何もしない）
        "byakuya:skill_end": {"sequence": [{"filters": not_cine, **set_variant(
            0, ["sensor_normal"], ["hopper_guard", "mikiri_guard", "cine_guard"])}]},
        "byakuya:cine_end": set_variant(0, ["sensor_normal", "ai"], ["hopper_guard", "mikiri_guard", "cine_guard"]),
        "byakuya:counter": {"queue_command": {"command": [
            "damage @a[r=6,m=!creative] 6 thorns entity @s",
            "playsound random.anvil_land @a[r=30] ~ ~ ~ 0.7 1.8",
            "particle byakuya:spark_burst ~ ~1.2 ~",
            "particle byakuya:slash_cyan ~ ~1.2 ~",
            "particle byakuya:shockwave_cyan ~ ~0.1 ~",
        ]}},
        # 殴られたとき: 15% で「受け流し」（2秒間 80% 軽減 + 反撃 + 吹き飛ばし）
        "byakuya:on_hit": {"randomize": [
            {"weight": 15, "trigger": "byakuya:parry"},
            {"weight": 85, "queue_command": {"command": ["particle byakuya:spark_burst ~ ~1.2 ~"]}}]},
        "byakuya:parry": {"queue_command": {"command": [
            "effect @s resistance 2 3 true",
            "title @a[r=16] actionbar §b§l◆ 受け流し ◆",
            "particle byakuya:slash_cyan ~ ~1.2 ~", "particle byakuya:shockwave_cyan ~ ~0.1 ~",
            "playsound random.anvil_land @a[r=24] ~ ~ ~ 0.8 1.6",
            "damage @a[r=4,m=!creative] 6 entity_attack entity @s",
            "summon byakuya:blast ~ ~0.8 ~",
        ]}},
        "byakuya:phase2": cine(31, ["phase_2"], ["phase_1"]),
        "byakuya:final": cine(20, ["phase_3"], ["phase_1", "phase_2"]),
        "byakuya:rival_meet": {"sequence": [{"filters": {"test": "is_mark_variant", "value": 0}, **cine(32)}]},
    }

    for v in sorted(SKILLS):
        if v in CINE_V:
            continue
        if v == 8:
            events["byakuya:skill_8"] = set_variant(8, ["hopper_guard"], ["sensor_normal"])
        elif v == 19:
            events["byakuya:skill_19"] = set_variant(19, ["mikiri_guard"], ["sensor_normal"])
        else:
            events["byakuya:skill_%d" % v] = set_variant(v)

    # 見切り成功 → 背後へ回り込んで反撃
    events["byakuya:mikiri_counter"] = {"trigger": "byakuya:skill_end", "queue_command": {"command": [
        'tellraw @a[r=48] {"rawtext":[{"text":"§f白石白夜§7「――見切った」"}]}',
        "particle byakuya:afterimage ~ ~0.9 ~",
        "execute as @p[r=16,m=!creative] at @s positioned ^ ^ ^-1.8 run tp %s ~ ~ ~ facing @s" % BOSS,
        "particle byakuya:big_slash_white ~ ~1.2 ~",
        "particle byakuya:slash_flat_red ~ ~1 ~",
        "damage @a[r=4,m=!creative] 18 entity_attack entity @s",
        "playsound game.player.attack.strong @a[r=30] ~ ~ ~ 1 0.5",
        "playsound random.anvil_land @a[r=30] ~ ~ ~ 1 0.6",
        "camerashake add @a[r=12] 0.8 0.4 positional",
    ]}}

    # 武装解除はキャラシ通り成功率50%
    events["byakuya:try_disarm"] = {"randomize": [
        {"weight": 50, "trigger": "byakuya:skill_9"},
        {"weight": 50, "queue_command": {"command": [
            'tellraw @a[r=48] {"rawtext":[{"text":"§7【武装を解除する程度の能力】§8……失敗。§f白石白夜§7「おっと、今日は調子が悪いね」"}]}',
            "particle byakuya:shatter ~ ~1.5 ~"]}},
    ]}

    # 距離で技を選ぶ: 近い相手には近接技、離れた相手には遠距離技を多めに
    near1 = [1, 2, 3, 4, 5, 6, 8, "disarm", 10, 17, 17, 19, 22, 22, 13, 24, 27, 60, 60, 61, 62]   # 60〜62: 立ち回り
    far1 = [1, 2, 4, 5, 7, 13, 13, 14, 14, 15, 15, 16, 16, 18, 18, 24, 60]   # 60: 間合いを取って遠距離で返す
    near2 = near1 + [11, 11, 12, 12, 21, 17, 22, 25, 26, 27]
    far2 = far1 + [21, 13, 14, 15, 16, 18, 25, 26]
    near3 = near2 + [23, 23, 25, 26]
    far3 = far2 + [23, 23, 25]
    NEAR, FAR = stance_filters("byakuya_near")   # 近接の構えで敵が近い → 近距離の技 / それ以外 → 遠距離の技

    def rnd(lst):
        return [{"weight": 10, "trigger": "byakuya:try_disarm" if s == "disarm" else "byakuya:skill_%d" % s}
                for s in lst]

    base_f = [{"test": "is_mark_variant", "value": 0}, {"test": "has_target", "value": True}]
    seq = []
    for skin, near, far in ((0, near1, far1), (1, near2, far2), (2, near3, far3)):
        for cond, lst in ((NEAR, near), (FAR, far)):
            seq.append({"filters": {"all_of": base_f + [{"test": "is_skin_id", "value": skin}, cond]},
                        "randomize": rnd(lst)})
    events["byakuya:choose_skill"] = {"sequence": seq}

    # ほかのボスの演出（登場など）のあいだは一時停止して、お互いに手出ししない
    events.update(pause_events(not_cine))
    # 間合いの判断: 4 秒ごとに「近接の構え / 遠距離の構え」を選び直す（HP が減ると遠距離寄り）
    events.update(stance_events(not_cine, 70, 30, int(HP * 0.4)))
    apply_stance_groups(events)

    components = {
        "minecraft:type_family": {"family": ["byakuya", "boss", RIVAL_FAMILY, "monster", "mob"]},
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
        "minecraft:movement": {"value": 0.34},
        "minecraft:navigation.walk": {"can_path_over_water": True, "can_open_doors": True, "can_break_doors": True,
                                      "avoid_damage_blocks": True},
        "minecraft:follow_range": {"value": 48, "max": 64},
        "minecraft:attack": {"damage": 14},
        "minecraft:equipment": {"table": "loot_tables/entities/shiraishi_byakuya_equipment.json",
                                "slot_drop_chance": [{"slot": "slot.weapon.mainhand", "drop_chance": 0}]},
        "minecraft:loot": {"table": "loot_tables/entities/shiraishi_byakuya.json"},
        "minecraft:experience_reward": {"on_death": "800"},
        "minecraft:environment_sensor": {"triggers": [
            {"filters": {"all_of": [{"test": "actor_health", "operator": "<=", "value": PHASE2_HP},
                                    {"test": "is_skin_id", "value": 0}] + not_cine["all_of"]},
             "event": "byakuya:phase2"},
            {"filters": {"all_of": [{"test": "actor_health", "operator": "<=", "value": FINAL_HP},
                                    {"test": "is_skin_id", "value": 1}] + not_cine["all_of"]},
             "event": "byakuya:final"},
        ]},
    }

    return {
        "format_version": "1.21.0",
        "minecraft:entity": {
            "description": {
                "identifier": ID,
                "is_spawnable": True,
                "is_summonable": True,
                "is_experimental": False,
                "scripts": {"animate": ["skills", "upkeep", "death", "foe_tags", "stance"]},
                "animations": {
                    "foe_tags": "animation.byakuya.foe_tags", "stance": "animation.byakuya.stance_loop",
                    "skills": "controller.animation.byakuya.skills",
                    "death": "controller.animation.byakuya.death",
                    "upkeep": "animation.byakuya.upkeep",
                    "idle_loop": "animation.byakuya.idle_loop",
                    **{"skill_%d" % v: "animation.byakuya.skill_%d" % v for v in SKILLS},
                },
            },
            "component_groups": groups,
            "components": components,
            "events": events,
        },
    }


# ほかのボスと初めて会ったときのひとこと（独とは専用のカットシーン）
ENCOUNTER = {'sophia': '§f白石白夜§7「……神様、ねぇ。斬れるかどうか、試してみようか」', 'shinonome': '§f白石白夜§7「おや……ただの子どもじゃないね。悪いが、手加減はしないよ」', 'fuuka': '§f白石白夜§7「おや、怪盗のお嬢さんかい。……その銃、わしの刀より速いかね」'}


def bp_animations():
    a = {"animation.byakuya.skill_%d" % v: {"animation_length": length, "loop": False, "timeline": timeline}
         for v, (name, length, timeline) in SKILLS.items()}
    # 常に動く: 周りの人数に応じた防御（集団戦対策）
    a["animation.byakuya.upkeep"] = {"animation_length": 5.0, "loop": True, "timeline": {"0.50": [
        "/scoreboard players set @s byakuya_players 0",
        "/execute as @a[r=40,m=!creative] run scoreboard players add %s byakuya_players 1" % BOSS,
        "/execute if score @s byakuya_players matches 2 run effect @s resistance 6 0 true",
        "/execute if score @s byakuya_players matches 3 run effect @s resistance 6 1 true",
        "/execute if score @s byakuya_players matches 4.. run effect @s resistance 6 2 true"]}}
    # 待機中だけ動く: カメラの後片付けと、宿敵（電子 独）・ほかのボスの発見
    a["animation.byakuya.idle_loop"] = {"animation_length": 2.0, "loop": True, "timeline": {"1.00": CINE.end() + [
        "/execute if entity @s[tag=!byakuya_met] if entity @e[family=hitori,r=24] run event entity @s byakuya:rival_meet"],
        "1.50": encounter_cmds("byakuya", say, ENCOUNTER)}}
    # 常に動く: 敵の目印と「近くに敵がいる」タグ
    a["animation.byakuya.stance_loop"] = STANCE_ANIM   # 間合いの判断（4 秒ごと）
    a["animation.byakuya.foe_tags"] = foe_tag_anim(ID, "byakuya_near")
    return {"format_version": "1.10.0", "animations": a}


def bp_controllers():
    states = {"default": {"animations": ["idle_loop"],
                          "transitions": [{"skill_%d" % v: "q.mark_variant == %d" % v} for v in sorted(SKILLS)]}}
    for v in sorted(SKILLS):
        states["skill_%d" % v] = {
            "animations": ["skill_%d" % v],
            "transitions": [{"default": "q.all_animations_finished || q.mark_variant != %d" % v}],
            "on_exit": ["@s byakuya:%s" % ("cine_end" if v in CINE_V else "skill_end")],
        }
    return {"format_version": "1.10.0", "animation_controllers": {
        "controller.animation.byakuya.skills": {"initial_state": "default", "states": states},
        "controller.animation.byakuya.death": {"initial_state": "alive", "states": {
            "alive": {"transitions": [{"dead": "!q.is_alive"}]},
            "dead": {"on_entry": ["/summon byakuya:director ~ ~ ~", "/tag @a remove byakuya_sayanari",
                                  "/fog @a[r=64] remove byakuya_final"] + CINE.end()},
        }},
    }}


def bp_loot():
    drop = {"pools": [
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:iron_sword", "weight": 1, "functions": [
            {"function": "set_name", "name": "§c§l村正"},
            {"function": "set_lore", "lore": ["§7しがない刀鍛冶が打った一振り", "§8『炎を極め、刀を極めた』"]},
            {"function": "specific_enchants", "enchants": [
                {"id": "sharpness", "level": 5}, {"id": "fire_aspect", "level": 2},
                {"id": "unbreaking", "level": 3}, {"id": "looting", "level": 3}, {"id": "mending", "level": 1}]},
        ]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:iron_ingot", "weight": 1,
                                  "functions": [{"function": "set_count", "count": 20}]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:golden_apple", "weight": 1,
                                  "functions": [{"function": "set_count", "count": 6},
                                                {"function": "set_name", "name": "§e団子"}]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:enchanted_golden_apple", "weight": 1}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:totem_of_undying", "weight": 1}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:netherite_ingot", "weight": 1,
                                  "functions": [{"function": "set_count", "count": {"min": 1, "max": 3}}]}]},
    ]}
    equip = {"pools": [{"rolls": 1, "entries": [{"type": "item", "name": "minecraft:iron_sword", "weight": 1,
                                                 "functions": [{"function": "set_name", "name": "§c日本刀"},
                                                               {"function": "specific_enchants",
                                                                "enchants": [{"id": "sharpness", "level": 5}]}]}]}]}
    return drop, equip


# ---------------------------------------------------------------------------
# Resource Pack
# ---------------------------------------------------------------------------
def rp_manifest():
    return {
        "format_version": 2,
        "header": {"name": "白石白夜 ボス RP", "description": "ボス「白石白夜」を追加します（リソースパック）",
                   "uuid": UUID_RP_HEADER, "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUID_RP_MODULE, "version": VERSION}],
    }


def cube(origin, size, uv, inflate=0):
    c = {"origin": origin, "size": size, "uv": uv}
    if inflate:
        c["inflate"] = inflate
    return c


def rp_geometry():
    bones = [
        {"name": "root", "pivot": [0, 0, 0]},
        {"name": "body", "parent": "root", "pivot": [0, 24, 0], "cubes": [
            cube([-4, 12, -2], [8, 12, 4], [16, 16]), cube([-4, 12, -2], [8, 12, 4], [16, 32], 0.25)],
         "locators": {"body_center": [0, 18, 0]}},
        {"name": "head", "parent": "body", "pivot": [0, 24, 0], "cubes": [
            cube([-4, 24, -4], [8, 8, 8], [0, 0]), cube([-4, 24, -4], [8, 8, 8], [32, 0], 0.5)]},
        {"name": "rightArm", "parent": "body", "pivot": [-5, 22, 0], "cubes": [
            cube([-8, 12, -2], [4, 12, 4], [40, 16]), cube([-8, 12, -2], [4, 12, 4], [40, 32], 0.25)],
         "locators": {"right_hand": [-6, 11, 0], "reach": [-6, 5, -1.5]}},
        {"name": "rightItem", "parent": "rightArm", "pivot": [-6, 15, 1]},
        {"name": "leftArm", "parent": "body", "pivot": [5, 22, 0], "cubes": [
            cube([4, 12, -2], [4, 12, 4], [32, 48]), cube([4, 12, -2], [4, 12, 4], [48, 48], 0.25)],
         "locators": {"left_hand": [6, 11, 0]}},
        {"name": "rightLeg", "parent": "root", "pivot": [-1.9, 12, 0], "cubes": [
            cube([-3.9, 0, -2], [4, 12, 4], [0, 16]), cube([-3.9, 0, -2], [4, 12, 4], [0, 32], 0.25)],
         "locators": {"right_foot": [-2, 0, 0]}},
        {"name": "leftLeg", "parent": "root", "pivot": [1.9, 12, 0], "cubes": [
            cube([-0.1, 0, -2], [4, 12, 4], [16, 48]), cube([-0.1, 0, -2], [4, 12, 4], [0, 48], 0.25)],
         "locators": {"left_foot": [2, 0, 0]}},
    ]
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": "geometry.shiraishi_byakuya", "texture_width": 64, "texture_height": 64,
                        "visible_bounds_width": 3, "visible_bounds_height": 4, "visible_bounds_offset": [0, 1.5, 0]},
        "bones": bones}]}


def rp_entity():
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": smooth_client({
        "identifier": ID,
        "materials": {"default": "entity_alphatest"},
        "textures": {"default": "textures/entity/shiraishi_byakuya"},
        "geometry": {"default": "geometry.shiraishi_byakuya"},
        "render_controllers": ["controller.render.shiraishi_byakuya"],
        "enable_attachables": True,
        "spawn_egg": {"base_color": "#f0f0f0", "overlay_color": "#5c1414"},
        "particle_effects": anims.PARTICLE_MAP,
        "animations": anims.short_names(sorted(SKILLS)),
        "scripts": {"animate": ["main", "aura_ctrl", "attack_fx"]},
    })}}


def rp_render_controller():
    pulse = "0.10 + math.sin(q.life_time * 240) * 0.06"
    return {"format_version": "1.10.0", "render_controllers": {"controller.render.shiraishi_byakuya": {
        "geometry": "Geometry.default",
        "materials": [{"*": "Material.default"}],
        "textures": ["Texture.default"],
        "overlay_color": {"r": "1.0", "g": "q.skin_id >= 2 ? 0.05 : 0.35", "b": "0.05",
                          "a": "q.skin_id >= 2 ? 0.25 + math.sin(q.life_time * 360) * 0.05 : "
                               "(q.skin_id == 1 ? %s : 0.0)" % pulse},
    }}}


def lang():
    return "\n".join([
        "entity.%s.name=%s" % (ID, NAME),
        "item.spawn_egg.entity.%s.name=%sのスポーンエッグ" % (ID, NAME),
        "entity.byakuya:shadow.name=白夜の影",
        "entity.byakuya:slash_wave.name=飛ぶ斬撃",
        "entity.byakuya:homing_blade.name=追刃",
        "entity.byakuya:marker.name=目印",
        "entity.byakuya:blast.name=衝撃",
        "entity.byakuya:director.name=白石白夜",
        "pack.name=白石白夜 ボス",
        "pack.description=刀鍛冶「白石白夜」ボスアドオン",
        "",
    ])


def main():
    skin = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RP, "textures/entity/shiraishi_byakuya.png")
    skin_bytes = open(skin, "rb").read()
    for d in (BP, RP, DIST):
        if os.path.isdir(d):
            shutil.rmtree(d)
    # BP
    write(os.path.join(BP, "manifest.json"), bp_manifest())
    write(os.path.join(BP, "entities/shiraishi_byakuya.json"), bp_entity())
    boss_anims_bp = bp_animations()
    write(os.path.join(BP, "animations/shiraishi_byakuya.animation.json"), boss_anims_bp)
    write(os.path.join(BP, "animation_controllers/shiraishi_byakuya.ac.json"), bp_controllers())
    # 補助エンティティ（斬撃波・追尾刀・目印・影分身）
    wave, wave_a = summons.bp_slash_wave()
    blade, blade_a, blade_c = summons.bp_homing_blade()
    marker, marker_a = summons.bp_marker()
    for name, data in (("slash_wave", wave), ("homing_blade", blade), ("marker", marker),
                       ("shadow", summons.bp_shadow()), ("blast", summons.bp_blast()),
                       ("director", summons.bp_director())):
        write(os.path.join(BP, "entities/%s.json" % name), data)
    summ_anims = {**wave_a, **blade_a, **marker_a,
                  "animation.byakuya.director.death": {"animation_length": 5.6, "loop": False, "timeline": DEATH}}
    write(os.path.join(BP, "animations/summons.animation.json"),
          {"format_version": "1.10.0", "animations": summ_anims})
    write(os.path.join(BP, "animation_controllers/summons.ac.json"),
          {"format_version": "1.10.0", "animation_controllers": blade_c})
    drop, equip = bp_loot()
    write(os.path.join(BP, "loot_tables/entities/shiraishi_byakuya.json"), drop)
    write(os.path.join(BP, "loot_tables/entities/shiraishi_byakuya_equipment.json"), equip)
    for lc in ("ja_JP", "en_US"):
        write(os.path.join(BP, "texts/%s.lang" % lc), lang())
    write(os.path.join(BP, "texts/languages.json"), ["ja_JP", "en_US"])
    # RP
    tex_dst = os.path.join(RP, "textures/entity/shiraishi_byakuya.png")
    os.makedirs(os.path.dirname(tex_dst), exist_ok=True)
    open(tex_dst, "wb").write(skin_bytes)
    write(os.path.join(RP, "manifest.json"), rp_manifest())
    write(os.path.join(RP, "entity/shiraishi_byakuya.entity.json"), rp_entity())
    write(os.path.join(RP, "models/entity/shiraishi_byakuya.geo.json"), rp_geometry())
    ra = anims.all_animations()
    add_arc_trails(ra["animations"], {"sword_trail"}, arc="arc")
    add_arc_trails(ra["animations"], {"sword_trail_red"}, arc="arc_red")
    bake_smooth(ra["animations"], step=SMOOTH_STEP)
    vectorize_animations(ra["animations"])
    write(os.path.join(RP, "animations/shiraishi_byakuya.animation.json"), ra)
    write(os.path.join(RP, "animation_controllers/shiraishi_byakuya.ac.json"), anims.controllers(sorted(SKILLS)))
    write(os.path.join(RP, "render_controllers/shiraishi_byakuya.rc.json"), rp_render_controller())
    for name, data in fx.build_particles().items():
        write(os.path.join(RP, "particles/%s.json" % name), data)
    for name, im in fx.build_textures().items():
        os.makedirs(os.path.join(RP, "textures/particle"), exist_ok=True)
        im.save(os.path.join(RP, "textures/particle/%s.png" % name))
    boss_anims = anims.short_names(sorted(SKILLS))
    for name, data in summons.rp_clients(boss_anims).items():
        if name == "shadow":
            data["minecraft:client_entity"]["description"]["particle_effects"].update(anims.PARTICLE_MAP)
            smooth_client(data["minecraft:client_entity"]["description"])
        write(os.path.join(RP, "entity/%s.entity.json" % name), data)
    write(os.path.join(RP, "models/entity/byakuya_slash_wave.geo.json"), summons.geo_slash_wave())
    write(os.path.join(RP, "models/entity/byakuya_blade.geo.json"), summons.geo_blade())
    write(os.path.join(RP, "models/entity/byakuya_empty.geo.json"), summons.geo_empty())
    write(os.path.join(RP, "render_controllers/summons.rc.json"), summons.rc_simple())
    write(os.path.join(RP, "animations/summons.animation.json"),
          {"format_version": "1.10.0",
           "animations": vectorize_animations(bake_smooth(summons.rp_animations(), step=SMOOTH_STEP))})
    for name, im in fx.build_entity_textures().items():
        im.save(os.path.join(RP, "textures/entity/%s.png" % name))
    for name, data in fx.build_fogs().items():
        write(os.path.join(RP, "fogs/%s.json" % name), data)
    for lc in ("ja_JP", "en_US"):
        write(os.path.join(RP, "texts/%s.lang" % lc), lang())
    write(os.path.join(RP, "texts/languages.json"), ["ja_JP", "en_US"])
    for d in (RP, BP):
        open(os.path.join(d, "pack_icon.png"), "wb").write(skin_bytes)

    # .mcaddon
    # 声・足音・守りの反応・瀕死の演出
    brushup_files(BP, RP, dict(id=ID, ns="byakuya", prop="byakuya:react", react_events=["byakuya:parry", "byakuya:mikiri_counter"],
             react_anim={"loop": True, "bones": {   # 受け流し: 刀で受け止めて、少し押し下がる
                 "rightArm": {"rotation": ["-v.react * 70", "-v.react * 35", 0]},
                 "body": {"rotation": [0, "v.react * 15", 0]}, "root": {"position": [0, 0, "v.react * 1.2"]}}},
             prefix="animation.byakuya", main_ctrl="controller.animation.byakuya.main", glow="byakuya_glow", pitch=0.85))
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "ShiraishiByakuya_Boss.mcaddon")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for pack, arc in ((BP, "Byakuya_BP"), (RP, "Byakuya_RP")):
            for dp, _, fs in sorted(os.walk(pack)):
                for f in sorted(fs):
                    full = os.path.join(dp, f)
                    z.write(full, os.path.join(arc, os.path.relpath(full, pack)))
    print("built", out)


if __name__ == "__main__":
    main()
