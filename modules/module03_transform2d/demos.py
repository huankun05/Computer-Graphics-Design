# -*- coding: utf-8 -*-
"""
=====================================================================
 modules/module03_transform2d/demos.py — 模块三演示页（二维变换）
=====================================================================
四页：平移 / 旋转 / 缩放 / 复合变换。参数卡给变换量；
默认把"参数算出的最终矩阵"按 t∈(0,1] 逐帧施加（原位平滑动画），
逐帧对同一个图形做仿射变换并光栅化；监视器里的矩阵始终是最终值，
不展示中途矩阵（动画只是过渡，不是另一套参数）。
勾选「分解演示」改成逐个精确矩阵：旋转 3 阶段 / 缩放 3 阶段 / 复合 5 阶段，
每个阶段内部同样逐帧动画（STAGE_FRAMES 帧），阶段矩阵常显不随帧跳动。
复合页默认勾选分解——把五步合成一个 M 会同时发生平移+旋转+缩放，看不出过程。

演示对象就是演示画布上已有的图元（第五十五轮）：
  选中哪个图元就对哪个做变换；没有选中时取画布上最后一个图元。
  不再保留内置五边形/「对象来源」下拉——先在画布上画好元素，
  再在它身上做平移/旋转/缩放/复合，和模块二"画什么就演示什么"一致。
  旋转/缩放轴心取该图元自身包围盒中心；每帧克隆后施加矩阵，
  画布上的原件由 demo_view 在播放期间隐藏，播完恢复（起点+终态对照）。

所有页面共用 3×3 仿射矩阵内核（algorithms/transform2d.py），
与画布里的拖动/手柄/数值变换是同一套代码，不是另写演示逻辑。
=====================================================================
"""

import copy

from PySide6.QtWidgets import (QCheckBox, QGridLayout, QLabel, QSpinBox,
                               QVBoxLayout)

from algorithms import transform2d as tf
from algorithms.steps import (GUIDE_HIT, GUIDE_MARK, GUIDE_REF, Step,
                              arrow_guide, line_guide, point_guide)
from core.geom import bbox_of
from core.rasterizer import rasterize
from core.shapes import restore, snapshot, transform_shape

EMPTY_HINT = ("演示画布上还没有图元：先到模块二任一演示页画一个，"
              "回来选中它再播放")

ANIM_FRAMES = 18        # 原位动画帧数：只影响画面平滑度，不改展示的矩阵
STAGE_FRAMES = 6        # 分解演示：每个阶段内部再分几帧做平滑动画
HOLD_FRAMES = 2         # 每个阶段末尾多停几帧（0.5 秒），阶段边界更好辨认


def _shape_at(src, m):
    """克隆来源图元并施加矩阵（不动画布上的原件）。"""
    sh = copy.copy(src)
    restore(sh, snapshot(src))
    # 动画演示的是【完整图形】：擦掉的像素与裁剪窗口都不参与
    sh.erased = set()
    sh.cuts = []
    sh.visible = True
    transform_shape(sh, m)
    return sh


def _shape_center(shape) -> tuple:
    """图元包围盒中心（模拟像素坐标），作为旋转/缩放轴心。"""
    bb = bbox_of(shape)
    if bb is None:
        return (0.0, 0.0)
    return ((bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0)


def _probe_point(shape) -> tuple:
    """用于逐点演算的取样点：图元包围盒左上角（模拟像素坐标）。

    取角点而不是中心：中心是旋转/缩放轴心，矩阵作用后原地不动，
    看不出"逐点代入"；角点在旋转/缩放下位移明显，便于对照。
    """
    bb = bbox_of(shape)
    if bb is None:
        return (0, 0)
    return (int(bb[0]), int(bb[1]))


class _TransformDemoBase:
    title = "平移变换"
    icon = "cursor"
    kind = "canvas"
    freehand_replay = False
    trails = False          # 替换式渲染：每帧只显示当前图形，不累积拖影
    default_fps = 4         # 每帧约 250ms：动画平滑，又不会拖太久
    variables = {"步": "进度", "源点 P": "取样点（包围盒左上角）",
                 "映射 P′": "P 经 M 变换后的坐标", "矩阵": "当前矩阵"}
    pivot_marks = True      # 是否标注轴心（平移无轴心）
    probe_guides = True     # 画布上是否画 P→P′ 箭头（分段演示页不要）
    show_origin = False     # 是否标出原点 O 与"轴心→原点"虚线（分段演示页）
    decomposable = False    # 参数卡是否给「分解演示」开关（旋转/缩放给）
    stage_pausable = False  # 参数卡是否给「按阶段暂停」开关（复合页给）
    always_staged = False   # 是否始终按阶段演示（复合页给，取消勾选的对照已移除）
    formula = ""

    def __init__(self):
        self._spins = {}
        self._decomp = None           # 「分解演示」复选框（decomposable 页才有）
        self._canvas = None
        self._pinned_source = None    # 上一次生成步骤流时用的图元
        self._pivot_xy = (0.0, 0.0)
        self._final = None            # 原位动画要展示（而非逐帧变化）的最终矩阵

    def _defs(self):
        return [("n", "步数", 12, 2, 40)]

    def build_params(self, lay: QVBoxLayout):
        self._spins = {}
        self._decomp = None
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        for i, (key, cn, dft, mn, mx) in enumerate(self._defs()):
            lab = QLabel(cn)
            lab.setObjectName("secondary")
            lab.setMinimumWidth(56)
            sb = QSpinBox()
            sb.setRange(mn, mx)
            sb.setValue(dft)
            sb.setFixedWidth(92)
            grid.addWidget(lab, i, 0)
            grid.addWidget(sb, i, 1)
            self._spins[key] = sb
        grid.setColumnStretch(2, 1)
        lay.addLayout(grid)
        if self.decomposable:
            self._decomp = QCheckBox("分解演示：搬到原点 → 变换 → 搬回")
            self._decomp.setObjectName("secondary")
            self._decomp.setChecked(False)
            lay.addWidget(self._decomp)
        if self.stage_pausable:
            self._pause_stage = QCheckBox("按阶段暂停：每执行完一个阶段自动暂停")
            self._pause_stage.setObjectName("noRegen")   # 只影响播放，不重生成
            lay.addWidget(self._pause_stage)
        note = QLabel("动画对象 = 画布上选中的图元（未选中取最后一个）；"
                      "画面逐帧形变，矩阵只显示最终值/阶段终值")
        note.setObjectName("secondary")
        note.setWordWrap(True)
        lay.addWidget(note)

    def collect(self) -> dict:
        if self._spins:
            p = {k: sb.value() for k, sb in self._spins.items()}
        else:
            p = {k: dft for k, _cn, dft, _mn, _mx in self._defs()}
        p["decompose"] = bool(self._decomp and self._decomp.isChecked())
        return p

    def tool_selector(self, canvas):
        """演示画布装选择工具：选中哪个图元，就对哪个做变换动画。

        选中框/手柄只用于指定对象；播放一开始 demo_view 会清掉选集，
        不会混进动画画面。
        """
        self._canvas = canvas
        from modules.module03_transform2d.tools import Transform2DTool
        if not isinstance(getattr(canvas, "tool", None), Transform2DTool):
            canvas.set_tool(Transform2DTool(canvas))

    def playback_source(self):
        """当前动画对象：选中优先，其次上次生成用的图元，最后画布最后一个。"""
        cv = self._canvas
        if cv is None:
            return None
        shapes = list(getattr(cv, "shapes", []))
        if not shapes:
            return None
        sel = getattr(cv, "_selected_shape", None)
        if sel is not None and any(sel is s for s in shapes):
            return sel
        pinned = self._pinned_source
        if pinned is not None and any(pinned is s for s in shapes):
            return pinned
        return shapes[-1]

    @property
    def empty_hint(self):
        return "" if self.playback_source() is not None else EMPTY_HINT

    def reference_pixels(self):
        """初始态像素（未施加变换的源图元轮廓+填充）。

        播放/单步期间由演示壳作为橙色参照层常显，与当前帧（蓝色）
        区分；到达末帧时清除——画面只留终态（用户指定交互）。
        """
        src = self.playback_source()
        if src is None:
            return []
        shape = _shape_at(src, tf.identity())
        outline, fill = rasterize(shape)
        return sorted(set(outline) | set(fill))

    # ---- 子类实现：t → 矩阵（不分段的页用） ----
    def _matrix(self, p: dict, t: float):
        return tf.identity()

    def _stage_anim(self, stage, target, fn, disp=None, origin=True,
                    moving=False, note=""):
        """把一个分解阶段展开成 STAGE_FRAMES 帧平滑动画 + 末尾停留帧。

        fn(t) → 该帧实际施加的矩阵（t = 1/STAGE_FRAMES … 1）；
        target 是该阶段的精确矩阵（监视器/P′ 常显它，不随帧跳动）；
        disp 是这一阶段要展示的读数（角度/缩放等）；
        末尾 HOLD_FRAMES 帧停在 target 上，让阶段之间的边界看得清。
        """
        out = []
        for i in range(1, STAGE_FRAMES + 1):
            out.append({"m": fn(i / STAGE_FRAMES), "q_matrix": target,
                        "stage": stage, "origin": origin, "moving": moving,
                        "disp": {"矩阵": target, **(disp or {})},
                        "note": note})
        for _ in range(HOLD_FRAMES):
            out.append({"m": target, "q_matrix": target, "stage": stage,
                        "origin": origin, "moving": moving,
                        "disp": {"矩阵": target, **(disp or {})},
                        "note": f"{note}（阶段结束，停留观察）"})
        return out

    def _frames(self, p: dict) -> list:
        """步骤流：默认一帧，施加参数算出的最终矩阵。

        返回 [{"m": 该帧实际施加的矩阵, "q_matrix": 监视器/P′ 用的最终矩阵,
               "stage": 阶段名, "note": 人话解释,
               "origin": 是否标出原点与搬移虚线,
               "moving": 该帧是否"轴心→原点"的平移,
               "disp": 该阶段要展示的读数（缺省则走 _values）}]；各页 override。
        """
        return [{"m": self._matrix(p, 1.0)}]

    def _values(self, p: dict, k: int, n: int, m) -> dict:
        return {"步": f"{k}/{n}", "矩阵": m}

    def _guides(self, probe, q, fr) -> list:
        """画布注记：P→P′ 箭头（平移页）/ 轴心 + 原点 + 虚线（分段页）。"""
        guides = []
        if self.probe_guides:
            guides = [point_guide(probe, "P", GUIDE_MARK),
                      arrow_guide(probe, q),
                      point_guide(q, "P′", GUIDE_HIT)]
        if self.pivot_marks:
            c = (int(round(self._pivot_xy[0])),
                 int(round(self._pivot_xy[1])))
            guides.append(point_guide(c, "轴心", GUIDE_REF))
            # 原位单步变换不涉及原点，只有分解演示才画 O 与搬移虚线
            if self.show_origin and fr.get("origin"):
                guides.append(point_guide((0, 0), "O", GUIDE_REF))
                if fr.get("moving"):
                    guides.append(line_guide(c, (0, 0), GUIDE_REF, dash=True))
        return guides

    def make_steps(self, params):
        src = self.playback_source()
        if src is None:
            return []             # 空画布：由 empty_hint 提示，不出示例
        self._pinned_source = src
        self._pivot_xy = _shape_center(src)
        probe = _probe_point(src)
        px, py = probe
        steps = []
        frames = self._frames(params)
        n = len(frames)
        for k, fr in enumerate(frames, start=1):
            m = fr["m"]
            shape = _shape_at(src, m)
            outline, fill = rasterize(shape)
            # ---- 逐点演算：P --(M)--> P′（数值进监视器，箭头可选） ----
            # 原位动画帧只换画面，P′ 按最终矩阵算（不随帧跳动）
            qx, qy = tf.apply(fr.get("q_matrix", m), probe)
            q = (int(round(qx)), int(round(qy)))
            if "disp" in fr:
                # 分解阶段帧：读数由该阶段给出（矩阵=阶段目标，不随帧跳动）
                values = {"进度": f"{k}/{n}", **fr["disp"]}
            else:
                values = self._values(params, k, n, m)
            values.update({"源点 P": f"({px}, {py})",
                           "映射 P′": f"({q[0]}, {q[1]})"})
            stage = fr.get("stage", "")
            if stage:
                values = {"阶段": stage, **values}   # 阶段行置顶
            note = fr.get("note") or \
                f"第 {k}/{n} 步｜P({px}, {py}) → M → P′({q[0]}, {q[1]})"
            steps.append(Step(sorted(set(outline) | set(fill)), values, note,
                              guides=self._guides(probe, q, fr)))
        return steps


class TranslateDemo(_TransformDemoBase):
    title = "平移"
    icon = "cursor"
    pivot_marks = False
    default_fps = 4
    variables = {"阶段": "当前阶段", "进度": "进度",
                 "dx": "dx", "dy": "dy",
                 "源点 P": "取样点 P", "映射 P′": "映射 P′",
                 "矩阵": "最终矩阵 T"}
    formula = ("平移矩阵（屏幕坐标）\n"
               "x′ = x + dx，y′ = y + dy\n"
               "各点同向等量移动，形状/大小不变\n"
               "T(dx, dy) =")
    formula_matrix = [[1, 0, "dx"], [0, 1, "dy"], [0, 0, 1]]

    def _defs(self):
        return [("dx", "dx", 8, -40, 40), ("dy", "dy", 5, -40, 40)]

    def _matrix(self, p, t):
        return tf.translation(p["dx"], p["dy"])

    def _frames(self, p):
        """动画：逐帧平移到位；展示的矩阵始终是最终的 T(dx,dy)。"""
        dx, dy = p["dx"], p["dy"]
        final = tf.translation(dx, dy)
        self._final = final
        return [{"m": tf.translation(dx * i / ANIM_FRAMES, dy * i / ANIM_FRAMES),
                 "q_matrix": final, "stage": "施加最终矩阵 T(dx,dy)",
                 "note": "动画：按最终矩阵逐帧移到终点（中间过程不显示矩阵）"}
                for i in range(1, ANIM_FRAMES + 1)]

    def _values(self, p, k, n, m):
        return {"进度": f"{k}/{n}", "dx": f"{p['dx']}", "dy": f"{p['dy']}",
                "矩阵": self._final}


class RotateDemo(_TransformDemoBase):
    title = "旋转"
    icon = "replay"
    probe_guides = False    # 分段演示：不画 P→P′ 箭头，只标轴心与原点
    show_origin = True
    decomposable = True
    default_fps = 4
    variables = {"阶段": "本阶段矩阵", "进度": "进度",
                 "角度": "转角 θ", "轴心": "旋转中心",
                 "源点 P": "取样点 P", "映射 P′": "映射 P′",
                 "矩阵": "矩阵 M"}
    formula = ("绕轴心 (cx, cy) 旋转 θ（屏幕 y 向下，正角=顺时针）\n"
               "M = T(cx,cy) · R(θ) · T(-cx,-cy)\n"
               "= 轴心移到原点 → 绕原点转 θ → 轴心移回\n"
               "轴心 = 包围盒中心；圆旋转后变为椭圆\n"
               "R(θ) =")
    formula_matrix = [["cosθ", "−sinθ", 0], ["sinθ", "cosθ", 0], [0, 0, 1]]

    def _defs(self):
        return [("angle", "角度 °", 75, -360, 360)]

    def _frames(self, p):
        """默认：原位动画（逐帧绕轴心转到位，矩阵只展示最终的 M）；
        勾选「分解演示」后三个精确矩阵各自再展开成一段平滑动画：
        ① T(-c) → ② R(θ)·T(-c) → ③ T(c)·R(θ)·T(-c)。
        """
        cx, cy = self._pivot_xy
        a = float(p["angle"])
        ax = f"{cx:.0f},{cy:.0f}"
        minus = tf.translation(-cx, -cy)
        m2 = tf.compose(tf.rotation(a), minus)
        final = tf.compose(tf.translation(cx, cy), m2)
        self._final = final
        if not p.get("decompose"):
            return [{"m": tf.compose(tf.translation(cx, cy),
                                     tf.rotation(a * i / ANIM_FRAMES), minus),
                     "q_matrix": final, "stage": "施加最终矩阵 M",
                     "note": "动画：绕轴心旋转到 θ，画面逐帧形变（矩阵不随帧变化）"}
                    for i in range(1, ANIM_FRAMES + 1)]
        keep = {"角度": "0°", "轴心": ax}
        full = {"角度": f"{a:.0f}°", "轴心": ax}
        frames = []
        frames += self._stage_anim(
            "① 轴心移到原点", minus,
            lambda t: tf.translation(-cx * t, -cy * t), keep, moving=True,
            note=f"① M₁ = T(−c)：轴心 ({cx:.0f}, {cy:.0f}) 逐帧移到原点 O")
        frames += self._stage_anim(
            "② 绕原点旋转", m2,
            lambda t: tf.compose(tf.rotation(a * t), minus), full,
            note=f"② M₂ = R({a:.0f}°)·M₁：绕原点 O 逐帧旋转 {a:.0f}°")
        frames += self._stage_anim(
            "③ 轴心移回原位", final,
            lambda t: tf.compose(tf.translation(cx * t, cy * t), m2), full,
            moving=True,
            note=f"③ M₃ = T(c)·M₂：轴心逐帧移回 ({cx:.0f}, {cy:.0f})，M₃ 即最终矩阵")
        return frames

    def _values(self, p, k, n, m):
        # 仅原位动画走到这里（分解帧自带 disp）
        return {"进度": f"{k}/{n}", "角度": f"{float(p['angle']):.0f}°",
                "轴心": f"{self._pivot_xy[0]:.0f},{self._pivot_xy[1]:.0f}",
                "矩阵": self._final}



class ScaleDemo(_TransformDemoBase):
    title = "缩放"
    icon = "zoom-in"
    probe_guides = False
    show_origin = True
    decomposable = True
    default_fps = 4
    variables = {"阶段": "本阶段矩阵", "进度": "进度",
                 "sx": "sx", "sy": "sy",
                 "源点 P": "取样点 P", "映射 P′": "映射 P′",
                 "矩阵": "矩阵 M"}
    formula = ("绕轴心 (cx, cy) 缩放（屏幕坐标）\n"
               "M = T(cx,cy) · S(sx,sy) · T(-cx,-cy)\n"
               "= 轴心移到原点 → 绕原点缩放 → 轴心移回\n"
               "轴心 = 包围盒中心；sx≠sy 时圆变椭圆\n"
               "S(sx, sy) =")
    formula_matrix = [["sx", 0, 0], [0, "sy", 0], [0, 0, 1]]

    def _defs(self):
        return [("sx", "sx %", 160, 5, 800), ("sy", "sy %", 70, 5, 800)]

    def _frames(self, p):
        """默认：原位动画（逐帧绕轴心缩放到位，矩阵只展示最终的 M）；
        勾选「分解演示」后三个精确矩阵各自再展开成一段平滑动画：
        ① T(-c) → ② S(sx,sy)·T(-c) → ③ T(c)·S·T(-c)。
        """
        cx, cy = self._pivot_xy
        tx, ty = p["sx"] / 100.0, p["sy"] / 100.0
        minus = tf.translation(-cx, -cy)
        m2 = tf.compose(tf.scaling(tx, ty), minus)
        final = tf.compose(tf.translation(cx, cy), m2)
        self._final = final
        if not p.get("decompose"):
            frames = []
            for i in range(1, ANIM_FRAMES + 1):
                t = i / ANIM_FRAMES
                frames.append({
                    "m": tf.compose(tf.translation(cx, cy),
                                    tf.scaling(1.0 + (tx - 1.0) * t,
                                               1.0 + (ty - 1.0) * t), minus),
                    "q_matrix": final, "stage": "施加最终矩阵 M",
                    "note": "动画：绕轴心缩放到 sx/sy，画面逐帧形变（矩阵不随帧变化）"})
            return frames
        keep = {"sx": "1.00", "sy": "1.00"}
        full = {"sx": f"{tx:.2f}", "sy": f"{ty:.2f}"}
        frames = []
        frames += self._stage_anim(
            "① 轴心移到原点", minus,
            lambda t: tf.translation(-cx * t, -cy * t), keep, moving=True,
            note=f"① M₁ = T(−c)：轴心 ({cx:.0f}, {cy:.0f}) 逐帧移到原点 O")
        frames += self._stage_anim(
            "② 绕原点缩放", m2,
            lambda t: tf.compose(tf.scaling(1.0 + (tx - 1.0) * t,
                                            1.0 + (ty - 1.0) * t), minus),
            full, note=f"② M₂ = S({tx:.2f}, {ty:.2f})·M₁：绕原点 O 逐帧缩放")
        frames += self._stage_anim(
            "③ 轴心移回原位", final,
            lambda t: tf.compose(tf.translation(cx * t, cy * t), m2), full,
            moving=True,
            note=f"③ M₃ = T(c)·M₂：轴心逐帧移回 ({cx:.0f}, {cy:.0f})，M₃ 即最终矩阵")
        return frames

    def _values(self, p, k, n, m):
        # 仅原位动画走到这里（分解帧自带 disp）
        return {"进度": f"{k}/{n}", "sx": f"{p['sx'] / 100.0:.2f}",
                "sy": f"{p['sy'] / 100.0:.2f}", "矩阵": self._final}


class ComposeDemo(_TransformDemoBase):
    title = "复合变换"
    icon = "sparkle"
    probe_guides = False
    show_origin = True
    stage_pausable = True       # 每阶段末尾可自动暂停，便于逐步观察
    always_staged = True        # 始终按五阶段演示（没有"合成一个 M"的对照）
    default_fps = 4
    variables = {"阶段": "本阶段矩阵", "进度": "进度",
                 "角度": "转角 θ", "缩放": "缩放 s",
                 "源点 P": "取样点 P", "映射 P′": "映射 P′",
                 "矩阵": "矩阵 M"}
    formula = ("复合变换（右乘先作用）\n"
               "M = T(dx,dy) · T(c) · R(θ) · S(sx,sy) · T(-c)\n"
               "五个精确矩阵依次相乘：\n"
               "T(-c) → S → R → T(c) → T(dx,dy)\n"
               "顺序不可交换（R·S ≠ S·R）")

    def _defs(self):
        return [("dx", "dx", 10, -40, 40), ("dy", "dy", 4, -40, 40),
                ("angle", "角度 °", 60, -360, 360),
                ("sx", "sx %", 140, 5, 800)]

    def _frames(self, p):
        """始终五阶段动画：
        ① T(-c) ② S·T(-c) ③ R·S·T(-c) ④ T(c)·R·S·T(-c)
        ⑤ T(dx,dy)·T(c)·R·S·T(-c)，每个阶段内部逐帧平滑动画 + 末尾停留。
        不再提供"合成一个 M"的对照——五步合一后同时平移/旋转/缩放，
        看不出先后顺序（用户指定）。
        """
        cx, cy = self._pivot_xy
        ang, sc = float(p["angle"]), p["sx"] / 100.0
        dx, dy = float(p["dx"]), float(p["dy"])
        minus = tf.translation(-cx, -cy)
        m2 = tf.compose(tf.scaling(sc, sc), minus)
        m3 = tf.compose(tf.rotation(ang), tf.scaling(sc, sc), minus)
        m4 = tf.compose(tf.translation(cx, cy), tf.rotation(ang),
                        tf.scaling(sc, sc), minus)
        m5 = tf.compose(tf.translation(dx, dy), m4)
        self._final = m5
        keep = {"角度": "0°", "缩放": "×1.00"}
        turned = {"角度": f"{ang:.0f}°", "缩放": f"×{sc:.2f}"}
        frames = []
        frames += self._stage_anim(
            "① 轴心移到原点", minus,
            lambda t: tf.translation(-cx * t, -cy * t), keep, moving=True,
            note=f"① M₁ = T(−c)：轴心 ({cx:.0f}, {cy:.0f}) 逐帧移到原点 O")
        frames += self._stage_anim(
            "② 缩放 S", m2,
            lambda t: tf.compose(tf.scaling(1.0 + (sc - 1.0) * t,
                                            1.0 + (sc - 1.0) * t), minus),
            {"角度": "0°", "缩放": f"×{sc:.2f}"},
            note=f"② M₂ = S({sc:.2f})·M₁：绕原点 O 逐帧缩放")
        frames += self._stage_anim(
            "③ 旋转 R", m3,
            lambda t: tf.compose(tf.rotation(ang * t),
                                 tf.scaling(sc, sc), minus), turned,
            note=f"③ M₃ = R({ang:.0f}°)·M₂：绕原点 O 逐帧旋转")
        frames += self._stage_anim(
            "④ 轴心移回原位", m4,
            lambda t: tf.compose(tf.translation(cx * t, cy * t), m3), turned,
            moving=True,
            note=f"④ M₄ = T(c)·M₃：轴心逐帧移回 ({cx:.0f}, {cy:.0f})")
        frames += self._stage_anim(
            "⑤ 平移 T(dx,dy)", m5,
            lambda t: tf.compose(tf.translation(dx * t, dy * t), m4), turned,
            note=f"⑤ M₅ = T({dx},{dy})·M₄：再整体逐帧平移，M₅ 即最终矩阵")
        return frames


def create_demos():
    return [TranslateDemo(), RotateDemo(), ScaleDemo(), ComposeDemo()]
