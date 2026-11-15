"""Contact sheet of sprites from the built SFF (decoded back), for visual checks."""
import sys, os
from PIL import Image, ImageDraw
import numpy as np
from mugenfmt import read_sff2

def render(spr, pal):
    a = np.frombuffer(spr.pixels, dtype=np.uint8).reshape(spr.height, spr.width)
    p = np.array(pal, dtype=np.uint8)
    rgb = p[a]
    alpha = (a != 0).astype(np.uint8) * 255
    return Image.fromarray(np.dstack([rgb, alpha]), 'RGBA')

def sheet(path, keys, out, palno=1, cell=(260, 300), cols=8, bg=(120, 140, 160)):
    sprs, pals = read_sff2(path)
    pal = dict(pals)[(1, palno)]
    keys = [k for k in keys if k in sprs]
    rows = (len(keys) + cols - 1) // cols
    W, H = cell
    im = Image.new('RGBA', (cols * W, rows * H), bg + (255,))
    d = ImageDraw.Draw(im)
    for n, k in enumerate(keys):
        s = sprs[k]
        cx, cy = (n % cols) * W + W // 2, (n // cols) * H + H - 30
        im.alpha_composite(render(s, pal), (int(cx - s.axisx), int(cy - s.axisy)))
        d.line((cx - 8, cy, cx + 8, cy), fill=(255, 0, 0, 255))
        d.text(((n % cols) * W + 4, (n // cols) * H + 4), f'{k[0]},{k[1]}', fill=(255, 255, 0, 255))
    im.save(out)

if __name__ == '__main__':
    path = sys.argv[1]; out = sys.argv[2]; palno = int(sys.argv[3])
    keys = [tuple(map(int, k.split(','))) for k in sys.argv[4:]]
    sheet(path, keys, out, palno)
