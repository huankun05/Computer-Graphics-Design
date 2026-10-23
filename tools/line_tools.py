# -*- coding: utf-8 -*-
"""tools/line_tools.py — DDA / Bresenham 直线工具（带公式说明）"""

from PySide6.QtCore import QPointF
from core.tool_base import ToolBase
from core.shapes import LineShape, KIND_LINE_DDA, KIND_LINE_BRESENHAM


class _LineToolBase(ToolBase):
    kind: str = ""

    def __init__(self, canvas):
        super().__init__(canvas)
        self._start: QPointF | None = None
        self._cur: QPointF | None = None

    def on_press(self, pos):
        self._start = pos
        self._cur = pos

    def on_move(self, pos):
        self._cur = pos
        if self._start is None: return
        shape = LineShape(kind=self.kind, color=self.canvas.pen_color,
                          width=self.canvas.pen_width)
        shape.p0 = (int(self._start.x()), int(self._start.y()))
        shape.p1 = (int(pos.x()), int(pos.y()))
        self.canvas.preview_shape = shape
        self.canvas.redraw()

    def on_release(self, pos):
        if self._start is None: return
        shape = LineShape(kind=self.kind, color=self.canvas.pen_color,
                          width=self.canvas.pen_width)
        shape.p0 = (int(self._start.x()), int(self._start.y()))
        shape.p1 = (int(pos.x()), int(pos.y()))
        self.canvas.add_shape(shape)
        self._start = None

    def _dxdy(self):
        if self._start is None or self._cur is None:
            return 0, 0
        return int(self._cur.x()-self._start.x()), int(self._cur.y()-self._start.y())


class LineDDATool(_LineToolBase):
    name = "DDA 直线"
    kind = KIND_LINE_DDA
    icon = "╱"
    cursor_hint = "拖拽：从起点拉到终点"

    def formula(self):
        return ("DDA 数值微分法\n"
                "steps = max(|dx|, |dy|)\n"
                "x += dx/steps,  y += dy/steps\n"
                "每步四舍五入取整")

    def status(self):
        dx, dy = self._dxdy()
        if self._start is None: return "等待起点..."
        steps = max(abs(dx), abs(dy))
        if steps == 0: return ""
        return f"dx={dx}, dy={dy}, steps={steps}\n" \
               f"x_inc={dx/steps:.3f}, y_inc={dy/steps:.3f}"


class LineBresenhamTool(_LineToolBase):
    name = "Bresenham 直线"
    kind = KIND_LINE_BRESENHAM
    icon = "╱"
    cursor_hint = "拖拽：从起点拉到终点（整数运算）"

    def formula(self):
        return ("Bresenham 整数决策项法\n"
                "err = dx - dy\n"
                "e2 = 2*err\n"
                "e2 > -dy → x += sx\n"
                "e2 <  dx → y += sy")

    def status(self):
        dx, dy = self._dxdy()
        if self._start is None: return "等待起点..."
        err = abs(dx) - abs(dy)
        return f"dx={abs(dx)}, dy={abs(dy)}\n" \
               f"初值 err = dx - dy = {err}\n" \
               f"e2 = 2*err = {2*err}"
