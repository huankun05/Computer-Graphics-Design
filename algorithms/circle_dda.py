# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/circle_dda.py  —  DDA 圆（角度采样法）
=====================================================================
原理：把圆看作参数方程的连续曲线，对角度 θ 均匀采样：

    x = cx + r·cosθ ,  y = cy + r·sinθ ,  θ = 2π·i/n

  采样点数 n 取周长（2πr），每点四舍五入取整。

教学价值：与中点圆对比——
  - 中点圆用决策项逐步选点，像素分布均匀、无空洞；
  - DDA 采样法在曲率大处（45° 方向）可能出现像素重合/空隙，
    放大对比两种算法的像素归属差异，正是"算法对比"的好素材。

双出口（规范契约①）：
  dda_circle()       -> 最终像素列表
  dda_circle_steps() -> 步骤流（每步记录 θ 与采样点）
=====================================================================
"""

import math
from typing import List, Tuple

from algorithms.steps import Step, expand_steps
from algorithms.line_bresenham import bresenham_line


def dda_circle_steps(cx: int, cy: int, r: int) -> List[Step]:
    """以 (cx,cy) 为圆心、r 为半径，角度采样法生成圆周【步骤流】。"""
    if r < 0:
        r = -r
    if r == 0:
        return [Step([(cx, cy)], {"x": cx, "y": cy, "θ": "—"}, "r=0，退化为圆心点")]

    # 采样点数 = 周长（每弧长 ≈1 取一点）
    n = max(24, int(2 * math.pi * r))
    samples: List[Tuple[int, int]] = []
    for i in range(n):
        th = 2 * math.pi * i / n
        x = int(round(cx + r * math.cos(th)))
        y = int(round(cy + r * math.sin(th)))
        samples.append((x, y))

    # 封闭处理：四舍五入会使相邻采样点"角接触"甚至跳格，
    # 相邻采样点距离超过 1 格时用线段补齐，最后强制首尾闭合。
    chain: List[Tuple[int, int]] = [samples[0]]
    patched: List[bool] = [False]      # 与 chain 对齐：该点是否来自补线段
    for i in range(1, n):
        prev, cur = chain[-1], samples[i]
        if max(abs(cur[0] - prev[0]), abs(cur[1] - prev[1])) > 1:
            # 补线段[1:] 已含 cur 本身，直接整段接入（避免 cur 重复）
            chain.extend(bresenham_line(prev[0], prev[1], cur[0], cur[1])[1:])
            patched.extend([True] * (len(chain) - len(patched)))
        else:
            chain.append(cur)
            patched.append(False)
    chain.extend(bresenham_line(chain[-1][0], chain[-1][1],
                                samples[0][0], samples[0][1])[1:])
    patched.extend([True] * (len(chain) - len(patched)))

    steps: List[Step] = []
    for k, (x, y) in enumerate(chain):
        steps.append(Step(
            [(x, y)],
            {"i": f"{k}/{len(chain)}", "x": x, "y": y},
            f"{'补线段点' if patched[k] else '采样点'} ({x},{y})",
        ))
    return steps


def dda_circle(cx: int, cy: int, r: int) -> List[Tuple[int, int]]:
    """角度采样法圆周像素列表（由步骤流展开，保证逐步版本一致）。"""
    return expand_steps(dda_circle_steps(cx, cy, r))
