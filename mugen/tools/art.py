"""Sprite generation for Denshi Doku (電子 独).

All character frames are derived from the original illustration
(mugen/source/denshi_doku.png): the body is kept intact, the scarf tails are
separated and animated with a wave warp, and attack / glitch frames add
procedurally drawn scarf ribbons, glitch slices and chromatic offsets.

Work happens on a large "source scale" canvas, then everything is
downscaled by SCALE to the character's localcoord (640x480).
"""
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageChops

SCALE = 0.5            # source pixels -> localcoord 640x480 pixels
CW, CH = 1100, 900     # working canvas (source scale)
GX, GY = 550, 700      # ground axis on the canvas
SRC_AXIS = (255, 540)  # ground axis on the (unmirrored) source image: hover gap below feet

# ------------------------------------------------------------- palette ---
# index 0 is transparent in MUGEN
GRAY0, NGRAY = 1, 64          # 1..64  gray ramp black->white
CYAN0, MAG0, RED0, GRN0, BLU0 = 65, 81, 97, 113, 129  # 16-step accent ramps
NACC = 16


def _ramp(c_dark, c_light, n):
    return [tuple(int(round(c_dark[k] + (c_light[k] - c_dark[k]) * i / (n - 1))) for k in range(3))
            for i in range(n)]


ACCENTS = [
    _ramp((0, 40, 60), (170, 255, 255), NACC),     # cyan
    _ramp((60, 0, 50), (255, 160, 240), NACC),     # magenta
    _ramp((60, 0, 0), (255, 140, 140), NACC),      # red
    _ramp((0, 40, 10), (170, 255, 170), NACC),     # terminal green
    _ramp((0, 0, 70), (120, 150, 255), NACC),      # BSOD blue
]


def make_palette(keys=None):
    """keys: four colors for luminance 0 / .22 / .60 / 1.0 (hair, sweater, scarf, skin).
    None = the original monochrome look."""
    pal = [(0, 0, 0)]
    for i in range(NGRAY):
        L = i / (NGRAY - 1)
        if keys is None:
            v = int(round(L * 255))
            pal.append((v, v, v))
        else:
            stops = [0.0, 0.22, 0.60, 1.0]
            for j in range(3):
                if L <= stops[j + 1]:
                    t = (L - stops[j]) / (stops[j + 1] - stops[j])
                    a, b = keys[j], keys[j + 1]
                    pal.append(tuple(int(round(a[k] + (b[k] - a[k]) * t)) for k in range(3)))
                    break
    for r in ACCENTS:
        pal.extend(r)
    while len(pal) < 256:
        pal.append((0, 0, 0))
    return pal


PALETTES = [
    None,                                                              # 1 original
    [(235, 235, 235), (190, 190, 190), (90, 90, 90), (20, 20, 25)],    # 2 negative
    [(10, 20, 80), (30, 60, 170), (225, 230, 255), (255, 255, 255)],   # 3 blue screen
    [(0, 30, 5), (0, 90, 35), (70, 255, 120), (215, 255, 215)],        # 4 terminal
    [(25, 0, 5), (95, 10, 25), (225, 45, 65), (255, 238, 238)],        # 5 crimson
    [(35, 10, 55), (105, 45, 145), (40, 225, 225), (255, 228, 250)],   # 6 vapor
]

_BASE_PAL = np.array(make_palette()[1:GRN0 + NACC + 0] + make_palette()[BLU0:BLU0 + NACC], dtype=np.int32)
_BASE_IDX = np.array(list(range(1, GRN0 + NACC)) + list(range(BLU0, BLU0 + NACC)), dtype=np.uint8)


def quantize(rgba: Image.Image):
    """RGBA -> (palette index bytes). Alpha < 128 becomes index 0."""
    a = np.asarray(rgba, dtype=np.int32)
    h, w = a.shape[:2]
    rgb = a[..., :3].reshape(-1, 3)
    alpha = a[..., 3].reshape(-1)
    out = np.zeros(h * w, dtype=np.uint8)
    m = alpha >= 128
    if m.any():
        px = rgb[m]
        # gray pixels map directly onto the ramp (fast + exact)
        isgray = (np.abs(px[:, 0] - px[:, 1]) < 6) & (np.abs(px[:, 1] - px[:, 2]) < 6)
        res = np.zeros(len(px), dtype=np.uint8)
        g = px[isgray].mean(axis=1)
        res[isgray] = (GRAY0 + np.round(g / 255 * (NGRAY - 1))).astype(np.uint8)
        col = px[~isgray]
        if len(col):
            d = ((col[:, None, :] - _BASE_PAL[None, :, :]) ** 2).sum(axis=2)
            res[~isgray] = _BASE_IDX[d.argmin(axis=1)]
        out[m] = res
    return out.tobytes(), w, h


# ------------------------------------------------------- source layers ---

class Source:
    def __init__(self, path):
        im = Image.open(path).convert('RGBA')
        a = np.asarray(im).astype(np.int32)
        self.orig = a
        rgb = a[..., :3].mean(axis=2)
        alpha = a[..., 3]
        opaque = alpha > 100
        H, W = alpha.shape
        yy, xx = np.mgrid[0:H, 0:W]
        scarf = opaque & (np.abs(rgb - 154) < 22)
        dark = opaque & (rgb < 120) & ~(np.abs(rgb - 56) < 14)

        def dilate(m, r):
            out = m.copy()
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if dx * dx + dy * dy <= r * r:
                        out |= np.roll(np.roll(m, dy, 0), dx, 1)
            return out

        near = dilate(scarf, 5)
        # big tail (unmirrored right side) and small tail (unmirrored left tip)
        big = (scarf | (dark & near)) & (xx >= 343)
        small = (scarf | (dark & near)) & (xx <= 152) & (yy <= 395)
        # include antialiased fringe pixels around tails
        anyalpha = alpha > 40          # ignore the near-invisible noise in the source background
        sweater_zone = (np.abs(rgb - 56) < 14) & (xx < 362)
        fringe = anyalpha & ~scarf & dilate(big | small, 3) & ~sweater_zone
        big |= fringe & (xx >= 343)
        small |= fringe & (xx <= 152) & (yy <= 400)
        self.big_mask, self.small_mask = big, small
        self.body_mask = anyalpha & ~big & ~small
        self.core_mask = opaque & self.body_mask & ~scarf & ~dilate(scarf, 3)
        # anchors (unmirrored source)
        self.big_x0, self.big_x1 = 345, 548
        self.small_x0, self.small_x1 = 152, 55

    def layer(self, mask):
        a = self.orig.copy()
        a[..., 3] = np.where(mask, a[..., 3], 0)
        return a

    def tails(self, phase, amp_big=14.0, amp_small=8.0, stretch=0.0):
        """Return RGBA array (source size) of both tails warped by a travelling wave."""
        H, W = self.big_mask.shape
        out = np.zeros((H, W, 4), dtype=np.int32)
        for mask, x0, x1, amp, kdir in ((self.big_mask, self.big_x0, self.big_x1, amp_big, 1),
                                        (self.small_mask, self.small_x0, self.small_x1, amp_small, -1)):
            lay = self.layer(mask)
            L = abs(x1 - x0)
            for x in range(W):
                t = (x - x0) * kdir / L
                if t <= 0:
                    dy = 0
                else:
                    t = min(t, 1.15)
                    dy = int(round(amp * (t ** 1.4) * math.sin(phase - 2 * math.pi * t * 0.9)
                                   + stretch * t * 18))
                col = lay[:, x, :]
                if dy == 0:
                    shifted = col
                elif dy > 0:
                    shifted = np.zeros_like(col)
                    shifted[dy:] = col[:-dy]
                else:
                    shifted = np.zeros_like(col)
                    shifted[:dy] = col[-dy:]
                m = shifted[:, 3] > 0
                out[m, x, :] = shifted[m]
        return out

    def body(self):
        return self.layer(self.body_mask)


def to_canvas(arr):
    """Place an (unmirrored) source-size RGBA array on the working canvas, mirrored to face right."""
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGBA').transpose(Image.FLIP_LEFT_RIGHT)
    W = im.size[0]
    mx = W - 1 - SRC_AXIS[0]
    canvas = Image.new('RGBA', (CW, CH), (0, 0, 0, 0))
    canvas.alpha_composite(im, (GX - mx, GY - SRC_AXIS[1]))
    return canvas


def src_to_canvas(x, y, W=600):
    """Unmirrored source coordinate -> canvas coordinate."""
    mx = W - 1 - SRC_AXIS[0]
    return (GX - mx + (W - 1 - x), GY - SRC_AXIS[1] + y)


NECK = src_to_canvas(292, 207)        # scarf knot under the chin
FEET = src_to_canvas(150, 470)        # front foot
HIP = src_to_canvas(250, 330)
CENTER = src_to_canvas(255, 300)      # rotation pivot (torso)

# --------------------------------------------------------------- ribbon ---


RIBBON_WIDTH = 1.7   # scarf ribbons match the thickness of the drawn scarf


def bezier(pts, n=40):
    out = []
    for i in range(n + 1):
        t = i / n
        p = list(pts)
        while len(p) > 1:
            p = [((1 - t) * a[0] + t * b[0], (1 - t) * a[1] + t * b[1]) for a, b in zip(p, p[1:])]
        out.append(p[0])
    return out


def draw_ribbon(img, ctrl, w0=26, w1=16, tear=True, fill=(154, 154, 154, 255), seed=0):
    """Scarf ribbon along a bezier through ctrl points (canvas coords). Returns its bbox."""
    pts = bezier(ctrl)
    w0, w1 = w0 * RIBBON_WIDTH, w1 * RIBBON_WIDTH
    left, right = [], []
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, n - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        l = math.hypot(dx, dy) or 1
        nx, ny = -dy / l, dx / l
        t = i / (n - 1)
        w = (w0 * (1 - t) + w1 * t) / 2
        w *= 1 + 0.12 * math.sin(t * 9 + seed)
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    rnd = random.Random(seed)
    tip = []
    if tear:
        ex, ey = pts[-1]
        a = pts[-2]
        dx, dy = ex - a[0], ey - a[1]
        l = math.hypot(dx, dy) or 1
        ux, uy = dx / l, dy / l
        L, R = left[-1], right[-1]
        for k in range(1, 5):
            t = k / 5
            px = L[0] + (R[0] - L[0]) * t
            py = L[1] + (R[1] - L[1]) * t
            ext = rnd.uniform(4, 16) * (1 if k % 2 else -0.3)
            tip.append((px + ux * ext, py + uy * ext))
    poly = left + tip + right[::-1]
    d = ImageDraw.Draw(img)
    d.polygon(poly, fill=fill, outline=(0, 0, 0, 255), width=4)
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return (min(xs), min(ys), max(xs), max(ys))


def pixel_noise(img, box, density=0.5, seed=0, cell=10, colors=None):
    """Fill box with a field of glitch blocks."""
    rnd = random.Random(seed)
    colors = colors or [(0, 0, 0, 255), (255, 255, 255, 255), (154, 154, 154, 255),
                        (60, 230, 240, 255), (240, 80, 220, 255)]
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = [int(v) for v in box]
    for y in range(y0, y1, cell):
        for x in range(x0, x1, cell):
            if rnd.random() < density:
                w = cell * rnd.choice((1, 1, 2, 3))
                d.rectangle((x, y, min(x + w, x1) - 1, y + cell - 1), fill=rnd.choice(colors))


# --------------------------------------------------------------- poses ---

class Frame:
    def __init__(self, img, hurt, hit, axis):
        self.img, self.hurt, self.hit, self.axis = img, hurt, hit, axis


def _bbox(im, robust=False):
    a = np.asarray(im)[..., 3]
    ys, xs = np.where(a > 100)
    if len(xs) == 0:
        return None
    if robust:
        return (np.percentile(xs, 1.5), np.percentile(ys, 0.5), np.percentile(xs, 98.5), np.percentile(ys, 99.5))
    return (xs.min(), ys.min(), xs.max(), ys.max())


def transform(img, angle=0.0, pivot=CENTER, sx=1.0, sy=1.0, dx=0, dy=0):
    """Rotate (deg, counter-clockwise) around pivot, scale around the ground axis, then translate."""
    if angle:
        img = img.rotate(angle, resample=Image.BICUBIC, center=pivot)
    if sx != 1.0 or sy != 1.0:
        # affine inverse mapping, scale about (GX, GY)
        img = img.transform(img.size, Image.AFFINE,
                            (1 / sx, 0, GX - GX / sx, 0, 1 / sy, GY - GY / sy), resample=Image.BICUBIC)
    if dx or dy:
        img = ImageChops.offset(img, int(dx), int(dy))
    return img


def glitch_slices(img, amount, seed, invert_bands=0):
    """Horizontal band displacement (the signature glitch)."""
    if amount <= 0:
        return img
    rnd = random.Random(seed)
    a = np.asarray(img).copy()
    H = a.shape[0]
    bb = _bbox(img)
    if bb is None:
        return img
    y = bb[1]
    while y < bb[3]:
        h = rnd.randint(6, 34)
        if rnd.random() < 0.45:
            sh = int(rnd.uniform(-amount, amount))
            a[y:y + h] = np.roll(a[y:y + h], sh, axis=1)
            if invert_bands and rnd.random() < 0.25 * invert_bands:
                band = a[y:y + h]
                m = band[..., 3] > 0
                band[..., :3][m] = 255 - band[..., :3][m]
        y += h
    return Image.fromarray(a, 'RGBA')


def chroma(img, off, strength=1.0):
    """Cyan / magenta ghost silhouettes behind the image."""
    if off == 0:
        return img
    a = np.asarray(img)
    sil = a[..., 3] > 100
    base = Image.new('RGBA', img.size, (0, 0, 0, 0))
    for color, sh in (((60, 230, 240), -off), ((240, 80, 220), off)):
        g = np.zeros_like(a)
        g[..., 0], g[..., 1], g[..., 2] = color
        g[..., 3] = np.where(np.roll(sil, sh, axis=1), int(255 * strength), 0)
        base.alpha_composite(Image.fromarray(g, 'RGBA'))
    base.alpha_composite(img)
    return base


def dissolve(img, keep, seed):
    """Horizontal scanline dissolve: keep fraction of lines (teleport)."""
    rnd = random.Random(seed)
    a = np.asarray(img).copy()
    H = a.shape[0]
    for y in range(0, H, 4):
        if rnd.random() > keep:
            a[y:y + 4, :, 3] = 0
        else:
            a[y:y + 4] = np.roll(a[y:y + 4], int(rnd.uniform(-40, 40) * (1 - keep)), axis=1)
    return Image.fromarray(a, 'RGBA')


class Poser:
    def __init__(self, src_path):
        self.src = Source(src_path)
        self._body = to_canvas(self.src.body())
        self._core = to_canvas(self.src.layer(self.src.core_mask))
        self._tail_cache = {}

    def tails(self, phase, amp_big=14.0, amp_small=8.0, stretch=0.0):
        key = (round(phase, 3), amp_big, amp_small, stretch)
        if key not in self._tail_cache:
            self._tail_cache[key] = to_canvas(self.src.tails(phase, amp_big, amp_small, stretch))
        return self._tail_cache[key]

    def pose(self, phase=0.0, amp=1.0, stretch=0.0, angle=0.0, sx=1.0, sy=1.0, dx=0, dy=0,
             ribbons=(), ribbons_back=(), glitch=0, glitch_seed=0, invert_bands=0, chroma_off=0,
             keep=1.0, noise=None, hurt=True, extra_hit=None, pivot=None, tails=True):
        """Compose a frame. ribbons: list of (ctrl_points, w0, w1) in *unrotated* canvas coords,
        attached relative to NECK. Returns Frame with final-scale image, hurt/hit boxes (axis-relative)."""
        layer = Image.new('RGBA', (CW, CH), (0, 0, 0, 0))
        hitlayer = Image.new('RGBA', (CW, CH), (0, 0, 0, 0))
        for i, (ctrl, w0, w1) in enumerate(ribbons_back):
            draw_ribbon(layer, [(NECK[0] + x, NECK[1] + y) for x, y in ctrl], w0, w1, seed=i + 7)
        if tails:
            layer.alpha_composite(self.tails(phase, 14 * amp, 8 * amp, stretch))
        layer.alpha_composite(self._body)
        bodyonly = self._core
        for i, (ctrl, w0, w1) in enumerate(ribbons):
            pts = [(NECK[0] + x, NECK[1] + y) for x, y in ctrl]
            draw_ribbon(layer, pts, w0, w1, seed=i + 1)
            draw_ribbon(hitlayer, pts[1:] if len(pts) > 2 else pts, w0, w1, seed=i + 1)
        pv = pivot or CENTER
        layer = transform(layer, angle, pv, sx, sy, dx, dy)
        bodyonly = transform(bodyonly, angle, pv, sx, sy, dx, dy)
        hitlayer = transform(hitlayer, angle, pv, sx, sy, dx, dy)
        if noise:
            box, dens, seed = noise
            nl = Image.new('RGBA', (CW, CH), (0, 0, 0, 0))
            pixel_noise(nl, box, dens, seed)
            layer.alpha_composite(nl)
        layer = glitch_slices(layer, glitch, glitch_seed, invert_bands)
        layer = chroma(layer, chroma_off)
        if keep < 1.0:
            layer = dissolve(layer, keep, glitch_seed + 99)
        small = layer.resize((int(CW * SCALE), int(CH * SCALE)), Image.LANCZOS)
        ax, ay = GX * SCALE, GY * SCALE

        def rel(bb, shrink=0):
            if bb is None:
                return None
            x0, y0, x1, y1 = [v * SCALE for v in bb]
            return (int(x0 - ax + shrink), int(y0 - ay + shrink), int(x1 - ax - shrink), int(y1 - ay - shrink))

        hurtbox = rel(_bbox(bodyonly, True), 2) if hurt else None
        hitbox = rel(_bbox(hitlayer), 2)
        if extra_hit:
            hitbox = extra_hit
        return Frame(small, hurtbox, hitbox, (ax, ay))


# ----------------------------------------------------- effect drawing ----

def bitmap_text(text, scale=2, color=(255, 255, 255, 255)):
    f = ImageFont.load_default_imagefont()
    l, t, r, b = f.getbbox(text)
    im = Image.new('RGBA', (r + 2, b + 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((0, 0), text, font=f, fill=color)
    return im.resize((im.size[0] * scale, im.size[1] * scale), Image.NEAREST)


def error_window(title, lines, w=150, scale=2, seed=0, bsod=False):
    """Small retro error dialog in grays (final scale)."""
    h = 34 + 14 * len(lines)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w - 1, h - 1), fill=(192, 192, 192, 255), outline=(0, 0, 0, 255))
    d.line((1, 1, w - 2, 1), fill=(255, 255, 255, 255))
    d.line((1, 1, 1, h - 2), fill=(255, 255, 255, 255))
    d.rectangle((3, 3, w - 4, 15), fill=(0, 0, 0, 255))
    tt = bitmap_text(title, 1)
    im.alpha_composite(tt, (6, 4))
    d.rectangle((w - 15, 5, w - 6, 13), fill=(192, 192, 192, 255), outline=(0, 0, 0, 255))
    d.line((w - 13, 7, w - 8, 12), fill=(0, 0, 0, 255))
    d.line((w - 8, 7, w - 13, 12), fill=(0, 0, 0, 255))
    # icon
    d.ellipse((8, 21, 22, 35), fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    d.line((12, 25, 18, 31), fill=(0, 0, 0, 255), width=2)
    d.line((18, 25, 12, 31), fill=(0, 0, 0, 255), width=2)
    for i, ln in enumerate(lines):
        im.alpha_composite(bitmap_text(ln, 1, (0, 0, 0, 255)), (28, 22 + i * 14))
    if scale != 1:
        im = im.resize((im.size[0] * scale, im.size[1] * scale), Image.NEAREST)
    return im


def glitch_block(size, seed, cell=6, outline=True):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    pixel_noise(im, (0, 0, size, size), 0.8, seed, cell)
    if outline:
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, size - 1, size - 1), outline=(0, 0, 0, 255), width=2)
    return im


def scatter_blocks(w, h, n, seed, smin=4, smax=14, colors=None, cx=None, cy=None, spread=1.0):
    rnd = random.Random(seed)
    colors = colors or [(0, 0, 0, 255), (255, 255, 255, 255), (154, 154, 154, 255),
                        (60, 230, 240, 255), (240, 80, 220, 255)]
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = w / 2 if cx is None else cx
    cy = h / 2 if cy is None else cy
    for _ in range(n):
        s = rnd.randint(smin, smax)
        x = cx + rnd.gauss(0, w * 0.22 * spread)
        y = cy + rnd.gauss(0, h * 0.22 * spread)
        c = rnd.choice(colors)
        d.rectangle((x, y, x + s, y + s), fill=c)
        if c != (0, 0, 0, 255) and s > 6:
            d.rectangle((x, y, x + s, y + s), outline=(0, 0, 0, 255))
    return im


def transform_point(pt, angle=0.0, pivot=CENTER, sx=1.0, sy=1.0, dx=0, dy=0):
    """Same mapping as transform() applied to one canvas point."""
    x, y = pt
    if angle:
        t = math.radians(angle)
        cx, cy = pivot
        x, y = (cx + (x - cx) * math.cos(t) + (y - cy) * math.sin(t),
                cy - (x - cx) * math.sin(t) + (y - cy) * math.cos(t))
    x = GX + (x - GX) * sx
    y = GY + (y - GY) * sy
    return x + dx, y + dy


def foot_box(angle=0.0, pivot=None, sx=1.0, sy=1.0, dx=0, dy=0, rx=46, ry=34):
    """Hit box (axis-relative, final scale) around the front foot for kick poses."""
    fx, fy = transform_point(src_to_canvas(140, 455), angle, pivot or CENTER, sx, sy, dx, dy)
    return (int((fx - rx - GX) * SCALE), int((fy - ry - GY) * SCALE),
            int((fx + rx - GX) * SCALE), int((fy + ry - GY) * SCALE))
