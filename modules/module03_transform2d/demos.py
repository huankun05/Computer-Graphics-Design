# -*- coding: utf-8 -*-
"""
=====================================================================
 modules/module03_transform2d/demos.py — 模块三演示页（二维变换）
=====================================================================
四页：平移 / 旋转 / 缩放 / 复合变换。参数卡给变换量与步数，
步骤流把矩阵按 t∈(0,1] 插值，逐帧对同一个图形做仿射变换并光栅化
——动画看到的就是矩阵作用下的真实像素轨迹（拖影 = 运动路径）。

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

from PySide6.QtWidgets import QGridLayout, QLabel, QSpinBox, QVBoxLayout

from algorithms import transform2d as tf
from algorithms.steps import Step
from core.geom import bbox_of
from core.rasterizer import rasterize
from core.shapes import restore, snapshot, transform_shape

EMPTY_HINT = ("演示画布上还没有图元：先到模块二任一演示页画一个，"
              "回来选中它再播放")


def _shape_at(src, m):
    """克隆来源图元并施加矩阵（不动画布上的原件）。"""
    sh = copy.copy(src)
    restore(sh, snapshot(src))
    sh.erased = set()
    sh.visible = True
    transform_shape(sh, m)
    return sh


def _shape_center(shape) -> tuple:
    """图元包围盒中心（模拟像素坐标），作为旋转/缩放轴心。"""
    bb = bbox_of(shape)
    if bb is None:
        return (0.0, 0.0)
    return ((bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0)


class _TransformDemoBase:
    title = "平移变换"
    icon = "cursor"
    kind = "canvas"
    freehand_replay = False
    trails = False          # 替换式渲染：每帧只显示当前图形，不累积拖影
    default_fps = 2         # 每帧约 500ms，留出观察停留
    variables = {"步": "进度", "矩阵": "当前矩阵"}
    formula = ""

    def __init__(self):
        self._spins = {}
        self._canvas = None
        self._pinned_source = None    # 上一次生成步骤流时用的图元
        self._pivot_xy = (0.0, 0.0)

    def _defs(self):
        return [("n", "步数", 12, 2, 40)]

    def build_params(self, lay: QVBoxLayout):
        self._spins = {}
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
        note = QLabel("动画对象 = 画布上选中的图元（未选中取最后一个）；逐帧施加矩阵")
        note.setObjectName("secondary")
        note.setWordWrap(True)
        lay.addWidget(note)

    def collect(self) -> dict:
        if self._spins:
            return {k: sb.value() for k, sb in self._spins.items()}
        return {k: dft for k, _cn, dft, _mn, _mx in self._defs()}

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

    # ---- 子类实现：t → 矩阵 ----
    def _matrix(self, p: dict, t: float):
        return tf.identity()

    def _values(self, p: dict, k: int, n: int, m) -> dict:
        return {"步": f"{k}/{n}", "矩阵": _mat_text(m)}

    def make_steps(self, params):
        n = max(2, int(params.get("n", 12)))
        src = self.playback_source()
        if src is None:
            return []             # 空画布：由 empty_hint 提示，不出示例
        self._pinned_source = src
        self._pivot_xy = _shape_center(src)
        steps = []
        for k in range(1, n + 1):
            t = k / n
            m = self._matrix(params, t)
            shape = _shape_at(src, m)
            outline, fill = rasterize(shape)
            steps.append(Step(sorted(set(outline) | set(fill)),
                              self._values(params, k, n, m),
                              f"t = {t:.2f}"))
        return steps


def _mat_text(m) -> str:
    return (f"[{m[0][0]:.2f} {m[0][1]:.2f} {m[0][2]:.1f} | "
            f"{m[1][0]:.2f} {m[1][1]:.2f} {m[1][2]:.1f}]")


class TranslateDemo(_TransformDemoBase):
    title = "平移"
    icon = "cursor"
    variables = {"步": "进度", "dx": "累计 dx", "dy": "累计 dy"}
    formula = ("平移矩阵（屏幕坐标）\n"
               "T(dx, dy) = [1 0 dx]\n"
               "            [0 1 dy]\n"
               "            [0 0  1]\n"
               "x' = x + dx，y' = y + dy\n"
               "各点同向等量移动，形状/大小不变")

    def _defs(self):
        return [("dx", "dx", 8, -40, 40), ("dy", "dy", 5, -40, 40),
                ("n", "步数", 12, 2, 40)]

    def _matrix(self, p, t):
        return tf.translation(p["dx"] * t, p["dy"] * t)

    def _values(self, p, k, n, m):
        return {"步": f"{k}/{n}", "dx": f"{p['dx'] * k / n:.1f}",
                "dy": f"{p['dy'] * k / n:.1f}", "矩阵": _mat_text(m)}


class RotateDemo(_TransformDemoBase):
    title = "旋转"
    icon = "replay"
    variables = {"步": "进度", "角度": "本帧角度", "轴心": "旋转中心"}
    formula = ("绕轴心 (cx, cy) 旋转 θ（屏幕 y 向下，正角=顺时针）\n"
               "R(θ) = [cosθ  -sinθ  0]\n"
               "       [sinθ   cosθ  0]\n"
               "       [0      0     1]\n"
               "M = T(cx,cy) · R(θ) · T(-cx,-cy)\n"
               "轴心 = 选中图元包围盒中心；圆旋转后按椭圆协方差重参数化")

    def _defs(self):
        return [("angle", "角度 °", 75, -360, 360), ("n", "步数", 12, 2, 40)]

    def _matrix(self, p, t):
        return tf.around(self._pivot_xy, tf.rotation(p["angle"] * t))

    def _values(self, p, k, n, m):
        return {"步": f"{k}/{n}", "角度": f"{p['angle'] * k / n:.1f}°",
                "轴心": f"{self._pivot_xy[0]:.0f},{self._pivot_xy[1]:.0f}",
                "矩阵": _mat_text(m)}


class ScaleDemo(_TransformDemoBase):
    title = "缩放"
    icon = "zoom-in"
    variables = {"步": "进度", "sx": "本帧 sx", "sy": "本帧 sy"}
    formula = ("绕轴心 (cx, cy) 缩放（屏幕坐标）\n"
               "S(sx, sy) = [sx 0  0]\n"
               "            [0  sy 0]\n"
               "            [0  0  1]\n"
               "M = T(cx,cy) · S · T(-cx,-cy)\n"
               "轴心 = 选中图元包围盒中心；sx≠sy 为非等比，圆形会变椭圆")

    def _defs(self):
        return [("sx", "sx %", 160, 5, 800), ("sy", "sy %", 70, 5, 800),
                ("n", "步数", 12, 2, 40)]

    def _matrix(self, p, t):
        sx = 1.0 + (p["sx"] / 100.0 - 1.0) * t
        sy = 1.0 + (p["sy"] / 100.0 - 1.0) * t
        return tf.around(self._pivot_xy, tf.scaling(sx, sy))

    def _values(self, p, k, n, m):
        sx = 1.0 + (p["sx"] / 100.0 - 1.0) * k / n
        sy = 1.0 + (p["sy"] / 100.0 - 1.0) * k / n
        return {"步": f"{k}/{n}", "sx": f"{sx:.2f}", "sy": f"{sy:.2f}",
                "矩阵": _mat_text(m)}


class ComposeDemo(_TransformDemoBase):
    title = "复合变换"
    icon = "sparkle"
    variables = {"步": "进度", "矩阵": "当前复合矩阵"}
    formula = ("复合变换（矩阵相乘，右乘先作用）\n"
               "M = T(dx,dy) · R(θ) · S(sx,sy)\n"
               "作用于点：先缩放 → 再旋转 → 最后平移\n"
               "M 为 3×3 仿射矩阵，顺序不可交换\n"
               "（R·S ≠ S·R，先转后缩与先缩后转结果不同）")

    def _defs(self):
        return [("dx", "dx", 10, -40, 40), ("dy", "dy", 4, -40, 40),
                ("angle", "角度 °", 60, -360, 360),
                ("sx", "sx %", 140, 5, 800),
                ("n", "步数", 16, 2, 40)]

    def _matrix(self, p, t):
        s = 1.0 + (p["sx"] / 100.0 - 1.0) * t
        return tf.compose(
            tf.translation(p["dx"] * t, p["dy"] * t),
            tf.around(self._pivot_xy, tf.rotation(p["angle"] * t)),
            tf.around(self._pivot_xy, tf.scaling(s, s)))

    def _values(self, p, k, n, m):
        return {"步": f"{k}/{n}", "矩阵": _mat_text(m)}


def create_demos():
    return [TranslateDemo(), RotateDemo(), ScaleDemo(), ComposeDemo()]
