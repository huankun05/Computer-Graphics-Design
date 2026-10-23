# -*- coding: utf-8 -*-
"""
=====================================================================
 modules/module01_color/view3d.py — 轻量 3D 视图基类（无 OpenGL）
=====================================================================
颜色模型教学只需"能转着看的线框/半透明体"，用不上真实渲染管线：
这里自写一套 ~百行的正交投影 + 画家算法，QPainter 直接画。
  · 偏航 yaw（绕竖直轴）/ 俯仰 pitch（绕屏幕水平轴）两自由度，
    左键拖拽改变视角，滚轮缩放；
  · 子类实现 render(painter, scale, project) 画自己的立体形：
    project(p) 把世界坐标 (x,y,z)（y 向上）变成屏幕 QPointF，
    并给出深度（越大离相机越近）供面排序。

选正交投影（而非透视）的原因：平行棱永远平行，立方体/棱锥的
结构关系和课程 PPT 插图一致，教学辨识度最好。
=====================================================================
"""

import math

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor
from PySide6.QtWidgets import QWidget

from ui import theme


def rot_xyz(p, yaw: float, pitch: float):
    """世界坐标 → 相机坐标：先偏航（绕 y 竖直轴）再俯仰（绕 x 轴）。

    返回 (xa, ya, za)；xa/ya 是屏幕平面坐标（ya 向上），za 是深度。
    """
    x, y, z = p
    cy, sy = math.cos(yaw), math.sin(yaw)
    xa = x * cy + z * sy
    za = -x * sy + z * cy
    cp, sp = math.cos(pitch), math.sin(pitch)
    ya = y * cp - za * sp
    zb = y * sp + za * cp
    return (xa, ya, zb)


class RotatingCanvas(QWidget):
    """可拖拽旋转的 3D 画布基类。

    子类覆盖 render()：p3d(p) 返回 (屏幕点, 深度)，按深度排序面后
    用 QPainter 半透明填充（画家算法）。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(320)
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)
        self.yaw = math.radians(-28)       # 初始视角：黑顶点在左前（PPT 位）
        self.pitch = math.radians(16)
        self.zoom = 1.0
        self.center3d = (0.0, 0.0, 0.0)    # 放到屏幕中心的 world 点（质心）
        self._drag_from = None             # 拖拽中上一次鼠标位置

    # ---- 相机 -------------------------------------------------------
    def p3d(self, p):
        """世界坐标 → (屏幕 QPointF, 深度)。子类 render 里用。

        先减 center3d（把形体质心放屏幕中心），再旋转投影。
        """
        q = (p[0] - self.center3d[0],
             p[1] - self.center3d[1],
             p[2] - self.center3d[2])
        xa, ya, zb = rot_xyz(q, self.yaw, self.pitch)
        s = self._scale_px()
        return (QPointF(self.width() / 2 + xa * s,
                        self.height() / 2 - ya * s), zb)

    def _scale_px(self) -> float:
        """世界单位 → 像素：按窗口自适应再乘滚轮缩放。"""
        return min(self.width(), self.height()) * 0.40 * self.zoom

    # ---- 交互：拖拽旋转 / 滚轮缩放 -----------------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_from = e.position()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if self._drag_from is None:
            return
        d = e.position() - self._drag_from
        self._drag_from = e.position()
        # 拖拽方向 = 转动模型的方向（像捏着球面转）
        self.yaw += d.x() * 0.011
        self.pitch = max(-1.45, min(1.45, self.pitch + d.y() * 0.011))
        self.update()

    def mouseReleaseEvent(self, e):
        self._drag_from = None
        self.setCursor(Qt.OpenHandCursor)

    def wheelEvent(self, e):
        self.zoom *= 1.1 if e.angleDelta().y() > 0 else 1 / 1.1
        self.zoom = max(0.5, min(2.6, self.zoom))
        self.update()

    # ---- 绘制骨架 ---------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        self.render(p)
        # 操作提示（右上角小字，不与下方平面视图挤在一起）
        p.setPen(QPen(QColor(theme.TEXT_3), 1))
        p.drawText(self.rect().adjusted(0, 4, -10, 0),
                   Qt.AlignRight | Qt.AlignTop,
                   "拖动旋转视角 · 滚轮缩放")

    def render(self, p: QPainter):
        raise NotImplementedError

    # ---- 子类共用的小工具 --------------------------------------------
    @staticmethod
    def face_sort_key(faces):
        """画家算法：faces = [(深度参考, 背面标记?, 画法), ...] 的辅助。

        这里只提供约定：面按平均深度从小到大（远→近）排序后绘制。
        """
        faces.sort(key=lambda f: f[0])
        return faces

    @staticmethod
    def draw_label(p: QPainter, pos: QPointF, text: str, outward: QPointF,
                   color=None, dim: float = 1.0):
        """在投影点外侧偏移画顶点标注（避免压在图形上）。

        dim：0~1 不透明度系数——背面的顶点标注淡化，减轻视觉含糊。
        """
        n = math.hypot(outward.x(), outward.y()) or 1.0
        a = pos + QPointF(outward.x() / n * 16, outward.y() / n * 16)
        col = QColor(color or theme.TEXT_1)
        col.setAlpha(int(255 * max(0.15, min(1.0, dim))))
        p.setPen(QPen(col, 1))
        from PySide6.QtCore import QRectF
        p.drawText(QRectF(a.x() - 44, a.y() - 10, 88, 20),
                   Qt.AlignCenter, text)

    @staticmethod
    def draw_axis_arrow(p: QPainter, a: QPointF, b: QPointF, color: str,
                        text: str):
        """世界轴的箭头 + 字母标注（R/G/B、V 等教具式轴标）。"""
        p.setPen(QPen(QColor(color), 2))
        p.setBrush(QBrush(QColor(color)))
        p.drawLine(a, b)
        import math as _m
        ang = _m.atan2(b.y() - a.y(), b.x() - a.x())
        size = 7
        tip1 = QPointF(b.x() - size * _m.cos(ang - 0.45),
                       b.y() - size * _m.sin(ang - 0.45))
        tip2 = QPointF(b.x() - size * _m.cos(ang + 0.45),
                       b.y() - size * _m.sin(ang + 0.45))
        from PySide6.QtGui import QPolygonF
        p.drawPolygon(QPolygonF([b, tip1, tip2]))
        p.setPen(QPen(QColor(color), 1))
        from PySide6.QtCore import QRectF
        p.drawText(QRectF(b.x() - 30, b.y() - 26, 60, 20),
                   Qt.AlignCenter, text)
