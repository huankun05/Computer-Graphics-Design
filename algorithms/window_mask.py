# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/window_mask.py  —  任意多边形窗口掩膜（区域挖除）
=====================================================================
区域裁剪工具的"窗口内消失"语义，需要一个"窗口到底覆盖了哪些像素"
的判定。窗口可以是矩形，也可以是任意不规则（含凹）多边形。

算法（三步，全部手写，无第三方依赖）：
  1) 内部：扫描线求交 + 交点按 x 排序两两配对（偶奇规则）。
     与扫描线填充用的是同一套判定，因此凹多边形同样正确；
  2) 边界：每条边用 Bresenham 逐像素补入。
     扫描线按 [y_min, y_max) 半开区间统计（避免公共顶点被数两次），
     所以水平边和最高顶点所在的那一行不会被内部填充覆盖，必须补边；
  3) 按扫描线 y 聚合：一行为一个步骤，便于演示逐行扫描。

双出口（规范契约①）：
  polygon_mask()        -> 掩膜像素集合（挖除判定用）
  polygon_mask_steps()  -> 步骤流（每步 = 一条扫描线的掩膜像素）
两个出口的像素输出完全一致（后者展开即前者）。

坐标一律为 int 模拟像素坐标，原点在左上。
=====================================================================
"""

from typing import List, Set, Tuple

from algorithms.fill_scanline import scanline_fill_steps
from algorithms.line_bresenham import bresenham_line
from algorithms.steps import Step, expand_steps

Pixel = Tuple[int, int]


def polygon_mask_steps(vertices: List[Pixel]) -> List[Step]:
    """任意多边形（可凹）→ 逐扫描线的掩膜步骤流。

    每条扫描线一步：像素 = 内部配对像素 ∪ 该行的边界像素。
    """
    n = len(vertices)
    if n < 3:
        return []

    # k: 扫描线 y → 该行掩膜像素集合（去重，避免内部与边界重复）
    rows: dict = {}

    # ---- 1. 内部：复用扫描线填充的逐行配对（偶奇规则） ----
    for st in scanline_fill_steps(vertices):
        y = st.values.get("y")
        rows.setdefault(y, set()).update(st.pixels)

    # ---- 2. 边界：Bresenham 补边（水平边 / 最高顶点行） ----
    for i in range(n):
        x0, y0 = vertices[i]
        x1, y1 = vertices[(i + 1) % n]
        for px in bresenham_line(x0, y0, x1, y1):
            rows.setdefault(px[1], set()).add(px)

    # ---- 3. 按 y 递增输出步骤（从上到下逐行扫描） ----
    steps: List[Step] = []
    for y in sorted(rows):
        px = sorted(rows[y])
        steps.append(Step(
            px,
            {"y": y, "像素": len(px)},
            f"扫描线 y={y}：内部配对 + 边界补点，掩膜 {len(px)} 像素",
        ))
    return steps


def polygon_mask(vertices: List[Pixel]) -> Set[Pixel]:
    """任意多边形窗口 → 掩膜像素集合（由步骤流展开，保证与逐步版一致）。"""
    return set(expand_steps(polygon_mask_steps(vertices)))


def point_in_polygon(vertices: List[Pixel], point: Pixel) -> bool:
    """射线法（偶奇规则）判断点是否在多边形内；落在边界上按"内"处理。

    用于裁剪窗口的整体拖动：按在窗口内部 = 移动窗口，按在顶点 = 拖顶点。
    凹多边形同样正确（射线与边交点计数只反映"穿越"次数）。
    """
    n = len(vertices)
    if n < 3:
        return False
    x, y = point
    inside = False
    for i in range(n):
        x0, y0 = vertices[i]
        x1, y1 = vertices[(i + 1) % n]
        # 先判边界：叉积为 0 且落在端点范围内
        cross = (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)
        if cross == 0 and min(x0, x1) <= x <= max(x0, x1) \
                and min(y0, y1) <= y <= max(y0, y1):
            return True
        # 扫描线穿过该边：只统计 y 区间半开的一侧，避免顶点重复计数
        if (y0 > y) != (y1 > y):
            xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xi:
                inside = not inside
    return inside
