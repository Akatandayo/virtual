# -*- coding: utf-8 -*-
"""カメラ演出（カットシーン・カットイン）用のコマンドを作る.

- カットシーン中は、近くのプレイヤーにタグを付けて、カメラ・HUD・移動を制御する
- 終わったら必ず元に戻す（ボスが待機状態に戻ったときにも、念のため戻す）
"""
import math
import re

HUD = ["hotbar", "crosshair", "paperdoll", "health", "hunger", "armor", "progress_bar", "status_effects",
       "air_bubbles", "item_text"]


class Cine:
    def __init__(self, tag, radius=48):
        self.tag = tag
        self.radius = radius

    @property
    def sel(self):
        return "@a[tag=%s]" % self.tag

    def begin(self, sec, lock=True, hud=True):
        """近くのプレイヤーをカットシーンに参加させる（lock: 移動を止めて無敵にする）"""
        cmds = ["/tag @a[r=%d] add %s" % (self.radius, self.tag)]
        if lock:
            n = int(math.ceil(sec))
            cmds += ["/effect %s slowness %d 255 true" % (self.sel, n),
                     "/effect %s resistance %d 255 true" % (self.sel, n),
                     "/effect %s weakness %d 255 true" % (self.sel, n)]
        if hud:
            cmds += ["/hud %s hide %s" % (self.sel, h) for h in HUD]
        return cmds

    def cam(self, pos, facing, ease=None, kind="in_out_sine", run_as=None):
        e = " ease %.2f %s" % (ease, kind) if ease else ""
        cmd = "camera %s set minecraft:free%s pos %s facing %s" % (self.sel, e, pos, facing)
        if run_as:
            return "/execute as %s at @s run %s" % (run_as, cmd)
        return "/" + cmd

    def fade(self, t_in, hold, t_out, rgb=(0, 0, 0)):
        return "/camera %s fade time %.2f %.2f %.2f color %d %d %d" % ((self.sel, t_in, hold, t_out) + tuple(rgb))

    def end(self):
        return ["/camera %s clear" % self.sel, "/hud %s reset all" % self.sel,
                "/tag %s remove %s" % (self.sel, self.tag)]

    def cutin(self, tl, t, dur, pos, facing, title=None, sub=None):
        """戦闘中の一瞬のカットイン（移動は止めない）"""
        cmds = self.begin(dur, lock=False) + [self.cam(pos, facing), self.fade(0, 0, 0.25, (255, 255, 255))]
        if title:
            cmds += ["/title %s title %s" % (self.sel, title)]
        if sub:
            cmds += ["/title %s subtitle %s" % (self.sel, sub)]
        tl.setdefault(round(t, 2), []).extend(cmds)
        tl.setdefault(round(t + dur, 2), []).extend(self.end())


def add_rival(animations, rival_type, cause=None):
    """技のダメージがライバルのボスにも当たるように、ダメージ命令を複製する"""
    for anim in animations.values():
        tl = anim.get("timeline")
        if not tl:
            continue
        for key, cmds in tl.items():
            extra = []
            for c in cmds:
                if "damage @a[" not in c:
                    continue
                r = c.replace("@a[", "@e[type=%s," % rival_type)
                r = r.replace(",m=!creative", "").replace("m=!creative,", "").replace(",]", "]")
                if cause:
                    r = re.sub(r"(damage @e\[[^\]]*\] \d+) \w+", r"\1 %s" % cause, r)
                extra.append(r)
            tl[key] = cmds + extra


def vectorize_animations(anims):
    """アニメーションの値を必ず [x, y, z] にそろえる.

    拡大縮小などを 1 つの数値で書くと、統合版ではアニメーションのファイルごと読み込まれないことがあるため、
    書き出す前に全部 3 つの値に直しておく。
    """
    def vec(v):
        return [v, v, v] if isinstance(v, (int, float, str)) else v

    for a in anims.values():
        for chans in a.get("bones", {}).values():
            for ch, val in list(chans.items()):
                if isinstance(val, dict) and not ({"pre", "post"} & set(val)):
                    for t, kv in list(val.items()):
                        if isinstance(kv, dict):
                            for side in ("pre", "post"):
                                if side in kv:
                                    kv[side] = vec(kv[side])
                        else:
                            val[t] = vec(kv)
                else:
                    chans[ch] = vec(val)
    return anims


def _pchip_sample(pts, times):
    """単調な 3 次エルミート補間（PCHIP）。同じ値が続く「保持」からはみ出さない.

    pts: [(t, y), ...]（t は昇順）。両端の傾きは 0（ゆっくり動き始めて、ゆっくり止まる）。
    """
    n = len(pts)
    ts = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    hs = [ts[k + 1] - ts[k] for k in range(n - 1)]
    ds = [(ys[k + 1] - ys[k]) / hs[k] if hs[k] > 0 else 0.0 for k in range(n - 1)]
    ms = [0.0] * n
    for k in range(1, n - 1):
        if ds[k - 1] == 0 or ds[k] == 0 or (ds[k - 1] > 0) != (ds[k] > 0):
            ms[k] = 0.0
        else:
            w1 = 2 * hs[k] + hs[k - 1]
            w2 = hs[k] + 2 * hs[k - 1]
            ms[k] = (w1 + w2) / (w1 / ds[k - 1] + w2 / ds[k])
    out = []
    k = 0
    for t in times:
        if t <= ts[0]:
            out.append(ys[0])
            continue
        if t >= ts[-1]:
            out.append(ys[-1])
            continue
        while ts[k + 1] < t:
            k += 1
        h = hs[k]
        if h <= 0:
            out.append(ys[k + 1])
            continue
        s = (t - ts[k]) / h
        h00 = 2 * s ** 3 - 3 * s ** 2 + 1
        h10 = s ** 3 - 2 * s ** 2 + s
        h01 = -2 * s ** 3 + 3 * s ** 2
        h11 = s ** 3 - s ** 2
        out.append(h00 * ys[k] + h10 * h * ms[k] + h01 * ys[k + 1] + h11 * h * ms[k + 1])
    return out


def bake_smooth(anims, skip=(), step=0.1):
    """キーフレームの間を、なめらかな曲線で細かく焼き直す（統合版では直線補間のキーとして書き出す）.

    動き始めと止まり際にタメが出て、ポーズの保持中は揺れない。数式（文字列）を含むチャンネルはそのまま。
    """
    for name, a in anims.items():
        if name in skip:
            continue
        for chans in a.get("bones", {}).values():
            for ch, val in list(chans.items()):
                if not isinstance(val, dict) or len(val) < 2 or ({"pre", "post"} & set(val)):
                    continue
                pts = []
                for t, v in val.items():
                    if isinstance(v, (int, float)):
                        v = [v, v, v]
                    if not isinstance(v, list) or len(v) != 3 or any(isinstance(x, str) for x in v):
                        pts = None
                        break
                    pts.append((float(t), [float(x) for x in v]))
                if not pts:
                    continue
                pts.sort()
                t0, t1 = pts[0][0], pts[-1][0]
                grid = {round(t0 + i * step, 2) for i in range(int((t1 - t0) / step) + 1)}
                times = sorted(grid | {round(p[0], 2) for p in pts})
                comps = [_pchip_sample([(p[0], p[1][c]) for p in pts], times) for c in range(3)]
                chans[ch] = {"%.2f" % t: [round(comps[0][i], 2), round(comps[1][i], 2), round(comps[2][i], 2)]
                             for i, t in enumerate(times)}
    return anims


def add_arc_trails(anims, trail_effects, arc="arc", lead=0.12, reach=True, locators=("right_hand", "left_hand")):
    """斬撃の瞬間（trail_effects）の少し前から、手（や足）の動きに沿って光の粒を出し続ける（剣の軌跡）"""
    for a in anims.values():
        pe = a.get("particle_effects")
        if not pe:
            continue
        extra = {}
        for t, effs in pe.items():
            for e in (effs if isinstance(effs, list) else [effs]):
                if e.get("effect") in trail_effects and e.get("locator") in locators:
                    t2 = "%.2f" % max(0.0, float(t) - lead)
                    extra.setdefault(t2, []).append({"effect": arc, "locator": e["locator"]})
                    if reach and e["locator"] == "right_hand":
                        extra[t2].append({"effect": arc, "locator": "reach"})
        for t2, effs in extra.items():
            cur = pe.get(t2, [])
            cur = cur if isinstance(cur, list) else [cur]
            pe[t2] = cur + [e for e in effs if e not in cur]
    return anims
