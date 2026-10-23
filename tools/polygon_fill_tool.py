# -*- coding: utf-8 -*-
"""tools/polygon_fill_tool.py — 扫描线填充工具（带公式）"""

from PySide6.QtCore import QPointF
from core.tool_base import ToolBase
from core.shapes import PolygonShape, KIND_POLYGON


class PolygonFillTool(ToolBase):
    name = "扫描线填充"
    icon = "⬢"
    cursor_hint = "左键逐点点击顶点，右键闭合并填充"

    def __init__(self, canvas):
        super().__init__(canvas)
        self._verts = []

    def on_press(self, pos):
        self._verts.append((int(pos.x()), int(pos.y())))
        self._update_preview()

    def on_move(self, pos): pass
    def on_release(self, pos): pass

    def on_right_click(self, pos):
        if len(self._verts) >= 3:
            s = PolygonShape(kind=KIND_POLYGON, color=self.canvas.pen_color,
                             width=self.canvas.pen_width)
            s.vertices = list(self._verts); s.fill = True
            self.canvas.add_shape(s)
        self._verts.clear()
        self.canvas.preview_shape = None
        self.canvas.redraw()

    def _update_preview(self):
        if len(self._verts) < 2:
            self.canvas.preview_shape = None
        else:
            s = PolygonShape(kind=KIND_POLYGON, color=self.canvas.pen_color,
                             width=self.canvas.pen_width)
            s.vertices = list(self._verts); s.fill = False
            self.canvas.preview_shape = s
        self.canvas.redraw()

    def deactivate(self):
        self._verts.clear()
        self.canvas.preview_shape = None

    def formula(self):
        return ("扫描线多边形填充\n"
                "对每条扫描线 y：\n"
                "  1. 求与所有边的交点 x\n"
                "  2. x 排序\n"
                "  3. 两两配对 [x0,x1] 填充\n"
                "顶点只计较小 y 端避免重复")

    def status(self):
        n = len(self._verts)
        if n == 0: return "等待第一个顶点..."
        return f"已点击 {n} 个顶点\n" \
               f"右键闭合后填充" + ("" if n >= 3 else "（至少需要 3 个）")
