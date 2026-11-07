# -*- coding: utf-8 -*-
"""ソフィア・ハート: クライアント側アニメーション（細腕モデル・右手に紺碧刀）."""

from cine import ALIVE_ANIM, SPD, TURN_ANIM, footwork_bones, smooth_controller  # noqa: E402

N = [0, 0, 0]
HOLD = [-20, -8, 0]          # 普段の右腕（刀を軽く前に）
IAI_R, IAI_B = [-30, 70, 0], [12, 40, 0]   # 居合の構え
SLASH_R, SLASH_B = [-95, -90, 0], [10, -45, 0]
CAST = [-90, 0, 0]          # 腕を前に突き出す
UP = [-175, 0, 0]


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


def dash_slashes(times, length, flip=False):
    """居合 → 一閃 を times の各時刻で"""
    r, b, rt = {0: HOLD, 0.15: IAI_R}, {0: N, 0.15: IAI_B}, {0: N}
    for t in times:
        r.update({t - 0.05: IAI_R, t: SLASH_R, t + 0.15: [-90, -80, 0]})
        b.update({t - 0.05: IAI_B, t: SLASH_B, t + 0.15: [8, -40, 0]})
        rt.update({t - 0.05: [0, -1, 0], t: [0, -3, 0], t + 0.15: [0, -2, 0]})
    end = max(times) + 0.4
    r[end], b[end], rt[end] = HOLD, N, N
    return anim(length, {"rightArm": {"rotation": r}, "body": {"rotation": b}, "root": {"position": rt},
                         "leftArm": {"rotation": {0: N, 0.15: [-40, 30, 0], end: N}}},
                {t: fx("trail") + fx("trail", "body_center") for t in times})


def skill_anims():
    A = {}
    A[1] = dash_slashes([0.3], 1.0)
    # 2 三段蹴り: 右・左・右回し蹴り（最後は打ち上げ）
    A[2] = anim(1.4, {
        "rightLeg": {"rotation": {0: N, 0.3: [-95, 0, 0], 0.45: N, 0.85: [-100, 0, 20], 0.95: [-120, 0, 0], 1.2: N}},
        "leftLeg": {"rotation": {0: N, 0.55: [-95, 0, 0], 0.7: N}},
        "body": {"rotation": {0: N, 0.3: [-15, 0, 0], 0.55: [-15, 20, 0], 0.85: [-20, -60, 0], 0.95: [-25, -120, 0],
                              1.2: N}},
        "root": {"position": {0: N, 0.85: [0, 1, 0], 0.95: [0, 3, 0], 1.2: N},
                 "rotation": {0: N, 0.85: [0, 0, 0], 1.0: [0, -180, 0], 1.25: [0, -360, 0], 1.4: [0, -360, 0]}},
        "rightArm": {"rotation": {0: HOLD, 0.3: [20, 0, 20], 1.2: HOLD}},
        "leftArm": {"rotation": {0: N, 0.3: [20, 0, -20], 1.2: N}},
    }, {0.35: fx("spark", "right_foot"), 0.6: fx("spark", "left_foot"), 0.95: fx("spark", "right_foot")})
    # 3 一閃連撃・改: 左右の連撃 × 5
    r, b = {0: HOLD}, {0: N}
    for i, t in enumerate((0.3, 0.6, 0.9, 1.2, 1.5)):
        r[t - 0.1] = [-90, 80, 0] if i % 2 == 0 else [-90, -80, 0]
        r[t] = [-95, -85, 0] if i % 2 == 0 else [-95, 85, 0]
        b[t] = [10, -35, 0] if i % 2 == 0 else [10, 35, 0]
    r[1.8], b[1.8] = HOLD, N
    A[3] = anim(1.8, {"rightArm": {"rotation": r}, "body": {"rotation": b}},
                {t: fx("trail") for t in (0.3, 0.6, 0.9, 1.2, 1.5)})
    # 4 ガーラ: 両手を胸の前で合わせ → 解き放つ
    A[4] = anim(1.2, {
        "rightArm": {"rotation": {0: HOLD, 0.2: [-70, 40, 0], 0.45: [-70, 40, 0], 0.5: [-150, 0, 40], 1.0: [-150, 0, 40],
                                  1.2: HOLD}},
        "leftArm": {"rotation": {0: N, 0.2: [-70, -40, 0], 0.45: [-70, -40, 0], 0.5: [-150, 0, -40], 1.0: [-150, 0, -40],
                                 1.2: N}},
        "body": {"rotation": {0: N, 0.45: [15, 0, 0], 0.5: [-15, 0, 0], 1.2: N}},
    }, {0.2: fx("electric") + fx("electric", "left_hand"), 0.5: fx("electric", "body_center")})
    # 5 ヴァルガーラ: 指を天に → 振り下ろす × 3
    l = {0: N}
    for t in (0.55, 1.05, 1.55):
        l.update({t - 0.3: UP, t: [-60, 0, 0]})
    l[1.9] = N
    A[5] = anim(2.0, {"leftArm": {"rotation": l}, "head": {"rotation": {0: N, 0.25: [-25, 0, 0], 1.9: N}}},
                {0.25: fx("electric", "left_hand"), 0.75: fx("electric", "left_hand"), 1.25: fx("electric", "left_hand")})
    # 6 ヴァーラ: 左手で突風を押し出す
    A[6] = anim(1.2, {
        "leftArm": {"rotation": {0: N, 0.25: [-60, 40, 0], 0.4: CAST, 0.9: CAST, 1.2: N}},
        "body": {"rotation": {0: N, 0.25: [0, 25, 0], 0.4: [5, -10, 0], 1.2: N}},
        "rightLeg": {"rotation": {0: N, 0.4: [-25, 0, 0], 0.9: [-25, 0, 0], 1.2: N}},
    }, {0.4: fx("glow", "left_hand")})
    # 7 竜巻: 腕を回して風を巻き上げる
    A[7] = anim(1.0, {
        "root": {"rotation": {0: N, 0.8: [0, 360, 0], 1.0: [0, 360, 0]}},
        "leftArm": {"rotation": {0: N, 0.1: [-90, 0, -60], 0.8: [-90, 0, -60], 1.0: N}},
        "rightArm": {"rotation": {0: HOLD, 0.1: [-90, 0, 60], 0.8: [-90, 0, 60], 1.0: HOLD}},
    })
    # 8 岩槍: 拳で地面を叩く
    A[8] = anim(1.6, {
        "root": {"position": {0: N, 0.3: [0, -4, 0], 0.9: [0, -4, 0], 1.2: N}},
        "body": {"rotation": {0: N, 0.15: [-15, 0, 0], 0.3: [45, 0, 0], 0.9: [45, 0, 0], 1.2: N}},
        "leftArm": {"rotation": {0: N, 0.15: UP, 0.3: [-40, 0, 0], 0.9: [-40, 0, 0], 1.2: N}},
        "rightLeg": {"rotation": {0: N, 0.3: [-60, 0, 0], 0.9: [-60, 0, 0], 1.2: N}},
        "leftLeg": {"rotation": {0: N, 0.3: [40, 0, 0], 0.9: [40, 0, 0], 1.2: N}},
    }, {0.3: fx("glow", "left_hand")})
    # 9・10・22 弾幕: 両手を広げて撃ち出す
    for v, length, times in ((9, 1.6, (0.3, 0.8, 1.2)), (10, 1.4, (0.3, 0.6, 0.9)),
                             (22, 3.0, tuple(round(0.3 + 0.3 * i, 2) for i in range(9)))):
        r, l = {0: HOLD}, {0: N}
        for i, t in enumerate(times):
            arm = l if i % 2 else r
            arm[t - 0.08] = [-110, 0, 0]
            arm[t] = [-80, 0, 0]
        r[length] = HOLD
        l[length] = N
        A[v] = anim(length, {"rightArm": {"rotation": r}, "leftArm": {"rotation": l}},
                    {t: fx("glow", "left_hand" if i % 2 else "right_hand") for i, t in enumerate(times)})
    # 11 神滅: 左手で銃を構え、3 発撃つ（反動）
    l = {0: N, 0.2: CAST}
    for t in (0.5, 1.0, 1.5):
        l.update({t - 0.02: CAST, t: [-115, 0, 0], t + 0.15: CAST})
    l[1.9] = N
    A[11] = anim(2.0, {"leftArm": {"rotation": l}, "body": {"rotation": {0: N, 0.2: [0, 30, 0], 1.8: [0, 30, 0], 2.0: N}},
                       "head": {"rotation": {0: N, 0.2: [0, -20, 0], 1.8: [0, -20, 0], 2.0: N}}},
                {t: fx("glow", "left_hand") for t in (0.5, 1.0, 1.5)})
    # 12 退勤届: 封筒を投げる
    A[12] = anim(1.0, {"leftArm": {"rotation": {0: N, 0.2: [-170, 0, 0], 0.35: [-40, 0, 0], 0.8: [-40, 0, 0], 1.0: N}},
                       "body": {"rotation": {0: N, 0.2: [-8, 20, 0], 0.35: [8, -15, 0], 1.0: N}}})
    # 13 フランスパン: 大きく振りかぶってポコッ
    A[13] = anim(0.9, {"leftArm": {"rotation": {0: N, 0.3: [-175, 0, 0], 0.45: [-50, 0, 0], 0.75: [-50, 0, 0], 0.9: N}},
                       "body": {"rotation": {0: N, 0.3: [-10, 0, 0], 0.45: [20, 0, 0], 0.9: N}}},
                {0.45: fx("bread", "left_hand")})
    # 14 リフバリアΩ: 両手を前にかざす
    A[14] = anim(1.0, {
        "rightArm": {"rotation": {0: HOLD, 0.2: [-100, 30, 0], 0.8: [-100, 30, 0], 1.0: HOLD}},
        "leftArm": {"rotation": {0: N, 0.2: [-100, -30, 0], 0.8: [-100, -30, 0], 1.0: N}},
    }, {0.2: fx("glow") + fx("glow", "left_hand")})
    # 15 次元斬: 居合で空間を斬る
    A[15] = dash_slashes([0.9], 1.8)
    # 16 宇宙CQC: 掴む → 叩きつける → 投げる
    A[16] = anim(1.5, {
        "leftArm": {"rotation": {0: N, 0.2: CAST, 0.6: [-150, 0, 0], 0.7: [-20, 0, 0], 0.95: [-160, 0, -20],
                                 1.05: [-60, 0, 0], 1.5: N}},
        "body": {"rotation": {0: N, 0.6: [-10, 0, 0], 0.7: [35, 0, 0], 0.95: [-10, 40, 0], 1.05: [10, -40, 0], 1.5: N}},
        "root": {"position": {0: N, 0.7: [0, -3, 0], 0.95: N}},
    }, {0.7: fx("spark", "left_hand"), 1.05: fx("spark", "left_hand")})
    # 17 宇宙猫: 首をかしげて猫の手
    A[17] = anim(1.5, {
        "head": {"rotation": {0: N, 0.2: [0, 0, 25], 1.2: [0, 0, -25], 1.5: N}},
        "rightArm": {"rotation": {0: HOLD, 0.2: [-130, 0, 20], 0.5: [-115, 0, 20], 0.8: [-130, 0, 20], 1.2: [-115, 0, 20],
                                  1.5: HOLD}},
        "leftArm": {"rotation": {0: N, 0.2: [-130, 0, -20], 0.5: [-115, 0, -20], 0.8: [-130, 0, -20], 1.2: [-115, 0, -20],
                                 1.5: N}},
    }, {0.3: fx("cat", "body_center")})
    # 18 目を合わせる: 片目を手で覆い、じっと見る
    A[18] = anim(2.2, {
        "leftArm": {"rotation": {0: N, 0.2: [-150, -30, 0], 1.4: [-150, -30, 0], 1.5: [-60, 0, 0], 2.2: N}},
        "head": {"rotation": {0: N, 0.2: [5, 0, 0], 2.2: N}},
    })
    # 19 ヴァルドガーラ: 両手を天に掲げ、黒い雷を落とす
    A[19] = anim(2.2, {
        "rightArm": {"rotation": {0: HOLD, 0.3: UP, 1.3: UP, 1.45: [-50, 0, 0], 2.2: HOLD}},
        "leftArm": {"rotation": {0: N, 0.3: UP, 1.3: UP, 1.45: [-50, 0, 0], 2.2: N}},
        "body": {"rotation": {0: N, 0.3: [-12, 0, 0], 1.3: [-12, 0, 0], 1.45: [20, 0, 0], 2.2: N}},
    }, {0.3: fx("electric") + fx("electric", "left_hand"), 0.8: fx("electric") + fx("electric", "left_hand")})
    # 21 抜刀隊: 刀を掲げ、周りに刀を呼ぶ
    A[21] = anim(1.4, {"rightArm": {"rotation": {0: HOLD, 0.25: UP, 0.9: UP, 1.05: CAST, 1.4: HOLD}},
                       "body": {"rotation": {0: N, 0.25: [-10, 0, 0], 1.05: [10, 0, 0], 1.4: N}}},
                {0.25: fx("glow")})
    # 23 魔力砲: 両手を突き出して溜め → 薙ぎ払う
    A[23] = anim(3.2, {
        "rightArm": {"rotation": {0: HOLD, 0.3: [-90, 15, 0], 3.0: [-90, 15, 0], 3.2: HOLD}},
        "leftArm": {"rotation": {0: N, 0.3: [-90, -15, 0], 3.0: [-90, -15, 0], 3.2: N}},
        "body": {"rotation": {0: N, 1.6: [0, 0, 0], 1.7: [-5, 0, 0], 3.0: [-5, 0, 0], 3.2: N}},
        "rightLeg": {"rotation": {0: N, 0.3: [-30, 0, 0], 3.0: [-30, 0, 0], 3.2: N}},
        "leftLeg": {"rotation": {0: N, 0.3: [25, 0, 0], 3.0: [25, 0, 0], 3.2: N}},
    }, {**{0.4 + i * 0.3: fx("glow") + fx("glow", "left_hand") for i in range(5)}})
    # 24 entropy: 手のひらを握りつぶす
    A[24] = anim(1.0, {"leftArm": {"rotation": {0: N, 0.2: [-110, 0, 0], 0.6: [-110, 0, 0], 0.7: [-80, 0, 0], 1.0: N}}},
                 {0.2: fx("glow", "left_hand")})
    # 25 自動回復システム / 26 影分身: 指を鳴らす
    for v in (25, 26):
        A[v] = anim(1.2, {"leftArm": {"rotation": {0: N, 0.2: [-130, 0, -20], 0.35: [-120, 0, -20], 1.0: [-120, 0, -20],
                                                   1.2: N}}},
                    {0.35: fx("spark", "left_hand")})
    # 27 砲撃支援: 耳に手を当てて通信 → 指差しで指示
    A[27] = anim(3.0, {
        "leftArm": {"rotation": {0: N, 0.2: [-150, 0, -40], 0.9: [-150, 0, -40], 1.0: [-100, 0, 0], 2.6: [-100, 0, 0],
                                 3.0: N}},
        "head": {"rotation": {0: N, 0.2: [0, 0, 15], 0.9: [0, 0, 15], 1.0: N}},
    })
    # 28 次元斬・紅: 溜めの長い居合
    A[28] = dash_slashes([1.6], 2.4)
    # 29 天道・大審判: 刀を天に掲げ続ける
    A[29] = anim(3.0, {"rightArm": {"rotation": {0: HOLD, 0.3: UP, 2.7: UP, 3.0: HOLD}},
                       "leftArm": {"rotation": {0: N, 0.3: [-90, 0, -30], 2.7: [-90, 0, -30], 3.0: N}},
                       "head": {"rotation": {0: N, 0.3: [-30, 0, 0], 2.7: [-30, 0, 0], 3.0: N}}},
                {0.3 + 0.5 * i: fx("glow") for i in range(5)})
    # 30 登場: 空から舞い降りる（つま先から着地）
    A[30] = anim(4.6, {
        "root": {"position": {0: [0, 64, 0], 2.2: [0, 8, 0], 2.6: N, 4.6: N}},
        "rightLeg": {"rotation": {0: [10, 0, 0], 2.2: [10, 0, 0], 2.6: [-20, 0, 0], 2.9: N}},
        "leftLeg": {"rotation": {0: [25, 0, 0], 2.2: [25, 0, 0], 2.6: [10, 0, 0], 2.9: N}},
        "rightArm": {"rotation": {0: [-20, 0, 30], 2.4: [-20, 0, 30], 3.6: HOLD, 3.9: [-95, -80, 0], 4.3: HOLD}},
        "leftArm": {"rotation": {0: [-20, 0, -30], 2.4: [-20, 0, -30], 3.2: N, 3.4: [-140, 0, -20], 3.7: N}},
        "head": {"rotation": {0: [20, 0, 0], 2.6: [20, 0, 0], 3.0: N, 3.3: [0, 0, 12], 3.8: N}},
    }, {0.0: fx("sparkle", "body_center"), 1.0: fx("sparkle", "body_center"), 2.6: fx("spark", "right_foot"),
        3.9: fx("trail")})
    # 31 適応: 一瞬止まり、目が光り、魔法陣を広げる
    A[31] = anim(4.6, {
        "head": {"rotation": {0: N, 0.3: [15, 0, 0], 1.6: [15, 0, 0], 1.8: [-10, 0, 0], 4.6: N}},
        "rightArm": {"rotation": {0: HOLD, 1.8: [-150, 0, 40], 3.6: [-150, 0, 40], 4.0: HOLD}},
        "leftArm": {"rotation": {0: N, 1.8: [-150, 0, -40], 3.6: [-150, 0, -40], 4.0: N}},
        "root": {"position": {0: N, 1.8: [0, 6, 0], 3.6: [0, 6, 0], 4.0: N}},
    }, {1.8: fx("electric", "body_center") + fx("glow") + fx("glow", "left_hand"), 2.6: fx("electric", "body_center")})
    # 32 内なる宇宙: 手を掲げて宇宙を広げる → 指を鳴らす
    A[32] = anim(11.0, {
        "leftArm": {"rotation": {0: N, 0.5: [-160, 0, -20], 4.0: [-160, 0, -20], 4.3: CAST, 9.6: CAST, 9.8: [-120, 0, -20],
                                 10.5: N}},
        "rightArm": {"rotation": {0: HOLD, 0.5: [-40, 0, 40], 9.6: [-40, 0, 40], 10.5: HOLD}},
        "root": {"position": {0: N, 1.0: [0, 6, 0], 9.6: [0, 6, 0], 10.2: N}},
        "head": {"rotation": {0: N, 0.5: [-15, 0, 0], 4.0: [-15, 0, 0], 4.3: N}},
    }, {0.5: fx("glow", "left_hand"), 9.8: fx("spark", "left_hand")})
    # 33 再臨: 崩れ落ちる → 光の柱の中で立ち上がる
    A[33] = anim(6.0, {
        "root": {"position": {0: N, 0.3: [0, -6, 0], 2.8: [0, -6, 0], 3.4: [0, 4, 0], 4.5: [0, 4, 0], 4.8: N}},
        "rightLeg": {"rotation": {0: N, 0.3: [-85, 10, 0], 2.8: [-85, 10, 0], 3.4: N}},
        "leftLeg": {"rotation": {0: N, 0.3: [70, -5, 0], 2.8: [70, -5, 0], 3.4: N}},
        "body": {"rotation": {0: N, 0.3: [40, 0, 0], 2.8: [40, 0, 0], 3.4: [-10, 0, 0], 4.8: N}},
        "head": {"rotation": {0: N, 0.3: [40, 0, 10], 2.8: [40, 0, 10], 3.4: [-25, 0, 0], 4.8: N}},
        "rightArm": {"rotation": {0: HOLD, 0.3: [5, 0, 10], 2.8: [5, 0, 10], 3.4: [-150, 0, 40], 4.5: [-150, 0, 40],
                                  4.8: HOLD}},
        "leftArm": {"rotation": {0: N, 0.3: [5, 0, -10], 2.8: [5, 0, -10], 3.4: [-150, 0, -40], 4.5: [-150, 0, -40],
                                 4.8: N}},
    }, {3.4: fx("sparkle", "body_center") + fx("flame", "right_foot") + fx("flame", "left_foot")})
    # 40 一閃神速: 一閃 × 5
    A[40] = dash_slashes([0.9, 1.25, 1.6, 1.95, 2.3], 2.8)
    # 41 クロノスピア: 指先で時計の針を止める → 槍を放つ
    A[41] = anim(3.2, {
        "leftArm": {"rotation": {0: N, 0.3: [-120, 0, -10], 1.9: [-120, 0, -10], 2.1: [-60, 0, 0], 3.2: N}},
        "rightArm": {"rotation": {0: HOLD, 1.9: HOLD, 2.1: UP, 2.3: CAST, 3.2: HOLD}},
    }, {0.3: fx("glow", "left_hand"), 2.2: fx("trail")})
    # 34 おすわり: 地面におでこをぶつける（土下座）
    A[34] = anim(3.0, {
        "root": {"position": {0: N, 0.2: [0, -8, 0], 2.7: [0, -8, 0], 3.0: N}},
        "rightLeg": {"rotation": {0: N, 0.2: [-90, 0, 0], 2.7: [-90, 0, 0], 3.0: N}},
        "leftLeg": {"rotation": {0: N, 0.2: [-90, 0, 0], 2.7: [-90, 0, 0], 3.0: N}},
        "body": {"rotation": {0: N, 0.2: [80, 0, 0], 2.7: [80, 0, 0], 3.0: N}},
        "head": {"rotation": {0: N, 0.2: [10, 0, 0], 2.7: [10, 0, 0], 3.0: N}},
        "rightArm": {"rotation": {0: HOLD, 0.2: [-100, 15, 0], 2.7: [-100, 15, 0], 3.0: HOLD}},
        "leftArm": {"rotation": {0: N, 0.2: [-100, -15, 0], 2.7: [-100, -15, 0], 3.0: N}},
    }, {0.2: fx("spark", "body_center")})
    # 60 間合いを取る（後ろへ跳んで遠距離で反撃）/ 61・62 右・左へ回り込んで斬る（立ち回り）
    A[60] = anim(1.1, footwork_bones("back", HOLD), {0.17: fx("step", "left_foot"), 0.17 + 0.01: fx("step", "right_foot"),
                                                  0.5: fx("glow")})
    A[61] = anim(1.3, footwork_bones("right", HOLD), {0.1: fx("step", "right_foot"), 0.26: fx("step", "right_foot"),
                                                   0.42: fx("step", "right_foot"), 0.56: fx("trail")})
    A[62] = anim(1.3, footwork_bones("left", HOLD), {0.1: fx("step", "left_foot"), 0.26: fx("step", "left_foot"),
                                                  0.42: fx("step", "left_foot"), 0.56: fx("trail")})
    return A


def all_animations():
    walk = "q.modified_distance_moved * 38.17"
    spd = SPD   # 走り出し・止まり際をなめらかにした移動速度
    anims = {
        "animation.sophia.look_at": {"loop": True, "bones": {
            "head": {"rotation": ["q.target_x_rotation", "q.target_y_rotation", 0]}}},
        # 待機: 呼吸・重心移動・刀をゆらす
        "animation.sophia.idle": {"loop": True, "bones": {
            "root": {"position": [0, "math.sin(q.life_time * 100) * 0.3", 0]},
            "body": {"rotation": ["math.sin(q.life_time * 100) * 1.2", "math.sin(q.life_time * 40) * 3", 0]},
            "head": {"rotation": [0, 0, "math.sin(q.life_time * 45) * 4"]},
            "rightArm": {"rotation": ["-20 + math.sin(q.life_time * 100) * 2", "-8 + math.sin(q.life_time * 55) * 6",
                                     "math.sin(q.life_time * 70) * 3"]},
            "leftArm": {"rotation": ["math.sin(q.life_time * 100) * -2.5", 0, "-5 - math.sin(q.life_time * 100) * 2"]},
            "leftLeg": {"rotation": [0, -6, -2]},
        }},
        # 走る: 前傾・腕の振り・上下の弾み
        "animation.sophia.move": {"loop": True, "bones": {
            "root": {"position": [0, "math.abs(math.cos(%s)) * 1.3 * %s" % (walk, spd), 0]},
            "body": {"rotation": ["12 * %s" % spd, "math.cos(%s) * 8 * %s" % (walk, spd), 0]},
            "head": {"rotation": ["-9 * %s" % spd, 0, 0]},
            "rightArm": {"rotation": ["math.cos(%s + 180) * 35 * %s - 12 * %s" % (walk, spd, spd), 0, 0]},
            "leftArm": {"rotation": ["math.cos(%s) * 60 * %s" % (walk, spd), 0, "-8 * %s" % spd]},
            "rightLeg": {"rotation": ["math.cos(%s) * 70 * %s" % (walk, spd), 0, 0]},
            "leftLeg": {"rotation": ["math.cos(%s + 180) * 70 * %s" % (walk, spd), 0, 0]},
        }},
        # 内なる宇宙のあと: 宙に浮いて移動する（足は後ろに流れる）
        "animation.sophia.float": {"loop": True, "bones": {
            "root": {"position": [0, "3 + math.sin(q.life_time * 120) * 1.2", 0]},
            "body": {"rotation": ["20 * %s" % spd, 0, 0]},
            "head": {"rotation": ["-15 * %s" % spd, 0, 0]},
            "rightLeg": {"rotation": ["15 + 30 * %s + math.sin(q.life_time * 120) * 5" % spd, 0, 3]},
            "leftLeg": {"rotation": ["10 + 30 * %s + math.sin(q.life_time * 120 + 60) * 5" % spd, 0, -3]},
            "leftArm": {"rotation": ["15 * %s" % spd, 0, "-12"]},
        }},
        # 待機中、時々刀をくるっと回して、首をかしげる（11 秒ごと）
        "animation.sophia.idle_flavor": anim(11.0, {
            "rightArm": {"rotation": {0: N, 7.5: N, 7.65: [-60, -40, 0], 7.8: [-95, 30, 0], 7.95: [-60, 85, 0],
                                      8.1: [-30, 30, 0], 8.3: N, 11.0: N}},
            "body": {"rotation": {0: N, 7.5: N, 7.8: [0, 12, 0], 8.1: [0, -8, 0], 8.3: N, 11.0: N}},
            "head": {"rotation": {0: N, 9.3: N, 9.6: [0, 0, 16], 10.4: [0, 0, 16], 10.7: N, 11.0: N}},
        }, {7.65: fx("arc"), 7.95: fx("spark")}, loop=True),
        "animation.sophia.step_fx": {"loop": True, "animation_length": 0.5, "particle_effects": {
            "0.00": [{"effect": "step", "locator": "right_foot"}], "0.25": [{"effect": "step", "locator": "left_foot"}]}},
        # 技を使いながら移動するとき: 足だけ動かす
        "animation.sophia.move_legs": {"loop": True, "bones": {
            "rightLeg": {"rotation": ["math.cos(%s) * 55 * %s" % (walk, spd), 0, 0]},
            "leftLeg": {"rotation": ["math.cos(%s + 180) * 55 * %s" % (walk, spd), 0, 0]},
        }},
        # 被弾: のけぞる
        "animation.sophia.hurt": {"loop": True, "bones": {
            "body": {"rotation": ["-v.flinch * 14", 0, 0]},
            "head": {"rotation": ["-v.flinch * 10", 0, 0]},
        }},
        # 通常攻撃: 刀・左拳・回し蹴りが順番に出る
        "animation.sophia.attack": {"loop": True, "bones": {
            "rightArm": {"rotation": ["math.mod(v.atk_n, 3) == 0 ? "
                                      "-math.sin(variable.attack_time * 180) * 120 : 0",
                                      "math.mod(v.atk_n, 3) == 0 ? "
                                      "math.sin(variable.attack_time * 360) * 60 : 0", 0]},
            "leftArm": {"rotation": ["math.mod(v.atk_n, 3) == 1 ? "
                                     "-math.sin(variable.attack_time * 180) * 95 : 0", 0, 0]},
            "rightLeg": {"rotation": ["math.mod(v.atk_n, 3) == 2 ? "
                                      "-math.sin(variable.attack_time * 180) * 100 : 0", 0, 0]},
            "body": {"rotation": [0, "math.sin(variable.attack_time * 180) * -25", 0]},
        }},
        # 適応から: 体に電気、左目（ラプラスの目）が青く光る
        "animation.sophia.aura_1": {"loop": True, "animation_length": 0.4, "particle_effects": {
            "0.00": [{"effect": "electric_aura", "locator": "body_center"}, {"effect": "eye", "locator": "eye"}]}},
        "animation.sophia.aura_2": {"loop": True, "animation_length": 0.4, "particle_effects": {
            "0.00": [{"effect": "electric_aura", "locator": "body_center"}, {"effect": "sparkle", "locator": "body_center"},
                     {"effect": "eye", "locator": "eye"}]}},
        "animation.sophia.aura_3": {"loop": True, "animation_length": 0.4, "particle_effects": {
            "0.00": [{"effect": "flame", "locator": "right_foot"}, {"effect": "flame", "locator": "left_foot"}],
            "0.20": [{"effect": "flame", "locator": "body_center"}, {"effect": "sparkle", "locator": "body_center"},
                     {"effect": "eye", "locator": "eye"}]}},
        "animation.sophia.death": anim(1.0, {
            "body": {"rotation": {0: N, 0.4: [30, 0, 0]}}, "head": {"rotation": {0: N, 0.4: [30, 0, 0]}}}),
    }
    for v, a in skill_anims().items():
        anims["animation.sophia.skill_%d" % v] = a
    # 分身・撃破カットシーンの像
    anims["animation.sophia.director_pose"] = anim(5.6, {
        "root": {"position": {0: [0, -10, 0]},
                 "scale": {0: 0, 1.05: 0, 1.1: 1, 4.6: 1, 5.4: [0.3, 1.3, 0.3]}},
        "rightLeg": {"rotation": {0: [-90, 15, 0]}}, "leftLeg": {"rotation": {0: [-90, -15, 0]}},
        "body": {"rotation": {0: [10, 0, 0]}}, "head": {"rotation": {0: [10, 0, 12], 3.0: [10, 0, -12], 4.6: [10, 0, 12]}},
        "rightArm": {"rotation": {0: [-50, 30, 0]}}, "leftArm": {"rotation": {0: [-50, -30, 0]}}})
    anims["animation.sophia.turn"] = TURN_ANIM
    anims["animation.sophia.alive"] = ALIVE_ANIM
    return {"format_version": "1.10.0", "animations": anims}


NO_LOOK = {2, 7, 30, 33, 32, 34}


def short_names(skill_ids):
    names = {"look_at": "animation.sophia.look_at", "idle": "animation.sophia.idle", "move": "animation.sophia.move",
             "attack": "animation.sophia.attack", "aura_1": "animation.sophia.aura_1",
             "float": "animation.sophia.float", "move_legs": "animation.sophia.move_legs",
             "idle_flavor": "animation.sophia.idle_flavor", "step_fx": "animation.sophia.step_fx",
             "hurt": "animation.sophia.hurt",
             "aura_2": "animation.sophia.aura_2", "aura_3": "animation.sophia.aura_3",
             "death_pose": "animation.sophia.death", "main": "controller.animation.sophia.main",
             "aura_ctrl": "controller.animation.sophia.aura", "attack_fx": "controller.animation.sophia.attack_fx"}
    names.update({"turn": "animation.sophia.turn", "alive": "animation.sophia.alive"})
    for v in skill_ids:
        names["s%d" % v] = "animation.sophia.skill_%d" % v
    return names


def controllers(skill_ids):
    dead = {"death": "!q.is_alive"}
    states = {"default": {"animations": ["look_at", "idle", {"move": "q.skin_id < 2"}, {"float": "q.skin_id >= 2"},
                                         {"attack": "variable.attack_time > 0"}, "hurt",
                                         {"idle_flavor": "q.modified_move_speed < 0.3"},
                                         {"step_fx": "q.modified_move_speed > 0.4 && q.skin_id < 2"}],
                          "transitions": [dead] + [{"s%d" % v: "q.mark_variant == %d" % v} for v in skill_ids],
                          "blend_transition": 0.1},
              "death": {"animations": ["death_pose"]}}
    for v in skill_ids:
        states["s%d" % v] = {"animations": (["s%d" % v] if v in NO_LOOK else ["look_at", "s%d" % v])
                             + [{"move_legs": "q.modified_move_speed > 0.1"}, "hurt"],
                             "transitions": [dead, {"default": "q.mark_variant != %d" % v}], "blend_transition": 0.08}
    return smooth_controller({"format_version": "1.10.0", "animation_controllers": {
        "controller.animation.sophia.main": {"initial_state": "default", "states": states},
        "controller.animation.sophia.aura": {"initial_state": "none", "states": {
            "none": {"transitions": [{"a3": "q.skin_id >= 3"}, {"a2": "q.skin_id == 2"}, {"a1": "q.skin_id == 1"}]},
            "a1": {"animations": ["aura_1"], "transitions": [{"a2": "q.skin_id >= 2"}, {"none": "!q.is_alive"}]},
            "a2": {"animations": ["aura_2"], "transitions": [{"a3": "q.skin_id >= 3"}, {"none": "!q.is_alive"}]},
            "a3": {"animations": ["aura_3"], "transitions": [{"none": "!q.is_alive"}]}}},
        "controller.animation.sophia.attack_fx": {"initial_state": "ready", "states": {
            "ready": {"transitions": [{"swing_0": "variable.attack_time > 0.25 && math.mod(v.atk_n, 3) == 0"},
                                      {"swing_1": "variable.attack_time > 0.25 && math.mod(v.atk_n, 3) == 1"},
                                      {"swing_2": "variable.attack_time > 0.25"}]},
            "swing_0": {"particle_effects": [{"effect": "trail", "locator": "right_hand"},
                                             {"effect": "arc", "locator": "reach"}],
                        "transitions": [{"ready": "variable.attack_time < 0.2"}]},
            "swing_1": {"particle_effects": [{"effect": "trail", "locator": "left_hand"},
                                             {"effect": "arc", "locator": "left_hand"}],
                        "transitions": [{"ready": "variable.attack_time < 0.2"}]},
            "swing_2": {"particle_effects": [{"effect": "spark", "locator": "right_foot"},
                                             {"effect": "arc", "locator": "right_foot"}],
                        "transitions": [{"ready": "variable.attack_time < 0.2"}]}}},
    }}, "controller.animation.sophia.main")


PARTICLE_MAP = {"arc": "sophia:arc", "step": "sophia:step_dust",
                "trail": "sophia:spark_burst", "spark": "sophia:spark_burst", "glow": "sophia:hand_glow",
                "electric": "sophia:electric", "electric_aura": "sophia:aura_electric", "sparkle": "sophia:sparkle",
                "flame": "sophia:aura_flame", "bread": "sophia:bread", "cat": "sophia:cat", "eye": "sophia:laplace_eye"}
