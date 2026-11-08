# -*- coding: utf-8 -*-
"""月島 風花（つきしま ふうか）ボスアドオン生成スクリプト.

使い方:
  python3 fuuka_boss/tools/generate.py [skin.png]
  python3 fuuka_boss/tools/generate.py --tusk <Stand_disc の .mcaddon>   # 個人用（スタンドの見た目を差し替え）

スキンを省略すると、前回のスキン（なければ仮のスキン）を使います。
--tusk を付けると、通常版に加えて fuuka_boss/personal/ に個人用の .mcaddon も作ります
（スタンドの見た目だけ、手元のアドオンのファイルから読み込みます。リポジトリには入りません）。
"""
import argparse
import json
import math
import os
import re
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fanims  # noqa: E402
import ffx  # noqa: E402
from cine import (brushup_files, FOE_ANY, RIVAL_FAMILY, Cine, add_rival, aim_at_foes, bake_smooth,  # noqa: E402
                  encounter_cmds, foe_tag_anim, footwork_steps, near_filters, pause_events, rival_target,
                  smooth_client, split_dashes, stance_group, vectorize_animations)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BP = os.path.join(ROOT, "Fuuka_BP")
RP = os.path.join(ROOT, "Fuuka_RP")
DIST = os.path.join(ROOT, "dist")
PERSONAL = os.path.join(ROOT, "personal")

ID = "fuuka:tsukishima_fuuka"
NAME = "月島 風花"
VERSION = [1, 4, 0]
MIN_ENGINE = [1, 21, 0]
UUID_BP_HEADER = "760895b1-a50e-4fa9-9a8f-b0b6b578a3ef"
UUID_BP_MODULE = "91dcd908-5ce6-462a-ac32-57279a769143"
UUID_RP_HEADER = "63c99bab-d14d-4b80-89e5-c056b564f79c"
UUID_RP_MODULE = "77569f40-df30-41fa-ae9b-c22cad8da8cf"

HP = 1500
PHASE2_HP = 900      # 60%: 花鳥風月
PHASE3_HP = 450      # 30%: 鳥獣戯画
OBJ_BIRD = "fuuka_bird"
OBJ_PLAYERS = "fuuka_players"
SPIN = "fuuka_spin"

BOSS = "@e[type=%s,c=1]" % ID
STAND = "@e[type=fuuka:fang,c=1]"
NEAREST = "@p[r=48,m=!creative]"     # 書き出すときに「一番近い敵（プレイヤー・ほかのボス）」に置き換わる
FACE = "^ ^1.4 ^"
CINE = Cine("fuuka_cine")
TICK = 0.05


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not isinstance(data, str) and os.path.abspath(path).startswith(os.path.abspath(BP) + os.sep):
        add_rival(data, ID)     # プレイヤーへのダメージ命令を、ほかのボスにも当たるように複製する
        aim_at_foes(data, ID)   # 技の狙いを「一番近い敵（プレイヤー・ほかのボス）」に
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(data, str):
            f.write(data)
        elif "/animations/" in path.replace(os.sep, "/"):
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# コマンド用ヘルパー
# ---------------------------------------------------------------------------
def say(text):
    return '/tellraw @a[r=48] {"rawtext":[{"text":"%s"}]}' % text.replace('"', '\\"')


def act(text):
    return "/title @a[r=40] actionbar %s" % text


def pt(name, pos="~ ~ ~"):
    return "/particle fuuka:%s %s" % (name, pos)


def shake(i, sec, r=24):
    return "/camerashake add @a[r=%d] %.2f %.2f positional" % (r, i, sec)


def sound(name, pitch=1.0, r=40, vol=1.0):
    return "/playsound %s @a[r=%d] ~ ~ ~ %.1f %.2f" % (name, r, vol, pitch)


def flash(r, g, b, rad=32, t=(0.05, 0.1, 0.2)):
    return "/camera @a[r=%d] fade time %.2f %.2f %.2f color %d %d %d" % (rad, t[0], t[1], t[2], r, g, b)


# ---------------------------------------------------------------------------
# 狙撃の仕組み
#   1. 狙い始めに相手を 1 人に決める（狙っている間は変えない。狙われた人には知らせる）
#   2. 風花の「目の高さ」から相手の目へ向き直り続ける（膝立ち・腰だめで高さが変わる）
#   3. 弾と照準線は、1 マスずつ進む見えない「弾道」で飛ばす。ブロックか敵に当たったらそこで止まる
#      （物陰に隠れれば防げる。DXL-5 だけは壁も敵も貫通する）
# ---------------------------------------------------------------------------
EYE_STAND, EYE_KNEEL, EYE_HIP = 1.35, 1.05, 1.2
MARK = "fuuka_mark"
TARGET = "@e[tag=%s,c=1]" % MARK
RAY_TAG = "fuuka_ray_on"
RAY = "@e[type=fuuka:ray,tag=%s,c=1]" % RAY_TAG
STOP_P = "@a[r=1.25,m=!creative]"
STOP_R = "@e[family=%s,type=!%s,tag=!vb_cine,tag=!vb_paused,r=1.25]" % (RIVAL_FAMILY, ID)


def mark_target(notify=True):
    out = ["/tag @e[tag=%s] remove %s" % (MARK, MARK), "/execute as %s run tag @s add %s" % (NEAREST, MARK)]
    if notify:
        out.append("/title @a[tag=%s] actionbar §c§l◎ 狙われている！ §r§7照準線が点滅したら、横へ動くか物陰へ" % MARK)
    return out


def track(h):
    """決めた相手の目へ、風花の目の高さから向き直る（相手がいなくなったら一番近い敵へ）"""
    return ["/execute unless entity @e[tag=%s,r=64] as %s run tag @s add %s" % (MARK, NEAREST, MARK),
            "/execute at @s positioned ~ ~%.2f ~ facing entity %s eyes run tp @s ~ ~-%.2f ~ ~ ~" % (h, TARGET, h)]


def ray_start(h):
    """弾道を、風花の目の高さ・向きで出す"""
    return ["/tag @e[type=fuuka:ray] remove %s" % RAY_TAG, "/summon fuuka:ray ~ ~%.2f ~" % h,
            "/execute at @s positioned ~ ~%.2f ~ run tag @e[type=fuuka:ray,c=1] add %s" % (h, RAY_TAG),
            "/execute at @s positioned ~ ~%.2f ~ run tp %s ~ ~ ~ ~ ~" % (h, RAY)]


def ray_step(foe=True, blocks=True):
    """弾道を 1 マス進める（敵のすぐそば・ブロックの手前で止まる）"""
    c = "/execute as %s at @s" % RAY
    if foe:
        c += " positioned ~ ~-1 ~ unless entity %s unless entity %s positioned ~ ~1 ~" % (STOP_P, STOP_R)
    c += " positioned ^ ^ ^1"
    if blocks:
        c += " if block ~ ~ ~ air"
    return c + " run tp @s ~ ~ ~"


def laser(kind="laser", rng=28, h=EYE_STAND):
    out = ray_start(h)
    for _ in range(rng):
        out += [ray_step(), "/execute at %s run particle fuuka:%s ~ ~ ~" % (RAY, kind)]
    return out


def reticle():
    return "/execute at %s run particle fuuka:reticle ~ ~1 ~" % TARGET


def impact():
    """着弾: 当たった所に火花と破片、当たった人は画面が赤く"""
    return ["/execute at %s run particle fuuka:hit_spark ~ ~ ~" % RAY, "/execute at %s run particle fuuka:debris ~ ~ ~" % RAY,
            "/execute at %s positioned ~ ~-1 ~ run camera @a[r=1.6,m=!creative] fade time 0 0.04 0.22 color 150 0 0" % RAY,
            "/execute at %s run playsound random.anvil_land @a[r=16] ~ ~ ~ 0.35 1.9" % RAY]


def gunshot_fx(h, shell):
    out = ["/execute at @s positioned ~ ~%.2f ~ run particle fuuka:muzzle ^-0.25 ^-0.1 ^1.1" % h,
           sound("firework.blast", 0.5, 64), sound("random.explode", 1.8, 48, 0.4), sound("crossbow.shoot", 0.6, 48),
           shake(0.25, 0.12, 16)]
    if shell:
        out.append(pt("shell", "^-0.35 ^1.2 ^0.3"))
    return out


def shot(dmg, rng=40, h=EYE_STAND, shell=True):
    """普通の弾: 最初に当たった敵（かブロック）で止まり、そこでダメージ"""
    out = ray_start(h)
    for k in range(rng):
        out.append(ray_step())
        if k % 2 == 0:
            out.append("/execute at %s run particle fuuka:tracer ~ ~ ~" % RAY)
    out.append("/execute at %s positioned ~ ~-1 ~ run damage @a[r=1.3,m=!creative] %d entity_attack entity @s" % (RAY, dmg))
    return out + impact() + gunshot_fx(h, shell)


def pierce_shot(dmg, rng=44, h=EYE_STAND):
    """DXL-5: 壁も敵も貫通する"""
    out = ray_start(h)
    for k in range(rng):
        out += [ray_step(foe=False, blocks=False),
                "/execute at %s positioned ~ ~-1 ~ run damage @a[r=1.3,m=!creative] %d entity_attack entity @s" % (RAY, dmg)]
        if k % 2 == 0:
            out.append("/execute at %s run particle fuuka:tracer ~ ~ ~" % RAY)
    return out + gunshot_fx(h, False)


def aim_window(tl, t0, lock, fire, dmg, rng=40, h=EYE_STAND, bolt=True, pierce=False):
    """t0: 相手を決める / t0〜lock: 照準を合わせ続ける / lock〜fire: 照準を固定（ここで避ける）/ fire: 撃つ"""
    add(tl, t0, mark_target())
    t, k = t0, 0
    while t < lock - 1e-6:
        cmds = track(h)
        if k % 2 == 0:
            cmds += laser("laser", 28, h)
        if k % 4 == 0:
            cmds.append(reticle())
        if k % 6 == 0:   # 遠くからでも分かる、スコープのきらめき
            cmds.append("/execute at @s positioned ~ ~%.2f ~ run particle fuuka:scope_glint ^-0.2 ^ ^0.5" % h)
        if k == 6 and lock - t0 >= 0.6:   # 照準線が壁で届いていなければ、横へずれて射線を取り直す
            cmds.append("/execute at %s unless entity @e[tag=%s,r=3] run event entity @s fuuka:sidestep" % (RAY, MARK))
        add(tl, t, cmds)
        t, k = t + 0.05, k + 1
    add(tl, lock, ["/title @a[tag=%s] actionbar §c§l◎ 撃たれる――！" % MARK])
    t = lock
    while t < fire - 1e-6:
        add(tl, t, laser("laser_lock", 28, h))
        t += 0.1
    add(tl, fire, pierce_shot(dmg, rng, h) if pierce else shot(dmg, rng, h, shell=not bolt))
    add(tl, fire + 0.05, ["/tag @e[tag=%s] remove %s" % (MARK, MARK)])
    if bolt:
        add(tl, fire + 0.3, [sound("random.click", 1.5, 16)])
        add(tl, fire + 0.42, [sound("random.click", 1.9, 16), pt("shell", "^-0.35 ^1.0 ^0.3")])


def quick_window(tl, fire, dmg, h=EYE_HIP, pre=0.3, lock=0.1, rng=32):
    """腰だめの早撃ち: 短く狙って、少しだけ固定して撃つ"""
    add(tl, fire - pre, mark_target(False))
    t = fire - pre
    while t < fire - lock - 1e-6:
        add(tl, t, track(h) + laser("laser", 24, h))
        t += 0.05
    add(tl, fire - lock, laser("laser_lock", 24, h))
    add(tl, fire, shot(dmg, rng, h))
    add(tl, fire + 0.05, ["/tag @e[tag=%s] remove %s" % (MARK, MARK)])


AIM_ON = "/event entity @s fuuka:aim_on"
AIM_OFF = "/event entity @s fuuka:aim_off"


SKILLS = {}


def skill(v, name, length, tl):
    SKILLS[v] = (name, length, {"%.2f" % k: c for k, c in sorted(tl.items())})


def add(tl, t, cmds):
    tl.setdefault(round(t, 2), []).extend(cmds)


def aim_name(prefix, deg):
    return "fuuka:%s_%s" % (prefix, ("m%d" % -deg) if deg < 0 else deg)


# ===========================================================================
# 技
# ===========================================================================
# 1 狙撃「アウトロー・レッドノート」: 膝をつき、赤い照準線で狙う → 固定 → 撃つ（狙っている間は回避できない）
tl = {0: [act("§c◆ 狙撃「アウトロー・レッドノート」"), AIM_ON, sound("item.spyglass.use", 1.0, 32),
          pt("scope_glint", "~ ~1.4 ~")]}
aim_window(tl, 0.1, 1.2, 1.5, 18, h=EYE_KNEEL)
add(tl, 1.2, [say("§c風花§7「――そこ」")])
add(tl, 1.7, [AIM_OFF])
skill(1, "狙撃", 2.4, tl)

# 2 速射: 腰だめで 3 連射
tl = {0: [act("§c◆ 速射")]}
for t in (0.45, 0.9, 1.35):
    quick_window(tl, t, 7)
skill(2, "速射", 1.8, tl)

# 3 風符「鳥の気まぐれ」: 鳥の弾幕が飛んでいき、卵（爆弾）を落とす
BIRD_ANGLES = (-24, -12, 0, 12, 24)
tl = {0: [say("§c風花§7「風符――『鳥の気まぐれ』！」"), sound("mob.parrot.fly", 1.0, 40), pt("feather_burst", "~ ~2 ~")]}
add(tl, 0.85, ["/summon fuuka:bird ^%d ^5.5 ^-1 %s" % (k * 2 - 4, aim_name("b", a)) for k, a in enumerate(BIRD_ANGLES)]
    + [sound("mob.enderdragon.flap", 1.6, 40), pt("feather_burst", "~ ~5 ~")])
skill(3, "風符「鳥の気まぐれ」", 3.0, tl)

# 4 万華鏡の虹月島人形達: 七体の人形が周りを飛び回り、ミサイルを撃つ（人形は 3 回殴れば壊れる）
tl = {0: [say("§c風花§7「おいで、みんな！」"), act("§d◆ 万華鏡の虹月島人形達")]}
add(tl, 0.4, ["/summon fuuka:doll ^%.1f ^1.5 ^%.1f fuuka:doll_%d" % (2.4 * math.sin(k * 0.9), 2.4 * math.cos(k * 0.9), k)
              for k in range(1, 8)] + [sound("random.pop", 1.4, 32), pt("rainbow", "~ ~1.5 ~")])
skill(4, "万華鏡の虹月島人形達", 2.0, tl)

# 5 オルカブースター: 足の裏から水を噴いて後ろへ飛びのき、そのまま撃つ
tl = {0: [act("§b◆ オルカブースター"), sound("random.splash", 1.6, 24), sound("mob.enderdragon.flap", 1.8, 24, 0.5)]}
for k in range(4):
    add(tl, 0.05 + k * 0.05, ["/tp @s ^ ^0.15 ^-2.4 facing %s true" % NEAREST, pt("water_jet", "~ ~0.2 ~"),
                              pt("splash", "~ ~ ~")])
quick_window(tl, 0.7, 8, pre=0.25, lock=0.12)
skill(5, "オルカブースター", 1.2, tl)

# 6 オルカブースター（跳躍）: 空高く跳び、宙に浮いたまま 2 発（狙っている間は回避できない）
tl = {0: [act("§b◆ オルカブースター・ハイジャンプ"), sound("random.splash", 1.2, 32)]}
for k in range(6):
    add(tl, 0.15 + k * 0.05, ["/tp @s ~ ~1.4 ~ true", pt("water_jet", "~ ~ ~"), pt("splash", "~ ~ ~")])
add(tl, 0.5, ["/effect @s slow_falling 4 0 true", AIM_ON])
aim_window(tl, 0.6, 1.5, 1.7, 14, 44, bolt=False)
aim_window(tl, 1.8, 2.1, 2.3, 14, 44, bolt=False)
add(tl, 2.5, [AIM_OFF])
skill(6, "オルカブースター・ハイジャンプ", 3.2, tl)

# 7 ウォーターカッター: 足の裏の水流で、前方を薙ぎ払う
tl = {0: [act("§b◆ ウォーターカッター"), sound("random.splash", 0.8, 24)]}
for a in range(-55, 56, 22):
    for d in (3, 7, 11):
        add(tl, 0.0, ["/execute at @s rotated ~%d 0 positioned ^ ^0.1 ^%d run particle fuuka:warn ~ ~ ~" % (a, d)])
        add(tl, 0.25, ["/execute at @s rotated ~%d 0 positioned ^ ^0.1 ^%d run particle fuuka:warn ~ ~ ~" % (a, d)])
for i in range(13):
    ang = -55 + i * 110 / 12
    cmds = ["/execute at @s rotated ~%d 0 positioned ^ ^0.7 ^%d run damage @a[r=1.2,m=!creative] 9 entity_attack entity @s"
            % (ang, d) for d in range(2, 13, 2)]
    cmds += ["/execute at @s rotated ~%d 0 positioned ^ ^0.7 ^%d run particle fuuka:water_blade ~ ~ ~" % (ang, d)
             for d in (3, 7, 11)]
    if i % 3 == 0:
        cmds.append(sound("random.splash", 1.4, 24, 0.6))
    add(tl, 0.45 + i * 0.05, cmds)
skill(7, "ウォーターカッター", 1.8, tl)

# 8 スタンガン: 近すぎる相手に押し当てて、すぐ離れる
tl = {0: [act("§b◆ スタンガン"), "/tp @s ~ ~ ~ facing %s" % NEAREST]}
add(tl, 0.15, ["/execute positioned ^ ^1 ^1.5 run damage @a[r=2.3,m=!creative] 5 entity_attack entity @s",
               "/execute positioned ^ ^1 ^1.5 run effect @a[r=2.3,m=!creative] slowness 2 3 true",
               "/execute positioned ^ ^1 ^1.5 run effect @a[r=2.3,m=!creative] nausea 3 0 true",
               pt("stun", "^ ^1 ^1.4"), sound("mob.bee.sting", 0.6, 24), sound("random.fizz", 1.8, 24)])
for t in (0.4, 0.5):
    add(tl, t, ["/tp @s ^ ^0.15 ^-2.5 facing %s true" % NEAREST, pt("water_jet", "~ ~0.2 ~")])
skill(8, "スタンガン", 1.0, tl)

# 9 自爆スイッチ: 相手の周りに爆弾を置いて、「ポチッ」
BOMB_POS = [(2.5, 0.5), (-2.0, 2.0), (0.5, -2.5), (-2.5, -1.5)]
tl = {0: [say("§c風花§7「プレゼント、置いとくね♪」"), act("§c◆ 自爆スイッチ")]}
for k, (dx, dz) in enumerate(BOMB_POS):
    add(tl, 0.4 if k < 2 else 0.75, ["/execute at %s positioned ~%.1f ~1.5 ~%.1f run summon fuuka:bomb ~ ~ ~"
                                     % (NEAREST, dx, dz), sound("random.bow", 0.8, 24)])
add(tl, 2.3, [say("§c風花§7「ポチッとな」")])
add(tl, 2.6, ["/event entity @e[type=fuuka:bomb,r=48] fuuka:detonate", sound("random.click", 1.2, 24)])
skill(9, "自爆スイッチ", 3.2, tl)

# 10 牙・爪弾: スタンド「牙」が、指先から回転する爪弾を撃つ
NAIL_ANGLES = (-6, -3, 0, 3, 6)
tl = {0: ["/event entity %s fuuka:pose_1" % STAND, act("§6◆ 牙・爪弾")]}
for k, t in enumerate((0.2, 0.35, 0.5, 0.65, 0.8)):
    add(tl, t, ["/execute at %s run summon fuuka:nail ^ ^1.2 ^0.6 %s" % (STAND, aim_name("n", NAIL_ANGLES[k])),
                sound("random.bow", 1.8, 24, 0.7)])
skill(10, "牙・爪弾", 1.6, tl)

# 11 DXL-5 特殊弾: 長い溜めのあと、貫通して爆発する弾（狙っている間は回避できない）
tl = {0: [say("§c風花§7「特殊弾、装填――」"), AIM_ON, sound("block.beacon.activate", 1.6, 40)]}
aim_window(tl, 0.3, 2.2, 2.6, 24, 44, h=EYE_KNEEL, pierce=True)
add(tl, 2.6, [say("§c風花§7「DXL-5――発射！」")]
    + ["/execute at @s positioned ~ ~1.05 ~ positioned ^ ^ ^%d run summon fuuka:blast ~ ~ ~" % d for d in (12, 24, 36)]
    + ["/execute at @s positioned ~ ~1.05 ~ positioned ^ ^ ^%d run particle fuuka:explosion ~ ~ ~" % d for d in (12, 24, 36)]
    + ["/execute at @s positioned ~ ~1.05 ~ positioned ^ ^ ^%d run damage @a[r=3,m=!creative] 10 entity_attack entity @s" % d
       for d in (12, 24, 36)] + [shake(1.2, 0.5, 48), flash(255, 200, 160, 48, (0, 0.05, 0.25))])
add(tl, 2.8, [AIM_OFF])
skill(11, "DXL-5 特殊弾", 3.4, tl)

# 12 戯「怪盗の手癖」: 背後に回り込み、金のリンゴと矢を盗む（盗んだリンゴは自分で食べる）
tl = {0: [act("§d◆ 戯「怪盗の手癖」"), pt("smoke_bomb", "~ ~1 ~"), sound("random.pop", 0.8, 24)]}
add(tl, 0.1, ["/execute as %s at @s positioned ^ ^ ^-1.5 run tp %s ~ ~ ~ facing @s" % (NEAREST, BOSS),
              pt("afterimage", "~ ~0.9 ~")])
add(tl, 0.45, ["/execute if entity @a[r=3.5,m=!creative,hasitem={item=golden_apple}] run event entity @s fuuka:ate_apple",
               "/title @a[r=3.5,m=!creative,hasitem={item=golden_apple}] actionbar §c§l金のリンゴを盗まれた！",
               "/clear @a[r=3.5,m=!creative] golden_apple 0 1",
               "/title @a[r=3.5,m=!creative,hasitem={item=arrow}] actionbar §c§l矢を盗まれた！",
               "/clear @a[r=3.5,m=!creative] arrow 0 8", sound("random.orb", 1.6, 16)])
add(tl, 0.8, ["/tp @s ^ ^0.2 ^-3 facing %s true" % NEAREST, pt("water_jet", "~ ~0.2 ~")])
add(tl, 1.0, [say("§c風花§7「いただきっ♪」")])
skill(12, "戯「怪盗の手癖」", 1.6, tl)

# 13 雲散霧消: 霧の中に消え、離れたところから 2 発
tl = {0: [say("§c風花§7「雲散霧消――霧の中で、迷子になってね」"), act("§7◆ 雲散霧消"),
          "/fog @a[r=40] push fuuka:fog fuuka_mist", "/effect @s invisibility 5 0 true",
          "/effect %s invisibility 5 0 true" % STAND, sound("mob.evocation_illager.prepare_summon", 1.4, 40)]}
for t in (0.0, 1.0, 2.0, 3.0, 4.0):
    add(tl, t, ["/execute at @a[r=40,m=!creative] run particle fuuka:fog_cloud ~ ~1 ~"])
add(tl, 0.8, ["/execute as %s at @s rotated ~150 0 positioned ^ ^ ^12 run tp %s ~ ~ ~ facing @s true" % (NEAREST, BOSS)])
add(tl, 1.8, [AIM_ON])
aim_window(tl, 1.9, 2.1, 2.4, 14, bolt=False)
add(tl, 3.2, ["/execute as %s at @s rotated ~-120 0 positioned ^ ^ ^12 run tp %s ~ ~ ~ facing @s true" % (NEAREST, BOSS)])
aim_window(tl, 3.9, 4.1, 4.4, 14, bolt=False)
add(tl, 4.6, [AIM_OFF])
add(tl, 5.6, ["/fog @a[r=64] remove fuuka_mist"])
skill(13, "雲散霧消", 6.0, tl)

# 14 牙 ACT4「無限の回転」: スタンドが力を溜め、回転する爪弾を放つ。当たると回転ダメージが倍々に増える
#    → 月島の 5 マス以内に近づくと回転を返せる（月島に大ダメージ）。月島に攻撃を当てても止まる
tl = {0: ["/event entity %s fuuka:pose_3" % STAND, say("§c風花§7「――牙、ACT4」"),
          "/title @a[r=40] title §6§l牙 ACT4", "/title @a[r=40] subtitle §e無限の回転",
          sound("beacon.power", 0.6, 48)]}
for t in (0.3, 0.6, 0.9, 1.2):
    add(tl, t, ["/execute at %s run particle fuuka:act4_charge ~ ~1.4 ~" % STAND, sound("note.pling", 0.5 + t, 32)])
add(tl, 1.55, ["/execute at %s run summon fuuka:nail4 ^ ^1.3 ^0.6 fuuka:act4_aim" % STAND,
               sound("random.anvil_land", 1.6, 48), shake(0.6, 0.3, 24)])
skill(14, "牙 ACT4「無限の回転」", 4.0, tl)

# ---------------------------------------------------------------------------
# カットシーン
# ---------------------------------------------------------------------------
# 30 登場: 煙の中から降り立ち、名乗る → 最後にスタンド「牙」が現れる
tl = {}
add(tl, 0, CINE.begin(8) + [CINE.cam("^3 ^2.5 ^7", "^ ^1 ^"), CINE.fade(0, 0.4, 0.8),
                            "/scoreboard objectives add %s dummy" % OBJ_BIRD,
                            "/scoreboard objectives add %s dummy" % OBJ_PLAYERS,
                            "/scoreboard players set @s %s 4" % OBJ_BIRD, sound("random.fuse", 1.2, 48)])
add(tl, 0.95, [pt("smoke_bomb", "~ ~1 ~"), sound("random.explode", 1.6, 48, 0.6)])
add(tl, 1.1, [CINE.cam("^0.9 ^0.9 ^2.6", FACE), CINE.cam("^0.6 ^1.3 ^1.9", FACE, 1.4)])
add(tl, 1.5, [say("§c風花§7「秘密結社『花鳥風月』社長――月島 風花、参上！」"), "/title @a[r=64] title §c月島 風花",
              "/title @a[r=64] subtitle §7秘密結社「花鳥風月」社長 ―― 怪盗", sound("random.levelup", 1.4, 48, 0.5)])
add(tl, 2.4, [pt("card", "^0.3 ^1.5 ^1.2"), pt("card", "^-0.4 ^1.7 ^1.4"), pt("card", "^0.1 ^1.9 ^1.0"),
              say("§c風花§7「予告状、ちゃんと届いてたでしょ？」"), sound("item.book.page_turn", 1.4, 40)])
add(tl, 3.0, [CINE.cam("^-2.2 ^1.6 ^2.6", "^ ^1.2 ^", 1.4)])
add(tl, 4.6, [CINE.cam("^-0.7 ^1.65 ^-1.6", "^ ^1.4 ^8", 0.6), pt("scope_glint", "~ ~1.4 ~")])
add(tl, 5.0, [say("§c風花§7「お宝は――あなたの負け、ってことで。いくよ！」")])
add(tl, 6.2, ["/summon fuuka:fang ~ ~1 ~", "/ride @e[type=fuuka:fang,c=1,r=4] start_riding @s", "/tag @s add fuuka_stand_on",
              CINE.cam("^2.4 ^2.0 ^-0.6", "^-0.6 ^1.8 ^-0.6"), pt("stand_aura", "~ ~2 ~"), pt("feather_burst", "~ ~2 ~"),
              "/title @a[r=40] title §6§l牙", sound("beacon.activate", 1.4, 40)])
add(tl, 7.3, [CINE.fade(0, 0.2, 0.5)])
add(tl, 7.6, CINE.end())
skill(30, "登場", 8.0, tl)

# 31 花鳥風月（HP60%）
tl = {}
add(tl, 0, CINE.begin(7.5) + [CINE.cam("^0 ^1.6 ^4", FACE), CINE.cam("^0 ^1.4 ^2.6", FACE, 1.2),
                              say("§c風花§7「……ちょっと、本気出そっか。――花鳥風月！」")])
add(tl, 1.3, ["/title @a[r=40] title §d§l花", "/title @a[r=40] subtitle §7花のように周りを和ませ ― 攻撃力アップ",
              "/effect @s strength 9999 1 true", pt("petal", "~ ~1.5 ~"), sound("random.orb", 1.4, 40),
              CINE.fade(0, 0.05, 0.35, (255, 150, 190))])
add(tl, 2.8, ["/title @a[r=40] title §f§l鳥", "/title @a[r=40] subtitle §7鳥のように軽やかに動き ― 回避ゲージの上限が 6 に",
              "@s fuuka:bird_full", pt("feather_burst", "~ ~1.5 ~"), CINE.cam("^-3 ^2 ^2", "^ ^1.6 ^", 1.2),
              sound("mob.parrot.fly", 1.2, 40), CINE.fade(0, 0.05, 0.35, (255, 255, 255))])
add(tl, 4.3, ["/title @a[r=40] title §b§l風", "/title @a[r=40] subtitle §7風のように爽やかに吹き荒び ― 素早さアップ",
              pt("wind", "~ ~1 ~"), CINE.cam("^ ^7 ^0.01", "^ ^ ^", 1.0), sound("elytra.loop", 1.2, 40, 0.6),
              CINE.fade(0, 0.05, 0.35, (150, 230, 255))])
add(tl, 5.8, ["/title @a[r=40] title §e§l月", "/title @a[r=40] subtitle §7月のように静かに佇む ― 近くの全員の強化を打ち消す",
              "/effect @a[r=32,m=!creative] clear", pt("moon", "~ ~3 ~"), CINE.cam("^0.5 ^0.6 ^2.4", "^ ^2.4 ^", 1.0),
              sound("beacon.deactivate", 0.8, 40), CINE.fade(0, 0.05, 0.4, (255, 230, 140))])
add(tl, 7.2, CINE.end())
skill(31, "花鳥風月", 7.5, tl)

# 32 鳥獣戯画（HP30%）
tl = {}
add(tl, 0, CINE.begin(7.0) + [CINE.cam("^2 ^1.4 ^3", FACE), say("§c風花§7「まだまだ！ ――鳥獣戯画！」"),
                              CINE.fade(0, 0.1, 0.4, (255, 255, 255))])
add(tl, 1.2, ["/title @a[r=40] title §f§l鳥", "/title @a[r=40] subtitle §7鳥のように軽やかに遊び ― 回避ゲージの回復が速くなる",
              pt("feather_burst", "~ ~1.5 ~"), sound("mob.parrot.fly", 1.4, 40), CINE.fade(0, 0.05, 0.35, (255, 255, 255))])
add(tl, 2.6, ["/title @a[r=40] title §6§l獣", "/title @a[r=40] subtitle §7獣のように速く疾く ― 2 回行動",
              CINE.cam("^0 ^0.5 ^2.2", "^ ^0.8 ^", 0.6), sound("mob.wolf.growl", 1.2, 40),
              CINE.fade(0, 0.05, 0.35, (255, 150, 60))])
add(tl, 4.0, ["/title @a[r=40] title §d§l戯", "/title @a[r=40] subtitle §7怪盗にとっては戯れ ― アイテムを盗む技が解禁",
              pt("rainbow", "~ ~2 ~"), CINE.cam("^-2 ^1.6 ^2", FACE, 0.8), sound("random.pop", 1.4, 40),
              CINE.fade(0, 0.05, 0.35, (220, 120, 255))])
add(tl, 5.4, ["/title @a[r=40] title §c§l画", "/title @a[r=40] subtitle §7速く動くほど画になる ― 演出が終わった瞬間に動く",
              CINE.cam("^0 ^1.5 ^1.6", FACE, 0.5), sound("random.levelup", 1.6, 40, 0.6),
              CINE.fade(0, 0.05, 0.35, (255, 80, 80))])
add(tl, 6.8, CINE.end())
skill(32, "鳥獣戯画", 7.0, tl)

CINE_V = [30, 31, 32]

# 撃破カットシーン
DEATH = {}
add(DEATH, 0, CINE.begin(6) + [CINE.cam("~2.4 ~1.1 ~2.4", "~ ~0.6 ~"), CINE.fade(0, 0.3, 0.8, (120, 0, 20)),
                              pt("feather_burst", "~ ~0.8 ~"), "/playsound random.pop @a[r=64] ~ ~ ~ 1 0.6"])
add(DEATH, 0.1, [CINE.cam("~-2.4 ~1.3 ~2.4", "~ ~0.6 ~", 1.8, "linear")])
add(DEATH, 0.9, [say("§c風花§7「あちゃー……負けちゃった」")])
add(DEATH, 1.9, [CINE.cam("~-2.4 ~1.6 ~-2.4", "~ ~0.6 ~", 1.8, "linear")])
add(DEATH, 2.6, [say("§c風花§7「今日のところは、お宝はあきらめてあげる。――花鳥風月、撤収！」")])
add(DEATH, 4.3, [pt("smoke_bomb", "~ ~1 ~"), pt("feather_burst", "~ ~1.5 ~"), pt("petal", "~ ~1.5 ~"),
                 pt("card", "~ ~1.2 ~"), "/playsound random.explode @a[r=32] ~ ~ ~ 0.6 1.6"])
add(DEATH, 5.3, [CINE.fade(0, 0.1, 0.6, (120, 0, 20))] + CINE.end())
add(DEATH, 5.35, ["/title @a[r=64] title §6§l討伐成功", "/title @a[r=64] subtitle §7月島 風花を倒した",
                   "/playsound random.levelup @a[r=64] ~ ~ ~ 1 0.8", "/playsound random.totem @a[r=64] ~ ~ ~ 0.5 1.6"])
add(DEATH, 5.5, ["@s fuuka:despawn"])
DEATH = {"%.2f" % k: v for k, v in sorted(DEATH.items())}


# ---------------------------------------------------------------------------
# カットイン・立ち回り
# ---------------------------------------------------------------------------
SMOOTH_STEP = 0.02
for _v in SKILLS:
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


# 60 オルカブースター・ステップ: 水流で後ろへ跳び、腰だめで 1 発 / 61・62 横へ回り込みながら撃つ
tl = {0: [act("§b◆ ステップ"), sound("random.splash", 1.8, 24, 0.6)]}
footwork_steps(lambda t, c: add(tl, t, c), 0.05, 3, "^ ^0.2 ^-1.8", NEAREST, [pt("water_jet", "~ ~0.2 ~")])
quick_window(tl, 0.52, 7, pre=0.22)
skill(60, "ステップ・ショット", 1.1, tl)
for v, side in ((61, 1), (62, -1)):
    tl = {0: [act("§b◆ 回り込み"), sound("random.splash", 1.9, 24, 0.5)]}
    footwork_steps(lambda t, c: add(tl, t, c), 0.08, 7, "^%g ^ ^0.2" % (-1.4 * side), NEAREST,
                   [pt("water_trail", "~ ~0.2 ~")])
    quick_window(tl, 0.58, 7, pre=0.18)
    skill(v, "回り込み", 1.3, tl)

cutin_into(14, 0.0, 0.9, "^1.2 ^2.0 ^1.6", "^-0.6 ^1.8 ^-0.6", "§6§l牙 ACT4")
cutin_into(3, 0.0, 0.8, "^0.6 ^1.3 ^1.6", "^-0.2 ^1.5 ^0.2", "§c§l風符「鳥の気まぐれ」")
cutin_into(13, 0.0, 0.7, "^-1.2 ^1.6 ^-2.2", "^ ^1.3 ^", "§7§l雲散霧消")
# DXL-5: 溜めの途中でスコープ越しの一瞬（照準を固定する前なので、避ける邪魔はしない）
cutin_into(11, 1.0, 0.45, "^-0.35 ^1.0 ^0.3", "^ ^1.0 ^6", "§c§lDXL-5")


# ---------------------------------------------------------------------------
# Behavior Pack: 本体
# ---------------------------------------------------------------------------
def manifest(kind):
    if kind == "bp":
        return {"format_version": 2,
                "header": {"name": "月島 風花 ボス BP", "description": "ボス「月島 風花」を追加します",
                           "uuid": UUID_BP_HEADER, "version": VERSION, "min_engine_version": MIN_ENGINE},
                "modules": [{"type": "data", "uuid": UUID_BP_MODULE, "version": VERSION}],
                "dependencies": [{"uuid": UUID_RP_HEADER, "version": VERSION}]}
    return {"format_version": 2,
            "header": {"name": "月島 風花 ボス RP", "description": "ボス「月島 風花」を追加します",
                       "uuid": UUID_RP_HEADER, "version": VERSION, "min_engine_version": MIN_ENGINE},
            "modules": [{"type": "resources", "uuid": UUID_RP_MODULE, "version": VERSION}]}


def phase_group(skin, speed, timer):
    return {"minecraft:skin_id": {"value": skin}, "minecraft:movement": {"value": speed},
            "minecraft:timer": {"looping": True, "time": timer, "randomInterval": True,
                                "time_down_event": {"event": "fuuka:choose_skill", "target": "self"}}}


SENSORS = ["sensor_normal", "cine_guard"]
IMMUNE = ("fall", "fire", "fire_tick", "lava", "drowning", "suffocation", "magic", "entity_explosion", "block_explosion",
          "wither", "lightning")
FOE = FOE_ANY
BIRD_OK = [{"test": "int_property", "subject": "self", "domain": "fuuka:bird", "operator": ">", "value": 0},
           {"test": "bool_property", "subject": "self", "domain": "fuuka:aim", "operator": "!=", "value": True}]


def gauge_cmds(head):
    out = []
    for n in range(0, 7):
        bar = "§b" + "◆" * n + "§8" + "◇" * max(0, 6 - n)
        tail = " §c§l回避ゲージ切れ！ §r§e今なら当たる！" if n == 0 else ""
        out.append("execute if score @s %s matches %d run title @a[r=24] actionbar %s %s%s" % (OBJ_BIRD, n, head, bar, tail))
    return out


def bp_entity():
    imm = [{"cause": c, "deal_damage": False} for c in IMMUNE]
    stop_spin = ["tag @e[tag=%s] remove %s" % (SPIN, SPIN), "event entity @e[type=fuuka:spin] fuuka:despawn"]
    groups = {
        "phase_1": phase_group(0, 0.36, [1.6, 2.8]),
        "phase_2": phase_group(1, 0.40, [1.3, 2.3]),
        "phase_3": phase_group(2, 0.44, [0.9, 1.8]),
        # 回避: 回避ゲージ（鳥）がある間は、攻撃をすべて避ける（狙撃で狙っている間は避けられない）
        "sensor_normal": {"minecraft:damage_sensor": {"triggers": [
            {"on_damage": {"filters": {"all_of": [FOE] + BIRD_OK}, "event": "fuuka:dodge"}, "deal_damage": False},
            {"cause": "projectile", "on_damage": {"filters": {"all_of": BIRD_OK}, "event": "fuuka:dodge"},
             "deal_damage": False}] + imm + [
            {"cause": "entity_attack", "on_damage": {"filters": FOE, "event": "fuuka:on_hit"}},
            {"cause": "projectile", "on_damage": {"event": "fuuka:on_hit"}}]}},
        "cine_guard": {"minecraft:damage_sensor": {"triggers": [{"cause": "all", "deal_damage": False}]}},
        # 距離を保つ: 近づかれたら離れ、遠すぎたら 16 マスまで寄る（近接攻撃はしない）
        "ai": dict({
            "minecraft:behavior.float": {"priority": 0},
            "minecraft:behavior.hurt_by_target": {"priority": 1},
            "minecraft:behavior.nearest_attackable_target": {
                "priority": 2, "must_see": False, "reselect_targets": True, "within_radius": 48,
                "entity_types": [{"filters": {"test": "is_family", "subject": "other", "value": "player"}, "max_dist": 48},
                                 rival_target("fuuka")]},
            "minecraft:behavior.random_stroll": {"priority": 6, "speed_multiplier": 0.9},
            "minecraft:behavior.look_at_player": {"priority": 7, "look_distance": 16},
        }, **stance_group("fuuka", keep=16, flee=9)),
    }
    variants = [0] + sorted(SKILLS)
    for v in variants:
        groups["v_%d" % v] = {"minecraft:mark_variant": {"value": v}}
    all_v = ["v_%d" % v for v in variants]

    def set_variant(v, add_=None, remove_=None):
        return {"remove": {"component_groups": [g for g in all_v if g != "v_%d" % v] + (remove_ or [])},
                "add": {"component_groups": ["v_%d" % v] + (add_ or [])}}

    def cine(v, add_=(), remove_=()):
        return set_variant(v, ["cine_guard"] + list(add_), ["sensor_normal", "ai"] + list(remove_))

    not_busy = {"all_of": [{"test": "is_mark_variant", "operator": "!=", "value": c} for c in CINE_V]}
    aim_off = {"fuuka:aim": False}
    events = {
        "minecraft:entity_spawned": {"add": {"component_groups": ["phase_1", "v_30", "cine_guard"]}},
        "fuuka:skill_end": {"sequence": [{"filters": not_busy, **set_variant(0, ["sensor_normal"], ["cine_guard"]),
                                          "set_property": aim_off,
                                          "queue_command": {"command": ["event entity @s fuuka:combo_roll",
                                                                        "tag @e[tag=fuuka_mark] remove fuuka_mark"]}}]},
        # 獣（HP30%〜）: 一定確率でそのまま次の行動へ（2 回行動）
        "fuuka:combo_roll": {"sequence": [{"filters": {"test": "is_skin_id", "value": 2}, "randomize": [
            {"weight": 45, "trigger": "fuuka:choose_skill",
             "queue_command": {"command": ["title @a[r=24] actionbar §6§l獣 ― 2 回行動！"]}},
            {"weight": 55, "queue_command": {"command": ["particle fuuka:feather ~ ~1.5 ~"]}}]}]},
        "fuuka:cine_end": dict(set_variant(0, ["sensor_normal", "ai"], ["cine_guard"]), set_property=aim_off),
        "fuuka:aim_on": {"set_property": {"fuuka:aim": True}},
        "fuuka:aim_off": {"set_property": aim_off},
        # 回避: ゲージを 1 使って、ひらりと避ける（人形がいれば人形のところへ「move」）
        "fuuka:dodge": {"sequence": [
            {"set_property": {"fuuka:bird": "math.max(q.property('fuuka:bird') - 1, 0)"},
             "queue_command": {"command": [
                 "scoreboard players remove @s %s 1" % OBJ_BIRD, "particle fuuka:feather_burst ~ ~1 ~",
                 "particle fuuka:afterimage ~ ~0.9 ~", "playsound mob.bat.takeoff @a[r=16] ~ ~ ~ 0.7 1.6",
                 "execute if entity @e[family=fuuka_doll,r=32] run tp @s @e[family=fuuka_doll,c=-1,r=32]",
                 "execute unless entity @e[family=fuuka_doll,r=32] run event entity @s fuuka:sidestep"]
                 + gauge_cmds("§f回避！")}}]},
        "fuuka:sidestep": {"randomize": [
            {"weight": 1, "queue_command": {"command": ["tp @s ^2.6 ^ ^-0.6 facing %s true" % NEAREST]}},
            {"weight": 1, "queue_command": {"command": ["tp @s ^-2.6 ^ ^-0.6 facing %s true" % NEAREST]}},
            {"weight": 1, "queue_command": {"command": ["tp @s ^ ^0.3 ^-3 facing %s true" % NEAREST]}}]},
        # 回避ゲージの回復（第一形態は 4 まで、花鳥風月から 6 まで）
        "fuuka:bird_regen": {"sequence": [
            {"filters": {"all_of": [{"test": "is_skin_id", "value": 0},
                                    {"test": "int_property", "subject": "self", "domain": "fuuka:bird", "operator": "<",
                                     "value": 4}]},
             "set_property": {"fuuka:bird": "q.property('fuuka:bird') + 1"},
             "queue_command": {"command": ["scoreboard players add @s %s 1" % OBJ_BIRD]}},
            {"filters": {"all_of": [{"test": "is_skin_id", "operator": ">=", "value": 1},
                                    {"test": "int_property", "subject": "self", "domain": "fuuka:bird", "operator": "<",
                                     "value": 6}]},
             "set_property": {"fuuka:bird": "q.property('fuuka:bird') + 1"},
             "queue_command": {"command": ["scoreboard players add @s %s 1" % OBJ_BIRD]}}]},
        "fuuka:bird_regen_fast": {"sequence": [{"filters": {"test": "is_skin_id", "value": 2},
                                                "trigger": "fuuka:bird_regen"}]},
        "fuuka:bird_full": {"set_property": {"fuuka:bird": 6},
                            "queue_command": {"command": ["scoreboard players set @s %s 6" % OBJ_BIRD]}},
        # 攻撃が当たった: 無限の回転が止まる（集中が切れる）
        "fuuka:on_hit": {"queue_command": {"command": [
            "particle fuuka:feather_red ~ ~1.2 ~",
            "execute if entity @e[type=fuuka:spin] run title @a[r=32] actionbar §e§l風花に攻撃が当たった！ 回転が止まった"]
            + stop_spin}},
        "fuuka:ate_apple": {"queue_command": {"command": [
            "effect @s regeneration 4 2 true", "particle fuuka:rainbow ~ ~1.5 ~",
            'tellraw @a[r=32] {"rawtext":[{"text":"§c風花§7「金のリンゴ、いただきます♪」"}]}']}},
        "fuuka:phase2": cine(31, ["phase_2"], ["phase_1"]),
        "fuuka:phase3": cine(32, ["phase_3"], ["phase_1", "phase_2"]),
    }
    # 画（HP30%〜）: 演出が終わった瞬間に動く
    events["fuuka:cine_end"]["queue_command"] = {"command": ["execute if entity @s[tag=fuuka_stand_on] run event entity @s "
                                                             "fuuka:choose_skill"]}
    for v in sorted(SKILLS):
        if v not in CINE_V:
            events["fuuka:skill_%d" % v] = set_variant(v)

    near1 = [5, 5, 8, 8, 60, 60, 61, 62, 2, 7, 10, 3]
    far1 = [1, 1, 1, 2, 2, 3, 4, 6, 9, 10, 7]
    near2 = near1 + [7, 10, 61, 62]
    far2 = far1 + [11, 11, 4, 6, 14]
    near3 = near2 + [12, 12, 13]
    far3 = far2 + [13, 14, 14, 12]
    NEAR, FAR = near_filters("fuuka_near")
    base = [{"test": "is_mark_variant", "value": 0}, {"test": "has_target", "value": True}]
    seq = []
    for skin, near, far in ((0, near1, far1), (1, near2, far2), (2, near3, far3)):
        for cond, lst in ((NEAR, near), (FAR, far)):
            seq.append({"filters": {"all_of": base + [{"test": "is_skin_id", "value": skin}, cond]},
                        "randomize": [{"weight": 10, "trigger": "fuuka:skill_%d" % s} for s in lst]})
    events["fuuka:choose_skill"] = {"sequence": seq}
    events.update(pause_events(not_busy))

    components = {
        "minecraft:type_family": {"family": ["fuuka", "boss", RIVAL_FAMILY, "monster", "mob"]},
        "minecraft:health": {"value": HP, "max": HP},
        "minecraft:boss": {"hud_range": 64, "should_darken_sky": False},
        "minecraft:nameable": {"always_show": True, "allow_name_tag_renaming": False},
        "minecraft:persistent": {},
        "minecraft:scale": {"value": 0.86},
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
        # スタンド「牙」は風花の右肩の後ろに乗る（見た目を滑らかにくっつけるため）
        "minecraft:rideable": {"seat_count": 1, "family_types": ["fuuka_stand"], "interact_text": "",
                               "pull_in_entities": False, "crouching_skip_interact": True,
                               "seats": [{"position": [-0.55, 0.45, -0.55], "lock_rider_rotation": 0}]},
        "minecraft:loot": {"table": "loot_tables/entities/fuuka.json"},
        "minecraft:experience_reward": {"on_death": "1500"},
        "minecraft:environment_sensor": {"triggers": [
            {"filters": {"all_of": [{"test": "actor_health", "operator": "<=", "value": PHASE2_HP},
                                    {"test": "is_skin_id", "value": 0}] + not_busy["all_of"]}, "event": "fuuka:phase2"},
            {"filters": {"all_of": [{"test": "actor_health", "operator": "<=", "value": PHASE3_HP},
                                    {"test": "is_skin_id", "value": 1}] + not_busy["all_of"]}, "event": "fuuka:phase3"},
        ]},
    }
    anims = {"skills": "controller.animation.fuuka.skills", "death": "controller.animation.fuuka.death",
             "upkeep": "animation.fuuka.upkeep", "idle_loop": "animation.fuuka.idle_loop",
             "foe_tags": "animation.fuuka.foe_tags", "bird": "animation.fuuka.bird_regen",
             **{"skill_%d" % v: "animation.fuuka.skill_%d" % v for v in SKILLS}}
    return {"format_version": "1.21.0", "minecraft:entity": {
        "description": {"identifier": ID, "is_spawnable": True, "is_summonable": True, "is_experimental": False,
                        "properties": {"fuuka:bird": {"type": "int", "range": [0, 6], "default": 4, "client_sync": True},
                                       "fuuka:aim": {"type": "bool", "default": False, "client_sync": True}},
                        "scripts": {"animate": ["skills", "upkeep", "death", "foe_tags", "bird"]}, "animations": anims},
        "component_groups": groups, "components": components, "events": events}}


# ほかのボスと初めて会ったときのひとこと
ENCOUNTER = {
    "byakuya": "§c風花§7「白夜さん！？ ……引退したんじゃなかったの！？ ――今度こそ、手加減なしで勝つから！」",
    "hitori": "§c風花§7「独君……今日は敵同士、だね。……手加減、しないよ？」",
    "sophia": "§c風花§7「ソフィアさん。……また慢心してると、撃ち抜いちゃうよ？」",
    "shinonome": "§c風花§7「東雲さん！ 前は一緒に戦ったけど……今日は花鳥風月の名にかけて、負けないよ！」",
}


def bp_animations():
    a = {"animation.fuuka.skill_%d" % v: {"animation_length": length, "loop": False, "timeline": tl}
         for v, (name, length, tl) in SKILLS.items()}
    a["animation.fuuka.upkeep"] = {"animation_length": 5.0, "loop": True, "timeline": {
        "0.50": ["/scoreboard players set @s %s 0" % OBJ_PLAYERS,
                 "/execute as @a[r=40,m=!creative] run scoreboard players add %s %s 1" % (BOSS, OBJ_PLAYERS),
                 "/execute if score @s %s matches 2 run effect @s resistance 6 0 true" % OBJ_PLAYERS,
                 "/execute if score @s %s matches 3 run effect @s resistance 6 1 true" % OBJ_PLAYERS,
                 "/execute if score @s %s matches 4.. run effect @s resistance 6 2 true" % OBJ_PLAYERS],
        # スタンドはいつも出ている（いなくなっていたら呼び戻す）
        "2.50": ["/execute if entity @s[tag=fuuka_stand_on] unless entity @e[type=fuuka:fang,r=12] run "
                 "summon fuuka:fang ~ ~1 ~",
                 "/execute if entity @s[tag=fuuka_stand_on] run ride @e[type=fuuka:fang,c=1,r=12] start_riding @s"]}}
    a["animation.fuuka.idle_loop"] = {"animation_length": 2.0, "loop": True, "timeline": {
        "1.00": CINE.end(), "1.50": encounter_cmds("fuuka", say, ENCOUNTER)}}
    a["animation.fuuka.foe_tags"] = foe_tag_anim(ID, "fuuka_near", near=8)
    a["animation.fuuka.bird_regen"] = {"animation_length": 2.4, "loop": True, "timeline": {
        "1.20": ["/event entity @s fuuka:bird_regen_fast"], "2.40": ["/event entity @s fuuka:bird_regen"]}}
    return {"format_version": "1.10.0", "animations": a}


def bp_controllers():
    states = {"default": {"animations": ["idle_loop"],
                          "transitions": [{"skill_%d" % v: "q.mark_variant == %d" % v} for v in sorted(SKILLS)]}}
    for v in sorted(SKILLS):
        states["skill_%d" % v] = {"animations": ["skill_%d" % v],
                                  "transitions": [{"default": "q.all_animations_finished || q.mark_variant != %d" % v}],
                                  "on_exit": ["@s fuuka:%s" % ("cine_end" if v in CINE_V else "skill_end")]}
    return {"format_version": "1.10.0", "animation_controllers": {
        "controller.animation.fuuka.skills": {"initial_state": "default", "states": states},
        "controller.animation.fuuka.death": {"initial_state": "alive", "states": {
            "alive": {"transitions": [{"dead": "!q.is_alive"}]},
            "dead": {"on_entry": ["/summon fuuka:director ~ ~ ~", "/fog @a[r=64] remove fuuka_mist",
                                  "/tag @e[tag=%s] remove %s" % (SPIN, SPIN), "/tag @e[tag=fuuka_mark] remove fuuka_mark",
                                  "/event entity @e[family=fuuka_fx] fuuka:despawn",
                                  "/event entity @e[family=fuuka_stand] fuuka:despawn"] + CINE.end()}}},
    }}


def bp_loot():
    return {"pools": [
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:crossbow", "weight": 1, "functions": [
            {"function": "set_name", "name": "§c§lアウトロー・レッドノート"},
            {"function": "set_lore", "lore": ["§7赤く塗られた特別な狙撃銃", "§8秘密結社「花鳥風月」の宝物"]},
            {"function": "specific_enchants", "enchants": [
                {"id": "piercing", "level": 4}, {"id": "quick_charge", "level": 3}, {"id": "unbreaking", "level": 3},
                {"id": "mending", "level": 1}]}]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:feather", "weight": 1, "functions": [
            {"function": "set_count", "count": 16}, {"function": "set_name", "name": "§f鳥の羽（花鳥風月）"}]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:golden_apple", "weight": 1, "functions": [
            {"function": "set_count", "count": 4}, {"function": "set_name", "name": "§6盗まれていた金のリンゴ"}]}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:totem_of_undying", "weight": 1}]},
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:diamond", "weight": 1,
                                  "functions": [{"function": "set_count", "count": {"min": 6, "max": 12}}]}]},
    ]}


# ---------------------------------------------------------------------------
# 補助エンティティ
# ---------------------------------------------------------------------------
DESPAWN_G = {"despawn": {"minecraft:instant_despawn": {}}}
DESPAWN_E = {"fuuka:despawn": {"add": {"component_groups": ["despawn"]}}}


def fx_base(family, hitbox=0.2, gravity=False):
    return {"minecraft:type_family": {"family": family}, "minecraft:health": {"value": 1, "max": 1},
            "minecraft:collision_box": {"width": hitbox, "height": hitbox},
            "minecraft:physics": {"has_gravity": gravity, "has_collision": gravity},
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


def hit(r, dmg, cause="entity_attack", extra=(), dy=-0.6):
    pos = "positioned ~ ~%.1f ~ " % dy if dy else ""
    sel = "@a[r=%.1f,m=!creative]" % r
    out = ["/execute %sif entity %s run damage %s %d %s entity %s" % (pos, sel, sel, dmg, cause, BOSS)]
    out += ["/execute %sif entity %s run %s" % (pos, sel, e) for e in extra]
    out.append("/execute %sif entity %s run event entity @s fuuka:despawn" % (pos, sel))
    return out


def aim_events(prefix, angles, extra=()):
    return {aim_name(prefix, a): {"queue_command": {"command": [
        "tp @s ~ ~ ~ facing %s" % NEAREST, "tp @s ~ ~ ~ ~%d ~" % a] + list(extra)}} for a in angles}


def summons_bp():
    out, A, C = {}, {}, {}
    # スタンド「牙」: 風花に乗って（右肩の後ろ）ずっとついてくる。誰にでも見える
    g = dict(DESPAWN_G, **{"pose_%d" % k: {"minecraft:mark_variant": {"value": k}} for k in range(4)})
    e = dict(DESPAWN_E, **{"fuuka:pose_%d" % k: {"remove": {"component_groups": ["pose_%d" % j for j in range(4) if j != k]},
                                                  "add": {"component_groups": ["pose_%d" % k]}} for k in range(4)})
    stand = fx_base(["fuuka_stand", "inanimate"], 0.3)
    A["animation.fuuka.fang.keep"] = {"animation_length": 0.5, "loop": True, "timeline": {"0.25": [
        "/execute unless entity %s run event entity @s fuuka:despawn" % BOSS]}}
    A["animation.fuuka.fang.follow"] = {"animation_length": 0.25, "loop": True, "timeline": {"0.00": [
        "/execute at %s run tp @s ^-0.6 ^0.5 ^-0.6 ~ ~" % BOSS,
        "/ride @s start_riding %s" % BOSS]}}
    for k, L in ((1, 1.0), (2, 2.0), (3, 2.4)):
        A["animation.fuuka.fang.pose_%d" % k] = {"animation_length": L + 0.05, "loop": False, "timeline": {
            "%.2f" % L: ["@s fuuka:pose_0"]}}
    C["controller.animation.fuuka.fang"] = {"initial_state": "free", "states": {
        "free": {"animations": ["follow"], "transitions": [{"riding": "q.is_riding"}]},
        "riding": {"transitions": [{"free": "!q.is_riding"}]}}}
    C["controller.animation.fuuka.fang_pose"] = {"initial_state": "p0", "states": dict(
        p0={"transitions": [{"p%d" % k: "q.mark_variant == %d" % k} for k in (1, 2, 3)]},
        **{"p%d" % k: {"animations": ["pose_%d" % k], "transitions": [{"p0": "q.mark_variant != %d" % k}]}
           for k in (1, 2, 3)})}
    out["fang"] = entity("fuuka:fang", stand, g, e,
                         {"keep": "animation.fuuka.fang.keep", "follow": "animation.fuuka.fang.follow",
                          "pose_1": "animation.fuuka.fang.pose_1", "pose_2": "animation.fuuka.fang.pose_2",
                          "pose_3": "animation.fuuka.fang.pose_3", "ride": "controller.animation.fuuka.fang",
                          "pose": "controller.animation.fuuka.fang_pose"}, ["keep", "ride", "pose"])
    # 爪弾（小）
    g, e = dict(DESPAWN_G), dict(DESPAWN_E)
    e.update(aim_events("n", NAIL_ANGLES))
    A["animation.fuuka.nail.fly"] = {"animation_length": 1.55, "loop": False, "timeline": ticks(
        1.5, lambda i: ["/tp @s ^ ^ ^0.95"] + hit(1.1, 4, extra=["particle fuuka:hit_spark ~ ~1 ~"]),
        end=["@s fuuka:despawn"])}
    out["nail"] = entity("fuuka:nail", fx_base(["fuuka_fx", "inanimate"]), g, e, {"fly": "animation.fuuka.nail.fly"},
                         ["fly"])
    # ACT4 の爪弾: 最初の 1 秒は相手を追い、そのあと真っ直ぐ。当たった相手に「無限の回転」
    g, e = dict(DESPAWN_G), dict(DESPAWN_E)
    e["fuuka:act4_aim"] = {"queue_command": {"command": ["tp @s ~ ~ ~ facing %s" % NEAREST]}}
    victim = "r=1.4,tag=!%s" % SPIN
    e["fuuka:act4_hit"] = {"add": {"component_groups": ["despawn"]}, "queue_command": {"command": [
        "tag @a[%s,m=!creative] add %s" % (victim, SPIN),
        "tag @e[family=%s,type=!%s,tag=!vb_cine,tag=!vb_paused,%s] add %s" % (RIVAL_FAMILY, ID, victim, SPIN),
        "execute at @e[tag=%s,r=1.6] run summon fuuka:spin ~ ~ ~" % SPIN,
        "title @a[tag=%s,r=1.6] title §6§l無限の回転" % SPIN,
        "title @a[tag=%s,r=1.6] subtitle §e月島に近づけば回転を返せる！ 攻撃を当てても止まる" % SPIN,
        "particle fuuka:nail4_trail ~ ~ ~", "playsound random.anvil_land @a[r=24] ~ ~ ~ 1 1.8"]}}

    def nail4(i):
        if i < 20:
            cmds = ["/execute at @s facing entity %s eyes positioned ^ ^ ^0.5 run tp @s ~ ~ ~ ~ ~" % NEAREST]
        else:
            cmds = ["/tp @s ^ ^ ^0.7"]
        cmds += ["/execute if entity @a[r=1.3,m=!creative] run event entity @s fuuka:act4_hit",
                 "/execute if entity @e[family=%s,type=!%s,tag=!vb_cine,tag=!vb_paused,r=1.5] run event entity @s "
                 "fuuka:act4_hit" % (RIVAL_FAMILY, ID)]
        return cmds
    A["animation.fuuka.nail4.fly"] = {"animation_length": 3.05, "loop": False,
                                      "timeline": ticks(3.0, nail4, end=["@s fuuka:despawn"])}
    out["nail4"] = entity("fuuka:nail4", fx_base(["fuuka_fx", "inanimate"], 0.4), g, e,
                          {"fly": "animation.fuuka.nail4.fly"}, ["fly"])
    # 無限の回転: 当たった相手にくっつき、1 → 2 → 4 → 8 → 16 と倍々のダメージ
    g, e = dict(DESPAWN_G), dict(DESPAWN_E)
    e["fuuka:spin_return"] = {"add": {"component_groups": ["despawn"]}, "queue_command": {"command": [
        "tag @e[tag=%s,r=2] remove %s" % (SPIN, SPIN),
        "title @a[r=24] actionbar §e§l回転を返した！ §r§7風花に大ダメージ",
        "damage %s 30 override" % BOSS, "execute at %s run particle fuuka:spin_hole ~ ~1 ~" % BOSS,
        "execute at %s run particle fuuka:hit_spark ~ ~1 ~" % BOSS,
        "playsound random.anvil_land @a[r=24] ~ ~ ~ 1 0.6"]}}
    stages = {0.0: 1, 0.8: 2, 1.6: 4, 2.4: 8, 3.2: 16}

    def spin(i):
        t = round(i * TICK, 2)
        cmds = ["/tp @s @e[tag=%s,c=1,r=6]" % SPIN]
        if t in stages:
            cmds += ["/damage @a[tag=%s,c=1,r=1.5] %d magic entity %s" % (SPIN, stages[t], BOSS),
                     "/execute as @e[tag=%s,c=1,r=1.5] at @s run tp @s ~ ~ ~ ~60 ~" % SPIN,
                     "/title @a[tag=%s,c=1,r=1.5] actionbar §6§l無限の回転 §r§e%d ダメージ！ §7（風花に近づくか、攻撃を当てろ！）"
                     % (SPIN, stages[t]), "/playsound random.anvil_use @a[r=16] ~ ~ ~ 0.8 %.1f" % (1.0 + t * 0.3)]
        if i % 4 == 2:
            cmds.append("/execute if entity %s run event entity @s fuuka:spin_return" % BOSS.replace("c=1", "c=1,r=5"))
        return cmds
    A["animation.fuuka.spin.life"] = {"animation_length": 3.65, "loop": False, "timeline": ticks(
        3.6, spin, end=["/tag @e[tag=%s,c=1,r=2] remove %s" % (SPIN, SPIN), "@s fuuka:despawn"])}
    out["spin"] = entity("fuuka:spin", fx_base(["fuuka_fx", "inanimate"], 0.1), g, e,
                         {"life": "animation.fuuka.spin.life"}, ["life"])
    # 鳥（風符）: 相手の方へ飛び、卵を落としていく
    g, e = dict(DESPAWN_G), dict(DESPAWN_E)
    e.update({aim_name("b", a): {"queue_command": {"command": ["tp @s ~ ~ ~ facing %s" % NEAREST, "tp @s ~ ~ ~ ~%d 0" % a]}}
              for a in BIRD_ANGLES})
    A["animation.fuuka.bird.fly"] = {"animation_length": 3.05, "loop": False, "timeline": ticks(
        3.0, lambda i: ["/tp @s ^ ^ ^0.55"] + (["/summon fuuka:egg ~ ~-0.4 ~"] if i % 8 == 4 else []),
        end=["/particle fuuka:feather_burst ~ ~ ~", "@s fuuka:despawn"])}
    out["bird"] = entity("fuuka:bird", fx_base(["fuuka_fx", "inanimate"], 0.4), g, e, {"fly": "animation.fuuka.bird.fly"},
                         ["fly"])
    # 卵（爆弾）: 地面に落ちたら爆発
    g, e = dict(DESPAWN_G), dict(DESPAWN_E)
    boom = ["/damage @a[r=2.4,m=!creative] 7 entity_attack entity %s" % BOSS, "/particle fuuka:egg_boom ~ ~0.3 ~",
            "/particle fuuka:explosion ~ ~0.3 ~", "/playsound random.explode @a[r=24] ~ ~ ~ 0.5 1.6", "@s fuuka:despawn"]
    C["controller.animation.fuuka.egg"] = {"initial_state": "fall", "states": {
        "fall": {"animations": ["life"], "transitions": [{"boom": "q.is_on_ground"}]},
        "boom": {"on_entry": boom}}}
    A["animation.fuuka.egg.life"] = {"animation_length": 4.05, "loop": False, "timeline": {
        "0.00": ["/execute at @s positioned ~ ~-5 ~ run particle fuuka:egg_warn ~ ~ ~"], "4.00": boom}}
    out["egg"] = entity("fuuka:egg", fx_base(["fuuka_fx", "inanimate"], 0.3, gravity=True), g, e,
                        {"life": "animation.fuuka.egg.life", "ctrl": "controller.animation.fuuka.egg"}, ["ctrl"])
    # 人形 × 7: 風花の周りを回り、ミサイルを撃つ。どんな攻撃も 1 ダメージ（3 回で壊れる）
    g, e = dict(DESPAWN_G), dict(DESPAWN_E)
    doll_anims = {}
    for k in range(1, 8):
        g["d%d" % k] = {"minecraft:variant": {"value": k}}
        e["fuuka:doll_%d" % k] = {"add": {"component_groups": ["d%d" % k]}}

        def doll(i, k=k):
            ang = k * 360 / 7 + i * 5
            cmds = ["/execute at %s rotated %d 0 positioned ^ ^2.2 ^2.6 run tp @s ~ ~ ~ facing %s" % (BOSS, ang, NEAREST)]
            if i % 32 == (k * 4) % 32:
                cmds += ["/summon fuuka:missile ^ ^ ^0.4 fuuka:m_aim", "/particle fuuka:rainbow ~ ~ ~",
                         "/playsound firework.launch @a[r=24] ~ ~ ~ 0.5 1.4"]
            return cmds
        A["animation.fuuka.doll.o%d" % k] = {"animation_length": 12.05, "loop": False, "timeline": ticks(
            12.0, doll, end=["/particle fuuka:rainbow ~ ~ ~", "@s fuuka:despawn"])}
        doll_anims["o%d" % k] = "animation.fuuka.doll.o%d" % k
    e["fuuka:doll_hit"] = {"queue_command": {"command": ["damage @s 1 override", "particle fuuka:hit_spark ~ ~ ~"]}}
    C["controller.animation.fuuka.doll"] = {"initial_state": "pick", "states": {
        "pick": {"transitions": [{"o%d" % k: "q.variant == %d" % k} for k in range(1, 8)]},
        **{"o%d" % k: {"animations": ["o%d" % k]} for k in range(1, 8)}}}
    doll = fx_base(["fuuka_fx", "fuuka_doll", "monster"], 0.5)
    doll["minecraft:health"] = {"value": 3, "max": 3}
    doll["minecraft:damage_sensor"] = {"triggers": [
        {"cause": "override", "deal_damage": True},
        {"cause": "entity_explosion", "deal_damage": False}, {"cause": "fall", "deal_damage": False},
        {"cause": "all", "deal_damage": False, "on_damage": {"event": "fuuka:doll_hit", "target": "self"}}]}
    out["doll"] = entity("fuuka:doll", doll, g, e, dict(doll_anims, ctrl="controller.animation.fuuka.doll"), ["ctrl"])
    # ミサイル: 少しずつ相手を追う
    g, e = dict(DESPAWN_G), dict(DESPAWN_E)
    e["fuuka:m_aim"] = {"queue_command": {"command": ["tp @s ~ ~ ~ facing %s" % NEAREST]}}

    def missile(i):
        cmds = ["/tp @s ^ ^ ^0.5"]
        if i % 3 == 0 and i < 30:
            cmds = ["/execute at @s facing entity %s eyes positioned ^ ^ ^0.5 run tp @s ~ ~ ~ ~ ~" % NEAREST]
        return cmds + hit(1.2, 5, extra=["particle fuuka:explosion ~ ~1 ~",
                                         "playsound random.explode @a[r=16] ~ ~ ~ 0.4 1.8"])
    A["animation.fuuka.missile.fly"] = {"animation_length": 2.55, "loop": False, "timeline": ticks(
        2.5, missile, end=["/particle fuuka:explosion ~ ~ ~", "@s fuuka:despawn"])}
    out["missile"] = entity("fuuka:missile", fx_base(["fuuka_fx", "inanimate"]), g, e,
                            {"fly": "animation.fuuka.missile.fly"}, ["fly"])
    # 自爆スイッチの爆弾: 投げられて落ち、「ポチッ」で爆発（放っておいても 5 秒で爆発）
    g, e = dict(DESPAWN_G), dict(DESPAWN_E)
    e["fuuka:detonate"] = {"add": {"component_groups": ["despawn"]}, "queue_command": {"command": [
        "damage @a[r=3.2,m=!creative] 12 entity_attack entity %s" % BOSS, "summon fuuka:blast ~ ~0.5 ~",
        "particle fuuka:explosion ~ ~0.5 ~", "particle fuuka:shockwave ~ ~0.1 ~", "particle fuuka:debris ~ ~ ~",
        "playsound random.explode @a[r=32] ~ ~ ~ 1 1.1", "camerashake add @a[r=10] 0.5 0.3 positional"]}}
    beeps = {"%.2f" % t: ["/playsound note.pling @a[r=14] ~ ~ ~ 0.7 %.2f" % (1.0 + k * 0.12)]
             for k, t in enumerate((0.5, 1.0, 1.4, 1.7, 1.95, 2.15, 2.3, 2.45, 3.0, 3.5, 4.0, 4.4, 4.7))}
    beeps["5.00"] = ["@s fuuka:detonate"]
    A["animation.fuuka.bomb.life"] = {"animation_length": 5.05, "loop": False, "timeline": beeps}
    out["bomb"] = entity("fuuka:bomb", fx_base(["fuuka_fx", "inanimate"], 0.4, gravity=True), g, e,
                         {"life": "animation.fuuka.bomb.life"}, ["life"])
    # 弾道（見えない）: 弾と照準線を 1 マスずつ進める目印。使い終わったらすぐ消える
    A["animation.fuuka.ray.life"] = {"animation_length": 0.35, "loop": False, "timeline": {"0.30": ["@s fuuka:despawn"]}}
    out["ray"] = entity("fuuka:ray", fx_base(["fuuka_fx", "fuuka_ray", "inanimate"], 0.1), dict(DESPAWN_G), dict(DESPAWN_E),
                        {"life": "animation.fuuka.ray.life"}, ["life"])
    # 爆風（ノックバック用）
    ex = {"fuse_length": 0, "fuse_lit": True, "causes_fire": False, "breaks_blocks": False,
          "destroy_affected_by_griefing": False}
    out["blast"] = {"format_version": "1.21.0", "minecraft:entity": {
        "description": {"identifier": "fuuka:blast", "is_spawnable": False, "is_summonable": True, "is_experimental": False},
        "component_groups": {"small": {"minecraft:explode": dict(ex, power=2)}},
        "components": fx_base(["fuuka_fx", "inanimate"], 0.1),
        "events": {"minecraft:entity_spawned": {"add": {"component_groups": ["small"]}}}}}
    # 撃破カットシーンの監督
    A["animation.fuuka.director.death"] = {"animation_length": 5.6, "loop": False, "timeline": DEATH}
    out["director"] = entity("fuuka:director", fx_base(["fuuka_fx", "inanimate"], 0.1), dict(DESPAWN_G), dict(DESPAWN_E),
                             {"cut": "animation.fuuka.director.death"}, ["cut"])
    return out, A, C


# ---------------------------------------------------------------------------
# Resource Pack
# ---------------------------------------------------------------------------
def cube(origin, size, uv, inflate=0):
    c = {"origin": origin, "size": size, "uv": uv}
    if inflate:
        c["inflate"] = inflate
    return c


SWATCH = {"red": (64, 0), "black": (68, 0), "metal": (72, 0), "gold": (76, 0), "lens": (80, 0), "dark": (84, 0)}


def sw(name):
    u, v = SWATCH[name]
    return {f: {"uv": [u, v], "uv_size": [4, 4]} for f in ("north", "south", "east", "west", "up", "down")}


def geo_boss():
    """普通の腕の人型 + 右手のスナイパーライフル（テクスチャは 128x64 単位: 左半分がスキン、右半分が銃の色）"""
    rifle = [
        cube([-7, 9, -1.5], [2, 6, 3], sw("red")),            # 銃床・機関部
        cube([-7, 3, -2], [2, 6, 3.5], sw("red")),
        cube([-6.5, 4, 1.5], [1, 3, 2], sw("black")),          # 弾倉（下）
        cube([-6.5, -12, -1.0], [1, 15, 1], sw("black")),      # 銃身
        cube([-7, -13.5, -1.5], [2, 2, 2], sw("metal")),       # 銃口
        cube([-6.75, 2.5, -3.7], [1.5, 6, 1.5], sw("dark")),   # スコープ（上）
        cube([-6.5, 2.4, -3.45], [1, 0.2, 1], sw("lens")),
        cube([-7.1, 7, -2.1], [2.2, 0.6, 3.7], sw("gold")),
    ]
    bones = [
        {"name": "root", "pivot": [0, 0, 0]},
        {"name": "body", "parent": "root", "pivot": [0, 24, 0], "cubes": [
            cube([-4, 12, -2], [8, 12, 4], [16, 16]), cube([-4, 12, -2], [8, 12, 4], [16, 32], 0.25)],
         "locators": {"body_center": [0, 18, 0]}},
        {"name": "head", "parent": "body", "pivot": [0, 24, 0], "cubes": [
            cube([-4, 24, -4], [8, 8, 8], [0, 0]), cube([-4, 24, -4], [8, 8, 8], [32, 0], 0.5)],
         "locators": {"eye": [2, 28, -4.4], "head_top": [0, 33, 0]}},
        {"name": "rightArm", "parent": "body", "pivot": [-5, 22, 0], "cubes": [
            cube([-8, 12, -2], [4, 12, 4], [40, 16]), cube([-8, 12, -2], [4, 12, 4], [40, 32], 0.25)],
         "locators": {"right_hand": [-6, 11.5, 0], "reach": [-6, 4, -1.5]}},
        {"name": "rifle", "parent": "rightArm", "pivot": [-6, 12, 0], "cubes": rifle,
         "locators": {"muzzle": [-6, -14, -0.5], "scope": [-6, 6, -3.8]}},
        {"name": "leftArm", "parent": "body", "pivot": [5, 22, 0], "cubes": [
            cube([4, 12, -2], [4, 12, 4], [32, 48]), cube([4, 12, -2], [4, 12, 4], [48, 48], 0.25)],
         "locators": {"left_hand": [6, 11.5, 0]}},
        {"name": "rightLeg", "parent": "root", "pivot": [-1.9, 12, 0], "cubes": [
            cube([-3.9, 0, -2], [4, 12, 4], [0, 16]), cube([-3.9, 0, -2], [4, 12, 4], [0, 32], 0.25)],
         "locators": {"right_foot": [-2, 0, 0]}},
        {"name": "leftLeg", "parent": "root", "pivot": [1.9, 12, 0], "cubes": [
            cube([-0.1, 0, -2], [4, 12, 4], [16, 48]), cube([-0.1, 0, -2], [4, 12, 4], [0, 48], 0.25)],
         "locators": {"left_foot": [2, 0, 0]}},
    ]
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": "geometry.fuuka", "texture_width": 128, "texture_height": 64,
                        "visible_bounds_width": 4, "visible_bounds_height": 4, "visible_bounds_offset": [0, 1.5, 0]},
        "bones": bones}]}


def boss_texture(skin):
    """スキン（64x64 か高解像度）を左半分に、銃の色見本を右半分に置いた 128x64 単位のテクスチャ"""
    s = skin.width // 64
    im = ffx.Image.new("RGBA", (128 * s, 64 * s), (0, 0, 0, 0))
    im.paste(skin.crop((0, 0, 64 * s, 64 * s)), (0, 0))
    d = ffx.ImageDraw.Draw(im)
    cols = {"red": (200, 40, 45), "black": (30, 30, 36), "metal": (80, 84, 94), "gold": (216, 176, 74),
            "lens": (120, 220, 255), "dark": (46, 48, 56)}
    for name, (u, v) in SWATCH.items():
        c = cols[name]
        d.rectangle([u * s, v * s, (u + 4) * s - 1, (v + 4) * s - 1], fill=c + (255,))
        d.rectangle([u * s, (v + 3) * s, (u + 4) * s - 1, (v + 4) * s - 1], fill=tuple(int(x * 0.75) for x in c) + (255,))
    return im


def fang_cube(o, s, uv):
    return {"origin": o, "size": s, "uv": uv}


def geo_fang():
    """スタンド「牙」（オリジナル）: 細身の人型、頭に冠羽、腰に回る二重の輪、細い尾、指先に銃口"""
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": "geometry.fuuka_fang", "texture_width": 64, "texture_height": 64,
                        "visible_bounds_width": 3, "visible_bounds_height": 4, "visible_bounds_offset": [0, 1.5, 0]},
        "bones": [
            {"name": "root", "pivot": [0, 0, 0]},
            {"name": "body", "parent": "root", "pivot": [0, 22, 0], "cubes": [fang_cube([-3, 12, -1.5], [6, 10, 3], [0, 16])],
             "locators": {"core": [0, 18, -1.6]}},
            {"name": "head", "parent": "body", "pivot": [0, 22, 0], "cubes": [fang_cube([-3, 22, -3], [6, 6, 6], [0, 0])]},
            {"name": "crest", "parent": "head", "pivot": [0, 28, 1], "cubes": [
                fang_cube([-0.5, 27, -2], [1, 3, 6], [32, 0]), fang_cube([-2.5, 26.5, 1], [5, 2, 3], [48, 0])]},
            {"name": "rightArm", "parent": "body", "pivot": [-4, 21, 0], "cubes": [
                fang_cube([-6, 11, -1], [2, 10, 2], [24, 16]), fang_cube([-5.5, 9, -0.5], [1, 2, 1], [32, 32])],
             "locators": {"right_finger": [-5, 8.5, 0]}},
            {"name": "leftArm", "parent": "body", "pivot": [4, 21, 0], "cubes": [
                fang_cube([4, 11, -1], [2, 10, 2], [24, 16]), fang_cube([4.5, 9, -0.5], [1, 2, 1], [32, 32])],
             "locators": {"left_finger": [5, 8.5, 0]}},
            {"name": "tail", "parent": "body", "pivot": [0, 12, 0], "cubes": [
                fang_cube([-2, 6, -1], [4, 6, 2], [40, 16]), fang_cube([-1, 1, -0.5], [2, 5, 1], [40, 16])]},
            {"name": "ring1", "parent": "body", "pivot": [0, 14, 0], "cubes": [
                fang_cube([-6, 14, -6], [12, 0.5, 1], [0, 32]), fang_cube([-6, 14, 5], [12, 0.5, 1], [0, 32]),
                fang_cube([-6, 14, -5], [1, 0.5, 10], [0, 32]), fang_cube([5, 14, -5], [1, 0.5, 10], [0, 32])]},
            {"name": "ring2", "parent": "body", "pivot": [0, 16.5, 0], "cubes": [
                fang_cube([-4.5, 16.5, -4.5], [9, 0.5, 1], [0, 32]), fang_cube([-4.5, 16.5, 3.5], [9, 0.5, 1], [0, 32]),
                fang_cube([-4.5, 16.5, -3.5], [1, 0.5, 7], [0, 32]), fang_cube([3.5, 16.5, -3.5], [1, 0.5, 7], [0, 32])]},
        ]}]}


def geo_small():
    def box(o, s, w, h, u=0, v=0):
        return {"origin": o, "size": s, "uv": {f: {"uv": [u, v], "uv_size": [w, h]}
                                               for f in ("north", "south", "east", "west", "up", "down")}}
    return {
        "geometry.fuuka_empty": ((16, 16), [{"name": "root", "pivot": [0, 0, 0],
                                             "locators": {"center": [0, 0, 0], "hole": [0, 16, 0]}}]),
        "geometry.fuuka_nail": ((16, 16), [{"name": "nail", "pivot": [0, 0, 0], "locators": {"center": [0, 0, 0]},
                                            "cubes": [box([-0.5, -0.5, -3], [1, 1, 6], 8, 8), box([-1, -1, 2], [2, 2, 1], 8, 8, 8)]}]),
        "geometry.fuuka_nail4": ((16, 16), [{"name": "nail", "pivot": [0, 0, 0], "locators": {"center": [0, 0, 0]},
                                             "cubes": [box([-1, -1, -5], [2, 2, 10], 8, 8), box([-2, -2, 3], [4, 4, 1], 8, 8, 8),
                                                       box([-3, -3, -1], [6, 6, 0.5], 16, 8, 0, 8)]}]),
        "geometry.fuuka_bird": ((32, 16), [
            {"name": "bird", "pivot": [0, 0, 0], "locators": {"center": [0, 0, 0]},
             "cubes": [box([-1.5, -1.5, -3], [3, 3, 6], 16, 8), box([-0.5, -0.5, -4], [1, 1, 1], 8, 8, 0, 8)]},
            {"name": "wing_r", "parent": "bird", "pivot": [-1.5, 0.5, 0], "cubes": [box([-7.5, 0.5, -2], [6, 0.5, 4], 16, 8, 16)]},
            {"name": "wing_l", "parent": "bird", "pivot": [1.5, 0.5, 0], "cubes": [box([1.5, 0.5, -2], [6, 0.5, 4], 16, 8, 16)]}]),
        "geometry.fuuka_egg": ((16, 16), [{"name": "egg", "pivot": [0, 2, 0], "locators": {"center": [0, 2, 0]},
                                           "cubes": [box([-1.5, 0, -1.5], [3, 4, 3], 16, 16)]}]),
        "geometry.fuuka_doll": ((32, 32), [
            {"name": "doll", "pivot": [0, 0, 0], "locators": {"center": [0, 0, 0]},
             "cubes": [box([-2, 2, -2], [4, 4, 4], 16, 8), box([-1.5, -2, -1], [3, 4, 2], 16, 8, 16),
                       box([-1, -5, -0.5], [2, 3, 1], 16, 8, 0, 8), box([-1.5, -1, 1], [3, 3, 2], 16, 8, 16, 8)]},
            {"name": "arm_r", "parent": "doll", "pivot": [-2, 1.5, 0], "cubes": [box([-3, -1.5, -0.5], [1, 3, 1], 16, 8, 0, 8)]}]),
        "geometry.fuuka_missile": ((16, 8), [{"name": "missile", "pivot": [0, 0, 0], "locators": {"center": [0, 0, 0]},
                                              "cubes": [box([-0.75, -0.75, -2.5], [1.5, 1.5, 4], 8, 8),
                                                        box([-0.5, -0.5, -3.5], [1, 1, 1], 8, 8, 8)]}]),
        "geometry.fuuka_bomb": ((16, 16), [
            {"name": "bomb", "pivot": [0, 0, 0], "locators": {"center": [0, 0, 0]},
             "cubes": [box([-2, 0, -2], [4, 2.5, 4], 8, 8), box([-0.5, 2.5, -0.5], [1, 1, 1], 8, 8, 0, 8)]},
            {"name": "light", "parent": "bomb", "pivot": [0, 3, 0], "cubes": [box([-0.6, 3.4, -0.6], [1.2, 0.6, 1.2], 8, 8, 8)]}]),
    }


def geo_files():
    out = {}
    for ident, ((w, h), bones) in geo_small().items():
        out[ident] = {"format_version": "1.12.0", "minecraft:geometry": [{
            "description": {"identifier": ident, "texture_width": w, "texture_height": h,
                            "visible_bounds_width": 3, "visible_bounds_height": 3, "visible_bounds_offset": [0, 0.5, 0]},
            "bones": bones}]}
    return out


DOLL_COLORS = [(1.0, 0.25, 0.25), (1.0, 0.6, 0.15), (1.0, 0.9, 0.2), (0.3, 0.9, 0.35), (0.3, 0.7, 1.0), (0.35, 0.35, 1.0),
               (0.75, 0.35, 1.0)]


def render_controllers():
    v = "math.clamp(q.variant - 1, 0, 6)"
    pick = lambda i: " : ".join(["(%s == %d ? %.2f" % (v, k, DOLL_COLORS[k][i]) for k in range(6)]) + \
        " : %.2f" % DOLL_COLORS[6][i] + ")" * 6
    return {"format_version": "1.10.0", "render_controllers": {
        # 狙っている間（回避できない）は、体がうっすら赤く光る
        "controller.render.fuuka": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"],
            "overlay_color": {"r": "1.0", "g": "0.2", "b": "0.2",
                              "a": "q.property('fuuka:aim') ? 0.18 + math.sin(q.life_time * 900) * 0.08 : 0.0"}},
        "controller.render.fuuka_doll": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"],
            "overlay_color": {"r": pick(0), "g": pick(1), "b": pick(2), "a": "0.55"}},
        "controller.render.fuuka_simple": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"]},
    }}


def client(ident, tex, geo, material, animations=None, animate=None, particles=None, rc="controller.render.fuuka_simple",
           extra=None):
    d = {"identifier": ident, "materials": {"default": material}, "textures": {"default": "textures/entity/" + tex},
         "geometry": {"default": geo}, "render_controllers": rc if isinstance(rc, list) else [rc]}
    if particles:
        d["particle_effects"] = particles
    if animations:
        d["animations"] = animations
        d["scripts"] = {"animate": animate}
    if extra:
        d.update(extra)
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": d}}


def fang_client(tusk=None):
    """スタンドの見た目。tusk があれば（個人用ビルド）、手元のアドオンのモデル・テクスチャ・モーションを使う"""
    if tusk:
        anims = {"s_idle": tusk["idle"], "s_shoot": tusk["shoot"], "s_rush": tusk["rush"], "s_act4": tusk["act4"],
                 "ctrl": "controller.animation.fuuka.fang", "aura": "animation.fuuka.fang.aura_origin"}
        return client("fuuka:fang", "fuuka_tusk4", "geometry.fuuka_tusk4", "entity_emissive_alpha", anims,
                      ["ctrl", "aura"], fanims.FANG_PARTICLES)
    anims = {"s_idle": "animation.fuuka.fang.idle", "s_shoot": "animation.fuuka.fang.shoot",
             "s_rush": "animation.fuuka.fang.rush", "s_act4": "animation.fuuka.fang.act4",
             "ctrl": "controller.animation.fuuka.fang", "aura": "animation.fuuka.fang.aura",
             "spawn": "animation.fuuka.fang.spawn"}
    return client("fuuka:fang", "fuuka_fang", "geometry.fuuka_fang", "entity_alphatest", anims, ["ctrl", "aura", "spawn"],
                  fanims.FANG_PARTICLES)


def rp_clients(tusk=None):
    boss_anims = fanims.short_names(sorted(SKILLS))
    clients = {
        "fuuka": client(ID, "fuuka", "geometry.fuuka", "entity_alphatest", boss_anims, ["main", "aura_ctrl"],
                        fanims.PARTICLE_MAP, rc="controller.render.fuuka",
                        extra={"spawn_egg": {"base_color": "#d93a3a", "overlay_color": "#222222"}}),
        "fang": fang_client(tusk),
        "nail": client("fuuka:nail", "fuuka_nail", "geometry.fuuka_nail", "entity_emissive_alpha",
                       {"fx": "animation.fuuka.nail_fx"}, ["fx"], {"trail": "fuuka:nail_trail"}),
        "nail4": client("fuuka:nail4", "fuuka_nail", "geometry.fuuka_nail4", "entity_emissive_alpha",
                        {"fx": "animation.fuuka.nail4_fx"}, ["fx"], {"trail": "fuuka:nail4_trail"}),
        "spin": client("fuuka:spin", "fuuka_empty", "geometry.fuuka_empty", "entity_alphatest",
                       {"fx": "animation.fuuka.spin_fx", "hole": "animation.fuuka.spin_hole"}, ["fx", "hole"],
                       {"spin": "fuuka:spin", "hole": "fuuka:spin_hole"}),
        "bird": client("fuuka:bird", "fuuka_bird", "geometry.fuuka_bird", "entity_alphatest",
                       {"fx": "animation.fuuka.bird_fx"}, ["fx"], {"trail": "fuuka:feather"}),
        "egg": client("fuuka:egg", "fuuka_egg", "geometry.fuuka_egg", "entity_alphatest", {"fx": "animation.fuuka.egg_fx"},
                      ["fx"]),
        "doll": client("fuuka:doll", "fuuka_doll", "geometry.fuuka_doll", "entity_alphatest",
                       {"fx": "animation.fuuka.doll_fx"}, ["fx"], {"trail": "fuuka:rainbow"},
                       rc="controller.render.fuuka_doll"),
        "missile": client("fuuka:missile", "fuuka_missile", "geometry.fuuka_missile", "entity_alphatest",
                          {"fx": "animation.fuuka.missile_fx"}, ["fx"], {"trail": "fuuka:missile_trail"}),
        "bomb": client("fuuka:bomb", "fuuka_bomb", "geometry.fuuka_bomb", "entity_alphatest",
                       {"fx": "animation.fuuka.bomb_fx"}, ["fx"], {"warn": "fuuka:warn"}),
        "blast": client("fuuka:blast", "fuuka_empty", "geometry.fuuka_empty", "entity_alphatest"),
        "ray": client("fuuka:ray", "fuuka_empty", "geometry.fuuka_empty", "entity_alphatest"),
        "director": client("fuuka:director", "fuuka", "geometry.fuuka", "entity_alphatest",
                           {"pose": "animation.fuuka.director_pose"}, ["pose"]),
    }
    desc = clients["fuuka"]["minecraft:client_entity"]["description"]
    smooth_client(desc)
    desc["scripts"]["initialize"] += ["v.bird_prev = 4.0;", "v.dodge_t = -10.0;", "v.dodge = 0.0;", "v.dodge_dir = 1.0;"]
    desc["scripts"]["pre_animation"] += [
        "v.bird_now = q.property('fuuka:bird');",
        "v.dodge_dir = (v.bird_now < v.bird_prev) ? (math.mod(math.floor(q.life_time * 7), 2) * 2 - 1) : v.dodge_dir;",
        "v.dodge_t = (v.bird_now < v.bird_prev) ? q.life_time : v.dodge_t;",
        "v.bird_prev = v.bird_now;",
        "v.dodge = (q.life_time - v.dodge_t < 0.45) ? math.sin((q.life_time - v.dodge_t) * 400) : 0.0;"]
    clients["fuuka"]["minecraft:client_entity"]["description"]["animations"]["turn"] = "animation.fuuka.turn"
    return clients


def lang():
    names = {ID: NAME, "fuuka:fang": "スタンド「牙」", "fuuka:nail": "爪弾", "fuuka:nail4": "ACT4 の爪弾",
             "fuuka:spin": "無限の回転", "fuuka:bird": "鳥の弾幕", "fuuka:egg": "卵爆弾", "fuuka:doll": "月島人形",
             "fuuka:missile": "ミサイル", "fuuka:bomb": "自爆スイッチの爆弾", "fuuka:blast": "爆風", "fuuka:ray": "弾道", "fuuka:director": NAME}
    lines = ["entity.%s.name=%s" % kv for kv in names.items()]
    lines += ["item.spawn_egg.entity.%s.name=%sのスポーンエッグ" % (ID, NAME), "pack.name=月島 風花 ボス",
              "pack.description=秘密結社「花鳥風月」の社長・怪盗「月島 風花」ボスアドオン", ""]
    return "\n".join(lines)


def placeholder_skin():
    """スキン画像が無いときの仮スキン（緋色の髪・黒い服）"""
    im = ffx.Image.new("RGBA", (64, 64))
    d = ffx.ImageDraw.Draw(im)
    skin, hair, cloth = (255, 219, 172, 255), (217, 58, 58, 255), (34, 34, 34, 255)
    d.rectangle([0, 0, 31, 15], fill=hair)
    d.rectangle([8, 10, 15, 15], fill=skin)
    d.point((9, 12), fill=(230, 60, 60, 255)); d.point((14, 12), fill=(230, 60, 60, 255))
    d.rectangle([16, 16, 39, 31], fill=cloth)
    d.rectangle([40, 16, 55, 31], fill=cloth)
    d.rectangle([0, 16, 15, 31], fill=cloth)
    d.rectangle([16, 48, 31, 63], fill=cloth)
    d.rectangle([32, 48, 47, 63], fill=cloth)
    return im


# ---------------------------------------------------------------------------
# 個人用ビルド: 手元の Stand_disc アドオンから、スタンドの見た目（モデル・テクスチャ・モーション）だけ読み込む
# ---------------------------------------------------------------------------
TUSK_MAP = {"idle": "base", "shoot": "hf", "rush": "pb", "act4": "cc_pb"}


def _json_relaxed(text):
    return json.loads(re.sub(r"(?<![:\"])//[^\n]*", "", text))


def load_tusk(path):
    z = zipfile.ZipFile(path)
    names = z.namelist()

    def find(suffix):
        for n in names:
            if n.replace("\\", "/").endswith(suffix):
                return n
        raise SystemExit("アドオンの中に %s が見つかりません" % suffix)
    geo = _json_relaxed(z.read(find("models/entity/tusk4.geo.json")).decode("utf-8", "replace"))
    anims = _json_relaxed(z.read(find("animations/tusk4.animation.json")).decode("utf-8", "replace"))
    tex = z.read(find("textures/tusk/tusk4.png"))
    for g in geo["minecraft:geometry"]:
        g["description"]["identifier"] = "geometry.fuuka_tusk4"
    out_anims = {}
    for name, a in anims["animations"].items():
        a = {k: v for k, v in a.items() if k not in ("particle_effects", "sound_effects", "timeline")}
        out_anims[name.replace("animation.tusk4.", "animation.fuuka_tusk4.")] = a
    mapping = {k: "animation.fuuka_tusk4." + v for k, v in TUSK_MAP.items()}
    for k, v in mapping.items():
        if v not in out_anims:
            raise SystemExit("モーション %s が見つかりません" % v)
    vectorize_animations(out_anims)   # 拡大縮小の 1 つだけの数値を [x, y, z] にそろえる（読み込みエラー対策）
    out_anims["animation.fuuka.fang.aura_origin"] = {"loop": True, "animation_length": 0.5,
                                                     "particle_effects": {"0.00": [{"effect": "aura"}]}}
    return {"geo": geo, "anims": {"format_version": "1.10.0", "animations": out_anims}, "tex": tex, **mapping}


def zip_packs(out, packs):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for pack, arc in packs:
            for dp, _, fs in sorted(os.walk(pack)):
                for f in sorted(fs):
                    full = os.path.join(dp, f)
                    z.write(full, os.path.join(arc, os.path.relpath(full, pack)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skin", nargs="?")
    ap.add_argument("--tusk", help="個人用: Stand_disc アドオン（.mcaddon）のパス")
    args = ap.parse_args()
    kept = os.path.join(ROOT, "skin_source.png")
    if args.skin:
        shutil.copyfile(args.skin, kept)
    if os.path.exists(kept):
        skin = ffx.Image.open(kept).convert("RGBA")
    else:
        skin = placeholder_skin()
        print("スキン画像が指定されていないので、仮のスキンを使います")
    for d in (BP, RP, DIST):
        if os.path.isdir(d):
            shutil.rmtree(d)
    # BP
    write(os.path.join(BP, "manifest.json"), manifest("bp"))
    write(os.path.join(BP, "entities/fuuka.json"), bp_entity())
    sb, sa, sc = summons_bp()
    for name, data in sb.items():
        write(os.path.join(BP, "entities/%s.json" % name), data)
    anims_all = bp_animations()
    anims_all["animations"].update(sa)
    write(os.path.join(BP, "animations/fuuka.animation.json"), anims_all)
    ctrls = bp_controllers()
    ctrls["animation_controllers"].update(sc)
    write(os.path.join(BP, "animation_controllers/fuuka.ac.json"), ctrls)
    write(os.path.join(BP, "loot_tables/entities/fuuka.json"), bp_loot())
    # RP
    write(os.path.join(RP, "manifest.json"), manifest("rp"))
    os.makedirs(os.path.join(RP, "textures/entity"), exist_ok=True)
    boss_texture(skin).save(os.path.join(RP, "textures/entity/fuuka.png"))
    for name, im in ffx.entity_textures().items():
        im.save(os.path.join(RP, "textures/entity/%s.png" % name))
    for name, data in rp_clients().items():
        write(os.path.join(RP, "entity/%s.entity.json" % name), data)
    write(os.path.join(RP, "models/entity/fuuka.geo.json"), geo_boss())
    write(os.path.join(RP, "models/entity/fuuka_fang.geo.json"), geo_fang())
    for ident, data in geo_files().items():
        write(os.path.join(RP, "models/entity/%s.geo.json" % ident.split(".")[1]), data)
    ra = fanims.all_animations()
    bake_smooth(ra["animations"], step=SMOOTH_STEP)
    summ = fanims.summon_animations()
    summ["animation.fuuka.director_pose"] = ra["animations"].pop("animation.fuuka.director_pose")
    fang = fanims.fang_animations()
    bake_smooth(fang, step=SMOOTH_STEP)
    summ.update(fang)
    vectorize_animations(ra["animations"])
    vectorize_animations(summ)
    write(os.path.join(RP, "animations/fuuka.animation.json"), ra)
    write(os.path.join(RP, "animations/fuuka_summons.animation.json"), {"format_version": "1.10.0", "animations": summ})
    write(os.path.join(RP, "animation_controllers/fuuka.ac.json"), fanims.controllers(sorted(SKILLS)))
    write(os.path.join(RP, "animation_controllers/fuuka_fang.ac.json"), fanims.fang_controller(None))
    write(os.path.join(RP, "render_controllers/fuuka.rc.json"), render_controllers())
    for name, data in ffx.build_particles().items():
        write(os.path.join(RP, "particles/%s.json" % name), data)
    os.makedirs(os.path.join(RP, "textures/particle"), exist_ok=True)
    for name, im in ffx.build_textures().items():
        im.save(os.path.join(RP, "textures/particle/%s.png" % name))
    for name, data in ffx.build_fogs().items():
        write(os.path.join(RP, "fogs/%s.json" % name), data)
    s = skin.width // 64
    face = skin.crop((8 * s, 8 * s, 16 * s, 16 * s)).resize((128, 128), ffx.Image.NEAREST)
    face.alpha_composite(skin.crop((40 * s, 8 * s, 48 * s, 16 * s)).resize((128, 128), ffx.Image.NEAREST))
    for d in (BP, RP):
        for lc in ("ja_JP", "en_US"):
            write(os.path.join(d, "texts/%s.lang" % lc), lang())
        write(os.path.join(d, "texts/languages.json"), ["ja_JP", "en_US"])
        face.save(os.path.join(d, "pack_icon.png"))
    # 声・足音・守りの反応・瀕死の演出
    brushup_files(BP, RP, dict(id=ID, ns="fuuka", prop=None, react_events=[], evade_events=["fuuka:on_hit"], evade_skill=5, react_anim=None,
             prefix="animation.fuuka", main_ctrl="controller.animation.fuuka.main", glow="fuuka_glow", pitch=1.3))
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "TsukishimaFuuka_Boss.mcaddon")
    zip_packs(out, ((BP, "Fuuka_BP"), (RP, "Fuuka_RP")))
    print("built", out)

    # 個人用ビルド（--tusk）: personal/ に通常版をコピーして、スタンドの見た目だけ差し替える
    if args.tusk:
        tusk = load_tusk(args.tusk)
        if os.path.isdir(PERSONAL):
            shutil.rmtree(PERSONAL)
        pbp, prp = os.path.join(PERSONAL, "Fuuka_BP"), os.path.join(PERSONAL, "Fuuka_RP")
        shutil.copytree(BP, pbp)
        shutil.copytree(RP, prp)
        with open(os.path.join(prp, "entity/fang.entity.json"), "w", encoding="utf-8") as f:
            json.dump(fang_client(tusk), f, ensure_ascii=False, indent=2)
        with open(os.path.join(prp, "models/entity/fuuka_tusk4.geo.json"), "w", encoding="utf-8") as f:
            json.dump(tusk["geo"], f, ensure_ascii=False)
        with open(os.path.join(prp, "animations/fuuka_tusk4.animation.json"), "w", encoding="utf-8") as f:
            json.dump(tusk["anims"], f, ensure_ascii=False)
        with open(os.path.join(prp, "textures/entity/fuuka_tusk4.png"), "wb") as f:
            f.write(tusk["tex"])
        pout = os.path.join(PERSONAL, "TsukishimaFuuka_Boss_personal.mcaddon")
        zip_packs(pout, ((pbp, "Fuuka_BP"), (prp, "Fuuka_RP")))
        print("built (personal)", pout)


if __name__ == "__main__":
    main()
