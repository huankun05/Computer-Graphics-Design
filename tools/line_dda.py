# -*- coding: utf-8 -*-
"""
=====================================================================
 tools/line_dda.py  —  DDA 直线生成算法（任意斜率）
=====================================================================
DDA (Digital Differential Analyzer，数值微分法)：

  直线方程: y = k*x + b
  取步长 = max(|dx|, |dy|)，使 x 或 y 每步增量为 1；
  另一坐标按斜率做浮点增量，再四舍五入取整作为像素坐标。

  优点：思路直观，增量式计算；
  缺点：每步都有浮点运算，取整耗时。
=====================================================================
"""

from typing import List, Tuple


def dda_line(x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
    """
    在 (x0,y0) 与 (x1,y1) 之间用 DDA 算法生成像素点列表。
    自动处理任意斜率（|k|<1 与 |k|>=1 两种情况）。
    """
    dx = x1 - x0
    dy = y1 - y0

    # 水平/垂直/退化情况：直接返回端点
    if dx == 0 and dy == 0:
        return [(x0, y0)]

    # 步数 = 较长那条边的像素数，保证每步至少有一个坐标走 1 像素
    steps = max(abs(dx), abs(dy))

    # 每步的浮点增量
    x_inc = dx / steps
    y_inc = dy / steps

    x = float(x0)
    y = float(y0)

    points: List[Tuple[int, int]] = []
    for _ in range(steps + 1):
        # round() 是 DDA 的取整方式（四舍五入）
        points.append((int(round(x)), int(round(y))))
        x += x_inc
        y += y_inc
    return points
