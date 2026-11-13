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
                         KIND_RASTER_FILL, CircleShape, EllipseShape,
                         LineShape, PolygonShape, RasterFillShape, SIM,
                         restore, scale_snapshot, snapshot, transform_shape)
from algorithms import transform2d as tf  # noqa: E402
from algorithms.window_mask import point_in_polygon  # noqa: E402


def _mask_float(vertices):
    """浮点多边形 → 像素中心落在其中的像素集合（守卫自带，不依赖实现细节）。

    守卫要能在【旧代码】上跑出红色，所以这里不引用实现里的新函数：
    只用早已存在的 point_in_polygon 自己算一遍"应挖区域"。
    """
    import math
    if len(vertices) < 3:
        return set()
    x0 = int(math.floor(min(v[0] for v in vertices)))
    x1 = int(math.ceil(max(v[0] for v in vertices)))
    y0 = int(math.floor(min(v[1] for v in vertices)))
    y1 = int(math.ceil(max(v[1] for v in vertices)))
    return {(x, y)
            for y in range(y0, y1 + 1)
            for x in range(x0, x1 + 1)
            if point_in_polygon(vertices, (x, y))}
from modules.module04_clipping.demos import (CohenDemo, LiangDemo,  # noqa: E402
                                            MidpointDemo, PolygonClipDemo,
                                            PolygonClipWADemo)
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


def _gone(shape):
    """图元上【已经被挖掉】的像素（守卫自带，不依赖实现里的新函数）。

    = 橡皮擦点采样（shape.erased）∪ 区域裁剪的几何掩膜（shape.cuts）。
    守卫要能在【旧代码】上跑出红色，所以这里不 import 实现里的
    gone_pixels：自己按窗口掩膜算一遍。旧代码里区域裁剪还会把挖掉的
    像素写进 erased，两者取并集后口径一致。
    """
    from algorithms.window_mask import polygon_mask
    out = {(int(p[0]), int(p[1])) for p in (getattr(shape, "erased", None) or ())}
    for poly in (getattr(shape, "cuts", None) or []):
        verts = [(int(round(x)), int(round(y))) for x, y in poly]
        if len(verts) >= 3:
            out |= polygon_mask(verts)
    return out


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
    ("多边形裁剪·双边", PolygonClipWADemo, False),
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

    # ---- C1：裁剪页不产出【橙色参照层】----
    # 用户反馈（2026-11-13）："被裁剪掉的部分就不用额外颜色显示，
    # 显示画板颜色即可"。旧做法把"窗口内、将被裁掉"的像素整片染成
    # 橙色：既像删除/保留区域对调，又把图形自己的边框一起盖掉——
    # 窗口内那一段轮廓直接看不见了（用户反馈："显示不对啊"）。
    ref = _px(demo.reference_pixels())
    ok(not ref,
       f"{tag}: 裁剪页仍产出橙色参照层 {len(ref)} px"
       f"（被裁掉的部分应直接显示画板颜色）")

    # ---- C1b：画面上的像素只能越来越少（被挖掉的不许再出现）----
    sizes = [len(_px(st.pixels) | _px(st.tint)) for st in steps]
    ok(all(sizes[i] >= sizes[i + 1] for i in range(len(sizes) - 1)),
       f"{tag}: 像素层不是单调递减（挖除过程不是渐进的）")

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
    # "已经挖掉"的像素 = 橡皮擦点采样 ∪ 区域裁剪的几何掩膜
    # （区域裁剪现在只走几何通道，不再混进 shape.erased）；
    # 掩膜是"窗口这块区域"，与图元像素取交集才是真正被挖掉的像素。
    after_a = _gone(shape) & allpx
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
    after_b = _gone(shape) & allpx
    ok(after_a <= after_b,
       f"第二次裁剪把第一次的结果冲掉了"
       f"（丢了 {len(after_a - after_b)} 个像素）")
    ok(after_b == cut_a | cut_b,
       f"两次裁剪后擦除集不对（{len(after_b)} 像素，"
       f"应为 {len(cut_a | cut_b)}）")
    ok(len(after_b) > len(after_a),
       f"第二次裁剪没有新增任何擦除（{len(after_b)} == {len(after_a)}）")
    # 第一轮窗口内的像素必须仍然是"已裁掉"
    still = {p for p in cut_a if p in (_gone(shape) & allpx)}
    ok(still == cut_a,
       f"第二次裁剪后第一轮窗口内的 {len(cut_a - still)} "
       f"个像素复活了")
    # 显式收尾：离屏 Qt 在 QApplication 析构时容易踩到还没销毁的
    # QGraphicsScene，进程退出崩溃（测试结果本身已经打印完了）。
    dv.close()
    dv.deleteLater()
    _app.processEvents()


def check_canvas_fill_contrast():
    """C9：演示画布的【图元填充色】必须与演示层主色区分开。

    真实缺陷（用户截图）：演示画布的 fill_color 就是主题蓝，而演示层用
    主题蓝画被演示图元的轮廓 → 油漆桶填出来的内部和轮廓是同一个蓝，
    边框彻底看不见（"边界和填充一个颜色了，展示不出来"）。
    这里既查配置，也查【渲染实况】：桶填充的内部与演示层轮廓必须不同色。
    """
    from ui.demo_view import DemoView
    dv = DemoView()
    cv = dv.canvas
    fill = getattr(cv, "fill_color", None)
    ok(fill is not None and QColor(fill).name() != QColor(ACCENT).name(),
       f"演示画布填充色 {fill} 与演示层主色 {ACCENT} 相同（边框会被填充吃掉）")

    ell = EllipseShape(kind=KIND_ELLIPSE, color=QColor("#222222"), fill=False,
                       center=(28, 20), rx=16, ry=9)
    filled = EllipseShape(kind=KIND_ELLIPSE, color=QColor("#222222"), fill=True,
                          center=(28, 20), rx=16, ry=9)
    o, f = rasterize(filled)
    edge = {(int(x), int(y)) for x, y in o}
    interior = {(int(x), int(y)) for x, y in f} - edge
    bucket = RasterFillShape(kind=KIND_RASTER_FILL, color=QColor(fill),
                             width=1, seed=(28, 20),
                             pixels=sorted(interior), owner=ell)
    cv.document.shapes.append(ell)
    cv.document.shapes.append(bucket)
    cv._render_base()
    demo = CohenDemo()
    demo._canvas = cv
    demo._spins = {}
    steps = demo.make_steps(demo.collect())
    ok(bool(steps), "桶填充场景未生成步骤流")
    if not steps:
        return
    cv.demo.set_accumulate(getattr(demo, "trails", True))
    cv.demo.advance(steps[0], steps[0].values.get("color", ACCENT))
    # 像素层（演示层画的轮廓）与底图（画布画的桶填充）分别取样
    img = QImage(IMAGE_W, IMAGE_H, QImage.Format_RGB32)
    img.fill(QColor("#FFFFFF"))
    p = QPainter(img)
    cv.demo.paint(p)
    p.end()
    ox, oy = cv._base_origin
    rim_px = sorted(edge)[0]
    inner_px = sorted(interior)[0]
    c_rim = img.pixelColor(rim_px[0] * SIM + SIM // 2,
                           rim_px[1] * SIM + SIM // 2)
    c_inner = cv.base_image.pixelColor(inner_px[0] * SIM - ox * SIM + SIM // 2,
                                       inner_px[1] * SIM - oy * SIM + SIM // 2)
    ok(c_rim != c_inner,
       f"演示层轮廓色 {c_rim.name()} 与画布填充色 {c_inner.name()} 相同"
       f"（边框展示不出来）")
    dv.close()
    dv.deleteLater()
    _app.processEvents()


def check_transform_after_clip():
    """C10：图元被区域裁剪挖掉一部分后，再旋转/缩放 → 被挖区域必须仍然是干净的。

    用户反馈（截图）："原本是一个椭圆，裁剪裁到了它的右下方，照理说右下
    方就全是空白，本来是正确的，但是当我旋转它之后，它右下方就变成了这种
    样子"（右下方冒出一片黑散点）。

    根因：挖除范围原来只是**旧像素集的点采样**（shape.erased），
    而图元变换后是**重新光栅化**的（圆/椭圆还按协方差矩阵解析式
    重参数化）—— 两者不同源：采样点取整映射后漏格，本该被挖掉的像素
    没被盖住 → 变换后残留一片黑散点。
    修法：裁剪窗口作为**几何区域**（shape.cuts）随图元一起变换，
    渲染时按几何重新求交，挖掉的区域始终是连续区域。

    这里走真实路径：ClipTool._apply_all 挖除 → transform_shape 旋转 /
    scale_snapshot 缩放 → 核对"落在变换后窗口内的像素"必须为 0。
    """
    cases = [
        ("椭圆", EllipseShape(kind=KIND_ELLIPSE, color=QColor("#222222"),
                              fill=True, center=(30, 20), rx=15, ry=9)),
        ("多边形", PolygonShape(kind=KIND_POLYGON, fill=True,
                                color=QColor("#222222"),
                                vertices=[(14, 10), (44, 12), (40, 30),
                                          (16, 28)])),
    ]
    window = (30, 20, 46, 34)          # 右下角窗口
    win_poly = [(window[0], window[1]), (window[2], window[1]),
                (window[2], window[3]), (window[0], window[3])]

    for name, shape in cases:
        cv = CanvasView()
        cv.document.shapes.append(shape)
        cv._render_base()

        # ---- 真实挖除（应用模式 ClipTool） ----
        tool = ClipTool(cv)
        tool.rect = window
        tool.mode = "rect"
        tool._apply_all()
        ok(bool(getattr(shape, "cuts", None)),
           f"{name}：裁剪没有记录几何窗口（cuts 为空）——"
           f"变换后被挖区域会漏格、残留黑散点")
        ok(not getattr(shape, "erased", None),
           f"{name}：区域裁剪把挖掉的像素混进了点采样通道（erased）——"
           f"变换时按矩阵取整映射会与重新栅格化错开，"
           f"误挖掉轮廓像素，图形边框出现缺口"
           f"（用户反馈：\"边框也没有跟着图形走\"）")

        def leftovers(acc):
            """当前画出的像素里，落在【累计变换后的窗口】内的（应为 0）。

            acc = 到目前为止施加在图元上的总变换（后施加的矩阵在左）。
            """
            outline, fill = rasterize(shape)
            drawn = {(int(x), int(y)) for x, y in outline + fill}
            return drawn & _mask_float(
                [tf.apply(acc, v) for v in win_poly])

        acc = tf.identity()

        # ---- 旋转 30° ----
        cx, cy = shape.center if hasattr(shape, "center") else (29, 20)
        m = tf.around((cx, cy), tf.rotation(30))
        transform_shape(shape, m)
        acc = tf.compose(m, acc)
        left = leftovers(acc)
        ok(not left,
           f"{name}：旋转 30° 后，被裁掉的区域又冒出 {len(left)} 个黑散点"
           f"（样例 {sorted(left)[:5]}）——裁剪窗口没有跟着图元按几何变换")

        # ---- 再旋转 30°（连续变换不能累积误差） ----
        m2 = tf.around((cx, cy), tf.rotation(30))
        transform_shape(shape, m2)
        acc = tf.compose(m2, acc)
        left2 = leftovers(acc)
        ok(not left2,
           f"{name}：连续旋转两次后，被裁掉的区域冒出 {len(left2)} 个黑散点")

        # ---- 缩放（走 scale_snapshot 那条路径） ----
        snap = snapshot(shape)
        scaled = scale_snapshot(shape.kind, snap, 1.4, 1.4, anchor=(cx, cy))
        restore(shape, scaled)
        ms = tf.around((cx, cy), tf.scaling(1.4, 1.4))
        acc = tf.compose(ms, acc)
        left3 = leftovers(acc)
        ok(not left3,
           f"{name}：缩放 1.4 倍后，被裁掉的区域冒出 {len(left3)} 个黑散点")

        cv.close()


def check_crop_then_rotate_border():
    """C12：裁剪后旋转，图形自己的【边框】必须跟着图形走。

    用户反馈（2026-11-13）："旋转会出现这种情况，边框也没有跟着图形走"。

    根因：区域裁剪过去把挖掉的像素 ALSO 写进 shape.erased（**点采样**），
    变换时按矩阵取整映射；而图元变换后是**重新光栅化**的（圆/椭圆还
    按协方差矩阵解析式重参数化）——两者不同源，映射后的采样点与新像素
    错开，于是**误挖掉本该保留的轮廓像素**：图形边框上凭空出现缺口，
    看着就是"边框留在原地、没跟着图形转"（实测多挖 16~17 个轮廓像素）。

    现在区域裁剪只走 cuts（几何）一路，erased 只留给橡皮擦（像素级）。

    守卫自带期望：另起一份**干净**图元，施加同一变换后重新栅格化，
    再按变换后的窗口（同一矩阵、同一求交口径）扣掉——必须与实际画出
    的像素完全一致（既不多画，也不少画）。旧代码上会少画十几个轮廓
    像素 ⇒ 必红。
    """
    cases = [
        ("椭圆", lambda: EllipseShape(kind=KIND_ELLIPSE, color=QColor("#222222"),
                                      fill=True, center=(30, 20), rx=15, ry=9)),
        ("多边形", lambda: PolygonShape(kind=KIND_POLYGON, fill=True,
                                        color=QColor("#222222"),
                                        vertices=[(14, 10), (44, 12), (40, 30),
                                                  (16, 28)])),
    ]
    window = (30, 20, 46, 34)          # 右下角窗口
    win_poly = [(window[0], window[1]), (window[2], window[1]),
                (window[2], window[3]), (window[0], window[3])]

    for name, make_shape in cases:
        shape = make_shape()
        cv = CanvasView()
        cv.document.shapes.append(shape)
        cv._render_base()
        tool = ClipTool(cv)
        cv.set_tool(tool)
        tool.mode = "rect"
        tool.rect = window
        tool._apply_all()

        cx, cy = shape.center if hasattr(shape, "center") else (29, 20)
        m = tf.around((cx, cy), tf.rotation(30))
        transform_shape(shape, m)

        # 期望：干净图元施加同一变换后重新栅格化，再扣掉变换后窗口内的
        ref = make_shape()
        transform_shape(ref, m)
        ro, rf = rasterize(ref)
        expect = {(int(x), int(y)) for x, y in ro + rf} - _mask_float(
            [tf.apply(m, v) for v in win_poly])

        o, f = rasterize(shape)
        actual = {(int(x), int(y)) for x, y in o + f}
        missing = expect - actual          # 该保留却被挖掉（边框缺口）
        extra = actual - expect            # 不该保留却留着
        ok(not missing and not extra,
           f"{name}：旋转 30° 后图形边框没有跟着图形走"
           f"（被误挖 {len(missing)} 个像素，多留 {len(extra)} 个像素）"
           f"——区域裁剪不能把挖除范围同时写进点采样通道")
        cv.close()


def check_exact_intersection():
    """C11：几何出口必须是【精确交点】，不能在出口处取整。

    病灶（实测）：几何出口写的是 int(round(x))，斜边与斜边相交时
    交点是小数，被取整后整体挪动最多半格——"三角形 × 三角形窗口"
    的交集面积因此少算 5.8 px²（2.4%），斜边上的交点看上去像算错一半。
    而且与应用侧的浮点几何掩膜对不上（两套口径）。

    守卫自带精确解（分数形式，不依赖实现里的任何函数）：
      主体边 A(10,10)→B(45,12) 与窗口边 F(30,30)→D(15,8) 相交于
        x = 615/37 ≈ 16.6216, y = 384/37 ≈ 10.3784
      旧代码取整后得到 (17, 10)，偏差 0.535 px —— 必须判红。
    """
    from algorithms.sutherland_hodgman import clip_polygon_convex
    from algorithms.weiler_atherton import clip_polygon as wa_clip_polygon

    subject = [(10.0, 10.0), (45.0, 12.0), (25.0, 38.0)]
    window = [(15.0, 8.0), (45.0, 8.0), (30.0, 30.0)]
    exact = (615.0 / 37.0, 384.0 / 37.0)

    for algo_name, fn in (("S-H 逐边裁剪", clip_polygon_convex),
                          ("W-A 双边裁剪", wa_clip_polygon)):
        out = fn(subject, window)
        best = min((((p[0] - exact[0]) ** 2 + (p[1] - exact[1]) ** 2) ** 0.5
                    for p in out), default=1e9)
        ok(best <= 0.02,
           f"{algo_name}: 输出顶点离精确交点 {exact[0]:.4f},{exact[1]:.4f} "
           f"偏差 {best:.4f} px > 0.02（几何出口被取整了，交点整体偏半格）")
        ok(any(abs(p[0] - exact[0]) > 1e-9 or abs(p[1] - exact[1]) > 1e-9
               for p in out),
           f"{algo_name}: 输出顶点全是整数（几何出口应是浮点精确交点）")


def _seg_cross_t(a, b, c, d):
    """线段 AB 与 CD 是否相交（守卫自带，不依赖实现里的任何函数）。"""
    rx, ry = b[0] - a[0], b[1] - a[1]
    sx, sy = d[0] - c[0], d[1] - c[1]
    den = rx * sy - ry * sx
    if abs(den) < 1e-12:
        return None
    qx, qy = c[0] - a[0], c[1] - a[1]
    t = (qx * sy - qy * sx) / den
    u = (qx * ry - qy * rx) / den
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return t, u
    return None


def _true_crossings(subject, window):
    """主体多边形 × 窗口多边形的真实交点（守卫自带的期望值）。

    守卫自己按"线段求交"算一遍：这样期望值与实现**不同源**，
    实现取整/多算/少算都能被抓出来。
    """
    n, m = len(subject), len(window)
    pts = []
    for i in range(n):
        a, b = subject[i], subject[(i + 1) % n]
        for j in range(m):
            c, d = window[j], window[(j + 1) % m]
            hit = _seg_cross_t(a, b, c, d)
            if hit is None:
                continue
            t = hit[0]
            p = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            if any(abs(p[0] - q[0]) < 1e-6 and abs(p[1] - q[1]) < 1e-6
                   for q in pts):
                continue                 # 顶点处算两遍，去重
            pts.append(p)
    return pts


def check_wa_alternating_path():
    """C14：双边裁剪的交替路径不得把同一段反复播放。

    用户反馈（2026-11-13）："双边裁剪还是有问题，怎么一直动画反复"。

    病灶（实测）：演示动画沿【栅格化的阶梯轮廓】求交。斜边走到窗口
    边界时可能正好"歇一步"（那一小段与窗口边共线），同一个真实交点
    被拆成"进入 + 离开"两个 ⇒ 多出一个伪交点；行走时又没有"已消费
    节点"约束，外层循环从这个伪进入点重新出发，把同一段又走一遍。
    实测：五边形 × 矩形窗（默认窗口 16,12–46,34）产出 50 段，其中
    6 个不同的段各重复 8 遍 —— 画面上就是同一段动画反复播。

    守卫自带期望：真实几何下"主体边 × 窗口边"的交点数（自己算）。
    进入/离开成对出现 ⇒ 交替路径的段数应等于交点数（一半 P 段、
    一半 W 段），且任何一段都不得重复出现。
    """
    from algorithms.line_bresenham import bresenham_line
    from algorithms.weiler_atherton import wa_outline_path

    subject = [(10, 8), (40, 6), (48, 24), (30, 40), (12, 28)]
    window = [(16, 12), (46, 12), (46, 34), (16, 34)]
    f_subject = [(float(x), float(y)) for x, y in subject]
    f_window = [(float(x), float(y)) for x, y in window]

    true_n = len(_true_crossings(f_subject, f_window))
    ok(true_n == 6,
       f"双边交替路径: 守卫自算的交点数 {true_n} != 6（守卫数据变了？）")

    # ---- 路径层面：不得有重复段 ----
    edges = []
    for i in range(len(subject)):
        a, b = subject[i], subject[(i + 1) % len(subject)]
        edges.append([(float(x), float(y)) for x, y in
                      bresenham_line(a[0], a[1], b[0], b[1])])
    path = wa_outline_path(edges, f_window)
    ok(bool(path),
       f"双边交替路径: 没有生成任何段（真实交点 {true_n} 个）")
    if not path:
        return

    sigs = {}
    for i, seg in enumerate(path):
        pts = seg["pts"]
        sig = (seg["kind"], round(pts[0][0], 3), round(pts[0][1], 3),
               round(pts[-1][0], 3), round(pts[-1][1], 3))
        sigs.setdefault(sig, []).append(i + 1)
    dup = {k: v for k, v in sigs.items() if len(v) > 1}
    ok(not dup,
       f"双边交替路径: {len(dup)} 组段被重复播放（同一段出现多次，"
       f"动画会一直反复）——如 {list(dup.values())[:3]}")

    kinds = [s["kind"] for s in path]
    ok(all(kinds[i] != kinds[i + 1] for i in range(len(kinds) - 1)),
       f"双边交替路径: 段类型没有交替（{kinds}）")

    # ---- 演示页层面：交替段总数 == 真实交点数，且步数不得爆炸 ----
    shape = PolygonShape(kind=KIND_POLYGON, fill=True, vertices=subject,
                         color=QColor("#222222"))
    cv = CanvasView()
    cv.document.shapes.append(shape)
    cv._render_base()
    demo = PolygonClipWADemo()
    demo._canvas = cv
    demo._spins = {}
    steps = demo.make_steps(demo.collect())
    ok(bool(steps), "双边裁剪演示页: 未生成步骤流")
    if not steps:
        cv.close()
        return

    totals = set()
    for st in steps:
        seg_val = str(st.values.get("段", ""))
        if "/" in seg_val:
            totals.add(seg_val.split("/")[-1])
    ok(totals == {str(true_n)},
       f"双边裁剪演示页: 交替段总数 {sorted(totals)} != 真实交点数 "
       f"{true_n}（求交多算/少算了交点 ⇒ 同一段被反复播放）")

    ok(len(steps) <= true_n * 6 + 6,
       f"双边裁剪演示页: {len(steps)} 步远超交点数 {true_n}（同一段被"
       f"反复播放；旧实现这一例是 68 步）")

    # ---- 末帧 == 真实裁剪结果 ----
    rect = demo.window_rect()
    x0, y0, x1, y1 = rect
    outline, fill = rasterize(shape)
    allpx = {(int(x), int(y)) for x, y in outline + fill}
    real_kept = {p for p in allpx
                  if not (x0 <= p[0] <= x1 and y0 <= p[1] <= y1)}
    frame = _px(steps[-1].pixels) | _px(steps[-1].tint)
    ok(frame == real_kept,
       f"双边裁剪演示页: 动画末帧 != 真实保留集"
       f"（多出 {len(frame - real_kept)} / 缺少 {len(real_kept - frame)}）")
    cv.close()


def check_polygon_window():
    """C12：多边形窗口（画一个多边形区域去裁剪）必须与真实裁剪同口径。

    用户要求："多边形裁剪不应该是画一个多边形区域去裁剪吗"。
    这里用一个【凹的】多边形窗口跑两个多边形裁剪页，逐项核对：
      · 参照层 == 真实擦除集（掩膜口径，与应用模式同一套 polygon_mask）；
      · 动画末帧 == 真实保留集；
      · 动画末帧 == 真跑一次 apply_crop 之后的画布像素；
      · 像素层单调递减（挖除是渐进的，不是末帧一次性跳变）。
    """
    from modules.module04_clipping.demos import (PolygonClipDemo,
                                                 PolygonClipWADemo)
    # 凸窗口给逐边裁剪（S-H 只支持凸）；凹窗口给双边裁剪（W-A 的优势）
    convex = [(12, 6), (46, 6), (46, 30), (30, 38), (12, 20)]
    concave = [(12, 6), (46, 6), (46, 30), (30, 38), (30, 18), (12, 18)]
    for page_name, demo_cls, window in (("逐边裁剪", PolygonClipDemo, convex),
                                        ("双边裁剪", PolygonClipWADemo, concave)):
        shape = PolygonShape(kind=KIND_POLYGON, fill=True, vertices=POLY_V,
                             color=QColor("#222222"))
        cv = CanvasView()
        cv.document.shapes.append(shape)
        cv._render_base()
        demo = demo_cls()
        demo._canvas = cv
        demo.tool_selector(cv)
        # 切到"多边形窗口"并把窗口摆上去（等价于用户在画布上布点闭合）
        demo.window_kind = "poly"
        tool = demo._tool
        tool.mode = "poly"
        tool.poly = list(window)
        tool._mask_key = None
        steps = demo.make_steps(demo.collect())
        tag = f"多边形窗口/{page_name}"
        ok(bool(steps), f"{tag}: 未生成步骤流")
        if not steps:
            cv.close()
            continue

        # 真实口径：与 ClipTool.apply_crop 同一套掩膜
        mask = _mask_float(window)
        outline, fill = rasterize(shape)
        allpx = {(int(x), int(y)) for x, y in outline + fill}
        real_cut = {p for p in allpx if p in mask}
        real_kept = allpx - real_cut

        ref = _px(demo.reference_pixels())
        ok(not ref,
           f"{tag}: 裁剪页仍产出橙色参照层 {len(ref)} px"
           f"（被裁掉的部分应直接显示画板颜色）")

        last = steps[-1]
        frame = _px(last.pixels) | _px(last.tint)
        ok(frame == real_kept,
           f"{tag}: 动画末帧 != 真实保留集"
           f"（多出 {len(frame - real_kept)} / 缺少 {len(real_kept - frame)}）")

        tool2 = ClipTool(cv)
        cv.set_tool(tool2)
        tool2.apply_crop([shape], list(window), keep_window=True)
        o2, f2 = rasterize(shape)
        after = {(int(x), int(y)) for x, y in o2 + f2}
        ok(frame == after,
           f"{tag}: 动画末帧 != 真实裁剪结果"
           f"（多出 {len(frame - after)} / 缺少 {len(after - frame)}）")

        sizes = [len(st.pixels) for st in steps]
        ok(all(sizes[i] >= sizes[i + 1] for i in range(len(sizes) - 1)),
           f"{tag}: 像素层不是单调递减（挖除过程不是渐进的）")
        cv.close()

    # 逐边裁剪遇到【凹】窗口必须拒绝出步骤，而不是给一个错的结果
    # （半平面的交表示不了凹窗口；这类窗口请用双边裁剪页）
    shape = PolygonShape(kind=KIND_POLYGON, fill=True, vertices=POLY_V,
                         color=QColor("#222222"))
    cv = CanvasView()
    cv.document.shapes.append(shape)
    cv._render_base()
    demo = PolygonClipDemo()
    demo._canvas = cv
    demo.tool_selector(cv)
    demo.window_kind = "poly"
    tool = demo._tool
    tool.mode = "poly"
    tool.poly = list(concave)
    tool._mask_key = None
    steps = demo.make_steps(demo.collect())
    ok(not steps,
       "多边形窗口/逐边裁剪: 凹窗口竟然生成了步骤流"
       "（半平面切不出凹窗口，结果是错的，必须拒绝）")
    ok(bool(demo.empty_hint),
       "多边形窗口/逐边裁剪: 凹窗口被拒绝时没有给出提示")
    cv.close()


def check_app_polygon_window():
    """C13：应用模式（不是演示）用多边形窗口挖除，必须与掩膜一致。

    用户要求："多边形裁剪不应该是画一个多边形区域去裁剪吗"——应用模式
    里画一个多边形区域，按"挖除窗口内"必须真的只挖掉窗口内那部分，
    且挖除区要记成【几何多边形】随图元一起变换（旋转后仍是干净一块）。
    """
    from modules.module04_clipping.tools import MODE_POLY
    window = [(12, 6), (46, 6), (46, 30), (30, 38), (30, 18), (12, 18)]
    shape = PolygonShape(kind=KIND_POLYGON, fill=True, vertices=POLY_V,
                         color=QColor("#222222"))
    cv = CanvasView()
    cv.document.shapes.append(shape)
    cv._render_base()
    tool = ClipTool(cv)
    cv.set_tool(tool)
    tool.mode = MODE_POLY
    tool.poly = list(window)
    tool._mask_key = None

    mask = _mask_float(window)
    outline, fill = rasterize(shape)
    allpx = {(int(x), int(y)) for x, y in outline + fill}
    want_cut = {p for p in allpx if p in mask}
    tool._apply_all()
    o2, f2 = rasterize(shape)
    after = {(int(x), int(y)) for x, y in o2 + f2}
    ok(after == allpx - want_cut,
       f"应用模式/多边形窗口: 挖除结果不对"
       f"（多留 {len(after - (allpx - want_cut))} / 多挖 "
       f"{len((allpx - want_cut) - after)}）")
    ok(bool(shape.cuts) and len(shape.cuts[0]) == len(window),
       "应用模式/多边形窗口: 挖除区没有记成几何多边形"
       "（旋转后会残留黑散点）")
    cv.close()


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

print("-" * 64)
print("画布填充色：必须与演示层主色区分开")
check_canvas_fill_contrast()

print("-" * 64)
print("变换后：被裁掉的区域必须仍然是干净的（不能冒黑散点）")
check_transform_after_clip()

print("-" * 64)
print("变换后：图形自己的边框必须跟着图形走")
check_crop_then_rotate_border()

print("-" * 64)
print("播放速度：裁剪页必须够慢（逐帧看得清判定过程）")
for _page_name, _demo_cls, _is_line in PAGES:
    _fps = getattr(_demo_cls, "default_fps", 30)
    ok(_fps <= 1.0 + 1e-9,
       f"{_page_name}: 默认速度 {_fps:g} 步/秒 > 1（判定过程看不清，"
       f"用户反馈\"在最低速度下感觉都比较快\"）")
from teaching.player import MAX_FPS, MIN_FPS  # noqa: E402
ok(MIN_FPS <= 0.1 + 1e-9,
   f"播放器最慢档 {MIN_FPS:g} 步/秒（应 ≤0.1，即一步 10 秒）")
ok(MAX_FPS >= 240 - 1e-9, f"播放器最快档 {MAX_FPS:g} 步/秒（应 ≥240）")

print("-" * 64)
print("几何出口：斜边交点不能被取整（几何精确性）")
check_exact_intersection()

print("-" * 64)
print("双边裁剪：交替路径不得反复播放同一段")
check_wa_alternating_path()

print("-" * 64)
print("多边形窗口：画一个多边形区域去裁剪")
check_polygon_window()

print("-" * 64)
print("应用模式：多边形窗口挖除")
check_app_polygon_window()

print("=" * 64)
if FAIL:
    print(f"clip_test: FAIL ✗（{len(FAIL)} 项未通过，共 {PASS + len(FAIL)} 项）")
    sys.exit(1)
print(f"clip_test: PASS ✓（共 {PASS} 项）")
