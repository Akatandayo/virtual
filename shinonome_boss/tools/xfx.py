# -*- coding: utf-8 -*-
"""東雲 永々: テクスチャとパーティクル（宇宙・重力・時間・炎・フランスパン）."""
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


def t_star(u, v):
    dx, dy = abs(u - 0.5) * 2, abs(v - 0.5) * 2
    core = max(0.0, 1 - math.hypot(dx, dy) * 2.5) ** 2
    cross = max(0.0, 1 - dx * 10) * max(0.0, 1 - dy) + max(0.0, 1 - dy * 10) * max(0.0, 1 - dx)
    return (255, 255, 255, _c(min(1, core + cross) * 255))


def t_ring(u, v):
    d = math.hypot(u - 0.5, v - 0.5) * 2
    return (255, 255, 255, _c(min(1, math.exp(-((d - 0.85) / 0.06) ** 2)) * 255))


def t_portal(u, v):
    """ワープホール: 渦を巻く紫の輪"""
    x, y = u - 0.5, v - 0.5
    d = math.hypot(x, y) * 2
    ang = math.atan2(y, x)
    swirl = 0.5 + 0.5 * math.sin(ang * 4 + d * 14)
    a = max(0.0, 1 - abs(d - 0.7) / 0.3) * (0.5 + 0.5 * swirl)
    if d < 0.45:
        a = max(a, 0.85 * (1 - d / 0.45) ** 0.3)
        return (30, 0, 60, _c(a * 255))
    return (_c(150 + 100 * swirl), _c(60 + 60 * swirl), 255, _c(a * 255))


def t_slash(u, v):
    x, y = u - 0.5, v - 0.5
    r_out = math.hypot(x, y + 0.05) / 0.47
    r_in = math.hypot(x, y - 0.13) / 0.42
    if r_out > 1 or r_in < 1 or y > 0.18:
        return (255, 255, 255, 0)
    edge = 1 - min(1, (1 - r_out) * 4)
    ang = abs(math.atan2(x, -(y + 0.05))) / math.pi
    return (255, 255, 255, _c((0.35 + 0.65 * edge) * max(0.0, 1 - ang * 1.6) * 255))


def t_beam(u, v):
    x = abs(u - 0.5) * 2
    return (255, 255, 255, _c(max(0.0, 1 - x) ** 1.4 * 255))


def baguette(w=32, h=8):
    im = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 1, w - 1, h - 2], radius=3, fill=(214, 150, 70, 255))
    for x in range(6, w, 7):
        d.line([(x - 2, h - 3), (x + 1, 2)], fill=(250, 220, 160, 255))
    return im


def bread_point():
    """先の尖ったフランスパン（上向き）"""
    im = Image.new("RGBA", (8, 32))
    d = ImageDraw.Draw(im)
    d.polygon([(3.5, 0), (7, 6), (7, 31), (0, 31), (0, 6)], fill=(214, 150, 70, 255))
    for y in range(8, 30, 6):
        d.line([(1, y + 2), (6, y)], fill=(250, 220, 160, 255))
    return im


def claw():
    im = Image.new("RGBA", (32, 32))
    d = ImageDraw.Draw(im)
    for k in range(3):
        d.line([(6 + k * 8, 2), (2 + k * 8, 30)], fill=(255, 255, 255, 255), width=2)
    return im


def chain():
    im = Image.new("RGBA", (16, 32))
    d = ImageDraw.Draw(im)
    for y0 in (0, 10, 20):
        d.ellipse([3, y0, 12, y0 + 12], outline=(220, 220, 235, 255), width=2)
    return im


def halo():
    im = Image.new("RGBA", (32, 16))
    d = ImageDraw.Draw(im)
    d.ellipse([1, 3, 30, 13], outline=(255, 230, 120, 255), width=2)
    return im


def clock():
    im = Image.new("RGBA", (64, 64))
    d = ImageDraw.Draw(im)
    d.ellipse([2, 2, 61, 61], outline=(255, 255, 255, 255), width=3)
    d.ellipse([8, 8, 55, 55], outline=(255, 255, 255, 120), width=1)
    for k in range(12):
        a = k * math.pi / 6
        r0, r1 = 23, 27
        d.line([(31.5 + r0 * math.cos(a), 31.5 + r0 * math.sin(a)), (31.5 + r1 * math.cos(a), 31.5 + r1 * math.sin(a))],
               fill=(255, 255, 255, 255), width=2)
    d.line([(32, 32), (32, 12)], fill=(255, 255, 255, 255), width=3)
    d.line([(32, 32), (45, 38)], fill=(255, 255, 255, 255), width=2)
    return im


def sun():
    def f(u, v):
        d = math.hypot(u - 0.5, v - 0.5) * 2
        if d < 0.55:
            return (255, 255, 230, 255)
        a = max(0.0, 1 - (d - 0.55) / 0.45)
        return (255, _c(200 * a + 40), _c(60 * a), _c(a * 255))
    return _fn(64, 64, f)


def big_sword():
    """マルチバースソード（下向き）: 虹色に揺らめく刀身"""
    im = Image.new("RGBA", (16, 64))
    for y in range(64):
        for x in range(16):
            dx = abs(x - 7.5)
            if y < 14:  # 柄（上）
                if dx < 2:
                    im.putpixel((x, y), (40, 30, 70, 255))
            elif y < 17:  # 鍔
                im.putpixel((x, y), (255, 215, 90, 255))
            else:
                w = 5.5 * min(1, (63 - y) / 10)
                if dx < w:
                    t = (y - 17) / 46
                    r, g, b = (_c(140 + 115 * math.sin(t * 6)), _c(140 + 115 * math.sin(t * 6 + 2)),
                               _c(200 + 55 * math.sin(t * 6 + 4)))
                    im.putpixel((x, y), (r, g, b, 255) if dx < w * 0.7 else (255, 255, 255, 255))
    return im


def burger():
    im = Image.new("RGBA", (16, 16))
    d = ImageDraw.Draw(im)
    d.pieslice([1, 2, 14, 14], 180, 360, fill=(220, 150, 60, 255))
    d.rectangle([1, 8, 14, 9], fill=(80, 170, 60, 255))
    d.rectangle([1, 10, 14, 11], fill=(110, 60, 30, 255))
    d.rounded_rectangle([1, 12, 14, 14], radius=1, fill=(220, 150, 60, 255))
    for x in (4, 8, 11):
        d.point((x, 5), fill=(255, 250, 220, 255))
    return im


def window_tex():
    im = Image.new("RGBA", (32, 32))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 15, 31], fill=(240, 205, 110, 255))
    d.line([(0, 0), (15, 0)], fill=(255, 245, 200, 255))
    for y in range(32):
        a = 110 + int(60 * math.sin(y / 32 * math.pi))
        d.line([(16, y), (31, y)], fill=(90, 230, 255, a))
    d.line([(18, 4), (26, 12)], fill=(255, 255, 255, 200))
    return im


def build_textures():
    return {
        "toa_glow": _fn(64, 64, t_glow), "toa_star": _fn(32, 32, t_star), "toa_ring": _fn(128, 128, t_ring),
        "toa_portal": _fn(64, 64, t_portal), "toa_slash": _fn(128, 128, t_slash), "toa_beam": _fn(16, 64, t_beam),
        "toa_bread": baguette(), "toa_bread_point": bread_point(), "toa_claw": claw(), "toa_chain": chain(),
        "toa_halo": halo(), "toa_clock": clock(), "toa_sun": sun(), "toa_sword": big_sword(), "toa_burger": burger(),
    }


def star_tex():
    """星弾: 左半分が芯（不透明・発光）、右半分が外殻（半透明）"""
    im = Image.new("RGBA", (16, 16))
    for y in range(8):
        for x in range(8):
            d = math.hypot(x - 3.5, y - 3.5) / 4.95
            core = 1 - d
            im.putpixel((x, y), (255, _c(215 + 40 * core), _c(90 + 165 * core), 255))
            im.putpixel((x + 8, y), (180, 140, 255, _c(70 + 90 * d)))
    return im


def entity_textures():
    return {"toa_window": window_tex(), "toa_bread_e": baguette(32, 8), "toa_empty": Image.new("RGBA", (16, 16)),
            "toa_star_e": star_tex()}


# ---------------------------------------------------------------------------
# パーティクル
# ---------------------------------------------------------------------------
def particle(ident, tex, material="particles_add", *, count=None, rate=None, active=0.1, shape=None,
             lifetime="0.5", speed=None, accel=(0, 0, 0), drag=0.0, size="0.2", facing="lookat_xyz",
             color=None, spin=None, parametric=None):
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
    c["minecraft:particle_appearance_billboard"] = {"size": size, "facing_camera_mode": facing, "uv": UV}
    if color is not None:
        c["minecraft:particle_appearance_tinting"] = {"color": color}
    return {"format_version": "1.10.0", "particle_effect": {
        "description": {"identifier": "shinonome:" + ident,
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


def ring_shape(radius, y="0.1"):
    return {"minecraft:emitter_shape_custom": {"offset": [
        "math.cos(v.particle_random_1 * 360) * %s" % radius, y, "math.sin(v.particle_random_1 * 360) * %s" % radius]}}


def grad(*stops):
    n = len(stops) - 1
    return {"interpolant": "v.particle_age / v.particle_lifetime",
            "gradient": {"%.2f" % (i / n): s for i, s in enumerate(stops)}}


COLORS = {"white": (1, 1, 1), "purple": (0.65, 0.35, 1.0), "cyan": (0.35, 0.95, 1.0), "gold": (1.0, 0.82, 0.35),
          "red": (1.0, 0.25, 0.15), "black": (0.2, 0.05, 0.3), "silver": (0.85, 0.88, 0.95), "blue": (0.4, 0.6, 1.0)}
FIRE = grad("#FFFFF0A0", "#FFFF7020", "#FFC01808", "#00400000")


def rgba(name, alpha=FADE):
    r, g, b = COLORS[name]
    return [r, g, b, alpha]


def build_particles():
    P = {}

    def add(name, **kw):
        P[name] = particle(name, **kw)

    for col in ("white", "purple", "cyan", "gold", "red", "silver", "blue"):
        add("shockwave_" + col, tex="toa_ring", count=1, lifetime="0.5", facing="emitter_transform_xz",
            size="0.5 + v.particle_age / v.particle_lifetime * 7", color=rgba(col))
        add("warn_" + col, tex="toa_ring", count=1, lifetime="0.45", facing="emitter_transform_xz",
            size="2.0 - v.particle_age / v.particle_lifetime * 1.4",
            color=rgba(col, "0.4 + 0.6 * math.abs(math.sin(v.particle_age * 900))"))
        add("slash_" + col, tex="toa_slash", count=1, lifetime="0.25", size="1.4 + v.particle_age / v.particle_lifetime",
            spin={"rotation": "math.random(0, 360)"}, color=rgba(col))
        add("charge_" + col, tex="toa_glow", rate=(90, 120), active=0.7, shape=sphere(4, "inwards"), lifetime="0.5",
            speed=7, size="0.08 + v.particle_age / v.particle_lifetime * 0.12",
            color=rgba(col, "v.particle_age / v.particle_lifetime"))
    for col in ("purple", "white", "gold", "cyan"):
        add("shockwave_big_" + col, tex="toa_ring", count=1, lifetime="0.9", facing="emitter_transform_xz",
            size="1 + v.particle_age / v.particle_lifetime * 18", color=rgba(col))
        add("big_slash_" + col, tex="toa_slash", count=1, lifetime="0.6", size="6 + v.particle_age / v.particle_lifetime * 4",
            spin={"rotation": "math.random(-40, 40)"}, color=rgba(col))
    add("spark", tex="toa_star", count=16, shape=sphere(0.2), lifetime="math.random(0.25, 0.4)",
        speed="math.random(4, 9)", drag=5, size="0.15 * (" + FADE + ")", color=rgba("silver", 1))
    add("smoke", tex="toa_glow", material="particles_blend", count=40, shape=sphere(0.6), lifetime="math.random(0.5, 1.0)",
        speed="math.random(1, 3)", drag=2, size="0.5 + v.particle_age * 0.6", color=[0.9, 0.9, 0.95, "0.7 * (" + FADE + ")"])
    add("gold_eye", tex="toa_star", count=1, lifetime="0.35", size="0.12 * (" + FADE + ") + 0.04", color=rgba("gold", 1))
    add("portal", tex="toa_portal", count=1, lifetime="1.0", facing="lookat_y",
        size="2.2 * math.min(v.particle_age * 6, 1) * math.min((1 - v.particle_age / v.particle_lifetime) * 5, 1)",
        spin={"rotation": "0", "rotation_rate": "200"})
    add("portal_flat", tex="toa_portal", count=1, lifetime="1.4", facing="emitter_transform_xz",
        size="3.5 * math.min(v.particle_age * 4, 1) * math.min((1 - v.particle_age / v.particle_lifetime) * 4, 1)",
        spin={"rotation": "0", "rotation_rate": "160"})
    add("hole", tex="toa_glow", material="particles_blend", rate=(120, 120), active=0.25, shape=sphere(2.5, "inwards"),
        lifetime="0.4", speed=6, size="0.18", color=[0.08, 0.0, 0.15, FADE])
    add("hole_core", tex="toa_glow", material="particles_blend", count=2, lifetime="0.3", size="1.1",
        color=[0.02, 0.0, 0.05, "0.9"])
    add("accretion", tex="toa_ring", count=1, lifetime="0.3", facing="emitter_transform_xz", size="1.8",
        spin={"rotation": "math.random(0, 360)"}, color=rgba("purple", "0.8"))
    add("gravity_down", tex="toa_glow", rate=(60, 80), active=0.5, shape=box((1, 0.1, 1), (0, -1, 0), (0, 2.5, 0)),
        lifetime="0.4", speed=8, size=["0.04", "0.4"], facing="lookat_y", color=rgba("purple"))
    add("gravity_up", tex="toa_glow", rate=(60, 80), active=0.5, shape=box((1, 0.1, 1), (0, 1, 0)), lifetime="0.5",
        speed=5, size=["0.04", "0.35"], facing="lookat_y", color=rgba("cyan"))
    add("fire_burst", tex="toa_glow", count=40, shape=sphere(0.4), lifetime="math.random(0.5, 0.9)",
        speed="math.random(3, 8)", accel=(0, 3, 0), drag=2.5, size="0.25 * (" + FADE + ")", color=FIRE)
    add("dragon", tex="toa_glow", count=6, shape=sphere(0.5, surface=False), lifetime="math.random(0.4, 0.8)",
        speed="math.random(0.3, 1.2)", accel=(0, 1.5, 0), size="0.55 * (" + FADE + ")", color=FIRE)
    add("dragon_head", tex="toa_glow", count=2, lifetime="0.12", size="1.3", color=grad("#FFFFFFE0", "#FFFF9030"))
    add("sun", tex="toa_sun", count=1, lifetime="0.15", size="1.6")
    add("oil", tex="toa_glow", material="particles_blend", count=25, shape=sphere(0.6), lifetime="0.9",
        speed="math.random(1, 4)", accel=(0, -12, 0), size="0.16", color=[0.15, 0.12, 0.05, 0.9])
    add("oil_drip", tex="toa_glow", material="particles_blend", count=3, shape=box((0.3, 0.6, 0.3), (0, -1, 0), (0, 1, 0)),
        lifetime="0.5", speed=1, accel=(0, -6, 0), size="0.08", color=[0.15, 0.12, 0.05, 0.9])
    add("silver_beam", tex="toa_glow", count=2, shape=sphere(0.15, surface=False), lifetime="0.4",
        size="0.75 * (" + FADE + ")", color=grad("#FFFFFFFF", "#FFC8D2E6", "#00505A70"))
    add("beam_cyan", tex="toa_glow", count=2, shape=sphere(0.15, surface=False), lifetime="0.35",
        size="0.7 * (" + FADE + ")", color=grad("#FFFFFFFF", "#FF60E6FF", "#00104060"))
    add("beam_warn", tex="toa_glow", count=1, lifetime="0.3", size="0.2",
        color=[1.0, 0.3, 0.3, "0.5 + 0.5 * math.sin(v.particle_age * 1200)"])
    add("chain", tex="toa_chain", material="particles_alpha", count=6, shape=disc(0.6, (0, 1, 0)), lifetime="1.0",
        speed=1.5, drag=2, size=["0.2", "0.45"], spin={"rotation": "math.random(0, 360)"})
    add("halo", tex="toa_halo", material="particles_alpha", count=1, lifetime="0.55", size=["0.6", "0.3"])
    add("claw", tex="toa_claw", count=1, lifetime="0.3", size="1.4", spin={"rotation": "math.random(-30, 30)"},
        color=rgba("white"))
    add("bread_ring", tex="toa_bread_point", material="particles_alpha", count=8, shape=ring_shape("2.5", "1.2"),
        lifetime="1.1", facing="lookat_y", size=["0.18", "0.7"], spin={"rotation": "90"})
    add("bread_burst", tex="toa_bread", material="particles_alpha", count=8, shape=sphere(0.4), lifetime="0.8",
        speed="math.random(2, 5)", accel=(0, -9, 0), size=["0.35", "0.09"],
        spin={"rotation": "math.random(0, 360)", "rotation_rate": "math.random(-500, 500)"})
    add("bread_rain", tex="toa_bread_point", material="particles_alpha", count=3, shape=box((1, 0.2, 1), (0, -1, 0), (0, 8, 0)),
        lifetime="0.35", speed=22, facing="lookat_y", size=["0.18", "0.7"], spin={"rotation": "180"})
    add("burger", tex="toa_burger", material="particles_alpha", count=1, lifetime="0.6", speed=0.5, size="0.35")
    add("clock", tex="toa_clock", count=1, lifetime="2.0", facing="emitter_transform_xz",
        size="14 * math.min(v.particle_age * 3, 1)", spin={"rotation": "0", "rotation_rate": "-90"},
        color=[0.85, 0.9, 1.0, "0.6 * (" + FADE + ")"])
    add("big_sword", tex="toa_sword", material="particles_alpha", count=1, lifetime="0.55", facing="lookat_y",
        size=["1.6", "6"], parametric=["0", "math.max(0, 16 - v.particle_age * 60)", "0"])
    add("stars", tex="toa_star", rate=(160, 400), active=3.0, shape=box((16, 8, 16), (0, 0, 0), (0, 5, 0)),
        lifetime="math.random(1.5, 2.5)", size="0.08 + v.particle_random_2 * 0.15",
        color=["0.8", "0.8 + v.particle_random_3 * 0.2", "1.0", "math.sin(v.particle_age / v.particle_lifetime * 180)"])
    add("water", tex="toa_glow", material="particles_blend", count=18, shape=sphere(0.6), lifetime="0.6",
        speed="math.random(1, 4)", accel=(0, -10, 0), size="0.15", color=[0.4, 0.75, 1.0, 0.8])
    add("water_aura", tex="toa_glow", material="particles_blend", rate=(30, 30), active=0.4,
        shape=box((0.35, 0.8, 0.35), (0, 1, 0), (0, 0.8, 0)), lifetime="0.5", speed=0.6, size="0.12",
        color=[0.4, 0.75, 1.0, "0.7 * (" + FADE + ")"])
    add("rage", tex="toa_glow", rate=(40, 40), active=0.4, shape=disc(0.5), lifetime="0.6", speed="math.random(1, 3)",
        size="0.2 * (" + FADE + ")", color=grad("#FFFFFFFF", "#FFFF3040", "#00500010"))
    add("dark_aura", tex="toa_glow", material="particles_blend", rate=(25, 25), active=0.4, shape=disc(0.6),
        lifetime="0.8", speed=1.2, size="0.25 * (" + FADE + ")", color=[0.15, 0.0, 0.25, "0.8 * (" + FADE + ")"])
    add("hand", tex="toa_glow", count=8, shape=sphere(0.4, "inwards"), lifetime="0.3", speed=2, size="0.08",
        color=rgba("purple"))
    add("trail", tex="toa_glow", count=10, shape=sphere(0.3, surface=False), lifetime="0.3", speed="math.random(0.5, 2)",
        drag=3, size="0.13 * (" + FADE + ")", color=rgba("purple"))
    add("star_trail", tex="toa_glow", count=1, lifetime="0.22", size="0.45 * (1 - v.particle_age / v.particle_lifetime * 0.6)",
        color=rgba("gold", 1))
    add("cat_paw", tex="toa_claw", count=4, shape=sphere(0.5), lifetime="0.4", speed=2, size="0.3", color=rgba("gold"))
    return P


def build_fogs():
    return {
        "toa_timestop": {"format_version": "1.16.100", "minecraft:fog_settings": {
            "description": {"identifier": "shinonome:timestop"},
            "distance": {"air": {"fog_start": 2, "fog_end": 36, "fog_color": "#9aa0aa", "render_distance_type": "fixed"}}}},
    }
