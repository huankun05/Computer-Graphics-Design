# -*- coding: utf-8 -*-
"""
=====================================================================
 modules/module02_primitives/demos.py — 模块二演示页定义（阶段四）
=====================================================================
每个演示页 = 参数输入卡 + 公式卡 + 决策项监视 + 播放控制（通用壳，
见 ui/demo_view.py），页面本身只声明四件事（规范契约②）：
  build_params(layout)  参数卡里放什么控件
  collect() -> dict     收集参数
  make_steps(dict)      参数 → list[Step]（契约① 步骤流）
  formula / variables   公式文案 / 监视器变量说明
第 6 页为 DDA vs Bresenham 对比：两条步骤流按步交错，
每步用 values["color"] 标色（DDA 橙 / Bresenham 蓝紫）。
=====================================================================
"""

from dataclasses import dataclass, field
from typing import Dict, List

from PySide6.QtWidgets import (QComboBox, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QSpinBox, QVBoxLayout, QWidget)

from algorithms.line_dda import dda_line_steps, dda_line
from algorithms.seed_fill import (scanline_seed_fill_steps,
                                  seed_fill_wave_steps)
from algorithms.line_bresenham import bresenham_line_steps
from algorithms.circle_midpoint import midpoint_circle_steps
from algorithms.circle_dda import dda_circle_steps
from algorithms.ellipse_midpoint import midpoint_ellipse_steps
from algorithms.fill_scanline import scanline_fill_steps
from algorithms.fill_span import span_fill_steps
from algorithms.line_bresenham import bresenham_line_steps as _bl
from algorithms.steps import Step
from core.shapes import (
    LineShape, CircleShape, EllipseShape, PolygonShape,
    KIND_LINE_DDA, KIND_LINE_BRESENHAM,
    KIND_CIRCLE_MID, KIND_CIRCLE_DDA, KIND_CIRCLE,
)

# 对比页专用配色
DDA_COLOR = "#F76B15"    # DDA 橙
BRE_COLOR = "#3E63DD"    # Bresenham 蓝紫

# ------------------------------------------------------------------
# 监视器变量说明（演示页 与 画布拾取回放 共用）
# ------------------------------------------------------------------
VAR_PHASE   = {"阶段": "阶段"}
VAR_DDA     = {"x": "x", "y": "y", "步": "进度"}
VAR_CIRCLE_DDA = {"阶段": "阶段", "i": "采样", "x": "x", "y": "y", "θ": "角度"}
VAR_COMPARE_CIRCLE = {"阶段": "阶段", "算法": "算法", "x": "x", "y": "y"}


def _union(*dicts):
    """合并多个变量说明字典（后者不覆盖前者已有键）。"""
    out = {}
    for d in dicts:
        for k, v in d.items():
            out.setdefault(k, v)
    return out


def _tag(steps, phase):
    """给一组步骤打"阶段"标签（轮廓生成 / 内部填充）。"""
    return [Step(s.pixels, {**s.values, "阶段": phase}, s.note) for s in steps]
VAR_BRE     = {"x": "x", "y": "y", "err": "err", "e2": "2·err"}
VAR_CIRCLE  = {"x": "x", "y": "y", "p": "决策项 p"}
VAR_ELLIPSE = {"区域": "区域", "x": "x", "y": "y",
               "p1": "决策项 p1", "p2": "决策项 p2"}
VAR_FILL    = {"y": "扫描线 y", "交点数": "交点数", "填充像素": "本行像素"}
VAR_COMPARE = {"算法": "算法", "x": "x", "y": "y"}


def _merge_two(a_steps, b_steps, a_name, b_name, a_color, b_color):
    """两条步骤流按步交错并标色（对比页 / 对比工具回放共用）。"""
    steps = []
    for i in range(max(len(a_steps), len(b_steps))):
        if i < len(a_steps):
            s = a_steps[i]
            steps.append(Step(s.pixels,
                              {"算法": a_name, "x": s.values.get("x"),
                               "y": s.values.get("y"), "color": a_color},
                              f"{a_name}：{s.note}"))
        if i < len(b_steps):
            s = b_steps[i]
            steps.append(Step(s.pixels,
                              {"算法": b_name, "x": s.values.get("x"),
                               "y": s.values.get("y"), "color": b_color},
                              f"{b_name}：{s.note}"))
    return steps


VAR_FILL_ONLY = {"阶段": "阶段", "y": "扫描线 y", "填充像素": "本步像素"}


def fill_steps_for_shape(shape):
    """闭合图元 → (填充阶段步骤流, 变量表)；非闭合/未填充语义下也可用。

    圆/椭圆：按其算法轮廓做逐行跨段填充；多边形：扫描线交点配对填充。
    """
    from core.rasterizer import rasterize
    from core.shapes import KIND_ELLIPSE, KIND_POLYGON
    closed = (KIND_CIRCLE, KIND_CIRCLE_MID, KIND_CIRCLE_DDA, KIND_ELLIPSE)
    if isinstance(shape, PolygonShape) and len(shape.vertices) >= 3:
        return scanline_fill_steps(shape.vertices), VAR_FILL_ONLY
    if hasattr(shape, "r") or hasattr(shape, "rx") or shape.kind in closed:
        outline, _ = rasterize(shape)
        return span_fill_steps(outline), VAR_FILL_ONLY
    return None


def steps_for_shape(shapes):
    """已提交图元 → (步骤流, 监视器变量表)；无法识别返回 None。

    演示模式"画布拾取回放"。填充图元为【两阶段回放】：
    先逐像素画完轮廓（阶段=轮廓生成），确认后再逐步填充（阶段=内部填充）。
    """
    shapes = list(shapes)
    if not shapes:
        return None
    # 对比工具：一对 DDA/Bresenham 直线 → 同位双色交错步骤流
    if (len(shapes) == 2 and all(isinstance(s, LineShape) for s in shapes)
            and {s.kind for s in shapes} == {KIND_LINE_DDA, KIND_LINE_BRESENHAM}):
        bre = next(s for s in shapes if s.kind == KIND_LINE_BRESENHAM)
        dda = next(s for s in shapes if s.kind == KIND_LINE_DDA)
        a = _tag(dda_line_steps(dda.p0[0], dda.p0[1], dda.p1[0], dda.p1[1]),
                 "DDA 阶段")
        a = [Step(s.pixels, {**s.values, "算法": "DDA", "color": DDA_COLOR,
                             "inset": 5}, s.note) for s in a]
        b = _tag(bresenham_line_steps(bre.p0[0], bre.p0[1], bre.p1[0], bre.p1[1]),
                 "Bresenham 阶段")
        b = [Step(s.pixels, {**s.values, "算法": "Bresenham",
                             "color": BRE_COLOR, "inset": 0}, s.note) for s in b]
        merged = []
        for i in range(max(len(a), len(b))):
            if i < len(a):
                merged.append(a[i])
            if i < len(b):
                merged.append(b[i])
        return merged, VAR_COMPARE
    s = shapes[0]
    if isinstance(s, LineShape):
        if s.kind == KIND_LINE_DDA:
            return dda_line_steps(s.p0[0], s.p0[1], s.p1[0], s.p1[1]), VAR_DDA
        return bresenham_line_steps(s.p0[0], s.p0[1], s.p1[0], s.p1[1]), VAR_BRE
    if isinstance(s, CircleShape):
        if s.kind == KIND_CIRCLE_DDA:
            return dda_circle_steps(s.center[0], s.center[1], s.r), VAR_CIRCLE_DDA
        steps = _tag(midpoint_circle_steps(s.center[0], s.center[1], s.r),
                     "轮廓生成")
        if s.fill:
            fill, _ = fill_steps_for_shape(s)
            steps += _tag(fill, "内部填充")
        return steps, _union(VAR_PHASE, VAR_CIRCLE,
                             {"填充像素": "本步像素", "y": "扫描线 y"})
    if isinstance(s, EllipseShape):
        steps = _tag(midpoint_ellipse_steps(s.center[0], s.center[1],
                                            s.rx, s.ry), "轮廓生成")
        if s.fill:
            fill, _ = fill_steps_for_shape(s)
            steps += _tag(fill, "内部填充")
        return steps, _union(VAR_PHASE, VAR_ELLIPSE, {"填充像素": "本步像素"})
    if isinstance(s, PolygonShape) and len(s.vertices) >= 3:
        if s.fill:
            return scanline_fill_steps(s.vertices), VAR_FILL
        # 描边多边形：逐边 Bresenham 轮廓回放
        steps = []
        v = s.vertices
        for i in range(len(v)):
            for st in _bl(v[i][0], v[i][1], v[(i + 1) % len(v)][0],
                          v[(i + 1) % len(v)][1]):
                steps.append(Step(st.pixels, {"阶段": "轮廓生成",
                                              "x": st.values.get("x"),
                                              "y": st.values.get("y")},
                                  f"第 {i + 1} 边：{st.note}"))
        return steps, _union(VAR_PHASE, {"x": "x", "y": "y"})
    return None


@dataclass
class DemoSpec:
    """一个演示页的自描述（演示壳只认这个结构）。"""
    title: str
    icon: str
    variables: Dict[str, str]
    formula: str
    build_params: object      # callable(layout)
    collect: object           # callable() -> dict
    make_steps: object        # callable(dict) -> list[Step]


# =====================================================================
# 参数控件小工具
# =====================================================================
class _SpinParams:
    """基于"标签+整数微调框"网格的参数卡基类。"""

    def __init__(self):
        self._spins: Dict[str, QSpinBox] = {}
        self._extra_widgets = []

    # 子类提供：[(键, 中文标签, 默认值, 最小, 最大), ...]
    def _defs(self):
        return []

    def _extra(self, lay: QVBoxLayout):
        """子类扩展控件（默认无）。"""

    def _collect_extra(self) -> dict:
        return {}

    # ------------------------------------------------------------------
    def build_params(self, lay: QVBoxLayout):
        self._spins.clear()
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        for i, (key, cn, default, mn, mx) in enumerate(self._defs()):
            lab = QLabel(cn)
            lab.setObjectName("secondary")
            lab.setMinimumWidth(52)
            sb = QSpinBox()
            sb.setRange(mn, mx)
            sb.setValue(default)
            sb.setFixedWidth(96)
            grid.addWidget(lab, i, 0)
            grid.addWidget(sb, i, 1)
            grid.setColumnStretch(2, 1)
            self._spins[key] = sb
        lay.addLayout(grid)
        self._extra(lay)

    def collect(self) -> dict:
        if self._spins:
            d = {k: sb.value() for k, sb in self._spins.items()}
        else:
            # 无头调用（未构建参数卡）：回退到参数默认值
            d = {k: dft for k, _cn, dft, _mn, _mx in self._defs()}
        d.update(self._collect_extra())
        return d

    @staticmethod
    def _set_spin(sb, v):
        """程序化写入参数（屏蔽信号，避免触发防抖重生成）。"""
        sb.blockSignals(True)
        sb.setValue(int(v))
        sb.blockSignals(False)

    def apply_geometry(self, shapes):
        """画布拾取：把图元几何写回参数卡（子类按需实现）。"""

    def _add_algo_combo(self, lay: QVBoxLayout, options, current: str):
        """算法选择下拉（各演示页公用）：选择写入 self.kind。

        QComboBox 的变化由演示壳统一接防抖重生成——公式/步骤随之跟随。
        """
        combo = QComboBox()
        keys = [k for k, _cn in options]
        self.algo = current if current in keys else keys[0]
        for _k, cn in options:
            combo.addItem(cn)
        combo.setCurrentIndex(keys.index(self.algo))

        def _on(i):
            self.algo = keys[i]

        combo.currentIndexChanged.connect(_on)
        row = QHBoxLayout()
        lab = QLabel("算法")
        lab.setObjectName("secondary")
        row.addWidget(lab)
        row.addWidget(combo, stretch=1)
        lay.addLayout(row)
        self._combo = combo


# =====================================================================
# 1/2. 直线演示（DDA 与 Bresenham 合并为一页，算法下拉选择）
# =====================================================================
class LineDemo(_SpinParams):
    algo = "dda"            # "dda" | "bresenham"
    title = "直线"
    icon = "line"
    _VAR = {"dda": VAR_DDA, "bresenham": VAR_BRE}
    _FORMULA = {
        "dda": ("DDA 数值微分法\n"
                "steps = max(|dx|, |dy|)\n"
                "x += dx/steps,  y += dy/steps\n"
                "每步四舍五入取整"),
        "bresenham": ("Bresenham 整数决策项法\n"
                      "err = dx - dy，e2 = 2·err\n"
                      "e2 > -dy → x 步进\n"
                      "e2 <  dx → y 步进"),
    }

    @property
    def variables(self):
        return self._VAR[self.algo]

    @property
    def formula(self):
        return self._FORMULA[self.algo]

    def _extra(self, lay: QVBoxLayout):
        self._add_algo_combo(
            lay,
            [("dda", "DDA 数值微分法"),
             ("bresenham", "Bresenham 决策项法")],
            self.algo)

    def _defs(self):
        # 模拟像素坐标：60×40 网格（一格 = 一个像素）
        return [("x0", "起点 x", 10, 0, 59), ("y0", "起点 y", 28, 0, 39),
                ("x1", "终点 x", 48, 0, 59), ("y1", "终点 y", 12, 0, 39)]

    def apply_geometry(self, shapes):
        s = shapes[0]
        self._set_spin(self._spins["x0"], s.p0[0])
        self._set_spin(self._spins["y0"], s.p0[1])
        self._set_spin(self._spins["x1"], s.p1[0])
        self._set_spin(self._spins["y1"], s.p1[1])

    def collect_steps(self):
        p = self.collect()
        steps = (dda_line_steps(p["x0"], p["y0"], p["x1"], p["y1"])
                 if self.algo == "dda"
                 else bresenham_line_steps(p["x0"], p["y0"], p["x1"], p["y1"]))
        return steps

    def make_steps(self, p=None):
        return self.collect_steps()


# =====================================================================
# 3. 中点圆
# =====================================================================
class CircleDemo(_SpinParams):
    """圆演示：中点圆 与 DDA 角度采样 合并为一页，算法下拉选择。"""
    title = "圆"
    icon = "circle"
    algo = "mid"            # "mid" | "dda"
    _VAR = {"mid": VAR_CIRCLE, "dda": VAR_CIRCLE_DDA}
    _FORMULA = {
        "mid": ("中点圆（八对称）\n"
                "初值 p = 1 - r\n"
                "p < 0: p += 2x + 3\n"
                "p ≥ 0: p += 2(x-y) + 5, y--\n"
                "每步写 8 个对称位置"),
        "dda": ("DDA 圆（角度采样法）\n"
                "x = cx + r·cosθ, y = cy + r·sinθ\n"
                "θ 按 2π/n 均匀采样（n≈周长）\n"
                "每点四舍五入取整\n"
                "采样处像素可能重合/留隙"),
    }

    @property
    def variables(self):
        return self._VAR[self.algo]

    @property
    def formula(self):
        return self._FORMULA[self.algo]

    def _extra(self, lay: QVBoxLayout):
        self._add_algo_combo(
            lay,
            [("mid", "中点圆（八对称）"),
             ("dda", "DDA 圆（角度采样）")],
            self.algo)

    def _defs(self):
        return [("cx", "圆心 x", 30, 0, 59), ("cy", "圆心 y", 20, 0, 39),
                ("r", "半径 r", 9, 1, 28)]

    def apply_geometry(self, shapes):
        s = shapes[0]
        self._set_spin(self._spins["cx"], s.center[0])
        self._set_spin(self._spins["cy"], s.center[1])
        self._set_spin(self._spins["r"], s.r)

    def make_steps(self, p=None):
        p = p or self.collect()
        if self.algo == "dda":
            name = "DDA 圆（角度采样）"
            steps = dda_circle_steps(p["cx"], p["cy"], p["r"])
        else:
            name = "中点圆（八对称）"
            steps = midpoint_circle_steps(p["cx"], p["cy"], p["r"])
        # 每步打算法标签：监视器始终显示当前动画用的是哪个算法
        return [Step(s.pixels, {**s.values, "算法": name}, s.note)
                for s in steps]


# =====================================================================
# 4. 中点椭圆
# =====================================================================
class EllipseDemo(_SpinParams):
    title = "中点椭圆"
    icon = "ellipse"
    variables = VAR_ELLIPSE
    formula = ("中点椭圆（双区域）\n"
               "区域1 |k|>1: p1 = ry² - rx²·ry + rx²/4\n"
               "分界: 2ry²x = 2rx²y\n"
               "区域2 |k|<1: p2 由区域1末点重算\n"
               "四对称：(±x, ±y)")

    def _defs(self):
        return [("cx", "中心 x", 30, 0, 59), ("cy", "中心 y", 20, 0, 39),
                ("rx", "半轴 rx", 13, 1, 29), ("ry", "半轴 ry", 7, 1, 19)]

    def apply_geometry(self, shapes):
        s = shapes[0]
        self._set_spin(self._spins["cx"], s.center[0])
        self._set_spin(self._spins["cy"], s.center[1])
        self._set_spin(self._spins["rx"], s.rx)
        self._set_spin(self._spins["ry"], s.ry)

    def make_steps(self, p=None):
        p = p or self.collect()
        return midpoint_ellipse_steps(p["cx"], p["cy"], p["rx"], p["ry"])


# =====================================================================
# 5. 扫描线填充（顶点以文本输入）
# =====================================================================
class PolygonDemo(_SpinParams):
    """多边形演示：单击布点，右键/Enter 闭合；手绘回放 = 逐边 DDA 步进
    （每边一段，顶点间直线生成），配合扫描线填充页对照学习。"""
    title = "多边形"
    icon = "polygon"
    variables = {"顶点": "单击布点（x, y）", "边": "相邻顶点直线连接",
                 "闭合": "末顶点连回首顶点"}
    formula = ("多边形生成\n"
               "顶点序列 P0..Pn-1（单击布点）\n"
               "每条边 Pi→Pi+1 用直线算法步进\n"
               "末边 Pn-1→P0 闭合\n"
               "填充算法见下一页（扫描线/种子填充）")

    def _defs(self):
        return []

    def _extra(self, lay: QVBoxLayout):
        lay.addWidget(QLabel("多边形顶点 (x,y) 序列"))
        self.verts_edit = QLineEdit(self.DEFAULT_VERTS)
        self.verts_edit.setObjectName("mono")
        lay.addWidget(self.verts_edit)
        tip = QLabel("应用模式/演示画布：单击布点，右键或 Enter 闭合。\n"
                     "至少 3 个顶点。点播放看逐边生成动画。")
        tip.setObjectName("secondary")
        tip.setWordWrap(True)
        lay.addWidget(tip)

    DEFAULT_VERTS = "(13,26),(21,9),(32,15),(41,9),(46,21),(35,28),(22,24)"

    def parse_verts(self, text: str):
        import re
        nums = re.findall(r"(-?\d+)[,，]\s*(-?\d+)", text or "")
        verts = [(int(a), int(b)) for a, b in nums]
        return verts if len(verts) >= 3 else \
            [(int(a), int(b)) for a, b in
             re.findall(r"(-?\d+)[,，]\s*(-?\d+)", self.DEFAULT_VERTS)]

    def _collect_extra(self) -> dict:
        text = self.verts_edit.text() if hasattr(self, "verts_edit") \
            else self.DEFAULT_VERTS
        return {"vertices": self.parse_verts(text)}

    def apply_geometry(self, shapes):
        s = shapes[0]
        self.verts_edit.blockSignals(True)
        self.verts_edit.setText(
            ",".join(f"({x},{y})" for x, y in s.vertices))
        self.verts_edit.blockSignals(False)

    def make_steps(self, p=None):
        """逐边生成动画：相邻顶点 DDA 步进，每边一段（带边号）。"""
        p = p or self.collect()
        verts = p["vertices"]
        steps = []
        for i in range(len(verts)):
            x0, y0 = verts[i]
            x1, y1 = verts[(i + 1) % len(verts)]
            for st in dda_line_steps(x0, y0, x1, y1):
                steps.append(Step(st.pixels,
                                  {**st.values, "边": f"第 {i + 1} 条边"},
                                  None))
        return steps


class FillDemo(_SpinParams):
    """填充演示：扫描线 / 种子·4联通 / 种子·8联通 三种算法下拉切换。

    种子填充以参数多边形轮廓为边界、重心为种子，逐波前扩散动画
    （algorithms/seed_fill.py，与应用模式油漆桶同一实现）。
    """
    title = "填充"
    icon = "fill"
    algo = "scanline"       # "scanline" | "seed4" | "seed8"

    _VAR = {"scanline": VAR_FILL,
            "seed4": {"边界": "多边形轮廓像素（DDA 连边）",
                      "种子": "多边形重心",
                      "连通": "4 联通：只向上下左右扩散"},
            "seed8": {"边界": "多边形轮廓像素（DDA 连边）",
                      "种子": "多边形重心",
                      "连通": "8 联通：额外含对角方向"}}
    _FORMULA = {
        "scanline": ("扫描线填充（逐行求交配对）\n"
                     "对每条扫描线 y：\n"
                     "  1. 求与多边形所有边的交点\n"
                     "  2. 交点按 x 排序\n"
                     "  3. 两两配对 [x0,x1] 整段填充\n"
                     "顶点只计较小 y 端避免重复计数"),
        "seed4": ("种子填充（边界填充）· 4 联通\n"
                  "种子向上下左右扩散，遇边界停止\n"
                  "1px 对角缝隙挡得住（不泄漏）\n"
                  "每步 = 一圈扩散波前"),
        "seed8": ("种子填充（边界填充）· 8 联通\n"
                  "扩散额外含 4 个对角方向\n"
                  "1px 对角缝隙挡不住，会穿缝泄漏\n"
                  "每步 = 一圈扩散波前"),
    }

    @property
    def variables(self):
        return self._VAR[self.algo]

    @property
    def formula(self):
        return self._FORMULA[self.algo]

    def _extra(self, lay: QVBoxLayout):
        self._add_algo_combo(
            lay,
            [("scanline", "扫描线填充（逐行求交配对）"),
             ("seed4", "种子填充 · 4 联通"),
             ("seed8", "种子填充 · 8 联通")],
            self.algo)
        lay.addWidget(QLabel("多边形顶点 (x,y) 序列"))
        self.verts_edit = QLineEdit(self.DEFAULT_VERTS)
        self.verts_edit.setObjectName("mono")
        lay.addWidget(self.verts_edit)
        tip = QLabel("可编辑；右键闭合绘制同理。至少 3 个顶点。")
        tip.setObjectName("secondary")
        tip.setWordWrap(True)
        lay.addWidget(tip)

    DEFAULT_VERTS = "(13,26),(21,9),(32,15),(41,9),(46,21),(35,28),(22,24)"

    def _defs(self):
        return []

    def parse_verts(self, text: str):
        """解析 "(x,y),(x,y),..." 文本为顶点列表；失败返回默认顶点。"""
        import re
        nums = re.findall(r"(-?\d+)[,，]\s*(-?\d+)", text or "")
        verts = [(int(a), int(b)) for a, b in nums]
        return verts if len(verts) >= 3 else \
            [(int(a), int(b)) for a, b in
             re.findall(r"(-?\d+)[,，]\s*(-?\d+)", self.DEFAULT_VERTS)]

    def _collect_extra(self) -> dict:
        # 控件未构建时（无头调用/测试）直接用默认顶点
        text = self.verts_edit.text() if hasattr(self, "verts_edit") \
            else self.DEFAULT_VERTS
        return {"vertices": self.parse_verts(text),
                "algo": getattr(self, "algo", "scanline")}

    def apply_geometry(self, shapes):
        s = shapes[0]
        self.verts_edit.blockSignals(True)
        self.verts_edit.setText(
            ",".join(f"({x},{y})" for x, y in s.vertices))
        self.verts_edit.blockSignals(False)

    def make_steps(self, p=None):
        p = p or self.collect()
        algo = p.get("algo", "scanline")
        if algo == "scanline":
            return scanline_fill_steps(p["vertices"])
        # ---- 种子填充：多边形轮廓（DDA 连边）为边界，重心为种子 ----
        verts = p["vertices"]
        boundary = set()
        for i in range(len(verts)):
            x0, y0 = verts[i]
            x1, y1 = verts[(i + 1) % len(verts)]
            boundary.update(dda_line(x0, y0, x1, y1))
        sx = round(sum(v[0] for v in verts) / len(verts))
        sy = round(sum(v[1] for v in verts) / len(verts))
        nudge = 0
        while (sx, sy) in boundary and nudge < 20:
            sx += 1                         # 种子恰好落在边界上时向右挪
            nudge += 1
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        bounds = (min(xs) - 1, min(ys) - 1, max(xs) + 2, max(ys) + 2)
        conn = 8 if algo == "seed8" else 4
        # 波前扩散版：每步 = 从种子向外的一整圈，4/8 联通方向差异可见
        return seed_fill_wave_steps((sx, sy), boundary, bounds,
                                    connectivity=conn)


# =====================================================================
# 6. DDA vs Bresenham 对比（两流交错 + 每步标色）
# =====================================================================
class CompareDemo(_SpinParams):
    """通用算法对比页：自选形状（直线/圆）+ 任意两个算法，同位双层回放。

    算法A = 蓝紫满格（inset 0），算法B = 橙色内芯（inset 5）；
    重合像素呈蓝框橙芯，纯色像素即两算法的差异点。
    后续课程新算法注册进 COMPARE_SHAPES 即自动出现在对比选项里。
    """
    title = "算法对比（自选）"
    icon = "compare"
    variables = {"阶段": "阶段", "算法": "算法", "x": "x", "y": "y"}
    formula = ("算法对比（同位双层）\n"
               "蓝紫满格 = 算法A；橙色内芯 = 算法B\n"
               "重合像素呈蓝框橙芯\n"
               "纯橙/纯蓝 = 两算法选择不同的像素")

    # 形状 → (键, 显示名, 算法清单, 坐标参数定义)
    COMPARE_SHAPES = [
        ("line", "直线",
         [("line_dda", "DDA"), ("line_bresenham", "Bresenham")],
         [("x0", "起点 x", 10, 0, 59), ("y0", "起点 y", 28, 0, 39),
          ("x1", "终点 x", 48, 0, 59), ("y1", "终点 y", 12, 0, 39)]),
        ("circle", "圆",
         [("circle_dda", "DDA 圆（采样）"), ("circle_mid", "中点圆")],
         [("cx", "圆心 x", 30, 0, 59), ("cy", "圆心 y", 20, 0, 39),
          ("r", "半径 r", 9, 1, 28)]),
        ("fill", "填充",
         [("scanline", "扫描线"),
          ("seed4", "种子·4联通"), ("seed8", "种子·8联通")],
         []),
    ]

    def __init__(self):
        super().__init__()
        self._shape_key = "line"
        self._algo_a = "line_dda"
        self._algo_b = "line_bresenham"
        self.shape_combo = None
        self.combo_a = None
        self.combo_b = None
        self._grids = {}            # shape_key -> QGridLayout（按形状显隐）
        self._extra_widgets = []
        self._fill_shape = None     # 填充对比的手绘对象（多边形/圆/椭圆）

    # ---- 参数卡构建（覆盖基类：需要组合框 + 双坐标组） ----
    def build_params(self, lay: QVBoxLayout):
        from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel
        self._spins.clear()
        self._grids.clear()

        # 形状选择
        row = QGridLayout()
        lab = QLabel("形状")
        lab.setObjectName("secondary")
        lab.setMinimumWidth(52)
        self.shape_combo = QComboBox()
        for _k, name, _a, _d in self.COMPARE_SHAPES:
            self.shape_combo.addItem(name)
        row.addWidget(lab, 0, 0)
        row.addWidget(self.shape_combo, 0, 1)
        row.setColumnStretch(2, 1)
        lay.addLayout(row)

        # 算法 A / B
        for r, (cn, attr) in enumerate([("算法 A", "combo_a"),
                                        ("算法 B", "combo_b")]):
            row = QGridLayout()
            lab = QLabel(cn)
            lab.setObjectName("secondary")
            lab.setMinimumWidth(52)
            combo = QComboBox()
            setattr(self, attr, combo)
            # 下拉选择必须真正写回 _algo_a/_algo_b（此前只重建清单没连
            # 信号，用户换算法无效果，对比永远播默认那对）
            combo.currentIndexChanged.connect(
                lambda i, which=r: self._on_algo_changed(which, i))
            row.addWidget(lab, 0, 0)
            row.addWidget(combo, 0, 1)
            row.setColumnStretch(2, 1)
            lay.addLayout(row)

        # 两组坐标（按形状显隐：QGridLayout 无 setVisible，包一层宿主）
        for shape_key, _n, _algs, defs in self.COMPARE_SHAPES:
            host = QWidget()
            host.setObjectName(f"cmpGrid_{shape_key}")
            host.setStyleSheet(
                f"QWidget#cmpGrid_{shape_key} {{ background: transparent; }}")
            grid = QGridLayout(host)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(4)
            for i, (key, cn2, default, mn, mx) in enumerate(defs):
                lab2 = QLabel(cn2)
                lab2.setObjectName("secondary")
                lab2.setMinimumWidth(52)
                sb = QSpinBox()
                sb.setRange(mn, mx)
                sb.setValue(default)
                sb.setFixedWidth(96)
                grid.addWidget(lab2, i, 0)
                grid.addWidget(sb, i, 1)
                grid.setColumnStretch(2, 1)
                self._spins[key] = sb        # 直线/圆键名不冲突，可共用字典
            self._grids[shape_key] = host
            lay.addWidget(host)

        self._sync_shape_widgets()

        # 形状切换：重填算法清单 + 显隐坐标组（demo_view 的防抖负责重生成）
        self.shape_combo.currentIndexChanged.connect(self._on_shape_changed)

    def _sync_shape_widgets(self, repopulate=True):
        """按当前形状：显隐坐标组、重填算法清单、约束 A≠B。"""
        for key, host in self._grids.items():
            host.setVisible(key == self._shape_key)
        entry = next(e for e in self.COMPARE_SHAPES if e[0] == self._shape_key)
        algos = entry[2]
        if repopulate:
            for combo in (self.combo_a, self.combo_b):
                combo.blockSignals(True)
                combo.clear()
                for _k, name in algos:
                    combo.addItem(name)
                combo.blockSignals(False)
        keys = [k for k, _ in algos]
        self._algo_a = keys[0] if self._algo_a not in keys else self._algo_a
        self._algo_b = keys[1] if len(keys) > 1 and self._algo_b not in keys \
            else (keys[0] if self._algo_b not in keys else self._algo_b)
        if self._algo_a == self._algo_b:
            self._algo_b = next(k for k in keys if k != self._algo_a)
        for combo, val in ((self.combo_a, self._algo_a),
                           (self.combo_b, self._algo_b)):
            combo.blockSignals(True)
            combo.setCurrentIndex(keys.index(val))
            combo.blockSignals(False)

    def _on_shape_changed(self, idx):
        self._shape_key = self.COMPARE_SHAPES[idx][0]
        self._algo_a = self.COMPARE_SHAPES[idx][2][0][0]
        self._algo_b = self.COMPARE_SHAPES[idx][2][1][0]
        self._sync_shape_widgets()

    def _on_algo_changed(self, which, idx):
        """算法 A/B 下拉 → 写回状态；A、B 相同则自动兑换另一个。"""
        entry = next(e for e in self.COMPARE_SHAPES
                     if e[0] == self._shape_key)
        algos = entry[2]
        if not 0 <= idx < len(algos):
            return
        key = algos[idx][0]
        if which == 0:
            if key == self._algo_b:
                self._algo_b = self._algo_a
            self._algo_a = key
        else:
            if key == self._algo_a:
                self._algo_a = self._algo_b
            self._algo_b = key
        self._sync_shape_widgets(repopulate=False)

    def collect(self) -> dict:
        d = {"shape": self._shape_key, "a": self._algo_a, "b": self._algo_b}
        active = next(e for e in self.COMPARE_SHAPES if e[0] == self._shape_key)
        for key, _cn, _df, _mn, _mx in active[3]:
            d[key] = self._spins[key].value()
        return d

    def apply_geometry(self, shapes):
        """画布拾取：按图元种类切形状/算法并读回坐标。"""
        from core.shapes import KIND_LINE_DDA, KIND_LINE_BRESENHAM, \
            KIND_CIRCLE_MID, KIND_CIRCLE_DDA, RasterFillShape
        s = shapes[0]
        if isinstance(s, RasterFillShape):
            # 油漆桶填充图元：切到填充对比，无坐标可读回
            self._shape_key = "fill"
            self._algo_a, self._algo_b = "scanline", "seed4"
            self.shape_combo.blockSignals(True)
            self.shape_combo.setCurrentIndex(2)
            self.shape_combo.blockSignals(False)
            self._sync_shape_widgets()
            return
        if isinstance(s, LineShape):
            self._shape_key = "line"
            pair = {KIND_LINE_DDA, KIND_LINE_BRESENHAM}
            kinds = {s.kind} | pair
            self._algo_a = s.kind
            self._algo_b = next(k for k in kinds if k != s.kind)
        else:
            self._shape_key = "circle"
            self._algo_a = s.kind if s.kind in (KIND_CIRCLE_MID, KIND_CIRCLE_DDA) \
                else KIND_CIRCLE_MID
            self._algo_b = (KIND_CIRCLE_DDA if self._algo_a == KIND_CIRCLE_MID
                            else KIND_CIRCLE_MID)
        self.shape_combo.blockSignals(True)
        self.shape_combo.setCurrentIndex(
            0 if self._shape_key == "line" else 1)
        self.shape_combo.blockSignals(False)
        self._sync_shape_widgets()
        # 坐标读回
        if self._shape_key == "line":
            self._set_spin(self._spins["x0"], s.p0[0])
            self._set_spin(self._spins["y0"], s.p0[1])
            self._set_spin(self._spins["x1"], s.p1[0])
            self._set_spin(self._spins["y1"], s.p1[1])
        else:
            self._set_spin(self._spins["cx"], s.center[0])
            self._set_spin(self._spins["cy"], s.center[1])
            self._set_spin(self._spins["r"], s.r)

    def _fill_region_steps(self, algo):
        """填充对比的步骤流：只认画布上由用户指定的封闭图形。

        没有指定对象时返回空列表（不再回落内置示例多边形）。
        · scanline → 逐行扫描步骤（y 递增、行内连续段）；
        · seed4/8  → 波前扩散步骤（每步 = 从种子向外一整圈，
          4 联通菱形 / 8 联通方形），与扫描线过程明显不同。
        """
        from algorithms.seed_fill import seed_fill_wave_steps
        shp = self._fill_shape
        if shp is None:
            return []
        from core.rasterizer import rasterize
        outline = set(rasterize(shp)[0])
        if not outline:
            return []
        if hasattr(shp, "center"):
            sx, sy = shp.center
        else:
            vs = getattr(shp, "vertices", []) or outline
            sx = round(sum(v[0] for v in vs) / len(vs))
            sy = round(sum(v[1] for v in vs) / len(vs))
        while (sx, sy) in outline:                 # 种子挪到轮廓内部
            sx += 1
        bounds = (min(p[0] for p in outline) - 1, min(p[1] for p in outline) - 1,
                  max(p[0] for p in outline) + 2, max(p[1] for p in outline) + 2)
        if algo == "scanline":
            result = fill_steps_for_shape(shp)     # 多边形扫描线/圆跨段
            raw = result[0] if result else []
        else:
            conn = 8 if algo == "seed8" else 4
            raw = seed_fill_wave_steps((sx, sy), outline, bounds, conn)
        # 扣除轮廓像素：不覆盖用户的黑色边界
        steps = []
        for st in raw:
            px = [p for p in st.pixels if p not in outline]
            if px:
                steps.append(Step(px, st.values, st.note))
        return steps

    def make_steps(self, p=None):
        p = p or self.collect()
        from algorithms.line_bresenham import bresenham_line_steps as _bl
        steps_a, steps_b, name_a, name_b = [], [], "", ""
        if p["shape"] == "line":
            name_a = next(n for k, n in self.COMPARE_SHAPES[0][2] if k == p["a"])
            name_b = next(n for k, n in self.COMPARE_SHAPES[0][2] if k == p["b"])
            mk = {"line_dda": dda_line_steps,
                  "line_bresenham": bresenham_line_steps}
            steps_a = mk[p["a"]](p["x0"], p["y0"], p["x1"], p["y1"])
            steps_b = mk[p["b"]](p["x0"], p["y0"], p["x1"], p["y1"])
        elif p["shape"] == "circle":
            name_a = next(n for k, n in self.COMPARE_SHAPES[1][2] if k == p["a"])
            name_b = next(n for k, n in self.COMPARE_SHAPES[1][2] if k == p["b"])
            mk = {"circle_mid": midpoint_circle_steps,
                  "circle_dda": dda_circle_steps}
            steps_a = mk[p["a"]](p["cx"], p["cy"], p["r"])
            steps_b = mk[p["b"]](p["cx"], p["cy"], p["r"])
        if p["shape"] == "fill":
            name_a = next(n for k, n in self.COMPARE_SHAPES[2][2]
                          if k == p["a"])
            name_b = next(n for k, n in self.COMPARE_SHAPES[2][2]
                          if k == p["b"])
            # 各自保留自己的算法顺序：A 扫描线逐行 / B 种子波前扩散，
            # 不能再按 y 重新分组（那样 B 也被摊平成扫描线，过程看不出区别）
            steps_a = self._fill_region_steps(p["a"])
            steps_b = self._fill_region_steps(p["b"])
        if p["a"] == p["b"]:
            return []
        a = _tag(steps_a, f"{name_a} 阶段")
        a = [Step(s.pixels, {**s.values, "算法": name_a, "color": BRE_COLOR,
                             "inset": 0}, s.note) for s in a]
        b = _tag(steps_b, f"{name_b} 阶段")
        b = [Step(s.pixels, {**s.values, "算法": name_b, "color": DDA_COLOR,
                             "inset": 5}, s.note) for s in b]
        if p["shape"] == "fill":
            # 填充对比【分阶段】：先完整播算法A，再整层叠加算法B——
            # 逐行交错会让 B 的内芯当行盖住 A，两种过程读不出来
            return a + b
        merged = []
        for i in range(max(len(a), len(b))):
            if i < len(a):
                merged.append(a[i])
            if i < len(b):
                merged.append(b[i])
        return merged


# 模块二对外提供的演示页列表（module.py 引用）
def create_demos():
    return [LineDemo(), CircleDemo(), EllipseDemo(), PolygonDemo(),
            FillDemo(), CompareDemo()]
