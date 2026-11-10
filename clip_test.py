# -*- coding: utf-8 -*-
"""
=====================================================================
 clip_test.py  —  模块四裁剪演示：动画与真实裁剪【同一口径】回归守卫
=====================================================================
背景（真实缺陷）：裁剪演示页曾把 all_pixels() 改写成"演示长弦的像素"，
于是封闭图形（多边形/圆/椭圆）时整条链路都按长弦算：
  ① 橙色"待挖除"参照层标的是一条水平长弦，而真实裁剪删的是图形轮廓；
     ② 动画末帧多出长弦那一截，播完画布真实裁剪那一瞬画面跳变。
这类问题肉眼很难判（形状还在、只是颜色/轮廓对不上），必须机器守卫。

本脚本对四个演示页 × 各类图元逐项核对四条契约：
  C1 橙色参照层 == 真实擦除集（rasterize 轮廓∪填充 ∩ 窗口）
  C2 动画末帧像素 == 真实保留集（轮廓∪填充 ∩ 窗口外）
  C3 动画末帧像素 == 真正跑完 ClipTool.apply_crop 之后的画布像素
     （"演完即所得"：播完那一瞬画面不能跳）
  C4 判定过程有运动：紫色"当前工作线段"逐帧收缩（线段裁剪三页）

真实口径直接取自 ClipTool.apply_crop 的实现，不另起炉灶重算。
运行：python clip_test.py
=====================================================================
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Windows 控制台默认 GBK，输出 ✓/✗ 会 UnicodeEncodeError —— 强制 UTF-8
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from PySide6.QtWidgets import QApplication  # noqa: E402

_app = QApplication.instance() or QApplication([])

from core.canvas_view import CanvasView  # noqa: E402
from core.rasterizer import rasterize  # noqa: E402
from core.shapes import (KIND_CIRCLE_MID, KIND_ELLIPSE,  # noqa: E402
                         KIND_LINE_BRESENHAM, KIND_POLYGON, CircleShape,
                         EllipseShape, LineShape, PolygonShape)
from modules.module04_clipping.demos import (CohenDemo, LiangDemo,  # noqa: E402
                                            MidpointDemo, PolygonClipDemo)
from modules.module04_clipping.tools import ClipTool  # noqa: E402

PASS = 0
FAIL = []


def ok(cond, desc):
    global PASS
    if cond:
        PASS += 1
    else:
        FAIL.append(desc)
        print(f"    ✗ {desc}")


def _px(seq):
    return {(int(p[0]), int(p[1])) for p in seq}


# ---------------------------------------------------------------------
# 用例矩阵：演示页 × 图元
# ---------------------------------------------------------------------
POLY_V = [(14, 8), (40, 6), (46, 30), (20, 34), (10, 22)]

SUBJECTS = [
    ("直线", lambda: LineShape(kind=KIND_LINE_BRESENHAM,
                               p0=(4, 20), p1=(54, 20))),
    ("多边形", lambda: PolygonShape(kind=KIND_POLYGON, vertices=POLY_V)),
    ("填充多边形", lambda: PolygonShape(kind=KIND_POLYGON, fill=True,
                                        vertices=POLY_V)),
    ("圆", lambda: CircleShape(kind=KIND_CIRCLE_MID, center=(28, 20), r=11)),
    ("填充圆", lambda: CircleShape(kind=KIND_CIRCLE_MID, center=(28, 20),
                                   r=11, fill=True)),
    ("椭圆", lambda: EllipseShape(kind=KIND_ELLIPSE, center=(28, 20),
                                  rx=16, ry=9)),
]

PAGES = [
    ("编码裁剪", CohenDemo, True),
    ("中点分割", MidpointDemo, True),
    ("参数裁剪", LiangDemo, True),
    ("多边形裁剪", PolygonClipDemo, False),
]

PURPLE = "#7C3AED"          # GUIDE_MOVE：算法当前工作线段


def check_case(page_name, demo_cls, is_line_page, sname, make_shape):
    shape = make_shape()
    cv = CanvasView()
    cv.document.shapes.append(shape)
    cv._render_base()
    demo = demo_cls()
    demo._canvas = cv
    demo._spins = {}
    params = demo.collect()
    steps = demo.make_steps(params)
    tag = f"{page_name}/{sname}"
    if not steps:
        ok(False, f"{tag}: 未生成步骤流")
        return
    rect = demo.window_rect()
    x0, y0, x1, y1 = rect

    # ---- 真实口径（照 ClipTool.apply_crop 的语义）----
    outline, fill = rasterize(shape)
    allpx = {(int(x), int(y)) for x, y in outline + fill}
    real_cut = {p for p in allpx if x0 <= p[0] <= x1 and y0 <= p[1] <= y1}
    real_kept = allpx - real_cut

    # ---- C1：橙色参照层（待挖除）== 真实擦除集 ----
    ref = _px(demo.reference_pixels())
    ok(ref == real_cut,
       f"{tag}: 橙色参照层 != 真实擦除集"
       f"（多标 {len(ref - real_cut)} / 漏标 {len(real_cut - ref)}）")

    # ---- C2：动画末帧 == 真实保留集 ----
    last = steps[-1]
    frame = _px(last.pixels) | _px(last.tint)
    ok(frame == real_kept,
       f"{tag}: 动画末帧 != 真实保留集"
       f"（多出 {len(frame - real_kept)} / 缺少 {len(real_kept - frame)}）")

    # ---- C3：动画末帧 == 真跑一次 apply_crop 之后的画布像素 ----
    tool = ClipTool(cv)
    cv.set_tool(tool)
    tool.rect = rect
    tool.apply_crop([shape], rect, keep_window=True)
    o2, f2 = rasterize(shape)
    after = {(int(x), int(y)) for x, y in o2 + f2}
    ok(frame == after,
       f"{tag}: 动画末帧 != 真实裁剪结果"
       f"（多出 {len(frame - after)} / 缺少 {len(after - frame)}）")

    # ---- C4：判定过程有运动（紫色当前工作线段逐帧收缩）----
    if is_line_page:
        seq = []
        for st in steps:
            cur = tuple((g["a"], g["b"]) for g in st.guides
                        if g.get("kind") == "line" and g.get("color") == PURPLE)
            if not seq or seq[-1] != cur:
                seq.append(cur)
        ok(len(seq) >= 2, f"{tag}: 紫色当前线段全程未变化（动画不动）")

    # ---- C5：逐段遍历（封闭图形必须真的沿边界一段段走）----
    sizes = [len(st.pixels) for st in steps]
    ok(all(sizes[i] >= sizes[i + 1] for i in range(len(sizes) - 1)),
       f"{tag}: 像素层不是单调递减（挖除过程不是渐进的）{sizes}")
    if is_line_page and sname != "直线":
        segs = demo._segments()
        ok(len(segs) > 1,
           f"{tag}: 未沿边界逐段遍历（只有 {len(segs)} 段，应为多段）")
        ok(any("段" in st.note for st in steps),
           f"{tag}: 步骤未标注第几段")


print("=" * 64)
print("模块四裁剪演示：动画口径 vs 真实裁剪")
for page_name, demo_cls, is_line_page in PAGES:
    for sname, make_shape in SUBJECTS:
        if not is_line_page and sname == "直线":
            continue          # 多边形裁剪页只吃封闭图形
        check_case(page_name, demo_cls, is_line_page, sname, make_shape)

print("=" * 64)
if FAIL:
    print(f"clip_test: FAIL ✗（{len(FAIL)} 项未通过，共 {PASS + len(FAIL)} 项）")
    sys.exit(1)
print(f"clip_test: PASS ✓（共 {PASS} 项）")
