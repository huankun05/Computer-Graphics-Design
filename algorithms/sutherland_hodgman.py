# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/sutherland_hodgman.py — Sutherland-Hodgman 逐边裁剪
=====================================================================
用窗口的**每一条边**依次对多边形做"半平面裁剪"：

  对每条边界，遍历当前多边形顶点 S → E：
    · E 在内，S 在外 → 输出 S-E 与边界的交点、E
    · E、S 都在内     → 输出 E
    · E 在外，S 在内  → 输出交点
    · 都在外          → 不输出

四轮之后得到窗口内多边形（顶点顺序保持顶点的输入方向）。

★ 窗口可以是【矩形】也可以是【凸多边形】：
  逐边裁剪的本质是"把窗口表示成若干半平面的交"，所以窗口必须**凸**
  （凹窗口用半平面切会切出窗口外的部分）。凸多边形窗口有 N 条边，
  就裁 N 轮——动画里"一轮一条边"的叙事完全一致。
  凹窗口请用 Weiler-Atherton（algorithms/weiler_atherton.py，双边裁剪，
  任意简单多边形窗口都成立）。

双出口（规范契约①）：
  clip_polygon()               -> 裁剪后的顶点（浮点，精确交点）
  clip_polygon_steps()         -> 步骤流（逐边、逐顶点输出一步）
  clip_polygon_convex()        -> 凸多边形窗口的裁剪结果（浮点）
  clip_polygon_convex_steps()  -> 凸多边形窗口的步骤流
  clip_segment_convex()        -> 一条边被窗口切剩的那一段（浮点）
  clip_segment_convex_steps()  -> 一条边逐半平面切分的步骤流

★ 几何出口为什么是浮点：
  窗口是矩形时交点的 x 落在整数线上，但 y 是插值出来的小数（斜边 × 竖边）。
  早先在出口处 int(round()) 取整，交点被挪动最多半格——实测"三角形 ×
  三角形窗口"的交集面积少算 5.8 px²（2.4%），斜边交点看上去像算错一半。
  取整只该发生在【栅格化那一步】（polygon_outline），几何出口保持精确，
  才与应用侧的浮点几何掩膜同一口径。
=====================================================================
"""

from typing import Callable, List, Optional, Sequence, Tuple

from algorithms.line_bresenham import bresenham_line
from algorithms.steps import (GUIDE_HIT, GUIDE_MARK, GUIDE_MOVE, GUIDE_REF,
                              Step, arrow_guide, boundary_guide,
                              border_extension_segments, edge_guide,
                              line_guide, point_guide, polygon_guide,
                              rect_guide)

Rect = Tuple[int, int, int, int]
Point = Tuple[float, float]
Segment = Tuple[Point, Point]

_EDGES = ("left", "right", "top", "bottom")

_EDGE_CN = {"left": "左边界", "right": "右边界",
            "top": "上边界", "bottom": "下边界"}


# ---------------------------------------------------------------------
# 半平面抽象：窗口的每条边 = 一个"内侧判定 + 求交"的组合
# ---------------------------------------------------------------------
class _Plane:
    """窗口的一条边（一个半平面）。

    inside(p)   : 点是否在窗口这一侧的半平面内
    intersect(s, e): 线段 S→E 与这条边所在直线的交点
    """

    __slots__ = ("name", "inside", "intersect")

    def __init__(self, name: str, inside: Callable[[Point], bool],
                 intersect: Callable[[Point, Point], Point]):
        self.name = name
        self.inside = inside
        self.intersect = intersect


def _rect_planes(rect: Rect) -> List[_Plane]:
    """矩形窗口 → 4 个半平面（左 / 右 / 上 / 下）。"""
    rx0, ry0, rx1, ry1 = rect

    def mk(name, inside, intersect):
        return _Plane(name, inside, intersect)

    return [
        mk("left",
           lambda p: p[0] >= rx0,
           lambda s, e: (float(rx0),
                         s[1] + (e[1] - s[1]) * (rx0 - s[0]) / (e[0] - s[0])
                         if e[0] != s[0] else s[1])),
        mk("right",
           lambda p: p[0] <= rx1,
           lambda s, e: (float(rx1),
                         s[1] + (e[1] - s[1]) * (rx1 - s[0]) / (e[0] - s[0])
                         if e[0] != s[0] else s[1])),
        mk("top",
           lambda p: p[1] >= ry0,
           lambda s, e: (s[0] + (e[0] - s[0]) * (ry0 - s[1]) / (e[1] - s[1])
                         if e[1] != s[1] else s[0], float(ry0))),
        mk("bottom",
           lambda p: p[1] <= ry1,
           lambda s, e: (s[0] + (e[0] - s[0]) * (ry1 - s[1]) / (e[1] - s[1])
                         if e[1] != s[1] else s[0], float(ry1))),
    ]


def _signed_area(poly: Sequence[Point]) -> float:
    """有向面积（屏幕坐标 y 向下，正值 = 逆时针）。"""
    n = len(poly)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return s / 2.0


def is_convex(points: Sequence[Point]) -> bool:
    """多边形是否凸（顶点顺序任意；凹的返回 False）。"""
    n = len(points)
    if n < 3:
        return False
    sign = 0
    for i in range(n):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % n]
        x2, y2 = points[(i + 2) % n]
        cross = (x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1)
        if abs(cross) < 1e-9:
            continue
        s = 1 if cross > 0 else -1
        if sign == 0:
            sign = s
        elif s != sign:
            return False
    return True


def _convex_planes(window: Sequence[Point]) -> List[_Plane]:
    """凸多边形窗口 → N 个半平面（每条边一个）。

    先把顶点归一成"面积为正"的方向（屏幕坐标下即内部在叉积为正的一侧），
    再对每条边建立"内侧 = 叉积 ≥ 0"的判定。
    """
    pts = [(float(x), float(y)) for x, y in window]
    if _signed_area(pts) < 0:
        pts.reverse()
    n = len(pts)
    planes: List[_Plane] = []
    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]

        def make_inside(a=a, dx=dx, dy=dy):
            def inside(p):
                return (dx * (p[1] - a[1]) - dy * (p[0] - a[0])) >= -1e-9
            return inside

        def make_intersect(a=a, dx=dx, dy=dy):
            def intersect(s, e):
                ex, ey = e[0] - s[0], e[1] - s[1]
                denom = ex * dy - ey * dx
                if abs(denom) < 1e-12:
                    return s
                t = ((a[0] - s[0]) * dy - (a[1] - s[1]) * dx) / denom
                return (s[0] + t * ex, s[1] + t * ey)
            return intersect

        planes.append(_Plane(f"edge{i}", make_inside(), make_intersect()))
    return planes


# ---------------------------------------------------------------------
# 几何出口
# ---------------------------------------------------------------------
def _clip_geometry(points: Sequence[Point],
                   planes: Sequence[_Plane]) -> List[Point]:
    """逐半平面裁剪：返回裁剪后的顶点（浮点，精确交点）。

    ★ 为什么不再取整成整数：
      窗口是矩形时，交点落在 x = rx0 这类整数线上，但 **y 是插值出来的
      小数**（斜边与竖边相交）。早先在这里 int(round(x)) 取整，交点被
      整体挪动最多半格：实测"三角形 × 三角形窗口"的交集面积因此少算
      5.8 px²（2.4%），斜边上的交点看上去也"算错了一半"。
      像素层的取整只在【栅格化那一步】做（polygon_outline），
      几何出口必须保持精确，否则和应用侧（浮点几何掩膜）口径不一致。
    """
    out = [(float(x), float(y)) for x, y in points]
    for plane in planes:
        if not out:
            break
        src = out
        out = []
        s = src[-1]
        for e in src:
            s_in = plane.inside(s)
            e_in = plane.inside(e)
            if e_in:
                if not s_in:
                    out.append(plane.intersect(s, e))
                out.append(e)
            elif s_in:
                out.append(plane.intersect(s, e))
            s = e
    res: List[Point] = []
    for x, y in out:
        p = (float(x), float(y))
        if not res or not _same(res[-1], p):
            res.append(p)
    if len(res) > 1 and _same(res[0], res[-1]):
        res.pop()
    return res


def clip_polygon(points: Sequence[Point],
                 rect: Rect) -> List[Point]:
    """Sutherland-Hodgman：返回裁剪后的顶点（浮点，可能为空）。"""
    return _clip_geometry(points, _rect_planes(rect))


def clip_polygon_convex(points: Sequence[Point],
                         window: Sequence[Point]) -> List[Point]:
    """Sutherland-Hodgman（凸多边形窗口）：返回裁剪后的顶点（浮点）。"""
    if len(window) < 3:
        return []
    return _clip_geometry(points, _convex_planes(window))


def polygon_outline(points: Sequence[Point]) -> List[Tuple[int, int]]:
    """多边形闭合轮廓像素（逐边 Bresenham）。

    顶点允许带小数（几何出口就是精确交点）：栅格化这一步才取整，
    取整方式与几何出口的取整方式一致（四舍五入）。
    """
    pts = [(int(round(x)), int(round(y))) for x, y in points]
    out = []
    if len(pts) < 2:
        return list(pts)
    for i in range(len(pts)):
        a = pts[i]
        b = pts[(i + 1) % len(pts)]
        out.extend(bresenham_line(a[0], a[1], b[0], b[1]))
    return sorted(set(out))


# ---------------------------------------------------------------------
# 注记
# ---------------------------------------------------------------------
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


def _poly_edge_guides(window: Sequence[Point], idx: int, round_no: int):
    """凸多边形窗口：当前这条边整条加粗（橙）+ 轮次名字。"""
    n = len(window)
    a = window[idx]
    b = window[(idx + 1) % n]
    return [line_guide(a, b, GUIDE_MARK, dash=False, width=3.0),
            {"kind": "label", "xy": (int(a[0]), int(a[1])),
             "text": f"第 {round_no} 轮 · 窗口第 {idx + 1} 条边",
             "color": GUIDE_MARK, "align": "left", "valign": "above"}]


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


# ---------------------------------------------------------------------
# 步骤流出口
# ---------------------------------------------------------------------
def _clip_steps(points: Sequence[Point], planes: Sequence[_Plane],
                frame: List[dict], edge_guide_fn,
                final: List[Tuple[int, int]],
                edge_names: Sequence[str],
                title: str) -> List[Step]:
    """逐半平面、逐顶点输出一步的步骤流（矩形与凸多边形窗口共用）。

    每步 = 一次 S→E 判定（内→内 留 E / 内→外 留交点 /
    外→内 交点+E / 外→外 丢弃），画面上的多边形随之逐个顶点生长。
    约定（双出口一致）：Step.pixels 只放【当前部分结果多边形的轮廓】，
    窗口边框、当前边界线、S/E 与交点、输出顶点编号都在 guides；
    末步像素 = 几何出口结果（逐像素一致）。
    """
    out: List[Tuple[float, float]] = []
    for x, y in points:
        _push(out, (float(x), float(y)))    # 去掉输入里的重合顶点
    steps: List[Step] = []
    start = [(int(round(x)), int(round(y))) for x, y in out]
    steps.append(Step(sorted(set(polygon_outline(start))),
                      {"阶段": "初始", "输入顶点": len(start),
                       "输出顶点": len(start), "新增交点": 0,
                       "内→内": 0, "内→外": 0, "外→内": 0, "外→外": 0},
                      title,
                      guides=[*frame, *_vertex_guides(start)]))
    for k, plane in enumerate(planes, 1):
        edge = edge_names[k - 1]
        if not out:
            steps.append(Step([], {"阶段": edge_names[k - 1], "输入顶点": 0,
                                   "输出顶点": 0, "新增交点": 0, "情形": "—",
                                   "内→内": 0, "内→外": 0,
                                   "外→内": 0, "外→外": 0},
                              f"{edge_names[k - 1]}：多边形已空，停止",
                              guides=[*frame, *edge_guide_fn(k - 1, k)]))
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
            {"阶段": edge_names[k - 1], "输入顶点": len(src),
             "输出顶点": len(src), "新增交点": 0, "情形": "开始本轮",
             "轮次": k, "边界": edge_names[k - 1],
             "内→内": 0, "内→外": 0, "外→内": 0, "外→外": 0},
            f"第 {k} 轮：用窗口{edge_names[k - 1]}裁剪（输入 {len(src)} 个顶点，"
            "逐个 S→E 判定）",
            guides=[*frame, *edge_guide_fn(k - 1, k),
                    # 本轮输入的中间多边形：整条虚线闭合轮廓，
                    # 让"一轮一轮把多边形切小"的过程始终有形状可看
                    *([polygon_guide(cur0)] if len(cur0) >= 2 else []),
                    *_vertex_guides(cur0)]))
        s = src[-1]
        for e in src:
            s_in = plane.inside(s)
            e_in = plane.inside(e)
            case = ("内" if s_in else "外") + "→" + ("内" if e_in else "外")
            cases[case] += 1
            hit = None
            if e_in and not s_in:
                hit = plane.intersect(s, e)
                if _push(out, hit):
                    added += 1
                _push(out, e)
                act = "交点 + E"
            elif e_in:
                _push(out, e)
                act = "留 E"
            elif s_in:
                hit = plane.intersect(s, e)
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
                {"阶段": edge_names[k - 1], "输入顶点": len(src),
                 "输出顶点": len(cur), "新增交点": added, "情形": case,
                 "轮次": k, "边界": edge_names[k - 1],
                 "内→内": cases["内→内"], "内→外": cases["内→外"],
                 "外→内": cases["外→内"], "外→外": cases["外→外"]},
                f"{edge_names[k - 1]}：S{si} → E{ei}「{case}」→ {act}"
                f"（当前 {len(cur)} 个顶点）",
                guides=[*frame, *edge_guide_fn(k - 1, k),
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
    # 收尾步：末帧必须等于几何出口（双出口契约）
    steps.append(Step(sorted(set(polygon_outline(final))) if final else [],
                      {"阶段": "完成", "输入顶点": len(points),
                       "输出顶点": len(final), "新增交点": "—", "情形": "—",
                       "内→内": "—", "内→外": "—", "外→内": "—",
                       "外→外": "—"},
                      f"{len(planes)} 条边界裁完：输出 {len(final)} 个顶点",
                      guides=[*frame]))
    return steps


def clip_polygon_steps(points: Sequence[Tuple[int, int]],
                       rect: Rect) -> List[Step]:
    """多边形裁剪步骤流（矩形窗口）：逐条边界、**逐顶点**输出一步。"""
    planes = _rect_planes(rect)
    final = clip_polygon(points, rect)
    return _clip_steps(points, planes,
                       frame=[rect_guide(rect)],
                       edge_guide_fn=lambda i, k: _edge_guides(
                           _EDGES[i], rect, k),
                       final=final,
                       edge_names=[_EDGE_CN[e] for e in _EDGES],
                       title=f"待裁剪多边形：{len(points)} 个顶点")


def clip_polygon_convex_steps(points: Sequence[Tuple[int, int]],
                              window: Sequence[Point]) -> List[Step]:
    """多边形裁剪步骤流（**凸多边形**窗口）：逐条边、逐顶点输出一步。

    与矩形窗口的差别只有"边从哪来"：矩形的 4 条边固定，
    凸多边形的 N 条边按窗口顶点顺序来，轮数 = 边数。
    """
    if len(window) < 3:
        return []
    wpts = [(float(x), float(y)) for x, y in window]
    planes = _convex_planes(wpts)
    final = clip_polygon_convex(points, wpts)
    frame = [polygon_guide([(int(round(x)), int(round(y))) for x, y in wpts],
                           color="#17A2B8", dash=True, width=2.0)]
    return _clip_steps(points, planes,
                       frame=frame,
                       edge_guide_fn=lambda i, k: _poly_edge_guides(
                           wpts, i, k),
                       final=final,
                       edge_names=[f"第 {i + 1} 条边"
                                   for i in range(len(wpts))],
                       title=f"待裁剪多边形：{len(points)} 个顶点 × "
                             f"凸多边形窗口 {len(wpts)} 条边")


# ---------------------------------------------------------------------
# 逐段裁剪：沿被裁多边形的【每一条边】依次用窗口的半平面切
# ---------------------------------------------------------------------
def clip_segment_convex(p0: Point, p1: Point,
                        window: Sequence[Point]) -> List[Segment]:
    """一条边 × 凸多边形窗口 → 落在窗口内的那些片段。

    逐边裁剪的本质就是"把每条边依次用窗口的各半平面切一遍"：
    S-H 的输出多边形的每一条边，都是输入边被各半平面切剩的那一段。
    这里按【被裁多边形的边】逐条算，动画才能沿着图形的真实边界一段段走
    （和线段裁剪页同一套逐段判定的框架），而不是整块多边形一次性跳。
    凸窗口下结果至多一段；凹窗口不在本函数职责内（用 Weiler-Atherton）。
    """
    if len(window) < 3:
        return []
    a = (float(p0[0]), float(p0[1]))
    b = (float(p1[0]), float(p1[1]))
    for plane in _convex_planes(window):
        a_in = plane.inside(a)
        b_in = plane.inside(b)
        if a_in and b_in:
            continue
        if not a_in and not b_in:
            return []            # 整段在这一次半平面之外 → 整段出局
        hit = plane.intersect(a, b)
        if not a_in:
            a = hit
        else:
            b = hit
    return [(a, b)]


def _segment_guide_set(window: Sequence[Point], cur: Segment,
                       origin: Segment, hit: Optional[Point],
                       plane_idx: int, plane_name: str):
    """逐段裁剪的一帧注记：窗口 + 原边 + 当前边 + 交点 + 本次半平面。

    窗口用【红色 + 格角】画：画布上裁剪工具的窗口框也是红色格角，
    两者完全重合——早先这里画青色格心多边形，结果是"两重错开半格的
    窗口框"，看着像有两个窗口（用户反馈口径要统一）。
    """
    n = len(window)
    a = window[plane_idx]
    b = window[(plane_idx + 1) % n]
    guides = [
        polygon_guide(window, color="#E5484D", dash=True, width=1.8,
                      anchor="corner"),
        # 原始那条边（灰虚线）：看得出"这一段被切成了什么"
        line_guide(origin[0], origin[1], GUIDE_REF, dash=True, width=1.4),
        # 当前还在的那一段（紫实线）：算法每一步的结果
        line_guide(cur[0], cur[1], GUIDE_MOVE, dash=False, width=3.0),
        # 本次用的窗口边（橙）：哪个半平面在切
        line_guide(a, b, GUIDE_MARK, dash=False, width=2.6),
    ]
    if hit is not None:
        guides.append(point_guide(hit, "交点", GUIDE_HIT))
    return guides


def clip_segment_convex_steps(p0: Point, p1: Point,
                              window: Sequence[Point]) -> List[Step]:
    """一条边 × 凸多边形窗口：逐半平面切分的步骤流。

    每一步 = 一次半平面判定（窗口第 k 条边）：
      · 两端都在内侧 → 整段保留；
      · 一端在外     → 在交点处截断（画面上标出交点）；
      · 两端都在外   → 整段出局，后续半平面不必再看。
    末步给出生存下来的那段（= 落在窗口内 = 本模块要挖除的部分）。
    """
    if len(window) < 3:
        return []
    wpts = [(float(x), float(y)) for x, y in window]
    planes = _convex_planes(wpts)
    origin = ((float(p0[0]), float(p0[1])), (float(p1[0]), float(p1[1])))
    cur = origin
    steps: List[Step] = [Step(
        [], {"阶段": "初始", "半平面": "—", "情形": "—", "本段长度": "整段"},
        f"待判定边：({origin[0][0]:.1f}, {origin[0][1]:.1f}) → "
        f"({origin[1][0]:.1f}, {origin[1][1]:.1f})；"
        f"窗口 {len(wpts)} 条边，逐条半平面切下来",
        guides=[polygon_guide(wpts, color="#E5484D", dash=True, width=1.8,
                           anchor="corner"),
                line_guide(origin[0], origin[1], GUIDE_MOVE, dash=False,
                           width=3.0)])]
    for k, plane in enumerate(planes):
        a, b = cur
        a_in = plane.inside(a)
        b_in = plane.inside(b)
        case = ("内" if a_in else "外") + "→" + ("内" if b_in else "外")
        hit = None
        if a_in and b_in:
            act = "整段保留"
        elif not a_in and not b_in:
            act = "整段出局"
            cur = (a, b)          # 整段出局：后面几条半平面不必再看
        else:
            hit = plane.intersect(a, b)
            act = "在交点处截断"
            cur = (hit, b) if not a_in else (a, hit)
        steps.append(Step(
            [], {"阶段": f"第 {k + 1} 条边", "半平面": f"第 {k + 1} 条边",
                 "情形": case, "本段长度": act},
            f"窗口第 {k + 1} 条边切这一段：起点「"
            f"{'内' if a_in else '外'}」终点「{'内' if b_in else '外'}」→ {act}",
            guides=_segment_guide_set(wpts, cur, origin, hit, k,
                                      f"第 {k + 1} 条边")))
        if act == "整段出局":
            break
    inside = clip_segment_convex(origin[0], origin[1], wpts)
    if inside:
        a, b = inside[0]
        steps.append(Step(
            [], {"阶段": "判定完成", "半平面": "—", "情形": "—",
                 "本段长度": "落在窗口内"},
            f"这一段落在窗口内：({a[0]:.1f}, {a[1]:.1f}) → "
            f"({b[0]:.1f}, {b[1]:.1f})（要被挖除）",
            guides=[polygon_guide(wpts, color="#E5484D", dash=True, width=1.8,
                           anchor="corner"),
                    line_guide(a, b, GUIDE_MARK, dash=False, width=3.2)]))
    else:
        steps.append(Step(
            [], {"阶段": "判定完成", "半平面": "—", "情形": "—",
                 "本段长度": "整段在窗口外"},
            "这一段整段在窗口外，原样保留",
            guides=[polygon_guide(wpts, color="#E5484D", dash=True, width=1.8,
                           anchor="corner"),
                    line_guide(origin[0], origin[1], GUIDE_REF, dash=True,
                               width=1.8)]))
    return steps

