# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/fill_span.py  —  跨段填充（凸形内部填充：圆 / 椭圆）
=====================================================================
原理（与扫描线填充同一思想的最简形态）：
  对轮廓像素按行分组，每行取最左与最右像素，两之间的所有像素
  都属于内部，整段填充。

  该"奇偶跨段"填充对【凸形】严格正确（圆、椭圆是凸的）；
  凹多边形请用 fill_scanline.py 的交点配对版（按边求交而非按轮廓，
  可正确处理凹缺）。

双出口（规范契约①）：
  span_fill()       -> 最终像素列表
  span_fill_steps() -> 步骤流（每步 = 一行的整段填充像素）
=====================================================================
"""

from typing import List

from algorithms.steps import Step, expand_steps


def span_fill_steps(outline: List[tuple]) -> List[Step]:
    """轮廓像素 → 逐行跨段填充的【步骤流】。"""
    rows = {}
    for x, y in outline:
        rows.setdefault(y, []).append(x)
    steps = []
    for y in sorted(rows):
        xs = rows[y]
        row = [(x, y) for x in range(min(xs), max(xs) + 1)]
        steps.append(Step(
            row,
            {"y": y, "填充像素": len(row)},
            f"y={y}：轮廓 [{min(xs)},{max(xs)}]，整段填充 {max(xs)-min(xs)+1} 像素",
        ))
    return steps


def span_fill(outline: List[tuple]) -> List[tuple]:
    """轮廓像素 → 内部填充像素列表（由步骤流展开，保证两版本一致）。"""
    return expand_steps(span_fill_steps(outline))
