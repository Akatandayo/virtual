# -*- coding: utf-8 -*-
"""ソフィア・ハート: テクスチャとパーティクル（金と蒼が基調）."""
import math

from PIL import Image, ImageDraw

TEX = "textures/particle/"
FADE = "1 - v.particle_age / v.particle_lifetime"
UV = {"texture_width": 1, "texture_height": 1, "uv": [0, 0], "uv_size": [1, 1]}


# ---------------------------------------------------------------------------
# テクスチャ
# ---------------------------------------------------------------------------
def _fn(w, h, fn):
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


def t_orb(u, v):
    d = math.hypot(u - 0.5, v - 0.5) * 2
    if d < 0.45:
        return (255, 255, 255, 255)
    a = max(0.0, 1 - d) ** 1.2 * 1.6
    return (255, 255, 255, _c(min(1, a) * 255))


def t_star(u, v):
    dx, dy = abs(u - 0.5) * 2, abs(v - 0.5) * 2
    core = max(0.0, 1 - math.hypot(dx, dy) * 2.5) ** 2
    cross = max(0.0, 1 - dx * 10) * max(0.0, 1 - dy) + max(0.0, 1 - dy * 10) * max(0.0, 1 - dx)
    return (255, 255, 255, _c(min(1, core + cross) * 255))


def t_ring(u, v):
    d = math.hypot(u - 0.5, v - 0.5) * 2
    a = math.exp(-((d - 0.85) / 0.06) ** 2) + 0.3 * math.exp(-((d - 0.72) / 0.03) ** 2)
    return (255, 255, 255, _c(min(1, a) * 255))


def t_magic_circle(u, v):
    """魔法陣: 二重円 + 六芒星"""
    x, y = u - 0.5, v - 0.5
    d = math.hypot(x, y) * 2
    a = math.exp(-((d - 0.92) / 0.025) ** 2) + math.exp(-((d - 0.8) / 0.02) ** 2)
    ang = math.atan2(y, x)
    for k in range(6):  # 六芒星の辺
        t = ang - k * math.pi / 3
        dist = abs(d * math.cos(t - math.pi / 6) - 0.4)
        if d < 0.8:
            a += math.exp(-(dist / 0.02) ** 2) * 0.9
    if 0.8 < d < 0.92 and int((ang + math.pi) * 24 / math.pi) % 2 == 0:
        a += 0.35  # 文字の帯
    return (255, 255, 255, _c(min(1, a) * 255))


def t_slash(u, v):
    x, y = u - 0.5, v - 0.5
    r_out = math.hypot(x, y + 0.05) / 0.47
    r_in = math.hypot(x, y - 0.13) / 0.42
    if r_out > 1 or r_in < 1 or y > 0.18:
        return (255, 255, 255, 0)
    edge = 1 - min(1, (1 - r_out) * 4)
    ang = abs(math.atan2(x, -(y + 0.05))) / math.pi
    a = (0.35 + 0.65 * edge) * max(0.0, 1 - ang * 1.6)
    return (255, 255, 255, _c(a * 255))


def t_beam(u, v):
    x = abs(u - 0.5) * 2
    return (255, 255, 255, _c(max(0.0, 1 - x) ** 1.4 * 255))


def bolt():
    """稲妻（縦長）"""
    im = Image.new("RGBA", (16, 64))
    d = ImageDraw.Draw(im)
    pts = [(9, 0), (6, 14), (10, 22), (5, 36), (9, 44), (6, 64)]
    d.line(pts, fill=(255, 255, 255, 255), width=3)
    d.line([(7, 18), (2, 26)], fill=(255, 255, 255, 200), width=1)
    d.line([(8, 40), (13, 50)], fill=(255, 255, 255, 200), width=1)
    return im


def spike():
    im = Image.new("RGBA", (16, 32))
    for y in range(32):
        half = y / 32 * 7
        for x in range(16):
            if abs(x - 7.5) <= half:
                shade = 120 + int(60 * (1 - abs(x - 7.5) / max(half, 1)))
                im.putpixel((x, y), (shade, int(shade * 0.82), int(shade * 0.6), 255))
    return im


def t_hex(u, v):
    x, y = abs(u - 0.5) * 2, abs(v - 0.5) * 2
    d = max(x * 0.866 + y * 0.5, y)
    if d > 0.95:
        return (0, 0, 0, 0)
    if d > 0.8:
        return (255, 250, 220, 255)
    return (255, 230, 150, 70)


def rift():
    """次元の裂け目（黒い線と赤い縁）"""
    im = Image.new("RGBA", (16, 64))
    for y in range(64):
        w = 3.5 * math.sin(math.pi * y / 64)
        for x in range(16):
            dx = abs(x - 7.5)
            if dx < w * 0.45:
                im.putpixel((x, y), (10, 0, 15, 255))
            elif dx < w:
                im.putpixel((x, y), (255, 40, 60, _c(255 * (1 - (dx - w * 0.45) / (w * 0.55)))))
    return im


def cat_face():
    """宇宙猫（星空の猫の顔）"""
    im = Image.new("RGBA", (32, 32))
    d = ImageDraw.Draw(im)
    d.polygon([(4, 12), (6, 2), (13, 9)], fill=(40, 30, 90, 255))
    d.polygon([(28, 12), (26, 2), (19, 9)], fill=(40, 30, 90, 255))
    d.ellipse([3, 7, 29, 30], fill=(40, 30, 90, 255))
    for (x, y) in [(8, 12), (22, 24), (12, 26), (25, 14), (16, 10), (6, 20)]:
        d.point((x, y), fill=(255, 255, 255, 255))
    d.ellipse([9, 15, 14, 20], fill=(255, 255, 255, 255))
    d.ellipse([18, 15, 23, 20], fill=(255, 255, 255, 255))
    d.point((11, 17), fill=(0, 0, 0, 255))
    d.point((20, 17), fill=(0, 0, 0, 255))
    d.line([(15, 22), (17, 22)], fill=(255, 150, 190, 255))
    d.line([(1, 21), (8, 22)], fill=(220, 220, 255, 255))
    d.line([(24, 22), (31, 21)], fill=(220, 220, 255, 255))
    return im


def eye():
    """オッドアイの大きな目（金と蒼）"""
    im = Image.new("RGBA", (32, 16))
    d = ImageDraw.Draw(im)
    d.ellipse([1, 2, 31, 14], fill=(255, 255, 255, 255))
    d.ellipse([10, 2, 22, 14], fill=(255, 170, 30, 255))
    d.ellipse([13, 5, 19, 11], fill=(20, 10, 10, 255))
    d.point((14, 6), fill=(255, 255, 255, 255))
    d.arc([1, 2, 31, 14], 180, 360, fill=(30, 20, 40, 255), width=2)
    return im


def cross():
    im = Image.new("RGBA", (16, 16))
    d = ImageDraw.Draw(im)
    d.rectangle([6, 2, 9, 13], fill=(255, 255, 255, 255))
    d.rectangle([2, 6, 13, 9], fill=(255, 255, 255, 255))
    return im


def spear():
    """光の槍（上向き）"""
    im = Image.new("RGBA", (16, 64))
    d = ImageDraw.Draw(im)
    d.polygon([(7.5, 0), (12, 14), (7.5, 18), (3, 14)], fill=(255, 255, 255, 255))
    d.rectangle([6, 18, 9, 63], fill=(255, 240, 180, 230))
    d.rectangle([4, 18, 11, 20], fill=(255, 220, 120, 255))
    return im


def chain():
    im = Image.new("RGBA", (16, 32))
    d = ImageDraw.Draw(im)
    for y0 in (0, 10, 20):
        d.ellipse([3, y0, 12, y0 + 12], outline=(200, 190, 230, 255), width=2)
    return im


def baguette():
    im = Image.new("RGBA", (32, 8))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 1, 31, 6], radius=3, fill=(214, 150, 70, 255))
    for x in (6, 13, 20, 27):
        d.line([(x - 2, 5), (x + 1, 2)], fill=(250, 220, 160, 255))
    return im


def letter():
    """退勤届（封筒）"""
    im = Image.new("RGBA", (24, 16))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 23, 15], fill=(250, 248, 238, 255), outline=(120, 110, 100, 255))
    d.line([(0, 0), (12, 8), (23, 0)], fill=(120, 110, 100, 255))
    d.ellipse([9, 6, 15, 12], fill=(200, 30, 40, 255))
    return im


def clock():
    im = Image.new("RGBA", (32, 32))
    d = ImageDraw.Draw(im)
    d.ellipse([1, 1, 30, 30], outline=(255, 255, 255, 255), width=2)
    for k in range(12):
        a = k * math.pi / 6
        d.point((15.5 + 12 * math.cos(a), 15.5 + 12 * math.sin(a)), fill=(255, 255, 255, 255))
    d.line([(16, 16), (16, 6)], fill=(255, 255, 255, 255), width=2)
    d.line([(16, 16), (23, 19)], fill=(255, 255, 255, 255), width=1)
    return im


def build_textures():
    return {
        "sophia_glow": _fn(64, 64, t_glow), "sophia_orb": _fn(32, 32, t_orb), "sophia_star": _fn(32, 32, t_star),
        "sophia_ring": _fn(128, 128, t_ring), "sophia_circle": _fn(128, 128, t_magic_circle),
        "sophia_slash": _fn(128, 128, t_slash), "sophia_beam": _fn(16, 64, t_beam), "sophia_bolt": bolt(),
        "sophia_spike": spike(), "sophia_hex": _fn(32, 32, t_hex), "sophia_rift": rift(), "sophia_cat": cat_face(),
        "sophia_eye": eye(), "sophia_cross": cross(), "sophia_spear": spear(), "sophia_chain": chain(),
        "sophia_bread": baguette(), "sophia_letter": letter(), "sophia_clock": clock(),
        "sophia_chip": Image.new("RGBA", (4, 4), (255, 255, 255, 255)),
    }


# ---------------------------------------------------------------------------
# パーティクル
# ---------------------------------------------------------------------------
def particle(ident, tex, material="particles_add", *, count=None, rate=None, active=0.1, shape=None,
             lifetime="0.5", speed=None, accel=(0, 0, 0), drag=0.0, size="0.2", facing="lookat_xyz",
             color=None, spin=None, parametric=None, uv=UV):
    c = {}
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
    c["minecraft:particle_appearance_billboard"] = {"size": size, "facing_camera_mode": facing, "uv": uv}
    if color is not None:
        c["minecraft:particle_appearance_tinting"] = {"color": color}
    return {"format_version": "1.10.0", "particle_effect": {
        "description": {"identifier": "sophia:" + ident,
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


def ring_shape(radius_expr, y="0.1"):
    return {"minecraft:emitter_shape_custom": {"offset": [
        "math.cos(v.particle_random_1 * 360) * (%s)" % radius_expr, y,
        "math.sin(v.particle_random_1 * 360) * (%s)" % radius_expr]}}


def grad(*stops):
    n = len(stops) - 1
    return {"interpolant": "v.particle_age / v.particle_lifetime",
            "gradient": {"%.2f" % (i / n): s for i, s in enumerate(stops)}}


COLORS = {"gold": (1.0, 0.82, 0.3), "blue": (0.35, 0.65, 1.0), "white": (1, 1, 1), "red": (1.0, 0.15, 0.2),
          "purple": (0.7, 0.3, 1.0), "black": (0.25, 0.05, 0.35), "pink": (1.0, 0.45, 0.75), "green": (0.4, 1.0, 0.5),
          "cyan": (0.4, 0.95, 1.0)}


def rgba(name, alpha=FADE):
    r, g, b = COLORS[name]
    return [r, g, b, alpha]


def build_particles():
    P = {}

    def add(name, **kw):
        P[name] = particle(name, **kw)

    for col in COLORS:
        add("shockwave_" + col, tex="sophia_ring", count=1, lifetime="0.5", facing="emitter_transform_xz",
            size="0.5 + v.particle_age / v.particle_lifetime * 7", color=rgba(col))
        add("warn_" + col, tex="sophia_ring", count=1, lifetime="0.45", facing="emitter_transform_xz",
            size="2.0 - v.particle_age / v.particle_lifetime * 1.4",
            color=rgba(col, "0.4 + 0.6 * math.abs(math.sin(v.particle_age * 900))"))
        add("slash_" + col, tex="sophia_slash", count=1, lifetime="0.25",
            size="1.4 + v.particle_age / v.particle_lifetime * 1.0", spin={"rotation": "math.random(0, 360)"},
            color=rgba(col))
        add("charge_" + col, tex="sophia_glow", rate=(90, 120), active=0.7, shape=sphere(4, "inwards"),
            lifetime="0.5", speed=7, size="0.08 + v.particle_age / v.particle_lifetime * 0.12",
            color=rgba(col, "v.particle_age / v.particle_lifetime"))
    for col in ("gold", "red", "purple", "white", "blue"):
        add("big_slash_" + col, tex="sophia_slash", count=1, lifetime="0.6",
            size="6 + v.particle_age / v.particle_lifetime * 4", spin={"rotation": "math.random(-40, 40)"},
            color=rgba(col))
        add("shockwave_big_" + col, tex="sophia_ring", count=1, lifetime="0.9", facing="emitter_transform_xz",
            size="1 + v.particle_age / v.particle_lifetime * 18", color=rgba(col))
    add("magic_circle", tex="sophia_circle", count=1, lifetime="1.2", facing="emitter_transform_xz",
        size="2.6 * math.min(v.particle_age * 5, 1)", spin={"rotation": "0", "rotation_rate": "90"},
        color=rgba("gold", "math.min(1, (1 - v.particle_age / v.particle_lifetime) * 3)"))
    add("magic_circle_big", tex="sophia_circle", count=1, lifetime="2.0", facing="emitter_transform_xz",
        size="8 * math.min(v.particle_age * 3, 1)", spin={"rotation": "0", "rotation_rate": "-60"},
        color=rgba("purple", "math.min(1, (1 - v.particle_age / v.particle_lifetime) * 3)"))
    add("spark_burst", tex="sophia_star", count=16, shape=sphere(0.2), lifetime="math.random(0.25, 0.4)",
        speed="math.random(4, 9)", drag=5, size="0.16 * (" + FADE + ")", color=rgba("gold", 1))
    add("sparkle", tex="sophia_star", rate=(30, 30), active=0.4, shape=box((0.4, 1.0, 0.4), (0, 1, 0), (0, 1, 0)),
        lifetime="0.6", speed=0.4, size="0.1 * (" + FADE + ")", color=rgba("gold", 1))
    add("afterimage", tex="sophia_star", count=40, shape=box((0.3, 0.9, 0.3), (0, 1, 0)),
        lifetime="math.random(0.4, 0.8)", speed="math.random(0.2, 1)", size="0.12 * (" + FADE + ")",
        color=grad("#FFFFFFFF", "#FFFFD060", "#00FFA020"))
    add("beam_gold", tex="sophia_glow", count=2, shape=sphere(0.15, surface=False), lifetime="0.35",
        size="0.7 * (" + FADE + ")", color=grad("#FFFFFFFF", "#FFFFC040", "#00805000"))
    add("beam_purple", tex="sophia_glow", count=2, shape=sphere(0.15, surface=False), lifetime="0.4",
        size="1.0 * (" + FADE + ")", color=grad("#FFFFFFFF", "#FFB050FF", "#00300060"))
    add("beam_warn", tex="sophia_glow", count=1, lifetime="0.3", size="0.2",
        color=[1.0, 0.25, 0.2, "0.5 + 0.5 * math.sin(v.particle_age * 1200)"])
    add("electric", tex="sophia_bolt", count=10, shape=sphere(0.6), lifetime="0.15", size=["0.1", "0.4"],
        spin={"rotation": "math.random(0, 360)"}, color=[0.7, 0.85, 1.0, 1.0])
    add("electric_ring", tex="sophia_bolt", count=40, shape=disc(5, "outwards", surface=True, offset=(0, 0.8, 0)),
        lifetime="0.2", size=["0.25", "1.0"], spin={"rotation": "math.random(0, 360)"}, color=[0.7, 0.85, 1.0, 1.0])
    add("thunder", tex="sophia_bolt", count=3, shape=box((0.2, 0, 0.2), offset=(0, 8, 0)), lifetime="0.35",
        facing="lookat_y", size=["1.2", "8"], color=[0.9, 0.95, 1.0, FADE])
    add("thunder_black", tex="sophia_bolt", count=5, shape=box((0.6, 0, 0.6), offset=(0, 10, 0)), lifetime="0.6",
        facing="lookat_y", size=["2.4", "10"], color=[0.35, 0.05, 0.5, FADE])
    add("wind", tex="sophia_glow", count=60, shape=sphere(0.5), lifetime="0.5", speed="math.random(6, 14)",
        drag=3, size=["0.05", "0.5"], 
        color=[1, 1, 1, "0.6 * (" + FADE + ")"])
    add("tornado", tex="sophia_glow", rate=(120, 120), active=0.25, lifetime="0.7",
        parametric=["math.cos(v.particle_age * 900 + v.particle_random_1 * 360) * (0.4 + v.particle_age * 2.5)",
                    "v.particle_age * 5",
                    "math.sin(v.particle_age * 900 + v.particle_random_1 * 360) * (0.4 + v.particle_age * 2.5)"],
        size="0.14", color=[0.85, 0.9, 0.85, "0.7 * (" + FADE + ")"], material="particles_blend")
    add("earth_spike", tex="sophia_spike", material="particles_alpha", count=4,
        shape=disc(0.7, (0, 1, 0), offset=(0, -0.6, 0)), lifetime="0.6", speed=9, drag=10,
        facing="lookat_y", size=["0.4", "1.1"])
    add("dust", tex="sophia_glow", material="particles_blend", count=20, shape=disc(0.8, "outwards"),
        lifetime="0.8", speed="math.random(1, 3)", accel=(0, 0.5, 0), drag=2, size="0.3 * (" + FADE + ")",
        color=[0.55, 0.45, 0.3, "0.7 * (" + FADE + ")"])
    add("orb_gold", tex="sophia_orb", count=1, lifetime="0.22", size="0.45 * (1 - v.particle_age / v.particle_lifetime * 0.6)", color=rgba("gold", 1))
    add("orb_blue", tex="sophia_orb", count=1, lifetime="0.22", size="0.39 * (1 - v.particle_age / v.particle_lifetime * 0.6)", color=rgba("blue", 1))
    add("orb_pink", tex="sophia_orb", count=1, lifetime="0.22", size="0.53 * (1 - v.particle_age / v.particle_lifetime * 0.6)", color=rgba("pink", 1))
    add("hex_barrier", tex="sophia_hex", material="particles_blend", count=18, shape=sphere(1.4, (0, 0, 0)),
        lifetime="0.45", size="0.4", color=[1.0, 0.95, 0.8, "0.9 * (" + FADE + ")"])
    add("rift", tex="sophia_rift", material="particles_blend", count=1, lifetime="0.6", facing="lookat_y",
        size=["0.5", "1.6 * math.min(v.particle_age * 8, 1)"], spin={"rotation": "math.random(-30, 30)"})
    add("rift_big", tex="sophia_rift", material="particles_blend", count=1, lifetime="0.8",
        size=["1.0", "3.5 * math.min(v.particle_age * 6, 1)"], spin={"rotation": "math.random(-50, 50)"})
    add("cat", tex="sophia_cat", material="particles_alpha", count=6, shape=sphere(1.5, (0, 1, 0)),
        lifetime="1.4", speed=0.6, size="0.5 * math.min(v.particle_age * 6, 1)",
        spin={"rotation": "math.random(-20, 20)", "rotation_rate": "math.random(-60, 60)"})
    add("eye_big", tex="sophia_eye", material="particles_alpha", count=1, lifetime="1.5",
        size=["2.4 * math.min(v.particle_age * 4, 1)", "1.2 * math.min(v.particle_age * 4, 1) * "
              "(math.mod(v.particle_age, 0.7) < 0.08 ? 0.15 : 1)"])
    add("heal", tex="sophia_cross", count=8, shape=sphere(0.6), lifetime="0.9", speed=0.8, accel=(0, 1, 0),
        size="0.14 * (" + FADE + ")", color=rgba("green", 1))
    add("blackhole", tex="sophia_glow", material="particles_blend", rate=(140, 160), active=0.3,
        shape=sphere(4, "inwards"), lifetime="0.5", speed=8, size="0.25", color=[0.1, 0.0, 0.15, FADE])
    add("accretion", tex="sophia_ring", count=1, lifetime="0.35", facing="emitter_transform_xz", size="2.2",
        spin={"rotation": "math.random(0, 360)"}, color=rgba("purple", "0.8"))
    add("shell_fall", tex="sophia_glow", count=1, shape=box((0, 0, 0), (0, -1, 0), (0, 14, 0)), lifetime="0.7",
        speed=20, size="0.35", color=rgba("red", 1))
    add("light_pillar", tex="sophia_beam", count=2, shape=box((0.1, 0, 0.1), offset=(0, 10, 0)), lifetime="0.6",
        facing="lookat_y", size=["1.4 * (" + FADE + ")", "20"], color=grad("#FFFFFFFF", "#FFFFE080", "#00FFC040"))
    add("light_pillar_huge", tex="sophia_beam", count=3, shape=box((0.2, 0, 0.2), offset=(0, 16, 0)),
        lifetime="2.0", facing="lookat_y", size=["4 * (" + FADE + ")", "32"],
        color=grad("#FFFFFFFF", "#FFFFE080", "#00FFC040"))
    add("spear_ring", tex="sophia_spear", material="particles_alpha", count=8, lifetime="0.9",
        shape=ring_shape("3", "1"), size=["0.25", "1.0"], facing="lookat_y", spin={"rotation": "90"})
    add("chain", tex="sophia_chain", material="particles_alpha", count=6, shape=disc(0.6, (0, 1, 0)),
        lifetime="0.9", speed=1.5, drag=2, size=["0.2", "0.45"], spin={"rotation": "math.random(0, 360)"})
    add("stars", tex="sophia_star", rate=(220, 700), active=4.0, shape=box((22, 10, 22), (0, 0, 0), (0, 6, 0)),
        lifetime="math.random(1.5, 3)", size="0.08 + v.particle_random_2 * 0.18",
        color=["0.7 + v.particle_random_3 * 0.3", "0.7 + v.particle_random_4 * 0.3", "1.0",
               "math.sin(v.particle_age / v.particle_lifetime * 180)"])
    add("galaxy", tex="sophia_glow", rate=(400, 700), active=2.0, lifetime="1.2",
        parametric=["math.cos(v.particle_random_1 * 720 + v.particle_age * 200) * v.particle_random_1 * 6",
                    "1.5 + (v.particle_random_2 - 0.5) * 0.3",
                    "math.sin(v.particle_random_1 * 720 + v.particle_age * 200) * v.particle_random_1 * 6"],
        size="0.1", color=["0.6 + v.particle_random_1 * 0.4", "0.3", "1.0", FADE])
    add("bread", tex="sophia_bread", material="particles_alpha", count=6, shape=sphere(0.4),
        lifetime="0.8", speed="math.random(2, 5)", accel=(0, -9, 0), size=["0.35", "0.09"],
        spin={"rotation": "math.random(0, 360)", "rotation_rate": "math.random(-500, 500)"})
    add("letter_trail", tex="sophia_star", count=2, shape=sphere(0.2), lifetime="0.3", size="0.08",
        color=rgba("white"))
    add("clock", tex="sophia_clock", count=1, lifetime="1.6", facing="emitter_transform_xz",
        size="10 * math.min(v.particle_age * 3, 1)", spin={"rotation": "0", "rotation_rate": "-120"},
        color=[0.8, 0.85, 1.0, "0.5 * (" + FADE + ")"])
    add("aura_gold", tex="sophia_star", rate=(20, 20), active=0.4, shape=disc(0.5), lifetime="0.8", speed=1,
        size="0.1 * (" + FADE + ")", color=rgba("gold", 1))
    add("aura_electric", tex="sophia_bolt", rate=(15, 10), active=0.4, shape=box((0.4, 0.9, 0.4), (0, 0, 0), (0, 1, 0)),
        lifetime="0.1", size=["0.08", "0.35"], spin={"rotation": "math.random(0, 360)"}, color=rgba("blue", 1))
    add("aura_flame", tex="sophia_glow", rate=(35, 30), active=0.4, shape=disc(0.5), lifetime="math.random(0.4, 0.8)",
        speed="math.random(1, 2.5)", size="0.2 * (" + FADE + ")", color=grad("#FFFFD0FF", "#FFB040FF", "#00400070"))
    # --- v1.2: 剣の軌跡（金）・足音の土煙・着地の破片と土煙 ---
    add("arc", tex="sophia_glow", rate=(260, 120), active=0.16, lifetime="0.24", size="0.09 * (" + FADE + ") + 0.02",
        color=grad("#FFFFFFFF", "#FFFFE080", "#00FFB020"))
    add("step_dust", tex="sophia_glow", material="particles_blend", count=3, shape=disc(0.15, "outwards"), lifetime="0.5",
        speed=0.7, drag=2, size="0.12 + v.particle_age * 0.3", color=[0.62, 0.57, 0.5, "0.45 * (" + FADE + ")"])
    add("debris", tex="sophia_chip", material="particles_alpha", count=18, shape=sphere(0.3, (0, 1, 0)),
        lifetime="math.random(0.6, 1.0)", speed="math.random(3, 7)", accel=(0, -16, 0), drag=0.5,
        size="0.05 + v.particle_random_1 * 0.07",
        spin={"rotation": "math.random(0, 360)", "rotation_rate": "math.random(-500, 500)"},
        color=["0.35 + v.particle_random_2 * 0.2", "0.3 + v.particle_random_2 * 0.15", "0.25 + v.particle_random_2 * 0.1", 1.0])
    add("dust_ring", tex="sophia_glow", material="particles_blend", count=26, shape=disc(0.6, "outwards", True),
        lifetime="0.7", speed=5, drag=5, size="0.25 + v.particle_age * 0.8", color=[0.64, 0.58, 0.5, "0.55 * (" + FADE + ")"])
    add("laplace_eye", tex="sophia_star", count=1, lifetime="0.45", size="0.13 * (" + FADE + ") + 0.04",
        color=[0.45, 0.8, 1.0, 1.0])
    add("hand_glow", tex="sophia_glow", count=8, shape=sphere(0.4, "inwards"), lifetime="0.3", speed=2,
        size="0.08", color=rgba("gold"))
    return P


def build_fogs():
    return {"sophia_universe": {"format_version": "1.16.100", "minecraft:fog_settings": {
        "description": {"identifier": "sophia:universe"},
        "distance": {"air": {"fog_start": 6, "fog_end": 48, "fog_color": "#120624", "render_distance_type": "fixed"}}}}}


def entity_textures():
    sword = Image.new("RGBA", (16, 64))
    d = ImageDraw.Draw(sword)
    d.polygon([(7.5, 0), (11, 8), (11, 44), (4, 44), (4, 8)], fill=(150, 210, 255, 230))
    d.line([(7.5, 2), (7.5, 43)], fill=(255, 255, 255, 255))
    d.rectangle([1, 44, 14, 47], fill=(255, 210, 80, 255))
    d.rectangle([6, 48, 9, 63], fill=(40, 60, 140, 255))
    drone = Image.new("RGBA", (16, 16), (240, 250, 240, 255))
    dd = ImageDraw.Draw(drone)
    dd.rectangle([0, 0, 15, 15], outline=(80, 200, 120, 255))
    dd.rectangle([6, 3, 9, 12], fill=(60, 220, 110, 255))
    dd.rectangle([3, 6, 12, 9], fill=(60, 220, 110, 255))
    out = {"sophia_funnel": sword, "sophia_drone": drone, "sophia_letter_e": letter(),
           "sophia_empty": Image.new("RGBA", (16, 16))}
    # 弾幕の弾: 左半分が芯（不透明・発光）、右半分が外殻（半透明）
    for name, (r, g, b) in (("slow", (255, 110, 190)), ("normal", (255, 205, 70)), ("fast", (90, 170, 255))):
        im = Image.new("RGBA", (16, 16))
        for y in range(8):
            for x in range(8):
                d = math.hypot(x - 3.5, y - 3.5) / 4.95
                core = 1 - d
                im.putpixel((x, y), (_c(r + (255 - r) * core), _c(g + (255 - g) * core), _c(b + (255 - b) * core), 255))
                im.putpixel((x + 8, y), (r, g, b, _c(70 + 90 * d)))
        out["sophia_orb_" + name] = im
    return out
