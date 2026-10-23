# -*- coding: utf-8 -*-
"""tools/ellipse_tool.py — 中点椭圆工具（带公式）"""

from PySide6.QtCore import QPointF
from core.tool_base import ToolBase
from core.shapes import EllipseShape, KIND_ELLIPSE


class EllipseTool(ToolBase):
    name = "中点椭圆"
    icon = "◯"
    cursor_hint = "按下为中心，拖拽决定 Rx/Ry"

    def __init__(self, canvas):
        super().__init__(canvas)
        self._center = None
        self._cur = None

    def on_press(self, pos):
        self._center = pos
        self._cur = pos

    def _shape(self, pos):
        rx = abs(int(pos.x()-self._center.x()))
        ry = abs(int(pos.y()-self._center.y()))
        s = EllipseShape(kind=KIND_ELLIPSE, color=self.canvas.pen_color,
                         width=self.canvas.pen_width)
        s.center = (int(self._center.x()), int(self._center.y()))
        s.rx, s.ry = rx, ry
        return s

    def on_move(self, pos):
        self._cur = pos
        if self._center is None: return
        self.canvas.preview_shape = self._shape(pos)
        self.canvas.redraw()

    def on_release(self, pos):
        if self._center is None: return
        s = self._shape(pos)
        if s.rx > 0 and s.ry > 0:
            self.canvas.add_shape(s)
        self._center = None

    def formula(self):
        return ("中点椭圆（双区域）\n"
                "区域1 (|k|>1): p1 = ry² - rx²·ry + rx²/4\n"
                "区域2 (|k|<1): p2 由区域1末点初始化\n"
                "四对称：(±x, ±y)")

    def status(self):
        if self._center is None or self._cur is None:
            return "等待中心..."
        rx = abs(int(self._cur.x()-self._center.x()))
        ry = abs(int(self._cur.y()-self._center.y()))
        if rx == 0 or ry == 0: return ""
        p1 = ry*ry - rx*rx*ry + (rx*rx>>2)
        return f"rx = {rx}, ry = {ry}\n" \
               f"初值 p1 = {p1}\n" \
               f"分界: 2·ry²·x = 2·rx²·y"
