# -*- coding: utf-8 -*-
"""
=====================================================================
 tools/circle_midpoint.py  —  中点画圆算法（中点圆法）
=====================================================================
中点圆算法原理：

  圆关于 x 轴、y 轴、y=x、y=-x 都对称，因此只需计算 1/8 圆弧
  （从 (0,r) 到 (r/√2, r/√2)），其余 7/8 由对称性镜像得到。

  在 x 从 0 递增到 y 的过程中，下一个候选点是 (x+1, y) 与
  (x+1, y-1) 的中点。用决策项 p 判断哪个点更接近真实圆：

      初值 p = 1 - r
      若 p < 0：取 (x+1, y)，  p += 2x + 3
      若 p >=0：取 (x+1, y-1)，p += 2(x - y) + 5；同时 y 自减 1

  全部为整数运算。
=====================================================================
"""

from typing import List, Tuple


def midpoint_circle(cx: int, cy: int, r: int) -> List[Tuple[int, int]]:
    """以 (cx,cy) 为圆心、r 为半径，生成圆周像素点列表。"""
    points: List[Tuple[int, int]] = []

    if r < 0:
        r = -r
    if r == 0:
        return [(cx, cy)]

    def plot_sym(px: int, py: int):
        """把 (px,py) 按八对称写到圆周上（相对圆心偏移）。"""
        points.extend([
            (cx + px, cy + py),
            (cx - px, cy + py),
            (cx + px, cy - py),
            (cx - px, cy - py),
            (cx + py, cy + px),
            (cx - py, cy + px),
            (cx + py, cy - px),
            (cx - py, cy - px),
        ])

    x = 0
    y = r
    p = 1 - r          # 决策项初值

    plot_sym(x, y)
    while x < y:
        if p < 0:
            # 中点在圆内，取右边的点 (x+1, y)
            p += 2 * x + 3
        else:
            # 中点在圆外，取右下方点 (x+1, y-1)
            p += 2 * (x - y) + 5
            y -= 1
        x += 1
        plot_sym(x, y)

    return points
