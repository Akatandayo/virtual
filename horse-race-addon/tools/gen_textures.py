"""Generate pixel-art textures and pack icons for the horse race add-on.

Usage: python3 tools/gen_textures.py <path-to-merchant-skin.png>
Writes into packs/resource/textures and pack_icon.png of both packs.
"""
import os
import sys
import shutil
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RP = os.path.join(ROOT, "packs", "resource")
BP = os.path.join(ROOT, "packs", "behavior")


def from_map(rows, palette):
    h = len(rows)
    w = len(rows[0])
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(rows):
        assert len(row) == w, (y, row)
        for x, ch in enumerate(row):
            if ch != ".":
                px[x, y] = palette[ch]
    return img


# --- 16x16 item icons -------------------------------------------------------

LEDGER = [
    "................",
    "..kkkkkkkkkkk...",
    ".kBBBBBBBBBBBk..",
    ".kBbbbbbbbbbBkr.",
    ".kBbGGG.GGGbBkr.",
    ".kBbG.....GbBkr.",
    ".kBbG.....GbBkr.",
    ".kBbG.....GbBkr.",
    ".kBbbG...GbbBkr.",
    ".kBbbbbbbbbbBk..",
    ".kBbbbbbbbbbBk..",
    ".kBBBBBBBBBBBk..",
    ".kpppppppppppk..",
    ".kPPPPPPPPPPPk..",
    "..kkkkkkkkkkk...",
    "................",
]
LEDGER_PAL = {
    "k": (40, 22, 12, 255),
    "B": (120, 62, 30, 255),
    "b": (150, 82, 40, 255),
    "G": (255, 205, 60, 255),
    "r": (200, 30, 40, 255),
    "p": (240, 228, 200, 255),
    "P": (210, 196, 160, 255),
}

SPUR = [
    "............gg..",
    "...........gGGg.",
    "............gg..",
    "................",
    ".sss............",
    "sSSSs......y.y..",
    "sS..sss.....Y...",
    "sS....sssss.YyY.",
    "sS........sYYYy.",
    "sS....sssss.YyY.",
    "sS..sss.....Y...",
    "sSSSs......y.y..",
    ".sss............",
    "................",
    "................",
    "................",
]
SPUR_PAL = {
    "s": (90, 90, 100, 255),
    "S": (190, 195, 205, 255),
    "y": (180, 120, 20, 255),
    "Y": (255, 200, 50, 255),
    "g": (20, 110, 40, 255),
    "G": (80, 220, 90, 255),
}
# green up arrow drawn separately (top-right) for clarity
UP_ARROW = [
    "...G...",
    "..GGG..",
    ".GGGGG.",
    "GGGGGGG",
    "..GGG..",
    "..GGG..",
]

REINS = [
    "................",
    "....LLLLLL......",
    "...Ll....lL.....",
    "..Ll......lL....",
    "..L........L....",
    "..L........L....",
    "..Ll......lL....",
    "...Ll....lL.....",
    "....Ll..lL......",
    ".....L..L.......",
    "....oOo.oOo.....",
    "...o...o...o....",
    "...o...o...o....",
    "....oOo.oOo.....",
    "................",
    "................",
]
REINS_PAL = {
    "L": (110, 60, 25, 255),
    "l": (160, 95, 45, 255),
    "o": (120, 120, 130, 255),
    "O": (210, 210, 220, 255),
}
DOWN_ARROW = [
    "..RRR..",
    "..RRR..",
    "RRRRRRR",
    ".RRRRR.",
    "..RRR..",
    "...R...",
]


def paste_map(img, rows, color, ox, oy, outline=(30, 10, 10, 255)):
    px = img.load()
    pts = []
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                pts.append((ox + x, oy + y))
    # outline
    for (x, y) in pts:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < img.width and 0 <= ny < img.height and (nx, ny) not in pts:
                if px[nx, ny][3] == 0:
                    px[nx, ny] = outline
    for (x, y) in pts:
        px[x, y] = color


def make_items(outdir):
    os.makedirs(outdir, exist_ok=True)
    ledger = from_map(LEDGER, LEDGER_PAL)
    ledger.save(os.path.join(outdir, "hrace_race_config.png"))

    spur = from_map(SPUR, SPUR_PAL)
    spur_px = spur.load()
    # clear the placeholder dots at the top and draw the up arrow
    for y in range(0, 4):
        for x in range(9, 16):
            spur_px[x, y] = (0, 0, 0, 0)
    paste_map(spur, UP_ARROW, (80, 230, 90, 255), 9, 0, outline=(10, 60, 20, 255))
    spur.save(os.path.join(outdir, "hrace_spur.png"))

    reins = from_map(REINS, REINS_PAL)
    paste_map(reins, DOWN_ARROW, (235, 60, 60, 255), 9, 9, outline=(70, 10, 10, 255))
    reins.save(os.path.join(outdir, "hrace_reins.png"))


# --- pack icon --------------------------------------------------------------

HORSE = [
    "..........kk......",
    ".........kkkk.....",
    ".........kkk......",
    "...k.....kkk......",
    "..kk....kkkkk.....",
    "..kkk..kkkkkkkk.kk",
    "...kkkkkkkkkkkkkkk",
    "....kkkkkkkkkkkkk.",
    "....kkkkkkkkkkkk..",
    "....kkkkkkkkkkk...",
    "....k.kk...kk.k...",
    "...k..k.....k..k..",
    "..k...k.....k...k.",
]


def make_icon(path, size=128):
    n = 32
    img = Image.new("RGBA", (n, n), (0, 0, 0, 255))
    px = img.load()
    top = (255, 140, 60)
    bot = (255, 220, 140)
    for y in range(n):
        t = y / (n * 0.62)
        t = min(1.0, t)
        c = tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(3))
        for x in range(n):
            px[x, y] = c + (255,)
    # sun
    d = ImageDraw.Draw(img)
    d.ellipse([20, 5, 27, 12], fill=(255, 248, 210, 255))
    # mesa silhouettes
    d.polygon([(0, 18), (3, 13), (11, 13), (13, 18)], fill=(190, 90, 50, 255))
    d.rectangle([3, 15, 11, 15], fill=(220, 150, 90, 255))
    d.polygon([(22, 19), (24, 15), (30, 15), (32, 19)], fill=(175, 80, 45, 255))
    # beacon beam (checkpoint)
    d.rectangle([27, 0, 27, 18], fill=(255, 255, 200, 200))
    # dunes
    for x in range(n):
        import math
        h = 20 + int(1.5 * math.sin(x / 4.0) + 1.0 * math.sin(x / 2.3 + 1))
        for y in range(h, n):
            shade = (232, 200, 130) if y < h + 2 else (214, 178, 108)
            px[x, y] = shade + (255,)
    # horse + rider silhouette
    hx, hy = 7, 10
    for y, row in enumerate(HORSE):
        for x, ch in enumerate(row):
            if ch == "k":
                px[hx + x, hy + y] = (35, 22, 18, 255)
    # rider
    d.rectangle([hx + 7, hy + 1, hx + 8, hy + 5], fill=(35, 22, 18, 255))
    d.rectangle([hx + 7, hy - 1, hx + 8, hy + 0], fill=(35, 22, 18, 255))
    big = img.resize((size, size), Image.NEAREST)
    big.save(path)
    return big


def main():
    skin = sys.argv[1] if len(sys.argv) > 1 else None
    tex = os.path.join(RP, "textures")
    make_items(os.path.join(tex, "items"))
    if skin:
        os.makedirs(os.path.join(tex, "entity"), exist_ok=True)
        im = Image.open(skin).convert("RGBA")
        assert im.size == (64, 64), im.size
        im.save(os.path.join(tex, "entity", "hrace_merchant.png"))
    icon = make_icon(os.path.join(RP, "pack_icon.png"))
    shutil.copy(os.path.join(RP, "pack_icon.png"), os.path.join(BP, "pack_icon.png"))
    # world template icon (jpeg, 16:9-ish)
    wi = Image.new("RGB", (800, 450), (0, 0, 0))
    wi.paste(icon.resize((450, 450), Image.NEAREST).convert("RGB"), (175, 0))
    left = icon.convert("RGB").crop((0, 0, 4, 128)).resize((175, 450))
    right = icon.convert("RGB").crop((124, 0, 128, 128)).resize((175, 450))
    wi.paste(left, (0, 0))
    wi.paste(right, (625, 0))
    os.makedirs(os.path.join(ROOT, "template"), exist_ok=True)
    wi.save(os.path.join(ROOT, "template", "world_icon.jpeg"), quality=90)
    print("textures generated")


if __name__ == "__main__":
    main()
