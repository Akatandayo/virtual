# -*- coding: utf-8 -*-
"""電子 独: クライアント側アニメーション."""

N = [0, 0, 0]
TPOSE_R, TPOSE_L = [0, 0, 90], [0, 0, -90]   # バグったゲームの象徴「T ポーズ」
GL = "math.mod(math.floor(q.life_time * %s), %d) == 0"


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


def hold(pose, t0, t1, before=N, after=N, start=0.0, end=None):
    d = {start: before, t0: pose, t1: pose}
    if end is not None:
        d[end] = after
    return d


def stutter(t0, t1, poses, step=0.12):
    """カクカクしたコマ落ち（キーを同じ値で 2 回置いて段差を作る）"""
    d, t, i = {}, t0, 0
    while t < t1:
        d[round(t, 2)] = poses[i % len(poses)]
        d[round(t + step - 0.01, 2)] = poses[i % len(poses)]
        t += step
        i += 1
    return d


def skill_anims():
    A = {}
    # 1 ラグスパイク: カクカク瞬間移動 → 背後から突き
    A[1] = anim(1.2, {
        "root": {"position": stutter(0, 0.8, [[2, 0, 0], [-2, 1, 1], [0, -1, -2], [1, 0, 2]], 0.1)
                 | {0.81: N, 1.2: N}},
        "rightArm": {"rotation": {0: N, 0.8: [-30, 0, 0], 0.9: [-95, 0, 0], 1.1: [-95, 0, 0], 1.2: N}},
        "body": {"rotation": {0: N, 0.9: [10, -20, 0], 1.2: N}},
    }, {0.9: fx("hand_noise")})
    # 2 Remake: こめかみに指を当て、腕を逆回し
    A[2] = anim(2.2, {
        "rightArm": {"rotation": {0: N, 0.2: [-150, -30, 20], 1.3: [-150, -30, 20], 1.4: [-90, 0, 0], 1.6: [-200, 0, 0],
                                  1.8: [-90, 0, 0], 2.2: N}},
        "head": {"rotation": {0: N, 0.2: [0, 0, 15], 1.3: [0, 0, 15], 1.4: N}},
    }, {0.2: fx("hand_noise"), 1.4: fx("hand_noise")})
    # 3 テクスチャ欠損: T ポーズで固まる
    A[3] = anim(2.2, {
        "rightArm": {"rotation": hold(TPOSE_R, 0.1, 2.0, end=2.2)},
        "leftArm": {"rotation": hold(TPOSE_L, 0.1, 2.0, end=2.2)},
        "head": {"rotation": {0: N, 0.1: N, 2.2: N}},
        "root": {"position": {0: N, 0.1: [0, 2, 0], 2.0: [0, 2, 0], 2.2: N}},
    })
    # 4 座標破損 NaN: 首が 90°折れ曲がる
    A[4] = anim(2.2, {
        "head": {"rotation": {0: N, 0.15: [0, 0, 90], 1.0: [0, 180, 90], 2.0: [0, 180, 90], 2.2: N}},
        "rightArm": {"rotation": {0: N, 0.15: [-170, 0, 0], 2.0: [-170, 0, 0], 2.2: N}},
        "leftArm": {"rotation": {0: N, 0.15: [-170, 0, 0], 1.9: [-170, 0, 0], 2.0: [-20, 0, 0], 2.2: N}},
    }, {0.15: fx("hand_noise") + fx("hand_noise", "left_hand")})
    # 5 フレーム落ち: コマ送りの連撃
    A[5] = anim(2.0, {
        "rightArm": {"rotation": stutter(0.2, 1.9, [[-95, 30, 0], [-100, -40, 0], [-160, 0, 0], [-40, 0, 0]], 0.25)
                     | {0: N, 2.0: N}},
        "leftArm": {"rotation": stutter(0.2, 1.9, [[-30, 0, 0], [-95, 30, 0], [-60, 0, 0], [-100, -30, 0]], 0.25)
                    | {0: N, 2.0: N}},
        "body": {"rotation": stutter(0.2, 1.9, [[0, 25, 0], [0, -25, 0], [10, 0, 0], [0, 0, 0]], 0.25) | {2.0: N}},
    })
    # 6 ☂Mebius☂: 腕を前に伸ばし、ゆっくり回る
    A[6] = anim(2.2, {
        "root": {"rotation": {0: N, 1.8: [0, 360, 0], 2.2: [0, 360, 0]}},
        "rightArm": {"rotation": hold([-90, 20, 0], 0.15, 1.8, end=2.2)},
        "leftArm": {"rotation": hold([-90, -20, 0], 0.15, 1.6, after=[-150, 0, 0], end=1.8) | {2.2: N}},
    }, {0.2: fx("hand_noise"), 1.8: fx("hand_noise", "left_hand")})
    # 7 ✮Northern Lights✮: 天を仰ぎ、両腕を広げる
    A[7] = anim(2.6, {
        "rightArm": {"rotation": hold([-160, 0, 40], 0.3, 2.3, end=2.6)},
        "leftArm": {"rotation": hold([-160, 0, -40], 0.3, 2.3, end=2.6)},
        "head": {"rotation": hold([-35, 0, 0], 0.3, 2.3, end=2.6)},
        "body": {"rotation": hold([-12, 0, 0], 0.3, 2.3, end=2.6)},
    }, {0.3: fx("hand_noise") + fx("hand_noise", "left_hand")})
    # 8 番狂わせ: 指を鳴らす
    A[8] = anim(1.2, {
        "rightArm": {"rotation": {0: N, 0.2: [-120, 0, 30], 0.35: [-110, 0, 30], 0.5: [-120, 0, 30], 1.0: [-120, 0, 30],
                                  1.2: N}},
    }, {0.35: fx("hand_noise")})
    # 9 目を隠す: 両手で目を覆う
    A[9] = anim(2.2, {
        "rightArm": {"rotation": hold([-150, 30, 0], 0.15, 1.8, end=2.0) | {2.2: N}},
        "leftArm": {"rotation": hold([-150, -30, 0], 0.15, 1.8, end=2.0) | {2.2: N}},
        "head": {"rotation": hold([20, 0, 0], 0.15, 1.8, end=2.0) | {2.2: N}},
    })
    # 10 俯瞰: 腕を組み、真下を見下ろす
    A[10] = anim(2.8, {
        "rightArm": {"rotation": hold([-70, -40, 0], 0.2, 2.6, end=2.8)},
        "leftArm": {"rotation": hold([-70, 40, 0], 0.2, 2.6, end=2.8)},
        "head": {"rotation": hold([45, 0, 0], 0.2, 2.6, end=2.8)},
    })
    # 11 データ弾: 指先を向けて連射（反動）
    r = {0: N, 0.2: [-90, 0, 0]}
    for i in range(6):
        t = 0.35 + i * 0.18
        r[t] = [-105, 0, 0]
        r[t + 0.08] = [-90, 0, 0]
    r[1.6] = N
    A[11] = anim(1.6, {"rightArm": {"rotation": r}}, {0.35 + i * 0.18: fx("hand_noise") for i in range(6)})
    # 12 フォークボム: しゃがみ込み、腕を下に広げる
    A[12] = anim(1.4, {
        "root": {"position": hold([0, -3, 0], 0.2, 1.1, end=1.4)},
        "rightArm": {"rotation": hold([-20, 0, 45], 0.2, 1.1, end=1.4)},
        "leftArm": {"rotation": hold([-20, 0, -45], 0.2, 1.1, end=1.4)},
        "rightLeg": {"rotation": hold([-30, 0, 0], 0.2, 1.1, end=1.4)},
        "leftLeg": {"rotation": hold([30, 0, 0], 0.2, 1.1, end=1.4)},
    }, {0.8: fx("hand_noise") + fx("hand_noise", "left_hand")})
    # 13 DESTRUCTION 3,2,1: 指揮者のように数え、最後に振り下ろす
    A[13] = anim(4.0, {
        "rightArm": {"rotation": {0: N, 0.5: [-170, 0, 0], 0.8: [-120, 0, 0], 1.5: [-170, 0, 0], 1.8: [-120, 0, 0],
                                  2.5: [-170, 0, 0], 3.3: [-180, 0, 0], 3.5: [-30, 0, 0], 3.9: [-30, 0, 0], 4.0: N}},
        "leftArm": {"rotation": {0: N, 3.3: [-180, 0, 0], 3.5: [-30, 0, 0], 3.9: [-30, 0, 0], 4.0: N}},
        "body": {"rotation": {0: N, 3.3: [-10, 0, 0], 3.5: [25, 0, 0], 3.9: [25, 0, 0], 4.0: N}},
    }, {0.5: fx("hand_noise"), 1.5: fx("hand_noise"), 2.5: fx("hand_noise"), 3.5: fx("hand_noise")})
    # 14 ↓FREEDOM DiVE↓: 鍵盤を叩くように両腕を交互に振り下ろす → 急降下
    r, l = {0: N}, {0: N}
    for i in range(8):
        t = 0.6 + i * 0.35
        (r if i % 2 == 0 else l)[t] = [-60, 0, 0]
        (r if i % 2 == 0 else l)[t + 0.12] = [-100, 0, 0]
    r.update({3.6: [-100, 0, 0], 3.8: [40, 0, 0], 4.6: [40, 0, 0], 5.0: N})
    l.update({3.6: [-100, 0, 0], 3.8: [40, 0, 0], 4.6: [40, 0, 0], 5.0: N})
    A[14] = anim(5.0, {"rightArm": {"rotation": r}, "leftArm": {"rotation": l},
                       "body": {"rotation": {0: N, 3.6: N, 3.8: [40, 0, 0], 4.6: [40, 0, 0], 5.0: N}}},
                {0.6 + i * 0.35: fx("hand_noise" if True else "", "right_hand" if i % 2 == 0 else "left_hand")
                 for i in range(8)})
    # 20 🤍Re: End of a Dream💙: 宙に浮き、T ポーズのまま回転
    A[20] = anim(8.0, {
        "root": {"position": {0: N, 1.0: [0, 10, 0], 7.0: [0, 10, 0], 7.4: N, 8.0: N},
                 "rotation": {0: N, 1.0: N, 7.0: [0, 360, 0], 8.0: [0, 360, 0]}},
        "rightArm": {"rotation": hold(TPOSE_R, 1.0, 7.0, end=7.4) | {8.0: N}},
        "leftArm": {"rotation": hold(TPOSE_L, 1.0, 7.0, end=7.4) | {8.0: N}},
        "head": {"rotation": hold([-30, 0, 0], 1.0, 7.0, end=7.4) | {8.0: N}},
    }, {t: fx("glitch_heavy", "body_center") for t in (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)})
    # 99 強制解除（スタン）: 膝から崩れ落ちる
    A[99] = anim(5.0, {
        "root": {"position": {0: N, 0.3: [0, -6, 0], 4.6: [0, -6, 0], 5.0: N}},
        "rightLeg": {"rotation": hold([-85, 10, 0], 0.3, 4.6, end=5.0)},
        "leftLeg": {"rotation": hold([70, -5, 0], 0.3, 4.6, end=5.0)},
        "body": {"rotation": hold([35, 0, 0], 0.3, 4.6, end=5.0)},
        "head": {"rotation": hold([40, 0, 15], 0.3, 4.6, end=5.0)},
        "rightArm": {"rotation": hold([5, 0, 10], 0.3, 4.6, end=5.0)},
        "leftArm": {"rotation": hold([5, 0, -10], 0.3, 4.6, end=5.0)},
    }, {0.3 + i * 0.6: fx("stun_spark", "body_center") for i in range(7)})
    return A


def all_animations():
    walk = "q.modified_distance_moved * 38.17"
    spd = "math.min(q.modified_move_speed, 1.0)"
    anims = {
        "animation.hitori.look_at": {"loop": True, "bones": {
            "head": {"rotation": ["q.target_x_rotation", "q.target_y_rotation", 0]}}},
        "animation.hitori.idle": {"loop": True, "bones": {
            "body": {"rotation": ["math.sin(q.life_time * 90) * 1.5", 0, 0]},
            "rightArm": {"rotation": ["math.sin(q.life_time * 90) * 3", 0, "3"]},
            "leftArm": {"rotation": ["math.sin(q.life_time * 90) * -3", 0, "-3"]},
        }},
        "animation.hitori.move": {"loop": True, "bones": {
            "rightArm": {"rotation": ["math.cos(%s + 180) * 45 * %s" % (walk, spd), 0, 0]},
            "leftArm": {"rotation": ["math.cos(%s) * 45 * %s" % (walk, spd), 0, 0]},
            "rightLeg": {"rotation": ["math.cos(%s) * 60 * %s" % (walk, spd), 0, 0]},
            "leftLeg": {"rotation": ["math.cos(%s + 180) * 60 * %s" % (walk, spd), 0, 0]},
        }},
        # 時々ブレる・首がカクッと傾く（グリッチ）
        "animation.hitori.glitch": {"loop": True, "bones": {
            "root": {"position": ["(%s) ? math.random(-1.5, 1.5) : 0" % (GL % ("7", 5)), 0,
                                  "(%s) ? math.random(-1.5, 1.5) : 0" % (GL % ("7", 5))]},
            "head": {"rotation": [0, "(%s) ? math.random(-40, 40) : 0" % (GL % ("5", 7)),
                                  "(%s) ? math.random(-30, 30) : 0" % (GL % ("5", 7))]},
            "rightArm": {"rotation": ["(%s) ? math.random(-90, 0) : 0" % (GL % ("6", 9)), 0, 0]},
        }},
        "animation.hitori.attack": {"loop": True, "bones": {
            "rightArm": {"rotation": ["-math.sin(variable.attack_time * 180) * 100", 0, 0]},
            "body": {"rotation": [0, "math.sin(variable.attack_time * 180) * -20", 0]},
        }},
        "animation.hitori.aura": {"loop": True, "animation_length": 0.3,
                                  "particle_effects": {"0.00": [{"effect": "glitch", "locator": "body_center"}]}},
        "animation.hitori.aura_heavy": {"loop": True, "animation_length": 0.3,
                                        "particle_effects": {"0.00": [{"effect": "glitch_heavy", "locator": "body_center"}]}},
        "animation.hitori.death": anim(1.0, {
            "rightArm": {"rotation": {0: N, 0.2: TPOSE_R, 1.0: TPOSE_R}},
            "leftArm": {"rotation": {0: N, 0.2: TPOSE_L, 1.0: TPOSE_L}},
        }),
    }
    for v, a in skill_anims().items():
        anims["animation.hitori.skill_%d" % v] = a
    return {"format_version": "1.10.0", "animations": anims}


NO_LOOK = {4, 6, 20, 99}


def short_names(skill_ids):
    names = {
        "look_at": "animation.hitori.look_at", "idle": "animation.hitori.idle", "move": "animation.hitori.move",
        "glitch": "animation.hitori.glitch", "attack": "animation.hitori.attack", "aura": "animation.hitori.aura",
        "aura_heavy": "animation.hitori.aura_heavy", "death_pose": "animation.hitori.death",
        "main": "controller.animation.hitori.main", "aura_ctrl": "controller.animation.hitori.aura",
        "attack_fx": "controller.animation.hitori.attack_fx",
    }
    for v in skill_ids:
        names["s%d" % v] = "animation.hitori.skill_%d" % v
    return names


def controllers(skill_ids):
    dead = {"death": "!q.is_alive"}
    states = {
        "default": {"animations": ["look_at", "idle", "move", "glitch", {"attack": "variable.attack_time > 0"}],
                    "transitions": [dead] + [{"s%d" % v: "q.mark_variant == %d" % v} for v in skill_ids],
                    "blend_transition": 0.1},
        "death": {"animations": ["death_pose"]},
    }
    for v in skill_ids:
        a = ["s%d" % v] if v in NO_LOOK else ["look_at", "s%d" % v]
        if v not in (99,):
            a.append("glitch")
        states["s%d" % v] = {"animations": a, "transitions": [dead, {"default": "q.mark_variant != %d" % v}],
                             "blend_transition": 0.08}
    return {"format_version": "1.10.0", "animation_controllers": {
        "controller.animation.hitori.main": {"initial_state": "default", "states": states},
        "controller.animation.hitori.aura": {"initial_state": "light", "states": {
            "light": {"animations": ["aura"], "transitions": [{"off": "q.mark_variant == 99 || !q.is_alive"},
                                                               {"heavy": "q.skin_id >= 1"}]},
            "heavy": {"animations": ["aura_heavy"], "transitions": [{"off": "q.mark_variant == 99 || !q.is_alive"}]},
            "off": {"transitions": [{"light": "q.mark_variant != 99 && q.is_alive && q.skin_id == 0"},
                                    {"heavy": "q.mark_variant != 99 && q.is_alive && q.skin_id >= 1"}]},
        }},
        "controller.animation.hitori.attack_fx": {"initial_state": "ready", "states": {
            "ready": {"transitions": [{"swing": "variable.attack_time > 0.25"}]},
            "swing": {"particle_effects": [{"effect": "hand", "locator": "right_hand"}],
                      "transitions": [{"ready": "variable.attack_time < 0.2"}]},
        }},
    }}


PARTICLE_MAP = {"hand_noise": "hitori:hand_noise", "hand": "hitori:noise_burst", "glitch": "hitori:glitch_aura",
                "glitch_heavy": "hitori:glitch_aura_heavy", "stun_spark": "hitori:stun_spark"}
