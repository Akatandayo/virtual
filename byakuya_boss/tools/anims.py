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

    # 20 最終演技: 膝をつく → 立ち上がり宙に浮く → 渾身の一太刀
    hover = {0: N, 1.8: [0, -6, 0], 2.4: N}
    for i in range(7):
        hover[3.0 + i * 0.5] = [0, 8 + (i % 2), 0]
    hover.update({6.3: [0, 9, 0], 6.45: [0, -2, 0], 7.5: [0, -2, 0]})
    A[20] = anim(7.5, merge(kneel(0.2, 1.8), {
        "root": {"position": hover},
        "rightLeg": {"rotation": {0: N, 2.4: N, 6.45: [-40, 0, 0], 7.5: [-40, 0, 0]}},
        "leftLeg": {"rotation": {0: N, 2.4: N, 6.45: [35, 0, 0], 7.5: [35, 0, 0]}},
        "body": {"rotation": {0: N, 0.2: [30, 0, 0], 1.8: [30, 0, 0], 2.4: [-10, 0, 0], 6.3: [-15, 0, 0],
                              6.45: [45, 0, 0], 7.5: [40, 0, 0]}},
        "rightArm": {"rotation": {0: HOLD_R, 0.2: [-15, 0, 0], 1.8: [-15, 0, 0], 3.0: [-180, 0, 0],
                                  6.3: [-185, 0, 0], 6.45: [-25, 0, 0], 7.5: [-25, 0, 0]}},
        "leftArm": {"rotation": {0: N, 0.2: [-20, 0, 0], 1.8: [-20, 0, 0], 3.0: [-170, 0, 0],
                                 6.3: [-175, 0, 0], 6.45: [-25, 0, 0], 7.5: [-25, 0, 0]}},
    }), {**{3.0 + i * 0.4: fx("hand_charge") + fx("aura_soul", "body_center") for i in range(9)},
         6.45: fx("sword_trail_red") + fx("sword_trail_red", "body_center")})
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


NO_LOOK = {3, 11, 20}  # 回転する技・最終演技は頭を固定しない


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
    "sword_trail": "byakuya:sword_trail", "sword_trail_red": "byakuya:sword_trail_red",
    "hand_charge": "byakuya:hand_charge", "aura_flame": "byakuya:aura_flame",
    "aura_soul": "byakuya:aura_soul", "blade_halo": "byakuya:blade_halo",
}
