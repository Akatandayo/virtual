"""Build DenshiDoku.sff and DenshiDoku.air.

Usage: python3 build_sprites.py   (run from mugen/tools)
"""
import math
import os
import sys

from PIL import Image, ImageDraw

import art
from art import Poser, error_window, glitch_block, scatter_blocks, bitmap_text
from mugenfmt import Sprite, write_sff2, read_sff2

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'DenshiDoku')
SRC = os.path.join(HERE, '..', 'source', 'denshi_doku.png')
TAU = 2 * math.pi

poser = Poser(SRC)
sprites = []          # Sprite objects
frames = {}           # (group, idx) -> Frame (for clsn)


def add_img(group, idx, img, axis):
    """img: RGBA at final scale; axis: (x, y) inside img. Crops to content."""
    bb = img.getbbox()
    if bb is None:
        bb = (0, 0, 1, 1)
    x0, y0, x1, y1 = bb
    crop = img.crop((x0, y0, x1, y1))
    px, w, h = art.quantize(crop)
    sprites.append(Sprite(group, idx, w, h, int(round(axis[0] - x0)), int(round(axis[1] - y0)), px))


def add_pose(group, idx, **kw):
    f = poser.pose(**kw)
    add_img(group, idx, f.img, f.axis)
    frames[(group, idx)] = f
    return f


def phases(n):
    return [TAU * i / n for i in range(n)]


CROUCH = dict(sx=1.03, sy=0.80, angle=-4)

# ------------------------------------------------------------ movement ---
for i, ph in enumerate(phases(8)):
    add_pose(0, i, phase=ph)                                   # stand
for i, ph in enumerate(phases(8)):
    add_pose(11, i, phase=ph, **CROUCH)                        # crouching
add_pose(10, 0, phase=0, sx=1.01, sy=0.9, angle=-2)            # stand <-> crouch
for i, ph in enumerate(phases(8)):
    add_pose(20, i, phase=ph * 2, amp=1.25, angle=-7)          # walk fwd
for i, ph in enumerate(phases(8)):
    add_pose(21, i, phase=-ph * 2, amp=1.1, angle=5)           # walk back
add_pose(5, 0, glitch=26, glitch_seed=5, chroma_off=3)         # turn
add_pose(5, 1, glitch=14, glitch_seed=6, chroma_off=2)
add_pose(40, 0, sx=1.02, sy=0.9, angle=-3)                     # jump start
for i, ph in enumerate(phases(4)):
    add_pose(41, i, phase=ph * 2, amp=1.2, stretch=1.0, angle=-10)     # rising
for i, ph in enumerate(phases(4)):
    add_pose(44, i, phase=ph * 2, amp=1.2, stretch=-1.6, angle=6)      # falling
add_pose(47, 0, sx=1.02, sy=0.9, angle=-2)                     # land
for i, ph in enumerate(phases(4)):                             # run = glitch dash
    add_pose(100, i, phase=ph * 2, amp=1.3, stretch=-0.6, angle=-16, glitch=18, glitch_seed=10 + i,
             chroma_off=4)
for i in range(3):
    add_pose(105, i, angle=12, stretch=-0.8, glitch=20, glitch_seed=20 + i, chroma_off=4)  # hop back

# --------------------------------------------------------------- guard ---
SHIELD = [([(0, 0), (90, 40), (85, 200)], 40, 34)]
add_pose(120, 0, angle=6, ribbons=[([(0, 0), (60, 20), (70, 110)], 34, 30)], hurt=True)
add_pose(130, 0, angle=7, ribbons=SHIELD)
add_pose(130, 1, angle=9, ribbons=SHIELD, chroma_off=3, glitch=8, glitch_seed=3)
add_pose(131, 0, ribbons=[([(0, 0), (90, 40), (90, 160)], 40, 34)], **CROUCH)
add_pose(131, 1, ribbons=[([(0, 0), (90, 40), (90, 160)], 40, 34)], chroma_off=3, glitch=8, glitch_seed=4,
         **CROUCH)
add_pose(132, 0, angle=2, stretch=-1.0, ribbons=SHIELD)
add_pose(132, 1, angle=4, stretch=-1.0, ribbons=SHIELD, chroma_off=3, glitch=8, glitch_seed=5)

# ------------------------------------------------------------- get hit ---
for i, (ang, g) in enumerate(((10, 10), (16, 20), (24, 30))):
    add_pose(5000, i, angle=ang, glitch=g, glitch_seed=40 + i, invert_bands=1, chroma_off=3, stretch=-0.5)
for i, (ang, g) in enumerate(((6, 10), (10, 20), (14, 30))):
    add_pose(5010, i, angle=ang, sy=0.94, glitch=g, glitch_seed=50 + i, invert_bands=1, chroma_off=3)
for i, (ang, g) in enumerate(((4, 10), (8, 20), (12, 30))):
    add_pose(5020, i, angle=ang, sx=1.03, sy=0.8, glitch=g, glitch_seed=60 + i, invert_bands=1, chroma_off=3)
add_pose(5030, 0, angle=30, stretch=-1.2, glitch=24, glitch_seed=70, invert_bands=1, chroma_off=3)
add_pose(5030, 1, angle=40, stretch=-1.5, glitch=12, glitch_seed=71, chroma_off=2)
for i, ang in enumerate((55, 70, 82)):                         # falling (going down)
    add_pose(5050, i, angle=ang, stretch=-1.6, glitch=10 if i == 0 else 0, glitch_seed=72 + i)


def lie(angle, **kw):
    """Rotate then drop to the ground so the lowest pixel touches the floor line."""
    f = poser.pose(angle=angle, **kw)
    bb = f.img.getbbox()
    drop = (f.axis[1] + 2) - bb[3]
    kw2 = dict(kw)
    kw2['dy'] = kw.get('dy', 0) + drop / art.SCALE
    return kw2


LIE = lie(90)
add_pose(5040, 0, angle=40, stretch=-1.0)                       # air recover
add_pose(5060, 0, angle=82, stretch=-1.6)
add_pose(5070, 0, angle=50, glitch=20, glitch_seed=80, chroma_off=3)  # trip
add_pose(5080, 0, angle=90, glitch=24, glitch_seed=81, invert_bands=1, chroma_off=3, dy=LIE['dy'])
add_pose(5110, 0, angle=90, dy=LIE['dy'], hurt=True)            # lie down
add_pose(5110, 1, angle=90, dy=LIE['dy'], glitch=16, glitch_seed=82, chroma_off=2)
add_pose(5100, 0, angle=86, dy=LIE['dy'] - 20, glitch=20, glitch_seed=83, chroma_off=3)  # bounce
for i, ang in enumerate((65, 40, 18)):                          # get up
    L = lie(ang)
    add_pose(5120, i, angle=ang, dy=min(0, L['dy']), keep=0.55 + 0.15 * i, glitch_seed=84 + i)
for i in range(4):                                              # dizzy
    add_pose(5300, i, phase=TAU * i / 4, angle=8 * (1 if i % 2 else -1), glitch=10 + 6 * (i % 2),
             glitch_seed=90 + i, chroma_off=2 + i % 2)
add_pose(170, 0, angle=10, sy=0.95, stretch=1.0, amp=0.4)      # lose
add_pose(170, 1, angle=12, sy=0.94, stretch=1.2, amp=0.3, glitch=8, glitch_seed=95, chroma_off=2)

# --------------------------------------------------- intro / taunt / win ---
for i in range(8):
    add_pose(190, i, phase=TAU * i / 8, keep=min(1.0, 0.1 + i * 0.14), glitch=max(0, 40 - i * 6),
             glitch_seed=100 + i, chroma_off=max(0, 5 - i))
for i in range(6):
    add_pose(195, i, phase=TAU * i / 6, angle=(-6, 6, -3, 0, 4, 0)[i], glitch=(30, 0, 22, 0, 12, 0)[i],
             glitch_seed=110 + i, invert_bands=1, chroma_off=(4, 0, 3, 0, 2, 0)[i])
for i in range(4):
    add_pose(181, i, phase=TAU * i / 4, angle=-4, ribbons=[([(0, 0), (70, -70), (120, -170)], 26, 16)])

# ----------------------------------------------------------- normals ---
R = lambda *pts: list(pts)

# stand x : quick scarf jab
add_pose(200, 0, angle=-3, ribbons=[(R((0, 0), (30, 10), (60, 4)), 26, 22)])
add_pose(200, 1, angle=-6, ribbons=[(R((0, 0), (90, -4), (210, 6)), 26, 16)])
add_pose(200, 2, angle=-5, ribbons=[(R((0, 0), (70, 2), (150, 14)), 26, 18)], hurt=True)
# stand y : mid slash
add_pose(210, 0, angle=4, ribbons_back=[(R((0, 0), (-40, -70), (-30, -150)), 26, 16)])
add_pose(210, 1, angle=-6, ribbons=[(R((0, 0), (110, -110), (250, -40)), 28, 16)])
add_pose(210, 2, angle=-9, ribbons=[(R((0, 0), (130, -10), (260, 60)), 28, 16)])
add_pose(210, 3, angle=-4, ribbons=[(R((0, 0), (80, 50), (150, 120)), 26, 18)])
# stand z : heavy overhead swing
add_pose(220, 0, angle=8, ribbons_back=[(R((0, 0), (-20, -150), (60, -230)), 30, 20)])
add_pose(220, 1, angle=-4, ribbons=[(R((0, 0), (70, -200), (260, -170)), 32, 20)], chroma_off=2)
add_pose(220, 2, angle=-12, ribbons=[(R((0, 0), (170, -100), (330, 30)), 34, 20)], chroma_off=3)
add_pose(220, 3, angle=-14, ribbons=[(R((0, 0), (170, 40), (300, 150)), 32, 20)])
add_pose(220, 4, angle=-6, ribbons=[(R((0, 0), (90, 70), (150, 150)), 28, 20)])
# stand a : light kick
add_pose(230, 0, angle=8, pivot=art.HIP)
add_pose(230, 1, angle=22, pivot=art.HIP, dx=16, extra_hit=art.foot_box(angle=22, dx=16, pivot=art.HIP))
add_pose(230, 2, angle=12, pivot=art.HIP, dx=8, extra_hit=art.foot_box(angle=12, dx=8, pivot=art.HIP))
# stand b : mid kick
add_pose(240, 0, angle=-6, pivot=art.HIP)
add_pose(240, 1, angle=26, pivot=art.HIP, dx=24, chroma_off=2, extra_hit=art.foot_box(angle=26, dx=24, pivot=art.HIP))
add_pose(240, 2, angle=34, pivot=art.HIP, dx=34, chroma_off=2, extra_hit=art.foot_box(angle=34, dx=34, pivot=art.HIP))
add_pose(240, 3, angle=14, pivot=art.HIP, dx=12, extra_hit=art.foot_box(angle=14, dx=12, pivot=art.HIP))
# stand c : glitch pillar (body pose only, pillar is an explod)
add_pose(250, 0, angle=6, glitch=8, glitch_seed=120)
add_pose(250, 1, angle=-10, glitch=22, glitch_seed=121, chroma_off=4, invert_bands=1, extra_hit=(60, -230, 140, 0))
add_pose(250, 2, angle=-8, glitch=10, glitch_seed=122, chroma_off=2, extra_hit=(60, -240, 140, 0))

# crouch x/y/z
add_pose(400, 0, ribbons=[(R((0, 0), (30, 20), (60, 30)), 26, 22)], **CROUCH)
add_pose(400, 1, ribbons=[(R((0, 0), (110, 70), (220, 120)), 26, 16)], **CROUCH)
add_pose(410, 0, ribbons_back=[(R((0, 0), (-60, -20), (-90, -80)), 26, 18)], **CROUCH)
add_pose(410, 1, ribbons=[(R((0, 0), (130, 20), (270, 70)), 28, 16)], **CROUCH)
add_pose(410, 2, ribbons=[(R((0, 0), (90, 60), (170, 120)), 26, 18)], **CROUCH)
add_pose(420, 0, ribbons_back=[(R((0, 0), (-50, 30), (-60, 100)), 28, 18)], **CROUCH)
add_pose(420, 1, ribbons=[(R((0, 0), (90, -90), (150, -290)), 32, 18)], chroma_off=2, **CROUCH)
add_pose(420, 2, ribbons=[(R((0, 0), (40, -160), (-10, -300)), 30, 18)], **CROUCH)
add_pose(420, 3, ribbons=[(R((0, 0), (40, -60), (20, -150)), 28, 20)], **CROUCH)
# crouch a/b/c
add_pose(430, 0, angle=8, pivot=art.HIP, sx=1.03, sy=0.8)
add_pose(430, 1, angle=14, pivot=art.HIP, sx=1.03, sy=0.8, dx=20, extra_hit=art.foot_box(angle=14, sx=1.03, sy=0.8, dx=20, pivot=art.HIP))
add_pose(440, 0, angle=-4, pivot=art.HIP, sx=1.03, sy=0.8)
add_pose(440, 1, angle=16, pivot=art.HIP, sx=1.03, sy=0.8, dx=40, chroma_off=2, extra_hit=art.foot_box(angle=16, sx=1.03, sy=0.8, dx=40, pivot=art.HIP))
add_pose(440, 2, angle=10, pivot=art.HIP, sx=1.03, sy=0.8, dx=20, extra_hit=art.foot_box(angle=10, sx=1.03, sy=0.8, dx=20, pivot=art.HIP))
add_pose(450, 0, ribbons_back=[(R((0, 0), (-80, 60), (-140, 160)), 28, 18)], **CROUCH)
add_pose(450, 1, ribbons=[(R((0, 0), (80, 200), (330, 230)), 30, 18)], chroma_off=3, **CROUCH)
add_pose(450, 2, ribbons=[(R((0, 0), (120, 180), (240, 240)), 28, 18)], **CROUCH)

# air x/y/z/a/b/c
AIR = dict(stretch=-0.8, angle=-4)
add_pose(600, 0, ribbons=[(R((0, 0), (40, 20), (70, 30)), 26, 20)], **AIR)
add_pose(600, 1, ribbons=[(R((0, 0), (110, 40), (210, 80)), 26, 16)], **AIR)
add_pose(610, 0, ribbons_back=[(R((0, 0), (-30, -80), (10, -160)), 28, 18)], **AIR)
add_pose(610, 1, ribbons=[(R((0, 0), (140, -30), (250, 90)), 28, 16)], **AIR)
add_pose(610, 2, ribbons=[(R((0, 0), (100, 90), (150, 200)), 28, 18)], **AIR)
add_pose(620, 0, ribbons_back=[(R((0, 0), (0, -170), (100, -240)), 32, 20)], **AIR)
add_pose(620, 1, ribbons=[(R((0, 0), (180, -80), (310, 60)), 34, 20)], chroma_off=3, **AIR)
add_pose(620, 2, ribbons=[(R((0, 0), (150, 120), (200, 280)), 34, 20)], chroma_off=2, **AIR)
add_pose(630, 0, angle=10, pivot=art.HIP, stretch=-0.8)
add_pose(630, 1, angle=24, pivot=art.HIP, dx=14, stretch=-0.8, extra_hit=art.foot_box(angle=24, dx=14, pivot=art.HIP))
add_pose(640, 0, angle=20, pivot=art.HIP, stretch=-1.0)
add_pose(640, 1, angle=42, pivot=art.HIP, dx=20, stretch=-1.4, chroma_off=3, extra_hit=art.foot_box(angle=42, dx=20, pivot=art.HIP))
add_pose(650, 0, angle=-4, glitch=12, glitch_seed=130, stretch=-0.8)
add_pose(650, 1, angle=-4, glitch=34, glitch_seed=131, invert_bands=1, chroma_off=5, stretch=-0.8,
         noise=((art.CENTER[0] - 230, art.CENTER[1] - 230, art.CENTER[0] + 230, art.CENTER[1] + 200), 0.06, 7),
         extra_hit=(-110, -230, 120, 10))

# throw
add_pose(800, 0, angle=-6, ribbons=[(R((0, 0), (70, -10), (150, 10)), 30, 22)])
add_pose(800, 1, angle=-10, ribbons=[(R((0, 0), (100, -6), (210, 20)), 30, 18)])
add_pose(810, 0, angle=-4, ribbons=[(R((0, 0), (90, -60), (150, -140)), 32, 26)], chroma_off=2)
add_pose(810, 1, angle=6, ribbons=[(R((0, 0), (60, -150), (-40, -220)), 32, 26)], glitch=20, glitch_seed=140,
         chroma_off=4)
add_pose(810, 2, angle=-14, ribbons=[(R((0, 0), (160, 30), (230, 170)), 32, 22)], chroma_off=3)

# ------------------------------------------------------------ specials ---
# 1000 bug shot
add_pose(1000, 0, angle=4, glitch=6, glitch_seed=150)
add_pose(1000, 1, angle=-10, ribbons=[(R((0, 0), (60, -10), (110, -4)), 30, 24)], chroma_off=4, glitch=14,
         glitch_seed=151)
add_pose(1000, 2, angle=-6, ribbons=[(R((0, 0), (40, 0), (70, 10)), 28, 24)], chroma_off=2)
# 1100 warp (dissolve out / in)
for i in range(5):
    add_pose(1100, i, angle=-4, keep=max(0.0, 1 - i * 0.24), glitch=10 + i * 8, glitch_seed=160 + i,
             chroma_off=2 + i)
# 1200 data lash (rising)
for i, ctrl in enumerate((R((0, 0), (80, -80), (100, -200)), R((0, 0), (-60, -120), (40, -260)),
                          R((0, 0), (110, -120), (60, -300)), R((0, 0), (-80, -60), (-40, -220)))):
    add_pose(1200, i, angle=-8 + 4 * (i % 2), stretch=1.2, ribbons=[(ctrl, 34, 18)], chroma_off=3,
             glitch=10, glitch_seed=170 + i)
add_pose(1200, 4, angle=4, stretch=-1.4)
# 1300 self corrupt
add_pose(1300, 0, angle=10, sy=0.96)
for i in range(4):
    add_pose(1300, 1 + i, angle=(-8, 10, -12, 6)[i], glitch=40 - i * 6, glitch_seed=180 + i, invert_bands=2,
             chroma_off=6 - i, phase=TAU * i / 4, amp=1.6)
add_pose(1300, 5, angle=-4, chroma_off=2)

# ------------------------------------------------------------- supers ---
add_pose(3000, 0, angle=8, ribbons_back=[(R((0, 0), (-40, -120), (40, -220)), 30, 20)], chroma_off=3)
add_pose(3000, 1, angle=-12, ribbons=[(R((0, 0), (70, -6), (130, 0)), 34, 30)], chroma_off=5, glitch=20,
         glitch_seed=190)
add_pose(3000, 2, angle=-12, ribbons=[(R((0, 0), (70, -6), (130, 0)), 34, 30)], chroma_off=3, glitch=30,
         glitch_seed=191, invert_bands=1)
add_pose(3100, 0, angle=-18, ribbons=[(R((0, 0), (120, -10), (260, 10)), 32, 22)], chroma_off=5, glitch=16,
         glitch_seed=200)
add_pose(3100, 1, angle=-6, keep=0.5, glitch=40, glitch_seed=201, chroma_off=6)
add_pose(3100, 2, angle=0, glitch=60, glitch_seed=202, invert_bands=2, chroma_off=8)

# ------------------------------------------------------------- effects ---
CANVAS_E = 1


def add_fx(group, idx, img, axis=None):
    if axis is None:
        axis = (img.size[0] / 2, img.size[1] / 2)
    add_img(group, idx, img, axis)


# 6000 bug projectile
for i in range(4):
    im = Image.new('RGBA', (70, 70), (0, 0, 0, 0))
    im.alpha_composite(scatter_blocks(70, 70, 16, 300 + i, 3, 8, spread=1.3))
    im.alpha_composite(glitch_block(40, 310 + i, 5), (15, 15))
    add_fx(6000, i, im)
# 6010 projectile vanish
for i in range(5):
    add_fx(6010, i, scatter_blocks(110, 110, 30 - i * 5, 320 + i, 3, 10 - i, spread=0.5 + i * 0.35))
# 6020 hitspark / 6025 guardspark
for i in range(5):
    im = scatter_blocks(120, 120, 34 - i * 6, 340 + i, 3, 12 - i, spread=0.35 + i * 0.3)
    d = ImageDraw.Draw(im)
    if i < 3:
        r = 14 + i * 16
        d.line((60 - r, 60, 60 + r, 60), fill=(255, 255, 255, 255), width=4 - i)
        d.line((60, 60 - r // 2, 60, 60 + r // 2), fill=(60, 230, 240, 255), width=3 - i // 2)
    add_fx(6020, i, im)
for i in range(4):
    gray = [(255, 255, 255, 255), (154, 154, 154, 255), (60, 230, 240, 255)]
    add_fx(6025, i, scatter_blocks(100, 100, 24 - i * 5, 360 + i, 3, 9, colors=gray, spread=0.3 + i * 0.3))
# 6030 glitch pillar (axis bottom center)
for i in range(6):
    h = (60, 150, 220, 240, 200, 120)[i]
    im = Image.new('RGBA', (90, 250), (0, 0, 0, 0))
    art.pixel_noise(im, (10, 250 - h, 80, 250), 0.7 if i < 4 else 0.35, 400 + i, 8)
    im.alpha_composite(scatter_blocks(90, 250, 10, 410 + i, 3, 8, cy=250 - h, spread=0.4))
    add_fx(6030, i, im, (45, 250))
# 6040 error windows
add_fx(6040, 0, error_window('ERROR', ['0x0000DEAD', 'NOT RESPONDING']))
add_fx(6040, 1, error_window('WARNING', ['SELF-DAMAGE', 'HP -8%']))
add_fx(6040, 2, error_window('ERROR', ['OPPONENT', 'NOT FOUND.']))
add_fx(6040, 3, error_window('OVERFLOW', ['BUFFER', 'OVERRUN']))
# 6050 teleport burst
for i in range(5):
    im = Image.new('RGBA', (160, 240), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rnd = __import__('random').Random(500 + i)
    for _ in range(26 - i * 4):
        y = rnd.randint(0, 238)
        x = rnd.randint(0, 80)
        w = rnd.randint(20, 80)
        d.rectangle((x, y, x + w, y + rnd.randint(1, 3)),
                    fill=rnd.choice([(255, 255, 255, 255), (60, 230, 240, 255), (240, 80, 220, 255),
                                     (0, 0, 0, 255)]))
    add_fx(6050, i, im, (80, 240))
# 6060 FATAL ERROR banner
ban = Image.new('RGBA', (420, 90), (0, 0, 0, 0))
d = ImageDraw.Draw(ban)
d.rectangle((0, 0, 419, 89), fill=(0, 0, 0, 255), outline=(255, 255, 255, 255), width=3)
t = bitmap_text('FATAL ERROR', 3, (255, 255, 255, 255))
ban.alpha_composite(t, ((420 - t.size[0]) // 2, 14))
t2 = bitmap_text('PROCESS: DENSHI_DOKU.EXE', 2, (60, 230, 240, 255))
ban.alpha_composite(t2, ((420 - t2.size[0]) // 2, 56))
add_fx(6060, 0, ban)
add_fx(6060, 1, art.glitch_slices(ban.copy(), 30, 3, 1))
# 6070 beam
for i in range(4):
    im = Image.new('RGBA', (660, 110), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rnd = __import__('random').Random(600 + i)
    core_h = 46 + (i % 2) * 8
    d.rectangle((0, 55 - core_h // 2, 659, 55 + core_h // 2), fill=(255, 255, 255, 255))
    for _ in range(140):
        x = rnd.randint(0, 650)
        y = int(rnd.gauss(55, 22))
        w = rnd.randint(6, 40)
        h = rnd.randint(3, 10)
        d.rectangle((x, y, x + w, y + h), fill=rnd.choice([(0, 0, 0, 255), (60, 230, 240, 255),
                                                            (240, 80, 220, 255), (154, 154, 154, 255)]))
    add_fx(6070, i, im, (0, 55))
# 6080 self-damage burst (red pixels)
for i in range(5):
    reds = [(255, 70, 70, 255), (150, 0, 0, 255), (0, 0, 0, 255), (255, 255, 255, 255)]
    add_fx(6080, i, scatter_blocks(160, 160, 40 - i * 7, 700 + i, 3, 10, colors=reds, spread=0.35 + i * 0.25))
# 6090 overflow aura (rising pixels, axis bottom center)
for i in range(4):
    im = Image.new('RGBA', (180, 260), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rnd = __import__('random').Random(800 + i)
    for _ in range(30):
        x = rnd.gauss(90, 40)
        y = rnd.uniform(20, 250)
        s = rnd.randint(3, 7)
        d.rectangle((x, y, x + s, y + s * rnd.randint(1, 3)),
                    fill=rnd.choice([(255, 70, 70, 255), (60, 230, 240, 255), (255, 255, 255, 255)]))
    add_fx(6090, i, im, (90, 250))
# 6100 super start flash: scanlines
im = Image.new('RGBA', (300, 300), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
for y in range(0, 300, 6):
    d.line((0, y, 299, y), fill=(60, 230, 240, 255) if (y // 6) % 3 == 0 else (255, 255, 255, 255))
add_fx(6100, 0, im)
# 6110 system crash screen (full 640x480)
bs = Image.new('RGBA', (640, 480), (0, 0, 150, 255))
d = ImageDraw.Draw(bs)
lines = [('SYSTEM CRASH', 4), ('', 2), ('A FATAL EXCEPTION 0D HAS OCCURRED', 2),
         ('IN MODULE: OPPONENT.CNS', 2), ('', 2), ('THE CURRENT PLAYER WILL BE', 2), ('TERMINATED.', 2), ('', 2),
         ('*  DATA CORRUPTION: 100%', 2), ('*  COST: 15% OF OWN HP', 2), ('', 2),
         ('PRESS ANY KEY TO CONTINUE _', 2)]
y = 60
for text, sc in lines:
    if text:
        t = bitmap_text(text, sc, (255, 255, 255, 255))
        bs.alpha_composite(t, (60, y))
    y += 14 * sc + 4
add_fx(6110, 0, bs, (320, 240))
add_fx(6110, 1, art.glitch_slices(bs.copy(), 40, 9, 1), (320, 240))
# 6120 corruption particles around opponent (crash hits)
for i in range(4):
    add_fx(6120, i, scatter_blocks(220, 260, 60 - i * 10, 900 + i, 4, 16, spread=0.45 + i * 0.2))

# ------------------------------------------------------------ portraits ---
src_img = Image.open(SRC).convert('RGBA').transpose(Image.FLIP_LEFT_RIGHT)
# big portrait 240x280: head & shoulders
head = src_img.crop((150, 40, 450, 390))
big = Image.new('RGBA', (240, 280), (0, 0, 0, 0))
h2 = head.resize((240, 280), Image.LANCZOS)
big.alpha_composite(h2)
add_img(9000, 1, big, (0, 0))
small = src_img.crop((235, 60, 385, 210)).resize((50, 50), Image.LANCZOS)
sm = Image.new('RGBA', (50, 50), (0, 0, 0, 0))
sm.alpha_composite(small)
add_img(9000, 0, sm, (0, 0))
# portraits must keep their full size: re-add without crop
for s in sprites:
    if s.group == 9000:
        pass


def add_full(group, idx, img):
    px, w, h = art.quantize(img)
    for k, s in enumerate(sprites):
        if (s.group, s.number) == (group, idx):
            sprites[k] = Sprite(group, idx, w, h, 0, 0, px)


add_full(9000, 1, big)
add_full(9000, 0, sm)


# ------------------------------------------------------------- write ---
def write():
    os.makedirs(OUT, exist_ok=True)
    pals = [((1, i + 1), art.make_palette(k)) for i, k in enumerate(art.PALETTES)]
    path = os.path.join(OUT, 'DenshiDoku.sff')
    write_sff2(path, sprites, pals)
    back, _ = read_sff2(path)
    for s in sprites:
        b = back[(s.group, s.number)]
        assert b.pixels == s.pixels and (b.axisx, b.axisy) == (s.axisx, s.axisy)
    print(f'{len(sprites)} sprites, {os.path.getsize(path) // 1024} KB, round-trip OK')


if __name__ == '__main__':
    write()
    import build_air
    build_air.write(frames, sprites, OUT)
