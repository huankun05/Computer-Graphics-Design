# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/weiler_atherton.py — Weiler-Atherton 双边裁剪（多边形 × 多边形）
=====================================================================
与 Sutherland-Hodgman 的区别（课程里的"逐边裁剪" vs "双边裁剪"）：

  · S-H（逐边裁剪）：把裁剪窗口的每条边当成一个半平面，**一条一条**
    把被裁多边形切开。窗口必须是**凸**的——只有凸窗口才能表示成
    "若干半平面的交"，凹窗口用半平面切会切出窗口外的部分。
  · W-A（双边裁剪）：一次求出被裁多边形与窗口的**全部交点**，按
    【进入 / 离开】成对配对，然后沿"被裁多边形的边"与"窗口的边"
    交替前进，一次得到交集多边形。窗口可以是**任意简单多边形**
    （凸或凹都成立），这是它相对 S-H 的关键优势。

算法（输出区 = 两个多边形的交集）：

  1. 求交：被裁多边形 P 的每条边与窗口 W 的每条边求交点；
  2. 定向：P、W 统一成逆时针（屏幕坐标 y 向下）。两个逆时针多边形的
     交集边界 = ∂P 落在 W 内的部分（沿 P 方向）+ ∂W 落在 P 内的部分
     （沿 W 方向）——每一段都保持各自多边形的走向；
  3. 拼环：输出边界上每个顶点恰好"一进一出"，把段首尾相接即可闭合；
  4. 进入/离开：交点处若被裁边的走向是"由外进入窗口内"，该交点就是
     **进入点**；反之为**离开点**。进入点与离开点成对出现，这正是
     "双边"二字的由来。

双出口（规范契约①）：
  clip_polygon()          -> 交集多边形顶点（浮点）
  clip_polygon_steps()    -> 步骤流（每步 = 一条被裁边的求交 / 一段输出边界）

逐段出口（演示页沿图形真实边界一段段走时用）：
  clip_segment()          -> 一条边落在窗口内的片段
  clip_segment_steps()    -> 一条边的求交 / 进入-离开步骤流
  clip_window_segments()  -> 窗口的边落在被裁多边形内的片段（"另一半"）

★ 几何出口为什么是浮点：交点是精确解（斜边 × 斜边会得到小数坐标）。
  出口处取整会把交点挪动最多半格——实测交集面积少算 2.4%，
  也与应用侧的浮点几何掩膜对不上。取整只该发生在栅格化那一步。

正确性判据（守卫用）：交集多边形栅格化后的像素集合，必须等于
"被裁多边形像素 ∩ 窗口掩膜像素"——这是与像素口径的独立交叉验证。
=====================================================================
"""

import math
from typing import List, Optional, Sequence, Tuple

from algorithms.steps import (GUIDE_HIT, GUIDE_MARK, GUIDE_MOVE, GUIDE_REF,
                              Step, line_guide, point_guide, polygon_guide)

Point = Tuple[float, float]
Segment = Tuple[Point, Point]

_EPS = 1e-9


# ---------------------------------------------------------------------
# 基础几何
# ---------------------------------------------------------------------
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


def _to_ccw(poly: Sequence[Point]) -> List[Point]:
    """归一为逆时针（面积为负则整体反向）。"""
    pts = [(float(x), float(y)) for x, y in poly]
    if _signed_area(pts) < 0:
        pts.reverse()
    return pts


def _point_in(poly: Sequence[Point], p: Point) -> bool:
    """射线法判断点是否在多边形内（边界算内）。"""
    n = len(poly)
    if n < 3:
        return False
    x, y = p
    inside = False
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        cross = (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)
        if abs(cross) < _EPS and min(x0, x1) - _EPS <= x <= max(x0, x1) + _EPS \
                and min(y0, y1) - _EPS <= y <= max(y0, y1) + _EPS:
            return True
        if (y0 > y) != (y1 > y):
            xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xi:
                inside = not inside
    return inside


def _seg_intersect(a: Point, b: Point,
                   c: Point, d: Point) -> Optional[Tuple[float, Point]]:
    """线段 AB 与 CD 求交：返回 (t, 交点)，t 是交点在 AB 上的参数。

    不相交返回 None。共线重叠按"不处理"（退化情形交给调用方跳过）。
    """
    rx, ry = b[0] - a[0], b[1] - a[1]
    sx, sy = d[0] - c[0], d[1] - c[1]
    denom = rx * sy - ry * sx
    if abs(denom) < _EPS:
        return None
    qx, qy = c[0] - a[0], c[1] - a[1]
    t = (qx * sy - qy * sx) / denom
    u = (qx * ry - qy * rx) / denom
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return t, (a[0] + t * rx, a[1] + t * ry)
    return None


def _dedup(pts: List[Point]) -> List[Point]:
    """去掉相邻重复点（交点可能与端点重合）。"""
    out: List[Point] = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) > 1e-6 or abs(p[1] - out[-1][1]) > 1e-6:
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < 1e-6 \
            and abs(out[0][1] - out[-1][1]) < 1e-6:
        out.pop()
    return out


def _key(p: Point) -> Tuple[int, int]:
    """顶点配对用的量化键（1e-4 精度足够：输入顶点都是整数）。"""
    return (int(round(p[0] * 10000)), int(round(p[1] * 10000)))


# ---------------------------------------------------------------------
# 核心：求交 + 输出边界段
# ---------------------------------------------------------------------
class _EdgeInfo:
    """一条被裁边（或窗口边）的求交结果。"""

    __slots__ = ("owner", "idx", "a", "b", "cuts", "segs")

    def __init__(self, owner: str, idx: int, a: Point, b: Point):
        self.owner = owner        # "P" = 被裁多边形, "W" = 窗口
        self.idx = idx            # 边序号
        self.a = a
        self.b = b
        self.cuts: List[Tuple[float, Point]] = []   # (参数 t, 交点)
        self.segs: List[Tuple[Point, Point, bool]] = []  # (起点, 终点, 在内部)


def _split_edge(info: _EdgeInfo, other: Sequence[Point],
                cut_list: List[Tuple[float, Point, str, int]]) -> None:
    """把一条边按与对方多边形的交点切开，标记各段是否在对方内部。

    cut_list 收集 (t, 交点, 进入/离开, 对方边号) 供步骤流使用。
    """
    n = len(other)
    for j in range(n):
        c = other[j]
        d = other[(j + 1) % n]
        hit = _seg_intersect(info.a, info.b, c, d)
        if hit is None:
            continue
        t, pt = hit
        # 同一条边可能与对方多条边交于一点（顶点重合）→ 去重
        if any(abs(t - tt) < 1e-9 for tt, _ in info.cuts):
            continue
        info.cuts.append((t, pt))
        cut_list.append((t, pt, "", j))
    info.cuts.sort(key=lambda kv: kv[0])
    # 逐段判断是否在对方内部（取段中点）
    pts = [info.a] + [pt for _t, pt in info.cuts] + [info.b]
    for k in range(len(pts) - 1):
        p0, p1 = pts[k], pts[k + 1]
        mid = ((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0)
        inside = _point_in(other, mid)
        info.segs.append((p0, p1, inside))


def _classify_entering(info: _EdgeInfo) -> None:
    """给交点标【进入 / 离开】：沿边前进后是否进入对方内部。"""
    for k, (t, pt) in enumerate(info.cuts):
        # 该交点之后的段是否在内部 → 进入点；否则离开点
        nxt_inside = info.segs[k + 1][2] if k + 1 < len(info.segs) else False
        info.cuts[k] = (t, pt, "进入" if nxt_inside else "离开")


def _chain(segments: List[Segment]) -> List[List[Point]]:
    """把输出边界段首尾相接成闭合环。

    输出区边界上每个顶点恰好"一进一出"，所以配对唯一；退化情况
    （多个候选）取"转向最靠右"的一条，保证环不自交。
    """
    if not segments:
        return []
    starts: dict = {}
    for a, b in segments:
        starts.setdefault(_key(a), []).append((a, b))
    used = set()
    loops: List[List[Point]] = []
    for si, (a0, b0) in enumerate(segments):
        if si in used:
            continue
        loop = [a0]
        cur_a, cur_b = a0, b0
        used.add(si)
        guard = 0
        while guard < len(segments) * 4 + 8:
            guard += 1
            loop.append(cur_b)
            if _key(cur_b) == _key(a0):
                break
            cands = [(i, s) for i, s in enumerate(segments)
                     if i not in used and _key(s[0]) == _key(cur_b)]
            if not cands:
                break
            # 多个候选时取"转向最靠右"（相对当前前进方向），避免自交
            best = cands[0]
            if len(cands) > 1:
                dx = cur_b[0] - cur_a[0]
                dy = cur_b[1] - cur_a[1]
                best = None
                best_score = None
                for i, s in cands:
                    ex = s[1][0] - s[0][0]
                    ey = s[1][1] - s[0][1]
                    # 叉积：负 = 右转（最靠右）
                    score = dx * ey - dy * ex
                    if best_score is None or score < best_score - 1e-9:
                        best_score = score
                        best = (i, s)
            used.add(best[0])
            cur_a, cur_b = best[1]
        if len(loop) >= 3:
            loops.append(loop[:-1] if _key(loop[0]) == _key(loop[-1]) else loop)
    return loops


def _compute(points: Sequence[Point], window: Sequence[Point]):
    """核心计算：返回 (P 的边信息, W 的边信息, 输出段列表)。

    输出段 = P 落在 W 内的段（沿 P 方向）+ W 落在 P 内的段（沿 W 方向）。
    """
    P = _to_ccw(points)
    W = _to_ccw(window)
    p_edges = [_EdgeInfo("P", i, P[i], P[(i + 1) % len(P)]) for i in range(len(P))]
    w_edges = [_EdgeInfo("W", j, W[j], W[(j + 1) % len(W)]) for j in range(len(W))]

    p_cuts: List[Tuple[float, Point, str, int]] = []
    w_cuts: List[Tuple[float, Point, str, int]] = []
    for e in p_edges:
        _split_edge(e, W, p_cuts)
        _classify_entering(e)
    for e in w_edges:
        _split_edge(e, P, w_cuts)
        _classify_entering(e)

    segs: List[Segment] = []
    for e in p_edges:
        for (a, b, inside) in e.segs:
            if inside:
                segs.append((a, b))
    for e in w_edges:
        for (a, b, inside) in e.segs:
            if inside:
                segs.append((a, b))
    return P, W, p_edges, w_edges, segs


def clip_polygon(points: Sequence[Point],
                 window: Sequence[Point]) -> List[Point]:
    """Weiler-Atherton 双边裁剪：返回交集多边形顶点（浮点，可能为空）。

    顶点保持浮点（精确交点）：取整只该发生在栅格化那一步。
    早先在出口取整，交点被挪动最多半格——"三角形 × 三角形窗口"的
    交集面积因此少算 5.8 px²（2.4%），与应用侧的浮点几何掩膜也对不上。
    """
    if len(points) < 3 or len(window) < 3:
        return []
    P, W, _pe, _we, segs = _compute(points, window)
    loops = _chain(segs)
    if not loops:
        return []
    # 交集可能有多个环（理论上简单多边形只有一个），取面积最大的
    def _area(loop):
        return abs(_signed_area(loop))
    loop = max(loops, key=_area)
    res: List[Point] = []
    for x, y in _dedup(loop):
        p = (float(x), float(y))
        if not res or abs(res[-1][0] - p[0]) > 1e-9 or abs(res[-1][1] - p[1]) > 1e-9:
            res.append(p)
    if len(res) > 1 and abs(res[0][0] - res[-1][0]) < 1e-9 \
            and abs(res[0][1] - res[-1][1]) < 1e-9:
        res.pop()
    return res


# ---------------------------------------------------------------------
# 逐段裁剪：沿被裁多边形的【每一条边】与窗口求交（进入 / 离开）
# ---------------------------------------------------------------------
def clip_segment(p0: Point, p1: Point,
                 window: Sequence[Point]) -> List[Segment]:
    """一条边 × 任意简单多边形窗口 → 落在窗口内的那些片段。

    一条边与窗口边界求交后，边的内部状态在每个交点处翻转（进入 / 离开），
    于是这条边被切成若干段，其中"在窗口内"的段就是交集边界的一部分。
    窗口可以是凹的——这是双边裁剪相对逐边裁剪（S-H）的关键优势。
    """
    if len(window) < 3:
        return []
    W = _to_ccw(window)
    info = _EdgeInfo("P", 0, (float(p0[0]), float(p0[1])),
                      (float(p1[0]), float(p1[1])))
    _split_edge(info, W, [])
    return [(a, b) for (a, b, inside) in info.segs if inside]


def clip_segment_steps(p0: Point, p1: Point,
                       window: Sequence[Point]) -> List[Step]:
    """一条边 × 任意简单多边形窗口：求交 + 进入/离开的步骤流。

    每一步 = 一个交点：标出它是【进入】（由外进入窗口内）还是
    【离开】（由窗口内离开），并把已经在窗口内的片段用橙色标出来。
    末步给出这条边落在窗口内的全部片段（= 要被挖除的部分）。
    """
    if len(window) < 3:
        return []
    W = _to_ccw(window)
    a = (float(p0[0]), float(p0[1]))
    b = (float(p1[0]), float(p1[1]))
    info = _EdgeInfo("P", 0, a, b)
    _split_edge(info, W, [])
    _classify_entering(info)
    wg = _window_guide(W)
    steps: List[Step] = [Step(
        [], {"阶段": "初始", "进入点": 0, "离开点": 0, "本段": "整段"},
        f"待判定边：({a[0]:.1f}, {a[1]:.1f}) → ({b[0]:.1f}, {b[1]:.1f})；"
        f"与窗口 {len(W)} 条边求交",
        guides=[wg, line_guide(a, b, GUIDE_MOVE, dash=False, width=3.0)])]
    ent = 0
    leave = 0
    for k, (t, pt, kind) in enumerate(info.cuts):
        if kind == "进入":
            ent += 1
            color = "#17A2B8"
        else:
            leave += 1
            color = GUIDE_MARK
        # 交点之后已经在窗口内的片段
        inside_piece = None
        for (p0_, p1_, ins) in info.segs[k + 1:]:
            if ins:
                inside_piece = (p0_, p1_)
                break
        guides = [wg, line_guide(a, b, GUIDE_MOVE, dash=False, width=2.4),
                  point_guide(pt, kind, color)]
        if inside_piece:
            guides.append(line_guide(inside_piece[0], inside_piece[1],
                                     GUIDE_MARK, dash=False, width=3.0))
        steps.append(Step(
            [], {"阶段": "求交", "进入点": ent, "离开点": leave,
                 "本段": kind},
            f"交点 ({pt[0]:.1f}, {pt[1]:.1f})：{kind}"
            + ("（从窗口外进入窗口内）" if kind == "进入"
               else "（从窗口内离开窗口外）"),
            guides=guides))
    pieces = [(p0_, p1_) for (p0_, p1_, ins) in info.segs if ins]
    if pieces:
        steps.append(Step(
            [], {"阶段": "判定完成", "进入点": ent, "离开点": leave,
                 "本段": f"{len(pieces)} 段在窗口内"},
            "这一段落在窗口内 " + f"{len(pieces)}  段（要被挖除）",
            guides=[wg] + [line_guide(p0_, p1_, GUIDE_MARK, dash=False,
                                      width=3.2) for p0_, p1_ in pieces]))
    else:
        steps.append(Step(
            [], {"阶段": "判定完成", "进入点": ent, "离开点": leave,
                 "本段": "整段在窗口外"},
            "这一段整段在窗口外，原样保留",
            guides=[wg, line_guide(a, b, GUIDE_REF, dash=True, width=1.8)]))
    return steps


def clip_window_segments(points: Sequence[Point],
                         window: Sequence[Point]) -> List[Segment]:
    """窗口的边落在被裁多边形内的那些片段（"双边"的另一半）。

    交集边界由两类段交替组成：被裁多边形的边（落在窗口内的部分）
    + 窗口的边（落在被裁多边形内的部分）。前者由 clip_segment 逐条给出，
    后者就是本函数——它解释了为什么叫"双边"裁剪。
    """
    if len(points) < 3 or len(window) < 3:
        return []
    P = _to_ccw(points)
    W = _to_ccw(window)
    out: List[Segment] = []
    for j in range(len(W)):
        info = _EdgeInfo("W", j, W[j], W[(j + 1) % len(W)])
        _split_edge(info, P, [])
        out.extend((a, b) for (a, b, inside) in info.segs if inside)
    return out


# ---------------------------------------------------------------------
# 双边交替路径：沿【图形边】↔【窗口边】交替前进
# ---------------------------------------------------------------------
def _closed(seq: Sequence[Point]) -> List[Point]:
    """点列 → 闭合点列（末点补回首点）。

    闭合是必须的：多边形的【收尾那一条边】（末顶点 → 首顶点）同样会与
    对方边界求交，漏掉它就会少求出一半交点——交集边界缺了"窗口边"那一
    半，双边交替就退化成只沿图形边走（实测：窗口左边界上的两个交点
    整个丢失，W 段一条都没生成）。
    """
    pts = [(float(x), float(y)) for x, y in seq]
    if len(pts) < 2:
        return pts
    if abs(pts[0][0] - pts[-1][0]) < 1e-9 and abs(pts[0][1] - pts[-1][1]) < 1e-9:
        return pts
    return pts + [pts[0]]


def _poly_crossings(seq: Sequence[Point],
                    other: Sequence[Point]) -> List[Tuple[int, float, Point]]:
    """闭合点列 seq 与闭合多边形 other 的交点。

    返回 [(段号, 段内参数, 交点)]，按 (段号, 参数) 升序 —— 也就是沿
    seq 方向的先后次序。段内参数必须参与排序：同一段上可能有两个交点
    （例如窗口的左边框同时穿过图形的上下两条边），只按段号排会得到
    相反的先后次序，双边交替就会走反方向。
    """
    out: List[Tuple[int, float, Point]] = []
    for i in range(len(seq) - 1):
        a, b = seq[i], seq[i + 1]
        for j in range(len(other) - 1):
            c, d = other[j], other[j + 1]
            hit = _seg_intersect(a, b, c, d)
            if hit is None:
                continue
            t, pt = hit
            if any(abs(pt[0] - q[2][0]) < 1e-7 and
                   abs(pt[1] - q[2][1]) < 1e-7 for q in out):
                continue                      # 顶点处会算两遍，去重
            out.append((i, t, pt))
    out.sort(key=lambda v: (v[0], v[1]))
    return out


def _path_mid(pts: Sequence[Point]) -> Point:
    """折线路径的弧长中点（按顺序走过 pts 的各段）。"""
    if not pts:
        return (0.0, 0.0)
    total = 0.0
    for a, b in zip(pts, pts[1:]):
        total += math.hypot(b[0] - a[0], b[1] - a[1])
    if total <= 0:
        return pts[0]
    half = total / 2.0
    acc = 0.0
    for a, b in zip(pts, pts[1:]):
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        if acc + d >= half:
            t = (half - acc) / d if d > 0 else 0.0
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        acc += d
    return pts[-1]


def _classify(seq: Sequence[Point], other: Sequence[Point],
              crossings: Sequence[Tuple[int, float, Point]]) -> List[str]:
    """给交点分类：【进入】= 沿 seq 前进后进入 other 内部，否则【离开】。

    判据取"从该交点沿 seq 走到下一个交点"这条**路径**的中点是否在
    other 内。必须按路径取中点，不能取两个交点的直线中点——闭合边界
    上两个交点之间可能绕了大半圈（窗口边的"离开图形"那一段绕到窗口
    另一侧），直线中点会落在路径之外，分类就反了。
    """
    kinds: List[str] = []
    n = len(crossings)
    for idx, (i, _t, pt) in enumerate(crossings):
        ni, _nt, npt = crossings[(idx + 1) % n]
        # 最后一个交点的"下一个"是绕回序列开头的那个 → 路径要绕大半圈
        mid = _path_mid(_slice_path(seq, i, pt, ni, npt, wrap=(idx + 1 == n)))
        kinds.append("进入" if _point_in(other[:-1], mid) else "离开")
    return kinds


def _slice_path(seq: Sequence[Point], i0: int, pt0: Point,
                i1: int, pt1: Point, wrap: bool = False) -> List[Point]:
    """闭合点列上从 (i0,pt0) 走到 (i1,pt1) 的点列（含两端）。

    走法：pt0 → seq[i0+1] → … → seq[i1] → pt1（段号可绕回序列开头）。
    点列保持原样，所以图形边的这段轨迹就是**原轮廓的像素**本身，
    判定轨迹与原图逐像素重合（用户反馈："画出来的轨迹和原来的轨迹
    不一样，像是两种画法"）。

    wrap=True 表示"绕回序列开头"（走到的是同一段上的另一个交点，
    但路径是绕了大半圈才到）——这时不能按同段短路处理。
    """
    n = len(seq) - 1
    if i0 == i1 and not wrap:
        # 两个交点在同一段上（且不是绕圈）：路径就是这一段里的一小截
        # 直线，不能绕整圈（那会把窗口边界整个画一遍，轨迹全错）。
        return [pt0, pt1]
    pts: List[Point] = [pt0]
    i = i0
    for _ in range(n + 2):
        i = (i + 1) % n
        pts.append(seq[i])
        if i == i1:
            break
    pts.append(pt1)
    return pts


def _next_node(nodes: Sequence[Tuple[int, Point, str]], k: int,
               kind: str) -> Optional[int]:
    """从第 k 个节点出发，沿序列方向找下一个 kind 节点的下标。

    只有第 k 个节点自己属于 kind 时返回 None（没有"下一个"）——
    否则会把 k 本身当成下一个，走成自环。
    """
    n = len(nodes)
    for step in range(1, n):
        idx = (k + step) % n
        if nodes[idx][2] == kind:
            return idx
    return None


def _find_node(nodes: Sequence[Tuple[int, Point, str]], pt: Point,
               tol: float = 1e-6) -> Optional[int]:
    """按坐标找节点（同一个几何交点在两条边界上是同一个点）。"""
    for k, (_i, p, _kind) in enumerate(nodes):
        if abs(p[0] - pt[0]) <= tol and abs(p[1] - pt[1]) <= tol:
            return k
    return None


def wa_outline_path(edges_pts: Sequence[Sequence[Point]],
                    window: Sequence[Point]) -> List[dict]:
    """Weiler-Atherton 交集边界：沿【图形边】↔【窗口边】交替前进。

    这才是"双边"的完整含义：交集边界由两类段**交替**组成——
      · P 段：图形边落在窗口内的部分（沿图形方向）→ 这条边的像素要被挖除；
      · W 段：窗口边落在图形内的部分（沿窗口方向）→ 交集边界的另一半。

    edges_pts: 图形轮廓按"边"分组的有序点列（每组一条边的像素），
               相邻点连线就是该边 ⇒ 判定轨迹与原轮廓逐像素重合。
    window:    裁剪窗口多边形顶点（任意简单多边形）。

    返回交替段序列，每项：
      {"kind": "P"/"W", "pts": [...], "enter": pt, "leave": pt, "edge": i}
    无交点（图形整体在窗口内或整体在外）时返回空列表。
    """
    if not edges_pts or len(window) < 3:
        return []
    W = _to_ccw(window)
    # 图形侧：把各边的像素拼成一条闭合折线（首尾相接）
    # 相邻两段首尾相接（上一段的末点 = 下一段的首点），拼接时每段
    # 去掉【首点】保留【末点】——若去掉末点，最后一段的末点会整段丢失
    # （圆的极左点正好落在那里，画面上会剩一个孤立的蓝点）。
    S: List[Point] = []
    edge_of: List[int] = []
    for ei, pts in enumerate(edges_pts):
        if len(pts) < 2:
            continue
        start = 0 if not S else 1
        for q in pts[start:]:
            S.append((float(q[0]), float(q[1])))
            edge_of.append(ei)
    if len(S) < 3:
        return []
    S = _closed(S)
    Wc = _closed(W)

    p_cross = _poly_crossings(S, Wc)
    w_cross = _poly_crossings(Wc, S)
    if not p_cross or not w_cross:
        return []

    p_kinds = _classify(S, Wc, p_cross)
    w_kinds = _classify(Wc, S, w_cross)
    p_nodes = [(i, pt, k) for (i, _t, pt), k in zip(p_cross, p_kinds)]
    w_nodes = [(i, pt, k) for (i, _t, pt), k in zip(w_cross, w_kinds)]

    out: List[dict] = []
    used = set()
    for start in range(len(p_nodes)):
        if p_nodes[start][2] != "进入" or start in used:
            continue
        start_pt = p_nodes[start][1]
        k = start
        guard = 0
        while guard < len(p_nodes) * 2 + 8:
            guard += 1
            used.add(k)
            # ---- P 段：从进入点沿图形边走到下一个离开点 ----
            k_leave = _next_node(p_nodes, k, "离开")
            if k_leave is None:
                break
            i_leave, pt_leave, _ = p_nodes[k_leave]
            i_enter, pt_enter, _ = p_nodes[k]
            out.append({"kind": "P",
                        "pts": _slice_path(S, i_enter, pt_enter,
                                           i_leave, pt_leave,
                                           wrap=(k_leave <= k)),
                        "enter": pt_enter, "leave": pt_leave,
                        "edge": edge_of[i_enter] if i_enter < len(edge_of)
                        else 0})
            # ---- W 段：从离开点沿窗口边走到下一个进入点 ----
            # 图形在离开点"离开窗口" ⇒ 沿窗口方向此处"进入图形"
            # （横截交叉时二者互补），所以窗口边上的下一段要走到
            # "窗口离开图形"的那个交点——它正是下一个图形进入点。
            kw = _find_node(w_nodes, pt_leave)
            if kw is None:
                break
            kw_next = _next_node(w_nodes, kw, "离开")
            if kw_next is None:
                break
            j_next, pt_next, _ = w_nodes[kw_next]
            out.append({"kind": "W",
                        "pts": _slice_path(Wc, w_nodes[kw][0], pt_leave,
                                           j_next, pt_next,
                                           wrap=(kw_next <= kw)),
                        "enter": pt_leave, "leave": pt_next,
                        "edge": w_nodes[kw][0]})
            # ---- 回到图形边：找与该进入点重合的图形节点 ----
            kp = _find_node(p_nodes, pt_next)
            if kp is None:
                break
            if abs(pt_next[0] - start_pt[0]) < 1e-6 and \
                    abs(pt_next[1] - start_pt[1]) < 1e-6:
                break           # 回到起点 → 闭环
            k = kp
    return out


# ---------------------------------------------------------------------
# 步骤流
# ---------------------------------------------------------------------
def _window_guide(window: Sequence[Point]):
    """窗口多边形注记（红色虚线 + 格角）。

    与画布上裁剪工具的窗口框同一口径（红色、格角），两者完全重合——
    早先这里画青色格心多边形，结果是"两重错开半格的窗口框"。
    """
    return polygon_guide([(float(x), float(y)) for x, y in window],
                         color="#E5484D", dash=True, width=1.8,
                         anchor="corner")


def clip_polygon_steps(points: Sequence[Point],
                       window: Sequence[Point]) -> List[Step]:
    """双边裁剪步骤流：逐边求交（进入/离开）→ 逐段拼出交集边界。

    每一步的 note 说清"现在在处理什么"，guides 标出当前边、进入/离开
    点与已经拼出的交集边界。
    """
    steps: List[Step] = []
    if len(points) < 3 or len(window) < 3:
        return steps
    P, W, p_edges, w_edges, segs = _compute(points, window)
    wg = _window_guide(W)
    p_outline = polygon_guide([(int(round(x)), int(round(y))) for x, y in P],
                              color=GUIDE_HIT, dash=True, width=1.6)

    steps.append(Step([], {"阶段": "初始", "进入点": 0, "离开点": 0,
                           "输出段": 0, "输入顶点": len(P), "窗口顶点": len(W)},
                      f"待裁剪多边形 {len(P)} 个顶点 × 裁剪窗口 {len(W)} 个顶点"
                      f"（双边裁剪：求交点 → 进入/离开配对 → 拼出交集）",
                      guides=[wg, p_outline]))

    # ---- 阶段 1：逐条被裁边求交，标出进入/离开点 ----
    ent_total = 0
    leave_total = 0
    for e in p_edges:
        guides = [wg, p_outline]
        for (t, pt, kind, _j) in e.cuts:
            if kind == "进入":
                ent_total += 1
                guides.append(point_guide(pt, "进入", "#17A2B8"))
            else:
                leave_total += 1
                guides.append(point_guide(pt, "离开", GUIDE_MARK))
        guides.append(line_guide(e.a, e.b, GUIDE_MOVE, dash=False, width=2.4))
        steps.append(Step([], {"阶段": "求交", "边": e.idx + 1,
                               "进入点": ent_total, "离开点": leave_total,
                               "本边交点": len(e.cuts)},
                      f"被裁第 {e.idx + 1} 条边与窗口求交：{len(e.cuts)} 个交点"
                      f"（进入 {ent_total} / 离开 {leave_total}）",
                      guides=guides))

    # ---- 阶段 2：窗口边求交 ----
    for e in w_edges:
        guides = [wg, p_outline]
        for (t, pt, kind, _j) in e.cuts:
            if kind == "进入":
                ent_total += 1
                guides.append(point_guide(pt, "进入", "#17A2B8"))
            else:
                leave_total += 1
                guides.append(point_guide(pt, "离开", GUIDE_MARK))
        guides.append(line_guide(e.a, e.b, GUIDE_MOVE, dash=False, width=2.4))
        steps.append(Step([], {"阶段": "求交", "边": e.idx + 1,
                               "进入点": ent_total, "离开点": leave_total,
                               "本边交点": len(e.cuts)},
                      f"窗口第 {e.idx + 1} 条边与被裁多边形求交："
                      f"{len(e.cuts)} 个交点"
                      f"（进入 {ent_total} / 离开 {leave_total}）",
                      guides=guides))

    # ---- 阶段 3：逐段拼出交集边界 ----
    loops = _chain(segs)
    if loops:
        def _area(loop):
            return abs(_signed_area(loop))
        loop = max(loops, key=_area)
    else:
        loop = []
    acc: List[Point] = []
    for k, (a, b) in enumerate(segs):
        acc.append(a)
        acc.append(b)
        poly = _dedup(acc)
        steps.append(Step([], {"阶段": "拼接", "输出段": k + 1,
                               "当前顶点": len(poly)},
                      f"输出边界第 {k + 1} 段：沿"
                      f"{'被裁多边形' if _on_subject(a, b, P) else '窗口'}的边前进"
                      f"（已拼 {len(poly)} 个顶点）",
                      guides=[wg, p_outline,
                              polygon_guide([(int(round(x)), int(round(y)))
                                             for x, y in poly],
                                            color="#17A2B8", dash=True,
                                            width=2.4),
                              line_guide(a, b, GUIDE_MOVE, dash=False,
                                         width=2.6)]))

    # ---- 末帧：完整交集 ----
    steps.append(Step([], {"阶段": "完成", "输出段": len(segs),
                           "当前顶点": len(loop)},
                      f"双边裁剪完成：交集 {len(loop)} 个顶点"
                      f"（进入 {ent_total} / 离开 {leave_total}）",
                      guides=[wg, p_outline,
                              polygon_guide([(int(round(x)), int(round(y)))
                                             for x, y in loop],
                                            color="#17A2B8", dash=False,
                                            width=2.6)]))
    return steps


def _on_subject(a: Point, b: Point, P: Sequence[Point]) -> bool:
    """这段输出边界是不是来自被裁多边形的边。"""
    for i in range(len(P)):
        p0, p1 = P[i], P[(i + 1) % len(P)]
        if (abs(p0[0] - a[0]) < 1e-6 and abs(p0[1] - a[1]) < 1e-6) or \
           (abs(p1[0] - a[0]) < 1e-6 and abs(p1[1] - a[1]) < 1e-6):
            return True
    return False
