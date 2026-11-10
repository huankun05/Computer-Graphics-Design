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
from algorithms.steps import (GUIDE_HIT, GUIDE_MARK, GUIDE_MOVE, GUIDE_REF,
                              Step, arrow_guide, boundary_guide,
                              border_extension_segments, edge_guide,
                              line_guide, point_guide, polygon_guide,
                              rect_guide)

Rect = Tuple[int, int, int, int]
Point = Tuple[float, float]

_EDGES = ("left", "right", "top", "bottom")


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


def _edge_guides(edge: str, rect: Rect, round_no: int = 0):
    """当前被裁边界的高亮：整条边在红框外侧加粗（带"第 k 轮"名字）+
    窗口外两截延长段。

    用户反馈"逐边裁剪的过程看不出来"：只画窗口外 4px 的延长段几乎看不见。
    整条压在红框上又会染色。这里用 edge_guide（红框外侧 2.5px 加粗）
    标出本轮用的边，红框本身始终完整。
    """
    guides = []
    if round_no:
        guides.append(edge_guide(rect, edge,
                                 label=f"第 {round_no} 轮 · {_EDGE_CN[edge]}"))
    guides.extend(boundary_guide(a, b, "#F76B15", dash=False)
                  for name, a, b in border_extension_segments(rect, ext=4)
                  if name == edge)
    return guides


def _vertex_guides(pts: List[Tuple[int, int]]):
    """输出顶点序列的编号点注记（P0…Pn-1）。

    顶点多了标签会糊成一团（圆被离散成上百点），只标前 12 个，
    其余顶点仍画点、不标号。
    """
    return [point_guide(p, f"P{i}" if i < 12 else "", GUIDE_HIT)
            for i, p in enumerate(pts)]


def _same(a, b) -> bool:
    return (int(round(a[0])), int(round(a[1]))) == \
           (int(round(b[0])), int(round(b[1])))


def _push(pts, p) -> bool:
    """追加顶点，跳过与上一个顶点重合的点。

    交点恰好落在端点（或离散化后两点重合）时会追加重复顶点，
    演示里表现为"零长度边 + 重复顶点 + 退化箭头"，看起来像卡住不动。
    只去掉重合点，几何结果不变。
    """
    if pts and _same(pts[-1], p):
        return False
    pts.append(p)
    return True


def clip_polygon_steps(points: Sequence[Tuple[int, int]],
                       rect: Rect) -> List[Step]:
    """多边形裁剪步骤流：逐条边界、**逐顶点**输出一步。

    每步 = 一次 S→E 判定（内→内 留 E / 内→外 留交点 /
    外→内 交点+E / 外→外 丢弃），画面上的多边形随之逐个顶点生长。
    约定（双出口一致）：Step.pixels 只放【当前部分结果多边形的轮廓】，
    窗口边框、当前边界线、S/E 与交点、输出顶点编号都在 guides；
    末步像素 = clip_polygon() 结果（逐像素一致）。
    """
    frame = rect_guide(rect)
    out: List[Tuple[float, float]] = []
    for x, y in points:
        _push(out, (float(x), float(y)))    # 去掉输入里的重合顶点
    steps: List[Step] = []
    start = [(int(round(x)), int(round(y))) for x, y in out]
    steps.append(Step(sorted(set(polygon_outline(start))),
                      {"阶段": "初始", "输入顶点": len(start),
                       "输出顶点": len(start), "新增交点": 0,
                       "内→内": 0, "内→外": 0, "外→内": 0, "外→外": 0},
                      f"待裁剪多边形：{len(start)} 个顶点",
                      guides=[frame, *_vertex_guides(start)]))
    for k, edge in enumerate(_EDGES, 1):
        if not out:
            steps.append(Step([], {"阶段": _EDGE_CN[edge], "输入顶点": 0,
                                   "输出顶点": 0, "新增交点": 0, "情形": "—",
                                   "内→内": 0, "内→外": 0,
                                   "外→内": 0, "外→外": 0},
                              f"{_EDGE_CN[edge]}：多边形已空，停止",
                              guides=[frame, *_edge_guides(edge, rect, k)]))
            break
        src = out
        out = []
        added = 0
        cases = {"内→内": 0, "内→外": 0, "外→内": 0, "外→外": 0}
        # 本轮开头的"阶段说明帧"：先把上一轮的中间多边形整体显示出来，
        # 标出这一轮要用的窗口边——逐边裁剪的"一轮一轮"才看得出来
        cur0 = [(int(round(x)), int(round(y))) for x, y in src]
        steps.append(Step(
            sorted(set(polygon_outline(cur0))),
            {"阶段": _EDGE_CN[edge], "输入顶点": len(src),
             "输出顶点": len(src), "新增交点": 0, "情形": "开始本轮",
             "轮次": k, "边界": _EDGE_CN[edge],
             "内→内": 0, "内→外": 0, "外→内": 0, "外→外": 0},
            f"第 {k} 轮：用窗口{_EDGE_CN[edge]}裁剪（输入 {len(src)} 个顶点，"
            "逐个 S→E 判定）",
            guides=[frame, *_edge_guides(edge, rect, k),
                    # 本轮输入的中间多边形：整条虚线闭合轮廓，
                    # 让"一轮一轮把多边形切小"的过程始终有形状可看
                    *([polygon_guide(cur0)] if len(cur0) >= 2 else []),
                    *_vertex_guides(cur0)]))
        s = src[-1]
        for e in src:
            s_in = _inside(s, edge, rect)
            e_in = _inside(e, edge, rect)
            case = ("内" if s_in else "外") + "→" + ("内" if e_in else "外")
            cases[case] += 1
            hit = None
            if e_in and not s_in:
                hit = _intersect(s, e, edge, rect)
                if _push(out, hit):
                    added += 1
                _push(out, e)
                act = "交点 + E"
            elif e_in:
                _push(out, e)
                act = "留 E"
            elif s_in:
                hit = _intersect(s, e, edge, rect)
                if _push(out, hit):
                    added += 1
                act = "留交点"
            else:
                act = "丢弃"
            if len(out) > 1 and _same(out[0], out[-1]):
                out.pop()            # 闭合多边形首尾重合 → 去掉尾部重复点
            cur = [(int(round(x)), int(round(y))) for x, y in out]
            si = (int(round(s[0])), int(round(s[1])))
            ei = (int(round(e[0])), int(round(e[1])))
            hit_i = ((int(round(hit[0])), int(round(hit[1]))) if hit else None)
            steps.append(Step(
                polygon_outline(cur) if len(cur) >= 2 else [],
                {"阶段": _EDGE_CN[edge], "输入顶点": len(src),
                 "输出顶点": len(cur), "新增交点": added, "情形": case,
                 "轮次": k, "边界": _EDGE_CN[edge],
                 "内→内": cases["内→内"], "内→外": cases["内→外"],
                 "外→内": cases["外→内"], "外→外": cases["外→外"]},
                f"{_EDGE_CN[edge]}：S{si} → E{ei}「{case}」→ {act}"
                f"（当前 {len(cur)} 个顶点）",
                guides=[frame, *_edge_guides(edge, rect, k),
                        # 当前部分结果多边形：逐顶点生长/收缩的闭合轮廓
                        *([polygon_guide(cur)] if len(cur) >= 2 else []),
                        # 正在处理的那条多边形边：加粗实线 + S→E 箭头，
                        # 明确"沿着图形的哪条边在裁"（用户反馈）
                        line_guide(si, ei, GUIDE_MOVE, dash=False, width=3.5),
                        arrow_guide(si, ei, GUIDE_MOVE),
                        point_guide(si, "S", GUIDE_REF),
                        point_guide(ei, "E", GUIDE_MARK),
                        *([point_guide(hit_i, "交点", GUIDE_HIT)]
                          if hit_i else []),
                        *_vertex_guides(cur)]))
            s = e
    # 收尾步：末帧必须等于几何出口 clip_polygon()（双出口契约）
    final = clip_polygon(points, rect)
    steps.append(Step(sorted(set(polygon_outline(final))) if final else [],
                      {"阶段": "完成", "输入顶点": len(points),
                       "输出顶点": len(final), "新增交点": "—", "情形": "—",
                       "内→内": "—", "内→外": "—", "外→内": "—",
                       "外→外": "—"},
                      f"四条边界裁完：输出 {len(final)} 个顶点",
                      guides=[frame]))
    return steps
