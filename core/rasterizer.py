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
from algorithms.ellipse_rotated import rotated_ellipse
from algorithms.fill_scanline import scanline_fill
from algorithms.fill_span import span_fill
from algorithms.circle_dda import dda_circle
from core.shapes import RasterFillShape
from core.shapes import (
    Shape, LineShape, CircleShape, EllipseShape, PolygonShape,
    KIND_LINE_DDA, KIND_LINE_BRESENHAM, KIND_CIRCLE, KIND_ELLIPSE, KIND_POLYGON,
)

Pixel = Tuple[int, int]


def _cut_mask(shape: Shape) -> frozenset:
    """图元的几何挖除区域（裁剪窗口）→ 掩膜像素集合。

    ★ 为什么要有这一层（用户反馈："裁剪掉右下角后一旋转，右下角又冒出
    一片黑散点"）：裁剪是**几何**操作——"挖掉的是窗口这块区域"。
    图元变换后是重新光栅化的（圆/椭圆还按协方差矩阵解析式重参数化），
    若挖除范围只是"旧像素集的点采样"，两边就不同源：采样点取整后漏格，
    本该挖掉的像素没被盖住 → 变换后残留一片黑散点。
    所以窗口多边形随图元一起变换，渲染时按几何重新求交（区域始终连续）。

    掩膜按 cuts 内容缓存（内容变了缓存自动失效）。
    """
    cuts = getattr(shape, "cuts", None)
    if not cuts:
        return frozenset()
    key = tuple(tuple((float(x), float(y)) for x, y in poly) for poly in cuts)
    cache = getattr(shape, "_cut_cache", None)
    if cache is not None and cache[0] == key:
        return cache[1]
    from algorithms.window_mask import polygon_mask, polygon_mask_float
    mask = set()
    for poly in cuts:
        if all(float(x).is_integer() and float(y).is_integer()
               for x, y in poly):
            # 整数顶点：与窗口掩膜同一函数，保证未变换时逐像素一致
            mask |= polygon_mask([(int(x), int(y)) for x, y in poly])
        else:
            # 变换后的浮点顶点：按点包含判定，避免取整漂移
            mask |= polygon_mask_float(poly)
    mask = frozenset(mask)
    try:
        shape._cut_cache = (key, mask)
    except AttributeError:          # 极端情况：不允许挂属性就现算
        pass
    return mask


def _apply_erased(shape: Shape, outline: List[Pixel],
                  fill: List[Pixel]) -> Tuple[List[Pixel], List[Pixel]]:
    """擦除掩码 + 裁剪窗口扣减：被擦除/被挖掉的像素不再输出。"""
    erased = getattr(shape, "erased", None)
    cut = _cut_mask(shape)
    if not erased and not cut:
        return outline, fill
    if erased:
        outline = [p for p in outline if p not in erased]
        fill = [p for p in fill if p not in erased]
    if cut:
        outline = [p for p in outline if p not in cut]
        fill = [p for p in fill if p not in cut]
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
        angle = getattr(shape, "angle", 0.0)
        if abs(angle) > 1e-6:
            # 旋转椭圆：扫描线求交，轮廓/填充一次生成
            outline, inside = rotated_ellipse(cx, cy, shape.rx, shape.ry,
                                              angle)
            fill = inside if shape.fill else []
        else:
            # 角度为 0 时保持原中点椭圆路径，既有像素回归不变
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
