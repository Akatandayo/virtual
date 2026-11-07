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
