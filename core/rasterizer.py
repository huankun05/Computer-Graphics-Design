# -*- coding: utf-8 -*-
"""
=====================================================================
 core/rasterizer.py  —  光栅化器：图元参数 → 像素坐标列表
=====================================================================
把一个 Shape（只存几何参数）翻译成像素坐标，全部通过 algorithms/ 的
纯算法函数完成——画布自身不做任何几何计算。

输出分两组（对应旧版画布的绘制行为，像素级别一致）：
  outline: 轮廓像素（线条类图元的全部像素；多边形的各边）→ 按线宽画
  fill:    填充像素（扫描线填充内部，固定 1px 画）→ 仅多边形填充时有

未来新增图元类型（模块三~六）时在 _DISPATCH 里登记"kind → 算法"即可。
=====================================================================
"""

from typing import List, Tuple

from algorithms.line_dda import dda_line
from algorithms.line_bresenham import bresenham_line
from algorithms.circle_midpoint import midpoint_circle
from algorithms.ellipse_midpoint import midpoint_ellipse
from algorithms.fill_scanline import scanline_fill
from algorithms.fill_span import span_fill
from algorithms.circle_dda import dda_circle
from core.shapes import RasterFillShape
from core.shapes import (
    Shape, LineShape, CircleShape, EllipseShape, PolygonShape,
    KIND_LINE_DDA, KIND_LINE_BRESENHAM, KIND_CIRCLE, KIND_ELLIPSE, KIND_POLYGON,
)

Pixel = Tuple[int, int]


def _apply_erased(shape: Shape, outline: List[Pixel],
                  fill: List[Pixel]) -> Tuple[List[Pixel], List[Pixel]]:
    """橡皮擦掩码扣减：被擦除的像素不再输出。"""
    erased = getattr(shape, "erased", None)
    if not erased:
        return outline, fill
    outline = [p for p in outline if p not in erased]
    fill = [p for p in fill if p not in erased]
    return outline, fill


def rasterize(shape: Shape) -> Tuple[List[Pixel], List[Pixel]]:
    """
    图元 → (轮廓像素, 填充像素)。

    轮廓像素调用者按 shape.width 展开成小方块；
    填充像素固定 1 像素（大面积填充不放大线宽，与旧版一致）。
    """
    if isinstance(shape, LineShape):
        x0, y0 = shape.p0
        x1, y1 = shape.p1
        pts = (dda_line(x0, y0, x1, y1) if shape.kind == KIND_LINE_DDA
               else bresenham_line(x0, y0, x1, y1))
        outline, fill = _apply_erased(shape, pts, [])
        return outline, fill

    if isinstance(shape, CircleShape):
        cx, cy = shape.center
        # 圆算法分派：circle_dda=角度采样 / circle_mid|circle=中点圆
        if shape.kind == "circle_dda":
            outline = dda_circle(cx, cy, shape.r)
        else:
            outline = midpoint_circle(cx, cy, shape.r)
        fill = span_fill(outline) if shape.fill else []
        outline, fill = _apply_erased(shape, outline, fill)
        return outline, fill

    if isinstance(shape, EllipseShape):
        cx, cy = shape.center
        outline = midpoint_ellipse(cx, cy, shape.rx, shape.ry)
        fill = span_fill(outline) if shape.fill else []
        outline, fill = _apply_erased(shape, outline, fill)
        return outline, fill

    if isinstance(shape, PolygonShape):
        v = shape.vertices
        outline: List[Pixel] = []
        for i in range(len(v)):
            x0, y0 = v[i]
            x1, y1 = v[(i + 1) % len(v)]
            outline.extend(bresenham_line(x0, y0, x1, y1))
        fill = scanline_fill(v) if (shape.fill and len(v) >= 3) else []
        outline, fill = _apply_erased(shape, outline, fill)
        return outline, fill

    if isinstance(shape, RasterFillShape):
        outline, fill = _apply_erased(shape, list(shape.pixels), [])
        return outline, fill

    # 未知图元类型：不画（未来模块注册自己的 kind 前先保证 rasterize 支持）
    return [], []
