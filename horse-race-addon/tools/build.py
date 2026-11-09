"""Build the distributable files into dist/.

  dist/HorseRace_v<ver>.mcaddon                 behavior + resource pack (any world)
  dist/HorseRace_DesertWorld_v<ver>.mctemplate  flat desert world template with both packs

Usage: python3 tools/build.py
"""
import json
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKS = os.path.join(ROOT, "packs")
DIST = os.path.join(ROOT, "dist")
TEMPLATE = os.path.join(ROOT, "template")

BP_DIR = "HorseRace_BP"
RP_DIR = "HorseRace_RP"

TEMPLATE_HEADER_UUID = "6e508a8c-83bb-49e8-a720-e9459684cbbe"
TEMPLATE_MODULE_UUID = "4a13f7a2-9358-4244-afc9-6f8c4cd130de"

SKIP_SUFFIXES = (".d.ts",)


def pack_files(src):
    for base, _dirs, files in os.walk(src):
        for f in sorted(files):
            if f.endswith(SKIP_SUFFIXES):
                continue
            full = os.path.join(base, f)
            yield full, os.path.relpath(full, src).replace(os.sep, "/")


def add_pack(z, src, prefix):
    for full, rel in pack_files(src):
        z.write(full, f"{prefix}/{rel}")


def manifest(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    os.makedirs(DIST, exist_ok=True)
    bp = manifest(os.path.join(PACKS, "behavior", "manifest.json"))
    rp = manifest(os.path.join(PACKS, "resource", "manifest.json"))
    version = bp["header"]["version"]
    ver = ".".join(map(str, version))

    addon = os.path.join(DIST, f"HorseRace_v{ver}.mcaddon")
    with zipfile.ZipFile(addon, "w", zipfile.ZIP_DEFLATED) as z:
        add_pack(z, os.path.join(PACKS, "behavior"), BP_DIR)
        add_pack(z, os.path.join(PACKS, "resource"), RP_DIR)
    print("wrote", addon)

    tpl = os.path.join(DIST, f"HorseRace_DesertWorld_v{ver}.mctemplate")
    tpl_manifest = {
        "format_version": 2,
        "header": {
            "name": "大陸横断ホースレース（砂漠ワールド）",
            "description": "砂漠とメサの平坦な乾燥地帯で遊ぶ、チェックポイント制の馬バトルレース。デモ版",
            "uuid": TEMPLATE_HEADER_UUID,
            "version": version,
            "lock_template_options": False,
            "base_game_version": [1, 21, 100],
        },
        "modules": [{"type": "world_template", "uuid": TEMPLATE_MODULE_UUID, "version": version}],
    }
    with zipfile.ZipFile(tpl, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(tpl_manifest, ensure_ascii=False, indent=2))
        z.write(os.path.join(TEMPLATE, "level.dat"), "level.dat")
        z.writestr("levelname.txt", "大陸横断ホースレース")
        z.write(os.path.join(TEMPLATE, "world_icon.jpeg"), "world_icon.jpeg")
        z.writestr(
            "world_behavior_packs.json",
            json.dumps([{"pack_id": bp["header"]["uuid"], "version": bp["header"]["version"]}], indent=2),
        )
        z.writestr(
            "world_resource_packs.json",
            json.dumps([{"pack_id": rp["header"]["uuid"], "version": rp["header"]["version"]}], indent=2),
        )
        add_pack(z, os.path.join(PACKS, "behavior"), f"behavior_packs/{BP_DIR}")
        add_pack(z, os.path.join(PACKS, "resource"), f"resource_packs/{RP_DIR}")
    print("wrote", tpl)


if __name__ == "__main__":
    main()
