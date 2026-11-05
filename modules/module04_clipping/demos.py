# -*- coding: utf-8 -*-
"""
=====================================================================
 modules/module04_clipping/demos.py — 模块四演示页（区域裁剪）
=====================================================================
三页：Cohen-Sutherland / Liang-Barsky / Sutherland-Hodgman。
每页 = 参数卡（窗口四边）+ 公式卡 + 决策项监视 + 播放控制，
步骤流来自 algorithms/* 的 *_steps()（与真实裁剪函数共用同一套判定）。

演示对象 = 画布上选中（或最后画的）图元：
  · 直线 → 一条线段；
  · 多边形 → 各条边；
  · 圆 / 椭圆 → 按 TESS_SEGMENTS 段离散成折线再裁剪
    （与真实图形系统"曲线先离散成折线再裁剪"的做法一致）。
画布上没有可用图元时只提示，不生成任何内置示例。
演示页不对画布手绘图元做回放（freehand_replay=False）。
=====================================================================
"""

from PySide6.QtWidgets import QGridLayout, QLabel, QSpinBox, QVBoxLayout

from algorithms.cohen_sutherland import cohen_sutherland, cohen_sutherland_steps
from algorithms.liang_barsky import liang_barsky, liang_barsky_steps
from algorithms.sutherland_hodgman import (clip_polygon, clip_polygon_steps,
                                           polygon_outline)

ALGO_COHEN = "cohen_sutherland"
ALGO_LIANG = "liang_barsky"
ALGO_HODGMAN = "sutherland_hodgman"

TESS_SEGMENTS = 32          # 圆/椭圆 → 折线的离散段数


def _ellipse_polygon(cx, cy, rx, ry, angle, n=TESS_SEGMENTS):
    """圆/椭圆 → 闭合折线顶点（纯整数像素坐标）。

    曲线无法直接送进线段/多边形裁剪算法，先按角度均匀离散成折线——
    这与真实图形系统的做法一致（曲线先细分，再按折线裁剪）。
    """
    import math
    a = math.radians(float(angle or 0.0))
    ca, sa = math.cos(a), math.sin(a)
    pts = []
    for i in range(max(8, int(n))):
        t = 2.0 * math.pi * i / max(8, int(n))
        ex, ey = rx * math.cos(t), ry * math.sin(t)
        x = cx + ex * ca - ey * sa
        y = cy + ex * sa + ey * ca
        p = (int(round(x)), int(round(y)))
        if not pts or p != pts[-1]:      # 去掉相邻重复点，避免零长线段
            pts.append(p)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    return pts


def _outline_points(shape):
    """任意图元 → 轮廓折线顶点（圆/椭圆按 TESS_SEGMENTS 段离散）。"""
    from core.shapes import CircleShape, EllipseShape, LineShape, PolygonShape
    if isinstance(shape, LineShape):
        return [tuple(shape.p0), tuple(shape.p1)]
    if isinstance(shape, CircleShape):
        return _ellipse_polygon(shape.center[0], shape.center[1],
                                shape.r, shape.r, 0.0)
    if isinstance(shape, EllipseShape):
        return _ellipse_polygon(shape.center[0], shape.center[1],
                                shape.rx, shape.ry,
                                getattr(shape, "angle", 0.0))
    if isinstance(shape, PolygonShape):
        return [(int(x), int(y)) for x, y in shape.vertices]
    return []


def _polyline_edges(points, closed: bool):
    """折线顶点 → 线段列表 [(a, b), ...]；closed 时首尾相接。"""
    pts = [(int(round(x)), int(round(y))) for x, y in points]
    out = []
    count = len(pts) if closed else len(pts) - 1
    for i in range(max(0, count)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        if a != b:
            out.append((a, b))
    return out


class _ClipDemoBase:
    """参数卡基类：标签 + 整数微调框网格（与模块二演示页同构）。"""

    title = "裁剪"
    icon = "fit"
    kind = "canvas"
    freehand_replay = False
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

    def reference_pixels(self):
        """窗口外的线段像素（橙色参照层）：由裁剪算法结果反推。

        取"原始图元像素 − 各段裁剪结果像素"，而不是拿窗口掩膜做差——
        参照层与演示步骤流用的是同一个算法，末帧必然对得齐。
        """
        from algorithms.line_bresenham import bresenham_line
        from core.rasterizer import rasterize
        src = self.playback_source()
        if src is None or self._clip_fn is None:
            return []
        outline, fill = rasterize(src)
        rect = self._rect(self.collect())
        kept = set()
        for a, b in self._segments():
            res = self._clip_fn(a[0], a[1], b[0], b[1], rect)
            if res is not None:
                kept.update(bresenham_line(*res))
        return sorted((set(outline) | set(fill)) - kept)

    def _defs(self):
        return [("wx0", "窗口左", 20, -20, 120), ("wy0", "窗口上", 12, -20, 80),
                ("wx1", "窗口右", 44, -20, 120), ("wy1", "窗口下", 30, -20, 80)]

    def _rect(self, p):
        return (min(p["wx0"], p["wx1"]), min(p["wy0"], p["wy1"]),
                max(p["wx0"], p["wx1"]), max(p["wy0"], p["wy1"]))

    def _segments(self):
        """演示对象 → 待裁剪线段列表。

        直线 = 1 段；多边形 = 各条边；圆/椭圆 = 离散折线的各条边。
        画布没有对应图元时返回 []（不生成任何内置示例）。
        """
        src = self.playback_source()
        if src is None:
            return []
        from core.shapes import LineShape
        pts = _outline_points(src)
        if len(pts) < 2:
            return []
        return _polyline_edges(pts, closed=not isinstance(src, LineShape))

    def make_steps(self, params):
        self._pinned_source = self.playback_source()
        segs = self._segments()
        if not segs:
            return []
        rect = self._rect(params)
        if len(segs) == 1:
            (a, b), = segs
            return self._steps(a[0], a[1], b[0], b[1], rect)
        # 圆/椭圆/多边形：逐段跑同一裁剪算法，步骤流串联播放。
        # 替换式渲染下每步像素要带上"前面各段已裁好的结果"，
        # 否则每段演示完就被下一段覆盖，画面只剩最后一段。
        steps = []
        total = len(segs)
        committed = set()            # 前 i 段的最终裁剪结果（累计）
        for i, (a, b) in enumerate(segs):
            part = self._steps(a[0], a[1], b[0], b[1], rect)
            # 只有"接受"的段才进入累计结果；整段舍弃的段演示完应消失
            tail = part[-1].values if part else {}
            accepted = tail.get("判定") == "接受" or tail.get("阶段") == "输出"
            seg_final = set(part[-1].pixels) if (part and accepted) else set()
            for st in part:
                st.pixels = sorted(set(st.pixels) | committed)
                st.note = f"第 {i + 1}/{total} 段 · {st.note}"
            steps.extend(part)
            committed |= seg_final
        return steps


class CohenDemo(_LineClipDemo):
    title = "编码裁剪（Cohen-Sutherland）"
    icon = "fit"
    algo = ALGO_COHEN
    variables = {"区域码0": "起点区域码", "区域码1": "终点区域码",
                 "判定": "本步判定（接受/舍弃/求交）",
                 "端点0": "当前起点", "端点1": "当前终点",
                 "交点": "本轮新交点"}
    default_fps = 2
    formula = ("Cohen-Sutherland 编码裁剪\n"
               "区域码 bit：左1 右2 上4 下8\n"
               "① code0|code1 = 0 → 整段接受\n"
               "② code0&code1 ≠ 0 → 整段舍弃\n"
               "③ 否则取外端点按所在边界求交\n"
               "每轮至少一位区域码被清零，最多 4 轮")

    def _steps(self, *args):
        return cohen_sutherland_steps(*args)

    _clip_fn = staticmethod(cohen_sutherland)


class LiangDemo(_LineClipDemo):
    title = "参数裁剪（Liang-Barsky）"
    icon = "fit"
    algo = ALGO_LIANG
    variables = {"阶段": "本步阶段（初始/更新/跳过/舍弃/输出）",
                 "边界": "当前判定的窗口边界",
                 "p": "参数 p（-dx/dx/-dy/dy）",
                 "q": "参数 q（起点到边界的有向距离）",
                 "u0": "下界（进入参数）", "u1": "上界（离开参数）"}
    default_fps = 2
    formula = ("Liang-Barsky 参数裁剪\n"
               "P(t)=P0+t·(P1-P0), t∈[0,1]\n"
               "对左/右/上/下四条边界：\n"
               "p·t ≤ q，p<0 进边、p>0 出边\n"
               "u0 = max(u0, q/p)，u1 = min(u1, q/p)\n"
               "u0 > u1 → 整段舍弃")

    def _steps(self, *args):
        return liang_barsky_steps(*args)

    _clip_fn = staticmethod(liang_barsky)


# =====================================================================
# 多边形裁剪
# =====================================================================
class PolygonClipDemo(_ClipDemoBase):
    title = "多边形裁剪（Sutherland-Hodgman）"
    icon = "polygon"
    algo = ALGO_HODGMAN
    subject_kind = "closed"       # 演示对象 = 画布上选中/最后画的封闭图形
    default_fps = 2
    variables = {"阶段": "当前裁剪边",
                 "输入顶点": "本轮输入顶点数",
                 "输出顶点": "本轮保留顶点数",
                 "新增交点": "本边新增交点",
                 "四情形": "内→内 / 内→外 / 外→内 / 外→外 计数"}
    formula = ("Sutherland-Hodgman 逐边裁剪\n"
               "依次用 左→右→上→下 半平面切分\n"
               "内→外：输出交点；外→内：输出交点\n"
               "凹多边形可能拆成多个区域\n"
               "四轮后得到窗口内多边形")

    def _defs(self):
        return [("wx0", "窗口左", 16, -20, 120), ("wy0", "窗口上", 12, -20, 80),
                ("wx1", "窗口右", 46, -20, 120), ("wy1", "窗口下", 34, -20, 80)]

    def _vertices(self):
        """演示多边形 = 画布图元的轮廓顶点；圆/椭圆先离散成折线。

        没有对象（或只剩一条直线，凑不出面）时不生成任何示例。
        """
        src = self.playback_source()
        if src is None:
            return None
        verts = _outline_points(src)
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
        return clip_polygon_steps(verts, rect)

    def reference_pixels(self):
        """窗口外的多边形轮廓像素：由 clip_polygon 结果反推（与步骤同源）。"""
        verts = self._vertices()
        if verts is None:
            return []
        p = self.collect()
        rect = (min(p["wx0"], p["wx1"]), min(p["wy0"], p["wy1"]),
                max(p["wx0"], p["wx1"]), max(p["wy0"], p["wy1"]))
        full = set(polygon_outline(verts))
        clipped = clip_polygon(verts, rect)
        kept = set(polygon_outline(clipped)) if clipped else set()
        return sorted(full - kept)


# =====================================================================
def create_demos():
    return [CohenDemo(), LiangDemo(), PolygonClipDemo()]
