# -*- coding: utf-8 -*-
"""月島 風花: テクスチャとパーティクル（狙撃・羽・水流・人形・回転）."""
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


def t_slash(u, v):
    x, y = u - 0.5, v - 0.5
    r_out = math.hypot(x, y + 0.05) / 0.47
    r_in = math.hypot(x, y - 0.13) / 0.42
    if r_out > 1 or r_in < 1 or y > 0.18:
        return (255, 255, 255, 0)
    edge = 1 - min(1, (1 - r_out) * 4)
    ang = abs(math.atan2(x, -(y + 0.05))) / math.pi
    return (255, 255, 255, _c((0.35 + 0.65 * edge) * max(0.0, 1 - ang * 1.6) * 255))


def t_reticle(u, v):
    """照準: 円と十字"""
    x, y = u - 0.5, v - 0.5
    d = math.hypot(x, y) * 2
    ring = math.exp(-((d - 0.8) / 0.05) ** 2)
    cross = (abs(x) < 0.02 and 0.15 < abs(y) * 2 < 0.95) or (abs(y) < 0.02 and 0.15 < abs(x) * 2 < 0.95)
    return (255, 255, 255, _c(min(1, ring + (0.9 if cross else 0)) * 255))


def t_spiral(u, v):
    """回転: 金色の渦"""
    x, y = u - 0.5, v - 0.5
    d = math.hypot(x, y) * 2
    if d > 1:
        return (0, 0, 0, 0)
    ang = math.atan2(y, x)
    band = 0.5 + 0.5 * math.sin(ang * 2 + d * 18)
    a = band * (1 - d) ** 0.4
    return (255, 255, 255, _c(a * 255))


def feather():
    im = Image.new("RGBA", (16, 32))
    d = ImageDraw.Draw(im)
    d.ellipse([2, 1, 13, 26], fill=(255, 255, 255, 255))
    d.polygon([(7, 26), (9, 26), (8, 31)], fill=(255, 255, 255, 255))
    d.line([(8, 3), (8, 31)], fill=(200, 200, 200, 255))
    for y in range(6, 24, 4):
        d.line([(8, y), (3, y - 3)], fill=(225, 225, 225, 255))
        d.line([(8, y), (13, y - 3)], fill=(225, 225, 225, 255))
    return im


def petal():
    im = Image.new("RGBA", (16, 16))
    d = ImageDraw.Draw(im)
    d.ellipse([2, 4, 13, 13], fill=(255, 255, 255, 255))
    d.polygon([(5, 5), (8, 1), (11, 5)], fill=(255, 255, 255, 255))
    return im


def crescent():
    im = Image.new("RGBA", (32, 32))
    d = ImageDraw.Draw(im)
    d.ellipse([2, 2, 29, 29], fill=(255, 255, 255, 255))
    d.ellipse([9, 0, 34, 25], fill=(0, 0, 0, 0))
    return im


def chip():
    return _fn(4, 4, lambda u, v: (255, 255, 255, 255))


def build_textures():
    return {"fuuka_glow": _fn(32, 32, t_glow), "fuuka_star": _fn(32, 32, t_star), "fuuka_ring": _fn(64, 64, t_ring),
            "fuuka_slash": _fn(64, 64, t_slash), "fuuka_reticle": _fn(64, 64, t_reticle),
            "fuuka_spiral": _fn(64, 64, t_spiral), "fuuka_feather": feather(), "fuuka_petal": petal(),
            "fuuka_moon": crescent(), "fuuka_chip": chip()}


# ---------------------------------------------------------------------------
# 召喚物・スタンドのテクスチャ（すべてオリジナル）
# ---------------------------------------------------------------------------
def solid(w, h, col, shade=True):
    im = Image.new("RGBA", (w, h), col)
    if shade:
        d = ImageDraw.Draw(im)
        dark = tuple(int(c * 0.78) for c in col[:3]) + (255,)
        d.rectangle([0, h - max(1, h // 4), w - 1, h - 1], fill=dark)
    return im


def fang_texture():
    """スタンド「牙」: 深紅の体に金の縁取り、紺の継ぎ目、青く光る目（64x64）"""
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    crimson, dark, navy, gold, eye = (178, 32, 46, 255), (110, 16, 28, 255), (30, 34, 64, 255), (232, 196, 90, 255), \
        (130, 248, 255, 255)
    d.rectangle([0, 0, 31, 15], fill=crimson)                 # 頭
    d.rectangle([8, 8, 15, 15], fill=navy)                    # 顔（仮面）
    d.rectangle([9, 11, 10, 11], fill=eye); d.rectangle([13, 11, 14, 11], fill=eye)
    d.line([(8, 14), (15, 14)], fill=gold)
    d.rectangle([32, 0, 47, 7], fill=gold)                    # 冠羽
    d.rectangle([48, 0, 63, 7], fill=(255, 240, 200, 255))
    d.rectangle([0, 16, 23, 27], fill=crimson)                # 胴
    d.line([(0, 21), (23, 21)], fill=gold)
    d.rectangle([9, 17, 14, 20], fill=navy)                   # 胸の核
    d.rectangle([11, 18, 12, 19], fill=eye)
    d.rectangle([24, 16, 39, 27], fill=dark)                  # 腕
    d.line([(24, 18), (39, 18)], fill=gold)
    d.rectangle([40, 16, 51, 27], fill=navy)                  # 脚（先細り）
    d.rectangle([0, 32, 31, 35], fill=gold)                   # 輪
    d.rectangle([32, 32, 39, 39], fill=gold)                  # 爪（指先の銃口）
    d.rectangle([40, 32, 47, 39], fill=eye)
    return im


def bird_texture():
    im = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 15, 7], fill=(250, 250, 250, 255))     # 体（白）
    d.rectangle([16, 0, 31, 7], fill=(214, 52, 52, 255))      # 翼（赤）
    d.rectangle([0, 8, 7, 15], fill=(255, 196, 64, 255))      # くちばし
    d.rectangle([8, 8, 15, 15], fill=(20, 20, 20, 255))       # 目
    return im


def egg_texture():
    im = Image.new("RGBA", (16, 16), (252, 246, 232, 255))
    d = ImageDraw.Draw(im)
    for x, y in ((3, 4), (10, 7), (6, 11), (12, 2)):
        d.point((x, y), fill=(214, 52, 52, 255))
    return im


def doll_texture():
    """人形: 明るい灰色（色は描画で七色に染める）"""
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 15, 7], fill=(235, 235, 240, 255))     # 頭
    d.rectangle([4, 3, 5, 4], fill=(30, 30, 40, 255)); d.rectangle([10, 3, 11, 4], fill=(30, 30, 40, 255))
    d.rectangle([16, 0, 31, 7], fill=(200, 205, 215, 255))    # 鎧
    d.rectangle([0, 8, 15, 15], fill=(170, 175, 190, 255))    # 手足
    d.rectangle([16, 8, 31, 15], fill=(90, 95, 110, 255))     # ミサイルポッド
    d.rectangle([16, 12, 31, 13], fill=(240, 60, 60, 255))
    return im


def missile_texture():
    im = Image.new("RGBA", (16, 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 7, 7], fill=(230, 230, 236, 255))
    d.rectangle([8, 0, 15, 7], fill=(230, 64, 64, 255))
    return im


def bomb_texture():
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 7, 7], fill=(40, 40, 46, 255))
    d.rectangle([8, 0, 15, 7], fill=(255, 40, 40, 255))
    d.rectangle([0, 8, 7, 15], fill=(240, 200, 60, 255))
    return im


def nail_texture():
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 7, 7], fill=(255, 226, 120, 255))
    d.rectangle([8, 0, 15, 7], fill=(255, 250, 220, 255))
    d.rectangle([0, 8, 15, 15], fill=(255, 190, 60, 160))
    return im


def entity_textures():
    return {"fuuka_fang": fang_texture(), "fuuka_bird": bird_texture(), "fuuka_egg": egg_texture(),
            "fuuka_doll": doll_texture(), "fuuka_missile": missile_texture(), "fuuka_bomb": bomb_texture(),
            "fuuka_nail": nail_texture(), "fuuka_empty": Image.new("RGBA", (16, 16))}


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
        "description": {"identifier": "fuuka:" + ident,
                        "basic_render_parameters": {"material": material, "texture": TEX + tex}},
        "components": c}}


def sphere(r, direction="outwards", surface=True, offset=(0, 0, 0)):
    return {"minecraft:emitter_shape_sphere": {"radius": r, "surface_only": surface,
                                               "direction": direction if isinstance(direction, str) else list(direction),
                                               "offset": list(offset)}}


def disc(r, direction=(0, 1, 0), surface=False, offset=(0, 0, 0)):
    return {"minecraft:emitter_shape_disc": {"radius": r, "plane_normal": "y", "surface_only": surface,
                                             "direction": direction if isinstance(direction, str) else list(direction),
                                             "offset": list(offset)}}


def box(half, direction=(0, 1, 0), offset=(0, 0, 0)):
    return {"minecraft:emitter_shape_box": {"half_dimensions": list(half), "direction": list(direction),
                                            "offset": list(offset)}}


COLORS = {"white": (1, 1, 1), "red": (1.0, 0.18, 0.16), "crimson": (0.85, 0.08, 0.15), "gold": (1.0, 0.82, 0.35),
          "cyan": (0.45, 0.9, 1.0), "blue": (0.35, 0.6, 1.0), "pink": (1.0, 0.6, 0.75), "silver": (0.86, 0.9, 0.98),
          "orange": (1.0, 0.55, 0.15), "gray": (0.6, 0.6, 0.64)}
FIRE = {"interpolant": "v.particle_age / v.particle_lifetime",
        "gradient": {"0.00": "#FFFFF0A0", "0.33": "#FFFF8A20", "0.66": "#FFC02008", "1.00": "#00400000"}}
RAINBOW = ["math.clamp(math.abs(math.mod(v.particle_random_1 * 6, 6) - 3) - 1, 0, 1)",
           "math.clamp(2 - math.abs(math.mod(v.particle_random_1 * 6, 6) - 2), 0, 1)",
           "math.clamp(2 - math.abs(math.mod(v.particle_random_1 * 6, 6) - 4), 0, 1)", FADE]


def rgba(name, alpha=FADE):
    r, g, b = COLORS[name]
    return [r, g, b, alpha]


def build_particles():
    P = {}

    def add(name, **kw):
        P[name] = particle(name, **kw)

    # --- 狙撃
    add("laser", tex="fuuka_glow", count=1, lifetime="0.11", size="0.07", color=rgba("red", 0.9))
    add("laser_lock", tex="fuuka_glow", count=1, lifetime="0.11",
        size="0.09 + math.abs(math.sin(q.life_time * 2000)) * 0.04", color=[1, 0.55, 0.55, 1])
    add("tracer", tex="fuuka_glow", count=1, lifetime="0.18", size="0.14 * (" + FADE + ") + 0.04", color=[1, 0.95, 0.7, 1])
    add("scope_glint", tex="fuuka_star", count=1, lifetime="0.35", size="0.5 * (" + FADE + ") + 0.1",
        spin={"rotation": "0", "rotation_rate": "300"}, color=[1, 1, 1, 1])
    add("reticle", tex="fuuka_reticle", count=1, lifetime="0.12", size="0.9", color=rgba("red", 0.85))
    add("muzzle", tex="fuuka_star", count=8, shape=sphere(0.05), lifetime="0.1", speed=3, size="0.3 * (" + FADE + ")",
        color=FIRE)
    add("gunsmoke", tex="fuuka_glow", material="particles_blend", count=6, shape=sphere(0.1), lifetime="0.9",
        speed="math.random(0.3, 1.0)", accel=(0, 0.8, 0), drag=1.5, size="0.12 + v.particle_age * 0.5",
        color=[0.75, 0.75, 0.78, "0.55 * (" + FADE + ")"])
    add("hit_spark", tex="fuuka_star", count=12, shape=sphere(0.1), lifetime="math.random(0.2, 0.35)",
        speed="math.random(3, 7)", accel=(0, -10, 0), drag=2, size="0.1 * (" + FADE + ")", color=rgba("orange", 1))
    add("charge_red", tex="fuuka_glow", rate=(80, 100), active=0.5, shape=sphere(2.5, "inwards"), lifetime="0.45",
        speed=5, size="0.07 + v.particle_age / v.particle_lifetime * 0.1",
        color=rgba("red", "v.particle_age / v.particle_lifetime"))
    # --- 羽・回避
    for col, rgb in (("feather", "white"), ("feather_red", "red")):
        add(col, tex="fuuka_feather", material="particles_alpha", count=1, lifetime="1.4", speed=0.4,
            accel=(0, -0.6, 0), drag=1.2, size=["0.12", "0.24"],
            spin={"rotation": "math.random(0, 360)", "rotation_rate": "math.random(-120, 120)"},
            color=rgba(rgb, "1 - math.pow(v.particle_age / v.particle_lifetime, 3)"))
    add("feather_burst", tex="fuuka_feather", material="particles_alpha", count=16, shape=sphere(0.4),
        lifetime="math.random(0.9, 1.5)", speed="math.random(1.5, 3.5)", accel=(0, -1.2, 0), drag=2.2,
        size=["0.12", "0.24"], spin={"rotation": "math.random(0, 360)", "rotation_rate": "math.random(-200, 200)"},
        color=["1", "v.particle_random_1 > 0.5 ? 1 : 0.3", "v.particle_random_1 > 0.5 ? 1 : 0.28",
               "1 - math.pow(v.particle_age / v.particle_lifetime, 3)"])
    add("afterimage", tex="fuuka_glow", count=1, lifetime="0.35", size=["0.5", "1.0"], facing="lookat_y",
        color=rgba("crimson", "0.55 * (" + FADE + ")"))
    # --- 水流（オルカブースター）
    add("water_jet", tex="fuuka_glow", count=14, shape=sphere(0.12, (0, -1, 0)), lifetime="math.random(0.2, 0.35)",
        speed="math.random(4, 8)", drag=1, size="0.1 + v.particle_age * 0.3", color=rgba("cyan", 0.8))
    add("splash", tex="fuuka_glow", material="particles_blend", count=20, shape=sphere(0.3, (0, 1, 0)),
        lifetime="math.random(0.4, 0.7)", speed="math.random(2, 5)", accel=(0, -12, 0), size="0.09",
        color=[0.55, 0.85, 1.0, "0.85 * (" + FADE + ")"])
    add("water_blade", tex="fuuka_slash", count=1, lifetime="0.22", size="2.6 + v.particle_age / v.particle_lifetime * 1.5",
        spin={"rotation": "math.random(-20, 20)"}, color=rgba("cyan"))
    add("water_trail", tex="fuuka_glow", count=2, shape=sphere(0.15), lifetime="0.4", speed=0.5, accel=(0, -4, 0),
        size="0.1", color=rgba("cyan", 0.7))
    # --- 爆発・警告
    add("warn", tex="fuuka_ring", count=1, lifetime="0.45", facing="emitter_transform_xz",
        size="2.2 - v.particle_age / v.particle_lifetime * 1.5",
        color=rgba("red", "0.4 + 0.6 * math.abs(math.sin(v.particle_age * 900))"))
    add("explosion", tex="fuuka_glow", count=28, shape=sphere(0.4), lifetime="math.random(0.4, 0.7)",
        speed="math.random(3, 8)", drag=4, size="0.35 + v.particle_age * 0.8", color=FIRE)
    add("shockwave", tex="fuuka_ring", count=1, lifetime="0.5", facing="emitter_transform_xz",
        size="0.5 + v.particle_age / v.particle_lifetime * 7", color=rgba("orange"))
    add("smoke_bomb", tex="fuuka_glow", material="particles_blend", count=36, shape=sphere(0.8),
        lifetime="math.random(1.0, 1.8)", speed="math.random(1, 3)", drag=2, size="0.6 + v.particle_age * 0.7",
        color=[0.92, 0.92, 0.95, "0.8 * (" + FADE + ")"])
    add("egg_boom", tex="fuuka_star", count=14, shape=sphere(0.2), lifetime="0.35", speed=5, drag=3,
        size="0.2 * (" + FADE + ")", color=[1, 0.95, 0.7, 1])
    add("missile_trail", tex="fuuka_glow", material="particles_blend", count=2, shape=sphere(0.05), lifetime="0.6",
        speed=0.3, size="0.08 + v.particle_age * 0.25", color=RAINBOW)
    add("rainbow", tex="fuuka_star", count=10, shape=sphere(0.4), lifetime="0.6", speed=1.5, drag=2,
        size="0.12 * (" + FADE + ")", color=["math.clamp(math.abs(math.mod(v.particle_random_1 * 6, 6) - 3) - 1, 0, 1)",
                                                 "math.clamp(2 - math.abs(math.mod(v.particle_random_1 * 6, 6) - 2), 0, 1)",
                                                 "math.clamp(2 - math.abs(math.mod(v.particle_random_1 * 6, 6) - 4), 0, 1)",
                                                 1])
    add("stun", tex="fuuka_star", count=12, shape=sphere(0.5), lifetime="0.18", speed=6, size="0.12",
        color=rgba("cyan", 1))
    # --- 霧（雲散霧消）
    add("fog_cloud", tex="fuuka_glow", material="particles_blend", count=10, shape=sphere(3.0, "outwards", False),
        lifetime="math.random(2.0, 3.0)", speed=0.3, size="2.0 + v.particle_age * 0.4",
        color=[0.85, 0.78, 0.8, "0.35 * math.sin(v.particle_age / v.particle_lifetime * 180)"])
    # --- 花鳥風月
    add("petal", tex="fuuka_petal", material="particles_alpha", count=24, shape=sphere(1.2), lifetime="1.8", speed=1.2,
        accel=(0, -0.8, 0), drag=1, size="0.14",
        spin={"rotation": "math.random(0, 360)", "rotation_rate": "math.random(-180, 180)"}, color=rgba("pink"))
    add("moon", tex="fuuka_moon", count=1, lifetime="1.4", size="2.5 * math.min(v.particle_age * 4, 1)",
        color=rgba("silver", "0.9 * (" + FADE + ")"))
    add("wind", tex="fuuka_glow", count=20, shape=sphere(2.0), lifetime="0.5", speed=9, size=["0.04", "0.5"],
        facing="lookat_y", color=rgba("white", 0.6))
    # --- スタンド「牙」・無限の回転
    add("stand_aura", tex="fuuka_star", count=3, shape=sphere(0.6), lifetime="0.8", speed=0.3, accel=(0, 0.8, 0),
        size="0.1 * (" + FADE + ")", color=rgba("gold", 1))
    add("nail_trail", tex="fuuka_glow", count=2, lifetime="0.25", size="0.16 * (" + FADE + ")", color=rgba("gold", 1))
    add("nail4_trail", tex="fuuka_spiral", count=1, lifetime="0.5", size="1.1 + v.particle_age * 0.8",
        spin={"rotation": "math.random(0, 360)", "rotation_rate": "720"}, color=rgba("gold"))
    add("spin", tex="fuuka_glow", count=6, lifetime="0.9", size="0.13",
        parametric=["math.cos(v.particle_age * 900 + v.particle_random_1 * 360) * 0.7",
                    "v.particle_age * 2.0",
                    "math.sin(v.particle_age * 900 + v.particle_random_1 * 360) * 0.7"], color=rgba("gold", 1))
    add("spin_hole", tex="fuuka_spiral", count=1, lifetime="0.3", size="0.9",
        spin={"rotation": "q.life_time * 900", "rotation_rate": "1400"}, color=[1, 0.85, 0.4, 1])
    add("act4_charge", tex="fuuka_spiral", count=1, lifetime="0.5",
        size="2.2 * (1 - v.particle_age / v.particle_lifetime) + 0.3",
        spin={"rotation": "0", "rotation_rate": "900"}, color=rgba("gold"))
    # --- 共通（足元・着弾・軌跡）
    add("step_dust", tex="fuuka_glow", material="particles_blend", count=3, shape=disc(0.15, "outwards"),
        lifetime="0.5", speed=0.7, drag=2, size="0.12 + v.particle_age * 0.3",
        color=[0.62, 0.6, 0.62, "0.45 * (" + FADE + ")"])
    add("debris", tex="fuuka_chip", material="particles_alpha", count=18, shape=sphere(0.3, (0, 1, 0)),
        lifetime="math.random(0.6, 1.0)", speed="math.random(3, 7)", accel=(0, -16, 0), drag=0.5,
        size="0.05 + v.particle_random_1 * 0.07",
        spin={"rotation": "math.random(0, 360)", "rotation_rate": "math.random(-500, 500)"},
        color=["0.35 + v.particle_random_2 * 0.2", "0.3 + v.particle_random_2 * 0.15",
               "0.25 + v.particle_random_2 * 0.1", 1.0])
    add("dust_ring", tex="fuuka_glow", material="particles_blend", count=26, shape=disc(0.6, "outwards", True),
        lifetime="0.7", speed=5, drag=5, size="0.25 + v.particle_age * 0.8",
        color=[0.62, 0.6, 0.62, "0.55 * (" + FADE + ")"])
    add("arc", tex="fuuka_glow", rate=(260, 60), active=0.16, lifetime="0.22", size="0.09 * (" + FADE + ") + 0.02",
        color=["1", "0.3 + (1 - v.particle_age / v.particle_lifetime) * 0.5", "0.3", FADE])
    return P


def build_fogs():
    return {
        "fuuka_fog": {"format_version": "1.16.100", "minecraft:fog_settings": {
            "description": {"identifier": "fuuka:fog"},
            "distance": {"air": {"fog_start": 1, "fog_end": 14, "fog_color": "#c9b8bd", "render_distance_type": "fixed"}}}},
    }
