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

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QColor, QPainter

from core.shapes import SIM


class PixelLayer:
    """画布前景的教学像素层（由 CanvasView 持有并在 drawForeground 调用）。"""

    BLINK_MS = 350          # 呼吸闪烁周期（半周）

    def __init__(self, canvas):
        self._cv = canvas
        self._done = {}          # (color_name, inset) -> list[QRectF]
        self._cur_color = None   # 当前步颜色
        self._cur_inset = 0      # 当前步内缩（对比双层用）
        self._cur = []           # 当前步 QRectF 列表
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

    def reset(self):
        """清空整层（载入新算法 / 回退 / 重放时）。"""
        self._timer.stop()
        self._done.clear()
        self._cur = []
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
            self._done.setdefault((self._cur_color, self._cur_inset),
                                  []).extend(self._cur)
            self._cur = []
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
                self._done.setdefault((self._cur_color, self._cur_inset),
                                      []).extend(self._cur)
        else:
            self._done.clear()
        self._cur_color = color
        self._cur_inset = int(step.values.get("inset", 0)
                              if isinstance(step.values, dict) else 0)
        i = self._cur_inset
        # 步骤像素是模拟像素坐标 → 渲染为 SIM×SIM 方块（一格 = 一像素）
        self._cur = [QRectF(x * SIM + i, y * SIM + i, SIM - 2 * i, SIM - 2 * i)
                     for x, y in step.pixels]
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
            for (color_name, _inset), rects in self._done.items():
                c = QColor(color_name)
                c.setAlpha(255 if self._solid else 115)
                painter.setBrush(c)
                painter.drawRects(rects)
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

    def _toggle_blink(self):
        self._blink = not self._blink
        self._cv.viewport().update()
