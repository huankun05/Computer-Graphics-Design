# -*- coding: utf-8 -*-
"""
=====================================================================
 modules/module02_primitives/tools.py — 模块二：绘图工具（形状 × 算法）
=====================================================================
交互设计（v6）：工具按【形状】组织，算法由选项条下拉框选择——
  工具（形状）：直线 / 圆 / 椭圆 / 多边形 / 直线算法对比
  算法下拉：  直线 → DDA / Bresenham（后续课程算法往各形状的清单里加）
              圆   → 中点圆      椭圆 → 中点椭圆      多边形 → 扫描线填充
  填充模式：  圆 / 椭圆 / 多边形 支持 填充⇄描边（选项条开关）；
              圆与椭圆的内部填充用"逐行取轮廓跨段"的凸形填充算法
              （algorithms/fill_span.py，与扫描线填充同一思想）。

每个工具类通过两个类属性向框架声明能力（主窗口选项条据此渲染）：
  algorithm_options: [(算法键, 显示名), ...]   —— 无则隐藏算法下拉
  supports_fill: bool                         —— 是否显示填充开关
算法键存放在 canvas.algorithm / 填充开关在 canvas.fill_mode（全局当前态）。
=====================================================================
"""

import math

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor

from core.rasterizer import rasterize
from core.tool_base import ToolBase
from core.shapes import (
    LineShape, CircleShape, EllipseShape, PolygonShape, RasterFillShape,
    KIND_LINE_DDA, KIND_LINE_BRESENHAM, KIND_CIRCLE, KIND_ELLIPSE, KIND_POLYGON,
    KIND_RASTER_FILL,
)
from modules.module02_primitives.demos import DDA_COLOR, BRE_COLOR


def _snap_45(start: QPointF, pos: QPointF):
    """Shift 约束：把终点吸附到 45° 整数倍方向（PS/Figma 直线惯例）。"""
    dx = pos.x() - start.x()
    dy = pos.y() - start.y()
    ang = math.atan2(dy, dx)
    snapped = round(ang / (math.pi / 4)) * (math.pi / 4)
    length = round(math.hypot(dx, dy))
    return (int(start.x() + length * math.cos(snapped)),
            int(start.y() + length * math.sin(snapped)))


def _has_shift(event) -> bool:
    """事件是否按着 Shift 修饰键（event 缺省时 False）。"""
    return event is not None and bool(event.modifiers() & Qt.ShiftModifier)


def _end_point(start: QPointF, pos: QPointF, event):
    """按 Shift 状态求终点整数坐标（无 Shift 直接取整）。"""
    return _snap_45(start, pos) if _has_shift(event) \
        else (int(pos.x()), int(pos.y()))


# =====================================================================
# 直线工具：一个工具，算法由下拉框选择（DDA / Bresenham）
# =====================================================================
class _LineToolBase(ToolBase):
    """直线工具内部实现：按下定起点，拖拽定终点，松开提交。"""

    def __init__(self, canvas):
        super().__init__(canvas)
        self._start: QPointF | None = None
        self._cur: QPointF | None = None

    def _kind(self) -> str:
        """当前下拉框选择的直线算法（画布全局态）。"""
        algo = getattr(self.canvas, "algorithm", KIND_LINE_DDA)
        return algo if algo in (KIND_LINE_DDA, KIND_LINE_BRESENHAM) \
            else KIND_LINE_DDA

    def _make_shape(self, p0, p1) -> LineShape:
        s = LineShape(kind=self._kind(), color=self.canvas.pen_color, width=1)
        s.p0, s.p1 = p0, p1
        return s

    def on_press(self, pos, event=None):
        self._start = pos
        self._cur = pos

    def on_move(self, pos, event=None):
        self._cur = pos
        if self._start is None:
            return
        self.canvas.preview_shape = self._make_shape(
            (int(self._start.x()), int(self._start.y())),
            _end_point(self._start, pos, event))
        self.canvas.redraw()

    def on_release(self, pos, event=None):
        if self._start is None:
            return
        self.canvas.add_shape(self._make_shape(
            (int(self._start.x()), int(self._start.y())),
            _end_point(self._start, pos, event)))
        self._start = None

    def cancel(self):
        """Esc：放弃当前进行中的线段。"""
        self._start = None
        self._cur = None

    def _dxdy(self):
        """状态栏用的当前 dx/dy（未按下时为 0,0）。"""
        if self._start is None or self._cur is None:
            return 0, 0
        return int(self._cur.x() - self._start.x()), \
            int(self._cur.y() - self._start.y())


class LineTool(_LineToolBase):
    """直线工具（算法下拉：DDA / Bresenham）。"""
    name = "直线"
    icon_name = "line"
    cursor_hint = "拖拽：从起点拉到终点（Shift 吸附 45°）"
    algorithm_options = [
        (KIND_LINE_DDA, "DDA（数值微分）"),
        (KIND_LINE_BRESENHAM, "Bresenham（整数决策项）"),
    ]

    def formula(self):
        kind = self._kind()
        if kind == KIND_LINE_DDA:
            return ("DDA 数值微分法\n"
                    "steps = max(|dx|, |dy|)\n"
                    "x += dx/steps,  y += dy/steps\n"
                    "每步四舍五入取整")
        return ("Bresenham 整数决策项法\n"
                "err = dx - dy，e2 = 2·err\n"
                "e2 > -dy → x 步进\n"
                "e2 <  dx → y 步进")

    def status(self):
        dx, dy = self._dxdy()
        if self._start is None:
            return "等待起点..."
        if self._kind() == KIND_LINE_DDA:
            steps = max(abs(dx), abs(dy))
            if steps == 0:
                return ""
            return f"dx={dx}, dy={dy}, steps={steps}\n" \
                   f"x_inc={dx/steps:.3f}, y_inc={dy/steps:.3f}"
        err = abs(dx) - abs(dy)
        return f"dx={abs(dx)}, dy={abs(dy)}\n" \
               f"初值 err = dx - dy = {err}\n" \
               f"e2 = 2*err = {2*err}"


# =====================================================================
# 中点圆工具
# =====================================================================
class CircleTool(ToolBase):
    name = "圆"
    icon_name = "circle"
    cursor_hint = "按下为圆心，拖拽决定半径"
    algorithm_options = [
        ("circle_mid", "中点圆（八对称）"),
        ("circle_dda", "DDA 圆（角度采样）"),
    ]
    # 圆工具支持 填充⇄描边 开关（此前漏声明 → 圆工具激活时按钮被禁用，
    # 用户点击毫无反应，而椭圆/多边形正常——正是"圆不能切换"的根因）
    supports_fill = True
    applies_kinds = ("circle_mid", "circle_dda")   # 工具态切换作用的图元种类

    def __init__(self, canvas):
        super().__init__(canvas)
        self._center = None
        self._cur = None

    def _kind(self) -> str:
        """当前下拉框选择的圆算法（画布全局态）。"""
        algo = getattr(self.canvas, "algorithm", "circle_mid")
        return algo if algo in ("circle_mid", "circle_dda") else "circle_mid"

    def _make_shape(self, r: int) -> CircleShape:
        s = CircleShape(kind=self._kind(), color=self.canvas.pen_color, width=1)
        s.center = (int(self._center.x()), int(self._center.y()))
        s.r = r
        # 填充开关：填充态下画出来即为实心（扫描线/跨段内点填充）
        s.fill = getattr(self.canvas, "fill_mode", True)
        return s

    def on_press(self, pos, event=None):
        self._center = pos
        self._cur = pos

    def on_move(self, pos, event=None):
        self._cur = pos
        if self._center is None:
            return
        r = int(math.hypot(pos.x() - self._center.x(), pos.y() - self._center.y()))
        self.canvas.preview_shape = self._make_shape(r)
        self.canvas.redraw()

    def on_release(self, pos, event=None):
        if self._center is None:
            return
        r = int(math.hypot(pos.x() - self._center.x(), pos.y() - self._center.y()))
        if r > 0:
            self.canvas.add_shape(self._make_shape(r))
        self._center = None

    def cancel(self):
        self._center = None
        self._cur = None

    def formula(self):
        if self._kind() == "circle_dda":
            return ("DDA 圆（角度采样法）\n"
                    "x = cx + r·cosθ, y = cy + r·sinθ\n"
                    "θ 按 2π/n 均匀采样（n≈周长）\n"
                    "每点四舍五入取整\n"
                    "采样处像素可能重合/留隙")
        return ("中点圆算法（八对称）\n"
                "决策项 p = 1 - r\n"
                "p < 0: p += 2x + 3\n"
                "p ≥ 0: p += 2(x-y) + 5, y--\n"
                "每步写 8 个对称位置")

    def status(self):
        if self._center is None or self._cur is None:
            return "等待圆心..."
        r = int(math.hypot(self._cur.x() - self._center.x(),
                           self._cur.y() - self._center.y()))
        if r == 0:
            return ""
        if self._kind() == "circle_dda":
            return f"r = {r}\n采样点数 n ≈ 2πr = {int(2*math.pi*r)}"
        p = 1 - r
        return f"r = {r}\n" \
               f"初值 p = 1 - r = {p}\n" \
               f"从 (0, {r}) 开始，x 递增到 {int(r/1.414)}"


# =====================================================================
# 中点椭圆工具
# =====================================================================
class EllipseTool(ToolBase):
    name = "椭圆"
    icon_name = "ellipse"
    cursor_hint = "按下为中心，拖拽决定 Rx/Ry（Shift 为正圆）"
    algorithm_options = [("ellipse_mid", "中点椭圆（双区域）")]
    supports_fill = True
    applies_kinds = ("ellipse",)

    def __init__(self, canvas):
        super().__init__(canvas)
        self._center = None
        self._cur = None

    def _shape(self, pos, event=None):
        rx = abs(int(pos.x() - self._center.x()))
        ry = abs(int(pos.y() - self._center.y()))
        if _has_shift(event):
            rx = ry = max(rx, ry)          # Shift → 正圆
        s = EllipseShape(kind=KIND_ELLIPSE, color=self.canvas.pen_color, width=1)
        s.center = (int(self._center.x()), int(self._center.y()))
        s.rx, s.ry = rx, ry
        s.fill = getattr(self.canvas, "fill_mode", True)
        return s

    def on_press(self, pos, event=None):
        self._center = pos
        self._cur = pos

    def on_move(self, pos, event=None):
        self._cur = pos
        if self._center is None:
            return
        self.canvas.preview_shape = self._shape(pos, event)
        self.canvas.redraw()

    def on_release(self, pos, event=None):
        if self._center is None:
            return
        s = self._shape(pos, event)
        if s.rx > 0 and s.ry > 0:
            self.canvas.add_shape(s)
        self._center = None

    def cancel(self):
        self._center = None
        self._cur = None

    def formula(self):
        return ("中点椭圆（双区域）\n"
                "区域1 |k|>1: p1 = ry² - rx²·ry + rx²/4\n"
                "分界: 2ry²x = 2rx²y\n"
                "区域2 |k|<1: p2 由区域1末点重算\n"
                "四对称：(±x, ±y)")

    def status(self):
        if self._center is None or self._cur is None:
            return "等待中心..."
        rx = abs(int(self._cur.x() - self._center.x()))
        ry = abs(int(self._cur.y() - self._center.y()))
        if rx == 0 or ry == 0:
            return ""
        p1 = ry * ry - rx * rx * ry + (rx * rx >> 2)
        return f"rx = {rx}, ry = {ry}\n" \
               f"初值 p1 = {p1}\n" \
               f"分界: 2·ry²·x = 2·rx²·y"


# =====================================================================
# 多边形 + 扫描线填充工具
# =====================================================================
class PolygonTool(ToolBase):
    name = "多边形"
    icon_name = "polygon"
    cursor_hint = "单击布点；Backspace 回退；Enter/右键闭合"
    algorithm_options = [("scanline", "扫描线填充（逐行求交配对）")]
    supports_fill = True
    applies_kinds = ("polygon",)

    def __init__(self, canvas):
        super().__init__(canvas)
        self._verts = []            # 已点下的顶点

    def on_press(self, pos, event=None):
        self._verts.append((int(pos.x()), int(pos.y())))
        self._update_preview()

    def on_move(self, pos, event=None):
        pass

    def on_release(self, pos, event=None):
        pass

    def on_right_click(self, pos, event=None):
        self._close_and_commit()

    def on_key(self, event):
        """键盘：Backspace 回退一点，Enter/Return 闭合提交（Figma 钢笔惯例）。"""
        key = event.key()
        if key == Qt.Key_Backspace:
            if self._verts:
                self._verts.pop()
                self._update_preview()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            self._close_and_commit()

    def _close_and_commit(self):
        """闭合多边形并提交（右键 / Enter 共用）。填充⇄描边跟随选项条开关。"""
        if len(self._verts) >= 3:
            s = PolygonShape(kind=KIND_POLYGON, color=self.canvas.pen_color,
                             width=1)
            s.vertices = list(self._verts)
            s.fill = getattr(self.canvas, "fill_mode", True)
            self.canvas.add_shape(s)
        self._verts.clear()
        self.canvas.preview_shape = None
        self.canvas.redraw()

    def _update_preview(self):
        """预览已布顶点（1 个点也显示像素点与顶点标记，便于确认落点）。"""
        if not self._verts:
            self.canvas.preview_shape = None
        else:
            s = PolygonShape(kind=KIND_POLYGON, color=self.canvas.pen_color,
                             width=1)
            s.vertices = list(self._verts)
            s.fill = False
            self.canvas.preview_shape = s
        self.canvas.redraw()

    def cancel(self):
        """Esc：放弃全部已布顶点。"""
        self._verts.clear()

    def deactivate(self):
        """切换工具时清点（已布顶点撤销）。"""
        self._verts.clear()
        self.canvas.preview_shape = None

    def formula(self):
        return ("扫描线多边形填充\n"
                "对每条扫描线 y：\n"
                "  1. 求与所有边的交点\n"
                "  2. 交点按 x 排序\n"
                "  3. 两两配对 [x0,x1] 整段填充\n"
                "顶点只计较小 y 端避免重复计数")

    def status(self):
        n = len(self._verts)
        if n == 0:
            return "等待第一个顶点..."
        return f"已点击 {n} 个顶点\n" \
               f"右键/Enter 闭合" + ("" if n >= 3 else "（至少需要 3 个）")


# =====================================================================
# 选择 / 移动工具：点选图元、拖拽移动、方向键微调（全部可撤销）
# =====================================================================
class SelectMoveTool(ToolBase):
    name = "选择 / 移动"
    icon_name = "cursor"
    cursor_hint = "点击选中图元；再按住拖动移动；方向键微调 1 格"
    algorithm_options = []

    def __init__(self, canvas):
        super().__init__(canvas)
        self._prev = None           # 上一次选中的图元（二次按下即拖动）

    def on_press(self, pos, event=None):
        prev = self.canvas._selected_shape
        hit = self.canvas.hit_test(pos)
        self.canvas.set_selected_shape(hit)
        # 点在"已选中"的图元上再按 → 进入画布移动上下文（拖拽/幽灵预览）
        if hit is not None and hit is prev:
            self.canvas.begin_move(pos)
            self._prev = hit
        else:
            self._prev = hit

    def on_move(self, pos, event=None):
        if self.canvas._move_ctx:
            self.canvas.update_move(pos)

    def on_release(self, pos, event=None):
        if self.canvas._move_ctx:
            self.canvas.end_move()
        self._prev = None

    def cancel(self):
        self.canvas.cancel_move()


PolygonFillTool = PolygonTool


# =====================================================================
# 橡皮擦工具：像素擦除 / 整体删除 双模式（选项条下拉切换）
# =====================================================================
class EraserTool(ToolBase):
    name = "橡皮擦"
    icon_name = "eraser"
    cursor_hint = "像素擦除：点击/划过即擦除；整体模式：点击删除整个图元"
    algorithm_options = [("pixel", "像素擦除"), ("whole", "整体删除")]
    algo_icon = {"pixel": "eraser", "whole": "trash"}   # 选项条图标随模式联动

    def __init__(self, canvas):
        super().__init__(canvas)
        self._erasing = False
        self._stroke = {}          # id(shape) -> [shape, 擦除前掩码]

    def _pixel_mode(self) -> bool:
        return getattr(self.canvas, "algorithm", "pixel") != "whole"

    def on_press(self, pos, event=None):
        self._erasing = True
        self._stroke.clear()
        self._erase_at(pos)

    def on_move(self, pos, event=None):
        if self._erasing:
            self._erase_at(pos)

    def on_release(self, pos, event=None):
        if self._erasing and self._pixel_mode():
            # 笔画结束：每个被触碰的图元压入一条像素擦除命令（可撤销）
            from core.commands import ErasePixelsCommand
            for shape, before in self._stroke.values():
                self.canvas.document.do(
                    ErasePixelsCommand(self.canvas.document, shape,
                                       before, set(shape.erased)))
            self.canvas.document_changed.emit()
        self._erasing = False
        self._stroke.clear()

    def _erase_at(self, pos):
        if self._pixel_mode():
            self._erase_pixels_at(int(pos.x()), int(pos.y()))
        else:
            hit = self.canvas.hit_test(pos)
            if hit is not None:
                if self.canvas._selected_shape is hit:
                    self.canvas.set_selected_shape(None)
                self.canvas.remove_shape(hit)   # 走命令栈，可撤销

    def _erase_pixels_at(self, x: int, y: int):
        """像素擦除：命中像素的图元把该像素加入擦除掩码（笔画末统一入栈）。"""
        for shape in reversed(self.canvas.document.shapes):
            if not shape.visible:
                continue
            outline, fill = rasterize(shape)
            if (x, y) in set(outline) | set(fill):
                if id(shape) not in self._stroke:
                    self._stroke[id(shape)] = [shape, set(shape.erased)]
                shape.erased.add((x, y))
                self.canvas._render_base()

    def cancel(self):
        self._erasing = False
        self._stroke.clear()


# =====================================================================
# 种子填充工具（油漆桶）：在封闭边界内部点击 → 扫描线种子填充（4-连通）
# =====================================================================
class FillTool(ToolBase):
    """填充工具（油漆桶）：算法下拉可选 种子·4联通 / 种子·8联通 / 扫描线。"""
    name = "填充"
    icon_name = "fill"
    cursor_hint = "在封闭边界内部点击填充（不越出边界）"
    algorithm_options = [
        ("seed4", "种子填充 · 四联通"),
        ("seed8", "种子填充 · 八联通"),
        ("scanline", "扫描线填充（点中的多边形整体）"),
    ]

    def __init__(self, canvas):
        super().__init__(canvas)
        if getattr(self.canvas, "algorithm", "seed4") not in \
                ("seed4", "seed8", "scanline"):
            self.canvas.algorithm = "seed4"

    def _connectivity(self) -> int:
        return 8 if getattr(self.canvas, "algorithm", "seed4") == "seed8" else 4

    def _fill_color(self):
        """填充颜色：画布定义了 fill_color（如演示模式）则优先，
        否则跟随画笔颜色（应用模式用户可控）。"""
        return getattr(self.canvas, "fill_color", None)             or self.canvas.pen_color

    def on_press(self, pos, event=None):
        if getattr(self.canvas, "algorithm", "seed4") == "scanline":
            self._fill_scanline(pos)
            return
        self._fill_seed(pos)

    def _fill_scanline(self, pos):
        """扫描线填充：点击点落在某个【闭合图元】（多边形/圆/椭圆）
        内部 → 该图元区域逐行填充；填充像素扣除全部轮廓像素，
        黑色边界保持可见（区别于种子填充的"从种子向外连通扩散"）。"""
        from algorithms.steps import expand_steps
        from core.shapes import (RasterFillShape, PolygonShape, CircleShape,
                                 EllipseShape)
        from modules.module02_primitives.demos import fill_steps_for_shape
        seed = (int(pos.x()), int(pos.y()))
        shapes = self.canvas.document.shapes
        # 边界 = 全部可见图元的轮廓像素（填充不得覆盖边界）
        boundary = set()
        for s in shapes:
            if s.visible:
                o, _f = rasterize(s)
                boundary.update(o)
        closed = (PolygonShape, CircleShape, EllipseShape)
        for s in reversed(shapes):
            if not s.visible or not isinstance(s, closed):
                continue
            if isinstance(s, PolygonShape) and len(s.vertices) < 3:
                continue
            steps, _var = fill_steps_for_shape(s)
            pixels = set(expand_steps(steps)) - boundary
            outline = set(rasterize(s)[0])
            # 命中：种子在内部区域，或恰好点在轮廓线上（归属该图元）
            if seed in pixels or seed in outline:
                shape = RasterFillShape(kind=KIND_RASTER_FILL,
                                        color=self._fill_color(), width=1)
                shape.seed = seed
                shape.conn = 4                  # 回放波前形状记录（扫描线=4）
                shape.algo = "scanline"         # 回放顺序：逐行扫描
                shape.pixels = sorted(pixels)
                shape.owner = s                 # 归属该图元：整体移动/删除联动
                self.canvas.add_shape(shape)   # 入撤销栈，可撤销
                return
        self.canvas.notify.emit(
            "扫描线填充：请点击某个闭合图形（多边形/圆/椭圆）的内部")

    def _owner_at(self, seed):
        """种子所在几何区域的最上层闭合图元（填充的联动归属）。

        用解析几何判定（点在圆/椭圆/多边形内），而不是查轮廓像素——
        种子通常在区域中心，轮廓环上没有这个点。
        """
        from core.shapes import (CircleShape, EllipseShape, PolygonShape,
                                 RasterFillShape)
        x, y = seed
        for cand in reversed(self.canvas.document.shapes):
            if not cand.visible or isinstance(cand, RasterFillShape):
                continue
            if isinstance(cand, CircleShape):
                cx, cy = cand.center
                inside = (x - cx) ** 2 + (y - cy) ** 2 <= cand.r ** 2
            elif isinstance(cand, EllipseShape):
                cx, cy = cand.center
                inside = ((x - cx) / max(1, cand.rx)) ** 2 + \
                         ((y - cy) / max(1, cand.ry)) ** 2 <= 1
            elif isinstance(cand, PolygonShape) and len(cand.vertices) >= 3:
                vs = cand.vertices
                inside = False                      # 射线法（+x 方向）
                for i in range(len(vs)):
                    (x0, y0), (x1, y1) = vs[i], vs[(i + 1) % len(vs)]
                    if (y0 > y) != (y1 > y):
                        xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                        if xi > x:
                            inside = not inside
            else:
                continue
            if inside:
                return cand
        return None

    def _fill_seed(self, pos):
        from algorithms.seed_fill import scanline_seed_fill_steps
        from algorithms.steps import expand_steps
        from core.shapes import RasterFillShape
        seed = (int(pos.x()), int(pos.y()))
        # 边界 = 画布上全部可见图元的像素
        boundary = set()
        for s in self.canvas.document.shapes:
            if not s.visible:
                continue
            o, f = rasterize(s)
            boundary.update(o)
            boundary.update(f)
        # 泄漏防护：填充范围钳制在【可见区域】∪ 种子邻域，绝不渲染全画布
        vx0, vy0, vx1, vy1 = self.canvas.visible_sim_bounds()
        x0 = min(vx0, seed[0] - 5)
        y0 = min(vy0, seed[1] - 5)
        x1 = max(vx1, seed[0] + 6)
        y1 = max(vy1, seed[1] + 6)
        steps = scanline_seed_fill_steps(seed, boundary,
                                         (x0, y0, x1, y1),
                                         self._connectivity())
        if not steps:
            return                          # 种子在边界上/外部：无有效填充
        shape = RasterFillShape(kind=KIND_RASTER_FILL,
                                color=self._fill_color(), width=1)
        shape.seed = seed
        shape.conn = self._connectivity()   # 回放波前形状记录（4/8）
        shape.algo = "seed8" if self._connectivity() == 8 else "seed4"
        shape.pixels = expand_steps(steps)
        # 归属：种子落在哪个闭合图元的几何区域内，填充就联动谁
        #（整体移动/缩放/删除）；落在图元之间则不归属
        shape.owner = self._owner_at(seed)
        # 泄漏检测：填充触及钳制边界 → 发生泄漏，状态栏提示
        leaked = any(px[0] in (x0, x1 - 1) or px[1] in (y0, y1 - 1)
                     for px in shape.pixels)
        if leaked and self._connectivity() == 4:
            self.canvas.notify.emit(
                "⚠ 四联通填充经边界缝隙泄漏：已限制在可见区域（边界可能存在缺口）")
        elif leaked:
            self.canvas.notify.emit("⚠ 填充触及可见区域边缘：已限制在可见范围内")
        self.canvas.add_shape(shape)        # 入撤销栈，可撤销

    def formula(self):
        if self._connectivity() == 8:
            return ("八联通种子填充（边界填充）\n"
                    "种子向 8 个相邻方向扩散（含对角）\n"
                    "1px 对角缝隙挡不住，会穿缝泄漏\n"
                    "（切到四联通对比泄漏差异）")
        return ("四联通种子填充（边界填充）\n"
                "种子只向上下左右扩散\n"
                "1px 对角缝隙挡得住（不泄漏）\n"
                "正交 1px 空洞仍会泄漏")

    def status(self):
        return f"点击封闭边界内部的任意位置填充（{self._connectivity()}联通）"


# =====================================================================
# 直线算法对比工具：一拖同画两条平行线（DDA 橙上 / Bresenham 蓝紫下）
# =====================================================================
class CompareLineTool(ToolBase):
    """算法对比工具：可选形状（直线/圆）与算法对，同位双层对比。

    下拉选择对比对（键存 canvas.algorithm）：
      cmp_line   直线：DDA vs Bresenham
      cmp_circle 圆：中点圆 vs DDA 圆（角度采样）
    提交两份图元：算法A 满格（蓝紫）+ 算法B 内芯（橙），
    重合像素呈蓝框橙芯，纯色像素即两算法的差异点。
    后续课程新算法在 PAIRS 里加新对比对即可。
    """
    name = "算法对比"
    icon_name = "compare"
    cursor_hint = "拖拽：同位双层对比（下拉选择形状与算法对）"
    algorithm_options = [
        ("cmp_line", "直线：DDA vs Bresenham"),
        ("cmp_circle", "圆：中点圆 vs DDA 圆"),
    ]

    def __init__(self, canvas):
        super().__init__(canvas)
        self._start = None
        if getattr(self.canvas, "algorithm", "cmp_line") not in \
                ("cmp_line", "cmp_circle"):
            self.canvas.algorithm = "cmp_line"

    def _pair(self):
        """当前对比对 → (形状键, 算法A键, 算法B键, 名称A, 名称B)。"""
        key = getattr(self.canvas, "algorithm", "cmp_line")
        if key == "cmp_circle":
            return ("circle", "circle_mid", "circle_dda", "中点圆", "DDA 圆")
        return ("line", KIND_LINE_DDA, KIND_LINE_BRESENHAM, "DDA", "Bresenham")

    def _make_shape(self, kind_key, algo, p0, p1, inset, color):
        """按形状构造一个对比图元。"""
        if kind_key == "circle":
            import math
            r = int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]))
            algo_kind = ("circle_mid" if algo == "circle_mid"
                         else "circle_dda")
            s = CircleShape(kind=algo_kind, color=color, width=1)
            s.center, s.r = p0, r
            # 圆的"定点"= 圆心：两算法同心对比
        else:
            algo_kind = (KIND_LINE_DDA if algo == "line_dda"
                         else KIND_LINE_BRESENHAM)
            s = LineShape(kind=algo_kind, color=color, width=1)
            s.p0, s.p1 = p0, p1
        s.inset = inset
        return s

    def on_press(self, pos, event=None):
        self._start = pos

    def on_move(self, pos, event=None):
        if self._start is None:
            return
        kind, algo_a, _b, _na, _nb = self._pair()
        p0 = (int(self._start.x()), int(self._start.y()))
        p1 = _end_point(self._start, pos, event)
        s = self._make_shape(kind, algo_a, p0, p1, 0,
                             self.canvas.pen_color)
        self.canvas.preview_shape = s
        self.canvas.redraw()

    def on_release(self, pos, event=None):
        if self._start is None:
            return
        kind, algo_a, algo_b, _na, _nb = self._pair()
        p0 = (int(self._start.x()), int(self._start.y()))
        p1 = _end_point(self._start, pos, event)
        full = self._make_shape(kind, algo_b, p0, p1, 0, QColor(BRE_COLOR))
        core_ = self._make_shape(kind, algo_a, p0, p1, 5, QColor(DDA_COLOR))
        self.canvas.add_shapes([full, core_])   # 一条命令提交，撤销一步全退
        self._start = None

    def cancel(self):
        self._start = None

    def formula(self):
        _k, na, nb, _ = self._pair() if False else (None, None, None, None)
        kind, a, b, _ = self._pair()
        return (f"算法对比（同位双层）\n"
                f"蓝紫满格 = {b}；橙色内芯 = {a}\n"
                f"重合像素呈蓝框橙芯\n"
                f"纯橙/纯蓝 = 两算法选择不同的像素")

    def status(self):
        if self._start is None:
            return "等待起点..."
        return "拖拽中：松开同时生成两种算法的图形"


# 兼容别名（旧引用）
SeedFillTool = FillTool# 兼容别名（旧引用）
SeedFillTool = FillTool
