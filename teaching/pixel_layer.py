# -*- coding: utf-8 -*-
"""
=====================================================================
 teaching/pixel_layer.py  —  像素演示层（画布前景上的教学叠层）
=====================================================================
演示模式在画布上叠加两类像素（规范 3.2 / 决策 D6）：
  已生成像素 —— 主题色半透明染色（随播放逐步累积）；
  当前步像素 —— 全透明度与半透明交替（350ms 呼吸闪烁）。

性能设计：
  像素按颜色分组存 QRectF 列表，paint() 时每组一次 drawRects 批量调用；
  播放推进采用【增量 advance】（当前步沉淀为已完成），只有
  回退/跳转时才整层重建——最坏情况（两万像素扫描线）也只付一次代价。
=====================================================================
"""

import math

from PySide6.QtCore import QPointF, Qt, QRectF, QTimer, QLineF
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QPainter,
                           QPen, QPolygonF)

from core.shapes import SIM


def tint_color(color) -> QColor:
    """主色的"淡色版"——填充区专用色。

    之前用 QColor.lighter(165)：那会把明度顶到接近白色
    （#4F6EF7 → #EAEEFF），白纸上看不出填充，轮廓与填充看起来
    像"一个颜色"，边框就消失了（用户反馈："边框和填充弄成一个
    颜色了，展示不出来"）。

    这里显式与白色按 55% 混合：仍是主色的浅色调（一眼认得出
    "这是同一个图形的内部"），但和轮廓的主色分得清清楚楚。
    """
    c = QColor(color)
    return QColor(int(c.red() + (255 - c.red()) * 0.55),
                  int(c.green() + (255 - c.green()) * 0.55),
                  int(c.blue() + (255 - c.blue()) * 0.55))


class PixelLayer:
    """画布前景的教学像素层（由 CanvasView 持有并在 drawForeground 调用）。"""

    BLINK_MS = 350          # 呼吸闪烁周期（半周）

    def __init__(self, canvas):
        self._cv = canvas
        self._done = {}          # (color_name, inset, tint) -> list[QRectF]
        self._cur_color = None   # 当前步颜色
        self._cur_inset = 0      # 当前步内缩（对比双层用）
        self._cur = []           # 当前步 QRectF 列表（轮廓/主色）
        self._cur_tint = []      # 当前步的填充像素（淡色，Step.tint）
        self._guides = []        # 当前步演算注记（窗口/交点/轴心/箭头/标签）
        self._hover = []         # 鼠标悬停层（区域码分区等，独立于步骤流）
        self._ref = []           # 初始态参考层（变换动画期间常显）
        self._ref_color = None
        self._blink = False      # 闪烁相位
        self._solid = False      # 定格态：已完成像素按不透明实色渲染
        self._accumulate = True  # True=逐帧累积（划线/填充）；False=替换式（变换动画）
        self._timer = QTimer(canvas, interval=self.BLINK_MS)
        self._timer.timeout.connect(self._toggle_blink)

    # ------------------------------------------------------------------
    def set_accumulate(self, on: bool):
        """切换帧渲染方式。

        True  —— 已生成帧累积（DDA/中点圆/填充等"逐步长出"的算法）；
        False —— 替换式：每帧只显示当前步，不留历史轨迹（二维变换动画）。
        """
        self._accumulate = bool(on)
        self._done.clear()
        self._cur = []
        self._cur_tint = []
        self._guides = []
        self._hover = []
        self._ref = []
        self._ref_color = None
        self._timer.stop()
        self._blink = False
        self._cv.viewport().update()

    def set_reference(self, pixels, color: str, inset: int = 2):
        """设置初始态参考层：变换动画期间与当前帧一起常显。

        用与当前帧不同的颜色（演示壳传橙色），并略微内缩：
        第 1 帧与原位图形重叠时，当前帧（不透明、满格）仍压在上面看得清。
        """
        i = int(inset)
        self._ref_color = color
        self._ref = [QRectF(x * SIM + i, y * SIM + i, SIM - 2 * i, SIM - 2 * i)
                     for x, y in pixels]
        self._cv.viewport().update()

    def clear_reference(self):
        """清除初始态参考层（播放到末帧 / 换页 / 重放时）。"""
        if not self._ref and self._ref_color is None:
            return
        self._ref = []
        self._ref_color = None
        self._cv.viewport().update()

    def set_hover(self, guides):
        """设置鼠标悬停注记层（区域码分区等，不随步骤流变化）。

        内容与上次相同就不重绘：鼠标在同一区域内移动时不反复刷画布。
        """
        guides = list(guides or [])
        if guides == self._hover:
            return
        self._hover = guides
        self._cv.viewport().update()

    def clear_hover(self):
        """清除悬停注记层（鼠标离开画布 / 换页时）。"""
        if not self._hover:
            return
        self._hover = []
        self._cv.viewport().update()

    def clear_guides(self):
        """清除演算注记（播放结束定稿时）：窗口边框/交点/标签随步骤流结束，
        不再压在图元上——否则红框会一直留在成品画面上。"""
        if not self._guides:
            return
        self._guides = []
        self._cv.viewport().update()

    def reset(self):
        """清空整层（载入新算法 / 回退 / 重放时）。"""
        self._timer.stop()
        self._done.clear()
        self._cur = []
        self._cur_tint = []
        self._guides = []
        self._hover = []
        self._cur_color = None
        self._ref = []
        self._ref_color = None
        self._blink = False
        self._solid = False
        self._cv.viewport().update()

    def solidify(self):
        """播完定格：当前步并入已完成，整层转为不透明实色。

        对比结果保留用——半透明叠层压在恢复的黑色图元上会发暗发糊，
        定格后与直线对比对的实色图元观感一致。
        """
        if self._cur:
            self._done.setdefault((self._cur_color, self._cur_inset, False),
                                  []).extend(self._cur)
            self._cur = []
        if self._cur_tint:
            self._done.setdefault((self._cur_color, self._cur_inset, True),
                                  []).extend(self._cur_tint)
            self._cur_tint = []
        self._cur_color = None
        self._timer.stop()
        self._blink = False
        self._solid = True
        self._cv.viewport().update()

    def advance(self, step, color: str):
        """推进一步：旧"当前步"沉淀为已完成，新步骤像素成为当前步。

        替换式（_accumulate=False）下不沉淀，也不闪烁——画面只保留当前
        帧，看到的是"同一个图形在第 k 帧的位置/形态"。
        step.values 支持 "inset"（内缩渲染）：对比双层时下层满格、上层内芯。
        """
        if self._accumulate:
            if self._cur:
                self._done.setdefault((self._cur_color, self._cur_inset, False),
                                      []).extend(self._cur)
            if self._cur_tint:
                self._done.setdefault((self._cur_color, self._cur_inset, True),
                                      []).extend(self._cur_tint)
        else:
            self._done.clear()
        self._cur_color = color
        # 演算注记只跟随当前步：窗口边框/交点/轴心每步重画，不累积
        self._guides = list(getattr(step, "guides", None) or [])
        self._cur_inset = int(step.values.get("inset", 0)
                              if isinstance(step.values, dict) else 0)
        i = self._cur_inset
        # Step.tint = 填充像素（pixels 的子集）：用淡色画，和轮廓分开
        tint = {tuple(p) for p in (getattr(step, "tint", None) or [])}
        # 步骤像素是模拟像素坐标 → 渲染为 SIM×SIM 方块（一格 = 一像素）
        self._cur = [QRectF(x * SIM + i, y * SIM + i, SIM - 2 * i, SIM - 2 * i)
                     for x, y in step.pixels if (x, y) not in tint]
        self._cur_tint = [QRectF(x * SIM + i, y * SIM + i,
                                 SIM - 2 * i, SIM - 2 * i)
                          for x, y in step.pixels if (x, y) in tint]
        if self._accumulate and not self._timer.isActive():
            self._timer.start()
        self._cv.viewport().update()

    # ------------------------------------------------------------------
    def paint(self, painter: QPainter):
        """CanvasView.drawForeground 调用。已生成半透明，当前步呼吸闪烁；
        定格态下已完成像素改为不透明实色（对比结果观感与图元一致）。

        初始态参考层最先画（在最下层），用橙色半透明与当前帧的蓝色区分。
        """
        if self._ref and self._ref_color:
            c = QColor(self._ref_color)
            c.setAlpha(120)
            painter.setPen(Qt.NoPen)
            painter.setBrush(c)
            painter.drawRects(self._ref)
        if self._done:
            painter.setPen(Qt.NoPen)
            # 画序：先填充（淡色）后轮廓（主色）。
            # 之前按插入顺序画，轮廓先落、填充后盖 → 边框被填充吃掉，
            # 整块图元只剩一个颜色（用户反馈："边框展示不出来"）。
            # tint 组（is_tint=True）排在前面，轮廓组压在上面。
            for (color_name, _inset, is_tint), rects in sorted(
                    self._done.items(), key=lambda kv: 0 if kv[0][2] else 1):
                c = QColor(color_name)
                if is_tint:
                    c = tint_color(c)
                    c.setAlpha(255 if self._solid else 85)
                else:
                    c.setAlpha(255 if self._solid else 115)
                painter.setBrush(c)
                painter.drawRects(rects)
        # 填充像素：淡色（与轮廓的主色区分开，用户反馈"边框和填充一个颜色"）
        if self._cur_tint and self._cur_color:
            c = tint_color(self._cur_color)
            c.setAlpha(210 if (self._solid or not self._accumulate) else 110)
            painter.setPen(Qt.NoPen)
            painter.setBrush(c)
            painter.drawRects(self._cur_tint)
        if self._cur and self._cur_color:
            c = QColor(self._cur_color)
            # 替换式固定实色（无呼吸闪烁），避免"停留"时明暗跳动
            if self._solid or not self._accumulate:
                c.setAlpha(255)
            else:
                c.setAlpha(255 if self._blink else 130)
            painter.setPen(Qt.NoPen)
            painter.setBrush(c)
            painter.drawRects(self._cur)
        # 演算注记画在像素之上：窗口边框/交点/轴心/箭头/标签
        self._draw_guides(painter)
        # 鼠标悬停层（区域码分区）画在最上
        self._draw_hover(painter)

    # ------------------------------------------------------------------
    def _draw_hover(self, painter: QPainter):
        """悬停注记：zone = 分区（可填色/描边），line = 分区延长线。"""
        if not self._hover:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        font = QFont(painter.font())
        font.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei",
                          "Segoe UI", "Sans Serif"])
        for g in self._hover:
            kind = g.get("kind")
            if kind == "line":
                (x0, y0), (x1, y1) = g["xy"]
                painter.setPen(QPen(QColor(g.get("color") or "#B8C2D6"),
                                    1.0, Qt.DashLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawLine(QLineF(x0 * SIM, y0 * SIM,
                                        x1 * SIM, y1 * SIM))
                continue
            if kind != "zone":
                continue
            x0, y0, x1, y1 = g["xy"]
            box = QRectF(x0 * SIM, y0 * SIM,
                         (x1 - x0) * SIM, (y1 - y0) * SIM)
            fill = g.get("fill")
            if fill:
                c = QColor(fill)
                c.setAlpha(int(g.get("fill_alpha", 24)))
                painter.setBrush(c)
            else:
                painter.setBrush(Qt.NoBrush)
            if g.get("border"):
                painter.setPen(QPen(QColor(g.get("color") or "#E1E5F0"), 1.2,
                                    Qt.SolidLine))
                painter.drawRect(box)
            elif fill:
                painter.setPen(Qt.NoPen)
                painter.drawRect(box)
            text = g.get("text") or ""
            if not text:
                continue
            font.setPixelSize(int(g.get("size") or max(11, int(SIM * 0.68))))
            font.setBold(bool(g.get("bold")))
            painter.setFont(font)
            painter.setPen(QPen(QColor(g.get("text_color") or "#8A919F")))
            painter.drawText(box, Qt.AlignCenter, text)
        painter.restore()

    # ------------------------------------------------------------------
    # 演算注记渲染（Step.guides 的纯 dict 描述 → 图元）
    # ------------------------------------------------------------------
    def _draw_guides(self, painter: QPainter):
        if not self._guides:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        font = QFont(painter.font())
        # 显式给字体族：注记含中文，painter 继承的字体可能缺字形（显示方块）
        font.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei",
                          "Segoe UI", "Sans Serif"])
        font.setPixelSize(max(10, int(SIM * 0.7)))
        font.setBold(True)
        point_r = max(4.0, SIM * 0.22)
        # 窗口红框永远最后画：边界延长线/当前边界高亮都画在窗口外侧，
        # 但若某个算法把 rect 注记放在列表前面，这里也保证红框不被盖掉
        ordered = ([g for g in self._guides if g.get("kind") != "rect"]
                   + [g for g in self._guides if g.get("kind") == "rect"])
        for g in ordered:
            color = QColor(g.get("color") or "#3E63DD")
            kind = g.get("kind")
            if kind == "rect":
                x0, y0, x1, y1 = g["xy"]
                painter.setPen(QPen(color, 1.6, Qt.DashLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(QRectF(x0 * SIM, y0 * SIM,
                                        (x1 - x0 + 1) * SIM,
                                        (y1 - y0 + 1) * SIM))
            elif kind == "boundary":
                # 边界线：坐标是【格子边缘】，直接 x*SIM，不加半格——
                # 否则与红色窗口框差半格（用户反馈的"边界显示"问题）
                a, b = g["a"], g["b"]
                painter.setPen(QPen(color, float(g.get("width") or 1.6),
                                    Qt.DashLine if g.get("dash")
                                    else Qt.SolidLine))
                painter.drawLine(QLineF(a[0] * SIM, a[1] * SIM,
                                        b[0] * SIM, b[1] * SIM))
            elif kind == "edge":
                # 当前正在使用的那条窗口边：画在红框外侧 2.5px，
                # 加粗实线 + 名字，红框本身保持完整可见
                self._draw_edge(painter, g, color, font)
            elif kind in ("line", "arrow"):
                a, b = g["a"], g["b"]
                painter.setPen(QPen(color, float(g.get("width") or 1.6),
                                    Qt.DashLine if g.get("dash")
                                    else Qt.SolidLine))
                p1 = QPointF(a[0] * SIM + SIM / 2, a[1] * SIM + SIM / 2)
                p2 = QPointF(b[0] * SIM + SIM / 2, b[1] * SIM + SIM / 2)
                painter.drawLine(p1, p2)
                if kind == "arrow":
                    self._draw_arrow_head(painter, p1, p2, color, point_r)
            elif kind == "polygon":
                # 当前结果多边形（S-H 的中间多边形）：按格心闭合折线绘制。
                # 与 Step.pixels 分离，不会被"原图像素"求交过滤掉。
                # anchor="corner" 时画在格角——裁剪窗口用它，才能和画布上
                # 裁剪工具的红框完全重合（否则是两重错开半格的窗口框）。
                pts = g.get("points") or []
                if len(pts) < 2:
                    continue
                off = SIM / 2 if g.get("anchor", "center") == "corner" else 0.0
                poly = QPolygonF([
                    QPointF(p[0] * SIM + off, p[1] * SIM + off)
                    for p in pts])
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(color, float(g.get("width") or 2.2),
                                    Qt.DashLine if g.get("dash")
                                    else Qt.SolidLine))
                painter.drawPolygon(poly)
            elif kind == "point":
                x, y = g["xy"]
                cx = x * SIM + SIM / 2
                cy = y * SIM + SIM / 2
                painter.setPen(QPen(color, 1))
                painter.setBrush(QBrush(color))
                painter.drawEllipse(QPointF(cx, cy), point_r, point_r)
                text = g.get("label") or ""
                if text:
                    painter.setFont(font)
                    painter.setPen(QPen(color))
                    painter.drawText(QPointF(cx + point_r + 3,
                                             cy - point_r), text)
            elif kind == "label":
                x, y = g["xy"]
                text = g.get("text") or ""
                if not text:
                    continue
                painter.setFont(font)
                painter.setPen(QPen(color))
                fm = QFontMetricsF(font)
                w = fm.horizontalAdvance(text) + 4
                h = fm.height()
                cx = x * SIM + SIM / 2
                cy = y * SIM + SIM / 2
                align = g.get("align", "left")
                valign = g.get("valign", "above")
                if align == "center":
                    left = cx - w / 2
                elif align == "right":
                    left = cx - w - 3
                else:
                    left = cx + 3
                if valign == "middle":
                    top = cy - h / 2
                elif valign == "below":
                    top = (y + 1) * SIM + 2
                else:                       # above：贴在锚点格上沿之外
                    top = y * SIM - h - 2
                painter.drawText(QRectF(left, top, w, h),
                                 Qt.AlignHCenter | Qt.AlignVCenter, text)
        painter.restore()

    @staticmethod
    def _draw_edge(painter, g: dict, color: QColor, font: QFont):
        """当前被使用的窗口边：红框外侧 2.5px 的加粗实线 + 名字。"""
        rx0, ry0, rx1, ry1 = g["rect"]
        ox1, oy1 = (rx1 + 1) * SIM, (ry1 + 1) * SIM
        off = 2.5
        side = g.get("side")
        if side == "left":
            a = QPointF(rx0 * SIM - off, ry0 * SIM)
            b = QPointF(rx0 * SIM - off, oy1)
        elif side == "right":
            a = QPointF(ox1 + off, ry0 * SIM)
            b = QPointF(ox1 + off, oy1)
        elif side == "top":
            a = QPointF(rx0 * SIM, ry0 * SIM - off)
            b = QPointF(ox1, ry0 * SIM - off)
        else:
            a = QPointF(rx0 * SIM, oy1 + off)
            b = QPointF(ox1, oy1 + off)
        painter.setPen(QPen(color, 3.0, Qt.SolidLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(a, b)
        text = g.get("label") or ""
        if not text:
            return
        painter.setFont(font)
        painter.setPen(QPen(color))
        fm = QFontMetricsF(font)
        w = fm.horizontalAdvance(text) + 4
        h = fm.height()
        mx, my = (a.x() + b.x()) / 2, (a.y() + b.y()) / 2
        if side == "left":
            rect = QRectF(a.x() - w - 4, my - h / 2, w, h)
        elif side == "right":
            rect = QRectF(a.x() + 4, my - h / 2, w, h)
        elif side == "top":
            rect = QRectF(mx - w / 2, a.y() - h - 2, w, h)
        else:
            rect = QRectF(mx - w / 2, a.y() + 2, w, h)
        painter.drawText(rect, Qt.AlignCenter, text)

    @staticmethod
    def _draw_arrow_head(painter, p1: QPointF, p2: QPointF,
                         color: QColor, size: float):
        """箭头：在 p2 端画两段短线（方向 = p1→p2）。"""
        dx, dy = p2.x() - p1.x(), p2.y() - p1.y()
        length = math.hypot(dx, dy)
        if length < 1e-6:
            return
        ux, uy = dx / length, dy / length
        head = max(6.0, size * 1.8)
        left = QPointF(p2.x() - ux * head - uy * head / 2,
                       p2.y() - uy * head + ux * head / 2)
        right = QPointF(p2.x() - ux * head + uy * head / 2,
                        p2.y() - uy * head - ux * head / 2)
        painter.setPen(QPen(color, 1.6))
        painter.drawLine(p2, left)
        painter.drawLine(p2, right)

    def _toggle_blink(self):
        self._blink = not self._blink
        self._cv.viewport().update()
