# -*- coding: utf-8 -*-
"""月島 風花: クライアント側アニメーション（右手にスナイパーライフル、背後にスタンド「牙」）."""

from cine import ALIVE_ANIM, SPD, TURN_ANIM, footwork_bones, mute_controller, smooth_controller  # noqa: E402

N = [0, 0, 0]
HOLD_R, HOLD_L = [-28, -10, 0], [-24, 22, 0]          # ライフルを低く構える
AIM_R, AIM_L = [-90, 6, 0], [-88, 36, 0]              # 狙う（左手は銃身の下）
AIM_HEAD, AIM_BODY = [2, -10, 0], [0, 12, 0]
HIP_R, HIP_L = [-76, 4, 0], [-62, 30, 0]              # 腰だめ
RECOIL_R = [-106, 6, 0]


def kf(d):
    return {"%.2f" % t: v for t, v in sorted(d.items())}


def anim(length, bones, particles=None, loop="hold_on_last_frame"):
    a = {"animation_length": length, "loop": loop, "bones": {}}
    for bone, chans in bones.items():
        a["bones"][bone] = {ch: kf(keys) if isinstance(keys, dict) else keys for ch, keys in chans.items()}
    if particles:
        a["particle_effects"] = {"%.2f" % t: v for t, v in sorted(particles.items())}
    return a


def fx(effect, loc="right_hand"):
    return [{"effect": effect, "locator": loc}]


def merge(*ds):
    out = {}
    for d in ds:
        for bone, chans in d.items():
            for ch, keys in chans.items():
                out.setdefault(bone, {}).setdefault(ch, {}).update(keys)
    return out


def kneel(t0, t1, t2):
    """t0 で膝をつき、t1 まで保って、t2 で立つ"""
    return {
        "root": {"position": {0: N, t0: [0, -6, 0], t1: [0, -6, 0], t2: N}},
        "rightLeg": {"rotation": {0: N, t0: [-85, 10, 0], t1: [-85, 10, 0], t2: N}},
        "leftLeg": {"rotation": {0: N, t0: [70, -5, 0], t1: [70, -5, 0], t2: N}},
    }


def aim(t0, t1, t2, shots=(), hip=False, recoil=RECOIL_R):
    """t0 で構え、t1 まで保って、t2 で下ろす。shots の時刻で反動"""
    ar, al = (HIP_R, HIP_L) if hip else (AIM_R, AIM_L)
    r = {0: HOLD_R, t0: ar, t1: ar, t2: HOLD_R}
    l_ = {0: HOLD_L, t0: al, t1: al, t2: HOLD_L}
    for s in shots:
        r.update({s: recoil, s + 0.12: ar})
        l_.update({s: [al[0] - 10, al[1], al[2]], s + 0.12: al})
    return {"rightArm": {"rotation": r}, "leftArm": {"rotation": l_},
            "head": {"rotation": {0: N, t0: AIM_HEAD, t1: AIM_HEAD, t2: N}},
            "body": {"rotation": {0: N, t0: AIM_BODY, t1: AIM_BODY, t2: N}}}


def mergefx(*ds):
    out = {}
    for d in ds:
        for t, v in d.items():
            out[t] = out.get(t, []) + v
    return out


def bolt(t, al=AIM_L):
    """t（撃った直後）からボルトを引いて戻す: 左手が機関部へ → 引く → 押し込む → 銃身の下へ"""
    return {"leftArm": {"rotation": {t + 0.18: [-72, 52, 0], t + 0.3: [-62, 66, -8], t + 0.42: [-72, 52, 0],
                                     t + 0.55: al}},
            "head": {"rotation": {t + 0.3: [6, -14, 4], t + 0.55: AIM_HEAD}}}


def shot_fx(times):
    return {t: fx("muzzle", "muzzle") + fx("gunsmoke", "muzzle") for t in times}


def skill_anims():
    A = {}
    # 1 狙撃: 膝をついて構え、照準 → 発砲
    A[1] = anim(2.4, merge(aim(0.25, 2.1, 2.4, [1.5]), kneel(0.3, 2.1, 2.35), bolt(1.5)),
                mergefx(shot_fx([1.5]), {0.2: fx("glint", "scope"), 0.9: fx("glint", "scope"),
                                         1.8: fx("shell", "right_hand")}))
    # 2 速射: 腰だめで 3 連射
    A[2] = anim(1.8, aim(0.2, 1.45, 1.8, [0.45, 0.9, 1.35], hip=True), shot_fx([0.45, 0.9, 1.35]))
    # 3 風符「鳥の気まぐれ」: スペルカードを掲げて放つ
    A[3] = anim(3.0, {
        "leftArm": {"rotation": {0: HOLD_L, 0.3: [-172, 0, -12], 0.7: [-172, 0, -12], 0.85: [-100, 0, 0], 2.6: [-100, 0, 0],
                                 3.0: HOLD_L}},
        "rightArm": {"rotation": {0: HOLD_R, 0.3: [-15, 0, 20], 2.6: [-15, 0, 20], 3.0: HOLD_R}},
        "head": {"rotation": {0: N, 0.3: [-20, 0, 0], 0.7: [-20, 0, 0], 0.85: N}},
        "body": {"rotation": {0: N, 0.3: [-6, 0, 0], 0.85: [6, -10, 0], 2.6: [4, -8, 0], 3.0: N}},
    }, {0.3: fx("feather", "left_hand"), 0.85: fx("feather_burst", "left_hand")})
    # 4 万華鏡の虹月島人形達: 両手を広げて呼び出す
    A[4] = anim(2.0, {
        "rightArm": {"rotation": {0: HOLD_R, 0.25: [-60, 0, 55], 1.3: [-60, 0, 55], 2.0: HOLD_R}},
        "leftArm": {"rotation": {0: HOLD_L, 0.25: [-60, 0, -55], 1.3: [-60, 0, -55], 2.0: HOLD_L}},
        "head": {"rotation": {0: N, 0.25: [-12, 0, 0], 1.3: [-12, 0, 0], 2.0: N}},
        "root": {"position": {0: N, 0.25: [0, 1, 0], 1.3: [0, 1, 0], 2.0: N}},
    }, {0.3: fx("rainbow", "left_hand") + fx("rainbow", "right_hand"), 0.9: fx("rainbow", "body_center")})
    # 5 オルカブースター: 足の裏の水流で後ろへ飛びのき、腰だめで撃つ
    A[5] = anim(1.2, merge(aim(0.08, 0.9, 1.2, [0.7], hip=True), {
        "body": {"rotation": {0: N, 0.05: [-16, 12, 0], 0.4: [-12, 12, 0], 0.9: [0, 12, 0], 1.2: N}},
        "rightLeg": {"rotation": {0: N, 0.05: [-35, 0, 0], 0.4: [-25, 0, 0], 0.6: N}},
        "leftLeg": {"rotation": {0: N, 0.05: [-20, 0, 0], 0.4: [-10, 0, 0], 0.6: N}},
        "root": {"position": {0: N, 0.05: [0, 1.5, 0], 0.4: [0, 0.5, 0], 0.55: [0, -1.5, 0], 0.75: N}},
    }), mergefx(shot_fx([0.7]), {0.05: fx("water_jet", "right_foot") + fx("water_jet", "left_foot"),
                                0.2: fx("water_jet", "right_foot") + fx("water_jet", "left_foot")}))
    # 6 オルカブースター（跳躍）: 空へ跳んで、上から 2 発
    A[6] = anim(3.2, merge(aim(0.6, 2.5, 3.0, [1.7, 2.3]), {
        "root": {"position": {0: N, 0.1: [0, -2.5, 0], 0.2: [0, 1, 0], 2.7: [0, 1, 0], 2.9: [0, -2, 0], 3.2: N}},
        "rightLeg": {"rotation": {0: N, 0.1: [-30, 0, 0], 0.25: [-70, 0, 6], 2.6: [-60, 0, 6], 2.9: [-30, 0, 0], 3.2: N}},
        "leftLeg": {"rotation": {0: N, 0.1: [-30, 0, 0], 0.25: [-40, 0, -6], 2.6: [-35, 0, -6], 2.9: [-30, 0, 0], 3.2: N}},
        "head": {"rotation": {0: N, 0.6: [22, -10, 0], 2.5: [22, -10, 0], 3.0: N}},
    }), mergefx(shot_fx([1.7, 2.3]), {0.15: fx("water_jet", "right_foot") + fx("water_jet", "left_foot"),
                                     0.3: fx("water_jet", "right_foot") + fx("water_jet", "left_foot"),
                                     0.45: fx("water_jet", "right_foot") + fx("water_jet", "left_foot")}))
    # 7 ウォーターカッター: 片足を振り抜いて、足の裏から水の刃
    A[7] = anim(1.8, {
        "rightLeg": {"rotation": {0: N, 0.3: [-85, 55, 10], 0.45: [-88, 50, 10], 1.05: [-88, -55, 10], 1.3: [-30, 0, 0],
                                  1.6: N}},
        "body": {"rotation": {0: N, 0.3: [-14, -25, 0], 1.05: [-14, 30, 0], 1.6: N}},
        "rightArm": {"rotation": {0: HOLD_R, 0.3: [-40, 0, 45], 1.3: [-40, 0, 45], 1.8: HOLD_R}},
        "leftArm": {"rotation": {0: HOLD_L, 0.3: [-30, 0, -50], 1.3: [-30, 0, -50], 1.8: HOLD_L}},
        "root": {"position": {0: N, 0.3: [0, 0.6, 0], 1.3: [0, 0.6, 0], 1.6: N}},
    }, {0.45: fx("water_trail", "right_foot"), 0.65: fx("water_trail", "right_foot"), 0.85: fx("water_trail", "right_foot")})
    # 8 スタンガン: 左手で押し当てて、すぐ離れる
    A[8] = anim(1.0, {
        "leftArm": {"rotation": {0: HOLD_L, 0.08: [-40, 0, -10], 0.15: [-95, 0, 0], 0.3: [-95, 0, 0], 0.5: HOLD_L}},
        "body": {"rotation": {0: N, 0.08: [0, -20, 0], 0.15: [10, 20, 0], 0.4: [-10, 0, 0], 0.7: N}},
        "root": {"position": {0: N, 0.15: [0, -1, -1.5], 0.45: [0, 0.5, 1.5], 0.7: N}},
    }, {0.15: fx("stun", "left_hand"), 0.22: fx("stun", "left_hand")})
    # 9 自爆スイッチ: 爆弾を投げて、スイッチを「ポチッ」
    A[9] = anim(3.2, {
        "leftArm": {"rotation": {0: HOLD_L, 0.2: [-170, 0, -10], 0.4: [-60, 0, 0], 0.55: [-170, 0, -10], 0.75: [-60, 0, 0],
                                 1.0: HOLD_L, 2.2: HOLD_L, 2.4: [-100, 10, 0], 2.6: [-104, 10, 0], 2.62: [-96, 10, 0],
                                 3.0: [-100, 10, 0], 3.2: HOLD_L}},
        "head": {"rotation": {0: N, 2.4: [5, 10, 0], 3.0: [5, 10, 0], 3.2: N}},
        "body": {"rotation": {0: N, 0.2: [-8, 15, 0], 0.4: [10, -10, 0], 0.55: [-8, 15, 0], 0.75: [10, -10, 0], 1.0: N}},
    })
    # 10 牙・爪弾: スタンドに指示を出す
    A[10] = anim(1.6, {
        "leftArm": {"rotation": {0: HOLD_L, 0.2: [-92, 20, 0], 1.2: [-92, 20, 0], 1.6: HOLD_L}},
        "head": {"rotation": {0: N, 0.2: [0, 10, 0], 1.2: [0, 10, 0], 1.6: N}},
    })
    # 11 DXL-5 特殊弾: 長い溜め → 強烈な反動
    A[11] = anim(3.4, merge(aim(0.3, 3.2, 3.4, [2.6], recoil=[-125, 6, 0]), kneel(0.35, 3.2, 3.38), {
        "body": {"rotation": {0: N, 0.3: AIM_BODY, 2.6: [-14, 12, 0], 2.8: AIM_BODY, 3.2: AIM_BODY, 3.4: N}},
        "root": {"position": {2.6: [0, -6, 1.8], 2.75: [0, -6, 0]}},
    }, bolt(2.6)), mergefx(shot_fx([2.6]), {0.4: fx("charge", "muzzle"), 0.9: fx("charge", "muzzle"),
                                         1.4: fx("charge", "muzzle"), 1.9: fx("charge", "muzzle"),
                                         2.3: fx("glint", "scope"), 2.9: fx("shell", "right_hand")}))
    # 12 戯「怪盗の手癖」: 相手の懐に飛び込んで盗み、掲げて見せる
    A[12] = anim(1.6, {
        "body": {"rotation": {0: N, 0.1: [25, 0, 0], 0.45: [20, 0, 0], 0.7: N}},
        "leftArm": {"rotation": {0: HOLD_L, 0.25: [-80, -20, 0], 0.45: [-85, -10, 0], 0.7: [-40, 0, 0], 1.0: [-165, 0, -8],
                                 1.4: [-165, 0, -8], 1.6: HOLD_L}},
        "head": {"rotation": {0: N, 1.0: [-12, 0, 8], 1.4: [-12, 0, 8], 1.6: N}},
        "root": {"position": {0: N, 0.1: [0, -1.5, 0], 0.45: [0, -1.5, 0], 0.7: N}},
    }, {0.45: fx("rainbow", "left_hand"), 1.0: fx("rainbow", "left_hand")})
    # 13 雲散霧消: 薬を飲んで霧に溶け、霧の中から 2 発
    A[13] = anim(6.0, merge(aim(1.8, 4.6, 5.2, [2.4, 4.4]), {
        "leftArm": {"rotation": {0: HOLD_L, 0.3: [-150, -30, 0], 0.8: [-150, -30, 0], 1.0: HOLD_L}},
        "head": {"rotation": {0: N, 0.3: [-25, 0, 0], 0.8: [-25, 0, 0], 1.0: N}},
    }), shot_fx([2.4, 4.4]))
    # 14 ACT4「無限の回転」: スタンドに力を集め、指さして撃たせる
    A[14] = anim(4.0, {
        "leftArm": {"rotation": {0: HOLD_L, 0.4: [-165, 20, 0], 1.4: [-165, 20, 0], 1.6: [-92, 15, 0], 3.2: [-92, 15, 0],
                                 4.0: HOLD_L}},
        "rightArm": {"rotation": {0: HOLD_R, 0.4: [-20, 0, 25], 3.2: [-20, 0, 25], 4.0: HOLD_R}},
        "head": {"rotation": {0: N, 0.4: [-15, 0, 0], 1.4: [-15, 0, 0], 1.6: [0, 10, 0], 3.2: [0, 10, 0], 4.0: N}},
        "body": {"rotation": {0: N, 1.6: [6, -15, 0], 3.2: [6, -15, 0], 4.0: N}},
    }, {0.4: fx("act4", "left_hand"), 1.6: fx("act4", "left_hand")})
    # 30 登場: 煙の中から降り立ち、ライフルを回して構える
    A[30] = anim(8.0, {
        "root": {"position": {0: [0, -2.5, 0], 1.6: [0, -2.5, 0], 2.2: N}, "scale": {0: [0, 0, 0], 0.9: [0, 0, 0],
                                                                                     1.0: [1, 1, 1]}},
        "rightLeg": {"rotation": {0: [-60, 0, 0], 1.6: [-60, 0, 0], 2.2: N}},
        "leftLeg": {"rotation": {0: [40, 0, 0], 1.6: [40, 0, 0], 2.2: N}},
        "rightArm": {"rotation": {0: HOLD_R, 2.6: HOLD_R, 3.0: [-170, -10, 15], 3.6: [-150, -40, 30], 4.4: [-150, -40, 30],
                                  4.8: AIM_R, 6.4: AIM_R, 7.2: HOLD_R}},
        "leftArm": {"rotation": {0: HOLD_L, 4.4: HOLD_L, 4.8: AIM_L, 6.4: AIM_L, 7.2: HOLD_L}},
        "head": {"rotation": {0: [20, 0, 0], 1.6: [20, 0, 0], 2.4: N, 4.8: AIM_HEAD, 6.4: AIM_HEAD, 7.2: N}},
        "body": {"rotation": {0: [20, 0, 0], 1.6: [20, 0, 0], 2.4: N, 4.8: AIM_BODY, 6.4: AIM_BODY, 7.2: N}},
    }, {1.0: fx("smoke_bomb", "body_center"), 3.2: fx("feather_burst", "right_hand"), 4.8: fx("glint", "scope")})
    # 31 花鳥風月: 花 → 鳥 → 風 → 月
    A[31] = anim(7.5, {
        "rightArm": {"rotation": {0: HOLD_R, 1.2: [-120, 0, 40], 2.4: [-120, 0, 40], 2.7: [-10, 0, 85], 3.0: [-10, 0, 60],
                                  3.3: [-10, 0, 85], 3.6: [-10, 0, 60], 4.2: [-60, 0, 30], 5.6: [-60, 0, 30],
                                  5.9: [-172, 0, 8], 7.0: [-172, 0, 8], 7.5: HOLD_R}},
        "leftArm": {"rotation": {0: HOLD_L, 1.2: [-120, 0, -40], 2.4: [-120, 0, -40], 2.7: [-10, 0, -85], 3.0: [-10, 0, -60],
                                 3.3: [-10, 0, -85], 3.6: [-10, 0, -60], 4.2: [-60, 0, -30], 5.6: [-60, 0, -30],
                                 5.9: [-20, 0, -15], 7.0: [-20, 0, -15], 7.5: HOLD_L}},
        "root": {"rotation": {0: N, 4.2: N, 5.4: [0, -360, 0], 7.5: [0, -360, 0]},
                 "position": {0: N, 2.7: [0, 2, 0], 3.6: [0, 2, 0], 4.0: N}},
        "head": {"rotation": {0: N, 5.9: [-25, 0, 0], 7.0: [-25, 0, 0], 7.5: N}},
    }, {1.3: fx("petal", "body_center"), 2.8: fx("feather_burst", "body_center"), 4.4: fx("wind", "body_center"),
        6.0: fx("moon", "head_top")})
    # 32 鳥獣戯画: 鳥 → 獣 → 戯 → 画
    A[32] = anim(7.0, {
        "rightArm": {"rotation": {0: HOLD_R, 1.2: [-10, 0, 85], 1.5: [-10, 0, 60], 1.8: [-10, 0, 85], 2.6: [-30, 0, 10],
                                  3.8: [-30, 0, 10], 4.2: [-160, 30, 0], 5.0: [-160, 30, 0], 5.4: [-95, 30, 0],
                                  6.5: [-95, 30, 0], 7.0: HOLD_R}},
        "leftArm": {"rotation": {0: HOLD_L, 1.2: [-10, 0, -85], 1.5: [-10, 0, -60], 1.8: [-10, 0, -85], 2.6: [-30, 0, -10],
                                 3.8: [-30, 0, -10], 4.2: [-160, -30, 0], 5.0: [-160, -30, 0], 5.4: [-95, -30, 0],
                                 6.5: [-95, -30, 0], 7.0: HOLD_L}},
        "body": {"rotation": {0: N, 2.6: [38, 0, 0], 3.8: [38, 0, 0], 4.2: N}},
        "root": {"position": {0: N, 2.6: [0, -3, 0], 3.8: [0, -3, 0], 4.2: N}},
        "head": {"rotation": {0: N, 2.6: [-30, 0, 0], 3.8: [-30, 0, 0], 4.2: [0, 0, 15], 5.0: [0, 0, -15], 5.4: N}},
    }, {1.3: fx("feather_burst", "body_center"), 2.7: fx("stand_aura", "body_center"), 4.3: fx("rainbow", "head_top"),
        5.5: fx("glint", "right_hand")})
    # 60 / 61 / 62 立ち回り（腕を突き出す ＝ 腰だめで撃つ）
    for v, kind in ((60, "back"), (61, "right"), (62, "left")):
        L = 1.1 if kind == "back" else 1.3
        t = 0.52 if kind == "back" else 0.58
        bones = footwork_bones(kind, HOLD_R, "punch")
        bones["leftArm"] = {"rotation": {0: HOLD_L, t - 0.1: HIP_L, t + 0.3: HIP_L, L: HOLD_L}}
        A[v] = anim(L, bones, shot_fx([t]))
    return A


NO_LOOK = {30, 31, 32}


def all_animations():
    walk = "q.modified_distance_moved * 38.17"
    spd = SPD
    anims = {
        "animation.fuuka.look_at": {"loop": True, "bones": {
            "head": {"rotation": ["q.target_x_rotation", "q.target_y_rotation", 0]}}},
        "animation.fuuka.idle": {"loop": True, "bones": {
            "body": {"rotation": ["math.sin(q.life_time * 100) * 1.2", "math.sin(q.life_time * 45) * 3", 0]},
            "head": {"rotation": [0, 0, "math.sin(q.life_time * 50) * 3"]},
            "rightArm": {"rotation": ["-28 + math.sin(q.life_time * 100) * 2", "-10", 0]},
            "leftArm": {"rotation": ["-24 + math.sin(q.life_time * 100) * 2", "22", 0]},
            "rightLeg": {"rotation": [0, 8, 2]},
        }},
        # 軽い身のこなしの走り: 前傾、ライフルはぶらさず、跳ねるように
        "animation.fuuka.move": {"loop": True, "bones": {
            "root": {"position": [0, "math.abs(math.cos(%s)) * 1.4 * %s" % (walk, spd), 0]},
            "body": {"rotation": ["16 * %s" % spd, "math.cos(%s) * 6 * %s" % (walk, spd), 0]},
            "head": {"rotation": ["-12 * %s" % spd, 0, 0]},
            "rightArm": {"rotation": ["-10 * %s" % spd, "-20 * %s" % spd, 0]},
            "leftArm": {"rotation": ["math.cos(%s) * 55 * %s + 20 * %s" % (walk, spd, spd), "-22 * %s" % spd, "-6 * %s" % spd]},
            "rightLeg": {"rotation": ["math.cos(%s) * 70 * %s" % (walk, spd), 0, 0]},
            "leftLeg": {"rotation": ["math.cos(%s + 180) * 70 * %s" % (walk, spd), 0, 0]},
        }},
        "animation.fuuka.move_legs": {"loop": True, "bones": {
            "rightLeg": {"rotation": ["math.cos(%s) * 55 * %s" % (walk, spd), 0, 0]},
            "leftLeg": {"rotation": ["math.cos(%s + 180) * 55 * %s" % (walk, spd), 0, 0]},
        }},
        "animation.fuuka.hurt": {"loop": True, "bones": {
            "body": {"rotation": ["-v.flinch * 14", 0, 0]},
            "head": {"rotation": ["-v.flinch * 10", 0, "v.flinch * 10"]},
        }},
        # 待機中のしぐさ（12 秒ごと）: ライフルを肩に担ぐ → きょろきょろ見回す
        "animation.fuuka.idle_flavor": anim(12.0, {
            "rightArm": {"rotation": {0: N, 1.6: N, 2.1: [-150, -18, 16], 3.0: [-150, -18, 16], 3.4: N, 6.6: N,
                                      7.2: [-122, -18, 30], 8.8: [-122, -18, 30], 9.3: N, 12.0: N}},
            "leftArm": {"rotation": {0: N, 4.0: N, 4.4: [-142, 26, -14], 5.2: [-142, 26, -14], 5.6: N, 12.0: N}},
            "head": {"rotation": {0: N, 1.6: N, 2.1: [10, -16, 10], 3.0: [10, -16, 10], 3.4: N, 4.0: N,
                                  4.4: [0, 8, -12], 5.2: [0, 8, -12], 5.6: N, 9.6: N, 10.0: [0, 35, 0], 10.5: [0, 35, 0],
                                  10.9: [0, -35, 0], 11.4: [0, -35, 0], 11.8: N, 12.0: N}},
            "body": {"rotation": {0: N, 4.0: N, 4.4: [0, -10, 4], 5.2: [0, -10, 4], 5.6: N, 12.0: N}},
        }, {2.5: fx("gunsmoke", "muzzle"), 4.5: fx("glint_s", "left_hand"), 7.3: fx("feather", "head_top")}, loop=True),
        # 回避した瞬間: ひらりと身をひねって跳ぶ（回避ゲージが減ったのを見て再生）
        "animation.fuuka.dodge": {"loop": True, "bones": {
            "root": {"rotation": [0, "v.dodge * v.dodge_dir * 45", 0], "position": [0, "v.dodge * 2.0", 0]},
            "body": {"rotation": ["-v.dodge * 14", 0, "v.dodge * v.dodge_dir * 32"]},
            "head": {"rotation": ["v.dodge * 10", "-v.dodge * v.dodge_dir * 25", 0]},
            "rightArm": {"rotation": ["-v.dodge * 45", 0, "v.dodge * 28"]},
            "leftArm": {"rotation": ["-v.dodge * 25", 0, "-v.dodge * 48"]},
            "rightLeg": {"rotation": ["-v.dodge * 35", 0, "v.dodge * 14"]},
            "leftLeg": {"rotation": ["v.dodge * 30", 0, "-v.dodge * 14"]}}},
        "animation.fuuka.step_fx": {"loop": True, "animation_length": 0.46, "particle_effects": {
            "0.00": [{"effect": "step", "locator": "right_foot"}], "0.23": [{"effect": "step", "locator": "left_foot"}]}},
        # 花鳥風月（HP60%）から: ときどき花びらと羽 / 鳥獣戯画（HP30%）から: 赤い羽と金の光
        "animation.fuuka.aura_1": {"loop": True, "animation_length": 0.9, "particle_effects": {
            "0.00": [{"effect": "feather", "locator": "body_center"}], "0.45": [{"effect": "glint_s", "locator": "head_top"}]}},
        "animation.fuuka.aura_2": {"loop": True, "animation_length": 0.5, "particle_effects": {
            "0.00": [{"effect": "feather_red", "locator": "body_center"}],
            "0.25": [{"effect": "stand_aura", "locator": "body_center"}]}},
        "animation.fuuka.death": anim(1.0, {"body": {"rotation": {0: N, 0.4: [20, 0, 0]}}}),
        # 撃破: 座り込んで笑い、煙玉で消える
        "animation.fuuka.director_pose": anim(5.6, {
            "root": {"position": {0: [0, -10, 0]}, "scale": {0: [0, 0, 0], 1.05: [0, 0, 0], 1.1: [1, 1, 1],
                                                              4.4: [1, 1, 1], 4.6: [0, 0, 0]}},
            "rightLeg": {"rotation": {0: [-90, 15, 0]}}, "leftLeg": {"rotation": {0: [-90, -15, 0]}},
            "rightArm": {"rotation": {0: [-40, -10, 20], 3.0: [-40, -10, 20], 3.4: [-160, 0, 20], 4.4: [-160, 0, 20]}},
            "leftArm": {"rotation": {0: [-30, 0, -20]}},
            "head": {"rotation": {0: [10, 0, 8], 2.0: [10, 0, -8], 3.4: [-10, 0, 0]}}}),
    }
    for v, a in skill_anims().items():
        anims["animation.fuuka.skill_%d" % v] = a
    anims["animation.fuuka.turn"] = TURN_ANIM
    anims["animation.fuuka.alive"] = ALIVE_ANIM
    return {"format_version": "1.10.0", "animations": anims}


def short_names(skill_ids):
    n = {"look_at": "animation.fuuka.look_at", "idle": "animation.fuuka.idle", "move": "animation.fuuka.move",
         "move_legs": "animation.fuuka.move_legs", "hurt": "animation.fuuka.hurt",
         "idle_flavor": "animation.fuuka.idle_flavor", "step_fx": "animation.fuuka.step_fx",
         "aura_1": "animation.fuuka.aura_1", "aura_2": "animation.fuuka.aura_2", "death_pose": "animation.fuuka.death",
         "turn": "animation.fuuka.turn", "alive": "animation.fuuka.alive", "dodge": "animation.fuuka.dodge",
         "main": "controller.animation.fuuka.main", "aura_ctrl": "controller.animation.fuuka.aura"}
    for v in skill_ids:
        n["s%d" % v] = "animation.fuuka.skill_%d" % v
    return n


def controllers(skill_ids):
    dead = {"death": "!q.is_alive"}
    states = {"default": {"animations": ["look_at", "idle", "move", "hurt", "dodge",
                                         {"idle_flavor": "q.modified_move_speed < 0.3"},
                                         {"step_fx": "q.modified_move_speed > 0.4"}],
                          "transitions": [dead] + [{"s%d" % v: "q.mark_variant == %d" % v} for v in skill_ids],
                          "blend_transition": 0.1},
              "death": {"animations": ["death_pose"]}}
    for v in skill_ids:
        a = ["s%d" % v] if v in NO_LOOK else ["look_at", "s%d" % v]
        a += [{"move_legs": "q.modified_move_speed > 0.1"}, "hurt", "dodge"]
        states["s%d" % v] = {"animations": a, "transitions": [dead, {"default": "q.mark_variant != %d" % v}],
                             "blend_transition": 0.08}
    return mute_controller(smooth_controller({"format_version": "1.10.0", "animation_controllers": {
        "controller.animation.fuuka.main": {"initial_state": "default", "states": states},
        "controller.animation.fuuka.aura": {"initial_state": "none", "states": {
            "none": {"transitions": [{"a2": "q.skin_id >= 2"}, {"a1": "q.skin_id == 1"}]},
            "a1": {"animations": ["aura_1"], "transitions": [{"a2": "q.skin_id >= 2"}, {"none": "!q.is_alive"}]},
            "a2": {"animations": ["aura_2"], "transitions": [{"none": "!q.is_alive"}]}}},
    }}, "controller.animation.fuuka.main"), "controller.animation.fuuka.main")


PARTICLE_MAP = {"arc": "fuuka:arc", "step": "fuuka:step_dust", "muzzle": "fuuka:muzzle", "gunsmoke": "fuuka:gunsmoke",
                "glint": "fuuka:scope_glint", "glint_s": "fuuka:scope_glint", "feather": "fuuka:feather",
                "feather_red": "fuuka:feather_red", "feather_burst": "fuuka:feather_burst", "rainbow": "fuuka:rainbow",
                "water_jet": "fuuka:water_jet", "water_trail": "fuuka:water_trail", "stun": "fuuka:stun",
                "charge": "fuuka:charge_red", "act4": "fuuka:act4_charge", "shell": "fuuka:shell", "smoke_bomb": "fuuka:smoke_bomb",
                "petal": "fuuka:petal", "wind": "fuuka:wind", "moon": "fuuka:moon", "stand_aura": "fuuka:stand_aura"}


# ---------------------------------------------------------------------------
# スタンド「牙」（オリジナルのモデル用）
# ---------------------------------------------------------------------------
def fang_animations():
    rings = {"ring1": {"rotation": [0, "q.life_time * (q.mark_variant == 3 ? 900 : 160)", 0]},
             "ring2": {"rotation": [0, "-q.life_time * (q.mark_variant == 3 ? 700 : 110)", 0]}}
    rush_r, rush_l = {0: [-20, 0, 15]}, {0: [-20, 0, -15]}
    for i in range(18):
        t = 0.1 + i * 0.1
        if i % 2 == 0:
            rush_r.update({t: [-95, -10, 0], t + 0.05: [-40, 10, 10]})
        else:
            rush_l.update({t: [-95, 10, 0], t + 0.05: [-40, -10, -10]})
    rush_r[2.0] = [-20, 0, 15]
    rush_l[2.0] = [-20, 0, -15]
    return {
        "animation.fuuka.fang.idle": {"loop": True, "bones": dict(rings, **{
            "root": {"position": [0, "math.sin(q.life_time * 90) * 1.2", 0],
                     "scale": ["math.min(q.life_time * 2.5, 1)"] * 3},
            "head": {"rotation": ["math.sin(q.life_time * 60) * 4", "math.sin(q.life_time * 40) * 6", 0]},
            "crest": {"rotation": ["math.sin(q.life_time * 220) * 6", 0, 0]},
            "rightArm": {"rotation": ["-20 + math.sin(q.life_time * 90) * 4", 0, 15]},
            "leftArm": {"rotation": ["-20 + math.sin(q.life_time * 90 + 60) * 4", 0, -15]},
            "tail": {"rotation": ["math.sin(q.life_time * 120) * 10", 0, "math.sin(q.life_time * 80) * 6"]}})},
        "animation.fuuka.fang.spawn": {"loop": False, "animation_length": 0.6, "particle_effects": {
            "0.00": [{"effect": "charge", "locator": "core"}], "0.30": [{"effect": "aura", "locator": "core"}]}},
        "animation.fuuka.fang.aura": {"loop": True, "animation_length": 0.5,
                                      "particle_effects": {"0.00": [{"effect": "aura", "locator": "core"}]}},
        "animation.fuuka.fang.shoot": anim(1.0, {
            "rightArm": {"rotation": {0: [-20, 0, 15], 0.12: [-90, 0, 0], 0.2: [-98, 0, 0], 0.27: [-90, 0, 0],
                                      0.35: [-98, 0, 0], 0.42: [-90, 0, 0], 0.5: [-98, 0, 0], 0.57: [-90, 0, 0],
                                      0.65: [-98, 0, 0], 0.8: [-90, 0, 0], 1.0: [-20, 0, 15]}},
            "body": {"rotation": {0: N, 0.12: [0, -15, 0], 0.8: [0, -15, 0], 1.0: N}},
        }, {t: fx("nail", "right_finger") for t in (0.2, 0.35, 0.5, 0.65, 0.8)}),
        "animation.fuuka.fang.rush": anim(2.0, {"rightArm": {"rotation": rush_r}, "leftArm": {"rotation": rush_l},
                                                "body": {"rotation": {0: N, 0.1: [12, 0, 0], 1.9: [12, 0, 0], 2.0: N}}},
                                          {t: fx("nail", "right_finger") for t in (0.1, 0.5, 0.9, 1.3, 1.7)}),
        "animation.fuuka.fang.act4": anim(2.4, {
            "rightArm": {"rotation": {0: [-20, 0, 15], 0.3: [-165, 0, 20], 1.4: [-165, 0, 20], 1.55: [-92, 0, 0],
                                      2.0: [-92, 0, 0], 2.4: [-20, 0, 15]}},
            "leftArm": {"rotation": {0: [-20, 0, -15], 0.3: [-165, 0, -20], 1.4: [-165, 0, -20], 1.55: [-30, 0, -30],
                                     2.4: [-20, 0, -15]}},
            "head": {"rotation": {0: N, 0.3: [-20, 0, 0], 1.4: [-20, 0, 0], 1.55: [5, 0, 0], 2.4: N}},
            "root": {"position": {0: N, 0.3: [0, 3, 0], 1.4: [0, 3, 0], 1.6: N}},
        }, {0.3: fx("charge", "core"), 0.8: fx("charge", "core"), 1.55: fx("nail4", "right_finger")}),
    }


def fang_controller(names):
    """スタンドのポーズ（mark_variant: 0 待機 / 1 爪弾 / 2 ラッシュ / 3 ACT4）"""
    return {"format_version": "1.10.0", "animation_controllers": {"controller.animation.fuuka.fang": {
        "initial_state": "idle", "states": {
            "idle": {"animations": ["s_idle"], "transitions": [{"shoot": "q.mark_variant == 1"}, {"rush": "q.mark_variant == 2"},
                                                               {"act4": "q.mark_variant == 3"}], "blend_transition": 0.15},
            "shoot": {"animations": ["s_idle", "s_shoot"], "transitions": [{"idle": "q.mark_variant != 1"}],
                      "blend_transition": 0.2},
            "rush": {"animations": ["s_idle", "s_rush"], "transitions": [{"idle": "q.mark_variant != 2"}],
                     "blend_transition": 0.2},
            "act4": {"animations": ["s_idle", "s_act4"], "transitions": [{"idle": "q.mark_variant != 3"}],
                     "blend_transition": 0.2},
        }}}}


FANG_PARTICLES = {"aura": "fuuka:stand_aura", "nail": "fuuka:nail_trail", "nail4": "fuuka:nail4_trail",
                  "charge": "fuuka:act4_charge"}


def summon_animations():
    def emit(effect, every, loc="center", bones=None):
        a = {"loop": True, "animation_length": every, "particle_effects": {"0.00": [{"effect": effect, "locator": loc}]}}
        if bones:
            a["bones"] = bones
        return a
    return {
        "animation.fuuka.nail_fx": emit("trail", 0.05, bones={"nail": {"rotation": [0, 0, "q.life_time * 1800"]}}),
        "animation.fuuka.nail4_fx": emit("trail", 0.1, bones={"nail": {"rotation": [0, 0, "q.life_time * 2400"]}}),
        "animation.fuuka.spin_fx": emit("spin", 0.15),
        "animation.fuuka.spin_hole": emit("hole", 0.3, "hole"),
        "animation.fuuka.bird_fx": emit("trail", 0.3, bones={
            "wing_r": {"rotation": [0, 0, "math.sin(q.life_time * 1400) * 40"]},
            "wing_l": {"rotation": [0, 0, "-math.sin(q.life_time * 1400) * 40"]}}),
        "animation.fuuka.egg_fx": {"loop": True, "bones": {"egg": {"rotation": ["q.life_time * 400", 0, "q.life_time * 250"]}}},
        "animation.fuuka.doll_fx": emit("trail", 0.8, bones={
            "doll": {"position": [0, "math.sin(q.life_time * 200) * 1", 0]},
            "arm_r": {"rotation": ["-90 + math.sin(q.life_time * 300) * 10", 0, 0]}}),
        "animation.fuuka.missile_fx": emit("trail", 0.05),
        "animation.fuuka.bomb_fx": emit("warn", 0.5, bones={
            "light": {"scale": ["1 + (math.mod(math.floor(q.life_time * (4 + q.life_time * 5)), 2) == 0 ? 0.6 : 0)"] * 3}}),
    }
