# -*- coding: utf-8 -*-
"""東雲 永々: クライアント側アニメーション（右手に黒胎刀、背中にクロノスピアの窓）."""

N = [0, 0, 0]
HOLD = [-15, -6, 0]
UP = [-175, 0, 0]
CAST = [-90, 0, 0]
SEAL_R, SEAL_L = [-95, 25, 0], [-95, -25, 0]   # 分身の印


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


def slashes(times, length, extra=None):
    r, b = {0: HOLD}, {0: N}
    for i, t in enumerate(times):
        r[t - 0.1] = [-100, 75, 0] if i % 2 == 0 else [-95, -80, 0]
        r[t] = [-95, -85, 0] if i % 2 == 0 else [-100, 80, 0]
        b[t] = [10, -35, 0] if i % 2 == 0 else [10, 35, 0]
    end = max(times) + 0.3
    r[end], b[end] = HOLD, N
    bones = {"rightArm": {"rotation": r}, "body": {"rotation": b}}
    if extra:
        bones.update(extra)
    return anim(length, bones, {t: fx("trail") for t in times})


def throws(times, length, arm="leftArm"):
    a = {0: N}
    for t in times:
        a.update({t - 0.2: [-170, 0, 0], t: [-45, 0, 0]})
    a[max(times) + 0.3] = N
    return anim(length, {arm: {"rotation": a}}, {t: fx("hand", "left_hand") for t in times})


def skill_anims():
    A = {}
    seal = anim(1.4, {"rightArm": {"rotation": {0: HOLD, 0.15: SEAL_R, 1.1: SEAL_R, 1.4: HOLD}},
                      "leftArm": {"rotation": {0: N, 0.15: SEAL_L, 1.1: SEAL_L, 1.4: N}},
                      "head": {"rotation": {0: N, 0.15: [10, 0, 0], 1.1: [10, 0, 0], 1.4: N}}},
                {0.3: fx("hand"), 0.6: fx("hand")})
    for v in (1, 51, 52, 53, 54, 55):
        A[v] = seal
    A[2] = slashes([0.75, 1.45, 2.15], 2.6)
    A[3] = anim(1.6, {"rightArm": {"rotation": {0: HOLD, 0.2: [-90, 80, 0], 0.4: [-90, -80, 0], 0.6: [-150, 0, 0],
                                                0.8: [-90, 80, 0], 1.0: [-40, 0, 0], 1.6: HOLD}}},
                {0.2: fx("trail"), 0.6: fx("trail"), 1.0: fx("trail")})
    A[4] = anim(2.6, {"rightArm": {"rotation": {0: HOLD, 0.2: [-70, 0, 30], 2.2: [-70, 0, 30], 2.6: HOLD}},
                      "leftArm": {"rotation": {0: N, 0.2: [-70, 0, -30], 2.2: [-70, 0, -30], 2.6: N}},
                      "root": {"position": {0: N, 0.2: [0, -2, 0], 2.2: [0, -2, 0], 2.6: N}}},
                {0.2: fx("hand") + fx("hand", "left_hand")})
    A[5] = anim(2.6, {"rightArm": {"rotation": {0: HOLD, 0.2: [-160, 0, 30], 2.2: [-160, 0, 30], 2.6: HOLD}},
                      "leftArm": {"rotation": {0: N, 0.2: [-160, 0, -30], 2.2: [-160, 0, -30], 2.6: N}},
                      "root": {"position": {0: N, 0.3: [0, 4, 0], 2.2: [0, 4, 0], 2.6: N}}})
    A[6] = anim(2.0, {"rightArm": {"rotation": {0: HOLD, 0.2: CAST, 0.5: [-60, 30, 0], 0.8: CAST, 1.1: [-60, 30, 0],
                                                1.6: [-110, 0, 0], 2.0: HOLD}},
                      "leftArm": {"rotation": {0: N, 0.2: CAST, 0.5: [-60, -30, 0], 0.8: CAST, 1.1: [-60, -30, 0],
                                               1.6: [-110, 0, 0], 2.0: N}}}, {1.6: fx("hand") + fx("hand", "left_hand")})
    A[7] = throws([0.4, 0.75, 1.1], 1.5)
    A[8] = throws([0.45], 1.2)
    A[9] = anim(2.4, {"rightArm": {"rotation": {0: HOLD, 0.3: UP, 1.4: UP, 1.6: [-60, 0, 0], 2.4: HOLD}},
                      "leftArm": {"rotation": {0: N, 0.3: UP, 1.4: UP, 1.6: [-60, 0, 0], 2.4: N}},
                      "body": {"rotation": {0: N, 0.3: [-10, 0, 0], 1.4: [-10, 0, 0], 1.6: [20, 0, 0], 2.4: N}}})
    A[10] = anim(1.6, {"leftArm": {"rotation": {0: N, 0.2: CAST, 1.3: CAST, 1.6: N}},
                       "body": {"rotation": {0: N, 0.2: [0, 20, 0], 1.3: [0, 20, 0], 1.6: N}}},
                 {0.5: fx("hand", "left_hand"), 0.9: fx("hand", "left_hand")})
    A[11] = slashes([1.0, 1.4, 1.8], 2.2, {"leftArm": {"rotation": {0: N, 0.2: CAST, 0.4: [-40, 0, 0], 0.9: N}}})
    A[12] = anim(1.6, {"root": {"rotation": {0: N, 0.6: [0, 360, 0], 1.6: [0, 360, 0]}},
                       "rightArm": {"rotation": {0: HOLD, 0.6: [-90, 30, 0], 0.7: [-90, -10, 0], 1.6: HOLD}},
                       "leftArm": {"rotation": {0: N, 0.6: [-90, -30, 0], 0.7: [-90, 10, 0], 1.6: N}}}, {0.7: fx("hand")})
    # 13 おやつタイム: 座ってハンバーガーをもぐもぐ
    eat = {0: N, 0.3: [-130, -30, 0]}
    for i in range(6):
        eat[0.5 + i * 0.4] = [-150, -30, 0]
        eat[0.7 + i * 0.4] = [-125, -30, 0]
    eat[3.0] = N
    A[13] = anim(3.0, {"root": {"position": {0: N, 0.3: [0, -10, 0], 2.8: [0, -10, 0], 3.0: N}},
                       "rightLeg": {"rotation": {0: N, 0.3: [-90, 10, 0], 2.8: [-90, 10, 0], 3.0: N}},
                       "leftLeg": {"rotation": {0: N, 0.3: [-90, -10, 0], 2.8: [-90, -10, 0], 3.0: N}},
                       "leftArm": {"rotation": eat},
                       "head": {"rotation": {0: N, 0.5: [10, 0, 8], 1.5: [10, 0, -8], 2.5: [10, 0, 8], 3.0: N}}},
                 {0.5 + i * 0.4: fx("burger", "left_hand") for i in range(6)})
    A[14] = slashes([0.3, 0.6, 0.9, 1.2], 1.6)
    A[15] = anim(2.6, {"root": {"rotation": {0: N, 2.4: [0, 270, 0], 2.6: [0, 270, 0]}},
                       "rightArm": {"rotation": {0: HOLD, 0.2: [-90, 0, 70], 2.4: [-90, 0, 70], 2.6: HOLD}},
                       "leftArm": {"rotation": {0: N, 0.2: [-90, 0, -70], 2.4: [-90, 0, -70], 2.6: N}}})
    A[16] = anim(1.6, {"rightArm": {"rotation": {0: HOLD, 0.3: UP, 1.0: UP, 1.15: [-60, -40, 0], 1.6: HOLD}},
                       "body": {"rotation": {0: N, 0.3: [-12, 0, 0], 1.0: [-12, 0, 0], 1.15: [20, -30, 0], 1.6: N}}},
                 {0.3: fx("fire"), 0.6: fx("fire"), 0.9: fx("fire"), 1.15: fx("fire")})
    A[17] = anim(3.2, {"leftArm": {"rotation": {0: N, 0.3: UP, 2.6: UP, 2.8: [-60, 0, 0], 3.2: N}},
                       "head": {"rotation": {0: N, 0.3: [-30, 0, 0], 2.6: [-30, 0, 0], 3.2: N}}})
    A[18] = anim(2.4, {"rightArm": {"rotation": {0: HOLD, 0.2: [-40, 0, 60], 2.2: [-40, 0, 60], 2.4: HOLD}},
                       "leftArm": {"rotation": {0: N, 0.2: [-40, 0, -60], 2.2: [-40, 0, -60], 2.4: N}},
                       "window": {"scale": {0: 1, 0.3: 1.15, 0.6: 1, 0.9: 1.15, 1.2: 1, 1.5: 1.15, 1.8: 1}}},
                 {0.5: fx("cyan", "window_center"), 1.0: fx("cyan", "window_center"), 1.5: fx("cyan", "window_center")})
    A[19] = slashes([0.4, 0.9, 1.4, 1.9], 2.4)
    # 20 混沌の体: ぷるぷる揺れる水の体
    A[20] = anim(6.0, {"root": {"scale": ["1 + math.sin(q.anim_time * 720) * 0.06", "1 - math.sin(q.anim_time * 720) * 0.06",
                                          "1 + math.sin(q.anim_time * 720) * 0.06"]}}, loop=True)
    pts = {0: N}
    for i in range(8):
        t = 0.6 + i * 0.4
        pts.update({t - 0.15: [-120, 0, 0], t: [-80, 0, 0]})
    pts[4.0] = N
    A[21] = anim(4.2, {"leftArm": {"rotation": pts}, "rightArm": {"rotation": {0: HOLD, 0.3: [-60, 0, 30], 4.0: [-60, 0, 30],
                                                                                 4.2: HOLD}}})
    A[22] = anim(4.6, {"rightArm": {"rotation": {0: HOLD, 0.3: [-165, -20, 0], 4.2: [-165, -20, 0], 4.6: HOLD}},
                       "leftArm": {"rotation": {0: N, 0.3: [-165, 20, 0], 4.2: [-165, 20, 0], 4.6: N}},
                       "head": {"rotation": {0: N, 0.3: [-20, 0, 0], 4.2: [-20, 0, 0], 4.6: N}}})
    # 23 ねこぉ: 小さくなって四つ足で駆ける
    A[23] = anim(5.0, {"root": {"scale": {0: 1, 0.3: 0.55, 4.7: 0.55, 5.0: 1},
                                "rotation": {0: N, 0.3: [60, 0, 0], 4.7: [60, 0, 0], 5.0: N},
                                "position": {0: N, 0.3: [0, 0, -6], 4.7: [0, 0, -6], 5.0: N}},
                       "rightArm": {"rotation": {0: HOLD, 0.3: [-60, 0, 0], 4.7: [-60, 0, 0], 5.0: HOLD}},
                       "leftArm": {"rotation": {0: N, 0.3: [-60, 0, 0], 4.7: [-60, 0, 0], 5.0: N}},
                       "head": {"rotation": {0: N, 0.3: [-55, 0, 0], 4.7: [-55, 0, 0], 5.0: N}}},
                 {0.3: fx("smoke", "body_center"), 4.7: fx("smoke", "body_center")})
    # 24 狂化: 激しく揺れながら乱れ斬り
    r, b = {0: HOLD}, {0: N}
    for i in range(30):
        t = 0.2 + i * 0.25
        r[t] = [-100, 80, 0] if i % 2 == 0 else [-100, -80, 0]
        b[t] = [15, 30, 3] if i % 2 == 0 else [15, -30, -3]
    r[8.0], b[8.0] = HOLD, N
    A[24] = anim(8.0, {"rightArm": {"rotation": r}, "body": {"rotation": b}},
                 {0.2 + i * 0.5: fx("trail") + fx("rage", "body_center") for i in range(16)})
    # 25 気絶: へたり込み、目を回す
    A[25] = anim(4.0, {"root": {"position": {0: N, 0.3: [0, -10, 0], 3.7: [0, -10, 0], 4.0: N}},
                       "rightLeg": {"rotation": {0: N, 0.3: [-90, 20, 0], 3.7: [-90, 20, 0], 4.0: N}},
                       "leftLeg": {"rotation": {0: N, 0.3: [-90, -20, 0], 3.7: [-90, -20, 0], 4.0: N}},
                       "rightArm": {"rotation": {0: HOLD, 0.3: [10, 0, 20], 3.7: [10, 0, 20], 4.0: HOLD}},
                       "leftArm": {"rotation": {0: N, 0.3: [10, 0, -20], 3.7: [10, 0, -20], 4.0: N}},
                       "head": {"rotation": ["math.sin(q.anim_time * 360) * 15", 0, "math.cos(q.anim_time * 360) * 15"]}},
                 {0.3 + i * 0.7: fx("spark", "head_top") for i in range(5)})
    # 30 登場: 空のワープホールから落ちてきて、くるっと着地
    A[30] = anim(4.6, {"root": {"position": {0: [0, 128, 0], 1.6: [0, 128, 0], 2.3: N, 4.6: N},
                                "rotation": {0: N, 1.6: N, 2.3: [0, 720, 0], 4.6: [0, 720, 0]}},
                       "rightLeg": {"rotation": {2.3: N, 2.35: [-30, 0, 0], 2.6: N}},
                       "rightArm": {"rotation": {0: [-150, 0, 30], 2.3: [-150, 0, 30], 2.6: HOLD, 3.2: HOLD,
                                                 3.4: [-160, 0, 30], 3.6: [-160, 0, 10], 3.8: [-160, 0, 30], 4.1: HOLD}},
                       "leftArm": {"rotation": {0: [-150, 0, -30], 2.3: [-150, 0, -30], 2.6: N}},
                       "head": {"rotation": {3.2: N, 3.4: [0, 0, 15], 4.1: [0, 0, 15], 4.4: N}}},
                 {2.3: fx("smoke", "body_center")})
    # 31 シニスターの憑依: うずくまる → 立ち上がって腕を広げる。背中の窓が現れる
    A[31] = anim(5.0, {"root": {"position": {0: N, 0.3: [0, -5, 0], 2.0: [0, -5, 0], 2.4: [0, 3, 0], 4.6: [0, 3, 0], 5.0: N}},
                       "body": {"rotation": {0: N, 0.3: [40, 0, 0], 2.0: [40, 0, 0], 2.4: [-15, 0, 0], 4.6: N}},
                       "rightArm": {"rotation": {0: HOLD, 0.3: [10, 0, 20], 2.0: [10, 0, 20], 2.4: [-150, 0, 45],
                                                 4.4: [-150, 0, 45], 4.8: HOLD}},
                       "leftArm": {"rotation": {0: N, 0.3: [10, 0, -20], 2.0: [10, 0, -20], 2.4: [-150, 0, -45], 4.4: [-150, 0, -45],
                                                4.8: N}},
                       "window": {"scale": {0: 0, 1.2: 0, 2.4: 1.2, 2.7: 1.0}}},
                 {1.2: fx("dark", "body_center"), 2.4: fx("cyan", "window_center") + fx("dark", "body_center")})
    # 32 全時間停止: 指を鳴らす → 止まった世界を歩く → もう一度鳴らす
    A[32] = anim(6.6, {"leftArm": {"rotation": {0: N, 0.3: [-120, 0, -20], 0.45: [-110, 0, -20], 1.0: N, 4.6: N,
                                                4.9: [-120, 0, -20], 5.05: [-110, 0, -20], 5.6: N}},
                       "rightArm": {"rotation": {0: HOLD, 1.2: [-40, 0, 0], 1.5: [20, 0, 0], 1.8: [-40, 0, 0], 2.1: [20, 0, 0],
                                                 2.4: HOLD}},
                       "head": {"rotation": {0: N, 0.45: [0, 0, 12], 1.0: N}}},
                 {0.45: fx("hand", "left_hand"), 5.05: fx("hand", "left_hand")})
    return A


def all_animations():
    walk = "q.modified_distance_moved * 38.17"
    spd = "math.min(q.modified_move_speed, 1.0)"
    anims = {
        "animation.toa.look_at": {"loop": True, "bones": {
            "head": {"rotation": ["q.target_x_rotation", "q.target_y_rotation", 0]}}},
        "animation.toa.idle": {"loop": True, "bones": {
            "body": {"rotation": [0, 0, "math.sin(q.life_time * 90) * 2"]},
            "head": {"rotation": [0, 0, "math.sin(q.life_time * 60) * 6"]},
            "rightArm": {"rotation": ["-15 + math.sin(q.life_time * 90) * 4", "-6", 0]},
            "leftArm": {"rotation": ["math.sin(q.life_time * 90 + 90) * 6", 0, "-6"]},
        }},
        # スキップするように歩く
        "animation.toa.move": {"loop": True, "bones": {
            "root": {"position": [0, "math.abs(math.sin(%s * 0.5)) * 1.5 * %s" % (walk, spd), 0]},
            "rightArm": {"rotation": ["math.cos(%s + 180) * 40 * %s" % (walk, spd), 0, 0]},
            "leftArm": {"rotation": ["math.cos(%s) * 55 * %s" % (walk, spd), 0, 0]},
            "rightLeg": {"rotation": ["math.cos(%s) * 60 * %s" % (walk, spd), 0, 0]},
            "leftLeg": {"rotation": ["math.cos(%s + 180) * 60 * %s" % (walk, spd), 0, 0]},
        }},
        "animation.toa.attack": {"loop": True, "bones": {
            "rightArm": {"rotation": ["-math.sin(variable.attack_time * 180) * 120", "60 - variable.attack_time * 120", 0]},
            "body": {"rotation": [0, "math.sin(variable.attack_time * 180) * -25", 0]},
        }},
        # 背中の窓（クロノスピア）はふわふわ浮く
        "animation.toa.window": {"loop": True, "bones": {
            "window": {"position": [0, "math.sin(q.life_time * 80) * 1.2", 0],
                       "rotation": [0, 0, "math.sin(q.life_time * 50) * 3"]}}},
        # 本物の印: 左目が金色に光る（分身には無い）
        "animation.toa.gold_eye": {"loop": True, "animation_length": 0.4,
                                   "particle_effects": {"0.00": [{"effect": "gold_eye", "locator": "eye"}]}},
        "animation.toa.aura_1": {"loop": True, "animation_length": 0.4,
                                 "particle_effects": {"0.00": [{"effect": "dark", "locator": "right_foot"}],
                                                      "0.20": [{"effect": "dark", "locator": "left_foot"}]}},
        "animation.toa.aura_2": {"loop": True, "animation_length": 0.4,
                                 "particle_effects": {"0.00": [{"effect": "dark", "locator": "right_foot"},
                                                               {"effect": "rage", "locator": "left_foot"}],
                                                      "0.20": [{"effect": "rage", "locator": "body_center"}]}},
        "animation.toa.water": {"loop": True, "animation_length": 0.3,
                                "particle_effects": {"0.00": [{"effect": "water", "locator": "body_center"}]}},
        "animation.toa.death": anim(1.0, {"body": {"rotation": {0: N, 0.4: [20, 0, 0]}}}),
        "animation.toa.director_pose": anim(5.6, {
            "root": {"position": {0: [0, -10, 0]}, "scale": {0: 0, 1.05: 0, 1.1: 1, 4.4: 1, 4.9: 0}},
            "rightLeg": {"rotation": {0: [-90, 15, 0]}}, "leftLeg": {"rotation": {0: [-90, -15, 0]}},
            "leftArm": {"rotation": {0: [-130, -30, 0], 1.8: [-130, -30, 0], 2.0: [-150, -30, 0], 2.2: [-125, -30, 0],
                                     2.4: [-150, -30, 0], 2.6: [-125, -30, 0], 3.6: [-125, -30, 0], 3.8: N}},
            "rightArm": {"rotation": {0: N, 3.8: N, 4.0: [-160, 0, 30], 4.2: [-160, 0, 10], 4.4: [-160, 0, 30]}},
            "head": {"rotation": {0: [10, 0, 8], 2.0: [10, 0, -8], 3.6: [0, 0, 12]}}},
            {1.9: fx("burger", "left_hand"), 2.3: fx("burger", "left_hand")}),
    }
    for v, a in skill_anims().items():
        anims["animation.toa.skill_%d" % v] = a
    return {"format_version": "1.10.0", "animations": anims}


NO_LOOK = {12, 13, 15, 23, 24, 25, 30, 31}


def short_names(skill_ids):
    n = {"look_at": "animation.toa.look_at", "idle": "animation.toa.idle", "move": "animation.toa.move",
         "attack": "animation.toa.attack", "window": "animation.toa.window", "gold_eye": "animation.toa.gold_eye",
         "aura_1": "animation.toa.aura_1", "aura_2": "animation.toa.aura_2", "water": "animation.toa.water",
         "death_pose": "animation.toa.death", "main": "controller.animation.toa.main",
         "aura_ctrl": "controller.animation.toa.aura", "attack_fx": "controller.animation.toa.attack_fx"}
    for v in skill_ids:
        n["s%d" % v] = "animation.toa.skill_%d" % v
    return n


def controllers(skill_ids):
    dead = {"death": "!q.is_alive"}
    states = {"default": {"animations": ["look_at", "idle", "move", {"attack": "variable.attack_time > 0"}],
                          "transitions": [dead] + [{"s%d" % v: "q.mark_variant == %d" % v} for v in skill_ids],
                          "blend_transition": 0.1},
              "death": {"animations": ["death_pose"]}}
    for v in skill_ids:
        a = ["s%d" % v] if v in NO_LOOK else ["look_at", "s%d" % v]
        if v == 20:
            a.append("water")
        states["s%d" % v] = {"animations": a, "transitions": [dead, {"default": "q.mark_variant != %d" % v}],
                             "blend_transition": 0.08}
    return {"format_version": "1.10.0", "animation_controllers": {
        "controller.animation.toa.main": {"initial_state": "default", "states": states},
        "controller.animation.toa.aura": {"initial_state": "none", "states": {
            "none": {"transitions": [{"a2": "q.skin_id >= 2"}, {"a1": "q.skin_id == 1"}]},
            "a1": {"animations": ["aura_1"], "transitions": [{"a2": "q.skin_id >= 2"}, {"none": "!q.is_alive"}]},
            "a2": {"animations": ["aura_2"], "transitions": [{"none": "!q.is_alive"}]}}},
        "controller.animation.toa.attack_fx": {"initial_state": "ready", "states": {
            "ready": {"transitions": [{"swing": "variable.attack_time > 0.25"}]},
            "swing": {"particle_effects": [{"effect": "trail", "locator": "right_hand"}],
                      "transitions": [{"ready": "variable.attack_time < 0.2"}]}}},
    }}


PARTICLE_MAP = {"trail": "shinonome:trail", "hand": "shinonome:hand", "spark": "shinonome:spark",
                "smoke": "shinonome:smoke", "fire": "shinonome:fire_burst", "cyan": "shinonome:charge_cyan",
                "dark": "shinonome:dark_aura", "rage": "shinonome:rage", "water": "shinonome:water_aura",
                "gold_eye": "shinonome:gold_eye", "burger": "shinonome:burger"}
