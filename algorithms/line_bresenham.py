# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/line_bresenham.py  —  Bresenham 直线生成算法（任意斜率）
=====================================================================
Bresenham 算法（中点误差项法）：

  只使用整数加法与位移，避免 DDA 的浮点运算。
  原理：从直线一个端点出发，每步在主方向上走 1 像素，
  由决策项（误差项）的符号决定另一坐标是否同时走 1。

  本实现采用【通用版】：决策项 err = dx - dy，每步看两倍误差 e2：
      e2 > -dy  → 横向该走（x += sx）
      e2 <  dx  → 纵向该走（y += sy）
  因此天然支持任意斜率（水平、垂直、45°、陡峭线都正确）。

双出口（规范契约①）：
  bresenham_line()       -> 最终像素列表（渲染用）
  bresenham_line_steps() -> 步骤流（演示模式用，err/e2 逐步可视化）
两个出口的像素输出【完全一致】，由 render_test.py 像素级回归保证。
=====================================================================
"""

from typing import List, Tuple

from algorithms.steps import Step, expand_steps

Pixel = Tuple[int, int]


def bresenham_line_steps(x0: int, y0: int, x1: int, y1: int) -> List[Step]:
    """Bresenham 直线完整步骤流，每步记录 x/y/决策项 err/两倍误差 e2。"""
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)

    # 步进方向：sx/sy 为 ±1
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1

    # 决策项初值：err = dx - dy（教材标准式）
    err = dx - dy

    step_list: List[Step] = []
    x, y = x0, y0

    while True:
        # 记录本步：当前像素 + 决策项状态
        e2 = 2 * err
        notes = []
        # 预演本步的走向，生成人话解释（不影响像素计算）
        if x == x1 and y == y1:
            notes.append("到达终点")
        else:
            if e2 > -dy:
                notes.append(f"e2={e2} > -dy → x{'+' if sx>0 else '-'}1")
            if e2 < dx:
                notes.append(f"e2={e2} < dx → y{'+' if sy>0 else '-'}1")
        step_list.append(Step(
            [(x, y)],
            {"x": x, "y": y, "dx": dx, "dy": dy, "err": err, "e2": e2},
            "；".join(notes),
        ))

        # 到达终点则结束
        if x == x1 and y == y1:
            break

        # 两倍误差项判定（避免除法），按符号决定单步或双向步进
        if e2 > -dy:          # 横向该走
            err -= dy
            x += sx
        if e2 < dx:           # 纵向该走
            err += dx
            y += sy

    return step_list


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> List[Pixel]:
    """Bresenham 直线最终像素列表（由步骤流展开，保证逐步版本一致）。"""
    return expand_steps(bresenham_line_steps(x0, y0, x1, y1))
