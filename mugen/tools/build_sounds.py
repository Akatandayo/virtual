"""Synthesize glitchy sound effects into DenshiDoku.snd."""
import os
import numpy as np
from mugenfmt import wav_bytes, write_snd

RATE = 22050
rng = np.random.default_rng(7)
HERE = os.path.dirname(os.path.abspath(__file__))


def t(sec):
    return np.arange(int(RATE * sec)) / RATE


def env(n, attack=0.005, decay=None):
    e = np.ones(n)
    a = int(RATE * attack)
    if a:
        e[:a] = np.linspace(0, 1, a)
    if decay:
        e *= np.exp(-np.arange(n) / (RATE * decay))
    return e


def lowpass(x, k):
    if k <= 1:
        return x
    return np.convolve(x, np.ones(k) / k, mode='same')


def crush(x, bits=4, hold=4):
    x = np.repeat(x[::hold], hold)[:len(x)]
    q = 2 ** (bits - 1)
    return np.round(x * q) / q


def square(f, tt):
    return np.sign(np.sin(2 * np.pi * np.cumsum(np.broadcast_to(f, tt.shape)) / RATE))


def norm(x, vol=0.8):
    m = np.max(np.abs(x)) or 1
    return (x / m * vol * 32767).astype(np.int16)


def whoosh(sec, k, vol):
    tt = t(sec)
    n = rng.uniform(-1, 1, len(tt))
    shape = np.sin(np.pi * tt / sec) ** 2
    x = lowpass(n, k) * shape
    x = crush(x, 6, 2)
    return norm(x, vol)


def zap(sec, f0, f1, bits=4, vol=0.7):
    tt = t(sec)
    f = np.geomspace(f0, f1, len(tt))
    x = square(f, tt) * env(len(tt), 0.002, sec / 3)
    x += rng.uniform(-0.3, 0.3, len(tt)) * env(len(tt), 0, sec / 6)
    return norm(crush(x, bits, 3), vol)


def stutter(sec, vol=0.8, seed=1):
    r = np.random.default_rng(seed)
    out = []
    while sum(len(o) for o in out) < RATE * sec:
        d = r.uniform(0.015, 0.05)
        tt = t(d)
        kind = r.integers(3)
        if kind == 0:
            seg = square(np.full(len(tt), r.uniform(200, 2000)), tt)
        elif kind == 1:
            seg = r.uniform(-1, 1, len(tt))
        else:
            seg = np.zeros(len(tt))
        out.append(seg * r.uniform(0.3, 1))
    x = np.concatenate(out)[:int(RATE * sec)]
    return norm(crush(x * env(len(x), 0.002, sec / 2), 3, 2), vol)


def hit(sec, body_f, vol):
    tt = t(sec)
    thump = np.sin(2 * np.pi * np.geomspace(body_f, 40, len(tt)) * tt) * env(len(tt), 0.001, sec / 4)
    noise = rng.uniform(-1, 1, len(tt)) * env(len(tt), 0.0, sec / 8)
    x = thump + 0.7 * crush(noise, 3, 3)
    return norm(x, vol)


def beep(freqs, dur=0.09, vol=0.5):
    parts = []
    for f in freqs:
        tt = t(dur)
        parts.append(square(np.full(len(tt), f), tt) * env(len(tt), 0.003, dur))
        parts.append(np.zeros(int(RATE * 0.02)))
    return norm(np.concatenate(parts), vol)


def ko():
    tt = t(1.4)
    f = np.geomspace(900, 30, len(tt))
    x = square(f, tt) * env(len(tt), 0.002, 0.7)
    x = crush(x + rng.uniform(-0.4, 0.4, len(tt)) * env(len(tt), 0, 0.3), 3, 6)
    return norm(x, 0.8)


def alarm():
    tt = t(0.8)
    f = 600 + 300 * (np.sign(np.sin(2 * np.pi * 8 * tt)) > 0)
    return norm(crush(square(f, tt) * env(len(tt), 0.002, 0.6), 4, 2), 0.6)


SOUNDS = [
    ((0, 0), whoosh(0.16, 3, 0.45)),      # swing light
    ((0, 1), whoosh(0.24, 5, 0.55)),      # swing medium
    ((0, 2), whoosh(0.36, 8, 0.65)),      # swing heavy
    ((1, 0), zap(0.18, 2400, 300)),       # glitch zap (projectile)
    ((1, 1), stutter(0.5, seed=3)),       # long glitch
    ((1, 2), zap(0.3, 200, 3000, 3)),     # teleport
    ((1, 3), stutter(0.7, 0.9, seed=9)),  # self damage crunch
    ((1, 4), stutter(1.2, 0.8, seed=11)), # beam
    ((1, 5), beep([880, 660])),           # error beep
    ((1, 6), beep([440, 440, 440], 0.12)),# warning beep
    ((2, 0), ko()),                       # KO
    ((11, 0), ko()),
    ((3, 0), alarm()),                    # super start
    ((5, 0), hit(0.15, 300, 0.6)),        # hit light
    ((5, 1), hit(0.22, 220, 0.75)),       # hit medium
    ((5, 2), hit(0.32, 160, 0.9)),        # hit heavy
    ((5, 3), hit(0.5, 120, 0.95)),        # hit super
    ((6, 0), zap(0.12, 1500, 1200, 5, 0.5)),  # guard
    ((40, 0), zap(0.12, 300, 900, 5, 0.35)),  # jump
    ((52, 0), zap(0.08, 500, 200, 5, 0.3)),   # land
]

if __name__ == '__main__':
    out = os.path.join(HERE, '..', 'DenshiDoku', 'DenshiDoku.snd')
    write_snd(out, [(k, wav_bytes(v.tolist(), RATE)) for k, v in SOUNDS])
    print(len(SOUNDS), 'sounds,', os.path.getsize(out) // 1024, 'KB')
