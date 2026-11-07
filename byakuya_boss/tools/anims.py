# -*- coding: utf-8 -*-
"""クライアント側（RP）のアニメーションとアニメーションコントローラー."""

N = [0, 0, 0]
HOLD_R = [-25, -10, 0]   # 普段の右腕（刀を前に）


def kf(d):
    return {"%.2f" % t: v for t, v in sorted(d.items())}


def anim(length, bones, particles=None, loop="hold_on_last_frame"):
    a = {"animation_length": length, "loop": loop, "bones": {}}
    for bone, chans in bones.items():
        a["bones"][bone] = {ch: kf(keys) for ch, keys in chans.items()}
    if particles:
        a["particle_effects"] = {"%.2f" % t: v for t, v in sorted(particles.items())}
    return a


def fx(effect, loc="right_hand"):
    return [{"effect": effect, "locator": loc}]


def kneel(t0, t1, depth=-6):
    """t0〜t1 の間、片膝をつく"""
    return {
        "root": {"position": {0: N, t0: [0, depth, 0], t1: [0, depth, 0]}},
        "rightLeg": {"rotation": {0: N, t0: [-85, 10, 0], t1: [-85, 10, 0]}},
        "leftLeg": {"rotation": {0: N, t0: [70, -5, 0], t1: [70, -5, 0]}},
    }


def merge(*ds):
    out = {}
    for d in ds:
        for bone, chans in d.items():
            for ch, keys in chans.items():
                out.setdefault(bone, {}).setdefault(ch, {}).update(keys)
    return out


def skill_anims():
    A = {}

    # 1 瞬閃: 抜刀の構え → 一閃
    A[1] = anim(1.0, {
        "root": {"position": {0: N, 0.15: [0, -2, 0], 0.4: [0, -2, 0], 0.5: [0, -1, 0], 1.0: N}},
        "body": {"rotation": {0: N, 0.15: [15, 35, 0], 0.4: [15, 35, 0], 0.5: [10, -45, 0], 0.8: [5, -35, 0], 1.0: N}},
        "rightArm": {"rotation": {0: HOLD_R, 0.15: [-40, 65, 0], 0.4: [-40, 65, 0], 0.5: [-90, -85, 0],
                                  0.8: [-80, -75, 0], 1.0: HOLD_R}},
        "leftArm": {"rotation": {0: N, 0.15: [-35, 30, 0], 0.4: [-35, 30, 0], 0.5: [20, 0, 0], 1.0: N}},
        "rightLeg": {"rotation": {0: N, 0.15: [-30, 0, 0], 0.8: [-30, 0, 0], 1.0: N}},
        "leftLeg": {"rotation": {0: N, 0.15: [25, 0, 0], 0.8: [25, 0, 0], 1.0: N}},
    }, {0.1: fx("hand_charge"), 0.45: fx("sword_trail") + fx("sword_trail", "body_center")})

    # 2 天地雷鳴: 刀を天に掲げ、雷のたびに振り下ろす
    arm, body = {0: HOLD_R, 0.3: [-180, 0, 0]}, {0: N, 0.3: [-12, 0, 0]}
    for t in (0.6, 1.2, 1.8):
        arm[t - 0.05] = [-180, 0, 0]
        arm[t + 0.08] = [-150, 0, 0]
        arm[t + 0.3] = [-180, 0, 0]
    arm.update({2.25: [-180, 0, 0], 2.4: [-50, 0, 0], 2.6: HOLD_R})
    body.update({2.25: [-12, 0, 0], 2.4: [20, 0, 0], 2.6: N})
    A[2] = anim(2.6, {"rightArm": {"rotation": arm}, "body": {"rotation": body},
                      "leftArm": {"rotation": {0: N, 0.3: [-30, 0, 0], 2.4: [-30, 0, 0], 2.6: N}}},
                {0.3: fx("hand_charge"), 0.9: fx("hand_charge"), 1.5: fx("hand_charge"), 2.4: fx("sword_trail")})

    # 3 火炎の狂滅: 刀を突き出して高速回転
    A[3] = anim(2.2, {
        "root": {"rotation": {0: N, 0.2: [0, 90, 0], 2.0: [0, 1530, 0], 2.2: [0, 1620, 0]}},
        "body": {"rotation": {0: N, 0.2: [10, 0, 0], 2.0: [10, 0, 0], 2.2: N}},
        "rightArm": {"rotation": {0: HOLD_R, 0.2: [-90, -10, 0], 2.0: [-90, -10, 0], 2.2: HOLD_R}},
        "leftArm": {"rotation": {0: N, 0.2: [-20, 0, 0], 2.0: [-20, 0, 0], 2.2: N}},
    }, {t / 10: fx("sword_trail_red") for t in range(2, 21, 2)})

    # 4 水没の重滅: 両腕でゆっくり持ち上げ、一気に叩きつける
    A[4] = anim(3.0, {
        "rightArm": {"rotation": {0: HOLD_R, 1.8: [-170, 10, 0], 2.0: [-40, 0, 0], 2.8: [-40, 0, 0], 3.0: HOLD_R}},
        "leftArm": {"rotation": {0: N, 1.8: [-170, -10, 0], 2.0: [-40, 0, 0], 2.8: [-40, 0, 0], 3.0: N}},
        "body": {"rotation": {0: N, 1.8: [-15, 0, 0], 2.0: [30, 0, 0], 2.8: [30, 0, 0], 3.0: N}},
        "root": {"position": {0: N, 1.8: [0, 1, 0], 2.0: [0, -3, 0], 2.8: [0, -3, 0], 3.0: N}},
    }, {0.2: fx("hand_charge", "left_hand"), 1.0: fx("hand_charge", "left_hand"), 2.0: fx("sword_trail")})

    # 5 樹海の誘滅: 左手で手招きし、引き寄せて斬る
    beckon = {0: N}
    for i in range(6):
        t = 0.15 + i * 0.25
        beckon[t] = [-95, 0, 0]
        beckon[t + 0.12] = [-60, 0, 0]
    beckon.update({1.6: [10, 0, 0], 2.0: N})
    A[5] = anim(2.0, {
        "leftArm": {"rotation": beckon},
        "rightArm": {"rotation": {0: HOLD_R, 0.2: [-35, 60, 0], 1.55: [-35, 60, 0], 1.7: [-95, -90, 0], 2.0: HOLD_R}},
        "body": {"rotation": {0: N, 0.2: [0, 20, 0], 1.55: [0, 20, 0], 1.7: [5, -45, 0], 2.0: N}},
    }, {1.7: fx("sword_trail") + fx("sword_trail", "body_center")})

    # 6 スコーピオン: 刀を地面に突き立てる
    A[6] = anim(1.8, merge(kneel(0.35, 1.5), {
        "root": {"position": {0: N, 1.8: N}},
        "rightLeg": {"rotation": {0: N, 1.8: N}}, "leftLeg": {"rotation": {0: N, 1.8: N}},
        "rightArm": {"rotation": {0: HOLD_R, 0.2: [-175, 0, 0], 0.35: [-40, 0, 0], 1.5: [-40, 0, 0], 1.8: HOLD_R}},
        "leftArm": {"rotation": {0: N, 0.2: [-160, 0, 0], 0.35: [-45, 0, 0], 1.5: [-45, 0, 0], 1.8: N}},
        "body": {"rotation": {0: N, 0.35: [35, 0, 0], 1.5: [35, 0, 0], 1.8: N}},
    }), {0.35: fx("sword_trail")})

    # 7 千本投擲: 左右交互に投げる
    r, l, b = {0: HOLD_R}, {0: N}, {0: N}
    for i in range(7):
        t = 0.4 + i * 0.25
        if i % 2 == 0:
            r[t] = [-165, 0, 0]; r[t + 0.12] = [-40, -10, 0]
            b[t + 0.12] = [5, -15, 0]
        else:
            l[t] = [-165, 0, 0]; l[t + 0.12] = [-40, 10, 0]
            b[t + 0.12] = [5, 15, 0]
    r[2.4], l[2.4], b[2.4] = HOLD_R, N, N
    A[7] = anim(2.4, {"rightArm": {"rotation": r}, "leftArm": {"rotation": l}, "body": {"rotation": b}},
                {0.2: fx("blade_halo", "body_center")})

    # 8 ホッパー: 腕を交差させて防御
    A[8] = anim(4.0, {
        "rightArm": {"rotation": {0: HOLD_R, 0.2: [-95, -40, 0], 3.8: [-95, -40, 0], 4.0: HOLD_R}},
        "leftArm": {"rotation": {0: N, 0.2: [-95, 40, 0], 3.8: [-95, 40, 0], 4.0: N}},
        "root": {"position": {0: N, 1.0: [0, -1, 0], 2.0: N, 3.0: [0, -1, 0], 4.0: N}},
    })

    # 9 武装解除: 指差し → はじく
    A[9] = anim(1.2, {
        "leftArm": {"rotation": {0: N, 0.15: [-90, 0, 0], 0.3: [-115, 25, 0], 0.9: [-115, 25, 0], 1.2: N}},
        "body": {"rotation": {0: N, 0.15: [0, -20, 0], 0.9: [0, -20, 0], 1.2: N}},
    }, {0.3: fx("sword_trail", "left_hand")})

    # 10 鋼糸: 糸を引き絞る → 消えて斬る
    A[10] = anim(2.0, {
        "rightArm": {"rotation": {0: HOLD_R, 0.15: [-90, -25, 0], 0.35: [-25, -45, 0], 1.2: [-25, -45, 0],
                                  1.3: [-40, 65, 0], 1.65: [-40, 65, 0], 1.75: [-95, -85, 0], 2.0: HOLD_R}},
        "leftArm": {"rotation": {0: N, 0.15: [-90, 25, 0], 0.35: [-25, 45, 0], 1.2: [-25, 45, 0], 1.3: N}},
        "body": {"rotation": {0: N, 0.35: [-10, 0, 0], 1.2: [-10, 0, 0], 1.3: [15, 35, 0], 1.65: [15, 35, 0],
                              1.75: [10, -45, 0], 2.0: N}},
    }, {0.35: fx("hand_charge") + fx("hand_charge", "left_hand"), 1.75: fx("sword_trail")})

    # 11 集散: 回転しながら乱れ斬り
    r, b = {0: HOLD_R}, {0: N}
    for i in range(12):
        t = 0.3 + i * 0.24
        r[t] = [-90, 75, 0] if i % 2 == 0 else [-100, -75, 0]
        b[t] = [5, 30, 0] if i % 2 == 0 else [5, -30, 0]
    r[3.2], b[3.2] = HOLD_R, N
    A[11] = anim(3.2, {
        "root": {"rotation": {0: N, 3.0: [0, 720, 0], 3.2: [0, 720, 0]}},
        "rightArm": {"rotation": r}, "body": {"rotation": b},
        "leftArm": {"rotation": {0: N, 0.3: [-30, 0, -10], 3.0: [-30, 0, -10], 3.2: N}},
    }, {0.4 + i * 0.5: fx("sword_trail_red") for i in range(6)})

    # 12 無刀 無残: 居合の構えで震えながら溜め → 一閃して残心
    trem = {0: N}
    for i in range(14):
        trem[0.1 + i * 0.1] = [20 + (i % 2), 40, 0]
    trem.update({1.5: [0, -65, 0], 2.4: [0, -60, 0]})
    A[12] = anim(2.4, merge(kneel(0.1, 1.45, -3), {
        "root": {"position": {0: N, 1.5: [0, -2, 0], 2.4: [0, -2, 0]}},
        "rightLeg": {"rotation": {0: N, 1.5: [-35, 0, 0], 2.4: [-35, 0, 0]}},
        "leftLeg": {"rotation": {0: N, 1.5: [30, 0, 0], 2.4: [30, 0, 0]}},
        "body": {"rotation": trem},
        "rightArm": {"rotation": {0: HOLD_R, 0.1: [-30, 75, 0], 1.45: [-30, 75, 0], 1.5: [-95, -115, 0], 2.4: [-90, -110, 0]}},
        "leftArm": {"rotation": {0: N, 0.1: [-40, 30, 0], 1.45: [-40, 30, 0], 1.5: [15, 0, 0], 2.4: [15, 0, 0]}},
    }), {**{0.1 + i * 0.25: fx("hand_charge") for i in range(6)}, 1.5: fx("sword_trail") + fx("sword_trail", "body_center")})

    # 20 最終演技（10.8 秒）: 膝をつく → 立ち上がる → 宙に浮き大上段 → 渾身の一太刀
    hover = {0: N, 2.2: [0, -6, 0], 3.6: N}
    for i in range(10):
        hover[4.2 + i * 0.5] = [0, 8 + (i % 2), 0]
    hover.update({9.15: [0, 10, 0], 9.3: [0, -2, 0], 10.8: [0, -2, 0]})
    A[20] = anim(10.8, merge(kneel(0.2, 2.2), {
        "root": {"position": hover},
        "rightLeg": {"rotation": {3.6: N, 9.3: [-40, 0, 0], 10.8: [-40, 0, 0]}},
        "leftLeg": {"rotation": {3.6: N, 9.3: [35, 0, 0], 10.8: [35, 0, 0]}},
        "body": {"rotation": {0: N, 0.2: [30, 0, 0], 2.2: [30, 0, 0], 3.6: [-10, 0, 0], 9.15: [-15, 0, 0],
                              9.3: [45, 0, 0], 10.8: [40, 0, 0]}},
        "head": {"rotation": {0: N, 0.2: [20, 0, 0], 2.2: [20, 0, 0], 3.6: N}},
        "rightArm": {"rotation": {0: HOLD_R, 0.2: [-15, 0, 0], 2.2: [-15, 0, 0], 4.2: [-180, 0, 0],
                                  9.15: [-185, 0, 0], 9.3: [-25, 0, 0], 10.8: [-25, 0, 0]}},
        "leftArm": {"rotation": {0: N, 0.2: [-20, 0, 0], 2.2: [-20, 0, 0], 4.2: [-170, 0, 0],
                                 9.15: [-175, 0, 0], 9.3: [-25, 0, 0], 10.8: [-25, 0, 0]}},
    }), {**{4.2 + i * 0.4: fx("hand_charge") + fx("aura_soul", "body_center") for i in range(12)},
         9.3: fx("sword_trail_red") + fx("sword_trail_red", "body_center")})

    # 13 飛燕斬月: 右→左、左→右と二度の横薙ぎで斬撃を飛ばす
    A[13] = anim(1.2, {
        "rightArm": {"rotation": {0: HOLD_R, 0.2: [-90, 80, 0], 0.32: [-90, -85, 0], 0.65: [-95, -85, 0],
                                  0.8: [-90, 80, 0], 1.0: [-90, 80, 0], 1.2: HOLD_R}},
        "body": {"rotation": {0: N, 0.2: [5, 30, 0], 0.32: [5, -35, 0], 0.65: [5, -35, 0], 0.8: [5, 30, 0],
                              1.0: [5, 30, 0], 1.2: N}},
        "leftArm": {"rotation": {0: N, 0.3: [-20, 0, 0], 1.0: [-20, 0, 0], 1.2: N}},
        "rightLeg": {"rotation": {0: N, 0.2: [-25, 0, 0], 1.0: [-25, 0, 0], 1.2: N}},
        "leftLeg": {"rotation": {0: N, 0.2: [20, 0, 0], 1.0: [20, 0, 0], 1.2: N}},
    }, {0.3: fx("sword_trail_red"), 0.8: fx("sword_trail_red")})

    # 14 追刃: 左手を天に掲げて刀を呼び、前へ振り下ろして放つ
    A[14] = anim(1.2, {
        "leftArm": {"rotation": {0: N, 0.2: [-175, 0, 0], 0.6: [-175, 0, 0], 0.75: [-80, 0, 0], 1.2: N}},
        "rightArm": {"rotation": {0: HOLD_R, 0.2: [-15, 0, 0], 1.0: [-15, 0, 0], 1.2: HOLD_R}},
        "body": {"rotation": {0: N, 0.2: [-8, 0, 0], 0.6: [-8, 0, 0], 0.75: [10, 0, 0], 1.2: N}},
    }, {0.2: fx("hand_charge", "left_hand"), 0.45: fx("hand_charge", "left_hand")})

    # 15 遠当て: 居合の構えで狙いを定め、一気に抜き放つ
    trem = {0: N}
    for i in range(10):
        trem[0.1 + i * 0.1] = [15 + (i % 2), 35, 0]
    trem.update({1.2: [0, -55, 0], 1.9: [0, -50, 0], 2.1: N})
    A[15] = anim(2.1, {
        "body": {"rotation": trem},
        "root": {"position": {0: N, 0.1: [0, -2, 0], 1.15: [0, -2, 0], 1.2: [0, -1, 0], 1.9: [0, -1, 0], 2.1: N}},
        "rightArm": {"rotation": {0: HOLD_R, 0.1: [-30, 70, 0], 1.15: [-30, 70, 0], 1.2: [-90, -95, 0],
                                  1.9: [-90, -90, 0], 2.1: HOLD_R}},
        "leftArm": {"rotation": {0: N, 0.1: [-40, 30, 0], 1.15: [-40, 30, 0], 1.2: [-90, 20, 0],
                                 1.9: [-90, 20, 0], 2.1: N}},
        "rightLeg": {"rotation": {0: N, 0.1: [-30, 0, 0], 1.9: [-30, 0, 0], 2.1: N}},
        "leftLeg": {"rotation": {0: N, 0.1: [30, 0, 0], 1.9: [30, 0, 0], 2.1: N}},
    }, {**{0.1 + i * 0.25: fx("hand_charge") for i in range(4)},
        1.2: fx("sword_trail_red") + fx("sword_trail", "body_center")})

    # 16 流星刀: 刀を天へ突き上げ、振り下ろして刃の雨を呼ぶ
    A[16] = anim(2.8, {
        "rightArm": {"rotation": {0: HOLD_R, 0.25: [-180, 0, 0], 0.9: [-180, 0, 0], 1.1: [-60, 0, 0],
                                  2.5: [-60, 0, 0], 2.8: HOLD_R}},
        "leftArm": {"rotation": {0: N, 0.25: [-170, 0, 0], 0.9: [-170, 0, 0], 1.1: [-30, 0, 0], 2.8: N}},
        "body": {"rotation": {0: N, 0.25: [-15, 0, 0], 0.9: [-15, 0, 0], 1.1: [15, 0, 0], 2.5: [15, 0, 0], 2.8: N}},
    }, {0.25: fx("hand_charge"), 0.6: fx("hand_charge"), 1.1: fx("sword_trail_red")})

    # 17 三段斬り: 踏み込みながら三連撃 → 唐竹割り
    r, b = {0: HOLD_R}, {0: N}
    for i, t in enumerate((0.3, 0.65, 1.0)):
        r[t - 0.1] = [-90, 80, 0] if i % 2 == 0 else [-90, -80, 0]
        r[t] = [-95, -85, 0] if i % 2 == 0 else [-95, 85, 0]
        b[t] = [10, -35, 0] if i % 2 == 0 else [10, 35, 0]
    r.update({1.25: [-185, 0, 0], 1.4: [-30, 0, 0], 1.7: HOLD_R})
    b.update({1.25: [-10, 0, 0], 1.4: [35, 0, 0], 1.7: N})
    A[17] = anim(1.7, {"rightArm": {"rotation": r}, "body": {"rotation": b},
                       "leftArm": {"rotation": {0: N, 1.25: [-170, 0, 0], 1.4: [-30, 0, 0], 1.7: N}},
                       "rightLeg": {"rotation": {0: N, 0.3: [-35, 0, 0], 1.4: [-35, 0, 0], 1.7: N}},
                       "leftLeg": {"rotation": {0: N, 0.3: [30, 0, 0], 1.4: [30, 0, 0], 1.7: N}}},
                {0.3: fx("sword_trail"), 0.65: fx("sword_trail"), 1.0: fx("sword_trail"), 1.4: fx("sword_trail_red")})

    # 18 兜割り: しゃがんで跳躍 → 空中で大上段 → 落下と同時に叩き割る
    A[18] = anim(1.8, merge(kneel(1.3, 1.6, -4), {
        "root": {"position": {0.2: [0, -3, 0], 0.3: N, 1.25: N, 1.8: N}},
        "rightLeg": {"rotation": {0.3: [-20, 0, 0], 1.25: [-20, 0, 0], 1.8: N}},
        "leftLeg": {"rotation": {0.3: [-40, 0, 0], 1.25: [-40, 0, 0], 1.8: N}},
        "rightArm": {"rotation": {0: HOLD_R, 0.3: [-185, 0, 0], 1.25: [-185, 0, 0], 1.3: [-35, 0, 0],
                                  1.6: [-35, 0, 0], 1.8: HOLD_R}},
        "leftArm": {"rotation": {0: N, 0.3: [-175, 0, 0], 1.25: [-175, 0, 0], 1.3: [-35, 0, 0], 1.6: [-35, 0, 0],
                                 1.8: N}},
        "body": {"rotation": {0: N, 0.3: [-15, 0, 0], 1.25: [-15, 0, 0], 1.3: [40, 0, 0], 1.6: [40, 0, 0], 1.8: N}},
    }), {0.5: fx("hand_charge"), 1.3: fx("sword_trail_red") + fx("sword_trail_red", "body_center")})

    # 19 見切り: 静かな居合の構え（攻撃されると即座に反撃）
    A[19] = anim(2.5, {
        "root": {"position": {0: N, 0.2: [0, -2, 0], 2.3: [0, -2, 0], 2.5: N}},
        "body": {"rotation": {0: N, 0.2: [12, 40, 0], 2.3: [12, 40, 0], 2.5: N}},
        "rightArm": {"rotation": {0: HOLD_R, 0.2: [-30, 75, 0], 2.3: [-30, 75, 0], 2.5: HOLD_R}},
        "leftArm": {"rotation": {0: N, 0.2: [-40, 30, 0], 2.3: [-40, 30, 0], 2.5: N}},
        "rightLeg": {"rotation": {0: N, 0.2: [-25, 0, 0], 2.3: [-25, 0, 0], 2.5: N}},
        "leftLeg": {"rotation": {0: N, 0.2: [25, 0, 0], 2.3: [25, 0, 0], 2.5: N}},
    })

    # 21 影分身: 刀を立てて構え、影を生む
    A[21] = anim(1.2, {
        "rightArm": {"rotation": {0: HOLD_R, 0.2: [-70, 25, 0], 0.9: [-70, 25, 0], 1.2: HOLD_R}},
        "leftArm": {"rotation": {0: N, 0.2: [-70, -25, 0], 0.9: [-70, -25, 0], 1.2: N}},
        "body": {"rotation": {0: N, 0.6: [0, 0, 0], 1.2: N}},
    }, {0.2: fx("hand_charge") + fx("hand_charge", "left_hand")})

    # 22 燕返し: 斬り上げ → 返す刀で二連撃
    A[22] = anim(1.5, {
        "rightArm": {"rotation": {0: HOLD_R, 0.2: [-10, 30, 0], 0.32: [-185, 0, 0], 0.85: [-185, 0, 0],
                                  0.95: [-60, -40, 0], 1.1: [-90, 85, 0], 1.25: [-95, -85, 0], 1.5: HOLD_R}},
        "body": {"rotation": {0: N, 0.2: [20, 15, 0], 0.32: [-15, 0, 0], 0.85: [-15, 0, 0], 0.95: [25, 0, 0],
                              1.25: [5, -35, 0], 1.5: N}},
        "leftArm": {"rotation": {0: N, 0.32: [-40, 0, 0], 1.25: [-40, 0, 0], 1.5: N}},
    }, {0.32: fx("sword_trail"), 0.95: fx("sword_trail"), 1.25: fx("sword_trail_red")})

    # 23 森羅万象: 回転しながら全方位へ斬撃を放つ
    A[23] = anim(3.0, {
        "root": {"rotation": {0: N, 0.5: [0, 180, 0], 2.6: [0, 1260, 0], 3.0: [0, 1440, 0]}},
        "rightArm": {"rotation": {0: HOLD_R, 0.4: [-90, -20, 0], 2.6: [-90, -20, 0], 3.0: HOLD_R}},
        "leftArm": {"rotation": {0: N, 0.4: [-90, 20, 0], 2.6: [-90, 20, 0], 3.0: N}},
    }, {t / 10: fx("sword_trail_red") for t in range(4, 27, 3)})
    # 24 地走り・波紋: 振りかぶっては地面に突き立てる × 4
    r, bd, rt = {0: HOLD_R}, {0: N}, {0: N}
    for t0 in (0.5, 1.1, 1.7, 2.3):
        r.update({t0 - 0.25: [-175, 0, 0], t0: [-40, 0, 0], t0 + 0.2: [-40, 0, 0]})
        bd.update({t0 - 0.25: [-10, 0, 0], t0: [35, 0, 0], t0 + 0.2: [35, 0, 0]})
        rt.update({t0 - 0.25: N, t0: [0, -3, 0], t0 + 0.2: [0, -3, 0]})
    r.update({3.0: HOLD_R}); bd.update({3.0: N}); rt.update({3.0: N})
    A[24] = anim(4.4, {"rightArm": {"rotation": r}, "body": {"rotation": bd}, "root": {"position": rt},
                       "leftArm": {"rotation": {0: N, 0.3: [-160, 0, 0], 2.5: [-160, 0, 0], 3.0: N}}},
                {t0: fx("sword_trail_red") for t0 in (0.5, 1.1, 1.7, 2.3)})

    # 25 百花繚乱: 居合の構え → 斬り抜け × 6 → 納刀
    r, bd, rt, rl, ll = {0: HOLD_R, 0.2: [-30, 70, 0]}, {0: N, 0.2: [15, 40, 0]}, {0: N}, {0: N}, {0: N}
    for k in range(6):
        t = 1.0 + 0.5 * k
        r.update({t: [-30, 70, 0], t + 0.24: [-30, 70, 0], t + 0.27: [-95, -90, 0], t + 0.45: [-90, -80, 0]})
        bd.update({t: [15, 40, 0], t + 0.24: [15, 40, 0], t + 0.27: [25, -45, 0], t + 0.45: [20, -40, 0]})
        rt.update({t + 0.24: [0, -1, 0], t + 0.27: [0, -3, 0], t + 0.45: [0, -2, 0]})
        rl.update({t + 0.27: [-45, 0, 0]}); ll.update({t + 0.27: [40, 0, 0]})
    r.update({4.2: [-30, 70, 0], 4.4: [-20, 60, 0], 4.8: HOLD_R})
    bd.update({4.2: [10, 30, 0], 4.4: [15, 0, 0], 4.8: N})
    rt.update({4.2: N}); rl.update({4.2: N}); ll.update({4.2: N})
    A[25] = anim(4.8, {"rightArm": {"rotation": r}, "body": {"rotation": bd}, "root": {"position": rt},
                       "rightLeg": {"rotation": rl}, "leftLeg": {"rotation": ll},
                       "leftArm": {"rotation": {0: N, 0.2: [-40, 30, 0], 4.2: [-40, 30, 0], 4.8: N}}},
                {**{1.27 + 0.5 * k: fx("sword_trail_red") + fx("petal", "body_center") for k in range(6)},
                 0.2: fx("hand_charge"), 4.4: fx("petal", "body_center")})

    # 26 鞘鳴り: 静かな居合 → 鍔鳴り（納刀）
    trem = {0: N, 0.2: [10, 40, 0]}
    for i in range(16):
        trem[1.2 + i * 0.15] = [10 + (i % 2) * 0.7, 40, 0]
    trem.update({3.55: [10, 40, 0], 3.65: [20, 0, 0], 4.2: [15, 0, 0]})
    A[26] = anim(4.2, {
        "body": {"rotation": trem},
        "root": {"position": {0: N, 0.2: [0, -2, 0], 3.55: [0, -2, 0], 3.65: N}},
        "rightArm": {"rotation": {0: HOLD_R, 0.2: [-30, 75, 0], 3.55: [-30, 75, 0], 3.6: [-95, -90, 0],
                                  3.65: [-20, 60, 0], 4.2: [-20, 60, 0]}},
        "leftArm": {"rotation": {0: N, 0.2: [-40, 30, 0], 3.65: [-40, 30, 0], 4.2: [-30, 20, 0]}},
        "rightLeg": {"rotation": {0: N, 0.2: [-25, 0, 0], 3.65: [-25, 0, 0], 4.2: N}},
        "leftLeg": {"rotation": {0: N, 0.2: [25, 0, 0], 3.65: [25, 0, 0], 4.2: N}},
    }, {1.2: fx("hand_charge"), 3.6: fx("sword_trail") + fx("sword_trail", "body_center")})

    # 27 業火螺旋: 刀を天に掲げて回り、最後に叩きつける
    A[27] = anim(2.6, {
        "root": {"rotation": {0: N, 0.3: [0, 60, 0], 1.95: [0, 600, 0], 2.0: [0, 720, 0], 2.6: [0, 720, 0]}},
        "rightArm": {"rotation": {0: HOLD_R, 0.3: [-180, 0, 0], 1.95: [-180, 0, 0], 2.05: [-40, 0, 0],
                                  2.6: HOLD_R}},
        "leftArm": {"rotation": {0: N, 0.3: [-90, 0, 0], 1.95: [-90, 0, 0], 2.05: [-30, 0, 0], 2.6: N}},
        "body": {"rotation": {0: N, 1.95: [-10, 0, 0], 2.05: [35, 0, 0], 2.6: N}},
    }, {**{0.4 + i * 0.25: fx("sword_trail_red") for i in range(7)}, 2.05: fx("sword_trail_red", "body_center")})

    # 30 登場: 煙管をふかす → 抜刀して構える
    A[30] = anim(4.4, {
        "leftArm": {"rotation": {0: [-125, 35, 0], 2.0: [-125, 35, 0], 2.4: N, 4.4: N}},
        "head": {"rotation": {0: [10, 0, 0], 0.6: [-8, 0, 0], 1.2: [10, 0, 0], 2.4: N}},
        "rightArm": {"rotation": {0: [-10, 0, 0], 2.5: [-30, 70, 0], 2.7: [-30, 70, 0], 2.8: [-95, -90, 0],
                                  3.2: [-90, -80, 0], 3.8: HOLD_R}},
        "body": {"rotation": {0: N, 2.5: [10, 35, 0], 2.7: [10, 35, 0], 2.8: [10, -40, 0], 3.8: N}},
    }, {0.5: fx("smoke", "left_hand"), 1.0: fx("smoke", "left_hand"), 1.5: fx("smoke", "left_hand"),
        2.8: fx("sword_trail") + fx("sword_trail", "body_center")})

    # 31 終焉化: うずくまって力を溜め → 咆哮 → 構え直す
    trem = {0: N}
    for i in range(12):
        trem[0.2 + i * 0.2] = [30 + (i % 2) * 2, 0, 0]
    trem.update({2.75: [30, 0, 0], 2.85: [-25, 0, 0], 3.7: [-25, 0, 0], 4.0: N})
    A[31] = anim(5.0, merge(kneel(0.2, 2.75, -4), {
        "root": {"position": {2.85: N, 5.0: N}},
        "rightLeg": {"rotation": {2.85: N}}, "leftLeg": {"rotation": {2.85: N}},
        "body": {"rotation": trem},
        "rightArm": {"rotation": {0: HOLD_R, 0.2: [-10, 0, 20], 2.75: [-10, 0, 20], 2.85: [-160, 0, 40],
                                  3.7: [-160, 0, 40], 4.0: HOLD_R}},
        "leftArm": {"rotation": {0: N, 0.2: [-10, 0, -20], 2.75: [-10, 0, -20], 2.85: [-160, 0, -40],
                                 3.7: [-160, 0, -40], 4.0: N}},
        "head": {"rotation": {0: N, 0.2: [30, 0, 0], 2.75: [30, 0, 0], 2.85: [-35, 0, 0], 3.7: [-35, 0, 0], 4.0: N}},
    }), {2.85: fx("sword_trail_red", "body_center") + fx("aura_flame", "right_foot") + fx("aura_flame", "left_foot")})

    # 32 宿敵: 相手に刀の切っ先を向ける
    A[32] = anim(9.0, {
        "rightArm": {"rotation": {0: HOLD_R, 4.5: HOLD_R, 4.8: [-90, 0, 0], 7.8: [-90, 0, 0], 8.1: HOLD_R}},
        "body": {"rotation": {0: N, 4.8: [0, 10, 0], 7.8: [0, 10, 0], 8.1: N}},
        "leftArm": {"rotation": {0: N, 1.0: [-125, 35, 0], 2.4: [-125, 35, 0], 2.8: N}},
    }, {1.3: fx("smoke", "left_hand"), 4.8: fx("sword_trail")})
    return A


def all_animations():
    walk = "q.modified_distance_moved * 38.17"
    spd = "math.min(q.modified_move_speed, 1.0)"
    anims = {
        "animation.byakuya.look_at": {"loop": True, "bones": {
            "head": {"rotation": ["q.target_x_rotation", "q.target_y_rotation", 0]}}},
        "animation.byakuya.idle": {"loop": True, "bones": {
            "body": {"rotation": ["math.sin(q.life_time * 100) * 1.2", 0, 0]},
            "rightArm": {"rotation": ["-25 + math.sin(q.life_time * 100) * 2.5", "-10", 0]},
            "leftArm": {"rotation": ["math.sin(q.life_time * 100) * -2", 0, "-3"]},
        }},
        "animation.byakuya.move": {"loop": True, "bones": {
            "body": {"rotation": ["8 * %s" % spd, "math.cos(%s) * 6 * %s" % (walk, spd), 0]},
            "rightArm": {"rotation": ["math.cos(%s + 180) * 20 * %s" % (walk, spd), 0, 0]},
            "leftArm": {"rotation": ["math.cos(%s) * 45 * %s" % (walk, spd), 0, 0]},
            "rightLeg": {"rotation": ["math.cos(%s) * 60 * %s" % (walk, spd), 0, 0]},
            "leftLeg": {"rotation": ["math.cos(%s + 180) * 60 * %s" % (walk, spd), 0, 0]},
        }},
        # 袈裟斬り
        "animation.byakuya.attack": {"loop": True, "bones": {
            "rightArm": {"rotation": ["-math.sin(variable.attack_time * 180) * 130",
                                      "60 - variable.attack_time * 120", 0]},
            "body": {"rotation": ["math.sin(variable.attack_time * 180) * 10",
                                  "math.sin(variable.attack_time * 180) * -30", 0]},
        }},
        "animation.byakuya.aura": {"loop": True, "animation_length": 0.4, "particle_effects": {
            "0.00": [{"effect": "aura_flame", "locator": "right_foot"}, {"effect": "aura_flame", "locator": "left_foot"}],
            "0.20": [{"effect": "aura_flame", "locator": "body_center"}],
        }},
        "animation.byakuya.final_aura": {"loop": True, "animation_length": 0.4, "particle_effects": {
            "0.00": [{"effect": "aura_soul", "locator": "right_foot"}, {"effect": "aura_flame", "locator": "left_foot"}],
            "0.20": [{"effect": "aura_soul", "locator": "body_center"}, {"effect": "aura_flame", "locator": "right_hand"}],
        }},
        "animation.byakuya.death": anim(1.5, merge(kneel(0.4, 1.5), {
            "body": {"rotation": {0: N, 0.4: [40, 0, 0], 1.5: [45, 0, 0]}},
            "rightArm": {"rotation": {0: HOLD_R, 0.4: [-20, 0, 0], 1.5: [-15, 0, 0]}},
            "leftArm": {"rotation": {0: N, 0.4: [-10, 0, 10], 1.5: [-5, 0, 10]}},
        })),
    }
    for v, a in skill_anims().items():
        anims["animation.byakuya.skill_%d" % v] = a
    return {"format_version": "1.10.0", "animations": anims}


def short_names(skill_ids):
    names = {
        "look_at": "animation.byakuya.look_at", "idle": "animation.byakuya.idle",
        "move": "animation.byakuya.move", "attack": "animation.byakuya.attack",
        "aura": "animation.byakuya.aura", "final_aura": "animation.byakuya.final_aura",
        "death_pose": "animation.byakuya.death",
        "main": "controller.animation.byakuya.main", "aura_ctrl": "controller.animation.byakuya.aura",
        "attack_fx": "controller.animation.byakuya.attack_fx",
    }
    for v in skill_ids:
        names["s%d" % v] = "animation.byakuya.skill_%d" % v
    return names


NO_LOOK = {3, 11, 20, 23, 27}  # 回転する技・最終演技は頭を固定しない


def controllers(skill_ids):
    dead = {"death": "!q.is_alive"}
    default = {
        "animations": ["look_at", "idle", "move", {"attack": "variable.attack_time > 0"}],
        "transitions": [dead] + [{"s%d" % v: "q.mark_variant == %d" % v} for v in skill_ids],
        "blend_transition": 0.12,
    }
    states = {"default": default,
              "death": {"animations": ["death_pose"]}}
    for v in skill_ids:
        anims_ = ["s%d" % v] if v in NO_LOOK else ["look_at", "s%d" % v]
        states["s%d" % v] = {"animations": anims_,
                             "transitions": [dead, {"default": "q.mark_variant != %d" % v}],
                             "blend_transition": 0.1}
    return {"format_version": "1.10.0", "animation_controllers": {
        "controller.animation.byakuya.main": {"initial_state": "default", "states": states},
        "controller.animation.byakuya.aura": {"initial_state": "none", "states": {
            "none": {"transitions": [{"final": "q.skin_id >= 2"}, {"aura": "q.skin_id == 1"}]},
            "aura": {"animations": ["aura"], "transitions": [{"final": "q.skin_id >= 2"}, {"none": "!q.is_alive"}]},
            "final": {"animations": ["final_aura"], "transitions": [{"none": "!q.is_alive"}]},
        }},
        "controller.animation.byakuya.attack_fx": {"initial_state": "ready", "states": {
            "ready": {"transitions": [{"swing": "variable.attack_time > 0.25"}]},
            "swing": {"particle_effects": [{"effect": "sword_trail", "locator": "right_hand"}],
                      "transitions": [{"ready": "variable.attack_time <= 0.0 || variable.attack_time < 0.2"}]},
        }},
    }}


PARTICLE_MAP = {
    "smoke": "byakuya:smoke_puff", "petal": "byakuya:petal_burst",
    "sword_trail": "byakuya:sword_trail", "sword_trail_red": "byakuya:sword_trail_red",
    "hand_charge": "byakuya:hand_charge", "aura_flame": "byakuya:aura_flame",
    "aura_soul": "byakuya:aura_soul", "blade_halo": "byakuya:blade_halo",
}
