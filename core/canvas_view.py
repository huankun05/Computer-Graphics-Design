# -*- coding: utf-8 -*-
"""
=====================================================================
 core/canvas_view.py v5 — 模拟像素画布（可增长"无限"纸面 + 五层渲染）
=====================================================================
模拟像素体系（规范：一个网格 = 一个像素）：
  算法运行在模拟像素坐标上（整数，可为负），每个像素渲染为 SIM×SIM
  方块；网格线只落在像素边界上，缩放时按阶梯合并显示。

可增长纸面（替代 v4 的固定 60×40）：
  base 位图覆盖"当前范围"（extent，模拟像素坐标 _base_origin/_base_size），
  初始为 60×40 的锚定纸面；向纸外绘制时自动扩张 base、移动位图原点、
  扩展场景矩形 —— 视觉上"纸跟着笔走"，等效无限画布
  （为防内存失控，软限制：每侧最多画出锚定纸面外 SPAN_SIM 格）。

渲染分层（规范契约③）：
  drawBackground   桌面衬底 + 纸投影/纸边（跟随 extent）
  base pixmap      已提交图元（仅提交/撤销/清空时重建或增量）
  drawForeground   像素网格/坐标轴 + 演示像素层 + 预览 + 选中框

性能设计（规范 6.2）：
  预览 16ms 节流 + 几何签名去重；像素批量 drawRects；
  add_shape 增量光栅化（仅范围变化时重建 base 底图）。

文档与撤销：一切修改走 Document 命令栈；shapes_committed 信号供
演示模式做"画布拾取回放"（手动划线 → 自动步骤动画重放）。
=====================================================================
"""

from typing import List, Optional, Tuple  # noqa: F401

from PySide6.QtCore import Qt, Signal, QPointF, QPoint, QRect, QRectF, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtGui import (
    QImage, QPainter, QPen, QColor, QPixmap, QBrush,
    QMouseEvent, QWheelEvent
)
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem

from core.document import Document
from core.commands import (
    AddShapeCommand, AddShapesCommand, RemoveShapeCommand, ClearCommand,
    ReplaceAllCommand,
)
from core.rasterizer import rasterize
from core.shapes import (
    Shape, LineShape, CircleShape, EllipseShape, PolygonShape,
    SIM, IMAGE_W, IMAGE_H, GRID_W, GRID_H,
)
from teaching.pixel_layer import PixelLayer

BG_COLOR      = QColor(255, 255, 255)   # 画布颜色（整张无限画布统一）
SURROUND      = QColor(255, 255, 255)   # （弃用）历史上"桌面"色，现与画布同色
PAPER_EDGE    = QColor(255, 255, 255)   # （弃用）历史上"纸边"色
SHADOW_COLOR  = QColor(31, 41, 55)      # （弃用）历史上"纸投影"色
GRID_MINOR    = QColor(224, 228, 236)   # 像素网格（细）
GRID_MAJOR    = QColor(203, 210, 221)   # 像素网格（每 5 格加深）
AXIS_COLOR    = QColor(70, 120, 190)    # 中心坐标轴（蓝虚线）
PREVIEW_COLOR = QColor(247, 107, 21)    # 拖拽预览（橙）
SELECT_COLOR  = QColor(79, 110, 247)    # 选中包围盒（主题蓝紫）

# 网格自适应阶梯（单位：模拟像素）：网格线永远落在像素边界上
_LADDER = {1: 2, 2: 5, 5: 10, 10: 20, 20: 50, 50: 100}
# 软限制：锚定纸面外每侧最多可画多少格（防 base 位图无限膨胀）
SPAN_SIM = 120


def _preview_signature(shape: Optional[Shape]):
    """预览的"几何签名"：取整后的全部决定像素输出的参数（颜色除外）。"""
    if shape is None:
        return None
    if isinstance(shape, LineShape):
        return ("line", shape.kind, shape.p0, shape.p1, shape.width)
    if isinstance(shape, CircleShape):
        return ("circle", shape.center, shape.r, shape.width)
    if isinstance(shape, EllipseShape):
        return ("ellipse", shape.center, shape.rx, shape.ry, shape.width)
    if isinstance(shape, PolygonShape):
        return ("poly", tuple(shape.vertices), shape.fill, shape.width)
    return (shape.kind, shape.width)


class CanvasView(QGraphicsView):
    """画布视图：可增长纸面 + 文档渲染 + 鼠标绘图 + 缩放平移。"""

    cursor_changed      = Signal(int, int)   # 鼠标所在模拟像素坐标（状态栏）
    zoom_changed        = Signal(float)      # 缩放倍率变化
    shape_count_changed = Signal(int)        # 图元数量变化
    document_changed    = Signal()           # 文档/撤销栈变化（按钮态刷新）
    context_requested   = Signal(object)     # 右键菜单请求（全局坐标 QPoint）
    shapes_committed    = Signal(object)     # 新图元提交（演示模式回放用）
    selection_changed   = Signal(object)     # 选中图元变化（图元列表/选项条联动）
    fill_toggled        = Signal(object)     # 填充切换（演示模式追加填充动画）
    notify              = Signal(str)        # 轻量提示（状态栏临时消息）
    demo_arrow          = Signal(int)        # 演示模式左右方向键（±1 单步）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # ---- base 层：已提交图元位图（跟随可增长范围） ----
        self._base_origin = (0, 0)          # base 左上角的模拟像素坐标（可为负）
        self._base_size = (GRID_W, GRID_H)  # base 尺寸（模拟像素数）
        self.base_image = QImage(IMAGE_W, IMAGE_H, QImage.Format_RGB32)
        self.base_image.fill(BG_COLOR)
        self.pix_item = QGraphicsPixmapItem(QPixmap.fromImage(self.base_image))
        self.scene.addItem(self.pix_item)
        self._update_scene_rect()

        self.setRenderHints(QPainter.Antialiasing)
        # 故意不开 SmoothPixmapTransform：放大看到清晰像素格（教学+更快）

        self.setMouseTracking(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # ---- 文档（图元 + 撤销栈） ----
        self.document = Document()

        # ---- 演示模式像素层 ----
        self.demo = PixelLayer(self)

        # ---- 预览状态（拖拽中的图元，foreground 层渲染） ----
        self.preview_shape: Optional[Shape] = None
        self._preview_pixels: list = []      # 预览像素（模拟像素坐标）
        self._preview_sig = None
        self._preview_dirty = False
        self._preview_timer = QTimer(self)   # 60fps 节流
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._refresh_preview)

        # ---- 工具与画笔 ----
        self.tool = None
        self.pen_color = QColor("#222222")
        self.pen_width = 1
        self.show_grid = True
        self.show_axis = True
        self._selected_shape: Optional[Shape] = None
        self._ghost_pixels = []              # 幽灵像素（移动预览）
        self._ghost_color = SELECT_COLOR
        self._move_ctx = None                # 移动上下文 {shape,start,snap,last}

        # ---- 算法下拉 / 填充切换（选项条驱动的全局绘图态） ----
        self.algorithm = "line_dda"     # 当前算法键（形状→算法清单在 tools/ 声明）
        self.fill_mode = True           # 多边形类工具提交时 填充(True)⇄描边(False)

        # ---- 平移状态（空格+左键 / 中键） ----
        self._space_pressed = False
        self._panning = False
        self._pan_last = None                 # 平移基准（全局光标位置）

        self._render_base()
        self.resetTransform()
        QTimer.singleShot(50, self._center_view)

    # ==================================================================
    # 范围（extent）管理：纸跟着笔走
    # ==================================================================
    def _extent_rect(self) -> QRectF:
        """当前 base 覆盖的真实位图矩形（场景坐标）。"""
        ox, oy = self._base_origin
        w, h = self._base_size
        return QRectF(ox * SIM, oy * SIM, w * SIM, h * SIM)

    def _update_scene_rect(self):
        """场景矩形 = 纸面 + 一圈余量（供继续向外画/平移浏览）。"""
        margin = 2 * IMAGE_W
        self.setSceneRect(self._extent_rect().adjusted(
            -margin, -margin, margin, margin))

    def _shapes_extent(self, shapes):
        """若干图元的模拟像素包围盒 (x0,y0,x1,y1)（右/下开区间），无像素返回 None。"""
        xs, ys = [], []
        for s in shapes:
            if not s.visible:
                continue
            outline, fill = rasterize(s)
            for px in outline + fill:
                xs.append(px[0])
                ys.append(px[1])
        if not xs:
            return None
        return min(xs), min(ys), max(xs) + 1, max(ys) + 1

    def _ensure_extent(self, shapes):
        """保证 base 覆盖这些图元；不够则扩张 base 并迁移旧内容。"""
        ext = self._shapes_extent(shapes)
        if ext is None:
            return
        ox, oy = self._base_origin
        w, h = self._base_size
        x0, y0 = min(ox, ext[0]), min(oy, ext[1])
        x1, y1 = max(ox + w, ext[2]), max(oy + h, ext[3])
        if (x0, y0, x1, y1) == (ox, oy, ox + w, oy + h):
            return
        old = self.base_image
        img = QImage((x1 - x0) * SIM, (y1 - y0) * SIM, QImage.Format_RGB32)
        img.fill(BG_COLOR)
        p = QPainter(img)
        p.drawImage(QPoint((ox - x0) * SIM, (oy - y0) * SIM), old)
        p.end()
        self.base_image = img
        self._base_origin = (x0, y0)
        self._base_size = (x1 - x0, y1 - y0)
        self.pix_item.setPixmap(QPixmap.fromImage(img))
        self.pix_item.setPos(x0 * SIM, y0 * SIM)
        self._update_scene_rect()

    # ==================================================================
    # 工具 / 画笔
    # ==================================================================
    def _center_view(self):
        """让锚定纸面初始居中显示。"""
        self.centerOn(IMAGE_W // 2, IMAGE_H // 2)

    def set_tool(self, tool):
        """切换当前工具（清掉进行中的预览）。"""
        if self.tool:
            self.tool.deactivate()
        self.tool = tool
        self.set_preview(None)

    def set_pen_color(self, c):
        self.pen_color = c

    def set_pen_width(self, w):
        self.pen_width = w

    def set_algorithm(self, key: str):
        """选项条算法下拉 → 当前算法键（工具提交图元时读取）。"""
        self.algorithm = key

    # ------------------------------------------------------------------
    # 选择 / 命中测试 / 幽灵预览（选择移动工具用）
    # ------------------------------------------------------------------
    def visible_sim_bounds(self) -> tuple:
        """当前可见区域对应的模拟像素范围 (x0,y0,x1,y1)（右/下开区间，含 1 格余量）。"""
        vp = self.viewport().rect()
        tl = self.mapToScene(vp.topLeft())
        br = self.mapToScene(vp.bottomRight())
        x0 = int(tl.x()) // SIM - 1
        y0 = int(tl.y()) // SIM - 1
        x1 = int(br.x()) // SIM + 2
        y1 = int(br.y()) // SIM + 2
        return (x0, y0, x1, y1)

    def hit_test(self, pos) -> Optional[Shape]:
        """模拟像素坐标 → 命中的最上层图元（轮廓或内部像素），无则 None。"""
        x, y = int(pos.x()), int(pos.y())
        for shape in reversed(self.document.shapes):    # 后画的在上层
            if not shape.visible:
                continue
            outline, fill = rasterize(shape)
            if (x, y) in set(outline) or (x, y) in set(fill):
                return shape
        return None

    def set_ghost(self, pixels, color=SELECT_COLOR):
        """设置"幽灵"像素（移动预览用，画在前景层，不进 base）。"""
        self._ghost_pixels = list(pixels)
        self._ghost_color = color
        self.viewport().update()

    # ------------------------------------------------------------------
    # 图元移动（选中态下按住拖动；供画布拦截与选择工具共用）
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # 图元变换（移动 / 缩放；选中态下画布拦截，供所有工具共用）
    #   移动：按住图元或其包围盒内部拖动；
    #   缩放：按住 8 方位手柄拖动（角=双向，边=单向；圆一律圆心定点等比）。
    #   Ctrl+拖拽 = 以形状锚点为定点的等比缩放（快捷方式，保留）。
    # ------------------------------------------------------------------
    _HANDLE_TOL = 12          # 手柄命中容差（场景像素）

    @staticmethod
    def _handle_positions(bbox):
        """8 方位手柄：四角 + 四边中点 → [(x, y, 轴模式)]。"""
        x0, y0, x1, y1 = bbox
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        return [(x0, y0, "xy"), (cx, y0, "y"), (x1, y0, "xy"),
                (x1, cy, "x"), (x1, y1, "xy"), (cx, y1, "y"),
                (x0, y1, "xy"), (x0, cy, "x")]

    def _sel_bbox(self) -> tuple:
        """选中图元的真实像素包围盒，无选中/空图元返回 None。"""
        s = self._selected_shape
        if s is None:
            return None
        bbox = self._shape_bbox(s)
        return bbox

    def _handle_hit(self, pos):
        """场景真实像素坐标 → 命中的手柄 (x, y, 轴模式)，未命中返回 None。

        注意：手柄位于包围盒边缘（任意真实像素值），必须用未量化的
        场景点做命中——若先按模拟格取整会偏差最多 SIM-1 像素，
        大于命中容差，导致手柄永远点不中。
        """
        bbox = self._sel_bbox()
        if bbox is None:
            return None
        px, py = pos.x(), pos.y()
        for hx, hy, axis in self._handle_positions(bbox):
            if abs(px - hx) <= self._HANDLE_TOL and                     abs(py - hy) <= self._HANDLE_TOL:
                return (hx, hy, axis)
        return None

    def _bbox_contains(self, pos) -> bool:
        """场景真实像素坐标是否落在选中图元包围盒内。"""
        bbox = self._sel_bbox()
        if bbox is None:
            return False
        px, py = pos.x(), pos.y()
        return bbox[0] <= px <= bbox[2] and bbox[1] <= py <= bbox[3]

    def _transform_group(self, s: Shape):
        """变换成组：图元与它的填充整体联动（双向）。

        · 边界图元 → [边界] + owner 指向它的全部填充；
        · 填充图元 → [owner 边界] + 该边界的全部填充（拖填充 = 拖整体）。
        """
        from core.shapes import RasterFillShape
        if isinstance(s, RasterFillShape):
            owner = getattr(s, "owner", None)
            if owner is not None:
                return [owner] + [f for f in self.document.shapes
                                  if isinstance(f, RasterFillShape)
                                  and getattr(f, "owner", None) is owner]
            return [s]
        return [s] + [f for f in self.document.shapes
                      if isinstance(f, RasterFillShape)
                      and getattr(f, "owner", None) is s]

    def begin_move(self, pos, scale: bool = False) -> bool:
        """开始变换选中图元（移动，或 Ctrl=锚点等比缩放）。

        pos 为模拟像素坐标（工具层传整数格点；鼠标路径传未量化
        浮点，内部 int() 取整到所在格，与 _to_pos 的 //SIM 等价）。
        成组：选中边界或填充之一，整组（边界+填充）一起变换。
        """
        import math
        s = self._selected_shape
        if s is None:
            return False
        from core.shapes import snapshot
        members = self._transform_group(s)
        ctx = {"shape": s,
               "group": [(m, snapshot(m)) for m in members],
               "start": (int(pos.x()), int(pos.y())),
               "snap": snapshot(s), "last": (0, 0), "f": 1.0,
               "mode": "scale_uni" if scale else "move"}
        if scale:
            if hasattr(s, "center"):
                # 圆/椭圆：以圆心为定点，系数 = 当前距离/按下时距离
                ctx["anchor"] = (s.center[0], s.center[1])
            elif hasattr(s, "p0"):
                ctx["anchor"] = ((s.p0[0] + s.p1[0]) / 2,
                                 (s.p0[1] + s.p1[1]) / 2)
            elif getattr(s, "pixels", None):
                # 光栅填充（无 owner 时单独选中）：以像素质心为定点
                px = s.pixels
                ctx["anchor"] = (sum(p[0] for p in px) / len(px),
                                 sum(p[1] for p in px) / len(px))
            else:
                vs = getattr(s, "vertices", [])
                ctx["anchor"] = (sum(v[0] for v in vs) / len(vs),
                                 sum(v[1] for v in vs) / len(vs))
            ctx["d0"] = max(1.0, math.hypot(ctx["start"][0] - ctx["anchor"][0],
                                            ctx["start"][1] - ctx["anchor"][1]))
        self._move_ctx = ctx
        return True

    def begin_scale(self, handle: tuple, pos) -> bool:
        """开始手柄缩放：handle = 命中的 (hx, hy, 轴模式)。"""
        s = self._selected_shape
        if s is None:
            return False
        from core.shapes import snapshot
        hx, hy, axis = handle
        bbox = self._sel_bbox()
        # 定点 = 对角/对边的 bbox 点
        ax = bbox[0] if hx >= (bbox[0] + bbox[2]) / 2 else bbox[2]
        ay = bbox[1] if hy >= (bbox[1] + bbox[3]) / 2 else bbox[3]
        if axis == "x":                       # 左右中点手柄：定点 = 对边中点
            ay = (bbox[1] + bbox[3]) / 2
        if axis == "y":
            ax = (bbox[0] + bbox[2]) / 2
        self._move_ctx = {"shape": s,
                          "group": [(m, snapshot(m))
                                    for m in self._transform_group(s)],
                          "mode": "scale_" + axis,
                          "anchor": (ax, ay), "snap": snapshot(s),
                          "h0": (float(hx), float(hy)),
                          "anchor_sim": (ax / SIM, ay / SIM),
                          "last": (1.0, 1.0)}
        return True

    def update_move(self, pos):
        """变换中：图元参数实时更新 + 幽灵预览（不进 base，松手才提交）。

        pos 为模拟像素坐标（工具层整数格点 / 鼠标路径未量化浮点）。
        移动按模拟格取整算增量；手柄缩放在内部 ×SIM 还原成真实
        像素再算比例（anchor/h0 存的是真实像素），避免两套单位混算。
        """
        import math
        from core.shapes import restore, scale_snapshot, translate
        if not self._move_ctx:
            return
        ctx = self._move_ctx
        grp = ctx.get("group") or [(ctx["shape"], ctx["snap"])]
        if ctx["mode"] == "scale_uni":
            # Ctrl+拖拽：定点 = 图元锚点（模拟像素），比例 = 距离比
            ax, ay = ctx["anchor"]
            d1 = max(1.0, math.hypot(pos.x() - ax, pos.y() - ay))
            f = max(0.05, min(20.0, d1 / ctx["d0"]))
            ctx["f"] = f
            for m, snap in grp:
                restore(m, snap)                 # 先还原到变换前
                # 成员填充与主图元共用同一锚点（如圆心），保证同心缩放
                scaled = scale_snapshot(m.kind, snap, f, f,
                                        anchor=(ax, ay))
                restore(m, scaled)
        elif ctx["mode"].startswith("scale"):
            # 手柄缩放：定点/初始手柄/当前点统一用真实像素
            rx, ry = pos.x() * SIM, pos.y() * SIM
            ax, ay = ctx["anchor"]
            hx, hy = ctx["h0"]
            if ctx["mode"] in ("scale_x", "scale_xy"):
                dx0 = max(1.0, abs(hx - ax))
                fx = max(0.05, min(20.0, abs(rx - ax) / dx0))
            else:
                fx = 1.0
            if ctx["mode"] in ("scale_y", "scale_xy"):
                dy0 = max(1.0, abs(hy - ay))
                fy = max(0.05, min(20.0, abs(ry - ay) / dy0))
            else:
                fy = 1.0
            ctx["fx"], ctx["fy"] = fx, fy
            for m, snap in grp:
                restore(m, snap)                 # 先还原到变换前
                scaled = scale_snapshot(m.kind, snap, fx, fy,
                                        anchor=ctx.get("anchor_sim"))
                restore(m, scaled)
        else:
            # 移动：同格去重必须放在 restore 之前——若先 restore 再
            # 提前 return，图元会被静默还原而虚影仍停在旧位置，
            # 松手时前后快照相等导致"移动丢失"
            dx = int(pos.x()) - ctx["start"][0]
            dy = int(pos.y()) - ctx["start"][1]
            if (dx, dy) == ctx["last"]:
                return
            ctx["last"] = (dx, dy)
            for m, snap in grp:
                restore(m, snap)                 # 还原到变换前
                translate(m, dx, dy)
        ghost = []
        for m, _snap in grp:
            o, f = rasterize(m)
            ghost += o + f
        self.set_ghost(ghost)

    def _refill(self, fill):
        """边界几何变化后按原算法/种子重跑填充。

        缩放时点集映射会留下稀疏网格洞，重跑才能正确覆盖新区域；
        重跑为空（如种子落到边界上）则保留原像素不动。
        仅适用于油漆桶产物（有 algo 标记）；对比结果图元对等
        无 algo 的像素图元不重跑（它们的像素就是算法结果本身）。
        """
        algo = getattr(fill, "algo", None)
        if algo is None:
            return
        from algorithms.steps import expand_steps
        from algorithms.seed_fill import scanline_seed_fill_steps
        seed = tuple(fill.seed)
        boundary = set()
        for s in self.document.shapes:
            if not s.visible or s is fill:
                continue
            o, f = rasterize(s)
            boundary.update(o)
            boundary.update(f)
        pixels = set()
        if algo == "scanline":
            owner = getattr(fill, "owner", None)
            if owner is None:
                return
            from modules.module02_primitives.demos import fill_steps_for_shape
            result = fill_steps_for_shape(owner)
            if result:
                steps, _var = result
                pixels = set(expand_steps(steps)) - boundary
        else:
            vx0, vy0, vx1, vy1 = self.visible_sim_bounds()
            x0 = min(vx0, seed[0] - 5)
            y0 = min(vy0, seed[1] - 5)
            x1 = max(vx1, seed[0] + 6)
            y1 = max(vy1, seed[1] + 6)
            conn = 8 if algo == "seed8" else 4
            steps = scanline_seed_fill_steps(seed, boundary,
                                             (x0, y0, x1, y1), conn)
            pixels = set(expand_steps(steps))
        if pixels:
            fill.pixels = sorted(pixels)

    def end_move(self):
        """结束变换：有实际变化则提交 GroupMoveCommand（整组一步撤销）。"""
        from core.commands import GroupMoveCommand
        from core.shapes import snapshot
        if not self._move_ctx:
            return
        ctx = self._move_ctx
        grp = ctx.get("group") or [(ctx["shape"], ctx["snap"])]
        self.set_ghost([])
        self._move_ctx = None
        if ctx["mode"] == "scale_uni" or ctx["mode"].startswith("scale"):
            name = "缩放图元"
        else:
            dx, dy = ctx["last"]
            if dx == 0 and dy == 0:
                return
            name = "移动图元"
        # update_move 已把每个成员留在变换后的状态，直接取终态快照
        entries = [(m, before, snapshot(m)) for m, before in grp]
        if ctx["mode"] != "move":
            # 缩放后光栅填充按新几何重跑（点集缩放会留稀疏洞）
            from core.shapes import RasterFillShape
            for i, (m, b, _a) in enumerate(entries):
                if isinstance(m, RasterFillShape):
                    self._refill(m)
                    entries[i] = (m, b, snapshot(m))
        if all(b == a for _m, b, a in entries):
            return
        self.document.do(GroupMoveCommand(self.document, entries, name))
        self._render_base()
        self.document_changed.emit()

    def cancel_move(self):
        """Esc：放弃正在进行的变换（还原参数，清幽灵）。"""
        if self._move_ctx:
            from core.shapes import restore
            restore(self._move_ctx["shape"], self._move_ctx["snap"])
            self.set_ghost([])
            self._move_ctx = None

    def set_shape_fill(self, shape, on: bool):
        """设置闭合图元填充态（命令化，可撤销）。

        选项条"填充⇄描边"按钮（选中图元分支）与图元列表行内开关共用。
        之前重构后只有 toggle_fill_selected 这个入口，调用方用的
        set_shape_fill 未定义 → AttributeError 被 Qt 吞掉，圆等
        闭合图元选中后点填充按钮看起来毫无反应。
        """
        from core.commands import SetFillCommand
        from core.shapes import KIND_ELLIPSE, KIND_POLYGON, KIND_CIRCLE, \
            KIND_CIRCLE_MID, KIND_CIRCLE_DDA
        closed = (KIND_CIRCLE, KIND_CIRCLE_MID, KIND_CIRCLE_DDA,
                  KIND_ELLIPSE, KIND_POLYGON)
        if shape is None or shape.kind not in closed or shape.fill == on:
            return
        self.document.do(SetFillCommand(self.document, shape, on))
        self._render_base()
        self.document_changed.emit()
        self.fill_toggled.emit(shape)

    def toggle_fill_selected(self):
        """两阶段填充：对选中的闭合图元切换 填充/描边（可撤销）。"""
        s = self._selected_shape
        if s is not None:
            self.set_shape_fill(s, not s.fill)

    # ==================================================================
    # 文档操作（全部走命令栈 → 自动可撤销）
    # ==================================================================
    def add_shape(self, shape: Shape):
        """提交一个图元：入命令栈 + 增量画进 base（不全量重画）。"""
        self.document.do(AddShapeCommand(self.document, shape))
        self._ensure_extent([shape])
        self._paint_shapes([shape])
        self.set_preview(None)
        self.shape_count_changed.emit(len(self.document.shapes))
        self.document_changed.emit()
        self.shapes_committed.emit([shape])

    def add_shapes(self, shapes):
        """一次提交多个图元（如直线算法对比的两条线），撤销一步整体回退。"""
        self.document.do(AddShapesCommand(self.document, shapes))
        self._ensure_extent(shapes)
        self._paint_shapes(shapes)
        self.set_preview(None)
        self.shape_count_changed.emit(len(self.document.shapes))
        self.document_changed.emit()
        self.shapes_committed.emit(list(shapes))

    def _paint_shapes(self, shapes):
        """把若干图元增量光栅化进 base（坐标为世界模拟像素 → 平移到纸内）。"""
        ox, oy = self._base_origin
        p = QPainter(self.base_image)
        p.translate(-ox * SIM, -oy * SIM)
        for s in shapes:
            outline, fill = rasterize(s)
            self._plot(p, outline, s.color, s.inset)
            self._plot(p, fill, s.color, s.inset)
        p.end()
        self.pix_item.setPixmap(QPixmap.fromImage(self.base_image))

    def remove_shape(self, shape: Shape):
        """删除图元（图元列表用），可撤销；边界/填充成组整体删除。"""
        from core.commands import RemoveShapesCommand
        doc_shapes = self.document.shapes
        group = [s for s in self._transform_group(shape)
                 if any(s is x for x in doc_shapes)]   # 身份比较防误配
        cmd = RemoveShapesCommand(self.document, group)
        cmd.capture()                      # do 之前记录原位置，撤销时按位插回
        self.document.do(cmd)
        sel = self._selected_shape
        if sel is not None and not any(sel is x for x in self.document.shapes):
            self.set_selected_shape(None)
        self._render_base()
        self.shape_count_changed.emit(len(self.document.shapes))
        self.document_changed.emit()

    def clear_all(self):
        """清空画布（保留快照，可撤销；范围复位到锚定纸面）。"""
        self.document.do(ClearCommand(self.document))
        self._render_base()
        self.set_preview(None)
        self.shape_count_changed.emit(0)
        self.document_changed.emit()

    def undo(self):
        if self.document.undo():
            self._render_base()
            self.set_preview(None)
            self.shape_count_changed.emit(len(self.document.shapes))
            self.document_changed.emit()

    def redo(self):
        if self.document.redo():
            self._render_base()
            self.set_preview(None)
            self.shape_count_changed.emit(len(self.document.shapes))
            self.document_changed.emit()

    @property
    def shapes(self):
        """当前图元列表（只读视图，供图元列表面板等使用）。"""
        return self.document.shapes

    # ==================================================================
    # 文档操作（全部走命令栈 → 自动可撤销）
    # ==================================================================
    # ------------------------------------------------------------------
    # 演示模式纸面暂存：进入时清空（应用图元走命令栈暂存，撤销历史保留），
    # 退出时整体恢复 —— 演示纸面始终空白，应用作品不受影响。
    # ------------------------------------------------------------------
    def enter_demo_mode(self):
        self._demo_clear_cmd = None
        self.set_preview(None)
        self.demo.reset()
        if self.document.shapes:
            self._demo_clear_cmd = ClearCommand(self.document)
            self.document.do(self._demo_clear_cmd)   # do() 清空图元并压栈
            self._render_base()
            self.shape_count_changed.emit(0)
            self.document_changed.emit()

    def exit_demo_mode(self):
        cmd = getattr(self, "_demo_clear_cmd", None)
        self.set_preview(None)
        self.demo.reset()
        if cmd is not None:
            self.document.undo_until(cmd)            # 连带撤销演示期间的绘制
            self._demo_clear_cmd = None
            self._render_base()
            self.shape_count_changed.emit(len(self.document.shapes))
            self.document_changed.emit()

    def save_image(self, path: str) -> bool:
        """导出画布为图片文件（当前纸面范围，不含预览层）。"""
        return self.base_image.save(path)

    def open_project(self, path: str):
        """打开 .gpad 工程文件：整体替换文档内容（可撤销）。"""
        from core.project_file import load_project
        shapes = load_project(path)
        self.document.do(ReplaceAllCommand(self.document, shapes))
        self._selected_shape = None
        self._render_base()
        self.set_preview(None)
        self.shape_count_changed.emit(len(self.document.shapes))
        self.document_changed.emit()

    # ==================================================================
    # 图元列表选中（画布上画虚线包围盒 + 角点手柄）
    # ==================================================================
    def set_selected_shape(self, shape: Optional[Shape]):
        self._selected_shape = shape
        self.selection_changed.emit(shape)
        self.viewport().update()

    @staticmethod
    def _shape_bbox(shape: Shape):
        """图元的包围盒（真实位图坐标，模拟像素 ×SIM），空图元返回 None。"""
        outline, fill = rasterize(shape)
        pts = outline + fill
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs) * SIM, min(ys) * SIM,
                (max(xs) + 1) * SIM - 1, (max(ys) + 1) * SIM - 1)

    # ==================================================================
    # 预览（拖拽实时反馈）
    # ==================================================================
    def set_preview(self, shape: Optional[Shape]):
        """工具设置预览图元（None=清除）。只记参数，真正刷新被节流。"""
        self.preview_shape = shape
        self.redraw()

    def redraw(self):
        """请求刷新预览。高频调用安全：16ms 定时器合并 + 签名去重。"""
        self._preview_dirty = True
        if not self._preview_timer.isActive():
            self._preview_timer.start(16)

    def _refresh_preview(self):
        """定时器到点：几何签名变了才重算像素并重绘视口。"""
        self._preview_timer.stop()
        if not self._preview_dirty:
            return
        self._preview_dirty = False
        sig = _preview_signature(self.preview_shape)
        if sig != self._preview_sig:
            self._preview_sig = sig
            if self.preview_shape is None:
                self._preview_pixels = []
            else:
                outline, fill = rasterize(self.preview_shape)
                # 填充图元（如"填充多边形"工具）实时预览内部填充
                self._preview_pixels = outline + fill
        self.viewport().update()

    # ==================================================================
    # 像素绘制（模拟像素 → SIM×SIM 方块；批量 drawRects，一格 = 一像素）
    # ==================================================================
    @staticmethod
    def _plot(painter: QPainter, pixels, color: QColor, inset: int = 0):
        """
        把模拟像素坐标列表画成 SIM×SIM 方块（一次批量调用）。
        inset>0 时向内缩——对比叠加下层画满格、上层画内芯，
        重合像素呈"外框+内芯"双色，差异像素呈纯色。
        """
        if not pixels:
            return
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawRects([QRect(x * SIM + inset, y * SIM + inset,
                                 SIM - inset * 2, SIM - inset * 2)
                           for x, y in pixels])

    # ==================================================================
    # base 层渲染（文档变化时整体重建，范围随之收缩/扩张/复位）
    # ==================================================================
    def _render_base(self):
        """按当前图元重算纸面范围并重画全部内容（撤销/清空/打开时调用）。"""
        ext = self._shapes_extent(self.document.shapes)
        x0, y0 = 0, 0
        x1, y1 = GRID_W, GRID_H           # 锚定纸面永远保留
        if ext:
            x0, y0 = min(x0, ext[0]), min(y0, ext[1])
            x1, y1 = max(x1, ext[2]), max(y1, ext[3])
        self._base_origin = (x0, y0)
        self._base_size = (x1 - x0, y1 - y0)

        img = QImage((x1 - x0) * SIM, (y1 - y0) * SIM, QImage.Format_RGB32)
        img.fill(BG_COLOR)
        p = QPainter(img)
        p.translate(-x0 * SIM, -y0 * SIM)
        for shape in self.document.shapes:
            if not shape.visible:
                continue                  # 图元列表里被眼睛隐藏的跳过
            outline, fill = rasterize(shape)
            self._plot(p, outline, shape.color, shape.inset)
            self._plot(p, fill, shape.color, shape.inset)
        p.end()
        self.base_image = img
        self.pix_item.setPixmap(QPixmap.fromImage(img))
        self.pix_item.setPos(x0 * SIM, y0 * SIM)
        self._update_scene_rect()

    # ==================================================================
    # 前景层：网格/坐标轴 + 演示层 + 预览 + 选中框
    # ==================================================================
    def drawForeground(self, painter: QPainter, rect: QRectF):
        # ---- 0. 像素网格 + 坐标轴（画在纸上面才可见） ----
        self._draw_grid_axis(painter, rect)

        # ---- 0.5 演示模式像素层（已生成染色 + 当前步闪烁） ----
        self.demo.paint(painter)

        # ---- 0.8 幽灵像素层（图元移动预览） ----
        if self._ghost_pixels:
            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(self._ghost_color))
            painter.setBrush(QColor(79, 110, 247, 130))
            painter.drawRects([QRect(x * SIM, y * SIM, SIM, SIM)
                               for x, y in self._ghost_pixels])

        # ---- 1. 拖拽预览层（模拟像素 → SIM×SIM 方块） ----
        if self._preview_pixels:
            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(PREVIEW_COLOR))
            painter.drawRects([QRect(x * SIM, y * SIM, SIM, SIM)
                               for x, y in self._preview_pixels])
            # 多边形顶点标记（白底蓝框小方块）
            if isinstance(self.preview_shape, PolygonShape) and                     self.preview_shape.vertices:
                from core.shapes import SIM as _S
                painter.setPen(QPen(SELECT_COLOR, 0))
                painter.setBrush(QBrush(QColor(255, 255, 255)))
                m = _S * 0.28
                side = _S * 0.44
                for vx, vy in self.preview_shape.vertices:
                    painter.drawRect(QRectF(vx * _S + m, vy * _S + m,
                                            side, side))

        # ---- 2. 选中图元的包围盒（虚线 + 四角手柄） ----
        if self._selected_shape is not None:
            bbox = self._shape_bbox(self._selected_shape)
            if bbox:
                x0, y0, x1, y1 = bbox
                pad = 4
                rect_s = QRectF(x0 - pad, y0 - pad,
                                x1 - x0 + pad * 2, y1 - y0 + pad * 2)
                painter.setRenderHint(QPainter.Antialiasing, True)
                painter.setPen(QPen(SELECT_COLOR, 0, Qt.DashLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(rect_s)
                painter.setPen(QPen(SELECT_COLOR, 0))
                painter.setBrush(QBrush(QColor(255, 255, 255)))
                hs = 6
                # 8 方位手柄：四角 + 四边中点（与 _handle_positions 命中一致）
                for hx, hy, _axis in self._handle_positions(bbox):
                    painter.drawRect(QRectF(hx - hs / 2, hy - hs / 2, hs, hs))

    # ==================================================================
    # 背景：桌面衬底 + 纸投影/纸边（跟随可增长范围）
    # ==================================================================
    def drawBackground(self, painter: QPainter, rect: QRectF):
        # 整个无限平面 = 一整张同色画布（白底 + 前景层像素网格）
        painter.fillRect(rect, BG_COLOR)

    def _draw_grid_axis(self, painter: QPainter, rect: QRectF):
        """模拟像素网格 + 中心坐标轴（无限纸面 → 网格铺满整个场景）。

        网格 = 像素格：网格线只画在模拟像素边界上。缩放按阶梯
        {1,2,5,10,...} 合并显示，边界始终像素对齐。
        """
        zoom = self.transform().m11()

        if self.show_grid:
            s = 1
            while s * SIM * zoom < 10:      # 屏幕上一格太小 → 合并格子显示
                s = _LADDER.get(s, s * 10)
            step = s * SIM
            left = int(rect.left()) // step * step
            top = int(rect.top()) // step * step
            pen_minor = QPen(GRID_MINOR, 0)
            pen_major = QPen(GRID_MAJOR, 0)
            for gx in range(left, int(rect.right()) + 1, step):
                painter.setPen(pen_major if (gx // step) % 5 == 0 else pen_minor)
                painter.drawLine(gx, int(rect.top()), gx, int(rect.bottom()))
            for gy in range(top, int(rect.bottom()) + 1, step):
                painter.setPen(pen_major if (gy // step) % 5 == 0 else pen_minor)
                painter.drawLine(int(rect.left()), gy, int(rect.right()), gy)

        # 坐标轴：锚定纸面的中心十字（模拟 (30,20) = 位图 (600,400)）
        if self.show_axis:
            cx, cy = IMAGE_W // 2, IMAGE_H // 2
            painter.setPen(QPen(AXIS_COLOR, 0, Qt.DashLine))
            painter.drawLine(cx, int(rect.top()), cx, int(rect.bottom()))
            painter.drawLine(int(rect.left()), cy, int(rect.right()), cy)

    # ==================================================================
    # 坐标换算（软限制：锚定纸面外每侧最多 SPAN_SIM 格）
    # ==================================================================
    def _to_pos(self, event) -> QPointF:
        """鼠标事件 → 模拟像素坐标（吸附格子；纸外可画，纸自动扩展）。"""
        pt = self.mapToScene(event.position().toPoint())
        x = max(-SPAN_SIM, min(GRID_W + SPAN_SIM - 1, int(pt.x()) // SIM))
        y = max(-SPAN_SIM, min(GRID_H + SPAN_SIM - 1, int(pt.y()) // SIM))
        return QPointF(x, y)

    # ==================================================================
    # 视图操作（快捷键 / 视图卡 / 右键菜单共用）
    # ==================================================================
    def fit_view(self):
        """适配窗口：当前纸面放进视口并居中。"""
        self.resetTransform()
        self.fitInView(self._extent_rect(), Qt.KeepAspectRatio)
        self.scale(0.96, 0.96)
        self.zoom_changed.emit(self.transform().m11())

    def zoom_100(self):
        """回到 100%（1 屏幕像素 = 1 位图像素）。"""
        self.resetTransform()
        self.centerOn(IMAGE_W // 2, IMAGE_H // 2)
        self.zoom_changed.emit(self.transform().m11())

    def fit_to_rect(self, x0: int, y0: int, x1: int, y1: int, pad: int = 60):
        """适配到指定区域（演示模式载入算法后自动对准生成范围）。"""
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        r = QRectF(x0 - pad, y0 - pad, (x1 - x0) + pad * 2, (y1 - y0) + pad * 2)
        self.resetTransform()
        self.fitInView(r, Qt.KeepAspectRatio)
        self.scale(0.97, 0.97)
        self.zoom_changed.emit(self.transform().m11())

    def contextMenuEvent(self, event):
        self.context_requested.emit(event.globalPos())

    def zoom_step(self, factor: float):
        """以视口中心为定点步进缩放（+/- 键调用）。"""
        cur = self.transform().m11()
        if cur * factor < 0.1 or cur * factor > 8.0:
            return
        self.scale(factor, factor)
        self.zoom_changed.emit(self.transform().m11())

    def zoom_to(self, z: float):
        """绝对缩放到 z 倍（滑杆调用）：换算成相对步进，定点=视口中心。"""
        cur = self.transform().m11()
        if cur > 0:
            self.zoom_step(z / cur)

    # ==================================================================
    # 鼠标事件：平移 / 交给工具
    # ==================================================================
    def mousePressEvent(self, event: QMouseEvent):
        # 空格+左键 或 中键：进入平移（PS 风格抓手）
        if event.button() == Qt.MiddleButton or \
                (event.button() == Qt.LeftButton and self._space_pressed):
            self._panning = True
            self._pan_last = (event.position() if hasattr(event, "position")
                              else QPointF(self.mapFromGlobal(QCursor.pos())))
            self.setCursor(Qt.ClosedHandCursor)
            return
        if event.button() == Qt.LeftButton and self._selected_shape is not None:
            # 选中态三优先：8 方位手柄=缩放 → 包围盒内=移动 → 其他=绘制
            # 命中判定必须用未量化的场景点：手柄位于包围盒边缘，
            # 若先按模拟格取整会偏差最多 SIM-1 像素，超过命中容差
            spt = self.mapToScene(event.position().toPoint())
            fpt = QPointF(spt.x() / SIM, spt.y() / SIM)   # 未量化模拟坐标
            handle = self._handle_hit(spt)
            if handle is not None:
                self.begin_scale(handle, fpt)
                return
            if self._bbox_contains(spt):
                # Ctrl 按住 = 以锚点为定点等比缩放（圆/椭圆即圆心定点）
                self.begin_move(fpt,
                                scale=bool(event.modifiers() & Qt.ControlModifier))
                return
        if event.button() == Qt.LeftButton and self.tool:
            # 开始绘制即取消列表选中态（避免选中框残留在新图元上）
            if self._selected_shape is not None:
                self.set_selected_shape(None)
            self.tool.on_press(self._to_pos(event), event)
        elif event.button() == Qt.RightButton and self.tool:
            self.tool.on_right_click(self._to_pos(event), event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._panning:
            pos = (event.position() if hasattr(event, "position")
                   else QPointF(self.mapFromGlobal(QCursor.pos())))
            dx = pos.x() - self._pan_last.x()
            dy = pos.y() - self._pan_last.y()
            self._pan_last = pos
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(dx))
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(dy))
            return
        pos = self._to_pos(event)
        self.cursor_changed.emit(int(pos.x()), int(pos.y()))
        if self._move_ctx:
            # 变换预览用未量化浮点模拟坐标：缩放比例连续平滑，
            # 移动增量在 update_move 内部 int() 取整到所在格
            spt = self.mapToScene(event.position().toPoint())
            self.update_move(QPointF(spt.x() / SIM, spt.y() / SIM))
            return
        if self.tool:
            self.tool.on_move(pos, event)   # event 透传：Shift 约束等修饰键
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if self._panning:
                self._panning = False
                self.setCursor(Qt.OpenHandCursor if self._space_pressed
                               else Qt.ArrowCursor)
                return
            if self._move_ctx:
                self.end_move()
                return
            if self.tool:
                self.tool.on_release(self._to_pos(event))
        elif event.button() == Qt.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    # ==================================================================
    # 键盘：空格 = 临时平移；Esc = 取消进行中操作；其余透传给工具
    # ==================================================================
    def press_space(self):
        """空格按下 → 平移模式（任何模式、任何焦点下都生效）。"""
        self._space_pressed = True
        self.setCursor(Qt.OpenHandCursor)

    def release_space(self):
        self._space_pressed = False
        self.setCursor(Qt.ArrowCursor)

    def nudge_selected(self, dx: int, dy: int):
        """方向键微调选中的图元（全局生效；边界/填充成组一起动）。"""
        from core.commands import GroupMoveCommand
        from core.shapes import translate, snapshot
        s = self._selected_shape
        if s is None or (dx == 0 and dy == 0):
            return
        entries = []
        for m in self._transform_group(s):
            before = snapshot(m)
            translate(m, dx, dy)
            entries.append((m, before, snapshot(m)))
        self.document.do(GroupMoveCommand(self.document, entries, "移动图元"))
        self._render_base()
        self.document_changed.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and not event.isAutoRepeat():
            # Esc：取消移动中的图元 / 取消进行中的图元（PS/Figma 惯例）
            if self._move_ctx:
                self.cancel_move()
                return
            if self.tool:
                self.tool.cancel()
            self.set_preview(None)
        else:
            if self.tool:
                self.tool.on_key(event)   # 多边形 Backspace/Enter 等
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space_pressed = False
            self.setCursor(Qt.ArrowCursor)
        super().keyReleaseEvent(event)

    # ==================================================================
    # 滚轮：以鼠标指针为中心缩放（10% ~ 800%）
    # ==================================================================
    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        before = self.mapToScene(event.position().toPoint())
        cur = self.transform().m11()
        if cur * factor < 0.1 or cur * factor > 8.0:
            event.accept()
            return
        self.scale(factor, factor)
        after = self.mapToScene(event.position().toPoint())
        delta = after - before
        self.translate(delta.x(), delta.y())
        self.zoom_changed.emit(self.transform().m11())
        event.accept()
