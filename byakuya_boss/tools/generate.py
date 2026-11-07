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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BP = os.path.join(ROOT, "Byakuya_BP")
RP = os.path.join(ROOT, "Byakuya_RP")
DIST = os.path.join(ROOT, "dist")

ID = "byakuya:shiraishi_byakuya"
NAME = "白石白夜"
VERSION = [1, 1, 0]
MIN_ENGINE = [1, 21, 0]

UUID_BP_HEADER = "293c6dbc-978c-4439-aa05-c2fa6e63c99d"
UUID_BP_MODULE = "82d49302-2ab7-4291-a50c-143a1fe02427"
UUID_RP_HEADER = "7a4ebd1f-167b-4145-a8ef-20e335975e29"
UUID_RP_MODULE = "05d778a7-bb90-40f4-8dd9-6e63d1913bf0"

HP = 800
PHASE2_HP = 400   # 50% で終焉化
FINAL_HP = 160    # 20% で最終演技

random.seed(1201)  # 誕生日 12/1


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

# 20 最終演技（HP20%で一度だけ）
tl = {}
add(tl, 0, ["/title @a[r=64] title §4§l最終演技", "/title @a[r=64] subtitle §7――彼の全てを賭けた技",
            "/effect %s darkness 8 0 true" % p(48), sound("mob.wither.spawn", 0.5, 64),
            "/fog @a[r=64] push byakuya:final_fog byakuya_final", pt("petal_storm"),
            pt("shockwave_big_red", "~ ~0.1 ~")])
add(tl, 1.5, [say("§f白石白夜§7「わしは……どこまでいっても『人間』でね」")])
add(tl, 3.0, [say("§f白石白夜§7「だからこそ届く刃がある。――受けてみな、お前さん」"),
              "/title @a[r=64] actionbar §c§l16ブロック以上離れろ……！", pt("petal_storm")])
for i in range(10):
    t = 1.0 + i * 0.5
    add(tl, t, [pt("ember_burst", q) for q in ring_pts(9 - i * 0.8, 6, 0.5)] +
        [sound("note.bass", 0.5 + i * 0.1, 48), pt("charge_red", "~ ~1.5 ~")])
    if i >= 4:
        add(tl, t, [at_players(48, "warn_red", "~ ~0.1 ~"), shake(0.1 + i * 0.04, 0.5, 48)])
add(tl, 5.5, [pt("charge_white", "~ ~2 ~"), sound("mob.warden.sonic_charge", 0.5, 64)])
add(tl, 6.45, [sound("random.explode", 0.4, 64), sound("mob.enderdragon.growl", 0.6, 64),
               "/damage %s 30 entity_attack entity @s" % p(16),
               pt("big_slash_red", "~ ~1.5 ~"), pt("big_slash_white", "~ ~1.5 ~"), pt("big_slash_red", "~ ~1.5 ~"),
               pt("shockwave_big_red", "~ ~0.1 ~"), pt("shockwave_big_white", "~ ~0.1 ~"),
               "/particle minecraft:huge_explosion_emitter ~ ~1 ~", shake(2.5, 1.2, 64)]
    + [pt("fire_pillar", q) for q in ring_pts(6, 10, 0)]
    + ["/particle minecraft:huge_explosion_emitter %s" % q for q in ring_pts(12, 10, 1)])
add(tl, 6.8, [pt("ember_burst", q) for q in ring_pts(14, 12, 1)])
add(tl, 7.2, [say("§f白石白夜§7「……まだ立ってるのかい。いいねぇ」"),
              "/fog @a[r=64] remove byakuya_final"])
skill(20, "最終演技", 7.5, tl)


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


def damage_sensor():
    triggers = []
    for cause in ("fall", "fire", "fire_tick", "lava", "lightning", "drowning", "suffocation", "magic", "thorns",
                  "block_explosion"):
        triggers.append({"cause": cause, "deal_damage": False})
    triggers.append({"cause": "projectile", "damage_multiplier": 0.5})
    return {"triggers": triggers}


def phase_group(skin, speed, dmg, timer):
    return {
        "minecraft:skin_id": {"value": skin},
        "minecraft:movement": {"value": speed},
        "minecraft:attack": {"damage": dmg, "effect_name": "slowness", "effect_duration": 2},
        "minecraft:timer": {"looping": True, "time": timer, "randomInterval": True,
                            "time_down_event": {"event": "byakuya:choose_skill", "target": "self"}},
    }


def bp_entity():
    groups = {
        "phase_1": phase_group(0, 0.33, 12, [3.0, 5.0]),
        "phase_2": phase_group(1, 0.4, 16, [2.0, 3.5]),
        "phase_3": phase_group(2, 0.44, 20, [1.5, 2.5]),
        "sensor_normal": {"minecraft:damage_sensor": damage_sensor()},
        "hopper_guard": {"minecraft:damage_sensor": {"triggers": [
            {"cause": "all", "deal_damage": False, "on_damage": {"event": "byakuya:counter", "target": "self"}}]}},
        "final_guard": {"minecraft:damage_sensor": {"triggers": [{"cause": "all", "deal_damage": False}]}},
    }
    variants = [0] + sorted(SKILLS)
    for v in variants:
        groups["v_%d" % v] = {"minecraft:mark_variant": {"value": v}}
    all_v = ["v_%d" % v for v in variants]

    def set_variant(v, extra_add=None, extra_remove=None):
        return {"remove": {"component_groups": [g for g in all_v if g != "v_%d" % v] + (extra_remove or [])},
                "add": {"component_groups": ["v_%d" % v] + (extra_add or [])}}

    events = {
        "minecraft:entity_spawned": {
            "add": {"component_groups": ["phase_1", "v_0", "sensor_normal"]},
            "queue_command": {"command": [
                "title @a[r=64] title §f白石白夜",
                "title @a[r=64] subtitle §7『わしはしがない刀鍛冶さ』",
                "playsound mob.wither.spawn @a[r=64] ~ ~ ~ 1 0.8",
                "particle byakuya:shockwave_big_white ~ ~0.1 ~",
                "particle byakuya:petal_storm ~ ~ ~",
                "particle byakuya:afterimage ~ ~0.9 ~",
            ]},
        },
        "byakuya:skill_end": {
            "remove": {"component_groups": all_v + ["hopper_guard", "final_guard"]},
            "add": {"component_groups": ["v_0", "sensor_normal"]},
        },
        "byakuya:counter": {"queue_command": {"command": [
            "damage @a[r=6,m=!creative] 6 thorns entity @s",
            "playsound random.anvil_land @a[r=30] ~ ~ ~ 0.7 1.8",
            "particle byakuya:spark_burst ~ ~1.2 ~",
            "particle byakuya:slash_cyan ~ ~1.2 ~",
            "particle byakuya:shockwave_cyan ~ ~0.1 ~",
        ]}},
        "byakuya:phase2": {
            "remove": {"component_groups": ["phase_1"]},
            "add": {"component_groups": ["phase_2"]},
            "queue_command": {"command": [
                "title @a[r=64] title §4終焉化",
                "title @a[r=64] subtitle §7――今まで斬ってきた全てを、この身に",
                "playsound mob.enderdragon.growl @a[r=64] ~ ~ ~ 1 0.7",
                "effect @s regeneration 8 2 true",
                "effect @s resistance 8 1 true",
                "particle minecraft:huge_explosion_emitter ~ ~1 ~",
                "particle byakuya:shockwave_big_red ~ ~0.1 ~",
                "particle byakuya:fire_pillar ~ ~ ~",
                "particle byakuya:ember_burst ~ ~1 ~",
                "camerashake add @a[r=32] 1.0 0.8 positional",
            ]},
        },
        "byakuya:final": set_variant(20, ["final_guard", "phase_3"], ["phase_1", "phase_2", "sensor_normal"]),
    }

    for v in sorted(SKILLS):
        if v == 20:
            continue
        if v == 8:
            events["byakuya:skill_8"] = set_variant(8, ["hopper_guard"], ["sensor_normal"])
        else:
            events["byakuya:skill_%d" % v] = set_variant(v)

    # 武装解除はキャラシ通り成功率50%
    events["byakuya:try_disarm"] = {"randomize": [
        {"weight": 50, "trigger": "byakuya:skill_9"},
        {"weight": 50, "queue_command": {"command": [
            'tellraw @a[r=48] {"rawtext":[{"text":"§7【武装を解除する程度の能力】§8……失敗。§f白石白夜§7「おっと、今日は調子が悪いね」"}]}',
            "particle byakuya:shatter ~ ~1.5 ~"]}},
    ]}

    p1 = [1, 2, 3, 4, 5, 6, 7, 8, "disarm", 10]
    p2 = p1 + [11, 11, 12, 12]

    def rnd(lst):
        return [{"weight": 10, "trigger": "byakuya:try_disarm" if s == "disarm" else "byakuya:skill_%d" % s}
                for s in lst]

    base_f = [{"test": "is_mark_variant", "value": 0}, {"test": "has_target", "value": True}]
    events["byakuya:choose_skill"] = {"sequence": [
        {"filters": {"all_of": base_f + [{"test": "is_skin_id", "value": 0}]}, "randomize": rnd(p1)},
        {"filters": {"all_of": base_f + [{"test": "is_skin_id", "operator": "!=", "value": 0}]}, "randomize": rnd(p2)},
    ]}

    components = {
        "minecraft:type_family": {"family": ["byakuya", "boss", "monster", "mob"]},
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
        "minecraft:navigation.walk": {"can_path_over_water": True, "can_open_doors": True, "can_break_doors": True,
                                      "avoid_damage_blocks": True},
        "minecraft:follow_range": {"value": 48, "max": 64},
        "minecraft:attack": {"damage": 12},
        "minecraft:equipment": {"table": "loot_tables/entities/shiraishi_byakuya_equipment.json",
                                "slot_drop_chance": [{"slot": "slot.weapon.mainhand", "drop_chance": 0}]},
        "minecraft:loot": {"table": "loot_tables/entities/shiraishi_byakuya.json"},
        "minecraft:experience_reward": {"on_death": "500"},
        "minecraft:environment_sensor": {"triggers": [
            {"filters": {"all_of": [{"test": "actor_health", "operator": "<=", "value": PHASE2_HP},
                                    {"test": "is_skin_id", "value": 0}]},
             "event": "byakuya:phase2"},
            {"filters": {"all_of": [{"test": "actor_health", "operator": "<=", "value": FINAL_HP},
                                    {"test": "is_skin_id", "value": 1},
                                    {"test": "is_mark_variant", "value": 0}]},
             "event": "byakuya:final"},
        ]},
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.melee_attack": {"priority": 2, "speed_multiplier": 1.3, "track_target": True,
                                            "reach_multiplier": 1.6},
        "minecraft:behavior.hurt_by_target": {"priority": 1},
        "minecraft:behavior.nearest_attackable_target": {
            "priority": 2, "must_see": False, "reselect_targets": True, "within_radius": 48,
            "entity_types": [
                {"filters": {"test": "is_family", "subject": "other", "value": "player"}, "max_dist": 48},
                {"filters": {"test": "is_family", "subject": "other", "value": "irongolem"}, "max_dist": 24},
            ]},
        "minecraft:behavior.random_stroll": {"priority": 6, "speed_multiplier": 0.8},
        "minecraft:behavior.look_at_player": {"priority": 7, "look_distance": 16},
        "minecraft:behavior.random_look_around": {"priority": 8},
    }

    return {
        "format_version": "1.21.0",
        "minecraft:entity": {
            "description": {
                "identifier": ID,
                "is_spawnable": True,
                "is_summonable": True,
                "is_experimental": False,
                "scripts": {"animate": ["skills", "death"]},
                "animations": {
                    "skills": "controller.animation.byakuya.skills",
                    "death": "controller.animation.byakuya.death",
                    **{"skill_%d" % v: "animation.byakuya.skill_%d" % v for v in SKILLS},
                },
            },
            "component_groups": groups,
            "components": components,
            "events": events,
        },
    }


def bp_animations():
    return {"format_version": "1.10.0", "animations": {
        "animation.byakuya.skill_%d" % v: {"animation_length": length, "loop": False, "timeline": timeline}
        for v, (name, length, timeline) in SKILLS.items()}}


def bp_controllers():
    states = {"default": {"transitions": [{"skill_%d" % v: "q.mark_variant == %d" % v} for v in sorted(SKILLS)]}}
    for v in sorted(SKILLS):
        states["skill_%d" % v] = {
            "animations": ["skill_%d" % v],
            "transitions": [{"default": "q.all_animations_finished || q.mark_variant != %d" % v}],
            "on_exit": ["@s byakuya:skill_end"],
        }
    return {"format_version": "1.10.0", "animation_controllers": {
        "controller.animation.byakuya.skills": {"initial_state": "default", "states": states},
        "controller.animation.byakuya.death": {"initial_state": "alive", "states": {
            "alive": {"transitions": [{"dead": "!q.is_alive"}]},
            "dead": {"on_entry": [
                say("§f白石白夜§7「……いい腕だ。人間の意地、確かに見せてもらったよ、お前さん」"),
                "/playsound random.totem @a[r=64] ~ ~ ~ 1 0.8",
                "/fog @a[r=64] remove byakuya_final",
                "/particle byakuya:petal_storm ~ ~ ~",
                "/particle byakuya:shockwave_big_white ~ ~0.1 ~",
                "/particle byakuya:afterimage ~ ~0.9 ~",
                "/particle minecraft:totem_particle ~ ~1 ~",
            ]},
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
         "locators": {"right_hand": [-6, 11, 0]}},
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
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": {
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
    }}}


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
    write(os.path.join(BP, "animations/shiraishi_byakuya.animation.json"), bp_animations())
    write(os.path.join(BP, "animation_controllers/shiraishi_byakuya.ac.json"), bp_controllers())
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
    write(os.path.join(RP, "animations/shiraishi_byakuya.animation.json"), anims.all_animations())
    write(os.path.join(RP, "animation_controllers/shiraishi_byakuya.ac.json"), anims.controllers(sorted(SKILLS)))
    write(os.path.join(RP, "render_controllers/shiraishi_byakuya.rc.json"), rp_render_controller())
    for name, data in fx.build_particles().items():
        write(os.path.join(RP, "particles/%s.json" % name), data)
    for name, im in fx.build_textures().items():
        os.makedirs(os.path.join(RP, "textures/particle"), exist_ok=True)
        im.save(os.path.join(RP, "textures/particle/%s.png" % name))
    for name, data in fx.build_fogs().items():
        write(os.path.join(RP, "fogs/%s.json" % name), data)
    for lc in ("ja_JP", "en_US"):
        write(os.path.join(RP, "texts/%s.lang" % lc), lang())
    write(os.path.join(RP, "texts/languages.json"), ["ja_JP", "en_US"])
    for d in (RP, BP):
        open(os.path.join(d, "pack_icon.png"), "wb").write(skin_bytes)

    # .mcaddon
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
