# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/cohen_sutherland.py — Cohen-Sutherland 编码裁剪
=====================================================================
矩形窗口 (x0, y0)-(x1, y1)（闭区间，含边界），屏幕坐标 y 向下。

4 位区域码（D3 D2 D1 D0）：
  LEFT=0001   RIGHT=0010   TOP=0100（y<y0）   BOTTOM=1000（y>y1）

判定：
  code0 | code1 == 0      → 完全在窗口内，直接接受
  code0 & code1 != 0      → 同侧外，直接舍弃
  否则                    → 选一个窗口外端点，按边界求交截断后重复

双出口约定（契约②）：cohen_sutherland() 返回几何，
cohen_sutherland_steps() 的末步像素与几何结果逐像素一致。
=====================================================================
"""

from typing import List, Optional, Tuple

from algorithms.line_bresenham import bresenham_line
from algorithms.steps import Step

LEFT, RIGHT, TOP, BOTTOM = 1, 2, 4, 8

Rect = Tuple[int, int, int, int]
Seg = Tuple[int, int, int, int]


def region_code(x: float, y: float, rect: Rect) -> int:
    """点 → 4 位区域码。"""
    x0, y0, x1, y1 = rect
    code = 0
    if x < x0:
        code |= LEFT
    elif x > x1:
        code |= RIGHT
    if y < y0:
        code |= TOP
    elif y > y1:
        code |= BOTTOM
    return code


def code_text(code: int) -> str:
    """区域码 → "左/右/上/下" 可读文本（监视器用）。"""
    if code == 0:
        return "0000 窗口内"
    parts = []
    for bit, name in ((LEFT, "左"), (RIGHT, "右"),
                      (TOP, "上"), (BOTTOM, "下")):
        if code & bit:
            parts.append(name)
    return f"{code:04b} " + "/".join(parts)


def _intersect(x0, y0, x1, y1, code, rect) -> Tuple[float, float]:
    """按区域码所在边界求交点（端点已保证在窗口外）。"""
    rx0, ry0, rx1, ry1 = rect
    if code & TOP:                       # y = ry0
        y = ry0
        x = x0 + (x1 - x0) * (ry0 - y0) / (y1 - y0) if y1 != y0 else x0
    elif code & BOTTOM:                  # y = ry1
        y = ry1
        x = x0 + (x1 - x0) * (ry1 - y0) / (y1 - y0) if y1 != y0 else x0
    elif code & RIGHT:                   # x = rx1
        x = rx1
        y = y0 + (y1 - y0) * (rx1 - x0) / (x1 - x0) if x1 != x0 else y0
    else:                                # x = rx0
        x = rx0
        y = y0 + (y1 - y0) * (rx0 - x0) / (x1 - x0) if x1 != x0 else y0
    return x, y


def _clamp(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else hi if v > hi else v


def cohen_sutherland(x0: int, y0: int, x1: int, y1: int,
                     rect: Rect) -> Optional[Seg]:
    """裁剪线段；返回窗口内线段 (x0, y0, x1, y1)，完全在外返回 None。"""
    rx0, ry0, rx1, ry1 = rect
    fx0, fy0, fx1, fy1 = float(x0), float(y0), float(x1), float(y1)
    while True:
        c0 = region_code(fx0, fy0, rect)
        c1 = region_code(fx1, fy1, rect)
        if not (c0 | c1):
            # 四舍五入可能把交点推出半格，最后钳到窗口内
            ax, ay = _clamp(int(round(fx0)), rx0, rx1), \
                _clamp(int(round(fy0)), ry0, ry1)
            bx, by = _clamp(int(round(fx1)), rx0, rx1), \
                _clamp(int(round(fy1)), ry0, ry1)
            return ax, ay, bx, by
        if c0 & c1:
            return None
        code = c0 if c0 else c1
        px, py = _intersect(fx0, fy0, fx1, fy1, code, rect)
        if code == c0:
            fx0, fy0 = px, py
        else:
            fx1, fy1 = px, py


def _rect_perimeter(rect: Rect) -> List[Tuple[int, int]]:
    """窗口边框像素（含四角，闭区间）。"""
    rx0, ry0, rx1, ry1 = rect
    pts = set()
    for x in range(rx0, rx1 + 1):
        pts.add((x, ry0))
        pts.add((x, ry1))
    for y in range(ry0, ry1 + 1):
        pts.add((rx0, y))
        pts.add((rx1, y))
    return sorted(pts)


def cohen_sutherland_steps(x0: int, y0: int, x1: int, y1: int,
                           rect: Rect) -> List[Step]:
    """编码裁剪步骤流：每步 = 窗口边框 + 当前线段，附两端区域码。"""
    rx0, ry0, rx1, ry1 = rect
    border = _rect_perimeter(rect)
    fx0, fy0, fx1, fy1 = float(x0), float(y0), float(x1), float(y1)
    steps: List[Step] = []
    guard = 0
    while guard < 16:
        guard += 1
        c0 = region_code(fx0, fy0, rect)
        c1 = region_code(fx1, fy1, rect)
        seg = bresenham_line(int(round(fx0)), int(round(fy0)),
                             int(round(fx1)), int(round(fy1)))
        values = {"区域码0": code_text(c0), "区域码1": code_text(c1),
                  "端点0": (int(round(fx0)), int(round(fy0))),
                  "端点1": (int(round(fx1)), int(round(fy1)))}
        if not (c0 | c1):
            steps.append(Step(sorted(set(border) | set(seg)),
                              {**values, "判定": "接受"},
                              f"两端均在窗口内（码 0000）→ 接受线段"))
            return steps
        if c0 & c1:
            steps.append(Step(border, {**values, "判定": "舍弃"},
                              "两端同侧外部（按位与非 0）→ 舍弃"))
            return steps
        code = c0 if c0 else c1
        side = ("上边界" if code & TOP else "下边界" if code & BOTTOM
                else "右边界" if code & RIGHT else "左边界")
        steps.append(Step(sorted(set(border) | set(seg)),
                          {**values, "判定": "求交"},
                          f"端点在外（{side}）→ 求交截断"))
        px, py = _intersect(fx0, fy0, fx1, fy1, code, rect)
        if code == c0:
            fx0, fy0 = px, py
        else:
            fx1, fy1 = px, py
    return steps
