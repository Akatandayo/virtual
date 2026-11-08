#!/usr/bin/env python3
"""Skin Changer アドオンのビルドスクリプト.

src/skins/*.png を読み込み、ビヘイビアパック (BP) とリソースパック (RP) を生成し、
dist/SkinChanger.mcaddon にまとめます。

    python3 build.py

スキンを追加したいときは src/skins に N.png を置き、下の SKINS に1行足すだけです。
"""
import json
import shutil
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
OUT_BP = ROOT / "SkinChanger_BP"
OUT_RP = ROOT / "SkinChanger_RP"
DIST = ROOT / "dist"

NS = "skin_changer"
PROP = f"{NS}:skin"
VERSION = [1, 0, 0]
MIN_ENGINE = [1, 21, 90]
SERVER_API = "2.0.0"

BP_HEADER_UUID = "5ece3160-6361-430e-b856-c518866eb601"
BP_DATA_UUID = "4d4f3a8e-5c52-46cd-8895-2df8017ab91e"
BP_SCRIPT_UUID = "231a27a2-0450-4af1-a37c-1a6ef773c18a"
RP_HEADER_UUID = "9e21cbbf-8a19-49e9-a7d6-5c838d376733"
RP_MODULE_UUID = "6fbfb375-e5bd-4cad-8c93-7bc4ac2191fc"

# (ファイル名, 日本語名, 英語名, 体型) 体型: "wide" = Steve型 / "slim" = Alex型(細腕)
SKINS = [
    ("1.png", "スキン1", "Skin 1", "wide"),
    ("2.png", "スキン2", "Skin 2", "wide"),
    ("3.png", "スキン3", "Skin 3", "slim"),
    ("4.png", "スキン4", "Skin 4", "slim"),
    ("5.png", "スキン5", "Skin 5", "slim"),
]
GEOMETRY = {"wide": "geometry.humanoid.custom", "slim": "geometry.humanoid.customSlim"}
SKIN_COND = f"query.property('{PROP}')"


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_vanilla(name: str):
    return json.loads((SRC / "vanilla" / name).read_text(encoding="utf-8"))


def head_icon(skin: Image.Image, size: int = 16) -> Image.Image:
    """スキンの顔(正面)+帽子レイヤーからアイコンを作る."""
    s = skin.width // 64
    face = skin.crop((8 * s, 8 * s, 16 * s, 16 * s)).convert("RGBA")
    hat = skin.crop((40 * s, 8 * s, 48 * s, 16 * s)).convert("RGBA")
    face = Image.alpha_composite(face, hat)
    return face.resize((size, size), Image.NEAREST)


def reset_icon() -> Image.Image:
    """「元に戻す」アイテム用の矢印アイコン."""
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((1, 1, 14, 14), fill=(60, 60, 70, 255), outline=(20, 20, 25, 255))
    d.arc((4, 4, 11, 11), 40, 330, fill=(255, 255, 255, 255), width=2)
    d.polygon([(10, 2), (13, 6), (8, 6)], fill=(255, 255, 255, 255))
    return im


# ---------------------------------------------------------------- RP
def build_rp() -> None:
    write_json(OUT_RP / "manifest.json", {
        "format_version": 2,
        "header": {
            "name": "pack.name", "description": "pack.description",
            "uuid": RP_HEADER_UUID, "version": VERSION, "min_engine_version": MIN_ENGINE,
        },
        "modules": [{"type": "resources", "uuid": RP_MODULE_UUID, "version": VERSION}],
        "dependencies": [{"uuid": BP_HEADER_UUID, "version": VERSION}],
    })

    item_textures = {}
    icons = []
    for i, (fname, *_rest) in enumerate(SKINS, start=1):
        skin = Image.open(SRC / "skins" / fname).convert("RGBA")
        dst = OUT_RP / "textures" / "entity" / NS / f"skin_{i}.png"
        dst.parent.mkdir(parents=True, exist_ok=True)
        skin.save(dst)
        icon = head_icon(skin)
        icons.append(icon)
        ipath = OUT_RP / "textures" / "items" / NS / f"skin_{i}.png"
        ipath.parent.mkdir(parents=True, exist_ok=True)
        icon.save(ipath)
        item_textures[f"{NS}_skin_{i}"] = {"textures": f"textures/items/{NS}/skin_{i}"}
    reset_icon().save(OUT_RP / "textures" / "items" / NS / "reset.png")
    item_textures[f"{NS}_reset"] = {"textures": f"textures/items/{NS}/reset"}
    write_json(OUT_RP / "textures" / "item_texture.json", {
        "resource_pack_name": NS, "texture_name": "atlas.items", "texture_data": item_textures,
    })

    # パックアイコン: スキンの顔を並べたもの
    pack_icon = Image.new("RGBA", (128, 128), (40, 40, 48, 255))
    n = len(icons)
    cols = 3 if n > 4 else 2
    cell = 128 // cols
    for k, ic in enumerate(icons[: cols * cols]):
        big = ic.resize((cell - 8, cell - 8), Image.NEAREST)
        pack_icon.alpha_composite(big, ((k % cols) * cell + 4, (k // cols) * cell + 4))
    pack_icon.save(OUT_RP / "pack_icon.png")

    # player.entity.json (バニラをベースに改変)
    ent = load_vanilla("player.entity.json")
    desc = ent["minecraft:client_entity"]["description"]
    for i, (_f, _ja, _en, model) in enumerate(SKINS, start=1):
        desc["textures"][f"{NS}_{i}"] = f"textures/entity/{NS}/skin_{i}"
        desc["geometry"][f"{NS}_{i}"] = GEOMETRY[model]
    new_rcs = []
    for rc in desc["render_controllers"]:
        (name, cond), = rc.items()
        short = name.rsplit(".", 1)[-1]
        if short in ("first_person", "third_person", "map"):
            new_rcs.append({name: f"({cond}) && {SKIN_COND} == 0"})
            new_rcs.append({f"controller.render.{NS}.{short}": f"({cond}) && {SKIN_COND} > 0"})
        else:
            new_rcs.append(rc)
    desc["render_controllers"] = new_rcs
    write_json(OUT_RP / "entity" / "player.entity.json", ent)

    # カスタムスキン用レンダーコントローラー (バニラのものを複製して差し替え)
    vanilla_rc = load_vanilla("player.render_controllers.json")["render_controllers"]
    arrays = {
        "textures": {"Array.skins": [f"Texture.{NS}_{i}" for i in range(1, len(SKINS) + 1)]},
        "geometries": {"Array.models": [f"Geometry.{NS}_{i}" for i in range(1, len(SKINS) + 1)]},
    }
    idx = f"math.clamp({SKIN_COND} - 1, 0, {len(SKINS) - 1})"
    rcs = {}
    for short in ("first_person", "third_person", "map"):
        rc = json.loads(json.dumps(vanilla_rc[f"controller.render.player.{short}"]))
        rc["arrays"] = arrays
        rc["geometry"] = f"Array.models[{idx}]"
        rc["textures"] = [f"Array.skins[{idx}]"]
        rcs[f"controller.render.{NS}.{short}"] = rc
    write_json(OUT_RP / "render_controllers" / f"{NS}.render_controllers.json",
               {"format_version": "1.8.0", "render_controllers": rcs})

    # 言語ファイル
    ja = ["pack.name=スキンチェンジャー RP", "pack.description=アイテムでスキンを切り替えるアドオン"]
    en = ["pack.name=Skin Changer RP", "pack.description=Change your skin with items"]
    for i, (_f, jname, ename, _m) in enumerate(SKINS, start=1):
        ja.append(f"item.{NS}:skin_{i}=スキンチェンジャー: {jname}")
        en.append(f"item.{NS}:skin_{i}=Skin Changer: {ename}")
    ja.append(f"item.{NS}:reset=スキンチェンジャー: 元のスキンに戻す")
    en.append(f"item.{NS}:reset=Skin Changer: Reset to Original")
    write_text(OUT_RP / "texts" / "ja_JP.lang", "\n".join(ja) + "\n")
    write_text(OUT_RP / "texts" / "en_US.lang", "\n".join(en) + "\n")
    write_json(OUT_RP / "texts" / "languages.json", ["ja_JP", "en_US"])


# ---------------------------------------------------------------- BP
def build_bp() -> None:
    write_json(OUT_BP / "manifest.json", {
        "format_version": 2,
        "header": {
            "name": "pack.name", "description": "pack.description",
            "uuid": BP_HEADER_UUID, "version": VERSION, "min_engine_version": MIN_ENGINE,
        },
        "modules": [
            {"type": "data", "uuid": BP_DATA_UUID, "version": VERSION},
            {"type": "script", "language": "javascript", "uuid": BP_SCRIPT_UUID,
             "version": VERSION, "entry": "scripts/main.js"},
        ],
        "dependencies": [
            {"uuid": RP_HEADER_UUID, "version": VERSION},
            {"module_name": "@minecraft/server", "version": SERVER_API},
        ],
    })
    shutil.copy(OUT_RP / "pack_icon.png", OUT_BP / "pack_icon.png")

    # player.json: バニラにスキン番号のプロパティを追加 (0 = 元のスキン)
    player = load_vanilla("player.json")
    player["minecraft:entity"]["description"]["properties"] = {
        PROP: {"type": "int", "range": [0, len(SKINS)], "default": 0, "client_sync": True},
    }
    write_json(OUT_BP / "entities" / "player.json", player)

    def item(ident: str, icon: str) -> dict:
        return {
            "format_version": "1.21.60",
            "minecraft:item": {
                "description": {"identifier": f"{NS}:{ident}",
                                "menu_category": {"category": "items"}},
                "components": {
                    "minecraft:icon": icon,
                    "minecraft:max_stack_size": 1,
                    "minecraft:hand_equipped": False,
                },
            },
        }

    for i in range(1, len(SKINS) + 1):
        write_json(OUT_BP / "items" / f"skin_{i}.json", item(f"skin_{i}", f"{NS}_skin_{i}"))
    write_json(OUT_BP / "items" / "reset.json", item("reset", f"{NS}_reset"))

    skin_map = {f"{NS}:skin_{i}": i for i in range(1, len(SKINS) + 1)}
    skin_map[f"{NS}:reset"] = 0
    names = {i: s[1] for i, s in enumerate(SKINS, start=1)}
    names[0] = "元のスキン"
    script = f"""import {{ world, system }} from "@minecraft/server";

// アイテムID -> スキン番号 (0 = 元のスキン)
const SKIN_ITEMS = {json.dumps(skin_map, ensure_ascii=False, indent=2)};
const SKIN_NAMES = {json.dumps({str(k): v for k, v in names.items()}, ensure_ascii=False, indent=2)};
const PROPERTY = "{PROP}";

// 連打防止 (プレイヤーごとに 10 tick = 0.5秒)
const lastUse = new Map();

world.afterEvents.itemUse.subscribe((ev) => {{
  const player = ev.source;
  const skin = SKIN_ITEMS[ev.itemStack.typeId];
  if (skin === undefined) return;

  const now = system.currentTick;
  if (now - (lastUse.get(player.id) ?? -100) < 10) return;
  lastUse.set(player.id, now);

  if (player.getProperty(PROPERTY) === skin) {{
    player.onScreenDisplay.setActionBar(`§eすでに「${{SKIN_NAMES[skin]}}」です`);
    return;
  }}
  player.setProperty(PROPERTY, skin);
  player.onScreenDisplay.setActionBar(`§aスキンを「${{SKIN_NAMES[skin]}}」に変更しました!`);
  player.playSound("random.orb", {{ pitch: 1.2 }});
  player.dimension.spawnParticle("minecraft:villager_happy", {{
    x: player.location.x,
    y: player.location.y + 1,
    z: player.location.z,
  }});
}});

world.afterEvents.playerLeave.subscribe((ev) => lastUse.delete(ev.playerId));
"""
    write_text(OUT_BP / "scripts" / "main.js", script)

    write_text(OUT_BP / "texts" / "ja_JP.lang",
               "pack.name=スキンチェンジャー BP\npack.description=アイテムでスキンを切り替えるアドオン\n")
    write_text(OUT_BP / "texts" / "en_US.lang",
               "pack.name=Skin Changer BP\npack.description=Change your skin with items\n")
    write_json(OUT_BP / "texts" / "languages.json", ["ja_JP", "en_US"])


def package() -> None:
    DIST.mkdir(exist_ok=True)
    out = DIST / "SkinChanger.mcaddon"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for pack in (OUT_BP, OUT_RP):
            for f in sorted(pack.rglob("*")):
                if f.is_file():
                    z.write(f, f"{pack.name}/{f.relative_to(pack).as_posix()}")
    print(f"built {out.relative_to(ROOT)}")


if __name__ == "__main__":
    for d in (OUT_BP, OUT_RP):
        if d.exists():
            shutil.rmtree(d)
    build_rp()
    build_bp()
    package()
