# -*- coding: utf-8 -*-
"""
=====================================================================
 tools/line_bresenham.py  —  Bresenham 直线生成算法（任意斜率）
=====================================================================
Bresenham 算法（中点误差项法）：

  只使用整数加法与位移，避免 DDA 的浮点运算。
  原理：从直线一个端点出发，每步在主方向上走 1 像素，
  由决策项（误差项）的符号决定另一坐标是否同时走 1。

  本实现采用【通用版】：当 |斜率|>1 时自动交换 x/y 的主方向，
  因此真正支持任意斜率（水平、垂直、45°、陡峭线都正确）。
=====================================================================
"""

from typing import List, Tuple


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
    """Bresenham 直线，返回像素点列表。"""
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)

    # 步进方向：sx/sy 为 ±1
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1

    # 决策项初值：2*dy - dx（教材标准式）
    err = dx - dy

    x, y = x0, y0
    points: List[Tuple[int, int]] = []

    while True:
        points.append((x, y))

        # 到达终点则结束
        if x == x1 and y == y1:
            break

        # 两倍误差项，避免除法
        e2 = 2 * err
        if e2 > -dy:          # 横向该走
            err -= dy
            x += sx
        if e2 < dx:           # 纵向该走
            err += dx
            y += sy

    return points
