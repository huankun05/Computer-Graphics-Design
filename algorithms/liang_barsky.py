# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/liang_barsky.py — Liang-Barsky 参数化裁剪
=====================================================================
把线段写成参数形式 P(t) = P0 + t·(P1-P0)，t ∈ [0, 1]。
对四条窗口边界 x=rx0、x=rx1、y=ry0、y=ry1 依次求：
    p·t ≤ q
  p = -dx, dx, -dy, dy
  q = x0-rx0, rx1-x0, y0-ry0, ry1-y0
  · p == 0 且 q < 0 → 平行且在窗口外 → 整段舍弃
  · p < 0 → 从外进入，更新下界 u0 = max(u0, q/p)
  · p > 0 → 从内离开，更新上界 u1 = min(u1, q/p)
  · u0 > u1 → 舍弃

与 Cohen-Sutherland 的区别：无需反复编码求交，一次循环求出参数区间，
乘法/除法次数固定，是教学中最常用的"高效裁剪"方案。
=====================================================================
"""

from typing import List, Optional, Tuple

from algorithms.line_bresenham import bresenham_line
from algorithms.steps import Step

Rect = Tuple[int, int, int, int]
Seg = Tuple[int, int, int, int]


def _clamp(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else hi if v > hi else v


def liang_barsky(x0: int, y0: int, x1: int, y1: int,
                 rect: Rect) -> Optional[Seg]:
    """裁剪线段；返回 (x0, y0, x1, y1)，整段在外返回 None。"""
    rx0, ry0, rx1, ry1 = rect
    dx, dy = float(x1 - x0), float(y1 - y0)
    p = (-dx, dx, -dy, dy)
    q = (x0 - rx0, rx1 - x0, y0 - ry0, ry1 - y0)
    u0, u1 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if pi == 0:
            if qi < 0:
                return None
            continue
        t = qi / pi
        if pi < 0:
            u0 = max(u0, t)
        else:
            u1 = min(u1, t)
        if u0 > u1:
            return None
    ax = _clamp(int(round(x0 + u0 * dx)), rx0, rx1)
    ay = _clamp(int(round(y0 + u0 * dy)), ry0, ry1)
    bx = _clamp(int(round(x0 + u1 * dx)), rx0, rx1)
    by = _clamp(int(round(y0 + u1 * dy)), ry0, ry1)
    return ax, ay, bx, by


def _rect_perimeter(rect: Rect) -> List[Tuple[int, int]]:
    rx0, ry0, rx1, ry1 = rect
    pts = set()
    for x in range(rx0, rx1 + 1):
        pts.add((x, ry0))
        pts.add((x, ry1))
    for y in range(ry0, ry1 + 1):
        pts.add((rx0, y))
        pts.add((rx1, y))
    return sorted(pts)


def liang_barsky_steps(x0: int, y0: int, x1: int, y1: int,
                       rect: Rect) -> List[Step]:
    """参数裁剪步骤流：每处理一条边界输出一步（u0/u1 区间可见）。"""
    rx0, ry0, rx1, ry1 = rect
    border = _rect_perimeter(rect)
    dx, dy = float(x1 - x0), float(y1 - y0)
    p = (-dx, dx, -dy, dy)
    q = (x0 - rx0, rx1 - x0, y0 - ry0, ry1 - y0)
    names = ("左边界", "右边界", "上边界", "下边界")
    u0, u1 = 0.0, 1.0
    steps: List[Step] = []

    def _seg_at(a: float, b: float):
        sx = int(round(x0 + a * dx))
        sy = int(round(y0 + a * dy))
        ex = int(round(x0 + b * dx))
        ey = int(round(y0 + b * dy))
        return bresenham_line(sx, sy, ex, ey)

    steps.append(Step(sorted(set(border) | set(_seg_at(u0, u1))),
                      {"阶段": "初始", "u0": 0.0, "u1": 1.0},
                      f"初始参数区间 [{u0:.2f}, {u1:.2f}]"))
    for i, (pi, qi) in enumerate(zip(p, q)):
        if pi == 0:
            if qi < 0:
                steps.append(Step(border, {"阶段": "舍弃", "边界": names[i],
                                           "p": 0.0, "q": qi},
                                  f"{names[i]}：p=0 且 q<0 → 平行且在外，舍弃"))
                return steps
            note = f"{names[i]}：p=0 且 q≥0 → 平行于边界，无影响"
            steps.append(Step(sorted(set(border) | set(_seg_at(u0, u1))),
                              {"阶段": "跳过", "边界": names[i],
                               "p": 0.0, "q": qi}, note))
            continue
        t = qi / pi
        if pi < 0:
            u0 = max(u0, t)
            act = f"进入边：u0 = max(u0, {t:.3f}) = {u0:.3f}"
        else:
            u1 = min(u1, t)
            act = f"离开边：u1 = min(u1, {t:.3f}) = {u1:.3f}"
        if u0 > u1:
            steps.append(Step(border, {"阶段": "舍弃", "边界": names[i],
                                       "u0": u0, "u1": u1},
                              f"{names[i]}：{act} → u0>u1，舍弃"))
            return steps
        steps.append(Step(sorted(set(border) | set(_seg_at(u0, u1))),
                          {"阶段": "更新", "边界": names[i],
                           "p": pi, "q": qi, "u0": u0, "u1": u1},
                          f"{names[i]}：{act}"))
    steps.append(Step(sorted(set(border) | set(_seg_at(u0, u1))),
                      {"阶段": "输出", "u0": u0, "u1": u1},
                      f"输出区间 [{u0:.3f}, {u1:.3f}]"))
    return steps
