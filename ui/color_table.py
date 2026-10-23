# -*- coding: utf-8 -*-
"""
 ui/color_table.py — 颜色表控件（HSV 二维色板 + 色相条）
=====================================================================
颜色卡主体：上方为"色相-饱和度-明度"二维渐变色板（当前色相下，
横向 = 饱和度 0→1，纵向 = 明度 1→0），下方为色相条（0°→360°）。
点击/拖拽即可连续选色。构成"颜色表 + 快捷色格"的颜色卡形态。
=====================================================================
"""

from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QPen
from PySide6.QtWidgets import QWidget

from ui import theme

_SV_H = 118          # 色板高度
_HUE_H = 14          # 色相条高度
_GAP = 8


class ColorTable(QWidget):
    """HSV 颜色表：点击/拖拽选色。signal colorChanged(QColor)。"""

    colorChanged = Signal(QColor)

    def __init__(self, color=None, parent=None):
        super().__init__(parent)
        self._hue = 0.0          # 0~359
        self._s = 0.0            # 0~1
        self._v = 0.0            # 0~1
        self._drag = None        # "sv" | "hue"
        self.set_color(color or QColor("#222222"))
        self.setMinimumHeight(_SV_H + _GAP + _HUE_H)
        self.setCursor(Qt.PointingHandCursor)

    # ------------------------------------------------------------------
    def set_color(self, c: QColor):
        """外部设置颜色（不回发信号）。"""
        h, s, v = c.hueF(), c.saturationF(), c.valueF()
        self._hue = (h * 359) if h >= 0 else 0.0
        self._s, self._v = s, v
        self.update()

    def color(self) -> QColor:
        return QColor.fromHsv(int(self._hue), int(self._s * 255),
                              int(self._v * 255))

    # ------------------------------------------------------------------
    def _sv_rect(self) -> QRectF:
        return QRectF(0, 0, self.width(), _SV_H)

    def _hue_rect(self) -> QRectF:
        return QRectF(0, _SV_H + _GAP, self.width(), _HUE_H)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        base = QColor.fromHsvF(self._hue / 359.0, 1, 1)

        # ---- SV 色板：白→纯色（横向）叠 透明→黑（纵向） ----
        sv = self._sv_rect()
        g1 = QLinearGradient(sv.left(), 0, sv.right(), 0)
        g1.setColorAt(0, QColor(255, 255, 255))
        g1.setColorAt(1, base)
        p.fillRect(sv, g1)
        g2 = QLinearGradient(0, sv.top(), 0, sv.bottom())
        g2.setColorAt(0, QColor(0, 0, 0, 0))
        g2.setColorAt(1, QColor(0, 0, 0))
        p.fillRect(sv, g2)
        p.setPen(QPen(QColor(theme.BORDER), 0))
        p.setBrush(Qt.NoBrush)
        p.drawRect(sv.adjusted(0, 0, -1, -1))

        # ---- 色相条：彩虹渐变 ----
        hr = self._hue_rect()
        gh = QLinearGradient(hr.left(), 0, hr.right(), 0)
        for i in range(7):
            gh.setColorAt(i / 6, QColor.fromHsvF(i / 6.0, 1, 1))
        p.fillRect(hr, gh)
        p.setPen(QPen(QColor(theme.BORDER), 0))
        p.drawRect(hr.adjusted(0, 0, -1, -1))

        # ---- 指示点：SV 圈 + 色相竖线 ----
        p.setRenderHint(QPainter.Antialiasing, True)
        cx = sv.left() + self._s * sv.width()
        cy = sv.top() + (1 - self._v) * sv.height()
        ring = QColor(255, 255, 255) if self._v < 0.6 else QColor(40, 40, 40)
        p.setPen(QPen(ring, 2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(cx - 5, cy - 5, 10, 10))
        hx = hr.left() + (self._hue / 359.0) * hr.width()
        p.setPen(QPen(QColor(255, 255, 255), 2))
        p.drawLine(QRectF(hx, hr.top(), 0, hr.height()).topLeft(),
                   QRectF(hx, hr.top(), 0, hr.height()).bottomLeft())
        p.setPen(QPen(QColor(0, 0, 0, 120), 0))
        p.drawLine(QRectF(hx - 1, hr.top(), 0, hr.height()).topLeft(),
                   QRectF(hx - 1, hr.top(), 0, hr.height()).bottomLeft())

    # ------------------------------------------------------------------
    def mousePressEvent(self, e):
        self._drag = "hue" if self._hue_rect().contains(e.position()) else "sv"
        self._pick(e.position())

    def mouseMoveEvent(self, e):
        if self._drag:
            self._pick(e.position())

    def mouseReleaseEvent(self, _e):
        self._drag = None

    def _pick(self, pos):
        sv, hr = self._sv_rect(), self._hue_rect()
        if self._drag == "hue":
            x = max(hr.left(), min(pos.x(), hr.right()))
            self._hue = (x - hr.left()) / hr.width() * 359.0
        else:
            x = max(sv.left(), min(pos.x(), sv.right()))
            y = max(sv.top(), min(pos.y(), sv.bottom()))
            self._s = (x - sv.left()) / sv.width()
            self._v = 1 - (y - sv.top()) / sv.height()
        self.update()
        self.colorChanged.emit(self.color())
