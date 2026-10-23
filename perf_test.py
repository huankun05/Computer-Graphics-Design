# -*- coding: utf-8 -*-
"""
=====================================================================
 perf_test.py  —  预览路径性能量化（旧路径 vs 新路径，离屏）
=====================================================================
背景：v3 每次鼠标移动执行【全图 copy + 全图 fromImage + 逐像素 new QPen】，
是用户反馈卡顿的根因（规范 6.2）。v4 预览只做【光栅化 + 批量 drawPoints】。

本脚本在同一批最坏情况图元上，模拟两条路径的单帧开销（不含 Qt 事件循环）：
  旧路径单帧 = base.copy() + 逐像素 drawPoint（每像素 new QPen）+ fromImage
  新路径单帧 = 光栅化 + drawPoints/drawRects（一次 setPen）
各跑 N 次取平均，输出对比表。目标：新路径 <16ms/帧（60fps）。
=====================================================================
"""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QImage, QPainter, QColor, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import QApplication

from core.rasterizer import rasterize
from core.shapes import LineShape, CircleShape, EllipseShape, PolygonShape, \
    KIND_LINE_DDA, KIND_CIRCLE, KIND_ELLIPSE, KIND_POLYGON

app = QApplication.instance() or QApplication(sys.argv)

W, H = 1200, 800
ORANGE = QColor(220, 120, 20)
N = 200

# 最坏情况用例：长线 / 大圆 / 大椭圆 / 八边轮廓
cases = [
    ("长直线 1100×700", LineShape(kind=KIND_LINE_DDA)),
    ("大圆 r=380", CircleShape(kind=KIND_CIRCLE)),
    ("大椭圆 360×240", EllipseShape(kind=KIND_ELLIPSE)),
    ("八边形轮廓", PolygonShape(kind=KIND_POLYGON)),
]

shapes = [s for _, s in cases]
shapes[0].p0, shapes[0].p1 = (50, 50), (1150, 750)
shapes[1].center, shapes[1].r = (600, 400), 380
shapes[2].center, shapes[2].rx, shapes[2].ry = (600, 400), 360, 240
shapes[3].vertices = [(600, 60), (1000, 220), (1140, 560), (880, 740),
                      (420, 760), (90, 590), (60, 200), (330, 70)]
shapes[3].fill = False


def old_frame(base: QImage, shape) -> float:
    """v3 旧路径单帧：copy + 逐像素 drawPoint（每像素 new QPen）+ fromImage。"""
    t0 = time.perf_counter()
    disp = base.copy()
    p = QPainter(disp)
    outline, fill = rasterize(shape)          # 光栅化两条路径相同
    for (x, y) in outline:
        p.setPen(QPen(ORANGE, 1))             # ← v3 热点：每像素 new QPen
        p.drawPoint(x, y)
    for (x, y) in fill:
        p.setPen(QPen(ORANGE, 1))
        p.drawPoint(x, y)
    p.end()
    _pixmap = QPixmap.fromImage(disp)         # ← v3 热点：全图 4MB 格式转换
    return time.perf_counter() - t0


def new_frame(base: QImage, shape) -> float:
    """v4 新路径单帧：光栅化 + 批量绘制（无 copy / 无 fromImage）。"""
    t0 = time.perf_counter()
    outline, fill = rasterize(shape)
    p = QPainter(base)                        # 直接在 base 上模拟 foreground 绘制
    p.setRenderHint(QPainter.Antialiasing, False)
    p.setPen(QPen(ORANGE, 1))
    p.drawPoints(QPolygon([QPoint(x, y) for x, y in outline]))
    p.end()
    return time.perf_counter() - t0


base_img = QImage(W, H, QImage.Format_RGB32)
base_img.fill(QColor(255, 255, 255))

print("=" * 62)
print(f"预览路径性能对比（{W}×{H}，各 {N} 帧平均，offscreen）")
print("-" * 62)
print(f"{'用例':<16}{'像素数':>8}{'旧路径 ms/帧':>14}{'新路径 ms/帧':>14}{'加速':>8}")
print("-" * 62)

for name, shape in cases:
    outline, fill = rasterize(shape)
    n_px = len(outline) + len(fill)

    # 预热
    old_frame(base_img, shape)
    new_frame(base_img, shape)

    t_old = 0.0
    for _ in range(N):
        t_old += old_frame(base_img, shape)
    t_old_ms = t_old / N * 1000

    t_new = 0.0
    for _ in range(N):
        t_new += new_frame(base_img, shape)
    t_new_ms = t_new / N * 1000

    speedup = t_old_ms / t_new_ms if t_new_ms > 0 else float("inf")
    print(f"{name:<16}{n_px:>8}{t_old_ms:>14.2f}{t_new_ms:>14.2f}{speedup:>7.1f}x")

print("-" * 62)
print("达标线：新路径 < 16 ms/帧（60fps）")
