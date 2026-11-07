# -*- coding: utf-8 -*-
"""ボスが呼び出す補助エンティティ（斬撃波・追尾刀・目印・影分身）."""

BOSS_ID = "byakuya:shiraishi_byakuya"
BOSS = "@e[type=%s,c=1]" % BOSS_ID
TICK = 0.05

# 斬撃波の向き（最寄りプレイヤーからのずれ・度）
AIM_ANGLES = sorted({-30, -20, -10, 0, 10, 20, 30} | set(range(0, 360, 15)))


def aim_event(deg):
    return "byakuya:aim_%s" % (("m%d" % -deg) if deg < 0 else str(deg))


def _fx_base(ident, family, hitbox=0.2):
    return {
        "minecraft:type_family": {"family": family},
        "minecraft:health": {"value": 1, "max": 1},
        "minecraft:collision_box": {"width": hitbox, "height": hitbox},
        "minecraft:physics": {"has_gravity": False, "has_collision": False},
        "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
        "minecraft:damage_sensor": {"triggers": [{"cause": "all", "deal_damage": False}]},
        "minecraft:knockback_resistance": {"value": 1.0},
        "minecraft:body_rotation_blocked": {},
        "minecraft:fire_immune": {},
        "minecraft:conditional_bandwidth_optimization": {"default_values": {
            "max_optimized_distance": 0, "max_dropped_ticks": 0, "use_motion_prediction_hints": True}},
    }


def _entity(ident, components, groups, events, animations, animate):
    return {"format_version": "1.21.0", "minecraft:entity": {
        "description": {"identifier": ident, "is_spawnable": False, "is_summonable": True,
                        "is_experimental": False,
                        "animations": animations, "scripts": {"animate": animate}},
        "component_groups": groups, "components": components, "events": events}}


DESPAWN_GROUP = {"despawn": {"minecraft:instant_despawn": {}}}
DESPAWN_EVENT = {"byakuya:despawn": {"add": {"component_groups": ["despawn"]}}}


def ticks(length, cmds_fn, end=None):
    """length 秒の間、毎 tick cmds_fn(i) を実行するタイムライン"""
    tl = {}
    n = int(round(length / TICK))
    for i in range(n):
        tl["%.2f" % (i * TICK)] = cmds_fn(i)
    if end:
        tl.setdefault("%.2f" % ((n - 1) * TICK), []).extend(end)
    return tl


def hit(r, dmg, cause="entity_attack", despawn=False):
    sel = "@a[r=%.1f,m=!creative]" % r
    out = ["/execute if entity %s run damage %s %d %s entity %s" % (sel, sel, dmg, cause, BOSS)]
    if despawn:
        out.append("/execute if entity %s run particle byakuya:spark_burst ~ ~ ~" % sel)
        out.append("/execute if entity %s run event entity @s byakuya:despawn" % sel)
    return out


# ---------------------------------------------------------------------------
# BP
# ---------------------------------------------------------------------------
def bp_slash_wave():
    events = dict(DESPAWN_EVENT)
    for deg in AIM_ANGLES:
        events[aim_event(deg)] = {"queue_command": {"command": [
            "tp @s ~ ~ ~ facing @p[m=!creative]",
            "tp @s ~ ~ ~ ~%d ~" % deg,
        ]}}
    anim = {"animation_length": 1.65, "loop": False, "timeline": ticks(
        1.6, lambda i: ["/tp @s ^ ^ ^0.9"] + hit(2.0, 9),
        end=["@s byakuya:despawn"])}
    return _entity("byakuya:slash_wave", _fx_base("slash_wave", ["byakuya_fx", "inanimate"]),
                   dict(DESPAWN_GROUP), events,
                   {"fly": "animation.byakuya.slash_wave.fly"}, ["fly"]), \
        {"animation.byakuya.slash_wave.fly": anim}


def bp_homing_blade():
    hover = {"animation_length": 0.6, "loop": False, "timeline": ticks(
        0.6, lambda i: ["/tp @s ~ ~ ~ facing @p[m=!creative]"])}
    home = {"animation_length": 0.9, "loop": False, "timeline": ticks(
        0.9, lambda i: ["/execute at @s facing entity @p[m=!creative] feet positioned ^ ^ ^0.5 "
                        "run tp @s ~ ~ ~ facing @p[m=!creative]"] + hit(1.8, 7, despawn=True))}
    fly = {"animation_length": 1.25, "loop": False, "timeline": ticks(
        1.2, lambda i: ["/tp @s ^ ^ ^0.6"] + hit(1.8, 7, despawn=True), end=["@s byakuya:despawn"])}
    ctrl = {"initial_state": "hover", "states": {
        "hover": {"animations": ["hover"], "transitions": [{"home": "q.all_animations_finished"}]},
        "home": {"animations": ["home"], "transitions": [{"fly": "q.all_animations_finished"}],
                 "on_entry": ["/playsound item.trident.throw @a[r=30] ~ ~ ~ 0.6 1.4"]},
        "fly": {"animations": ["fly"]},
    }}
    ent = _entity("byakuya:homing_blade", _fx_base("homing_blade", ["byakuya_fx", "inanimate"]),
                  dict(DESPAWN_GROUP), dict(DESPAWN_EVENT),
                  {"hover": "animation.byakuya.blade.hover", "home": "animation.byakuya.blade.home",
                   "fly": "animation.byakuya.blade.fly", "ctrl": "controller.animation.byakuya.blade"}, ["ctrl"])
    return ent, {"animation.byakuya.blade.hover": hover, "animation.byakuya.blade.home": home,
                 "animation.byakuya.blade.fly": fly}, {"controller.animation.byakuya.blade": ctrl}


MARKER_KINDS = ["aim_mark", "meteor_a", "meteor_b", "meteor_c"]


def bp_marker():
    groups = dict(DESPAWN_GROUP)
    events = dict(DESPAWN_EVENT)
    for k in MARKER_KINDS:
        groups[k] = {"minecraft:type_family": {"family": ["byakuya_marker", k, "inanimate"]}}
        events["byakuya:as_" + k] = {"add": {"component_groups": [k]}}
    life = {"animation_length": 4.05, "loop": False, "timeline": {"4.00": ["@s byakuya:despawn"]}}
    return _entity("byakuya:marker", _fx_base("marker", ["byakuya_marker", "inanimate"], 0.1),
                   groups, events, {"life": "animation.byakuya.marker.life"}, ["life"]), \
        {"animation.byakuya.marker.life": life}


def bp_shadow():
    comps = {
        "minecraft:type_family": {"family": ["byakuya", "byakuya_shadow", "monster", "mob"]},
        "minecraft:health": {"value": 40, "max": 40},
        "minecraft:nameable": {"always_show": False, "allow_name_tag_renaming": False},
        "minecraft:collision_box": {"width": 0.6, "height": 1.8},
        "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
        "minecraft:knockback_resistance": {"value": 0.5},
        "minecraft:fire_immune": {},
        "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0, "breathes_water": True},
        "minecraft:jump.static": {},
        "minecraft:movement.basic": {},
        "minecraft:movement": {"value": 0.37},
        "minecraft:navigation.walk": {"can_path_over_water": True, "avoid_damage_blocks": True},
        "minecraft:follow_range": {"value": 40, "max": 40},
        "minecraft:attack": {"damage": 8},
        "minecraft:damage_sensor": {"triggers": [
            {"cause": "fall", "deal_damage": False},
            {"on_damage": {"filters": {"test": "is_family", "subject": "other", "value": "byakuya"}},
             "deal_damage": False}]},
        "minecraft:equipment": {"table": "loot_tables/entities/shiraishi_byakuya_equipment.json",
                                "slot_drop_chance": [{"slot": "slot.weapon.mainhand", "drop_chance": 0}]},
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.melee_attack": {"priority": 2, "speed_multiplier": 1.4, "track_target": True},
        "minecraft:behavior.nearest_attackable_target": {
            "priority": 1, "must_see": False, "within_radius": 40,
            "entity_types": [{"filters": {"test": "is_family", "subject": "other", "value": "player"},
                              "max_dist": 40}]},
        "minecraft:behavior.random_stroll": {"priority": 6},
        "minecraft:timer": {"looping": False, "time": 15,
                            "time_down_event": {"event": "byakuya:despawn", "target": "self"}},
    }
    events = {
        "minecraft:entity_spawned": {"queue_command": {"command": [
            "particle byakuya:afterimage ~ ~0.9 ~", "playsound mob.endermen.portal @a[r=30] ~ ~ ~ 0.8 0.5"]}},
        "byakuya:despawn": {"add": {"component_groups": ["despawn"]},
                            "queue_command": {"command": ["particle byakuya:afterimage ~ ~0.9 ~"]}},
    }
    return {"format_version": "1.21.0", "minecraft:entity": {
        "description": {"identifier": "byakuya:shadow", "is_spawnable": False, "is_summonable": True,
                        "is_experimental": False},
        "component_groups": dict(DESPAWN_GROUP), "components": comps, "events": events}}


# ---------------------------------------------------------------------------
# RP
# ---------------------------------------------------------------------------
def geo_slash_wave():
    face = {"uv": [0, 0], "uv_size": [128, 128]}
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": "geometry.byakuya_slash_wave", "texture_width": 128, "texture_height": 128,
                        "visible_bounds_width": 4, "visible_bounds_height": 4, "visible_bounds_offset": [0, 1, 0]},
        "bones": [{"name": "wave", "pivot": [0, 16, 0], "rotation": [0, 0, 20],
                   "locators": {"center": [0, 16, 0]},
                   "cubes": [{"origin": [-24, 16, -24], "size": [48, 0, 48],
                              "uv": {"up": face, "down": {"uv": [0, 128], "uv_size": [128, -128]}}}]}]}]}


def geo_blade():
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": "geometry.byakuya_blade", "texture_width": 16, "texture_height": 64,
                        "visible_bounds_width": 3, "visible_bounds_height": 3, "visible_bounds_offset": [0, 0.5, 0]},
        "bones": [
            {"name": "roll", "pivot": [0, 8, 0], "locators": {"center": [0, 8, 0]}},
            {"name": "blade", "parent": "roll", "pivot": [0, 8, 0], "rotation": [90, 0, 0], "cubes": [
                {"origin": [-2, 0, 0], "size": [4, 16, 0],
                 "uv": {"north": {"uv": [0, 0], "uv_size": [16, 64]}, "south": {"uv": [0, 0], "uv_size": [16, 64]}}},
                {"origin": [0, 0, -2], "size": [0, 16, 4],
                 "uv": {"east": {"uv": [0, 0], "uv_size": [16, 64]}, "west": {"uv": [0, 0], "uv_size": [16, 64]}}},
            ]},
        ]}]}


def geo_empty():
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": "geometry.byakuya_empty", "texture_width": 16, "texture_height": 16},
        "bones": [{"name": "root", "pivot": [0, 0, 0]}]}]}


def rc_simple():
    return {"format_version": "1.10.0", "render_controllers": {
        "controller.render.byakuya_simple": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}],
            "textures": ["Texture.default"]},
        "controller.render.byakuya_shadow": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}],
            "textures": ["Texture.default"],
            "overlay_color": {"r": "0.08", "g": "0.0", "b": "0.15",
                              "a": "0.72 + math.sin(q.life_time * 300) * 0.08"}},
    }}


def client(ident, tex, geo, material, animations=None, animate=None, particles=None, rc="controller.render.byakuya_simple",
           extra=None):
    d = {"identifier": ident, "materials": {"default": material},
         "textures": {"default": "textures/entity/" + tex},
         "geometry": {"default": geo}, "render_controllers": [rc]}
    if particles:
        d["particle_effects"] = particles
    if animations:
        d["animations"] = animations
        d["scripts"] = {"animate": animate}
    if extra:
        d.update(extra)
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": d}}


def rp_animations():
    return {
        "animation.byakuya.wave_fx": {"loop": True, "animation_length": 0.1,
                                      "bones": {"wave": {"scale": "1 + math.sin(q.life_time * 1440) * 0.08"}},
                                      "particle_effects": {"0.00": [{"effect": "trail", "locator": "center"}]}},
        "animation.byakuya.blade_fx": {"loop": True, "animation_length": 0.1,
                                       "bones": {"roll": {"rotation": [0, 0, "q.life_time * 720"]}},
                                       "particle_effects": {"0.00": [{"effect": "trail", "locator": "center"}]}},
        "animation.byakuya.shadow_fx": {"loop": True, "animation_length": 0.5,
                                        "particle_effects": {"0.00": [{"effect": "wisp", "locator": "body_center"}]}},
    }


def rp_clients(boss_animation_names):
    return {
        "slash_wave": client("byakuya:slash_wave", "byakuya_slash_wave", "geometry.byakuya_slash_wave",
                             "entity_alphablend", {"fx": "animation.byakuya.wave_fx"}, ["fx"],
                             {"trail": "byakuya:wave_trail"}),
        "homing_blade": client("byakuya:homing_blade", "byakuya_blade", "geometry.byakuya_blade",
                               "entity_alphatest", {"fx": "animation.byakuya.blade_fx"}, ["fx"],
                               {"trail": "byakuya:blade_trail"}),
        "marker": client("byakuya:marker", "byakuya_empty", "geometry.byakuya_empty", "entity_alphatest"),
        "shadow": client("byakuya:shadow", "shiraishi_byakuya", "geometry.shiraishi_byakuya", "entity_alphatest",
                         dict(boss_animation_names, shadow_fx="animation.byakuya.shadow_fx"),
                         ["main", "attack_fx", "shadow_fx"],
                         {"wisp": "byakuya:shadow_wisp", "sword_trail": "byakuya:sword_trail"},
                         rc="controller.render.byakuya_shadow", extra={"enable_attachables": True}),
    }
