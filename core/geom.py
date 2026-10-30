# -*- coding: utf-8 -*-
"""
=====================================================================
 core/geom.py  —  共享几何谓词（解析判定，不生成像素）
=====================================================================
填充归属、命中测试等都要判断"点是否在闭合图元内"。旧实现把
几套公式散落在工具里，且无法处理旋转椭圆；这里集中成一份：

  - point_in_circle / point_in_ellipse（支持任意旋转角）
  - point_in_polygon（射线法）
  - shape_contains（按图元类型分派）
  - bbox_of（解析式包围盒：命中测试/选中框不再逐图元光栅化）

全部是纯数值计算，不依赖 Qt，也不光栅化，适合高频调用。
=====================================================================
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

from core.shapes import (
    CircleShape, EllipseShape, LineShape, PolygonShape, RasterFillShape, Shape,
)

Point = Tuple[float, float]


def point_in_circle(x: float, y: float, cx: float, cy: float,
                    r: float) -> bool:
    """点是否在圆内（含边界）。"""
    dx, dy = x - cx, y - cy
    return dx * dx + dy * dy <= max(0.0, r) ** 2


def point_in_ellipse(x: float, y: float, cx: float, cy: float,
                     rx: float, ry: float, angle_deg: float = 0.0) -> bool:
    """点是否在椭圆内（含边界），angle 为屏幕坐标下的顺时针角。"""
    rx = max(1e-9, abs(rx))
    ry = max(1e-9, abs(ry))
    dx, dy = x - cx, y - cy
    if abs(angle_deg) > 1e-9:
        a = math.radians(angle_deg)
        c, s = math.cos(a), math.sin(a)
        # 逆旋转回局部坐标
        u = c * dx + s * dy
        v = -s * dx + c * dy
    else:
        u, v = dx, dy
    return (u / rx) ** 2 + (v / ry) ** 2 <= 1.0 + 1e-9


def point_in_polygon(x: float, y: float, vertices) -> bool:
    """射线法判断点是否在多边形内（含边界近似）。"""
    if len(vertices) < 3:
        return False
    inside = False
    n = len(vertices)
    for i in range(n):
        x0, y0 = vertices[i]
        x1, y1 = vertices[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if xi > x:
                inside = not inside
    return inside


def shape_contains(shape: Shape, p: Point) -> bool:
    """点是否落在闭合图元的几何区域内（圆/椭圆/多边形）。"""
    x, y = p
    if isinstance(shape, CircleShape):
        return point_in_circle(x, y, shape.center[0], shape.center[1],
                               shape.r)
    if isinstance(shape, EllipseShape):
        return point_in_ellipse(x, y, shape.center[0], shape.center[1],
                                shape.rx, shape.ry,
                                getattr(shape, "angle", 0.0))
    if isinstance(shape, PolygonShape):
        return point_in_polygon(x, y, shape.vertices)
    return False


# ---------------------------------------------------------------------
# 解析式包围盒（模拟像素坐标，(x0, y0, x1, y1) 闭区间）
# ---------------------------------------------------------------------
def ellipse_extent(rx: float, ry: float, angle_deg: float) -> Tuple[float, float]:
    """旋转椭圆在 X/Y 轴上的半投影长度（=|R·diag(rx,ry)| 的行范数）。"""
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    ex = math.hypot(rx * c, ry * s)
    ey = math.hypot(rx * s, ry * c)
    return ex, ey


def bbox_of(shape: Shape) -> Optional[Tuple[int, int, int, int]]:
    """图元的解析包围盒（模拟像素，闭区间）；无像素的图元返回 None。

    与光栅化包围盒的关系：本函数给的是【保守】包围盒（可能比实际像素
    大 1 格），用于命中测试预筛与选中框显示——比逐图元 rasterize()
    快一个数量级以上，图元多时不再卡顿。
    """
    if isinstance(shape, LineShape):
        xs = (shape.p0[0], shape.p1[0])
        ys = (shape.p0[1], shape.p1[1])
        return min(xs), min(ys), max(xs), max(ys)
    if isinstance(shape, CircleShape):
        cx, cy, r = shape.center[0], shape.center[1], max(0, shape.r)
        return cx - r, cy - r, cx + r, cy + r
    if isinstance(shape, EllipseShape):
        cx, cy = shape.center
        ex, ey = ellipse_extent(shape.rx, shape.ry,
                                getattr(shape, "angle", 0.0))
        # 取整向外扩，保证任意角度下都覆盖真实像素
        return (int(math.floor(cx - ex)), int(math.floor(cy - ey)),
                int(math.ceil(cx + ex)), int(math.ceil(cy + ey)))
    if isinstance(shape, PolygonShape):
        if not shape.vertices:
            return None
        xs = [v[0] for v in shape.vertices]
        ys = [v[1] for v in shape.vertices]
        return min(xs), min(ys), max(xs), max(ys)
    if isinstance(shape, RasterFillShape):
        if not shape.pixels:
            return None
        xs = [p[0] for p in shape.pixels]
        ys = [p[1] for p in shape.pixels]
        return min(xs), min(ys), max(xs), max(ys)
    return None
