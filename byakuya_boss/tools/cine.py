# -*- coding: utf-8 -*-
"""カメラ演出（カットシーン・カットイン）用のコマンドを作る.

- カットシーン中は、近くのプレイヤーにタグを付けて、カメラ・HUD・移動を制御する
- 終わったら必ず元に戻す（ボスが待機状態に戻ったときにも、念のため戻す）
"""
import math
import re

CINE_TAG = "vb_cine"       # 演出（カットシーン）中のボス
PAUSE_TAG = "vb_paused"    # ほかのボスの演出のあいだ、一時停止しているボス
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
        if lock:   # 演出中: 自分に目印を付け、近くのほかのボスを一時停止させる（お互いに手出しできない）
            cmds += ["/tag @s add %s" % CINE_TAG,
                     "/event entity @e[family=%s,tag=!%s,r=64] vb:pause" % (RIVAL_FAMILY, CINE_TAG)]
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
        # 演出が終わったら（ほかに演出中のボスがいなければ）、一時停止していたボスを再開させる
        return ["/camera %s clear" % self.sel, "/hud %s reset all" % self.sel,
                "/tag %s remove %s" % (self.sel, self.tag), "/tag @s remove %s" % CINE_TAG,
                "/execute unless entity @e[tag=%s,r=64] run event entity @e[family=%s,tag=%s,r=64] vb:resume"
                % (CINE_TAG, RIVAL_FAMILY, PAUSE_TAG)]

    def cutin(self, tl, t, dur, pos, facing, title=None, sub=None):
        """戦闘中の一瞬のカットイン（移動は止めない）"""
        cmds = self.begin(dur, lock=False) + [self.cam(pos, facing), self.fade(0, 0, 0.25, (255, 255, 255))]
        if title:
            cmds += ["/title %s title %s" % (self.sel, title)]
        if sub:
            cmds += ["/title %s subtitle %s" % (self.sel, sub)]
        tl.setdefault(round(t, 2), []).extend(cmds)
        tl.setdefault(round(t + dur, 2), []).extend(self.end())


# ================================================================ ボス同士の敵対
RIVAL_FAMILY = "rival_boss"   # 4 体のボス全員が持つ family（自分以外の「ボス」を見分ける）
BOSS_NAMES = {"byakuya": "白石白夜", "hitori": "電子 独", "sophia": "ソフィア・ハート", "shinonome": "東雲 永々",
              "fuuka": "月島 風花"}
FOE_ANY = {"any_of": [{"test": "is_family", "subject": "other", "value": "player"},
                      {"test": "is_family", "subject": "other", "value": RIVAL_FAMILY}]}


def rival_target(own_family, max_dist=40):
    """nearest_attackable_target 用: 自分と同じ種類以外のボスを狙う（演出中・一時停止中のボスは狙わない）"""
    return {"filters": {"all_of": [{"test": "is_family", "subject": "other", "value": RIVAL_FAMILY},
                                   {"test": "is_family", "subject": "other", "operator": "!=", "value": own_family},
                                   {"test": "has_tag", "subject": "other", "operator": "!=", "value": CINE_TAG},
                                   {"test": "has_tag", "subject": "other", "operator": "!=", "value": PAUSE_TAG}]},
            "max_dist": max_dist}


def pause_events(not_busy):
    """vb:pause / vb:resume（4 体共通の名前）: ほかのボスの演出のあいだ、AI を止めて待つ.

    not_busy: 自分の演出中・スタン中などは何もしない（自分の都合で止めている AI を勝手に戻さない）
    """
    return {
        "vb:pause": {"sequence": [{"filters": not_busy, "remove": {"component_groups": ["ai"]},
                                   "queue_command": {"command": ["tag @s add %s" % PAUSE_TAG,
                                                                 "effect @s resistance 1 4 true"]}}]},
        "vb:resume": {"sequence": [{"filters": not_busy, "add": {"component_groups": ["ai"]}},
                                   {"queue_command": {"command": ["tag @s remove %s" % PAUSE_TAG]}}]},
    }


def rival_copy(cmd, self_type, cause="entity_attack"):
    """プレイヤーへのダメージ命令を、ほかのボス向けに書き換えたものを返す"""
    r = cmd.replace("@a[", "@e[family=%s,type=!%s,tag=!%s,tag=!%s," % (RIVAL_FAMILY, self_type, CINE_TAG, PAUSE_TAG))
    r = r.replace(",m=!creative", "").replace("m=!creative,", "").replace(",]", "]")
    return re.sub(r"(damage @e\[[^\]]*\] \d+) \w+(?: entity @\w(?:\[[^\]]*\])?)?",
                  lambda m: "%s %s entity @e[type=%s,c=1]" % (m.group(1), cause, self_type), r)


def add_rival(obj, self_type, cause="entity_attack"):
    """技のダメージが、ほかのボス（family=rival_boss・自分の種類以外）にも当たるように、ダメージ命令を複製する.

    アニメーションのタイムライン・コントローラーの on_entry・イベントの queue_command など、
    コマンドの並びならどこでも複製する。
    - ほかのボスのアドオンが入っていなくてもエラーにならないよう、type ではなく family で選ぶ
    - ダメージの種類は近接（entity_attack）にそろえ、攻撃者は自分（のボス）にする
      （反撃・Glitch の負荷・バリアの回数などが、プレイヤーに殴られたときと同じように働く）
    """
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, list) and v and all(isinstance(x, str) for x in v):
                    if any("damage @a[" in x for x in v):   # 元の命令のすぐ後ろに入れる（順番を崩さない）
                        o[k] = [y for x in v for y in ([x, rival_copy(x, self_type, cause)]
                                                         if "damage @a[" in x else [x])]
                elif isinstance(v, str) and k == "command" and "damage @a[" in v:
                    o[k] = [v, rival_copy(v, self_type, cause)]
                else:
                    walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(obj)
    return obj


def encounter_cmds(own, say, lines, radius=24):
    """ほかのボスと初めて出会ったときのひとこと（相手のアドオンが無くてもエラーにならないよう family で探す）.

    lines: {相手の family: say() に渡す文}
    """
    out = []
    for rival, text in lines.items():
        tag = "%s_met_%s" % (own, rival)
        cond = "/execute if entity @s[tag=!%s] if entity @e[family=%s,r=%d] run " % (tag, rival, radius)
        out += [cond + say(text)[1:],
                cond + "title @a[r=40] actionbar §c§l%s §7VS §c§l%s" % (BOSS_NAMES[own], BOSS_NAMES[rival]),
                cond + "playsound mob.wither.ambient @a[r=40] ~ ~ ~ 0.5 1.6",
                "/execute if entity @e[family=%s,r=%d] run tag @s add %s" % (rival, radius, tag)]
    return out


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


# ================================================================ なめらかさ（クライアント側）
# 各ボス本体（と分身）のクライアントエンティティに付ける変数の計算。毎フレーム、描画の前に動く。
CLIENT_SCRIPTS = {
    "initialize": ["v.atk_n = 0.0;", "v.atk_was = 0.0;", "v.melee_start = -10.0;", "v.melee_t = 10.0;",
                   "v.hurt_t = -10.0;", "v.hurt_was = 0.0;", "v.flinch = 0.0;",
                   "v.spd = 0.0;", "v.yaw_prev = 0.0;", "v.yaw_ready = 0.0;", "v.yaw_off = 0.0;", "v.dt = 0.016;"],
    "pre_animation": [
        "v.dt = math.clamp(q.delta_time, 0.004, 0.25);",
        # 移動速度をなめらかにする（走り出し・止まり際に、走りのモーションがゆっくり出入りする）
        "v.spd = v.spd + (math.clamp(q.modified_move_speed, 0.0, 1.0) - v.spd) * (1.0 - math.exp(-v.dt / 0.12));",
        # 体の向きの急な変化（tp で振り向く・tick ごとの回転技）を、なめらかな回転に変える
        "v.yaw_d = (v.yaw_ready > 0.5) ? q.body_y_rotation - v.yaw_prev : 0.0;",
        "v.yaw_d = v.yaw_d - 360.0 * math.round(v.yaw_d / 360.0);",
        "v.yaw_prev = q.body_y_rotation;",
        "v.yaw_ready = 1.0;",
        "v.yaw_off = math.clamp((v.yaw_off - v.yaw_d) * math.exp(-v.dt / 0.07), -160.0, 160.0);",
        # 通常攻撃の左右（技の順番）は「振り始めた瞬間」に切り替える（振っている途中で入れ替わらない）
        "v.atk_n = (v.attack_time > 0.0 && (v.atk_was <= 0.0 || v.attack_time < v.atk_was)) ? "
        "math.mod(v.atk_n + 1, 12) : v.atk_n;",
        # 通常攻撃のコンボ: 振り始めた時刻からの経過時間で、キーフレームのモーションを再生する
        "v.melee_start = (v.attack_time > 0.0 && (v.atk_was <= 0.0 || v.attack_time < v.atk_was)) ? "
        "q.life_time : v.melee_start;",
        "v.melee_t = q.life_time - v.melee_start;",
        "v.atk_was = v.attack_time;",
        # 被弾ののけぞり: 一瞬でのけぞって、なめらかに戻る（tick ごとの段差をなくす）
        "v.hurt_t = (q.hurt_time > v.hurt_was) ? q.life_time : v.hurt_t;",
        "v.hurt_was = q.hurt_time;",
        "v.flinch = (q.life_time - v.hurt_t < 0.08) ? math.sin((q.life_time - v.hurt_t) * 1125.0) : "
        "((q.life_time - v.hurt_t < 0.6) ? 0.5 + 0.5 * math.cos((q.life_time - v.hurt_t - 0.08) * 346.15) : 0.0);",
    ],
}
SPD = "v.spd"   # なめらかにした移動速度（0〜1）

# 体の向きの補正（ルートを逆に回して、少しずつ戻す）
TURN_ANIM = {"loop": True, "bones": {"root": {"rotation": [0, "v.yaw_off", 0]}}}

# 技の最中の「止まっているポーズ」にも、ごくわずかな呼吸と揺れを足す（固まって見えないように）
ALIVE_ANIM = {"loop": True, "bones": {
    "body": {"rotation": ["math.sin(q.life_time * 100) * 1.2", "math.sin(q.life_time * 63 + 20) * 1.0", 0]},
    "head": {"rotation": ["math.sin(q.life_time * 81 + 50) * 1.4", "math.sin(q.life_time * 57 + 10) * 1.8", 0]},
    "rightArm": {"rotation": ["math.sin(q.life_time * 92 + 30) * 1.6", 0, "math.sin(q.life_time * 74) * 1.3"]},
    "leftArm": {"rotation": ["math.sin(q.life_time * 87 + 75) * 1.6", 0, "-math.sin(q.life_time * 69 + 40) * 1.3"]},
}}

# 状態の中の「条件つきアニメーション」を、オン/オフではなく重み（0〜1）で出し入れする
SOFT_WEIGHTS = {
    "q.modified_move_speed < 0.3": "math.clamp((0.35 - v.spd) * 5.0, 0.0, 1.0)",
    "q.modified_move_speed > 0.1": "math.clamp(v.spd * 5.0, 0.0, 1.0)",
    "q.modified_move_speed > 0.4": "v.spd > 0.4",
    "q.modified_move_speed > 0.4 && q.skin_id < 2": "v.spd > 0.4 && q.skin_id < 2",
}


def smooth_controller(ac, name, enter=0.2, leave=0.3, skill_extra=("alive",)):
    """メインのアニメーションコントローラーの切り替えをなめらかにする.

    - 待機 → 技は enter 秒、技 → 待機は leave 秒かけてクロスフェード（技は最後のポーズを保持したまま溶ける）
    - 回転は近い向きへ（720° 回る技のあとに、逆回転して戻らない）
    - 条件つきアニメーションは重みで出し入れ（走り出しで腕がパッと戻らない）
    - 技の最中は ALIVE_ANIM を重ねる
    """
    states = ac["animation_controllers"][name]["states"]
    for sname, st in states.items():
        if sname != "death":
            st["blend_transition"] = enter if sname == "default" else leave
            st["blend_via_shortest_path"] = True
        new = []
        for a in st.get("animations", []):
            if isinstance(a, dict):
                (k, cond), = a.items()
                a = {k: SOFT_WEIGHTS.get(cond, cond)}
            new.append(a)
        if sname not in ("default", "death"):
            new += [x for x in skill_extra if x not in new]
        if "animations" in st:
            st["animations"] = new
    return ac


def smooth_client(desc, turn=True):
    """クライアントエンティティに、なめらかさ用の変数と体の向きの補正を付ける"""
    sc = desc.setdefault("scripts", {})
    sc["initialize"] = list(CLIENT_SCRIPTS["initialize"])
    sc["pre_animation"] = list(CLIENT_SCRIPTS["pre_animation"])
    if turn and "turn" in desc.get("animations", {}) and "turn" not in sc.get("animate", []):
        sc.setdefault("animate", []).append("turn")
    return desc


def split_dashes(timeline, min_dist=6.0, fracs=(0.5, 0.3, 0.2), dt=0.05):
    """一瞬の長距離 tp（斬り抜け）を、数 tick に分けた高速移動にする（見た目がなめらかになる）.

    当たり判定・エフェクトは元のタイミングのまま。最初の一歩は、その時刻のコマンドの一番最後に回す。
    """
    pat = re.compile(r"^/tp @s \^ \^ \^(-?\d+(?:\.\d+)?)$")
    adds = []
    for t in list(timeline):
        keep = []
        for c in timeline[t]:
            m = pat.match(c)
            if m and abs(float(m.group(1))) >= min_dist:
                adds.append((float(t), float(m.group(1))))
            else:
                keep.append(c)
        timeline[t] = keep
    for t, d in adds:
        for i, f in enumerate(fracs):
            key = "%.2f" % (t + i * dt)
            timeline[key] = timeline.get(key, []) + ["/tp @s ^ ^ ^%g" % round(d * f, 3)]
    return timeline


# ================================================================ ボス同士でも戦えるAI
FOE_TAG = "vb_foe"   # 「敵」の目印（サバイバル・アドベンチャーのプレイヤーと、すべてのボス）


def foe_sel(self_type, args=""):
    """一番近い敵（プレイヤー・ほかのボス）。自分と同じ種類のボスは除く"""
    a = "tag=%s,tag=!%s,tag=!%s,type=!%s" % (FOE_TAG, CINE_TAG, PAUSE_TAG, self_type)
    return "@e[%s%s,c=1]" % (a, "," + args if args else "")


def aim_at_foes(obj, self_type):
    """技の狙い「一番近いプレイヤー（@p[...m=!creative]）」を「一番近い敵」に置き換える.

    プレイヤー 1 人と戦うときは今までと同じ相手を狙い、ほかのボスがもっと近ければそちらを狙う。
    演出用の @p[r=64] や、プレイヤー専用の「鎖」のタグはそのまま。
    """
    pat = re.compile(r"@p\[([^\]]*)\]")

    def repl(m):
        args = [x for x in m.group(1).split(",") if x]
        if "m=!creative" not in args:
            return m.group(0)
        return foe_sel(self_type, ",".join(x for x in args if x != "m=!creative"))

    def fix(s):
        if "@p[" not in s or s.lstrip("/").startswith("tag @p["):
            return s
        return pat.sub(repl, s)

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str):
                    o[k] = fix(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                if isinstance(v, str):
                    o[i] = fix(v)
                else:
                    walk(v)
    walk(obj)
    return obj


def foe_tag_anim(self_type, near_tag, near=7.0, period=0.5):
    """常に動く: 敵の目印を付け直し、「近くに敵がいる」タグ（技選びの近距離・遠距離）を更新する"""
    return {"animation_length": period, "loop": True, "timeline": {"0.00": [
        "/tag @s add %s" % FOE_TAG,
        "/tag @a[m=survival] add %s" % FOE_TAG, "/tag @a[m=adventure] add %s" % FOE_TAG,
        "/tag @a[m=creative] remove %s" % FOE_TAG, "/tag @a[m=spectator] remove %s" % FOE_TAG,
        "/tag @s remove %s" % near_tag,
        "/execute if entity @e[tag=%s,tag=!%s,tag=!%s,type=!%s,r=%g] run tag @s add %s"
        % (FOE_TAG, CINE_TAG, PAUSE_TAG, self_type, near, near_tag),
        # 一時停止中は無敵（止まっている間に殴られ放題にならない）
        "/effect @s[tag=%s] resistance 1 4 true" % PAUSE_TAG]}}


def near_filters(near_tag):
    """技選び: 近くに敵がいる / いない"""
    return ({"test": "has_tag", "subject": "self", "value": near_tag},
            {"test": "has_tag", "subject": "self", "operator": "!=", "value": near_tag})


def footwork_steps(add, t0, n, offset, face, fx=(), dt=0.05, fx_every=2):
    """t0 から dt ごとに n 回、少しずつ tp する（壁の中には入らない）。向きは毎回 face に合わせ直す"""
    for i in range(n):
        add(t0 + i * dt, ["/tp @s %s facing %s true" % (offset, face)] + (list(fx) if i % fx_every == 0 else []))


def footwork_bones(kind, hold_r, strike="sword"):
    """立ち回りのモーション. kind: "back"（後ろへ跳んで遠距離で反撃）/ "right"・"left"（回り込んで斬る）"""
    N = [0, 0, 0]
    if strike == "sword":
        wind, hit, follow = [-128, 48, 0], [-82, -80, 0], [-70, -64, 0]
    else:   # 拳・魔法: 腕を引いて、まっすぐ突き出す
        wind, hit, follow = [-35, 25, 0], [-96, 0, 0], [-88, 0, 0]
    if kind == "back":
        return {
            "root": {"position": {0: N, 0.05: [0, 1.6, 0], 0.17: [0, -1.8, 0], 0.3: [0, -0.6, 0], 0.42: [0, -1.0, 0],
                                  0.52: [0, -1.4, 0], 0.8: [0, -0.6, 0], 1.1: N}},
            "body": {"rotation": {0: N, 0.05: [-14, 0, 0], 0.17: [12, 0, 0], 0.3: [4, 0, 0], 0.42: [2, 32, 0],
                                  0.52: [8, -28, 0], 0.8: [5, -18, 0], 1.1: N}},
            "head": {"rotation": {0: N, 0.05: [8, 0, 0], 0.17: [-8, 0, 0], 0.42: [0, -24, 0], 0.52: [-4, 20, 0],
                                  1.1: N}},
            "rightArm": {"rotation": {0: hold_r, 0.05: [-50, 15, 10], 0.17: [-35, 10, 0], 0.42: wind, 0.52: hit,
                                      0.8: follow, 1.1: hold_r}},
            "leftArm": {"rotation": {0: N, 0.05: [-30, 0, -40], 0.17: [-20, 0, -25], 0.42: [-55, -20, 0],
                                     0.52: [10, 0, -15], 1.1: N}},
            "rightLeg": {"rotation": {0: N, 0.05: [-45, 0, 0], 0.17: [-30, 0, 5], 0.3: [-10, 0, 0], 0.52: [-20, 0, 0],
                                      1.1: N}},
            "leftLeg": {"rotation": {0: N, 0.05: [30, 0, 0], 0.17: [20, 0, -5], 0.3: [10, 0, 0], 0.52: [25, 0, 0],
                                     1.1: N}},
        }
    s = 1 if kind == "right" else -1      # 右へ回り込む = +1
    lead, trail = ("rightLeg", "leftLeg") if s > 0 else ("leftLeg", "rightLeg")
    step = {0: N, 0.1: [0, 0, 26 * s], 0.18: [0, 0, 4 * s], 0.26: [0, 0, 26 * s], 0.34: [0, 0, 4 * s],
            0.42: [0, 0, 22 * s], 0.5: [-30, 0, 0], 0.58: [-40, 0, 0], 0.9: [-15, 0, 0], 1.3: N}
    follow_leg = {0: N, 0.14: [0, 0, 12 * s], 0.22: [0, 0, 0], 0.3: [0, 0, 12 * s], 0.38: [0, 0, 0],
                  0.5: [20, 0, 0], 0.58: [30, 0, 0], 0.9: [10, 0, 0], 1.3: N}
    return {
        "root": {"position": {0: N, 0.08: [0, -2.0, 0], 0.14: [0, -1.2, 0], 0.22: [0, -2.0, 0], 0.3: [0, -1.2, 0],
                              0.38: [0, -2.0, 0], 0.46: [0, -1.6, 0], 0.58: [0, -2.6, 0], 0.9: [0, -1.0, 0], 1.3: N}},
        "body": {"rotation": {0: N, 0.08: [16, 0, -10 * s], 0.44: [16, 0, -10 * s], 0.5: [10, 34, 0],
                              0.58: [18, -40, 0], 0.9: [10, -26, 0], 1.3: N}},
        "head": {"rotation": {0: N, 0.08: [-12, 0, 8 * s], 0.44: [-12, 0, 8 * s], 0.5: [-6, -26, 0],
                              0.58: [-10, 28, 0], 1.3: N}},
        "rightArm": {"rotation": {0: hold_r, 0.08: [-38, 32, 0], 0.44: [-38, 32, 0], 0.5: wind, 0.58: hit,
                                  0.9: follow, 1.3: hold_r}},
        "leftArm": {"rotation": {0: N, 0.08: [-18, 0, -28], 0.44: [-18, 0, -28], 0.5: [-60, -20, 0],
                                 0.58: [12, 0, -18], 1.3: N}},
        lead: {"rotation": step},
        trail: {"rotation": follow_leg},
    }


# ================================================================ 通常攻撃（近接）の 4 連コンボ
# 振り始めた時刻からの経過時間（v.melee_t）で再生する、全身を使ったキーフレームのモーション。
# 溜め → 踏み込みながら打つ → 振り抜き（フォロースルー）→ 戻り、の 4 段。
MELEE_LEN = 0.68


def melee_move(name, hold_r):
    N = [0, 0, 0]
    H = hold_r
    M = {
        # 袈裟斬り: 右上に振りかぶって、左下へ斬り下ろす
        "kesa": {
            "root": {"position": {0: N, 0.09: [0, 0.4, 0.8], 0.15: [0, -1.6, -2.2], 0.26: [0, -1.9, -2.5],
                                  0.46: [0, -0.6, -1.0], MELEE_LEN: N}},
            "body": {"rotation": {0: N, 0.09: [-6, 26, 0], 0.15: [16, -30, 0], 0.26: [19, -38, 0], 0.46: [7, -12, 0],
                                  MELEE_LEN: N}},
            "head": {"rotation": {0: N, 0.09: [4, -16, 0], 0.15: [-4, 18, 0], 0.26: [-6, 22, 0], 0.46: [0, 6, 0],
                                  MELEE_LEN: N}},
            "rightArm": {"rotation": {0: H, 0.09: [-150, 35, 25], 0.15: [-58, -72, -8], 0.26: [-42, -88, -14],
                                      0.46: [-35, -30, 0], MELEE_LEN: H}},
            "leftArm": {"rotation": {0: N, 0.09: [-35, 0, -25], 0.15: [12, 0, -12], 0.46: [-5, 0, -5], MELEE_LEN: N}},
            "rightLeg": {"rotation": {0: N, 0.09: [8, 0, 0], 0.15: [-34, 0, 0], 0.46: [-12, 0, 0], MELEE_LEN: N}},
            "leftLeg": {"rotation": {0: N, 0.09: [-12, 0, 0], 0.15: [24, 0, 0], 0.46: [8, 0, 0], MELEE_LEN: N}},
        },
        # 逆袈裟: 左下から右上へ斬り上げる
        "gyaku": {
            "root": {"position": {0: N, 0.09: [0, -1.3, 0.6], 0.15: [0, 0.5, -1.9], 0.26: [0, 0.7, -2.1],
                                  0.46: [0, 0, -0.8], MELEE_LEN: N}},
            "body": {"rotation": {0: N, 0.09: [11, -30, 0], 0.15: [-9, 26, 0], 0.26: [-12, 32, 0], 0.46: [-2, 8, 0],
                                  MELEE_LEN: N}},
            "head": {"rotation": {0: N, 0.09: [-4, 18, 0], 0.15: [8, -14, 0], 0.26: [8, -18, 0], 0.46: [0, -4, 0],
                                  MELEE_LEN: N}},
            "rightArm": {"rotation": {0: H, 0.09: [-22, -72, -18], 0.15: [-158, 40, 22], 0.26: [-172, 52, 26],
                                      0.46: [-60, 10, 5], MELEE_LEN: H}},
            "leftArm": {"rotation": {0: N, 0.09: [-25, 0, -30], 0.15: [10, 0, -20], 0.46: [0, 0, -6], MELEE_LEN: N}},
            "rightLeg": {"rotation": {0: N, 0.09: [14, 0, 0], 0.15: [-30, 0, 0], 0.46: [-10, 0, 0], MELEE_LEN: N}},
            "leftLeg": {"rotation": {0: N, 0.09: [-18, 0, 0], 0.15: [20, 0, 0], 0.46: [6, 0, 0], MELEE_LEN: N}},
        },
        # 突き: 引き絞って、深く踏み込みながら真っ直ぐ突く
        "thrust": {
            "root": {"position": {0: N, 0.1: [0, -1.4, 1.2], 0.16: [0, -2.2, -3.2], 0.3: [0, -2.0, -3.1],
                                  0.48: [0, -0.6, -1.1], MELEE_LEN: N}},
            "body": {"rotation": {0: N, 0.1: [6, 34, 0], 0.16: [13, -14, 0], 0.3: [12, -12, 0], 0.48: [5, -4, 0],
                                  MELEE_LEN: N}},
            "head": {"rotation": {0: N, 0.1: [0, -22, 0], 0.16: [-4, 10, 0], 0.48: [0, 3, 0], MELEE_LEN: N}},
            "rightArm": {"rotation": {0: H, 0.1: [-78, 32, 0], 0.16: [-92, -4, 0], 0.3: [-91, -6, 0],
                                      0.48: [-50, -10, 0], MELEE_LEN: H},
                         "position": {0: N, 0.1: [0, 0, 2.2], 0.16: [0, 0, -3.2], 0.3: [0, 0, -3.0],
                                      0.48: [0, 0, -0.6], MELEE_LEN: N}},
            "leftArm": {"rotation": {0: N, 0.1: [-62, -22, 0], 0.16: [14, 0, -22], 0.48: [0, 0, -6], MELEE_LEN: N}},
            "rightLeg": {"rotation": {0: N, 0.1: [10, 0, 0], 0.16: [-52, 0, 0], 0.3: [-50, 0, 0], 0.48: [-16, 0, 0],
                                      MELEE_LEN: N}},
            "leftLeg": {"rotation": {0: N, 0.1: [-16, 0, 0], 0.16: [36, 0, 0], 0.3: [34, 0, 0], 0.48: [10, 0, 0],
                                     MELEE_LEN: N}},
        },
        # 横一文字: 右に大きく引いて、腰の回転で水平に薙ぎ払う
        "sweep": {
            "root": {"position": {0: N, 0.1: [0, -1.0, 0.6], 0.17: [0, -1.8, -1.8], 0.28: [0, -1.9, -2.0],
                                  0.48: [0, -0.5, -0.8], MELEE_LEN: N},
                     "rotation": {0: N, 0.1: [0, 10, 0], 0.17: [0, -18, 0], 0.28: [0, -24, 0], 0.48: [0, -6, 0],
                                  MELEE_LEN: N}},
            "body": {"rotation": {0: N, 0.1: [2, 46, 0], 0.17: [9, -48, 0], 0.28: [11, -60, 0], 0.48: [4, -15, 0],
                                  MELEE_LEN: N}},
            "head": {"rotation": {0: N, 0.1: [0, -28, 0], 0.17: [0, 28, 0], 0.28: [0, 34, 0], 0.48: [0, 8, 0],
                                  MELEE_LEN: N}},
            "rightArm": {"rotation": {0: H, 0.1: [-88, 80, 0], 0.17: [-90, -78, 0], 0.28: [-86, -100, 0],
                                      0.48: [-40, -30, 0], MELEE_LEN: H}},
            "leftArm": {"rotation": {0: N, 0.1: [-20, 0, -35], 0.17: [-10, 0, -10], 0.48: [0, 0, -5], MELEE_LEN: N}},
            "rightLeg": {"rotation": {0: N, 0.17: [-26, 0, 0], 0.48: [-8, 0, 0], MELEE_LEN: N}},
            "leftLeg": {"rotation": {0: N, 0.17: [20, 0, 0], 0.48: [6, 0, 0], MELEE_LEN: N}},
        },
        # 右ストレート
        "straight_r": {
            "root": {"position": {0: N, 0.08: [0, -0.6, 0.6], 0.13: [0, -0.9, -1.6], 0.22: [0, -0.9, -1.7],
                                  0.4: [0, -0.3, -0.6], MELEE_LEN: N}},
            "body": {"rotation": {0: N, 0.08: [0, 26, 0], 0.13: [8, -20, 0], 0.22: [8, -22, 0], 0.4: [3, -6, 0],
                                  MELEE_LEN: N}},
            "head": {"rotation": {0: N, 0.08: [0, -16, 0], 0.13: [0, 12, 0], 0.4: [0, 3, 0], MELEE_LEN: N}},
            "rightArm": {"rotation": {0: H, 0.08: [24, 0, 12], 0.13: [-96, 0, 0], 0.22: [-95, 0, 0], 0.4: [-30, 0, 4],
                                      MELEE_LEN: H},
                         "position": {0: N, 0.13: [0, 0, -2.2], 0.22: [0, 0, -2.1], 0.4: [0, 0, -0.4], MELEE_LEN: N}},
            "leftArm": {"rotation": {0: N, 0.08: [-40, 0, -12], 0.13: [-25, 0, -8], 0.4: [-8, 0, -4], MELEE_LEN: N}},
            "rightLeg": {"rotation": {0: N, 0.13: [-20, 0, 0], 0.4: [-6, 0, 0], MELEE_LEN: N}},
            "leftLeg": {"rotation": {0: N, 0.13: [16, 0, 0], 0.4: [5, 0, 0], MELEE_LEN: N}},
        },
        # 左フック
        "hook_l": {
            "root": {"position": {0: N, 0.08: [0, -0.8, 0.4], 0.14: [0, -1.0, -1.3], 0.24: [0, -1.0, -1.4],
                                  0.42: [0, -0.3, -0.5], MELEE_LEN: N}},
            "body": {"rotation": {0: N, 0.08: [0, -28, 0], 0.14: [7, 30, 0], 0.24: [8, 36, 0], 0.42: [3, 10, 0],
                                  MELEE_LEN: N}},
            "head": {"rotation": {0: N, 0.08: [0, 18, 0], 0.14: [0, -16, 0], 0.24: [0, -20, 0], 0.42: [0, -5, 0],
                                  MELEE_LEN: N}},
            "leftArm": {"rotation": {0: N, 0.08: [-78, -62, 0], 0.14: [-90, 26, 0], 0.24: [-86, 46, 0],
                                     0.42: [-30, 10, 0], MELEE_LEN: N}},
            "rightArm": {"rotation": {0: H, 0.08: [-35, 0, 10], 0.14: [-30, 0, 8], 0.42: [-10, 0, 3], MELEE_LEN: H}},
            "leftLeg": {"rotation": {0: N, 0.14: [-18, 0, 0], 0.42: [-6, 0, 0], MELEE_LEN: N}},
            "rightLeg": {"rotation": {0: N, 0.14: [14, 0, 0], 0.42: [4, 0, 0], MELEE_LEN: N}},
        },
        # アッパー: 沈み込んでから、伸び上がりながら突き上げる
        "upper": {
            "root": {"position": {0: N, 0.09: [0, -2.2, 0.3], 0.15: [0, 1.2, -1.3], 0.26: [0, 1.4, -1.4],
                                  0.44: [0, 0, -0.5], MELEE_LEN: N}},
            "body": {"rotation": {0: N, 0.09: [14, 16, 0], 0.15: [-12, -10, 0], 0.26: [-14, -12, 0], 0.44: [-2, -3, 0],
                                  MELEE_LEN: N}},
            "head": {"rotation": {0: N, 0.09: [-10, -8, 0], 0.15: [10, 6, 0], 0.44: [2, 0, 0], MELEE_LEN: N}},
            "rightArm": {"rotation": {0: H, 0.09: [18, 0, 12], 0.15: [-162, -8, 0], 0.26: [-170, -10, 4],
                                      0.44: [-60, 0, 0], MELEE_LEN: H}},
            "leftArm": {"rotation": {0: N, 0.09: [-35, 0, -12], 0.15: [-30, 0, -15], 0.44: [-8, 0, -4], MELEE_LEN: N}},
            "rightLeg": {"rotation": {0: N, 0.09: [10, 0, 0], 0.15: [-14, 0, 0], 0.44: [-4, 0, 0], MELEE_LEN: N}},
            "leftLeg": {"rotation": {0: N, 0.09: [-14, 0, 0], 0.15: [8, 0, 0], 0.44: [2, 0, 0], MELEE_LEN: N}},
        },
        # 両手の掌底（ノイズで押し出す）
        "palm": {
            "root": {"position": {0: N, 0.1: [0, -1.2, 0.8], 0.16: [0, -1.4, -2.0], 0.3: [0, -1.4, -2.1],
                                  0.46: [0, -0.4, -0.7], MELEE_LEN: N}},
            "body": {"rotation": {0: N, 0.1: [-6, 0, 0], 0.16: [12, 0, 0], 0.3: [12, 0, 0], 0.46: [4, 0, 0],
                                  MELEE_LEN: N}},
            "head": {"rotation": {0: N, 0.1: [0, 0, 18], 0.16: [0, 0, -14], 0.3: [0, 0, 10], 0.46: N, MELEE_LEN: N}},
            "rightArm": {"rotation": {0: H, 0.1: [-62, 0, 26], 0.16: [-92, 0, 6], 0.3: [-90, 0, 6], 0.46: [-40, 0, 8],
                                      MELEE_LEN: H},
                         "position": {0: N, 0.1: [0, 0, 1.4], 0.16: [0, 0, -2.4], 0.3: [0, 0, -2.2],
                                      0.46: [0, 0, -0.5], MELEE_LEN: N}},
            "leftArm": {"rotation": {0: N, 0.1: [-62, 0, -26], 0.16: [-92, 0, -6], 0.3: [-90, 0, -6],
                                     0.46: [-40, 0, -8], MELEE_LEN: N},
                        "position": {0: N, 0.1: [0, 0, 1.4], 0.16: [0, 0, -2.4], 0.3: [0, 0, -2.2],
                                     0.46: [0, 0, -0.5], MELEE_LEN: N}},
            "rightLeg": {"rotation": {0: N, 0.16: [-24, 0, 0], 0.46: [-8, 0, 0], MELEE_LEN: N}},
            "leftLeg": {"rotation": {0: N, 0.16: [18, 0, 0], 0.46: [6, 0, 0], MELEE_LEN: N}},
        },
        # 左ジャブ（右手は刀を構えたまま）
        "jab_l": {
            "root": {"position": {0: N, 0.08: [0, -0.6, 0.6], 0.13: [0, -0.9, -1.6], 0.22: [0, -0.9, -1.7],
                                  0.4: [0, -0.3, -0.6], MELEE_LEN: N}},
            "body": {"rotation": {0: N, 0.08: [0, -26, 0], 0.13: [8, 22, 0], 0.22: [8, 24, 0], 0.4: [3, 6, 0],
                                  MELEE_LEN: N}},
            "head": {"rotation": {0: N, 0.08: [0, 16, 0], 0.13: [0, -12, 0], 0.4: [0, -3, 0], MELEE_LEN: N}},
            "leftArm": {"rotation": {0: N, 0.08: [22, 0, -12], 0.13: [-96, 0, 0], 0.22: [-95, 0, 0], 0.4: [-30, 0, -4],
                                     MELEE_LEN: N},
                        "position": {0: N, 0.13: [0, 0, -2.2], 0.22: [0, 0, -2.1], 0.4: [0, 0, -0.4], MELEE_LEN: N}},
            "rightArm": {"rotation": {0: H, 0.08: [-35, -10, 12], 0.13: [-30, -6, 8], 0.4: H, MELEE_LEN: H}},
            "leftLeg": {"rotation": {0: N, 0.13: [-20, 0, 0], 0.4: [-6, 0, 0], MELEE_LEN: N}},
            "rightLeg": {"rotation": {0: N, 0.13: [16, 0, 0], 0.4: [5, 0, 0], MELEE_LEN: N}},
        },
        # 右の回し蹴り: 腰をひねって溜め、軸足で回りながら脚を大きく回す
        "roundhouse": {
            "root": {"position": {0: N, 0.1: [0, -0.8, 0], 0.18: [0, 0.9, -0.8], 0.3: [0, 0.6, -0.9],
                                  0.5: [0, 0, -0.4], MELEE_LEN: N},
                     "rotation": {0: N, 0.1: [0, 18, 0], 0.18: [0, -30, 0], 0.3: [0, -52, 0], 0.5: [0, -16, 0],
                                  MELEE_LEN: N}},
            "body": {"rotation": {0: N, 0.1: [4, 14, 0], 0.18: [-16, -22, -8], 0.3: [-14, -30, -6], 0.5: [-4, -8, 0],
                                  MELEE_LEN: N}},
            "head": {"rotation": {0: N, 0.1: [0, -10, 0], 0.18: [6, 22, 0], 0.3: [6, 30, 0], 0.5: [0, 8, 0],
                                  MELEE_LEN: N}},
            "rightLeg": {"rotation": {0: N, 0.1: [16, 0, 8], 0.18: [-86, 10, 34], 0.3: [-78, -60, 22],
                                      0.5: [-18, -14, 6], MELEE_LEN: N}},
            "leftLeg": {"rotation": {0: N, 0.18: [0, 0, -6], 0.5: [0, 0, -2], MELEE_LEN: N}},
            "rightArm": {"rotation": {0: H, 0.1: [-30, 0, 40], 0.18: [-40, 0, 55], 0.3: [-36, 0, 50], 0.5: [-25, 0, 14],
                                      MELEE_LEN: H}},
            "leftArm": {"rotation": {0: N, 0.1: [-20, 0, -40], 0.18: [-25, 0, -60], 0.3: [-22, 0, -55],
                                     0.5: [-6, 0, -14], MELEE_LEN: N}},
        },
        # 振りかぶって真上から叩き斬る
        "chop": {
            "root": {"position": {0: N, 0.1: [0, 1.0, 0.6], 0.16: [0, -1.8, -1.6], 0.28: [0, -2.0, -1.8],
                                  0.46: [0, -0.5, -0.6], MELEE_LEN: N}},
            "body": {"rotation": {0: N, 0.1: [-10, 8, 0], 0.16: [20, 0, 0], 0.28: [22, 0, 0], 0.46: [6, 0, 0],
                                  MELEE_LEN: N}},
            "head": {"rotation": {0: N, 0.1: [8, 0, 0], 0.16: [-10, 0, 0], 0.46: [-2, 0, 0], MELEE_LEN: N}},
            "rightArm": {"rotation": {0: H, 0.1: [-172, 0, 10], 0.16: [-38, -10, 0], 0.28: [-30, -12, 0],
                                      0.46: [-20, -8, 0], MELEE_LEN: H}},
            "leftArm": {"rotation": {0: N, 0.1: [-150, 0, -15], 0.16: [-40, 0, -10], 0.46: [-8, 0, -4], MELEE_LEN: N}},
            "rightLeg": {"rotation": {0: N, 0.16: [-24, 0, 0], 0.46: [-8, 0, 0], MELEE_LEN: N}},
            "leftLeg": {"rotation": {0: N, 0.16: [18, 0, 0], 0.46: [6, 0, 0], MELEE_LEN: N}},
        },
        # 前蹴り（スナップ）
        "snap_kick": {
            "root": {"position": {0: N, 0.09: [0, -0.6, 0.4], 0.15: [0, 0.6, -0.6], 0.26: [0, 0.5, -0.7],
                                  0.44: [0, 0, -0.3], MELEE_LEN: N}},
            "body": {"rotation": {0: N, 0.09: [-6, 0, 0], 0.15: [-18, 0, 0], 0.26: [-16, 0, 0], 0.44: [-4, 0, 0],
                                  MELEE_LEN: N}},
            "head": {"rotation": {0: N, 0.15: [10, 0, 0], 0.44: [2, 0, 0], MELEE_LEN: N}},
            "rightLeg": {"rotation": {0: N, 0.09: [24, 0, 0], 0.15: [-104, 0, 0], 0.26: [-96, 0, 0], 0.44: [-20, 0, 0],
                                      MELEE_LEN: N}},
            "rightArm": {"rotation": {0: H, 0.09: [-40, 0, 30], 0.15: [-55, 0, 40], 0.44: [-25, 0, 10], MELEE_LEN: H}},
            "leftArm": {"rotation": {0: N, 0.09: [-30, 0, -30], 0.15: [-35, 0, -40], 0.44: [-8, 0, -10], MELEE_LEN: N}},
        },
        # 回転斬り: その場で一回転しながら斬る
        "spin_slash": {
            "root": {"position": {0: N, 0.08: [0, -1.2, 0], 0.32: [0, -1.6, -1.2], 0.52: [0, -0.4, -0.5],
                                  MELEE_LEN: N},
                     "rotation": {0: N, 0.08: [0, 24, 0], 0.2: [0, -180, 0], 0.32: [0, -336, 0], 0.38: [0, -360, 0],
                                  MELEE_LEN: [0, -360, 0]}},
            "body": {"rotation": {0: N, 0.08: [4, 20, 0], 0.2: [8, 0, 0], 0.38: [8, -10, 0], 0.52: [3, 4, 0],
                                  MELEE_LEN: N}},
            "rightArm": {"rotation": {0: H, 0.08: [-88, 70, 0], 0.2: [-90, -40, 0], 0.32: [-90, -60, 0],
                                      0.52: [-40, -20, 0], MELEE_LEN: H}},
            "leftArm": {"rotation": {0: N, 0.08: [-20, 0, -40], 0.32: [-25, 0, -50], 0.52: [-5, 0, -10],
                                     MELEE_LEN: N}},
        },
        # ジャンプ斬り: しゃがんで跳び、落ちながら斬り下ろす
        "hop_slash": {
            "root": {"position": {0: N, 0.08: [0, -2.6, 0.4], 0.16: [0, 4.5, -1.6], 0.24: [0, 2.4, -2.4],
                                  0.31: [0, -2.2, -2.6], 0.5: [0, -0.6, -1.0], MELEE_LEN: N}},
            "body": {"rotation": {0: N, 0.08: [16, 0, 0], 0.16: [-12, 0, 0], 0.24: [24, 0, 0], 0.31: [20, 0, 0],
                                  0.5: [6, 0, 0], MELEE_LEN: N}},
            "rightArm": {"rotation": {0: H, 0.08: [-40, 20, 0], 0.16: [-175, 0, 8], 0.24: [-40, -10, 0],
                                      0.5: [-25, -8, 0], MELEE_LEN: H}},
            "leftArm": {"rotation": {0: N, 0.08: [-30, 0, -20], 0.16: [-150, 0, -12], 0.24: [-30, 0, -10],
                                     0.5: [-6, 0, -4], MELEE_LEN: N}},
            "rightLeg": {"rotation": {0: N, 0.08: [-30, 0, 0], 0.16: [-20, 0, 0], 0.31: [-30, 0, 0], 0.5: [-8, 0, 0],
                                      MELEE_LEN: N}},
            "leftLeg": {"rotation": {0: N, 0.08: [-30, 0, 0], 0.16: [10, 0, 0], 0.31: [20, 0, 0], 0.5: [5, 0, 0],
                                     MELEE_LEN: N}},
        },
    }
    return M[name]


def melee_anims(pre, moves, anim_fn, hold_r):
    """通常攻撃の 4 連コンボ。moves: [(技, {時刻: [(effect, locator), ...]}), ...] を 4 つ"""
    out = {}
    for i, (name, fx) in enumerate(moves):
        parts = {t: [{"effect": e, "locator": loc} for e, loc in lst] for t, lst in fx.items()}
        a = anim_fn(MELEE_LEN, melee_move(name, hold_r), parts, loop=False)
        a["anim_time_update"] = "v.melee_t"   # 振り始めからの経過時間で再生
        out["animation.%s.melee_%d" % (pre, i)] = a
    return out


def melee_state_entries():
    """待機状態に入れる通常攻撃（振るたびに 0 → 1 → 2 → 3 の順）"""
    return [{"melee_%d" % i: "math.mod(v.atk_n, 4) == %d && v.melee_t < %.2f" % (i, MELEE_LEN)} for i in range(4)]


def mute_controller(ac, name):
    """コントローラーのパーティクルを止める（コンボのモーション側で出すため）"""
    for st in ac["animation_controllers"][name]["states"].values():
        st.pop("particle_effects", None)
    return ac


# ================================================================ 間合いの判断（近接の構え / 遠距離の構え）
# 近接の構え: 相手に近づいて殴る（近距離の技）。遠距離の構え: 近づかれたら離れ、13 マスくらいを保って遠距離の技。
STANCE_TAG = "vb_range"   # 遠距離の構えのあいだ付く目印


def stance_group(own_family, keep=13, flee=8):
    """遠距離の構え: 近すぎる敵からは離れ、遠すぎる相手には keep マスまで近づく"""
    foe = {"any_of": [
        {"all_of": [{"test": "is_family", "subject": "other", "value": "player"},
                    {"test": "has_ability", "subject": "other", "operator": "!=", "value": "instabuild"}]},
        rival_target(own_family)["filters"]]}
    return {
        "minecraft:behavior.avoid_mob_type": {
            "priority": 1, "remove_target": False, "ignore_visibility": True,
            "entity_types": [{"filters": foe, "max_dist": flee, "max_flee": flee + 8,
                              "walk_speed_multiplier": 1.15, "sprint_speed_multiplier": 1.35}]},
        "minecraft:behavior.move_towards_target": {"priority": 3, "speed_multiplier": 1.0, "within_radius": keep},
    }


def split_melee(groups, own_family, keep=13, flee=8):
    """「ai」から近接（melee_attack）を分けて、構えで出し入れできるようにする"""
    groups["ai_melee"] = {"minecraft:behavior.melee_attack": groups["ai"].pop("minecraft:behavior.melee_attack")}
    groups["stance_range"] = stance_group(own_family, keep, flee)
    return groups


def apply_stance_groups(events):
    """AI を止めるイベントでは構えのグループも止め、AI を戻すイベントでは近接の構えで戻す"""
    def fix(o):
        if isinstance(o, dict):
            rm = o.get("remove", {}).get("component_groups")
            ad = o.get("add", {}).get("component_groups")
            if rm is not None and "ai" in rm:
                rm += [g for g in ("ai_melee", "stance_range") if g not in rm]
            if ad is not None and "ai" in ad:
                if "ai_melee" not in ad:
                    ad.append("ai_melee")
                rml = o.setdefault("remove", {}).setdefault("component_groups", [])
                if "stance_range" not in rml:
                    rml.append("stance_range")
                qc = o.setdefault("queue_command", {})
                cmds = qc.get("command", [])
                cmds = [cmds] if isinstance(cmds, str) else list(cmds)
                qc["command"] = cmds + ["tag @s remove %s" % STANCE_TAG]
            for v in list(o.values()):
                fix(v)
        elif isinstance(o, list):
            for x in o:
                fix(x)
    fix(events)
    return events


def stance_events(not_busy, melee_w, range_w, low_hp, low_bias=1.6):
    """vb:stance: 構えを選び直す（HP が減ると遠距離寄りに）。演出中・一時停止中は何もしない"""
    ok = list(not_busy["all_of"]) + [{"test": "has_tag", "subject": "self", "operator": "!=", "value": PAUSE_TAG}]

    def pick(wm, wr):
        out = []
        if wm > 0:
            out.append({"weight": wm, "add": {"component_groups": ["ai_melee"]},
                        "remove": {"component_groups": ["stance_range"]},
                        "queue_command": {"command": ["tag @s remove %s" % STANCE_TAG]}})
        if wr > 0:
            out.append({"weight": wr, "add": {"component_groups": ["stance_range"]},
                        "remove": {"component_groups": ["ai_melee"]},
                        "queue_command": {"command": ["tag @s add %s" % STANCE_TAG]}})
        return out
    hi = {"test": "actor_health", "subject": "self", "operator": ">", "value": low_hp}
    lo = {"test": "actor_health", "subject": "self", "operator": "<=", "value": low_hp}
    return {"vb:stance": {"sequence": [
        {"filters": {"all_of": ok + [hi]}, "randomize": pick(melee_w, range_w)},
        {"filters": {"all_of": ok + [lo]}, "randomize": pick(int(melee_w / low_bias), int(range_w * low_bias))}]}}


STANCE_ANIM = {"animation_length": 4.0, "loop": True, "timeline": {"2.00": ["/event entity @s vb:stance"]}}


def stance_filters(near_tag):
    """技選び: 近接の構えで敵が近い → 近距離の技 / それ以外（遠距離の構え・敵が遠い）→ 遠距離の技"""
    near = {"all_of": [{"test": "has_tag", "subject": "self", "value": near_tag},
                       {"test": "has_tag", "subject": "self", "operator": "!=", "value": STANCE_TAG}]}
    other = {"any_of": [{"test": "has_tag", "subject": "self", "operator": "!=", "value": near_tag},
                        {"test": "has_tag", "subject": "self", "value": STANCE_TAG}]}
    return near, other


# ================================================================ 声・足音 / 守りの反応 / 瀕死の演出
def entity_sounds(entries):
    """RP の sounds.json: 殴られたときの声・倒れたときの声・足音（バニラの音を、キャラごとに高さを変えて使う）.

    entries: {識別子: (声の高さ, 足音の大きさ)}
    """
    ents = {}
    for ident, (pitch, step_vol) in entries.items():
        ents[ident] = {"volume": 1.0, "pitch": [round(pitch * 0.94, 2), round(pitch * 1.06, 2)], "events": {
            "hurt": {"sound": "game.player.hurt", "volume": 0.9},
            "death": {"sound": "game.player.die", "volume": 1.0},
            "step": {"sound": "step.stone", "volume": step_vol, "pitch": 1.0}}}
    return {"entity_sounds": {"entities": ents}}


def react_scripts(prop):
    """守りの反応: プロパティ prop が変わった瞬間から 0.4 秒、v.react が 0 → 1 → 0"""
    return (["v.react_prev = 0.0;", "v.react_t = -10.0;", "v.react = 0.0;"],
            ["v.react_now = q.property('%s');" % prop,
             "v.react_t = (v.react_now != v.react_prev) ? q.life_time : v.react_t;",
             "v.react_prev = v.react_now;",
             "v.react = (q.life_time - v.react_t < 0.4) ? math.sin((q.life_time - v.react_t) * 450) : 0.0;"])


def react_property(prop):
    return {prop: {"type": "int", "range": [0, 7], "default": 0, "client_sync": True}}


def react_bump(prop):
    """イベントに足す set_property（反応の合図。0〜7 を回る）"""
    return {prop: "math.mod(q.property('%s') + 1, 8)" % prop}


def add_react_to_client(desc, prop):
    ini, pre = react_scripts(prop)
    sc = desc.setdefault("scripts", {})
    sc["initialize"] = sc.get("initialize", []) + ini
    sc["pre_animation"] = sc.get("pre_animation", []) + pre
    return desc


def add_state_anim(ac, name, anim):
    """コントローラーの（撃破以外の）すべての状態に、アニメーションを重ねる"""
    for sname, st in ac["animation_controllers"][name]["states"].items():
        if sname != "death" and "animations" in st and anim not in st["animations"]:
            st["animations"].append(anim)
    return ac


DESPERATE = "q.is_alive && q.health < q.max_health * 0.15"   # 瀕死（HP 15% 未満）


def desperate_anim():
    return {"loop": True, "animation_length": 0.3, "particle_effects": {
        "0.00": [{"effect": "desperate", "locator": "right_foot"}], "0.15": [{"effect": "desperate", "locator": "left_foot"}]}}


def desperate_particle(ns, glow_tex):
    """瀕死: 足元から赤い火の粉が立ちのぼる"""
    return {"format_version": "1.10.0", "particle_effect": {
        "description": {"identifier": ns + ":desperate", "basic_render_parameters": {
            "material": "particles_add", "texture": "textures/particle/" + glow_tex}},
        "components": {
            "minecraft:emitter_rate_instant": {"num_particles": 6},
            "minecraft:emitter_lifetime_once": {"active_time": 0.1},
            "minecraft:emitter_shape_disc": {"radius": 0.7, "plane_normal": "y", "surface_only": False,
                                             "direction": [0, 1, 0], "offset": [0, 0.1, 0]},
            "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(0.6, 1.1)"},
            "minecraft:particle_initial_speed": "math.random(0.8, 2.0)",
            "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 1.2, 0], "linear_drag_coefficient": 1.2},
            "minecraft:particle_appearance_billboard": {
                "size": ["0.08 + v.particle_random_1 * 0.06", "0.08 + v.particle_random_1 * 0.06"],
                "facing_camera_mode": "lookat_xyz",
                "uv": {"texture_width": 1, "texture_height": 1, "uv": [0, 0], "uv_size": [1, 1]}},
            "minecraft:particle_appearance_tinting": {"color": {
                "interpolant": "v.particle_age / v.particle_lifetime",
                "gradient": {"0.00": "#FFFF6030", "0.50": "#FFD01818", "1.00": "#00300000"}}}}}}


def brushup_files(bp, rp, cfg):
    """ビルドしたパックに、声・足音・守りの反応・瀕死の演出を足す（zip にする直前に呼ぶ）.

    cfg: id, ns, prop（反応用のプロパティ。無ければ None）, react_events, react_anim, prefix, main_ctrl, glow, pitch
    """
    import glob
    import json
    import os

    def load(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def save(p, d):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    prop, ns, prefix = cfg.get("prop"), cfg["ns"], cfg["prefix"]
    # 1. 本体: 反応の合図（プロパティ）を、守りのイベントで回す
    if prop:
        for p in glob.glob(os.path.join(bp, "entities", "*.json")):
            d = load(p)
            ent = d.get("minecraft:entity", {})
            if ent.get("description", {}).get("identifier") != cfg["id"]:
                continue
            ent["description"].setdefault("properties", {}).update(react_property(prop))
            for name in cfg["react_events"]:
                e = ent["events"][name]
                if "sequence" in e:
                    e["sequence"].append({"set_property": react_bump(prop)})
                else:
                    e.setdefault("set_property", {}).update(react_bump(prop))
            save(p, d)
    # 2. クライアント: メインのコントローラーを使うもの（本体・分身）に、反応と瀕死のアニメーションを登録
    for p in glob.glob(os.path.join(rp, "entity", "*.json")):
        d = load(p)
        desc = d["minecraft:client_entity"]["description"]
        animate = [a if isinstance(a, str) else list(a)[0] for a in desc.get("scripts", {}).get("animate", [])]
        if "main" not in animate:
            continue
        desc["animations"]["react"] = prefix + ".react"
        desc["animations"]["desperate"] = prefix + ".desperate"
        desc.setdefault("particle_effects", {})["desperate"] = ns + ":desperate"
        if prop and desc["identifier"] == cfg["id"]:
            add_react_to_client(desc, prop)
        save(p, d)
    # 3. アニメーション（別ファイル）
    react = cfg.get("react_anim") or {"loop": True, "bones": {}}
    save(os.path.join(rp, "animations", ns + "_brushup.animation.json"), {"format_version": "1.10.0", "animations": {
        prefix + ".react": react, prefix + ".desperate": desperate_anim()}})
    # 4. コントローラー: 撃破以外のすべての状態に重ねる
    for p in glob.glob(os.path.join(rp, "animation_controllers", "*.json")):
        d = load(p)
        if cfg["main_ctrl"] in d.get("animation_controllers", {}):
            add_state_anim(d, cfg["main_ctrl"], "react")
            add_state_anim(d, cfg["main_ctrl"], {"desperate": DESPERATE})
            save(p, d)
    # 5. 瀕死のパーティクル / 6. 声と足音
    save(os.path.join(rp, "particles", "desperate.json"), desperate_particle(ns, cfg["glow"]))
    sp = os.path.join(rp, "sounds.json")
    snd = load(sp) if os.path.exists(sp) else {}
    snd.setdefault("entity_sounds", {}).setdefault("entities", {}).update(
        entity_sounds({cfg["id"]: (cfg["pitch"], 0.18)})["entity_sounds"]["entities"])
    save(sp, snd)
