# -*- coding: utf-8 -*-
"""
=====================================================================
 tools/ellipse_midpoint.py  —  中点椭圆生成算法
=====================================================================
椭圆方程: (x/rx)^2 + (y/ry)^2 = 1

椭圆关于 x 轴、y 轴对称，只需画第一象限，再四对称复制。

第一象限又分两个区域，分界点为斜率 = -1 处：
  区域 1：从 (0, ry) 开始，|斜率| > 1，x 走大步；
  区域 2：从分界点开始，|斜率| < 1，y 走大步。

  区域 1 决策项 p1：
      初值 p1 = ry*ry - rx*rx*ry + rx*rx/4
      若 p1 < 0：p1 += 2*ry*ry*x + ry*ry
      若 p1 ≥ 0：p1 += 2*ry*ry*x + ry*ry - 2*rx*rx*y；y 自减 1
      退出条件：2*ry*ry*x >= 2*rx*rx*y

  区域 2 决策项 p2（从区域 1 结束的 (x,y) 开始）：
      初值 p2 = ry*ry*(x+0.5)^2 + rx*rx*(y-1)^2 - rx*rx*ry*ry
      若 p2 > 0：p2 += rx*rx - 2*rx*rx*y
      若 p2 ≤ 0：p2 += rx*rx - 2*rx*rx*y + 2*ry*ry*x；x 自增 1
      退出条件：y < 0
=====================================================================
"""

from typing import List, Tuple


def midpoint_ellipse(cx: int, cy: int, rx: int, ry: int) -> List[Tuple[int, int]]:
    """以 (cx,cy) 为中心，rx/ry 为 x/y 半轴，生成椭圆周像素点。"""
    points: List[Tuple[int, int]] = []
    rx, ry = abs(rx), abs(ry)
    if rx == 0 and ry == 0:
        return [(cx, cy)]

    def plot_sym(px: int, py: int):
        """四对称写点。"""
        points.extend([
            (cx + px, cy + py),
            (cx - px, cy + py),
            (cx + px, cy - py),
            (cx - px, cy - py),
        ])

    x = 0
    y = ry
    rx2 = rx * rx
    ry2 = ry * ry

    # ---------- 区域 1：|斜率| > 1，x 走大步 ----------
    p1 = ry2 - rx2 * ry + (rx2 >> 2)   # 初值
    plot_sym(x, y)
    while 2 * ry2 * x < 2 * rx2 * y:
        x += 1
        if p1 < 0:
            p1 += 2 * ry2 * x + ry2
        else:
            y -= 1
            p1 += 2 * ry2 * x + ry2 - 2 * rx2 * y
        plot_sym(x, y)

    # ---------- 区域 2：|斜率| <= 1，y 走大步 ----------
    # 从区域 1 结束的 (x,y) 重新初始化 p2
    p2 = int(ry2 * (x + 0.5) ** 2 + rx2 * (y - 1) ** 2 - rx2 * ry2)
    while y >= 0:
        y -= 1
        if p2 > 0:
            p2 += rx2 - 2 * rx2 * y
        else:
            x += 1
            p2 += rx2 - 2 * rx2 * y + 2 * ry2 * x
        plot_sym(x, y)

    return points
