# -*- coding: utf-8 -*-
"""
=====================================================================
 render_test.py  —  算法像素级回归测试 + 测试图生成（离屏，无窗口）
=====================================================================
两部分：
  [1] 回归：新算法层（algorithms/）与旧实现（tools/，阶段一迁移基准）
      对同一批输入的像素输出做【逐像素全等比对】。
      覆盖：直线全 8 个方向/各斜率 + 100 组随机线；圆 r=1~120；
      椭圆各比例组合；多边形（凹/凸/含水平边/退化顶点数）。
      全部一致 → 打印 PASS；任何不一致 → 打印 FAIL 并指出用例。
  [2] 出图：用新算法重新生成 运行截图/test_0X_*.png 六张测试图
      （与旧版构图一致，供报告与人工核对）。
=====================================================================
"""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---- 新算法层（被测对象） ----
from algorithms.line_dda import dda_line as dda_new
from algorithms.line_bresenham import bresenham_line as bre_new
from algorithms.circle_midpoint import midpoint_circle as cir_new
from algorithms.ellipse_midpoint import midpoint_ellipse as ell_new
from algorithms.fill_scanline import scanline_fill as fill_new

# ---- 旧实现（迁移基准，阶段一结束后归档删除） ----
from tools.line_dda import dda_line as dda_old
from tools.line_bresenham import bresenham_line as bre_old
from tools.circle_midpoint import midpoint_circle as cir_old
from tools.ellipse_midpoint import midpoint_ellipse as ell_old
from tools.fill_scanline import scanline_fill as fill_old

# ---- 出图用 ----
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QColor, QPen
from PySide6.QtWidgets import QApplication

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "运行截图")
os.makedirs(OUT, exist_ok=True)

W, H = 900, 640
BG = QColor(255, 255, 255)
GRID = QColor(225, 228, 235)
AXIS = QColor(80, 130, 200)

failures = []          # (名称, 用例) 列表
total_cases = 0


def check(name, old_fn, new_fn, cases, star=True):
    """对一组用例逐个全等比对新旧输出。

    star=True  时用例元组按位置展开（dda_line(x0,y0,x1,y1)）；
    star=False 时用例整体作为单个参数（scanline_fill(vertices_list)）。
    """
    global total_cases
    for case in cases:
        total_cases += 1
        got_old = old_fn(*case) if star else old_fn(case)
        got_new = new_fn(*case) if star else new_fn(case)
        if got_old != got_new:
            failures.append((name, case))


# =====================================================================
# [1] 回归测试
# =====================================================================
# ---- 直线用例：8 方向 + 特殊斜率 ----
line_cases = [
    (0, 0, 0, 0),            # 点退化
    (0, 0, 100, 0),          # 水平 →
    (100, 0, 0, 0),          # 水平 ←
    (0, 0, 0, 100),          # 垂直 ↓
    (0, 100, 0, 0),          # 垂直 ↑
    (0, 0, 100, 100),        # 45° ↘
    (100, 100, 0, 0),        # 45° ↖
    (0, 0, 100, -100),       # 45° ↗（负坐标也允许，纯数学）
    (0, 0, 99, 49),          # 缓线 k≈0.5
    (0, 0, 49, 99),          # 陡线 k≈2
    (0, 0, 99, -49),         # 缓线负斜率
    (0, 0, 49, -99),         # 陡线负斜率
    (-50, -30, 210, 77),     # 跨象限
]
# 随机 100 组（固定种子可复现）
rng = random.Random(2026)
for _ in range(100):
    line_cases.append((rng.randint(-300, 300), rng.randint(-300, 300),
                       rng.randint(-300, 300), rng.randint(-300, 300)))

check("DDA直线", dda_old, dda_new, line_cases)
check("Bresenham直线", bre_old, bre_new, line_cases)

# ---- 圆用例：r=1~60 全量 + 大半径抽样 ----
circle_cases = [(0, 0, r) for r in range(1, 61)] + \
               [(5, -7, r) for r in (80, 120, 200, 333)]
check("中点圆", cir_old, cir_new, circle_cases)

# ---- 椭圆用例：比例组合 + 扁/立极端 ----
ellipse_cases = [(0, 0, rx, ry)
                 for rx in (1, 2, 3, 5, 10, 25, 50, 80, 120)
                 for ry in (1, 2, 3, 5, 10, 25, 50, 80, 120)] + \
                [(-10, 10, 100, 40), (10, -10, 40, 100), (0, 0, 7, 1)]
check("中点椭圆", ell_old, ell_new, ellipse_cases)

# ---- 多边形用例：凸/凹/水平边/三角/四边/退化 ----
poly_cases = [
    [(0, 0), (100, 0), (50, 80)],                       # 三角形
    [(0, 0), (100, 0), (100, 80), (0, 80)],             # 矩形（含水平边）
    [(0, 0), (100, 20), (80, 90), (50, 40), (10, 95)],  # 凹多边形
    [(10, 10), (90, 10), (70, 60), (90, 10), (20, 80)], # 自触顶点
    [(0, 0), (0, 0), (0, 0)],                           # 退化
    [(5, 5)],                                           # 单点
    [(5, 5), (60, 5)],                                  # 两点
    [(-40, -20), (80, -35), (120, 60), (10, 110), (-70, 50)],  # 跨象限五边
]
check("扫描线填充", fill_old, fill_new, poly_cases, star=False)

print("=" * 64)
print("算法像素级回归（新 algorithms/ vs 旧 tools/ 基准）")
print(f"用例总数: {total_cases}")
if failures:
    print(f"结果: FAIL ✗（{len(failures)} 处不一致）")
    for name, case in failures[:10]:
        print(f"  [{name}] case = {case}")
    sys.exit(1)
print("结果: PASS ✓ —— 新旧像素输出完全一致")


# =====================================================================
# [2] 生成测试图（与旧版构图一致，换用新算法）
# =====================================================================
app = QApplication.instance() or QApplication(sys.argv)


def new_canvas():
    img = QImage(W, H, QImage.Format_RGB32)
    img.fill(BG)
    p = QPainter(img)
    # 网格
    p.setPen(QPen(GRID, 1))
    for x in range(0, W, 20):
        p.drawLine(x, 0, x, H)
    for y in range(0, H, 20):
        p.drawLine(0, y, W, y)
    # 坐标轴
    p.setPen(QPen(AXIS, 1, Qt.DashLine))
    p.drawLine(W // 2, 0, W // 2, H)
    p.drawLine(0, H // 2, W, H // 2)
    return img, p


def save(img, name):
    path = os.path.join(OUT, name)
    img.save(path)
    print("saved:", path)


# 1. DDA 直线：不同斜率
img, p = new_canvas()
p.setPen(QPen(QColor("#F76B15"), 2))
cx, cy = W // 2, H // 2
for (x0, y0, x1, y1) in [
    (cx - 200, cy, cx + 200, cy),
    (cx, cy - 150, cx, cy + 150),
    (cx - 150, cy - 150, cx + 150, cy + 150),
    (cx - 50, cy - 200, cx + 50, cy + 200),
    (cx - 200, cy - 50, cx + 200, cy + 50),
]:
    for (x, y) in dda_new(x0, y0, x1, y1):
        p.drawPoint(x, y)
p.end()
save(img, "test_01_DDA直线_多斜率.png")

# 2. Bresenham 直线：同斜率对比
img, p = new_canvas()
cx, cy = W // 2, H // 2
p.setPen(QPen(QColor("#3E63DD"), 2))
for (x0, y0, x1, y1) in [
    (cx - 200, cy, cx + 200, cy),
    (cx, cy - 150, cx, cy + 150),
    (cx - 150, cy - 150, cx + 150, cy + 150),
    (cx - 50, cy - 200, cx + 50, cy + 200),
    (cx - 200, cy - 50, cx + 200, cy + 50),
]:
    for (x, y) in bre_new(x0, y0, x1, y1):
        p.drawPoint(x, y)
p.end()
save(img, "test_02_Bresenham直线_多斜率.png")

# 3. DDA vs Bresenham 叠加对比（同一直线）
img, p = new_canvas()
cx, cy = W // 2, H // 2
p.setPen(QPen(QColor("#F76B15"), 5))
for (x, y) in dda_new(cx - 200, cy - 50, cx + 200, cy + 80):
    p.drawPoint(x, y)
p.setPen(QPen(QColor("#3E63DD"), 2))
for (x, y) in bre_new(cx - 200, cy - 50, cx + 200, cy + 80):
    p.drawPoint(x, y)
p.end()
save(img, "test_03_DDA与Bresenham对比.png")

# 4. 中点圆
img, p = new_canvas()
cx, cy = W // 2, H // 2
p.setPen(QPen(QColor("#8764b8"), 2))
for r in [40, 80, 120, 160]:
    for (x, y) in cir_new(cx, cy, r):
        p.drawPoint(x, y)
p.end()
save(img, "test_04_中点圆_多半径.png")

# 5. 中点椭圆
img, p = new_canvas()
cx, cy = W // 2, H // 2
p.setPen(QPen(QColor("#ca5010"), 2))
for (rx, ry) in [(40, 80), (120, 50), (150, 100), (80, 80)]:
    for (x, y) in ell_new(cx, cy, rx, ry):
        p.drawPoint(x, y)
p.end()
save(img, "test_05_中点椭圆_多种尺寸.png")

# 6. 扫描线填充：不规则多边形
img, p = new_canvas()
cx, cy = W // 2, H // 2
poly = [
    (cx - 150, cy + 100),
    (cx - 50, cy - 120),
    (cx + 80, cy - 80),
    (cx + 180, cy + 20),
    (cx + 100, cy + 130),
    (cx - 30, cy + 80),
]
p.setPen(QPen(QColor("#107c10"), 1))
for (x, y) in fill_new(poly):
    p.drawPoint(x, y)
p.setPen(QPen(QColor("#107c10"), 2))
for i in range(len(poly)):
    x0, y0 = poly[i]
    x1, y1 = poly[(i + 1) % len(poly)]
    for (x, y) in bre_new(x0, y0, x1, y1):
        p.drawPoint(x, y)
p.end()
save(img, "test_06_扫描线填充_不规则多边形.png")

print("ALL DONE")
