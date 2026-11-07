# -*- coding: utf-8 -*-
"""電子 独: ノイズ系パーティクルとテクスチャ."""
import math

from PIL import Image, ImageDraw

TEX = "textures/particle/"
FADE = "1 - v.particle_age / v.particle_lifetime"
UV = {"texture_width": 1, "texture_height": 1, "uv": [0, 0], "uv_size": [1, 1]}

# RGB / CMY のどれかをランダムに（v.particle_random_1 で選ぶ）
RGB_R = "v.particle_random_1 < 0.33 ? 1.0 : (v.particle_random_1 < 0.66 ? 0.0 : 1.0)"
RGB_G = "v.particle_random_1 < 0.33 ? 0.0 : (v.particle_random_1 < 0.66 ? 1.0 : 1.0)"
RGB_B = "v.particle_random_1 < 0.33 ? 1.0 : (v.particle_random_1 < 0.66 ? 1.0 : 1.0)"
# 時々白く点滅
FLICKER = "math.random(0, 1) > 0.15 ? 1.0 : 0.2"


# ---------------------------------------------------------------------------
# テクスチャ
# ---------------------------------------------------------------------------
def _fn_img(w, h, fn):
    im = Image.new("RGBA", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = fn((x + 0.5) / w, (y + 0.5) / h)
    return im


def _c(v):
    return max(0, min(255, int(v)))


def t_glow(u, v):
    d = math.hypot(u - 0.5, v - 0.5) * 2
    return (255, 255, 255, _c(max(0.0, 1 - d) ** 2 * 255))


def t_ring_rgb(u, v):
    def ring(du):
        d = math.hypot(u - 0.5 + du, v - 0.5) * 2
        return math.exp(-((d - 0.82) / 0.06) ** 2)
    r, g, b = ring(0.025), ring(0.0), ring(-0.025)
    a = max(r, g, b)
    return (_c(r * 255), _c(g * 255), _c(b * 255), _c(a * 255))


def t_frame(u, v):
    e = max(abs(u - 0.5), abs(v - 0.5)) * 2
    if e > 0.95 or (0.8 < e < 0.9):
        return (255, 255, 255, 255)
    if e < 0.8 and int(u * 16) % 4 == 0 and int(v * 16) % 4 == 0:
        return (255, 255, 255, 120)
    return (0, 0, 0, 0)


def t_missing(u, v):
    on = (int(u * 2) + int(v * 2)) % 2 == 0
    return (248, 0, 248, 255) if on else (0, 0, 0, 255)


def t_beam(u, v):
    x = abs(u - 0.5) * 2
    a = max(0.0, 1 - x) ** 1.5
    a *= 0.6 + 0.4 * (int(v * 32) % 2)  # 走査線
    return (255, 255, 255, _c(a * 255))


def t_aurora(u, v):
    x = abs(u - 0.5) * 2
    a = max(0.0, 1 - x) * (v ** 1.5) * (0.7 + 0.3 * math.sin(u * 40))
    return (255, 255, 255, _c(a * 255))


def t_note(u, v):
    x, y = abs(u - 0.5) * 2, abs(v - 0.5) * 2
    if x > 0.95 or y > 0.9:
        return (0, 0, 0, 0)
    if x > 0.82 or y > 0.6:
        return (120, 240, 255, 255)
    return (255, 255, 255, 255)


def error_window():
    im = Image.new("RGBA", (32, 24))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 31, 23], fill=(60, 60, 70, 255))
    d.rectangle([1, 1, 30, 22], fill=(224, 224, 228, 255))
    d.rectangle([1, 1, 30, 6], fill=(16, 96, 216, 255))
    d.rectangle([25, 2, 29, 5], fill=(220, 40, 40, 255))
    d.line([26, 3, 28, 4], fill=(255, 255, 255, 255))
    d.ellipse([4, 9, 12, 17], fill=(220, 30, 30, 255))
    d.line([6, 11, 10, 15], fill=(255, 255, 255, 255))
    d.line([10, 11, 6, 15], fill=(255, 255, 255, 255))
    d.line([15, 11, 27, 11], fill=(90, 90, 100, 255))
    d.line([15, 14, 24, 14], fill=(90, 90, 100, 255))
    d.rectangle([20, 17, 28, 20], fill=(190, 190, 196, 255), outline=(90, 90, 100, 255))
    return im


DIGITS = {
    "1": ["01100", "11100", "01100", "01100", "01100", "01100", "11110"],
    "2": ["11110", "00011", "00011", "01110", "11000", "11000", "11111"],
    "3": ["11110", "00011", "00011", "01110", "00011", "00011", "11110"],
}


def digit(ch):
    s = 4
    im = Image.new("RGBA", (6 * s + 4, 8 * s + 4))
    rows = DIGITS[ch]
    for color, ox in (((255, 30, 60, 255), 0), ((0, 230, 255, 255), 4), ((255, 255, 255, 255), 2)):
        for y, row in enumerate(rows):
            for x, bit in enumerate(row):
                if bit == "1":
                    for dy in range(s):
                        for dx in range(s):
                            im.putpixel((x * s + dx + ox, y * s + dy + 2), color)
    return im


def arrow_down():
    """RGB がずれた「↓」"""
    im = Image.new("RGBA", (16, 16))
    shape = set()
    for y in range(1, 9):
        for x in range(6, 10):
            shape.add((x, y))
    for i, y in enumerate(range(8, 15)):
        for x in range(1 + i, 15 - i):
            shape.add((x, y))
    for color, ox in (((0, 230, 255, 255), -1), ((255, 30, 200, 255), 1), ((255, 255, 255, 255), 0)):
        for (x, y) in shape:
            if 0 <= x + ox < 16:
                im.putpixel((x + ox, y), color)
    return im


def disc_icon():
    """レコード「隔絶された記憶」のアイコン"""
    im = Image.new("RGBA", (16, 16))
    for y in range(16):
        for x in range(16):
            d = math.hypot(x - 7.5, y - 7.5)
            if d > 7.3:
                continue
            if d < 0.9:
                continue  # 中心の穴
            if d < 3.0:
                im.putpixel((x, y), (40, 220, 255, 255) if x < 8 else (240, 40, 200, 255))
            elif int(d * 1.6) % 2 == 0:
                im.putpixel((x, y), (36, 36, 48, 255))
            else:
                im.putpixel((x, y), (18, 18, 26, 255))
    # ノイズの走り
    for x in range(3, 13):
        if im.getpixel((x, 5))[3]:
            im.putpixel((x, 5), (255, 255, 255, 255) if x % 3 else (40, 220, 255, 255))
    return im


def build_textures():
    return {
        "hitori_pixel": Image.new("RGBA", (4, 4), (255, 255, 255, 255)),
        "hitori_glow": _fn_img(64, 64, t_glow),
        "hitori_ring_rgb": _fn_img(128, 128, t_ring_rgb),
        "hitori_frame": _fn_img(32, 32, t_frame),
        "hitori_missing": _fn_img(16, 16, t_missing),
        "hitori_beam": _fn_img(16, 64, t_beam),
        "hitori_aurora": _fn_img(16, 64, t_aurora),
        "hitori_note": _fn_img(32, 8, t_note),
        "hitori_error": error_window(),
        "hitori_num1": digit("1"), "hitori_num2": digit("2"), "hitori_num3": digit("3"),
        "hitori_arrow": arrow_down(),
    }


# ---------------------------------------------------------------------------
# パーティクル
# ---------------------------------------------------------------------------
def particle(ident, tex, material="particles_add", *, count=None, rate=None, active=0.1, shape=None,
             lifetime="0.5", speed=None, accel=(0, 0, 0), drag=0.0, size="0.2", facing="lookat_xyz",
             color=None, spin=None, parametric=None, local=False):
    c = {}
    if local:
        c["minecraft:emitter_local_space"] = {"position": True, "rotation": False}
    if count is not None:
        c["minecraft:emitter_rate_instant"] = {"num_particles": count}
    else:
        c["minecraft:emitter_rate_steady"] = {"spawn_rate": rate[0], "max_particles": rate[1]}
    c["minecraft:emitter_lifetime_once"] = {"active_time": active}
    c.update(shape or {"minecraft:emitter_shape_point": {"offset": [0, 0, 0]}})
    c["minecraft:particle_lifetime_expression"] = {"max_lifetime": lifetime}
    if speed is not None:
        c["minecraft:particle_initial_speed"] = speed
    if spin:
        c["minecraft:particle_initial_spin"] = spin
    if parametric:
        c["minecraft:particle_motion_parametric"] = {"relative_position": parametric}
    else:
        c["minecraft:particle_motion_dynamic"] = {"linear_acceleration": list(accel), "linear_drag_coefficient": drag}
    if isinstance(size, str):
        size = [size, size]
    c["minecraft:particle_appearance_billboard"] = {"size": size, "facing_camera_mode": facing, "uv": UV}
    if color is not None:
        c["minecraft:particle_appearance_tinting"] = {"color": color}
    return {"format_version": "1.10.0", "particle_effect": {
        "description": {"identifier": "hitori:" + ident,
                        "basic_render_parameters": {"material": material, "texture": TEX + tex}},
        "components": c}}


def sphere(r, direction="outwards", surface=True, offset=(0, 0, 0)):
    return {"minecraft:emitter_shape_sphere": {"radius": r, "surface_only": surface, "direction": direction,
                                               "offset": list(offset)}}


def disc(r, direction=(0, 1, 0), surface=False, offset=(0, 0, 0)):
    return {"minecraft:emitter_shape_disc": {"radius": r, "plane_normal": "y", "surface_only": surface,
                                             "direction": direction if isinstance(direction, str) else list(direction),
                                             "offset": list(offset)}}


def box(half, direction=(0, 1, 0), offset=(0, 0, 0)):
    return {"minecraft:emitter_shape_box": {"half_dimensions": list(half), "direction": list(direction),
                                            "offset": list(offset)}}


BAR = ["0.04 + v.particle_random_2 * 0.4", "0.03 + v.particle_random_3 * 0.07"]
RGB = [RGB_R, RGB_G, RGB_B, FLICKER]
TINTS = {"cyan": (0.2, 1.0, 1.0), "magenta": (1.0, 0.15, 0.9), "red": (1.0, 0.15, 0.2), "white": (1, 1, 1),
         "green": (0.3, 1.0, 0.5)}


def tint(name, alpha=FADE):
    r, g, b = TINTS[name]
    return [r, g, b, alpha]


def build_particles():
    P = {}
    # --- ノイズ ---
    P["noise_burst"] = particle("noise_burst", "hitori_pixel", count=40, shape=sphere(0.5),
                                lifetime="math.random(0.2, 0.5)", speed="math.random(2, 7)", drag=6, size=BAR, color=RGB)
    P["noise_big"] = particle("noise_big", "hitori_pixel", count=160, shape=sphere(1.0),
                              lifetime="math.random(0.4, 1.0)", speed="math.random(6, 18)", drag=3,
                              size=["0.1 + v.particle_random_2 * 0.8", "0.05 + v.particle_random_3 * 0.15"], color=RGB)
    P["glitch_aura"] = particle("glitch_aura", "hitori_pixel", rate=(40, 30), active=0.3,
                                shape=box((0.45, 1.0, 0.45), (0, 0, 0), (0, 1, 0)), lifetime="0.12", size=BAR, color=RGB)
    P["glitch_aura_heavy"] = particle("glitch_aura_heavy", "hitori_pixel", rate=(90, 60), active=0.3,
                                      shape=box((0.7, 1.2, 0.7), (0, 0, 0), (0, 1, 0)), lifetime="0.12",
                                      size=["0.1 + v.particle_random_2 * 0.7", "0.03 + v.particle_random_3 * 0.1"],
                                      color=RGB)
    P["afterimage"] = particle("afterimage", "hitori_pixel", "particles_blend", count=60,
                               shape=box((0.35, 0.95, 0.35), (1, 0, 0)), lifetime="math.random(0.3, 0.7)",
                               speed="math.random(-0.6, 0.6)",
                               size=["0.05 + v.particle_random_2 * 0.5", "0.06"],
                               color=["v.particle_random_1 > 0.5 ? 0.0 : 0.05", "v.particle_random_1 > 0.5 ? 0.9 : 0.0",
                                      "v.particle_random_1 > 0.5 ? 1.0 : 0.05", FADE])
    P["charge"] = particle("charge", "hitori_pixel", rate=(120, 150), active=0.8, shape=sphere(4.5, "inwards"),
                           lifetime="0.5", speed=8, size=BAR, color=RGB)
    P["destruction"] = particle("destruction", "hitori_pixel", count=400, shape=sphere(2.0),
                                lifetime="math.random(0.6, 1.4)", speed="math.random(10, 30)", drag=2,
                                size=["0.2 + v.particle_random_2 * 1.5", "0.1 + v.particle_random_3 * 0.3"], color=RGB)
    # --- 衝撃波・予兆 ---
    P["shockwave"] = particle("shockwave", "hitori_ring_rgb", count=1, lifetime="0.5", facing="emitter_transform_xz",
                              size="0.5 + v.particle_age / v.particle_lifetime * 7", color=[1, 1, 1, FADE])
    P["shockwave_big"] = particle("shockwave_big", "hitori_ring_rgb", count=1, lifetime="0.9",
                                  facing="emitter_transform_xz",
                                  size="1 + v.particle_age / v.particle_lifetime * 22", color=[1, 1, 1, FADE])
    P["safe_zone"] = particle("safe_zone", "hitori_ring_rgb", count=1, lifetime="1.0", facing="emitter_transform_xz",
                              size="9", color=[0.3, 1.0, 0.5, "0.5 + 0.5 * math.sin(v.particle_age * 720)"])
    for col in ("magenta", "cyan", "red"):
        P["warn_" + col] = particle("warn_" + col, "hitori_frame", count=1, lifetime="0.45",
                                    facing="emitter_transform_xz", size="2.4 - v.particle_age / v.particle_lifetime * 1.2",
                                    spin={"rotation": "45"},
                                    color=tint(col, "0.4 + 0.6 * math.abs(math.sin(v.particle_age * 900))"))
    # --- テクスチャ欠損 ---
    P["missing_tex"] = particle("missing_tex", "hitori_missing", "particles_alpha", count=1, lifetime="0.5",
                                size="1.0 + (math.random(0, 1) > 0.7 ? 0.4 : 0)",
                                spin={"rotation": "math.random(0, 1) > 0.5 ? 0 : 90"})
    P["missing_burst"] = particle("missing_burst", "hitori_missing", "particles_alpha", count=24, shape=sphere(0.4),
                                  lifetime="math.random(0.4, 0.8)", speed="math.random(3, 9)", accel=(0, -10, 0),
                                  drag=1, size="0.18", spin={"rotation": "math.random(0, 360)",
                                                             "rotation_rate": "math.random(-400, 400)"})
    # --- エラー画面 ---
    P["error_popup"] = particle("error_popup", "hitori_error", "particles_alpha", count=6, shape=sphere(1.6, (0, 1, 0)),
                                lifetime="math.random(0.8, 1.4)", speed=0.4,
                                size=["math.min(v.particle_age * 8, 1) * 0.8", "math.min(v.particle_age * 8, 1) * 0.6"])
    P["error_one"] = particle("error_one", "hitori_error", "particles_alpha", count=1, lifetime="0.9",
                              size=["math.min(v.particle_age * 8, 1) * 0.7", "math.min(v.particle_age * 8, 1) * 0.52"])
    # --- ビーム ---
    P["beam_column"] = particle("beam_column", "hitori_beam", count=2, shape=box((0.1, 0, 0.1), offset=(0, 8, 0)),
                                lifetime="0.45", facing="lookat_y", size=["1.2 * (" + FADE + ")", "16"],
                                color=["v.particle_random_1 > 0.5 ? 0.2 : 1.0", "v.particle_random_1 > 0.5 ? 1.0 : 0.2",
                                       "1.0", FLICKER])
    P["beam_warn"] = particle("beam_warn", "hitori_beam", count=1, shape=box((0, 0, 0), offset=(0, 8, 0)),
                              lifetime="0.3", facing="lookat_y", size=["0.12", "16"], color=tint("red", FLICKER))
    P["beam_dot"] = particle("beam_dot", "hitori_pixel", count=3, shape=sphere(0.25, surface=False), lifetime="0.25",
                             size=BAR, color=RGB)
    # 回転する3本のノイズビーム（Re: End of a Dream）: φ = 60°/秒
    arm = "(v.emitter_age * 60 + math.floor(v.particle_random_1 * 3) * 120)"
    P["dream_arms"] = particle(
        "dream_arms", "hitori_pixel", rate=(450, 900), active=6.5,
        shape={"minecraft:emitter_shape_custom": {"offset": [
            "-math.sin(%s) * (1 + v.particle_random_2 * 19)" % arm, "1",
            "math.cos(%s) * (1 + v.particle_random_2 * 19)" % arm]}},
        lifetime="0.18", size=["0.12 + v.particle_random_3 * 0.3", "0.08"],
        color=["v.particle_random_4 > 0.5 ? 0.3 : 1.0", "v.particle_random_4 > 0.5 ? 1.0 : 0.3", "1.0", FLICKER])
    # --- オーロラ（Northern Lights） ---
    P["aurora_ring"] = particle(
        "aurora_ring", "hitori_aurora", rate=(260, 500), active=1.4,
        shape={"minecraft:emitter_shape_custom": {"offset": [
            "math.cos(v.particle_random_1 * 360) * (2 + v.emitter_age * 13)", "0",
            "math.sin(v.particle_random_1 * 360) * (2 + v.emitter_age * 13)"]}},
        lifetime="0.6", speed=1.5, facing="lookat_y", size=["0.5", "3.5 * (" + FADE + ") + 0.5"],
        color=["v.particle_random_2 < 0.33 ? 0.2 : (v.particle_random_2 < 0.66 ? 0.3 : 0.7)",
               "v.particle_random_2 < 0.33 ? 1.0 : (v.particle_random_2 < 0.66 ? 0.8 : 0.3)",
               "v.particle_random_2 < 0.33 ? 0.5 : 1.0", FADE])
    P["aurora_sky"] = particle("aurora_sky", "hitori_aurora", rate=(40, 120), active=2.0,
                               shape=box((10, 0.5, 10), (0, 0, 0), (0, 8, 0)), lifetime="2.0", facing="lookat_y",
                               size=["1.5", "6"],
                               color=["v.particle_random_2 < 0.5 ? 0.2 : 0.6", "v.particle_random_2 < 0.5 ? 1.0 : 0.3",
                                      "0.8", "0.5 * math.sin(v.particle_age / v.particle_lifetime * 180)"])
    # --- 音ゲー（FREEDOM DiVE） ---
    P["note_fall"] = particle("note_fall", "hitori_note", "particles_alpha", count=1,
                              shape=box((0, 0, 0), (0, -1, 0), (0, 12, 0)), lifetime="0.6", speed=20, accel=(0, -0, 0),
                              size=["1.4", "0.35"])
    P["note_hit"] = particle("note_hit", "hitori_glow", count=20, shape=disc(0.5, "outwards"), lifetime="0.35",
                             speed="math.random(3, 7)", drag=4, size="0.25 * (" + FADE + ")", color=tint("cyan"))
    # --- カウントダウン ---
    for n in "123":
        P["num_" + n] = particle("num_" + n, "hitori_num" + n, "particles_alpha", count=1, lifetime="0.9",
                                 size=["2.4 * (1 + math.max(0, 0.3 - v.particle_age) * 3)",
                                       "3.0 * (1 + math.max(0, 0.3 - v.particle_age) * 3)"])
    # --- データ弾の軌跡 ---
    P["bit_trail"] = particle("bit_trail", "hitori_pixel", count=4, shape=sphere(0.25, surface=False), lifetime="0.3",
                              size=BAR, color=RGB)
    P["hand_noise"] = particle("hand_noise", "hitori_pixel", count=8, shape=sphere(0.4, surface=False), lifetime="0.2",
                               size=BAR, color=RGB)
    P["stun_spark"] = particle("stun_spark", "hitori_glow", count=10, shape=sphere(0.3), lifetime="0.4",
                               speed="math.random(1, 4)", accel=(0, -6, 0), size="0.1", color=tint("white"))
    # --- v1.3: 拳の軌跡（RGB のノイズが残る）・足跡のノイズ・着地の破片と土煙 ---
    P["arc"] = particle("arc", "hitori_pixel", rate=(220, 100), active=0.16, lifetime="0.2",
                        size=["0.05 + v.particle_random_2 * 0.2", "0.03 + v.particle_random_3 * 0.05"], color=RGB)
    P["step_dust"] = particle("step_dust", "hitori_pixel", count=4, shape=disc(0.2, "outwards"), lifetime="0.35",
                              speed=0.8, drag=3, size=BAR, color=[RGB_R, RGB_G, RGB_B, "0.8 * (" + FADE + ")"])
    P["debris"] = particle("debris", "hitori_pixel", "particles_alpha", count=22, shape=sphere(0.3, (0, 1, 0)),
                           lifetime="math.random(0.6, 1.0)", speed="math.random(3, 8)", accel=(0, -16, 0), drag=0.5,
                           size="0.05 + v.particle_random_1 * 0.08",
                           spin={"rotation": "math.random(0, 360)", "rotation_rate": "math.random(-500, 500)"},
                           color=["v.particle_random_2 < 0.7 ? 0.35 : %s" % RGB_R, "v.particle_random_2 < 0.7 ? 0.35 : %s" % RGB_G,
                                  "v.particle_random_2 < 0.7 ? 0.38 : %s" % RGB_B, 1.0])
    P["dust_ring"] = particle("dust_ring", "hitori_glow", "particles_blend", count=26, shape=disc(0.6, "outwards", True),
                              lifetime="0.7", speed=5, drag=5, size="0.25 + v.particle_age * 0.8",
                              color=[0.55, 0.55, 0.6, "0.5 * (" + FADE + ")"])
    # --- v1.2: ♪Rhythm Line♪（跳んで避けるリング）・Infinite Loop の範囲 ---
    P["rhythm_ring"] = particle(
        "rhythm_ring", "hitori_pixel", rate=(600, 700), active=1.8,
        shape={"minecraft:emitter_shape_custom": {"offset": [
            "math.cos(v.particle_random_1 * 360) * (1.5 + v.emitter_age * 9)", "0.1",
            "math.sin(v.particle_random_1 * 360) * (1.5 + v.emitter_age * 9)"]}},
        lifetime="0.15", size=["0.18", "0.06 + v.particle_random_3 * 0.12"],
        color=["v.particle_random_2 > 0.5 ? 0.3 : 1.0", "v.particle_random_2 > 0.5 ? 1.0 : 0.2", "1.0", "1.0"])
    P["zone_loop"] = particle(
        "zone_loop", "hitori_pixel", rate=(300, 200), active=0.5,
        shape={"minecraft:emitter_shape_custom": {"offset": [
            "math.cos(v.particle_random_1 * 360) * 4.5", "0.1", "math.sin(v.particle_random_1 * 360) * 4.5"]}},
        lifetime="0.5", size=BAR, color=tint("cyan", FLICKER))
    # --- ↓FREEDOM DiVE↓（落下） ---
    P["arrow_rain"] = particle("arrow_rain", "hitori_arrow", "particles_alpha", rate=(70, 220), active=3.0,
                               shape=box((12, 0.5, 12), (0, -1, 0), (0, 10, 0)), lifetime="0.8", speed=14,
                               size="0.55")
    P["arrow_down"] = particle("arrow_down", "hitori_arrow", "particles_alpha", count=5,
                               shape=disc(0.7, (0, -1, 0), offset=(0, 3.5, 0)), lifetime="0.5", speed=7, size="0.4")
    P["arrow_up"] = particle("arrow_up", "hitori_arrow", "particles_alpha", count=5,
                             shape=disc(0.7, (0, 1, 0)), lifetime="0.5", speed=7, size="0.4",
                             spin={"rotation": "180"})
    P["void_hole"] = particle("void_hole", "hitori_glow", "particles_blend", count=1, lifetime="0.4",
                              facing="emitter_transform_xz", size="4.2",
                              color=[0.04, 0.0, 0.08, "0.6 + 0.3 * math.sin(v.particle_age * 900)"])
    P["fall_pixels"] = particle("fall_pixels", "hitori_pixel", count=45, shape=disc(1.8, (0, -1, 0), offset=(0, 0.3, 0)),
                                lifetime="math.random(0.3, 0.6)", speed="math.random(2, 6)", accel=(0, -25, 0),
                                size=BAR, color=RGB)
    return P
