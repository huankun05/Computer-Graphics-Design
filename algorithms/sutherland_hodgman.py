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
from algorithms.steps import (GUIDE_HIT, Step, line_guide, point_guide,
                              rect_guide)

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


_EDGE_CN = {"left": "左边界", "right": "右边界",
            "top": "上边界", "bottom": "下边界"}


def _edge_guide(edge: str, rect: Rect):
    """当前被裁边界的高亮线（左/右为竖线，上/下为横线）。"""
    rx0, ry0, rx1, ry1 = rect
    if edge in ("left", "right"):
        x = rx0 if edge == "left" else rx1
        return line_guide((x, ry0), (x, ry1), "#F76B15", dash=False)
    y = ry0 if edge == "top" else ry1
    return line_guide((rx0, y), (rx1, y), "#F76B15", dash=False)


def _vertex_guides(pts: List[Tuple[int, int]]):
    """输出顶点序列的编号点注记（P0…Pn-1）。"""
    return [point_guide(p, f"P{i}", GUIDE_HIT) for i, p in enumerate(pts)]


def clip_polygon_steps(points: Sequence[Tuple[int, int]],
                       rect: Rect) -> List[Step]:
    """多边形裁剪步骤流：每裁完一条边界输出一步（窗口 + 当前多边形）。

    约定（双出口一致）：Step.pixels 只放【当前裁剪结果多边形的轮廓】，
    窗口边框与当前边界线、顶点编号、交点都放进 guides 注记。
    每步 values 给出四情形统计（内→内 / 内→外 / 外→内 / 外→外），
    把 S→E 逐顶点的判定过程写清楚。
    """
    frame = rect_guide(rect)
    out = [(float(x), float(y)) for x, y in points]
    steps: List[Step] = []
    start = [(int(round(x)), int(round(y))) for x, y in out]
    steps.append(Step(sorted(set(polygon_outline(start))),
                      {"阶段": "初始", "输入顶点": len(start),
                       "输出顶点": len(start), "新增交点": 0,
                       "内→内": 0, "内→外": 0, "外→内": 0, "外→外": 0},
                      f"待裁剪多边形：{len(start)} 个顶点",
                      guides=[frame, *_vertex_guides(start)]))
    for edge in ("left", "right", "top", "bottom"):
        if not out:
            steps.append(Step([], {"阶段": _EDGE_CN[edge], "输入顶点": 0,
                                   "输出顶点": 0, "新增交点": 0,
                                   "内→内": 0, "内→外": 0,
                                   "外→内": 0, "外→外": 0},
                              f"{_EDGE_CN[edge]}：多边形已空，停止",
                              guides=[frame, _edge_guide(edge, rect)]))
            break
        src = out
        out = []
        added = 0
        cases = {"内→内": 0, "内→外": 0, "外→内": 0, "外→外": 0}
        hits: List[Tuple[int, int]] = []
        for j, e in enumerate(src):
            s = src[j - 1]
            s_in = _inside(s, edge, rect)
            e_in = _inside(e, edge, rect)
            cases[("内" if s_in else "外") + "→" + ("内" if e_in else "外")] += 1
            if e_in:
                if not s_in:
                    p = _intersect(s, e, edge, rect)
                    out.append(p)
                    hits.append((int(round(p[0])), int(round(p[1]))))
                    added += 1
                out.append(e)
            elif s_in:
                p = _intersect(s, e, edge, rect)
                out.append(p)
                hits.append((int(round(p[0])), int(round(p[1]))))
                added += 1
        cur = [(int(round(x)), int(round(y))) for x, y in out]
        steps.append(Step(
            sorted(set(polygon_outline(cur))),
            {"阶段": _EDGE_CN[edge], "输入顶点": len(src),
             "输出顶点": len(cur), "新增交点": added,
             "内→内": cases["内→内"], "内→外": cases["内→外"],
             "外→内": cases["外→内"], "外→外": cases["外→外"]},
            f"{_EDGE_CN[edge]}：{len(src)} → {len(cur)} 顶点，"
            f"新增 {added} 个交点",
            guides=[frame, _edge_guide(edge, rect),
                    *_vertex_guides(cur),
                    *[point_guide(h, "交点", GUIDE_HIT) for h in hits]]))
    return steps
