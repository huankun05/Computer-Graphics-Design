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
from algorithms.steps import (GUIDE_HIT, GUIDE_MOVE, GUIDE_REF, Step,
                              arrow_guide, boundary_guide,
                              border_extension_segments, edge_guide,
                              point_guide, rect_guide)

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


def _border_guides(rect: Rect, hot: str = ""):
    """四条窗口边界的注记线（配合参数卡逐条判定）。

    只画窗口【外侧】的延长段（border_extension_segments）：边界线与
    红色窗口框本来重合，整条画上去会把红框染成灰色/橙色（用户反馈
    "演示过程边界颜色全变了"）。hot = 当前正在判定的边界名，用橙色
    实线高亮其延长段，其余灰色虚线。
    """
    names = {"left": "左边界", "right": "右边界",
             "top": "上边界", "bottom": "下边界"}
    return [boundary_guide(a, b,
                           "#F76B15" if names[edge] == hot else GUIDE_REF,
                           dash=names[edge] != hot)
            for edge, a, b in border_extension_segments(rect, ext=3)]


def liang_barsky_steps(x0: int, y0: int, x1: int, y1: int,
                       rect: Rect) -> List[Step]:
    """参数裁剪步骤流：每处理一条边界输出一步（p/q/u0/u1 全可见）。

    约定（双出口一致）：Step.pixels 只放【当前参数区间对应的线段像素】，
    窗口边框/边界线/当前端点作为 guides 注记，不混入算法像素。
    """
    rx0, ry0, rx1, ry1 = rect
    frame = rect_guide(rect)
    dx, dy = float(x1 - x0), float(y1 - y0)
    p = (-dx, dx, -dy, dy)
    q = (x0 - rx0, rx1 - x0, y0 - ry0, ry1 - y0)
    names = ("左边界", "右边界", "上边界", "下边界")
    side_of = {"左边界": "left", "右边界": "right",
               "上边界": "top", "下边界": "bottom"}
    u0, u1 = 0.0, 1.0
    steps: List[Step] = []

    def _ends(a: float, b: float):
        return (int(round(x0 + a * dx)), int(round(y0 + a * dy)),
                int(round(x0 + b * dx)), int(round(y0 + b * dy)))

    def _seg_at(a: float, b: float):
        sx, sy, ex, ey = _ends(a, b)
        return bresenham_line(sx, sy, ex, ey)

    def _marks(a: float, b: float):
        """当前区间两端的端点注记。"""
        sx, sy, ex, ey = _ends(a, b)
        return [point_guide((sx, sy), "P0", GUIDE_HIT),
                point_guide((ex, ey), "P1", GUIDE_HIT)]

    def _vals(stage, name, pi, qi, cur0, cur1):
        return {"阶段": stage, "边界": name,
                "p": "—" if pi is None else f"{pi:.0f}",
                "q": "—" if qi is None else f"{qi:.0f}",
                "u0": f"{cur0:.3f}", "u1": f"{cur1:.3f}"}

    steps.append(Step(sorted(set(_seg_at(u0, u1))),
                      _vals("初始", "—", None, None, u0, u1),
                      f"初始参数区间 [{u0:.2f}, {u1:.2f}]：整条线段，"
                      "四条边界依次判定",
                      guides=[frame, *_border_guides(rect), *_marks(u0, u1)]))
    for i, (pi, qi) in enumerate(zip(p, q)):
        # 当前边界高亮：整条边压在红框外侧加粗 + 延长段 + 名字，
        # 让"这一轮在跟哪条边求交"一眼可见
        base = [frame,
                edge_guide(rect, side_of[names[i]],
                           label=f"第 {i + 1} 条 · {names[i]}"),
                *_border_guides(rect, names[i]), *_marks(u0, u1)]
        prev = _ends(u0, u1)
        if pi == 0:
            if qi < 0:
                steps.append(Step(sorted(set(_seg_at(u0, u1))),
                                  _vals("舍弃", names[i], 0.0, qi, u0, u1),
                                  f"{names[i]}：p=0、q<0 → 平行在外，舍弃",
                                  guides=base))
                return steps
            steps.append(Step(sorted(set(_seg_at(u0, u1))),
                              _vals("跳过", names[i], 0.0, qi, u0, u1),
                              f"{names[i]}：p=0、q≥0 → 平行，跳过",
                              guides=base))
            continue
        t = qi / pi
        if pi < 0:
            old = u0
            u0 = max(u0, t)
            act = f"p={pi:.0f}<0 → u0 = max({old:.3f}, {t:.3f}) = {u0:.3f}"
        else:
            old = u1
            u1 = min(u1, t)
            act = f"p={pi:.0f}>0 → u1 = min({old:.3f}, {t:.3f}) = {u1:.3f}"
        if u0 > u1:
            steps.append(Step(sorted(set(_seg_at(u0, u1))),
                              _vals("舍弃", names[i], pi, qi, u0, u1),
                              f"{names[i]}：{act} → u0>u1，舍弃",
                              guides=base))
            return steps
        # 端点收缩的箭头：p<0 收起点、p>0 收终点，直观看到"哪一端被拉回来"
        cur = _ends(u0, u1)
        moved = (arrow_guide((prev[0], prev[1]), (cur[0], cur[1]), GUIDE_MOVE)
                 if pi < 0 else
                 arrow_guide((prev[2], prev[3]), (cur[2], cur[3]), GUIDE_MOVE))
        steps.append(Step(sorted(set(_seg_at(u0, u1))),
                          _vals("收窄", names[i], pi, qi, u0, u1),
                          f"{names[i]}：{act}",
                          guides=base + [moved]))
    # 输出步与几何出口一致：四舍五入可能把交点推出半格，钳回窗口内，
    # 保证"末步像素 == liang_barsky() 结果"的双出口契约
    out_ends = (_clamp(int(round(x0 + u0 * dx)), rx0, rx1),
                _clamp(int(round(y0 + u0 * dy)), ry0, ry1),
                _clamp(int(round(x0 + u1 * dx)), rx0, rx1),
                _clamp(int(round(y0 + u1 * dy)), ry0, ry1))
    steps.append(Step(sorted(set(bresenham_line(*out_ends))),
                      _vals("输出", "—", None, None, u0, u1),
                      f"输出参数区间 [{u0:.3f}, {u1:.3f}] 对应的线段",
                      guides=[frame, *_marks(u0, u1)]))
    return steps
