# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/circle_midpoint.py  —  中点画圆算法（中点圆法）
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

双出口（规范契约①）：
  midpoint_circle()       -> 最终像素列表（渲染用）
  midpoint_circle_steps() -> 步骤流（每步 = 8 个对称像素 + 决策项 p）
两个出口的像素输出【完全一致】，由 render_test.py 像素级回归保证。
=====================================================================
"""

from typing import List, Tuple

from algorithms.steps import Step, expand_steps

Pixel = Tuple[int, int]


def midpoint_circle_steps(cx: int, cy: int, r: int) -> List[Step]:
    """
    以 (cx,cy) 为圆心、r 为半径，生成圆周的【步骤流】。
    每步 = 决策项更新 + 一次八对称写点（8 个像素）。
    """
    step_list: List[Step] = []

    if r < 0:
        r = -r
    if r == 0:
        # 退化情况：半径 0 就是圆心一个点
        return [Step([(cx, cy)], {"x": 0, "y": 0, "p": 0}, "r=0，退化为圆心点")]

    def sym_pixels(px: int, py: int) -> List[Pixel]:
        """把 (px,py) 按八对称生成圆周上的 8 个像素（相对圆心偏移）。"""
        return [
            (cx + px, cy + py),
            (cx - px, cy + py),
            (cx + px, cy - py),
            (cx - px, cy - py),
            (cx + py, cy + px),
            (cx - py, cy + px),
            (cx + py, cy - px),
            (cx - py, cy - px),
        ]

    x = 0
    y = r
    p = 1 - r          # 决策项初值

    # 第一个点 (0, r)
    step_list.append(Step(sym_pixels(x, y),
                          {"x": x, "y": y, "p": p},
                          f"起点 (0,{r})，初值 p = 1 - r = {p}"))

    while x < y:
        if p < 0:
            # 中点在圆内，取右边的点 (x+1, y)：p 增量 2x+3
            p += 2 * x + 3
            note = f"p={p} < 0 → 取 (x+1,y)，p += 2x+3 = {p}"
        else:
            # 中点在圆外，取右下方点 (x+1, y-1)：p 增量 2(x-y)+5，y 自减
            p += 2 * (x - y) + 5
            y -= 1
            note = f"p ≥ 0 → 取 (x+1,y-1)，p += 2(x-y)+5 = {p}"
        x += 1
        step_list.append(Step(sym_pixels(x, y),
                              {"x": x, "y": y, "p": p}, note))

    return step_list


def midpoint_circle(cx: int, cy: int, r: int) -> List[Pixel]:
    """以 (cx,cy) 为圆心、r 为半径，生成圆周像素点列表（最终结果）。"""
    return expand_steps(midpoint_circle_steps(cx, cy, r))
