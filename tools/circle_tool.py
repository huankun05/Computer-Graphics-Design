# -*- coding: utf-8 -*-
"""tools/circle_tool.py — 中点圆工具（带公式）"""

import math
from PySide6.QtCore import QPointF
from core.tool_base import ToolBase
from core.shapes import CircleShape, KIND_CIRCLE


class CircleTool(ToolBase):
    name = "中点圆"
    icon = "◯"
    cursor_hint = "按下为圆心，拖拽决定半径"

    def __init__(self, canvas):
        super().__init__(canvas)
        self._center = None
        self._cur = None

    def on_press(self, pos):
        self._center = pos
        self._cur = pos

    def on_move(self, pos):
        self._cur = pos
        if self._center is None: return
        r = int(math.hypot(pos.x()-self._center.x(), pos.y()-self._center.y()))
        shape = CircleShape(kind=KIND_CIRCLE, color=self.canvas.pen_color,
                            width=self.canvas.pen_width)
        shape.center = (int(self._center.x()), int(self._center.y()))
        shape.r = r
        self.canvas.preview_shape = shape
        self.canvas.redraw()

    def on_release(self, pos):
        if self._center is None: return
        r = int(math.hypot(pos.x()-self._center.x(), pos.y()-self._center.y()))
        if r > 0:
            shape = CircleShape(kind=KIND_CIRCLE, color=self.canvas.pen_color,
                                width=self.canvas.pen_width)
            shape.center = (int(self._center.x()), int(self._center.y()))
            shape.r = r
            self.canvas.add_shape(shape)
        self._center = None

    def formula(self):
        return ("中点圆算法（八对称）\n"
                "决策项 p = 1 - r\n"
                "p < 0: p += 2x + 3\n"
                "p ≥ 0: p += 2(x-y) + 5, y--\n"
                "每点写 8 个对称位置")

    def status(self):
        if self._center is None or self._cur is None:
            return "等待圆心..."
        r = int(math.hypot(self._cur.x()-self._center.x(),
                           self._cur.y()-self._center.y()))
        if r == 0: return ""
        p = 1 - r
        return f"r = {r}\n" \
               f"初值 p = 1 - r = {p}\n" \
               f"从 (0, {r}) 开始，x 递增到 {int(r/1.414)}"
