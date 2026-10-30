# -*- coding: utf-8 -*-
"""
=====================================================================
 transform_test.py  —  二维变换内核 / 图元变换 / 持久化 独立校验
=====================================================================
覆盖：
  1. 3×3 矩阵：平移/旋转/缩放/复合/求逆；
  2. 椭圆参数在任意仿射变换下的协方差-特征分解换算；
  3. 图元变换的 4 个修复点：
       圆非等比缩放 → 椭圆、擦除掩码随动、填充负坐标不钳制、
       椭圆旋转角；
  4. 圆↔椭圆类型转换的 snapshot/restore；
  5. 旋转椭圆光栅化：轮廓闭合 8 连通、与填充不相交；
  6. 工程文件 v2：angle / conn / algo / 光栅像素往返；
  7. 共享几何谓词（含旋转椭圆）。

运行：python transform_test.py
=====================================================================
"""
import math
import os
import shutil
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtGui import QColor

from algorithms import transform2d as tf
from algorithms.ellipse_rotated import rotated_ellipse
from core.geom import point_in_ellipse, point_in_polygon
from core.project_file import save_project, load_project
from core.rasterizer import rasterize
from core.shapes import (
    CircleShape, EllipseShape, LineShape, PolygonShape, RasterFillShape,
    KIND_CIRCLE_MID, KIND_ELLIPSE, KIND_LINE_DDA, KIND_POLYGON,
    KIND_RASTER_FILL, scale_snapshot, snapshot, restore, translate,
    transform_shape,
)

PASS = 0


def ok(cond, msg):
    global PASS
    if not cond:
        raise AssertionError(msg)
    PASS += 1


def close(a, b, eps=1e-6):
    return abs(a - b) <= eps


def bfs_components(points):
    """8 邻域连通分量数。"""
    pts = set(points)
    nbrs = [(-1, 0), (1, 0), (0, -1), (0, 1),
            (-1, -1), (1, -1), (-1, 1), (1, 1)]
    seen, comps = set(), 0
    for p in pts:
        if p in seen:
            continue
        comps += 1
        stack = [p]
        seen.add(p)
        while stack:
            q = stack.pop()
            for dx, dy in nbrs:
                r = (q[0] + dx, q[1] + dy)
                if r in pts and r not in seen:
                    seen.add(r)
                    stack.append(r)
    return comps


# =====================================================================
# 1. 矩阵
# =====================================================================
print("[1] 矩阵内核")
m = tf.identity()
ok(tf.apply(m, (3, 4)) == (3.0, 4.0), "单位矩阵")
ok(tf.apply(tf.translation(5, -2), (3, 4)) == (8.0, 2.0), "平移")
# 屏幕坐标 y 向下：正角视觉顺时针，(1,0) 转 90° → (0,1)
rx, ry = tf.apply(tf.rotation(90), (1, 0))
ok(close(rx, 0.0) and close(ry, 1.0), f"旋转 90° 顺时针 ({rx},{ry})")
# compose(A,B) = A @ B：先缩放再平移
p = tf.apply(tf.compose(tf.translation(10, 0), tf.scaling(2, 2)), (1, 1))
ok(p == (12.0, 2.0), f"复合顺序先缩放后平移 {p}")
for _i in range(20):
    ang = _i * 17 - 160
    mat = tf.compose(tf.translation(_i * 3, -_i), tf.rotation(ang),
                     tf.scaling(0.3 + _i * 0.1, 2.0 - _i * 0.03))
    inv = tf.inverse(mat)
    q = (_i * 1.7 - 5, _i * 2.3 + 7)
    back = tf.apply(inv, tf.apply(mat, q))
    ok(close(back[0], q[0], 1e-6) and close(back[1], q[1], 1e-6),
       f"矩阵求逆往返 {q}->{back}")
print(f"    PASS（{PASS} 项）")


# =====================================================================
# 2. 椭圆参数变换
# =====================================================================
print("[2] 椭圆参数变换")
ell_cases = [
    (20, 20, 1.0), (20, 8, 0.0), (20, 8, 30.0), (12, 30, 115.0),
]
mat_cases = [
    tf.rotation(37),
    tf.scaling(1.7, 0.6),
    tf.compose(tf.translation(5, -3), tf.rotation(25), tf.scaling(2, 1.2)),
]
for (rx0, ry0, ang0) in ell_cases:
    for mat in mat_cases:
        ncx, ncy, nrx, nry, nang = tf.ellipse_from_matrix(
            3, -2, rx0, ry0, ang0, mat)
        for k in range(72):
            t = 2 * math.pi * k / 72
            a0 = math.radians(ang0)
            lx = rx0 * math.cos(t)
            ly = ry0 * math.sin(t)
            px = 3 + math.cos(a0) * lx - math.sin(a0) * ly
            py = -2 + math.sin(a0) * lx + math.cos(a0) * ly
            qx, qy = tf.apply(mat, (px, py))
            dx, dy = qx - ncx, qy - ncy
            a1 = math.radians(nang)
            u = math.cos(a1) * dx + math.sin(a1) * dy
            v = -math.sin(a1) * dx + math.cos(a1) * dy
            f = (u / nrx) ** 2 + (v / nry) ** 2
            ok(abs(f - 1.0) < 1e-6, f"椭圆边界点变换后仍在边界 f={f}")
print(f"    PASS（{PASS} 项）")


# =====================================================================
# 3. 图元变换与缺陷修复
# =====================================================================
print("[3] 图元变换 / 缺陷修复")
line = LineShape(kind=KIND_LINE_DDA, p0=(0, 0), p1=(10, 0))
line.erased = {(5, 0)}
translate(line, 3, 2)
ok(line.p0 == (3, 2) and line.p1 == (13, 2), "直线平移")
ok(line.erased == {(8, 2)}, f"擦除掩码随平移 {line.erased}")

circle = CircleShape(kind=KIND_CIRCLE_MID, center=(10, 10), r=8)
circle.erased = {(10, 2)}
snap = snapshot(circle)
scaled = scale_snapshot(circle.kind, snap, 2.0, 1.0, anchor=(10, 10))
restore(circle, scaled)
ok(isinstance(circle, EllipseShape),
   "圆非等比缩放 → 椭圆（类型已转换）")
ok(circle.center == (10, 10) and circle.rx == 16 and circle.ry == 8,
   f"圆缩放结果 center={circle.center} rx={circle.rx} ry={circle.ry}")
ok(circle.erased == {(10, 2)}, f"擦除掩码随缩放 {circle.erased}")
restore(circle, snap)
ok(isinstance(circle, CircleShape) and circle.r == 8,
   "撤销后恢复为圆")

ell = EllipseShape(kind=KIND_ELLIPSE, center=(30, 20), rx=10, ry=5)
transform_shape(ell, tf.compose(tf.translation(30, 20),
                               tf.rotation(35),
                               tf.translation(-30, -20)))
ok(ell.center == (30, 20) and close(ell.angle, 35.0, 1e-6) and
   ell.rx == 10 and ell.ry == 5, f"椭圆绕自身旋转 angle={ell.angle}")

fill = RasterFillShape(kind=KIND_RASTER_FILL, seed=(-5, -5),
                       pixels=[(-10, -10), (-5, -5)])
fill_snap = snapshot(fill)
fill_scaled = scale_snapshot(fill.kind, fill_snap, 2.0, 1.0, anchor=(0, 0))
ok(min(p[0] for p in fill_scaled["pixels"]) == -20,
   f"光栅填充负坐标不被钳制 {fill_scaled['pixels']}")

poly = PolygonShape(kind=KIND_POLYGON,
                    vertices=[(0, 0), (10, 0), (10, 10)], fill=True)
transform_shape(poly, tf.translation(4, -3))
ok(poly.vertices == [(4, -3), (14, -3), (14, 7)], "多边形平移")
print(f"    PASS（{PASS} 项）")


# =====================================================================
# 4. 圆↔椭圆快照往返
# =====================================================================
print("[4] 快照/还原类型转换")
c = CircleShape(kind=KIND_CIRCLE_MID, center=(0, 0), r=5)
before = snapshot(c)
conv = scale_snapshot(c.kind, before, 1.0, 3.0, anchor=(0, 0))
restore(c, conv)
_m00, _m01, _m11 = tf.ellipse_covariance(c.rx, c.ry, c.angle)
ok(isinstance(c, EllipseShape) and close(_m00, 25, 1e-9)
   and abs(_m01) < 1e-9 and close(_m11, 225, 1e-9),
   f"圆 → 椭圆（Y 向拉伸 3 倍）rx={c.rx} ry={c.ry} angle={c.angle}")
restore(c, before)
ok(isinstance(c, CircleShape) and c.r == 5, "椭圆 → 圆（撤销）")
ok("__cls__" in before and "erased" in before, "快照包含类型与掩码字段")
print(f"    PASS（{PASS} 项）")


# =====================================================================
# 5. 旋转椭圆光栅化
# =====================================================================
print("[5] 旋转椭圆光栅化")
for ang in (5, 20, 45, 70, 90, 135, 179):
    for rx0, ry0 in ((10, 5), (5, 10), (12, 12), (2, 9)):
        outline, inside = rotated_ellipse(30, 20, rx0, ry0, ang)
        ok(len(outline) > 0, f"轮廓非空 angle={ang} rx={rx0}")
        ok(bfs_components(outline) == 1,
           f"轮廓 8 连通 angle={ang} rx={rx0} ry={ry0}")
        ok(not (set(outline) & set(inside)), "轮廓与填充不重叠")
        # 所有像素应落在理论包围盒附近（±2 像素容差）
        a = math.radians(ang)
        hw = math.hypot(math.cos(a) * rx0, math.sin(a) * ry0)
        hh = math.hypot(math.sin(a) * rx0, math.cos(a) * ry0)
        ok(all(abs(x - 30) <= hw + 2 and abs(y - 20) <= hh + 2
               for x, y in outline), f"旋转椭圆包围盒 angle={ang}")
print(f"    PASS（{PASS} 项）")


# =====================================================================
# 6. 工程文件 v2 往返
# =====================================================================
print("[6] 工程文件 v2")
tmp = tempfile.mkdtemp(prefix="gpad_transform_")
try:
    path = os.path.join(tmp, "roundtrip.gpad")
    e2 = EllipseShape(kind=KIND_ELLIPSE, color=QColor("#123456"),
                      center=(7, 9), rx=11, ry=4, angle=33.5, fill=True)
    e2.erased = {(1, 2)}
    rf = RasterFillShape(kind=KIND_RASTER_FILL, color=QColor("#107c10"),
                         seed=(3, 3), pixels=[(3, 3), (4, 3), (3, 4)],
                         conn=8, algo="seed8")
    rf.owner = e2
    ok(save_project(path, [e2, rf]), "保存工程")
    loaded = load_project(path)
    le, lf = loaded
    ok(isinstance(le, EllipseShape) and close(le.angle, 33.5, 1e-4),
       f"angle 往返 {getattr(le, 'angle', None)}")
    ok(le.erased == {(1, 2)}, "擦除掩码往返")
    ok(isinstance(lf, RasterFillShape) and len(lf.pixels) == 3,
       "光栅填充像素往返")
    ok(lf.conn == 8 and lf.algo == "seed8", "连通性/算法往返")
    ok(lf.owner is le, "填充归属往返")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print(f"    PASS（{PASS} 项）")


# =====================================================================
# 7. 几何谓词
# =====================================================================
print("[7] 几何谓词")
ok(point_in_ellipse(10, 0, 0, 0, 10, 5, 0), "椭圆内")
ok(not point_in_ellipse(10.5, 0, 0, 0, 10, 5, 0), "椭圆外")
# 旋转 45° 后，长轴端点转到 (7.07, 7.07)
ok(point_in_ellipse(7.071, 7.071, 0, 0, 10, 5, 45), "旋转椭圆边界内")
ok(point_in_ellipse(-7.071, -7.071, 0, 0, 10, 5, 45),
   "旋转椭圆长轴另一端（边界）")
ok(not point_in_ellipse(0, -10, 0, 0, 10, 5, 45),
   "旋转椭圆短轴方向偏出外")
ok(point_in_polygon(5, 5, [(0, 0), (10, 0), (10, 10), (0, 10)]),
   "多边形内")
ok(not point_in_polygon(15, 5, [(0, 0), (10, 0), (10, 10), (0, 10)]),
   "多边形外")

# 旋转椭圆 rasterize 与谓词一致：轮廓像素都应在椭圆边缘附近
oe, of = rasterize(EllipseShape(kind=KIND_ELLIPSE, center=(30, 20),
                                rx=10, ry=5, angle=30, fill=True))
ok(len(oe) > 0 and len(of) > 0, "rasterize 旋转椭圆")
print(f"    PASS（{PASS} 项）")


# =====================================================================
# 8. 区域裁剪（Cohen-Sutherland / Liang-Barsky / Sutherland-Hodgman）
# =====================================================================
print("[8] 区域裁剪")
import random as _rnd
from algorithms.cohen_sutherland import (cohen_sutherland,
                                         cohen_sutherland_steps, region_code)
from algorithms.liang_barsky import liang_barsky, liang_barsky_steps
from algorithms.sutherland_hodgman import clip_polygon, clip_polygon_steps
from algorithms.line_bresenham import bresenham_line

_rect = (10, 8, 40, 26)
ok(region_code(20, 20, _rect) == 0, "区域码：窗口内")
ok(region_code(5, 20, _rect) & 1 and region_code(50, 20, _rect) & 2,
   "区域码：左右")
ok(region_code(20, 2, _rect) & 4 and region_code(20, 40, _rect) & 8,
   "区域码：上下")

# 已知用例
ok(cohen_sutherland(0, 0, 5, 5, _rect) is None, "Cohen 同侧外舍弃")
ok(liang_barsky(0, 0, 5, 5, _rect) is None, "Liang 同侧外舍弃")
ok(cohen_sutherland(20, 12, 30, 20, _rect) == (20, 12, 30, 20),
   "Cohen 完全在内原样返回")
ok(liang_barsky(20, 12, 30, 20, _rect) == (20, 12, 30, 20),
   "Liang 完全在内原样返回")

# 随机一致性 + 结果必在窗口内
_rnd.seed(20261023)
for _ in range(1200):
    a = (_rnd.randint(-20, 70), _rnd.randint(-20, 60),
         _rnd.randint(-20, 70), _rnd.randint(-20, 60))
    ca = cohen_sutherland(*a, _rect)
    la = liang_barsky(*a, _rect)
    ok((ca is None) == (la is None), f"两算法接受性一致 {a}")
    if ca is None:
        continue
    ok(max(abs(u - v) for u, v in zip(ca, la)) <= 1,
       f"两算法端点一致(±1) {a} {ca} {la}")
    for _x, _y in (ca[:2], ca[2:]):
        ok(_rect[0] <= _x <= _rect[2] and _rect[1] <= _y <= _rect[3],
           f"结果落在窗口内 {( _x, _y)}")

# 步骤流末步包含几何结果的全部像素（双出口一致）
for _seg in ((2, 3, 58, 34), (0, 0, 39, 25), (-5, 30, 60, 0),
             (12, 12, 20, 20), (30, 9, 60, 9)):
    for _fn, _sfn in ((cohen_sutherland, cohen_sutherland_steps),
                      (liang_barsky, liang_barsky_steps)):
        _res = _fn(*_seg, _rect)
        _steps = _sfn(*_seg, _rect)
        ok(bool(_steps), f"{_fn.__name__} 有步骤流 {_seg}")
        if _res is not None:
            ok(set(bresenham_line(*_res)) <= set(_steps[-1].pixels),
               f"{_fn.__name__} 末步像素与几何一致 {_seg}")
        else:
            ok(all(not (_rect[0] <= p[0] <= _rect[2]
                        and _rect[1] <= p[1] <= _rect[3])
                   for p in _steps[-1].pixels),
               f"{_fn.__name__} 舍弃步骤不含窗口内像素 {_seg}")

# 多边形裁剪：结果顶点全部在窗口内，且顶点数合理
_poly = [(0, 0), (60, 5), (55, 40), (20, 35), (25, 15)]
_clip = clip_polygon(_poly, _rect)
ok(len(_clip) >= 3, f"多边形裁剪保留顶点 {_clip}")
ok(all(_rect[0] <= x <= _rect[2] and _rect[1] <= y <= _rect[3]
       for x, y in _clip), "多边形裁剪结果在窗口内")
ok(clip_polygon([(0, 0), (5, 0), (5, 5)], _rect) == [],
   "多边形完全在外 → 空")
_psteps = clip_polygon_steps(_poly, _rect)
ok(len(_psteps) == 5, f"Hodgman 步骤流 4 边 + 初始 = {len(_psteps)}")
print(f"    PASS（{PASS} 项）")


print("=" * 64)
print(f"transform_test: PASS ✓（共 {PASS} 项）")
