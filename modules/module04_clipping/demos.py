# -*- coding: utf-8 -*-
"""
=====================================================================
 modules/module04_clipping/demos.py — 模块四演示页（区域裁剪）
=====================================================================
三页线段裁剪（Cohen-Sutherland / 中点分割 / Liang-Barsky）
+ 一页多边形裁剪（Sutherland-Hodgman）。
每页 = 参数卡（窗口四边）+ 公式卡 + 决策项监视 + 播放控制，
步骤流来自 algorithms/* 的 *_steps()（与真实裁剪函数共用同一套判定）。

演示对象 = 画布上选中（或最后画的）图元，动画沿它的【边界逐段遍历】，
每段跑一遍本页算法、当场判定在不在窗口里，落在窗口内的部分被挖掉：
  · 直线 → 一条线段（完整看一次判定过程）；
  · 多边形 → 各条边（逐边 Bresenham 像素与 rasterize 轮廓完全一致，
    判定轨迹与原图逐像素重合——用户反馈："画出来的轨迹和原来的轨迹
    不一样，像是两种画法"）；
  · 圆 / 椭圆 → 取图元真实栅格轮廓像素，按绕中心极角排成有序点列，
    每 5~6 个相邻像素切一段（段首尾连成直线，轨迹贴着原轮廓）。
画布上没有可用图元时只提示，不生成任何内置示例。
演示页不对画布手绘图元做回放（freehand_replay=False）。
=====================================================================
"""

from PySide6.QtWidgets import QGridLayout, QLabel, QSpinBox, QVBoxLayout

from algorithms.cohen_sutherland import (cohen_sutherland,
                                         cohen_sutherland_steps, code_text,
                                         region_code)
from algorithms.liang_barsky import liang_barsky, liang_barsky_steps
from algorithms.midpoint_clip import midpoint_clip, midpoint_clip_steps
from algorithms.sutherland_hodgman import clip_polygon_steps

ALGO_COHEN = "cohen_sutherland"
ALGO_MIDPOINT = "midpoint"
ALGO_LIANG = "liang_barsky"
ALGO_HODGMAN = "sutherland_hodgman"

# Cohen 的 9 个区域：窗口内 + 四边 + 四角（键 = 4 位区域码的十进制值）
REGION_CN = {0: "窗口内", 1: "左", 2: "右", 4: "上", 8: "下",
             5: "左上", 6: "右上", 9: "左下", 10: "右下"}


def _outline_pixels_sorted(shape, ignore_erased: bool = False):
    """圆/椭圆 → 真实栅格轮廓的有序点列（按绕中心极角排序）。

    不再用参数方程重新采样——那样得到的弦与画布实际栅格化的弧
    （中点圆/椭圆算法）是两套像素，演示轨迹贴不上原图（"两种画法"）。
    直接取 rasterize 的轮廓像素，按极角排成绕圈顺序：相邻点即轮廓上
    相邻像素，微段判定轨迹与原图逐一重合。

    ignore_erased=True 时取【未被裁掉】的完整轮廓：同一图形上做第二次
    裁剪时，要靠完整轮廓才能看出"哪一段连续、哪一段是上一轮的缺口"。
    """
    import copy
    import math
    from core.rasterizer import rasterize
    src = shape
    if ignore_erased and getattr(shape, "erased", None):
        src = copy.copy(shape)
        src.erased = set()
    outline, _fill = rasterize(src)
    cx, cy = shape.center
    return sorted({(int(x), int(y)) for x, y in outline},
                  key=lambda p: math.atan2(p[1] - cy, p[0] - cx))


def _alive_runs(px, erased):
    """像素序列 → 连续存活段（跳过已被裁掉的像素）。

    同一个图形上做第二次裁剪时，边界上留着上一轮挖掉的缺口；判定必须
    沿存活的连续段走，不能把缺口也当成一条完整边（否则紫色工作线段会
    横穿已经不存在的部分，用户看到的判定轨迹是假的）。
    """
    runs = []
    cur = []
    for p in px:
        if p in erased:
            if cur:
                runs.append(cur)
                cur = []
            continue
        cur.append(p)
    if cur:
        runs.append(cur)
    return runs


def _outline_points(shape):
    """任意图元 → 轮廓折线顶点（圆/椭圆取真实栅格轮廓像素）。"""
    from core.shapes import CircleShape, EllipseShape, LineShape, PolygonShape
    if isinstance(shape, LineShape):
        return [tuple(shape.p0), tuple(shape.p1)]
    if isinstance(shape, (CircleShape, EllipseShape)):
        return _outline_pixels_sorted(shape)
    if isinstance(shape, PolygonShape):
        return [(int(x), int(y)) for x, y in shape.vertices]
    return []


class _ClipDemoBase:
    """参数卡基类：标签 + 整数微调框网格（与模块二演示页同构）。"""

    title = "裁剪"
    icon = "fit"
    kind = "canvas"
    freehand_replay = False
    supports_hover = False      # True = 鼠标悬停时显示分区标签（Cohen 页）
    # 替换式渲染：每帧只显示"当前裁剪结果"，不累积历史线段——
    # 否则前面步骤留下的整段线会留到最后，末帧不再是算法输出
    trails = False
    variables = {}
    formula = ""
    algo = ALGO_COHEN

    def __init__(self):
        self._spins = {}
        self._canvas = None
        self._tool = None
        self._dirty = False       # 画布拖出/调整窗口 → 步骤流需重生成
        self._pinned_source = None  # 上次生成步骤流用的画布图元

    # ---- 子类声明：[(键, 中文标签, 默认, 最小, 最大), ...] ----
    def _defs(self):
        return []

    def build_params(self, lay: QVBoxLayout):
        self._spins = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        for i, (key, cn, dft, mn, mx) in enumerate(self._defs()):
            lab = QLabel(cn)
            lab.setObjectName("secondary")
            lab.setMinimumWidth(52)
            sb = QSpinBox()
            sb.setRange(mn, mx)
            sb.setValue(dft)
            sb.setFixedWidth(92)
            grid.addWidget(lab, i, 0)
            grid.addWidget(sb, i, 1)
            grid.setColumnStretch(2, 1)
            self._spins[key] = sb
        lay.addLayout(grid)

    def collect(self) -> dict:
        if self._spins:
            return {k: sb.value() for k, sb in self._spins.items()}
        return {k: dft for k, _cn, dft, _mn, _mx in self._defs()}

    def window_rect(self):
        """参数卡里的窗口矩形（闭区间，已按左上/右下规范成序）。

        演示动画与播完的裁剪必须用同一个窗口——否则动画按参数卡演、
        挖除按画布红框走，结果会错位。
        """
        p = self.collect()
        return (min(p["wx0"], p["wx1"]), min(p["wy0"], p["wy1"]),
                max(p["wx0"], p["wx1"]), max(p["wy0"], p["wy1"]))

    def all_pixels(self, rect, src=None):
        """当前演示对象的全部像素（轮廓 + 填充）。"""
        from core.rasterizer import rasterize
        if src is None:
            src = self._pinned_source if self._pinned_source is not None \
                else self.playback_source()
        if src is None:
            return set()
        outline, fill = rasterize(src)
        return {(int(x), int(y)) for x, y in list(outline) + list(fill)}

    def kept_pixels(self, rect, src=None):
        """窗口【外】保留下来的图元像素（动画末帧与播完真实裁剪的唯一口径）。

        本模块的"区域裁剪"= 裁去窗口内、保留窗口外（与 ClipTool 面板
        "挖除窗口内"一致），所以末帧必须落在窗口外，不能在窗口内。
        轮廓 + 填充一起取：播完画布裁剪（ClipTool.apply_crop）擦的是
        "轮廓∪填充 中窗口内的像素"，填充留在窗口外的部分必须一起保留——
        否则末帧只剩一圈线，播完填充突然冒出来，和"演完即所得"对不上。
        也不能用"裁剪后端点重画一条线段"：缓坡长线逐列 y 会偏，实证末帧
        与画布结果差 16 个像素，播完那一瞬画面会跳（用户反馈）。
        """
        x0, y0, x1, y1 = rect
        return sorted({p for p in self.all_pixels(rect, src)
                       if not (x0 <= p[0] <= x1 and y0 <= p[1] <= y1)})

    def cut_pixels(self, rect, src=None):
        """窗口【内】将被裁掉的像素（轮廓 + 填充）——橙色参照层。"""
        x0, y0, x1, y1 = rect
        return {p for p in self.all_pixels(rect, src)
                if x0 <= p[0] <= x1 and y0 <= p[1] <= y1}

    def kept_fill_pixels(self, rect):
        """窗口【外】的填充像素：动画每一步都常显（这部分不会被裁掉）。

        必须扣掉轮廓像素：span/scanline 填充的两端就落在轮廓上，
        不扣除会把轮廓一起染成淡色，"边框/填充"又分不开了。
        """
        from core.rasterizer import rasterize
        src = self._pinned_source if self._pinned_source is not None \
            else self.playback_source()
        if src is None:
            return set()
        outline, fill = rasterize(src)
        edge = {(int(x), int(y)) for x, y in outline}
        x0, y0, x1, y1 = rect
        return {(int(x), int(y)) for x, y in fill
                if (int(x), int(y)) not in edge
                and not (x0 <= x <= x1 and y0 <= y <= y1)}

    # ---- 演示对象 = 画布图元（选中优先 / 最后画的），不再内置示例 ----
    subject_kind = "any"           # any = 任意图元；closed = 只要封闭图形

    def subject_shapes(self):
        """画布上可作裁剪对象的图元（可见、且类型匹配当前页）。

        直线页接受任意图元：圆/椭圆会在 make_steps 里离散成折线；
        多边形页只接受封闭图形（多边形/圆/椭圆），直线没有可裁剪的面。
        """
        from core.shapes import CircleShape, EllipseShape, LineShape, PolygonShape
        cv = self._canvas
        if cv is None:
            return []
        if self.subject_kind == "closed":
            kinds = (PolygonShape, CircleShape, EllipseShape)
        else:
            kinds = (LineShape, PolygonShape, CircleShape, EllipseShape)
        return [s for s in getattr(cv, "shapes", [])
                if getattr(s, "visible", True) and isinstance(s, kinds)]

    def playback_source(self):
        """当前裁剪对象：选中优先，其次上次生成用的，最后画布最后一个。"""
        shapes = self.subject_shapes()
        if not shapes:
            return None
        sel = getattr(self._canvas, "_selected_shape", None)
        if sel is not None and any(sel is s for s in shapes):
            return sel
        if self._pinned_source is not None and \
                any(self._pinned_source is s for s in shapes):
            return self._pinned_source
        return shapes[-1]

    @property
    def empty_hint(self):
        if self.playback_source() is not None:
            return ""
        if self.subject_kind == "closed":
            return ("画布上没有封闭图形：先画多边形、圆或椭圆，"
                    "播放即演示它的裁剪")
        return ("画布上没有图元：先画直线、圆、椭圆或多边形，"
                "播放即演示它的裁剪")

    def cut_fill_pixels(self, rect):
        """窗口【内】的填充像素（轮廓除外）——随轮廓一起被挖除。

        真实裁剪擦掉的是"轮廓∪填充"中落在窗口内的部分；轮廓被挖穿时，
        窗口内被轮廓围住的填充也一并消失（否则填满的图元会在窗口里
        留下一个洞，与画布真实裁剪对不上）。
        """
        from core.rasterizer import rasterize
        src = self._pinned_source if self._pinned_source is not None \
            else self.playback_source()
        if src is None:
            return set()
        outline, fill = rasterize(src)
        edge = {(int(x), int(y)) for x, y in outline}
        x0, y0, x1, y1 = rect
        return {(int(x), int(y)) for x, y in fill
                if (int(x), int(y)) not in edge
                and x0 <= x <= x1 and y0 <= y <= y1}

    # ---- 页面联动：选中本页即切到裁剪工具 ----
    def tool_selector(self, canvas):
        """演示画布上的裁剪工具：拖窗口 → 回填右侧窗口参数 → 播放。

        复用已在场的 ClipTool（重生成/改参数不能把用户拖好的窗口弄丢），
        只把它切到"演示模式"：叠层照常画红窗，回车真实挖除（可撤销），
        播放只演示算法原理，不改动画布。
        """
        from modules.module04_clipping.tools import ClipTool
        canvas.set_algorithm(self.algo)
        tool = getattr(canvas, "tool", None)
        if not isinstance(tool, ClipTool):
            tool = ClipTool(canvas)
            canvas.set_tool(tool)
        tool.preview_only = True
        tool.window_changed = self._on_canvas_window
        self._canvas = canvas
        self._tool = tool

    def _on_canvas_window(self, rect):
        """画布拖出的矩形窗口 → 静默回填参数卡（不触发防抖自动播放）。"""
        x0, y0, x1, y1 = rect
        for key, val in (("wx0", x0), ("wy0", y0),
                         ("wx1", x1), ("wy1", y1)):
            sb = self._spins.get(key)
            if sb is None:
                continue
            sb.blockSignals(True)
            sb.setValue(max(sb.minimum(), min(sb.maximum(), int(val))))
            sb.blockSignals(False)
        self._dirty = True

    def consume_dirty(self) -> bool:
        """演示壳在播放前询问：画布窗口改过 → 需按新参数重生成步骤流。"""
        dirty = self._dirty
        self._dirty = False
        return dirty

    def reference_pixels(self):
        """被窗口裁掉的部分（橙色参照层）；子类实现具体形状。"""
        return []


# =====================================================================
# 线段裁剪两页：参数只差算法
# =====================================================================
class _LineClipDemo(_ClipDemoBase):
    # 子类用具体裁剪函数做"被裁部分"参照（与步骤流同源）
    _clip_fn = None

    # 圆/椭圆：每段包含多少个轮廓像素。太小（1~2 px）→ 每段一步就收敛，
    # 看不出求交/二分/参数收窄，三页看起来几乎一样；太大 → 一段横跨
    # 大半个图形，看不出是"沿边界一段段走"。5~6 像素两头都占。
    _PIECE_LEN = 6

    def reference_pixels(self):
        """窗口内的图元像素（橙色参照层 = 将被裁掉的部分）。

        取 rasterize 全部像素（轮廓 + 填充）− kept_pixels(窗口外)。
        旧写法"原图 − 各段裁剪后线段"有个致命问题：填充像素压根不在
        裁剪线段里，填充图形会整片进参照层——窗口外被染成橙色"将被删除"
        的样子，看起来就是删除/保留区域对调（用户反馈）。参照层必须
        严格落在窗口内（这块是要被裁掉的）。
        """
        src = self.playback_source()
        if src is None:
            return []
        return sorted(self.cut_pixels(self._rect(self.collect()), src))

    def _defs(self):
        return [("wx0", "窗口左", 20, -20, 120), ("wy0", "窗口上", 12, -20, 80),
                ("wx1", "窗口右", 44, -20, 120), ("wy1", "窗口下", 30, -20, 80)]

    def _rect(self, p):
        return (min(p["wx0"], p["wx1"]), min(p["wy0"], p["wy1"]),
                max(p["wx0"], p["wx1"]), max(p["wy0"], p["wy1"]))

    def kept_fill_pixels(self, rect):
        """窗口外的填充像素：线段本身没有填充区，但封闭图形有。

        不能像早期版本那样直接返回空集：裁剪挖除的是"轮廓∪填充"，
        填充满格图元时窗口内的填充像素同样会被删掉——末帧若不画它们，
        播完画布裁剪那一瞬填充会突然冒出来（"演完即所得"对不上）。
        基类实现按 rasterize 的 fill 取，线段图元自然返回空集。
        """
        return super().kept_fill_pixels(rect)

    @staticmethod
    def _seg_ends(px, a, b):
        """当前工作线段像素 → 沿弦方向的两端（用于紫色"当前线段"注记）。"""
        dx, dy = b[0] - a[0], b[1] - a[1]

        def key(p):
            return (p[0] - a[0]) * dx + (p[1] - a[1]) * dy

        return min(px, key=key), max(px, key=key)

    def _segments(self):
        """演示对象 → 沿图形边界【逐段遍历】的待裁剪线段。

        返回 [(起点, 终点, 本段拥有的轮廓像素), ...]：
          · 直线   → 它本身（1 段，完整看一次判定过程）；
          · 多边形 → 各条边（顶点 i → i+1）。逐边 Bresenham 的像素与
            rasterize 的多边形轮廓完全一致 ⇒ 判定轨迹与原图逐像素重合
            （用户反馈："画出来的轨迹和原来的轨迹不一样，像是两种画法"）；
          · 圆/椭圆 → 取图元真实栅格轮廓像素，按绕中心极角排成有序点列，
            每 _PIECE_LEN 个相邻像素切一段（段首尾连成直线）：轨迹贴着
            原轮廓（不用参数方程重采样——那是另一套像素，两种画法会脱节），
            每段又有几像素长——跨窗口边时能看清求交 / 二分 / 参数收窄
            （1~2 像素的微段每段一步就收敛，三页看起来几乎一样，用户反馈）。

        已被裁掉的像素（shape.erased）不参与：同一个图形上做第二次裁剪时，
        判定要沿【剩下的】边界走，不能跨过上一轮挖空的缺口——否则紫色
        工作线段会横穿已经不存在的部分，判定轨迹就成了假的。
        """
        from algorithms.line_bresenham import bresenham_line
        from core.shapes import LineShape, PolygonShape
        src = self.playback_source()
        if src is None:
            return []
        erased = set(getattr(src, "erased", None) or ())
        if isinstance(src, LineShape):
            a = (int(src.p0[0]), int(src.p0[1]))
            b = (int(src.p1[0]), int(src.p1[1]))
            px = [(int(x), int(y))
                  for x, y in bresenham_line(a[0], a[1], b[0], b[1])]
            return [(run[0], run[-1], set(run))
                    for run in _alive_runs(px, erased)]
        if isinstance(src, PolygonShape):
            pts = [(int(x), int(y)) for x, y in src.vertices]
            out = []
            for i in range(len(pts)):
                a = pts[i]
                b = pts[(i + 1) % len(pts)]
                if a == b:
                    continue
                px = [(int(x), int(y))
                      for x, y in bresenham_line(a[0], a[1], b[0], b[1])]
                for run in _alive_runs(px, erased):
                    out.append((run[0], run[-1], set(run)))
            return out
        # 圆 / 椭圆：真实栅格轮廓 → 极角有序点列 → 每 N 个切一段
        full = _outline_pixels_sorted(src, ignore_erased=True)
        out = []
        step = max(2, self._PIECE_LEN)
        for run in _alive_runs(full, erased):
            i = 0
            while i < len(run):
                j = min(i + step, len(run))      # 本段覆盖 run[i .. j-1]
                a, b = run[i], run[j - 1]
                if a != b:
                    owned = {(int(x), int(y)) for x, y in run[i:j]}
                    out.append((a, b, owned))
                i = j
        return out

    def _prelude_steps(self, a, b, rect, multi=False, full_px=None):
        """判定动画的铺垫步骤（区域划分/端点判定等）；子类按需覆盖。

        a, b = 第一段的两个端点；multi = 逐段遍历（端点编码交给各段
        自己的步骤，逐段遍历时先前的端点标签会叠在一起）；
        full_px = 完整图形像素（铺垫步在它上面叠加注记）。铺垫只加一次。
        """
        return []

    def make_steps(self, params):
        """步骤流：沿图形边界逐段走，每段跑一遍本页算法并当场判定。

        画面语义（固定三色，全模块统一）：
          蓝 = 还没被判定挖除的图元像素（窗口外最终留下的就是它）；
          橙 = 窗口内将被挖除的部分（reference_pixels 橙色参照层，
                随判定逐段露出来）；
          紫线 = 算法当前正在判定的那一段（本轮的工作线段）。
        每段判定完成的瞬间，落在窗口内的像素被挖掉——动画就是在原图
        基础上一步步裁掉窗口内的部分（用户反馈：要在原图基础上修改）。
        末帧 = 画布真实裁剪结果（"演完即所得"，播完那一瞬不跳变）。
        """
        self._pinned_source = self.playback_source()
        pieces = self._segments()
        if not pieces:
            return []
        rect = self._rect(params)
        total = len(pieces)
        multi = total > 1
        x0, y0, x1, y1 = rect

        def inside(p):
            """窗口内？（与 ClipTool.apply_crop 的闭区间判定一致）"""
            return x0 <= p[0] <= x1 and y0 <= p[1] <= y1

        # 起始状态 = 图元真实像素（轮廓 + 填充）
        current = set(self.all_pixels(rect))
        # tint = 【全部】填充像素（轮廓除外），窗口内窗口外都算：
        # 之前只取窗口外的填充，窗口内的填充就落进了"主色"组，
        # 和轮廓画成同一个颜色 —— 整块图元一片蓝，边框根本分不出来
        # （用户反馈："边框和填充弄成一个颜色了，展示不出来"）。
        # 判定挖除时再把窗口内那部分一起从 current / fill_now 里扣掉。
        fill_in = self.cut_fill_pixels(rect)                  # 窗口内填充（待挖除）
        fill_now = set(self.kept_fill_pixels(rect)) | fill_in  # 全部填充像素（淡色）

        from algorithms.steps import (GUIDE_MOVE, Step, line_guide, rect_guide)
        steps = []

        # ---- 铺垫：9 区划分 / 边界说明，只讲一次 ----
        first_a, first_b, _owned = pieces[0]
        prelude = self._prelude_steps(first_a, first_b, rect, multi,
                                      set(self.all_pixels(rect)))
        for st in prelude:
            st.guides = list(st.guides) + [
                line_guide(first_a, first_b, GUIDE_MOVE, dash=True, width=2.6)]
            st.pixels = sorted(current)
            st.tint = sorted(fill_now)
            steps.append(st)

        # ---- 逐段遍历：每段跑一遍本页算法，判定完就挖掉窗口内部分 ----
        for i, (a, b, owned) in enumerate(pieces):
            part = self._steps(a[0], a[1], b[0], b[1], rect)
            if not part:
                continue
            cut = {p for p in owned if inside(p)}
            for k, st in enumerate(part):
                cur = sorted({(int(p[0]), int(p[1])) for p in st.pixels})
                if len(cur) >= 2:
                    lo, hi = self._seg_ends(cur, a, b)
                    # 虚线而非实线：当前线段与原轮廓共线，实线会把底下
                    # "橙色=待挖除"整段盖掉；虚线能让两层同时可辨。
                    st.guides = list(st.guides) + [
                        line_guide(lo, hi, GUIDE_MOVE, dash=True, width=2.6)]
                if k == len(part) - 1 and cut:
                    # 本段判定完成 → 落在窗口内的部分被挖除；
                    # 窗口内被轮廓围住的填充也随之消失（否则填满的
                    # 图元会在窗口里留下一个洞，与画布真实裁剪对不上）
                    current -= cut
                    current -= fill_in
                    fill_now -= fill_in
                st.pixels = sorted(current)
                st.tint = sorted(fill_now)
                if multi:
                    st.note = f"第 {i + 1}/{total} 段 · {st.note}"
                if k == len(part) - 1:
                    if len(cut) == len(owned):
                        st.note += "（整段在窗口内，已挖除）"
                    elif cut:
                        st.note += "（段内落在窗口的部分已挖除）"
                    else:
                        st.note += "（本段在窗口外，保留）"
                if multi:
                    st.values = {**st.values, "段": f"{i + 1}/{total}"}
            steps.extend(part)

        # ---- 末帧 = 画布真实裁剪结果（窗口外保留） ----
        # 无论上一帧像素是否已相同都补一帧"完成"：算法末步仍带着
        # 紫色"当前线段"注记，不补的话定格画面会残留一条线，
        # 看着像窗口内那段没被裁掉。
        current -= fill_in
        fill_now -= fill_in
        vals = dict(steps[-1].values) if steps else {}
        vals["判定"] = "完成"
        steps.append(Step(
            sorted(current), vals,
            "裁剪完成：窗口内部分已挖除，只保留窗口外",
            guides=[rect_guide(rect)], tint=sorted(fill_now)))
        return steps


class CohenDemo(_LineClipDemo):
    title = "编码裁剪（Cohen-Sutherland）"
    icon = "fit"
    algo = ALGO_COHEN
    variables = {"区域码0": "起点码", "区域码1": "终点码",
                 "与 / 或": "与 / 或",
                 "判定": "判定", "使用边界": "本轮用的窗口边",
                 "端点0": "起点", "端点1": "终点",
                 "交点": "新交点"}
    # 判定过程要逐帧盯着看：每一步都在算求交 / 二分 / 参数收窄，
    # 2 步/秒仍嫌快（用户反馈："在最低速度下感觉都比较快"）→ 默认 1 步/秒；
    # 速度滑杆还能继续调慢到 0.1 步/秒（一步 10 秒）
    default_fps = 1
    formula = ("Cohen-Sutherland 编码裁剪\n"
               "区域码 4 位 D3 D2 D1 D0\n"
               "  D3 下 1000    D2 上 0100\n"
               "  D1 右 0010    D0 左 0001\n"
               "与 = code0 & code1，或 = code0 | code1\n"
               "① 或 = 0000 → 接受\n"
               "② 与 ≠ 0000 → 舍弃\n"
               "③ 否则取外端点求交，清 1 位重判\n"
               "每轮至少清 1 位，最多 4 轮")

    def _steps(self, *args):
        return cohen_sutherland_steps(*args)

    _clip_fn = staticmethod(cohen_sutherland)

    def _prelude_steps(self, a, b, rect, multi=False, full_px=None):
        """判定铺垫：① 窗口四边延长成 9 区逐区标码；②③ 端点逐个判区编码。

        逐段遍历（multi）时只做区域划分：端点编码交给各段自己的步骤——
        对"第一段"预先编码既与窗口无关，相邻端点的标签还会叠在一起。
        铺垫步像素 = 完整图形：动画从原图出发，在它上面叠加判定注记。
        """
        import math
        from algorithms.line_bresenham import bresenham_line
        from algorithms.steps import (GUIDE_MARK, Step, boundary_guide,
                                      border_extension_segments, label_guide,
                                      point_guide, rect_guide)
        rx0, ry0, rx1, ry1 = rect
        ox1, oy1 = rx1 + 1, ry1 + 1          # 闭区间 → 连续外边界
        m = 5                                 # 区域展示向窗口外扩的格数
        bx0, by0, bx1, by1 = rx0 - m, ry0 - m, ox1 + m, oy1 + m
        xs = (bx0, rx0, ox1, bx1)
        ys = (by0, ry0, oy1, by1)
        frame = rect_guide(rect)
        # 四条边向外延长成 9 区：只画窗口外侧的延长段——整条边界线与
        # 红色窗口框重合，画满会把红框染成灰色（用户反馈"边界颜色全变了"）
        guides = [frame, *[boundary_guide(a, b)
                           for _n, a, b in
                           border_extension_segments(rect, ext=m)]]
        for j in range(3):
            for i in range(3):
                # 区域中心格（与悬停分区同一套闭区间采样）
                cx = int(math.floor(0.5 * (xs[i] + xs[i + 1])))
                cy = int(math.floor(0.5 * (ys[j] + ys[j + 1])))
                code = region_code(cx, cy, rect)
                text = f"{code:04b} {REGION_CN.get(code, '')}".strip()
                # 居中在区域里（旧写法按字宽估算回退半格，实际会偏）
                guides.append(label_guide((cx, cy), text,
                                          align="center", valign="middle"))
        dash = {"区域码0": "—", "区域码1": "—", "与 / 或": "—",
                "端点0": "—", "端点1": "—", "交点": "—"}
        steps = [Step(sorted(full_px or []), {**dash, "判定": "区域划分"},
                      "窗口四条边向外延长 → 平面分成 9 个区域，"
                      "每区一个 4 位区域码（D3D2D1D0 = 下上右左）",
                      guides=guides)]
        if multi:
            return steps
        seg_px = sorted(set(bresenham_line(a[0], a[1], b[0], b[1])))
        marks = []
        for tag, p, kc, ke in (("起点", a, "区域码0", "端点0"),
                               ("终点", b, "区域码1", "端点1")):
            code = region_code(p[0], p[1], rect)
            marks.append(point_guide(p, f"{tag} {code:04b}", GUIDE_MARK))
            steps.append(Step(
                list(seg_px),
                {**dash, kc: code_text(code), ke: tuple(p),
                 "判定": f"{tag}编码"},
                f"判断{tag} {tuple(p)} 落在哪个区域 → "
                f"「{REGION_CN.get(code, '')}」区，区域码 {code:04b}",
                guides=[frame, *marks]))
        return steps

    # ---- 鼠标悬停：窗口四边延长 → 9 个区域各标一个二进制码 ----
    supports_hover = True

    def hover_guides(self, x, y, canvas):
        """按当前窗口把可见画布划成 9 个区域，每区标出 4 位区域码。

        优先读 ClipTool.rect（用户刚拖好的红框，实时更新）；
        未拖窗口时返回空——默认参数值只是占位，还没意义。
        码序与监视器一致（D3 D2 D1 D0 = 下 上 右 左）。
        """
        from core.shapes import SIM
        import math
        tool = getattr(self, "_tool", None)
        if tool is None or tool.rect is None:
            return []
        rect = tuple(tool.rect)
        rx0, ry0, rx1, ry1 = rect
        sr = canvas.mapToScene(canvas.viewport().rect()).boundingRect()
        bx0, by0 = sr.left() / SIM, sr.top() / SIM
        bx1, by1 = sr.right() / SIM, sr.bottom() / SIM
        # rect 是"闭区间"（x0..x1 这些格子都算在窗口内），和 ClipTool 画红框
        # 用的 (rx1-rx0+1)*SIM 一致；所以连续坐标的外边界是 rx1+1 / ry1+1。
        ox1, oy1 = rx1 + 1, ry1 + 1
        # 窗口必须完整落在分区里，四边至少留 3 格放标签
        bx0 = min(bx0, rx0 - 3)
        bx1 = max(bx1, ox1 + 3)
        by0 = min(by0, ry0 - 3)
        by1 = max(by1, oy1 + 3)
        xs = (bx0, rx0, ox1, bx1)
        ys = (by0, ry0, oy1, by1)
        # 鼠标连续坐标 → 格子下标（floor），再按闭区间判区域码；
        # 否则鼠标落在最后一列格子里会被误判成"右边"
        hot = region_code(int(math.floor(x)), int(math.floor(y)), rect)
        out = [
            # 窗口四条边向外延长 → 把平面分成 9 个区域。
            # 只画窗口外侧的两截：整条线会盖住红色窗口框，鼠标一动
            # 边框就像"换了颜色"（用户反馈）
            {"kind": "line", "xy": ((rx0, by0), (rx0, ry0))},
            {"kind": "line", "xy": ((rx0, oy1), (rx0, by1))},
            {"kind": "line", "xy": ((ox1, by0), (ox1, ry0))},
            {"kind": "line", "xy": ((ox1, oy1), (ox1, by1))},
            {"kind": "line", "xy": ((bx0, ry0), (rx0, ry0))},
            {"kind": "line", "xy": ((ox1, ry0), (bx1, ry0))},
            {"kind": "line", "xy": ((bx0, oy1), (rx0, oy1))},
            {"kind": "line", "xy": ((ox1, oy1), (bx1, oy1))},
        ]
        for j in range(3):
            for i in range(3):
                # 采样点取该区域中间的格子（整数格心），与闭区间语义对齐
                cx = int(math.floor(0.5 * (xs[i] + xs[i + 1])))
                cy = int(math.floor(0.5 * (ys[j] + ys[j + 1])))
                code = region_code(cx, cy, rect)
                on = code == hot
                text = f"{code:04b} {REGION_CN.get(code, '')}".strip()
                # 窄条区域自动缩字号，避免文字超出分区
                w = (xs[i + 1] - xs[i]) * SIM
                h = (ys[j + 1] - ys[j]) * SIM
                size = max(10, int(min(SIM * 0.68, h * 0.5,
                                      w / (max(1, len(text)) * 0.72))))
                out.append({
                    "kind": "zone",
                    "xy": (xs[i], ys[j], xs[i + 1], ys[j + 1]),
                    "text": text,
                    "size": size,
                    # 不描分区边框：贴窗口的分区边与红框重合，蓝边会把
                    # 红框染蓝。用加浓的底色表示"鼠标所在区域"即可
                    "border": False,
                    "color": "#4F6EF7",
                    "fill": "#4F6EF7" if on else None,
                    "fill_alpha": 40,
                    "text_color": "#2B4BD6" if on else "#8A919F",
                    "bold": on,
                })
        return out


class MidpointDemo(CohenDemo):
    """中点分割裁剪：与 Cohen 共用区域码铺垫与 9 区悬停注记，
    区别在判定方式——不求交点解析式，对窗口外端点反复二分。"""

    title = "中点分割裁剪（Midpoint Subdivision）"
    algo = ALGO_MIDPOINT
    variables = {"区域码0": "起点码", "区域码1": "终点码",
                 "与 / 或": "与 / 或", "判定": "判定",
                 "端点0": "起点", "端点1": "终点",
                 "中点": "中点 M", "中点码": "M 区域码",
                 "区间": "区间长度", "轮次": "二分轮次",
                 "当前": "当前在求哪端"}
    formula = ("中点分割裁剪（Midpoint Subdivision）\n"
               "区域码判定与 Cohen 相同：\n"
               "  或 = 0000 → 接受；与 ≠ 0000 → 舍弃\n"
               "否则不求交点，对窗口外端点二分：\n"
               "  取中点 M，算 M 的区域码\n"
               "  M 与外端点同侧 → 外端点移到 M\n"
               "  否则           → 内端点移到 M\n"
               "区间 ≤ 1 像素即达显示分辨率精度\n"
               "只有移位/加减（÷2），无乘除法，适合硬件实现")

    def _steps(self, *args):
        return midpoint_clip_steps(*args)

    _clip_fn = staticmethod(midpoint_clip)


class LiangDemo(_LineClipDemo):
    title = "参数裁剪（Liang-Barsky）"
    icon = "fit"
    algo = ALGO_LIANG
    variables = {"阶段": "阶段", "边界": "当前边界",
                 "p": "p", "q": "q", "u0": "u0", "u1": "u1"}
    # 判定过程要逐帧盯着看：每一步都在算求交 / 二分 / 参数收窄，
    # 2 步/秒仍嫌快（用户反馈："在最低速度下感觉都比较快"）→ 默认 1 步/秒；
    # 速度滑杆还能继续调慢到 0.1 步/秒（一步 10 秒）
    default_fps = 1
    formula = ("Liang-Barsky 参数裁剪\n"
               "P(t) = P0 + t·d，t ∈ [0, 1]\n"
               "四条边界依次判 p·t ≤ q：\n"
               "  p = -dx, dx, -dy, dy\n"
               "  q = x0-rx0, rx1-x0, y0-ry0, ry1-y0\n"
               "p < 0 → u0 = max(u0, q/p)\n"
               "p > 0 → u1 = min(u1, q/p)\n"
               "p = 0 且 q < 0 → 平行在外，舍弃\n"
               "u0 > u1 → 舍弃")

    def _steps(self, *args):
        return liang_barsky_steps(*args)

    _clip_fn = staticmethod(liang_barsky)

    def _prelude_steps(self, a, b, rect, multi=False, full_px=None):
        """判定铺垫：标出四条边界与初始参数区间，再逐边界判 p·t ≤ q。"""
        from algorithms.line_bresenham import bresenham_line
        from algorithms.steps import Step, label_guide, rect_guide
        rx0, ry0, rx1, ry1 = rect
        seg_px = sorted(full_px) if full_px else sorted(
            set(bresenham_line(a[0], a[1], b[0], b[1])))
        mx, my = (rx0 + rx1) // 2, (ry0 + ry1) // 2
        # 边界名贴在窗口外侧、并与边界线对齐（旧的锚点会压进窗口里）
        guides = [rect_guide(rect),
                  label_guide((rx0 - 1, my), "左边界",
                              align="right", valign="middle"),
                  label_guide((rx1 + 1, my), "右边界",
                              align="left", valign="middle"),
                  label_guide((mx, ry0 - 1), "上边界",
                              align="center", valign="above"),
                  label_guide((mx, ry1 + 1), "下边界",
                              align="center", valign="below")]
        return [Step(seg_px,
                     {"阶段": "边界划分", "边界": "—", "p": "—", "q": "—",
                      "u0": "0.000", "u1": "1.000"},
                     "线段参数化 P(t) = P0 + t·d，t ∈ [0,1]；"
                     "接下来对四条边界逐个判 p·t ≤ q，收窄参数区间",
                     guides=guides)]


# =====================================================================
# 多边形裁剪
# =====================================================================
class PolygonClipDemo(_ClipDemoBase):
    title = "多边形裁剪（Sutherland-Hodgman）"
    icon = "polygon"
    algo = ALGO_HODGMAN
    subject_kind = "closed"       # 演示对象 = 画布上选中/最后画的封闭图形
    # 判定过程要逐帧盯着看：每一步都在算求交 / 二分 / 参数收窄，
    # 2 步/秒仍嫌快（用户反馈："在最低速度下感觉都比较快"）→ 默认 1 步/秒；
    # 速度滑杆还能继续调慢到 0.1 步/秒（一步 10 秒）
    default_fps = 1
    variables = {"阶段": "当前边", "轮次": "第几轮", "边界": "本轮用的边",
                 "输入顶点": "输入", "输出顶点": "输出",
                 "新增交点": "新交点", "情形": "S→E 情形",
                 "内→内": "内→内", "内→外": "内→外",
                 "外→内": "外→内", "外→外": "外→外"}
    formula = ("Sutherland-Hodgman 逐边裁剪\n"
               "左 → 右 → 上 → 下，逐条半平面切分\n"
               "对每条边遍历 S→E：\n"
               "  E 内 S 内 → 留 E\n"
               "  E 内 S 外 → 交点 + E\n"
               "  E 外 S 内 → 交点\n"
               "  E 外 S 外 → 无\n"
               "四轮后即窗口内多边形")

    def _defs(self):
        return [("wx0", "窗口左", 16, -20, 120), ("wy0", "窗口上", 12, -20, 80),
                ("wx1", "窗口右", 46, -20, 120), ("wy1", "窗口下", 34, -20, 80)]

    def _vertices(self):
        """演示多边形 = 画布图元的轮廓顶点；圆/椭圆先离散成折线。

        没有对象（或只剩一条直线，凑不出面）时不生成任何示例。

        圆/椭圆按极角排出的栅格轮廓有上百个点，逐个 S→E 判定要跑
        4 轮 × 上百步（几分钟才播完，过程根本看不清）。超过 12 个点时
        等间隔抽稀成 12 边形——仍贴着原轮廓，S-H 的"逐边遍历"才看得清。
        """
        src = self.playback_source()
        if src is None:
            return None
        verts = _outline_points(src)
        if len(verts) > 12:
            step = max(1, len(verts) // 12)
            verts = verts[::step][:12]
        return verts if len(verts) >= 3 else None

    def make_steps(self, params):
        self._pinned_source = self.playback_source()
        verts = self._vertices()
        if verts is None:
            return []
        rect = (min(params["wx0"], params["wx1"]),
                min(params["wy0"], params["wy1"]),
                max(params["wx0"], params["wx1"]),
                max(params["wy0"], params["wy1"]))
        steps = clip_polygon_steps(verts, rect)
        # 「区域裁剪」= 裁去窗口内、保留窗口外。固定颜色语义（方案 A）：
        #   蓝 = 窗口外保留部分（每帧常显，不参与动画）；
        #   橙 = 窗口内待挖除部分（reference_pixels 橙色参照层）；
        #   青色虚线框 = 算法当前结果多边形（guides，逐顶点生长）；
        #   紫线 = 当前处理的 S→E 那条边。
        # 旧写法把中间结果 pixels 与"原图像素"求交，沿窗口边界新生成的
        # 边、收缩后的多边形全部被过滤掉——40 多帧画面几乎一动不动。
        # 现在中间多边形走 guides，不再受原图像素约束。
        if steps:
            from algorithms.steps import Step, rect_guide
            outside = set(self.kept_pixels(rect))
            fill_list = sorted(self.kept_fill_pixels(rect))
            for st in steps[:-1]:
                st.pixels = sorted(outside)
                st.tint = fill_list
            first = steps[0]
            first.note = (first.note
                          + "（蓝=保留 · 橙=待挖除 · 虚线框=当前结果多边形）")
            last = steps[-1]
            steps[-1] = Step(
                sorted(outside), dict(last.values),
                "算法输出 = 窗口内这个多边形；区域裁剪把它挖除 → "
                "只保留窗口外（橙色待挖除部分消失）",
                guides=[rect_guide(rect)], tint=fill_list)
        return steps

    def reference_pixels(self):
        """窗口内的图元像素（橙色参照层 = 将被裁掉的部分）。

        与线段页同一口径：rasterize 全部像素 − kept_pixels(窗口外)，
        保证橙色严格落在窗口内，不会把窗口外的保留部分染成"将被删除"。
        """
        src = self.playback_source()
        if src is None:
            return []
        p = self.collect()
        rect = (min(p["wx0"], p["wx1"]), min(p["wy0"], p["wy1"]),
                max(p["wx0"], p["wx1"]), max(p["wy0"], p["wy1"]))
        return sorted(self.cut_pixels(rect, src))


# =====================================================================
def create_demos():
    return [CohenDemo(), MidpointDemo(), LiangDemo(), PolygonClipDemo()]
