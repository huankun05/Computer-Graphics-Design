# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/fill_scanline.py  —  扫描线多边形填充算法
=====================================================================
原理：
  对每一条水平扫描线 y，求它与多边形所有边的交点，
  把交点按 x 排序，两两配对 [x0,x1], [x2,x3], ...
  每对交点之间的所有像素都属于多边形内部，直接填色。

顶点处理（避免重复计数）：
  对每条边只统计其【较小 y 端】（y_min 端），
  较大 y 端不参与交点计数——这样两条边在公共顶点处不会被数两次。

优化方向（报告里讲）：
  完整工程版会建立 ET（边表）+ AET（有效边表），
  按 y 递增时把新边链入 AET、把出边链摘出，并用 1/k 增量更新交点，
  把逐边遍历降到 O(边数) 均摊。本演示用直接遍历，多边形顶点少，足够快。

双出口（规范契约①）：
  scanline_fill()       -> 最终像素列表（渲染用）
  scanline_fill_steps() -> 步骤流（每步 = 一条扫描线的整行填充像素 +
                           交点数等状态），演示时逐行填充、观察配对
两个出口的像素输出【完全一致】，由 render_test.py 像素级回归保证。
=====================================================================
"""

from typing import List, Tuple

from algorithms.steps import Step, expand_steps

Pixel = Tuple[int, int]


def scanline_fill_steps(vertices: List[Pixel]) -> List[Step]:
    """
    给定多边形顶点（至少 3 个），返回按扫描线逐步填充的【步骤流】。
    每步 = 一条扫描线 y 的全部配对填充像素 + 交点信息。
    多边形按 vertices 顺序闭合。
    """
    n = len(vertices)
    if n < 3:
        # 少于 3 个顶点构不成多边形，返回空步骤流
        return []

    # ---------- 1. 收集所有非水平边 ----------
    edges = []
    for i in range(n):
        x0, y0 = vertices[i]
        x1, y1 = vertices[(i + 1) % n]
        if y0 == y1:
            continue                      # 水平边不与扫描线产生交点
        # 让 y_min 为边的"下端"，y_max 为"上端"
        if y0 < y1:
            y_min, y_max = y0, y1
            x_at_ymin = x0
        else:
            y_min, y_max = y1, y0
            x_at_ymin = x1
        dx = x1 - x0
        dy = y1 - y0
        inv_k = dx / dy                   # 每走 1 行，x 的增量
        edges.append((y_min, y_max, x_at_ymin, inv_k))

    if not edges:
        return []

    y_min_all = min(e[0] for e in edges)
    y_max_all = max(e[1] for e in edges)

    # ---------- 2. 对每条扫描线求交点并填充（一步 = 一条扫描线） ----------
    step_list: List[Step] = []
    for y in range(y_min_all, y_max_all):
        xs = []
        for (ey_min, ey_max, x_start, inv_k) in edges:
            # 该边与当前扫描线相交：y 在 [y_min, y_max) 区间
            if ey_min <= y < ey_max:
                x_intersect = x_start + inv_k * (y - ey_min)
                xs.append(x_intersect)

        xs.sort()
        # 两两配对填充
        row_pixels: List[Pixel] = []
        for i in range(0, len(xs) - 1, 2):
            xa = int(round(xs[i]))
            xb = int(round(xs[i + 1]))
            if xa > xb:
                xa, xb = xb, xa
            for x in range(xa, xb + 1):
                row_pixels.append((x, y))
        if row_pixels:
            step_list.append(Step(
                row_pixels,
                {"y": y, "交点数": len(xs), "填充像素": len(row_pixels)},
                f"扫描线 y={y}：{len(xs)} 个交点排序后两两配对，填 {len(row_pixels)} 像素",
            ))
    return step_list


def scanline_fill(vertices: List[Pixel]) -> List[Pixel]:
    """扫描线填充最终像素列表（由步骤流展开，保证逐步版本一致）。"""
    return expand_steps(scanline_fill_steps(vertices))
