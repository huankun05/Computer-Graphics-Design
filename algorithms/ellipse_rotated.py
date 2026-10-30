# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/ellipse_rotated.py  —  任意旋转角椭圆的光栅化
=====================================================================
中点椭圆算法只适用于轴对齐椭圆（angle=0）。二维变换引入旋转后，
椭圆主轴不再与坐标轴平行，这里用【扫描线 + 二次方程求交】生成：

  1. 每行 y 代入椭圆隐式方程，解出该行与椭圆的左右交点；
  2. 交点之间的整数 x 组成该行内部像素；
  3. 内部像素集合做 4 邻域边界提取，得到闭合、8 连通的轮廓。

椭圆隐式方程（局部坐标 u/v 旋转 θ 后）：
    (u/rx)² + (v/ry)² ≤ 1
    u = c·X + s·Y,  v = -s·X + c·Y   (X=x-cx, Y=y-cy)
展开后对固定 Y 是关于 X 的二次不等式，直接求根即可。

本模块只做像素生成，不依赖 Qt；angle=0 时 rasterizer 仍走原
中点椭圆算法，保证既有像素回归完全不变。
=====================================================================
"""

from __future__ import annotations

import math
from typing import List, Tuple

Pixel = Tuple[int, int]


def rotated_ellipse(cx: int, cy: int, rx: int, ry: int,
                    angle_deg: float) -> Tuple[List[Pixel], List[Pixel]]:
    """返回 (轮廓像素, 填充像素)；两者均按 (x, y) 升序去重。"""
    rx = max(1, int(round(rx)))
    ry = max(1, int(round(ry)))
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)

    inv_rx2 = 1.0 / (rx * rx)
    inv_ry2 = 1.0 / (ry * ry)
    # 二次项：A·X² + B(Y)·X + C(Y) ≤ 0（X = x - cx）
    qa = c * c * inv_rx2 + s * s * inv_ry2
    qb = 2.0 * c * s * (inv_rx2 - inv_ry2)
    qc = s * s * inv_rx2 + c * c * inv_ry2

    # 旋转后椭圆的轴对齐包围盒半宽/半高
    hw = math.hypot(c * rx, s * ry)
    hh = math.hypot(s * rx, c * ry)
    y0 = int(math.floor(cy - hh)) - 1
    y1 = int(math.ceil(cy + hh)) + 1

    inside = set()
    for y in range(y0, y1 + 1):
        dy = y - cy
        b = qb * dy
        cc = qc * dy * dy - 1.0
        disc = b * b - 4.0 * qa * cc
        if disc < 0.0:
            continue
        root = math.sqrt(disc)
        xl = (-b - root) / (2.0 * qa)
        xr = (-b + root) / (2.0 * qa)
        # 求根得到的是相对圆心的 X，需加回 cx 才是画布坐标
        i0 = int(math.ceil(cx + xl - 1e-9))
        i1 = int(math.floor(cx + xr + 1e-9))
        if i0 > i1:
            continue
        for x in range(i0, i1 + 1):
            inside.add((x, y))

    # 4 邻域边界：任何一个上下左右邻居不在内部，即为轮廓像素。
    # 这样轮廓天然闭合，且与填充严格不重叠。
    outline = set()
    for (x, y) in inside:
        if ((x - 1, y) not in inside or (x + 1, y) not in inside or
                (x, y - 1) not in inside or (x, y + 1) not in inside):
            outline.add((x, y))
    fill = inside - outline
    return sorted(outline), sorted(fill)
