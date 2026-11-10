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

本脚本对四个演示页 × 各类图元逐项核对六条契约：
  C1 橙色参照层 == 真实擦除集（rasterize 轮廓∪填充 ∩ 窗口）
  C2 动画末帧像素 == 真实保留集（轮廓∪填充 ∩ 窗口外）
  C3 动画末帧像素 == 真正跑完 ClipTool.apply_crop 之后的画布像素
     （"演完即所得"：播完那一瞬画面不能跳）
  C4 判定过程有运动：紫色"当前工作线段"逐帧收缩（线段裁剪三页）
  C5 像素层单调递减 + 封闭图形真的沿边界多段遍历
  C6 配色分层：帧内每个填充像素都必须落在 tint 里（否则填充被画成
     轮廓的同一个颜色，边框就"展示不出来"——用户反馈）
  C7 渲染实况：像素层真正画出来时，边框像素与填充像素颜色必须不同
  C8 累积：同一个图元上连续裁两次，第二次不能覆盖第一次的结果

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
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402

_app = QApplication.instance() or QApplication([])

from core.canvas_view import CanvasView  # noqa: E402
from core.rasterizer import rasterize  # noqa: E402
from core.shapes import (IMAGE_H, IMAGE_W, KIND_CIRCLE_MID,  # noqa: E402
                         KIND_ELLIPSE, KIND_LINE_BRESENHAM, KIND_POLYGON,
                         CircleShape, EllipseShape, LineShape, PolygonShape,
                         SIM)
from modules.module04_clipping.demos import (CohenDemo, LiangDemo,  # noqa: E402
                                            MidpointDemo, PolygonClipDemo)
from modules.module04_clipping.tools import ClipTool  # noqa: E402
from ui import theme  # noqa: E402

ACCENT = theme.ACCENT

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

    # ---- C6：配色分层——帧内每个填充像素都必须落在 tint 里 ----
    # tint = 演示层用"淡色"画的那部分像素（填充区）。填充像素若不在
    # tint 里，就会被当成轮廓用主色画 → 边框与填充同色，边框消失
    # （用户反馈："把它和填充的颜色弄成一个颜色了，展示不出来"）。
    edge = {(int(x), int(y)) for x, y in outline}
    fillonly = {(int(x), int(y)) for x, y in fill} - edge
    bad_tint = 0
    bad_untinted = 0
    for st in steps:
        ts = _px(st.tint)
        px_set = _px(st.pixels)
        bad_tint += len(ts & edge)                    # 轮廓被当成填充染色
        bad_untinted += len((px_set & fillonly) - ts)  # 填充没被单独染色
    ok(bad_tint == 0,
       f"{tag}: {bad_tint} 个轮廓像素被当成填充染色（边框会糊掉）")
    ok(bad_untinted == 0,
       f"{tag}: {bad_untinted} 个填充像素没被单独染色"
       f"（填充与边框同色，边框展示不出来）")

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


def check_paint_separation(page_name, demo_cls, sname, make_shape):
    """C7：像素层【真正画出来】时，边框像素与填充像素必须是两种颜色。

    数据层对齐（C6）还不够——演示层画的时候如果把填充画在轮廓之上、
    或者填充色与主色几乎一样，画面上照样只剩一个颜色。这里直接把
    PixelLayer 画到一张白底图上取样，量的是用户眼睛看到的那一层。

    取样点特意挑【窗口内】的填充像素：动画一开始它们就整片在画面上，
    旧实现把它们混进了"主色"组 → 边框与填充糊成同一个颜色。
    """
    shape = make_shape()
    cv = CanvasView()
    cv.document.shapes.append(shape)
    cv._render_base()
    demo = demo_cls()
    demo._canvas = cv
    demo._spins = {}
    steps = demo.make_steps(demo.collect())
    tag = f"{page_name}/{sname}"
    if not steps:
        ok(False, f"{tag}: 未生成步骤流")
        return
    # 与真实播放同口径：裁剪页是替换式（不累积轨迹）
    cv.demo.set_accumulate(getattr(demo, "trails", True))
    x0, y0, x1, y1 = demo.window_rect()
    outline, fill = rasterize(shape)
    edge = {(int(x), int(y)) for x, y in outline}
    fillonly = {(int(x), int(y)) for x, y in fill} - edge
    first = steps[0]
    frame = _px(first.pixels) | _px(first.tint)
    inside_fill = sorted(p for p in fillonly if p in frame
                         and x0 <= p[0] <= x1 and y0 <= p[1] <= y1)
    edge_in = sorted(p for p in edge if p in frame)
    if not inside_fill or not edge_in:
        return                   # 没有填充区 / 窗口没盖到填充 → 无从比较
    # 只走第一步（起始态：整块图元都在画面上）
    cv.demo.advance(first, first.values.get("color", ACCENT))
    cv.demo.solidify()          # 定格为不透明实色，颜色可精确取样
    img = QImage(IMAGE_W, IMAGE_H, QImage.Format_RGB32)
    img.fill(QColor("#FFFFFF"))
    p = QPainter(img)
    cv.demo.paint(p)
    p.end()

    def at(px):
        return img.pixelColor(px[0] * SIM + SIM // 2, px[1] * SIM + SIM // 2)

    c_edge, c_fill = at(edge_in[0]), at(inside_fill[0])
    ok(c_edge != c_fill,
       f"{tag}: 边框与填充渲染成同一颜色 {c_edge.name()}（边框展示不出来）")
    ok(c_fill.lightness() > c_edge.lightness() + 20,
       f"{tag}: 填充色 {c_fill.name()} 不比边框色 {c_edge.name()} 浅"
       f"（填充与边框分不开）")


class _Spin:
    """参数卡 SpinBox 的最小替身（测试里只需要读值）。"""

    def __init__(self, v):
        self._v = v

    def value(self):
        return self._v


def check_accumulate():
    """C8：同一个图元上连续裁两次，第二次不能覆盖第一次。

    用户反馈："我不能在同一个图形上面进行两次操作，第二次操作会覆盖
    第一次的操作。" 演示壳原先在每次重生成步骤流时都把上一轮裁剪
    还原掉 → 第二次裁剪从原图重来，第一次的结果整个消失。
    这里连做两轮真裁剪（走演示壳的落地路径），核对最终擦除集 =
    两轮窗口内像素的并集。
    """
    from ui.demo_view import DemoView
    dv = DemoView()
    cv = dv.canvas
    shape = PolygonShape(kind=KIND_POLYGON, fill=True, vertices=POLY_V,
                         color=QColor("#222222"))
    cv.document.shapes.append(shape)
    cv._render_base()
    demo = CohenDemo()
    demo._canvas = cv
    demo.tool_selector(cv)
    dv.current_demo = demo
    dv._spins = getattr(dv, "_spins", {})

    outline, fill = rasterize(shape)
    allpx = {(int(x), int(y)) for x, y in outline + fill}

    def cut_of(rect):
        x0, y0, x1, y1 = rect
        return {p for p in allpx if x0 <= p[0] <= x1 and y0 <= p[1] <= y1}

    # 第一轮：默认窗口
    rect_a = demo.window_rect()
    demo._spins = {"wx0": _Spin(rect_a[0]), "wy0": _Spin(rect_a[1]),
                   "wx1": _Spin(rect_a[2]), "wy1": _Spin(rect_a[3])}
    dv._regenerate(fit=False, autoplay=False)
    dv._finish_clip_playback()
    after_a = set(shape.erased)
    ok(after_a == cut_of(rect_a),
       f"第一轮裁剪结果不对（擦除 {len(after_a)} 像素）")

    # 第二轮：换到【与第一轮互不重叠】的另一个窗口。
    # 必须不重叠——否则第二个窗口是第一个的子集，"累积"与"覆盖"
    # 两种结果完全一样，守卫就白测了。
    rect_b = (10, 12, 19, 30)
    demo._spins = {"wx0": _Spin(rect_b[0]), "wy0": _Spin(rect_b[1]),
                   "wx1": _Spin(rect_b[2]), "wy1": _Spin(rect_b[3])}
    cut_a, cut_b = cut_of(rect_a), cut_of(rect_b)
    ok(cut_a and cut_b and not (cut_a & cut_b),
       f"测试用的两个窗口必须互不重叠且都命中图元"
       f"（A={len(cut_a)} B={len(cut_b)} 交集={len(cut_a & cut_b)}）")
    dv._regenerate(fit=False, autoplay=False)
    dv._finish_clip_playback()
    after_b = set(shape.erased)
    ok(after_a <= after_b,
       f"第二次裁剪把第一次的结果冲掉了"
       f"（丢了 {len(after_a - after_b)} 个像素）")
    ok(after_b == cut_a | cut_b,
       f"两次裁剪后擦除集不对（{len(after_b)} 像素，"
       f"应为 {len(cut_a | cut_b)}）")
    ok(len(after_b) > len(after_a),
       f"第二次裁剪没有新增任何擦除（{len(after_b)} == {len(after_a)}）")
    # 第一轮窗口内的像素必须仍然是"已裁掉"
    still = {p for p in cut_a if p in shape.erased}
    ok(still == cut_a,
       f"第二次裁剪后第一轮窗口内的 {len(cut_a - still)} "
       f"个像素复活了")
    # 显式收尾：离屏 Qt 在 QApplication 析构时容易踩到还没销毁的
    # QGraphicsScene，进程退出崩溃（测试结果本身已经打印完了）。
    dv.close()
    dv.deleteLater()
    _app.processEvents()


print("=" * 64)
print("模块四裁剪演示：动画口径 vs 真实裁剪")
for page_name, demo_cls, is_line_page in PAGES:
    for sname, make_shape in SUBJECTS:
        if not is_line_page and sname == "直线":
            continue          # 多边形裁剪页只吃封闭图形
        check_case(page_name, demo_cls, is_line_page, sname, make_shape)

print("-" * 64)
print("渲染实况：边框与填充必须是两种颜色")
for page_name, demo_cls, is_line_page in PAGES:
    for sname, make_shape in SUBJECTS:
        if not is_line_page and sname == "直线":
            continue
        check_paint_separation(page_name, demo_cls, sname, make_shape)

print("-" * 64)
print("累积：同一个图元上连续裁两次")
check_accumulate()

print("=" * 64)
if FAIL:
    print(f"clip_test: FAIL ✗（{len(FAIL)} 项未通过，共 {PASS + len(FAIL)} 项）")
    sys.exit(1)
print(f"clip_test: PASS ✓（共 {PASS} 项）")
