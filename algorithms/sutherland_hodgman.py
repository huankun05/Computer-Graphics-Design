# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/sutherland_hodgman.py — Sutherland-Hodgman 多边形裁剪
=====================================================================
用矩形窗口的四条边界依次对多边形做"半平面裁剪"：

  对每条边界，遍历当前多边形顶点 S → E：
    · E 在内，S 在外 → 输出 S-E 与边界的交点、E
    · E、S 都在内     → 输出 E
    · E 在外，S 在内  → 输出交点
    · 都在外          → 不输出

四轮之后得到窗口内多边形（顶点顺序保持顶点的输入方向）。
适用于凸窗口裁剪任意凹/凸多边形；裁剪后的多边形可能退化为 0 边形。
=====================================================================
"""

from typing import List, Sequence, Tuple

from algorithms.line_bresenham import bresenham_line
from algorithms.steps import Step

Rect = Tuple[int, int, int, int]
Point = Tuple[float, float]


def _inside(p: Point, edge: str, rect: Rect) -> bool:
    x, y = p
    rx0, ry0, rx1, ry1 = rect
    if edge == "left":
        return x >= rx0
    if edge == "right":
        return x <= rx1
    if edge == "top":
        return y >= ry0
    return y <= ry1


def _intersect(s: Point, e: Point, edge: str, rect: Rect) -> Point:
    """线段 S→E 与窗口边界求交（S/E 一内一外，必有交点）。"""
    rx0, ry0, rx1, ry1 = rect
    sx, sy = s
    ex, ey = e
    if edge in ("left", "right"):
        x = float(rx0 if edge == "left" else rx1)
        y = sy + (ey - sy) * (x - sx) / (ex - sx) if ex != sx else sy
    else:
        y = float(ry0 if edge == "top" else ry1)
        x = sx + (ex - sx) * (y - sy) / (ey - sy) if ey != sy else sx
    return x, y


def clip_polygon(points: Sequence[Point],
                 rect: Rect) -> List[Tuple[int, int]]:
    """Sutherland-Hodgman：返回裁剪后的整数顶点（可能为空）。"""
    out = [(float(x), float(y)) for x, y in points]
    for edge in ("left", "right", "top", "bottom"):
        if not out:
            break
        src = out
        out = []
        s = src[-1]
        for e in src:
            if _inside(e, edge, rect):
                if not _inside(s, edge, rect):
                    out.append(_intersect(s, e, edge, rect))
                out.append(e)
            elif _inside(s, edge, rect):
                out.append(_intersect(s, e, edge, rect))
            s = e
    # 取整并去掉连续重复点（交点可能落在同一像素）
    ints: List[Tuple[int, int]] = []
    for x, y in out:
        p = (int(round(x)), int(round(y)))
        if not ints or ints[-1] != p:
            ints.append(p)
    if len(ints) > 1 and ints[0] == ints[-1]:
        ints.pop()
    return ints


def polygon_outline(points: Sequence[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """多边形闭合轮廓像素（逐边 Bresenham）。"""
    pts = list(points)
    out = []
    if len(pts) < 2:
        return list(pts)
    for i in range(len(pts)):
        a = pts[i]
        b = pts[(i + 1) % len(pts)]
        out.extend(bresenham_line(a[0], a[1], b[0], b[1]))
    return sorted(set(out))


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


_EDGE_CN = {"left": "左边界", "right": "右边界",
            "top": "上边界", "bottom": "下边界"}


def clip_polygon_steps(points: Sequence[Tuple[int, int]],
                       rect: Rect) -> List[Step]:
    """多边形裁剪步骤流：每裁完一条边界输出一步（窗口 + 当前多边形）。"""
    border = _rect_perimeter(rect)
    out = [(float(x), float(y)) for x, y in points]
    steps: List[Step] = []
    start = [(int(round(x)), int(round(y))) for x, y in out]
    steps.append(Step(sorted(set(border) | set(polygon_outline(start))),
                      {"阶段": "初始", "顶点数": len(start)},
                      f"待裁剪多边形：{len(start)} 个顶点"))
    for edge in ("left", "right", "top", "bottom"):
        if not out:
            steps.append(Step(border, {"阶段": _EDGE_CN[edge], "顶点数": 0},
                              f"{_EDGE_CN[edge]}：多边形已空"))
            break
        src = out
        out = []
        s = src[-1]
        added = 0
        for e in src:
            if _inside(e, edge, rect):
                if not _inside(s, edge, rect):
                    out.append(_intersect(s, e, edge, rect))
                    added += 1
                out.append(e)
            elif _inside(s, edge, rect):
                out.append(_intersect(s, e, edge, rect))
                added += 1
            s = e
        cur = [(int(round(x)), int(round(y))) for x, y in out]
        steps.append(Step(sorted(set(border) | set(polygon_outline(cur))),
                          {"阶段": _EDGE_CN[edge], "顶点数": len(cur),
                           "新增交点": added},
                          f"{_EDGE_CN[edge]}：保留 {len(cur)} 个顶点，"
                          f"新增 {added} 个交点"))
    return steps
