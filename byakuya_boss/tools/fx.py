# -*- coding: utf-8 -*-
"""オリジナルパーティクルとそのテクスチャを生成する."""
import math

from PIL import Image

TEX_DIR = "textures/particle/"


# ---------------------------------------------------------------------------
# テクスチャ（すべて PIL で描画）
# ---------------------------------------------------------------------------
def _img(w, h, fn):
    im = Image.new("RGBA", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = fn((x + 0.5) / w, (y + 0.5) / h)
    return im


def _clamp(v):
    return max(0, min(255, int(v)))


def tex_glow(u, v):
    d = math.hypot(u - 0.5, v - 0.5) * 2
    a = max(0.0, 1 - d) ** 2
    return (255, 255, 255, _clamp(a * 255))


def tex_spark(u, v):
    dx, dy = abs(u - 0.5) * 2, abs(v - 0.5) * 2
    d = math.hypot(dx, dy)
    core = max(0.0, 1 - d * 2.5) ** 2
    cross = max(0.0, 1 - dx * 12) * max(0.0, 1 - dy) + max(0.0, 1 - dy * 12) * max(0.0, 1 - dx)
    return (255, 255, 255, _clamp(min(1, core + cross * 0.9) * 255))


def tex_ring(u, v):
    d = math.hypot(u - 0.5, v - 0.5) * 2
    a = math.exp(-((d - 0.85) / 0.07) ** 2) + 0.25 * math.exp(-((d - 0.7) / 0.12) ** 2)
    return (255, 255, 255, _clamp(min(1, a) * 255))


def tex_slash(u, v):
    # 三日月形の斬撃。外側ほど明るく、両端はすぼまる
    x, y = u - 0.5, v - 0.5
    r_out = math.hypot(x, y + 0.05) / 0.47
    r_in = math.hypot(x, y - 0.13) / 0.42
    if r_out > 1 or r_in < 1 or y > 0.18:
        return (255, 255, 255, 0)
    edge = 1 - min(1, (1 - r_out) * 4)
    ang = abs(math.atan2(x, -(y + 0.05))) / math.pi  # 0=上端, 1=下
    taper = max(0.0, 1 - ang * 1.6)
    a = (0.35 + 0.65 * edge) * taper
    return (255, 255, 255, _clamp(a * 255))


def tex_blade(u, v):
    # 上向きの刀。刃(0-0.68) / 鍔(0.68-0.74) / 柄(0.74-1)
    x = abs(u - 0.5) * 2
    if v < 0.68:
        width = 0.55 if v > 0.08 else 0.55 * (v / 0.08)
        if x > width:
            return (0, 0, 0, 0)
        if x > width * 0.6:
            return (255, 255, 255, 255)  # 刃文
        shade = 170 + int(60 * (1 - x))
        return (shade, shade, min(255, shade + 20), 255)
    if v < 0.74:
        return (120, 95, 40, 255) if x < 1.0 else (0, 0, 0, 0)
    if x > 0.5:
        return (0, 0, 0, 0)
    stripe = int(v * 40) % 2
    return (110, 20, 20, 255) if stripe else (30, 10, 10, 255)


def tex_hex(u, v):
    x, y = abs(u - 0.5) * 2, abs(v - 0.5) * 2
    d = max(x * 0.866 + y * 0.5, y)
    if d > 0.95:
        return (0, 0, 0, 0)
    if d > 0.8:
        return (230, 255, 255, 255)
    return (160, 230, 255, 70)


def tex_petal(u, v):
    # 桜の花びら（上が広く切れ込み、下がすぼまる）
    x = abs(u - 0.5)
    width = 0.46 * math.sin(math.pi * min(1.0, v * 0.85 + 0.12)) ** 0.7 * (1.1 - v * 0.5)
    notch = v < 0.25 and x < (0.25 - v) * 0.6
    if x > width or notch or v < 0.06:
        return (0, 0, 0, 0)
    t = min(1.0, x / max(width, 1e-3))
    return (255, _clamp(175 + 50 * t), _clamp(195 + 40 * t), 255)


TEXTURES = {
    "byakuya_glow": (64, 64, tex_glow),
    "byakuya_spark": (32, 32, tex_spark),
    "byakuya_ring": (128, 128, tex_ring),
    "byakuya_slash": (128, 128, tex_slash),
    "byakuya_blade": (16, 64, tex_blade),
    "byakuya_hex": (32, 32, tex_hex),
    "byakuya_petal": (16, 16, tex_petal),
}


def build_textures():
    return {name: _img(w, h, fn) for name, (w, h, fn) in TEXTURES.items()}


# ---------------------------------------------------------------------------
# パーティクル
# ---------------------------------------------------------------------------
FADE = "1 - v.particle_age / v.particle_lifetime"
UV = {"texture_width": 1, "texture_height": 1, "uv": [0, 0], "uv_size": [1, 1]}
UV_FLIP = {"texture_width": 1, "texture_height": 1, "uv": [0, 1], "uv_size": [1, -1]}


def _gradient(*stops):
    n = len(stops) - 1
    return {"interpolant": "v.particle_age / v.particle_lifetime",
            "gradient": {"%.2f" % (i / n): s for i, s in enumerate(stops)}}


def particle(ident, tex, material="particles_add", *, count=None, rate=None, active=0.1,
             shape=None, lifetime="0.5", speed=None, accel=(0, 0, 0), drag=0.0,
             size="0.2", facing="lookat_xyz", color=None, spin=None, parametric=None,
             uv=UV, local=False):
    c = {}
    if local:
        c["minecraft:emitter_local_space"] = {"position": True, "rotation": True}
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
        c["minecraft:particle_motion_dynamic"] = {"linear_acceleration": list(accel),
                                                  "linear_drag_coefficient": drag}
    if isinstance(size, str):
        size = [size, size]
    c["minecraft:particle_appearance_billboard"] = {"size": size, "facing_camera_mode": facing, "uv": uv}
    if color is not None:
        c["minecraft:particle_appearance_tinting"] = {"color": color}
    return {"format_version": "1.10.0", "particle_effect": {
        "description": {"identifier": "byakuya:" + ident,
                        "basic_render_parameters": {"material": material, "texture": TEX_DIR + tex}},
        "components": c}}


def sphere(r, direction="outwards", surface=True, offset=(0, 0, 0)):
    return {"minecraft:emitter_shape_sphere": {"radius": r, "surface_only": surface,
                                               "direction": direction, "offset": list(offset)}}


def disc(r, direction=(0, 1, 0), surface=False, offset=(0, 0, 0)):
    return {"minecraft:emitter_shape_disc": {"radius": r, "plane_normal": "y", "surface_only": surface,
                                             "direction": list(direction) if not isinstance(direction, str) else direction,
                                             "offset": list(offset)}}


def box(half, direction=(0, 1, 0), offset=(0, 0, 0)):
    return {"minecraft:emitter_shape_box": {"half_dimensions": list(half), "direction": list(direction),
                                            "offset": list(offset)}}


COLORS = {  # 名前: (r, g, b)
    "white": (1.0, 0.97, 0.9),
    "red": (1.0, 0.18, 0.12),
    "yellow": (1.0, 0.9, 0.3),
    "blue": (0.3, 0.6, 1.0),
    "green": (0.35, 1.0, 0.4),
    "purple": (0.7, 0.25, 1.0),
    "cyan": (0.5, 0.95, 1.0),
}


def rgba(name, alpha=FADE):
    r, g, b = COLORS[name]
    return [r, g, b, alpha]


def build_particles():
    P = {}

    # 衝撃波（地面に広がるリング）
    for col in COLORS:
        P["shockwave_" + col] = particle(
            "shockwave_" + col, "byakuya_ring", count=1, lifetime="0.55",
            size="0.5 + v.particle_age / v.particle_lifetime * 7", facing="emitter_transform_xz",
            color=rgba(col))
        P["shockwave_big_" + col] = particle(
            "shockwave_big_" + col, "byakuya_ring", count=1, lifetime="0.9",
            size="1 + v.particle_age / v.particle_lifetime * 18", facing="emitter_transform_xz",
            color=rgba(col))
        # 予兆（足元で縮むリング）
        P["warn_" + col] = particle(
            "warn_" + col, "byakuya_ring", count=1, lifetime="0.6",
            size="1.8 - v.particle_age / v.particle_lifetime * 1.3", facing="emitter_transform_xz",
            color=rgba(col, "0.4 + 0.6 * math.abs(math.sin(v.particle_age * 900))"))
        # 斬撃（カメラを向く三日月、ランダム角度）
        P["slash_" + col] = particle(
            "slash_" + col, "byakuya_slash", count=1, lifetime="0.25",
            size="1.4 + v.particle_age / v.particle_lifetime * 1.0",
            spin={"rotation": "math.random(0, 360)"}, color=rgba(col))
        # 横薙ぎ（地面と平行な三日月）
        P["slash_flat_" + col] = particle(
            "slash_flat_" + col, "byakuya_slash", count=1, lifetime="0.3",
            size="2.4 + v.particle_age / v.particle_lifetime * 1.2", facing="emitter_transform_xz",
            spin={"rotation": "math.random(0, 360)"}, color=rgba(col))
        # 大斬撃
        P["big_slash_" + col] = particle(
            "big_slash_" + col, "byakuya_slash", count=1, lifetime="0.6",
            size="7 + v.particle_age / v.particle_lifetime * 4",
            spin={"rotation": "math.random(-30, 30)"}, color=rgba(col))
        # 収束（力を溜める）
        P["charge_" + col] = particle(
            "charge_" + col, "byakuya_glow", rate=(90, 120), active=0.8, shape=sphere(4, "inwards"),
            lifetime="0.5", speed=7, size="0.08 + v.particle_age / v.particle_lifetime * 0.12",
            color=rgba(col, "v.particle_age / v.particle_lifetime"))

    # 火花（命中）
    P["spark_burst"] = particle("spark_burst", "byakuya_spark", count=18, shape=sphere(0.2),
                                lifetime="math.random(0.25, 0.4)", speed="math.random(4, 9)", drag=5,
                                size="0.18 * (" + FADE + ")", color=rgba("white", 1))
    # 火の粉
    P["ember_burst"] = particle("ember_burst", "byakuya_glow", count=45, shape=sphere(0.4),
                                lifetime="math.random(0.6, 1.1)", speed="math.random(3, 9)",
                                accel=(0, 3, 0), drag=2.5, size="0.22 * (" + FADE + ")",
                                color=_gradient("#FFFFF0A0", "#FFFF7020", "#FFC01808", "#00400000"))
    # 炎の柱
    P["fire_pillar"] = particle("fire_pillar", "byakuya_glow", rate=(140, 200), active=0.9, shape=disc(0.8),
                                lifetime="math.random(0.4, 0.8)", speed="math.random(4, 9)", drag=0.5,
                                size="0.35 * (" + FADE + ")",
                                color=_gradient("#FFFFF0A0", "#FFFF7020", "#FFC01808", "#00400000"))
    P["aura_flame"] = particle("aura_flame", "byakuya_glow", rate=(25, 20), active=0.4, shape=disc(0.45),
                               lifetime="math.random(0.4, 0.8)", speed="math.random(1, 2)",
                               size="0.18 * (" + FADE + ")",
                               color=_gradient("#FFFFD060", "#FFFF5010", "#00400000"))
    P["aura_soul"] = particle("aura_soul", "byakuya_glow", rate=(30, 25), active=0.3, shape=disc(0.5),
                              lifetime="math.random(0.5, 0.9)", speed="math.random(1, 3)",
                              size="0.2 * (" + FADE + ")",
                              color=_gradient("#FFFFFFFF", "#FF60E0FF", "#00104060"))
    # 水
    P["water_pillar"] = particle("water_pillar", "byakuya_glow", "particles_blend", rate=(120, 160), active=0.8,
                                 shape=disc(0.9), lifetime="math.random(0.4, 0.8)",
                                 speed="math.random(5, 9)", accel=(0, -9, 0),
                                 size="0.25 * (" + FADE + ")",
                                 color=_gradient("#FFE0F4FF", "#FF4090FF", "#00103080"))
    P["water_burst"] = particle("water_burst", "byakuya_glow", "particles_blend", count=50,
                                shape=disc(0.6, "outwards"), lifetime="math.random(0.5, 0.9)",
                                speed="math.random(3, 8)", accel=(0, -14, 0),
                                size="0.22 * (" + FADE + ")",
                                color=_gradient("#FFE0F4FF", "#FF4090FF", "#00103080"))
    P["water_spiral"] = particle(
        "water_spiral", "byakuya_glow", rate=(60, 80), active=0.5, lifetime="1.0", size="0.15 * (" + FADE + ")",
        parametric=["math.cos(v.particle_age * 600 + v.particle_random_1 * 360) * 1.2",
                    "v.particle_age * 2.5",
                    "math.sin(v.particle_age * 600 + v.particle_random_1 * 360) * 1.2"],
        color=rgba("blue"))
    # 樹海
    P["leaf_swirl"] = particle(
        "leaf_swirl", "byakuya_glow", rate=(70, 90), active=1.4, lifetime="1.2", size="0.16 * (" + FADE + ")",
        parametric=["math.cos(v.particle_age * 450 + v.particle_random_1 * 360) * (3 - v.particle_age * 2)",
                    "v.particle_age * 1.5 + v.particle_random_2",
                    "math.sin(v.particle_age * 450 + v.particle_random_1 * 360) * (3 - v.particle_age * 2)"],
        color=rgba("green"))
    P["leaf_burst"] = particle("leaf_burst", "byakuya_glow", count=25, shape=sphere(0.3),
                               lifetime="0.7", speed="math.random(2, 6)", drag=3, accel=(0, -2, 0),
                               size="0.15 * (" + FADE + ")", color=rgba("green"))
    # 刀（地面から突き出る / 降ってくる）
    P["ground_blade"] = particle("ground_blade", "byakuya_blade", "particles_alpha", count=7,
                                 shape=disc(1.0, (0, 1, 0), offset=(0, -0.8, 0)),
                                 lifetime="0.7", speed=10, drag=12, size=["0.22", "0.9"], facing="lookat_y")
    P["blade_rain"] = particle("blade_rain", "byakuya_blade", "particles_alpha", count=4,
                               shape=box((1.2, 0.2, 1.2), (0, -1, 0)), lifetime="0.38", speed=26,
                               size=["0.18", "0.75"], facing="lookat_y", uv=UV_FLIP)
    P["blade_halo"] = particle(
        "blade_halo", "byakuya_blade", "particles_alpha", count=12, lifetime="0.6", size=["0.15", "0.6"],
        facing="lookat_y", uv=UV_FLIP,
        parametric=["math.cos(v.particle_random_1 * 360 + v.particle_age * 200) * 1.6", "0",
                    "math.sin(v.particle_random_1 * 360 + v.particle_age * 200) * 1.6"])
    # ホッパー（反射板）
    P["hopper_panel"] = particle("hopper_panel", "byakuya_hex", "particles_blend", count=16,
                                 shape=sphere(1.5, (0, 0, 0)), lifetime="0.45",
                                 size="0.45", color=[0.8, 1.0, 1.0, "0.9 * (" + FADE + ")"])
    # 鋼糸
    P["wire"] = particle("wire", "byakuya_glow", count=1, lifetime="0.9",
                         size="0.07", color=[0.9, 0.95, 1.0, "0.3 + 0.7 * math.abs(math.sin(v.particle_age * 720))"])
    # 残像（瞬間移動）
    P["afterimage"] = particle("afterimage", "byakuya_glow", "particles_blend", count=40,
                               shape=box((0.3, 0.9, 0.3), (0, 1, 0)), lifetime="math.random(0.5, 0.9)",
                               speed="math.random(0.1, 0.6)", size="0.4 * (" + FADE + ")",
                               color=[0.12, 0.05, 0.12, "0.8 * (" + FADE + ")"])
    # 武器が砕ける欠片
    P["shatter"] = particle("shatter", "byakuya_spark", "particles_blend", count=20, shape=sphere(0.3),
                            lifetime="0.8", speed="math.random(2, 5)", accel=(0, -12, 0),
                            size="0.12", color=[0.75, 0.75, 0.8, FADE])
    # 剣筋（手元に付く光）
    P["sword_trail"] = particle("sword_trail", "byakuya_glow", count=14, shape=sphere(0.35, surface=False),
                                lifetime="0.3", speed="math.random(0.5, 2)", drag=3,
                                size="0.14 * (" + FADE + ")", color=rgba("white"))
    P["sword_trail_red"] = particle("sword_trail_red", "byakuya_glow", count=14, shape=sphere(0.35, surface=False),
                                    lifetime="0.35", speed="math.random(0.5, 2)", drag=3,
                                    size="0.16 * (" + FADE + ")", color=rgba("red"))
    P["hand_charge"] = particle("hand_charge", "byakuya_glow", count=10, shape=sphere(0.9, "inwards"),
                                lifetime="0.3", speed=3, size="0.07", color=rgba("white", "v.particle_age / v.particle_lifetime"))
    # 桜吹雪
    P["petal_storm"] = particle("petal_storm", "byakuya_petal", "particles_alpha", rate=(40, 200), active=3.0,
                                shape=box((8, 1, 8), (0.3, -1, 0.1), offset=(0, 6, 0)),
                                lifetime="math.random(3, 5)", speed="math.random(0.5, 1.5)",
                                accel=(0.4, -0.6, 0.2), drag=0.6, size="0.09",
                                spin={"rotation": "math.random(0, 360)", "rotation_rate": "math.random(-200, 200)"})
    # 遠当て（ビーム）
    P["beam_seg"] = particle("beam_seg", "byakuya_glow", count=2, shape=sphere(0.15, surface=False),
                             lifetime="0.4", size="0.9 * (" + FADE + ")",
                             color=_gradient("#FFFFFFFF", "#FFFF3020", "#00600000"))
    P["beam_warn"] = particle("beam_warn", "byakuya_glow", count=1, lifetime="0.3",
                              size="0.22", color=[1.0, 0.15, 0.1, "0.5 + 0.5 * math.sin(v.particle_age * 1200)"])
    # 飛ぶ斬撃・追尾刀の軌跡
    P["wave_trail"] = particle("wave_trail", "byakuya_glow", count=6, shape=sphere(0.8, surface=False),
                               lifetime="math.random(0.2, 0.4)", speed=0.3,
                               size="0.2 * (" + FADE + ")",
                               color=_gradient("#FFFFFFFF", "#FFFF4030", "#00600000"))
    P["blade_trail"] = particle("blade_trail", "byakuya_glow", count=3, shape=sphere(0.15, surface=False),
                                lifetime="0.25", size="0.12 * (" + FADE + ")", color=rgba("white"))
    # 影分身のゆらめき
    P["shadow_wisp"] = particle("shadow_wisp", "byakuya_glow", "particles_blend", count=6,
                                shape=box((0.3, 0.9, 0.3), (0, 1, 0)), lifetime="0.7", speed=0.6,
                                size="0.3 * (" + FADE + ")", color=[0.08, 0.02, 0.12, "0.7 * (" + FADE + ")"])
    # 流星刀の着弾
    P["meteor_impact"] = particle("meteor_impact", "byakuya_glow", count=40, shape=disc(0.5, "outwards"),
                                  lifetime="math.random(0.4, 0.8)", speed="math.random(4, 10)",
                                  accel=(0, -10, 0), drag=1.5, size="0.25 * (" + FADE + ")",
                                  color=_gradient("#FFFFFFFF", "#FFFF5030", "#FF801010", "#00300000"))
    # --- v1.3: 地走り（跳んで避ける波紋）・範囲表示・煙管の煙・炎の噴出 ---
    P["ripple_ring"] = particle(
        "ripple_ring", "byakuya_glow", rate=(500, 600), active=1.8,
        shape={"minecraft:emitter_shape_custom": {"offset": [
            "math.cos(v.particle_random_1 * 360) * (1.5 + v.emitter_age * 10)", "0.05",
            "math.sin(v.particle_random_1 * 360) * (1.5 + v.emitter_age * 10)"], "direction": [0, 1, 0]}},
        lifetime="0.18", speed="math.random(1, 3)", size="0.16 * (" + FADE + ") + 0.04",
        color=_gradient("#FFFFFFFF", "#FFFF3020", "#00600000"))
    P["zone_12"] = particle(
        "zone_12", "byakuya_glow", rate=(400, 300), active=0.6,
        shape={"minecraft:emitter_shape_custom": {"offset": [
            "math.cos(v.particle_random_1 * 360) * 12", "0.1", "math.sin(v.particle_random_1 * 360) * 12"]}},
        lifetime="0.6", speed=0.5, size="0.2", color=rgba("red", "0.5 + 0.5 * math.sin(v.particle_age * 900)"))
    P["smoke_puff"] = particle("smoke_puff", "byakuya_glow", "particles_blend", count=4, shape=sphere(0.08),
                               lifetime="math.random(1.0, 1.6)", speed=0.4, accel=(0.1, 0.5, 0), drag=1,
                               size="0.1 + v.particle_age * 0.25",
                               color=[0.85, 0.85, 0.88, "0.45 * (" + FADE + ")"])
    P["fire_jet"] = particle("fire_jet", "byakuya_glow", rate=(70, 40), active=0.45, shape=disc(0.5),
                             lifetime="math.random(0.3, 0.6)", speed="math.random(5, 9)", drag=0.5,
                             size="0.32 * (" + FADE + ")",
                             color=_gradient("#FFFFF0A0", "#FFFF7020", "#FFC01808", "#00400000"))
    P["petal_burst"] = particle("petal_burst", "byakuya_petal", "particles_alpha", count=40, shape=sphere(0.5),
                                lifetime="math.random(1.0, 2.0)", speed="math.random(2, 6)", accel=(0, -1.5, 0),
                                drag=2, size="0.09", spin={"rotation": "math.random(0, 360)",
                                                           "rotation_rate": "math.random(-300, 300)"})
    P["time_stop"] = particle("time_stop", "byakuya_ring", "particles_blend", count=1, lifetime="1.2",
                              facing="emitter_transform_xz", size="12.5",
                              color=[0.7, 0.7, 0.75, "0.35 * (" + FADE + ")"])
    return P


def _slash_wave_tex():
    w = h = 128
    im = Image.new("RGBA", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            a = tex_slash((x + 0.5) / w, (y + 0.5) / h)[3] / 255
            # 外側の縁は白、内側は紅
            r, g, b = 255, _clamp(25 + 230 * a ** 4), _clamp(20 + 235 * a ** 4)
            im.putpixel((x, y), (r, g, b, _clamp(min(1, a * 1.8) * 255)))
    return im


def build_entity_textures():
    return {"byakuya_slash_wave": _slash_wave_tex(), "byakuya_blade": _img(16, 64, tex_blade),
            "byakuya_empty": Image.new("RGBA", (16, 16))}


def build_fogs():
    return {"byakuya_final_fog": {"format_version": "1.16.100", "minecraft:fog_settings": {
        "description": {"identifier": "byakuya:final_fog"},
        "distance": {"air": {"fog_start": 4, "fog_end": 40, "fog_color": "#2a0505",
                             "render_distance_type": "fixed"}}}}}
