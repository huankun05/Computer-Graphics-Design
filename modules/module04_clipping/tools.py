# -*- coding: utf-8 -*-
"""
=====================================================================
 modules/module04_clipping/tools.py — 模块四：区域裁剪工具
=====================================================================
语义：窗口覆盖到的那部分图元【消失】，窗口外的部分原样保留。

交互（与 Word / Figma 的裁剪框一致，画窗口 → 调整 → 确认）：
  · 矩形窗口：空白拖出矩形；窗口出现后 8 个手柄可拖边/角，
    面板可精确输入 x0/y0/x1/y1；
  · 多边形窗口：面板切到"多边形窗口"，空白逐点单击布点
    （点回第一个点或右键 / Enter 闭合），闭合后可直接拖顶点、拖整体；
  · 窗口内部按 Enter（或双击画布、点面板"挖除窗口内"）才真正挖除，
    Esc 取消并清除窗口——定义完可以先对位置，不会误伤；
  · 一次挖除作用于画布上所有与窗口相交的可见图元，整组合并为一条命令，
    Ctrl+Z 一次完整还原。

算法（纯 Python，见 algorithms/window_mask.py）：
  窗口多边形 → 扫描线求交、交点两两配对（偶奇规则，凹多边形同样正确）
  → 边界用 Bresenham 补点 → 得到窗口掩膜；
  图元光栅像素 ∩ 掩膜 → 写入该图元的擦除掩码。
  掩码随图元一起参与后续平移/旋转/缩放，撤销走快照。

注意：标准裁剪算法（Cohen-Sutherland / 中点分割 / Liang-Barsky /
      Sutherland-Hodgman）仍可在演示模式的四个裁剪演示页中逐帧观察。
=====================================================================
"""

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPen, QPolygonF
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton,
                               QSpinBox)

from algorithms.window_mask import point_in_polygon, polygon_mask
from core.commands import ClipShapesCommand
from core.rasterizer import rasterize
from core.shapes import RasterFillShape, snapshot
from core.tool_base import ToolBase
from ui.widgets import SegmentedControl

CLIP_COLOR = QColor(229, 72, 77)          # 裁剪窗口：红（与选中蓝区分）
CLIP_FILL = QColor(229, 72, 77, 26)

MODE_RECT = "rect"
MODE_POLY = "poly"

_HANDLE_TOL = 0.8                          # 窗口手柄命中容差（模拟像素格）


class _EnterFilter(QObject):
    """窗口参数框的回车中转：QSpinBox 会吃掉回车，事件到不了画布。

    回车 = 确认裁剪（与画布上按 Enter 同效），避免用户改完坐标按回车没反应。
    """

    def __init__(self, tool: "ClipTool"):
        super().__init__(tool.canvas)
        self._tool = tool

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and \
                event.key() in (Qt.Key_Return, Qt.Key_Enter) and \
                not event.isAutoRepeat():
            if self._tool.commit_window():
                return True
        return False


class ClipTool(ToolBase):
    """区域裁剪：画矩形 / 多边形窗口 → 调整 → Enter 确认挖除（可撤销）。"""

    name = "区域裁剪"
    icon_name = "fit"
    cursor_hint = ("空白拖出矩形 / 画完多边形闭合 → 拖手柄调整 → Enter 或双击挖除窗口内部分"
                   "（Esc 取消，Ctrl+Z 撤销）")
    algorithm_options = []            # 挖除走像素掩膜，无需算法下拉

    def __init__(self, canvas):
        super().__init__(canvas)
        self.mode = MODE_RECT
        self.rect = None                  # 矩形窗口 (x0,y0,x1,y1)
        self.poly = None                  # 闭合的多边形窗口 [顶点...]
        self._verts = []                  # 正在布点的多边形顶点
        self._cursor = None               # 布点时的鼠标位置（橡皮筋预览）
        # 拖拽状态：new=正在拉新矩形 / move=整体移动 / resize=拖边角 /
        #           vertex=拖多边形顶点
        self._drag_mode = None
        self._drag0 = None                # 起手时的窗口快照
        self._press = None
        self._cur = None
        self._handle = None
        self._vi = None
        self._spins = {}
        self._rect_box = None
        self._poly_info = None
        self._seg = None
        self._msg = None
        self._msg_text = "画好窗口后按 Enter 才挖除"
        self._mask_key = None
        self._mask = set()
        # 演示模式预览：窗口驱动演示步骤，同时回车也真实挖除（可撤销）
        self.preview_only = False
        # 窗口变化回调（演示页用它把画布拖出的窗口回填到参数卡）
        self.window_changed = None
        # 演示页接管钩子：确认挖除（Enter/双击/按钮/参数框回车）时先问宿主——
        # 宿主返回 True 表示"先播判定动画，播完再挖"，本轮不直接挖除
        self.confirm_hook = None
        self._hook_applying = False
        # 参数框回车中转（面板重建后重新挂到新的输入框上）
        self._enter_filter = _EnterFilter(self)
        # 裁剪工具不参与"选中后拖动"，避免与定义窗口冲突
        canvas.set_selection([])

    # ------------------------------------------------------------------
    @property
    def is_drawing(self) -> bool:
        """多边形布点进行中：Backspace 归工具回退顶点，不删图元。"""
        return bool(self._verts)

    def formula(self):
        return ("像素掩膜区域挖除\n"
                "窗口多边形 → 扫描线逐行求交\n"
                "交点 x 排序后两两配对（偶奇规则）\n"
                "边界像素用 Bresenham 补入\n"
                "图元像素 ∩ 窗口掩膜 → 擦除掩码\n"
                "窗口外几何保持原样，Ctrl+Z 可撤销")

    def status(self):
        if self.mode == MODE_POLY:
            if self._verts:
                return f"多边形窗口布点中：{len(self._verts)} 个点\n" \
                       f"点回起点或右键/Enter 闭合，Backspace 回退，Esc 取消"
            if self.poly:
                return f"多边形窗口：{len(self.poly)} 个顶点（可拖顶点/整体）\n" \
                       f"Enter 或双击 = 挖除窗口内部分"
            return "未定义窗口\n多边形：空白处逐点单击布点，右键/Enter 闭合"
        if self.rect is None:
            return "未定义窗口\n矩形：空白处拖拽定义裁剪窗口"
        x0, y0, x1, y1 = self.rect
        return f"矩形窗口 ({x0},{y0})-({x1},{y1})\n" \
               f"宽 {x1 - x0 + 1} 高 {y1 - y0 + 1}\nEnter 或双击 = 挖除窗口内部分"

    # ------------------------------------------------------------------
    # 专属面板：窗口形状 + 矩形边界 + 确认挖除
    # ------------------------------------------------------------------
    def panel_widget(self):
        box = QFrame()
        box.setObjectName("clipPanel")
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._seg = SegmentedControl(["矩形窗口", "多边形窗口"],
                                     current=0 if self.mode == MODE_RECT else 1)
        self._seg.changed.connect(self._set_mode)
        row.addWidget(self._seg)

        # --- 矩形边界（仅矩形窗口显示；未定义前不可输入） ---
        self._rect_box = QFrame()
        rl = QHBoxLayout(self._rect_box)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)

        def spin(label, val, lo, hi):
            lab = QLabel(label)
            lab.setObjectName("secondary")
            sb = QSpinBox()
            sb.setRange(lo, hi)
            sb.setValue(val)
            sb.setFixedWidth(62)
            sb.setEnabled(False)
            sb.setToolTip("先在画布空白处拖出裁剪窗口，再精确输入边界")
            sb.valueChanged.connect(self._on_window_edited)
            rl.addWidget(lab)
            rl.addWidget(sb)
            return sb

        self._spins = {}
        self._spins["x0"] = spin("x0", 0, -200, 400)
        self._spins["y0"] = spin("y0", 0, -200, 400)
        self._spins["x1"] = spin("x1", 0, -200, 400)
        self._spins["y1"] = spin("y1", 0, -200, 400)
        for sb in self._spins.values():
            # 参数框里按回车 = 确认挖除（否则 QSpinBox 吃掉回车，看起来"没反应"）
            sb.installEventFilter(self._enter_filter)
        row.addWidget(self._rect_box)

        # --- 多边形顶点信息（仅多边形窗口显示） ---
        self._poly_info = QLabel("")
        self._poly_info.setObjectName("optHint")
        row.addWidget(self._poly_info)

        btn = QPushButton("挖除窗口内")
        btn.setObjectName("primaryBtn")
        btn.setToolTip("把窗口覆盖到的所有图元像素挖掉（Enter 同效，可撤销）")
        btn.clicked.connect(self._apply_all)
        row.addWidget(btn)

        clear = QPushButton("清除窗口")
        clear.setToolTip("移除当前裁剪窗口（Esc 同效，不影响已挖除的图元）")
        clear.clicked.connect(self._reset_window)
        row.addWidget(clear)

        hint = QLabel("画完窗口 → 拖手柄/顶点调整 → Enter 确认")
        hint.setObjectName("optHint")
        row.addWidget(hint)

        self._msg = QLabel(self._msg_text)
        self._msg.setObjectName("secondary")
        row.addWidget(self._msg)
        row.addStretch()
        self._refresh_ui()
        return box

    # ---- 面板状态同步（面板可能已被工具切换销毁，先判存活） ----
    @staticmethod
    def _alive(w) -> bool:
        if w is None:
            return False
        try:
            from shiboken6 import isValid
            return isValid(w)
        except Exception:
            return True

    def _refresh_ui(self):
        if self._alive(self._rect_box):
            self._rect_box.setVisible(self.mode == MODE_RECT)
        if self._alive(self._poly_info):
            self._poly_info.setVisible(self.mode == MODE_POLY)
            self._poly_info.setText(self._poly_text())
        if self.mode == MODE_RECT and self.rect is not None:
            self._sync_spins()
        elif self.mode == MODE_RECT:
            self._disable_spins()

    def _poly_text(self) -> str:
        if self._verts:
            return f"布点中：{len(self._verts)} 个（右键/Enter 闭合，Esc 取消）"
        if self.poly:
            return f"多边形窗口：{len(self.poly)} 个顶点（可拖顶点）"
        return "空白逐点单击布点，右键/Enter 闭合"

    def _set_mode(self, idx: int):
        self.mode = MODE_RECT if idx == 0 else MODE_POLY
        self._reset_window()
        self._refresh_ui()
        self.canvas.viewport().update()

    def _reset_window(self):
        """清除窗口（不动已挖除的图元）。"""
        self.rect = None
        self.poly = None
        self._verts = []
        self._cursor = None
        self._drag_mode = None
        self._mask_key = None
        self._mask = set()
        self._refresh_ui()
        self._set_msg("窗口已清除")
        self.canvas.viewport().update()

    def _on_window_edited(self):
        if self.rect is None:
            return
        vals = [self._spins[k].value() for k in ("x0", "y0", "x1", "y1")]
        x0, x1 = sorted((vals[0], vals[2]))
        y0, y1 = sorted((vals[1], vals[3]))
        self.rect = (x0, y0, max(x1, x0 + 1), max(y1, y0 + 1))
        self._mask_key = None
        self.canvas.viewport().update()

    def _sync_spins(self):
        if not self._spins:
            return
        for key, val in zip(("x0", "y0", "x1", "y1"), self.rect):
            sb = self._spins[key]
            if not self._alive(sb):
                continue
            sb.blockSignals(True)
            sb.setValue(val)
            sb.blockSignals(False)
            sb.setEnabled(True)
            sb.setToolTip("精确输入裁剪窗口边界")

    def _disable_spins(self):
        for sb in self._spins.values():
            if self._alive(sb):
                sb.setEnabled(False)
                sb.setToolTip("先在画布空白处拖出裁剪窗口，再精确输入边界")

    def _set_msg(self, text: str):
        self._msg_text = text
        if self._alive(self._msg):
            self._msg.setText(text)

    # ------------------------------------------------------------------
    # 窗口 → 顶点 → 掩膜
    # ------------------------------------------------------------------
    def window_vertices(self):
        """当前窗口 → 顶点列表（矩形转 4 个角点）；未定义返回 None。"""
        if self.mode == MODE_POLY:
            vs = self.poly
            if not vs or len(vs) < 3:
                return None
        else:
            if self.rect is None:
                return None
            x0, y0, x1, y1 = self.rect
            vs = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        return [(int(x), int(y)) for x, y in vs]

    def window_pixels(self):
        """当前窗口掩膜（像素集合，带缓存，窗口改动即失效）。"""
        verts = self.window_vertices()
        if verts is None:
            return set()
        key = tuple(verts)
        if key != self._mask_key:
            self._mask = polygon_mask(verts)
            self._mask_key = key
        return self._mask

    # ------------------------------------------------------------------
    # 鼠标：定义 / 调整窗口
    # ------------------------------------------------------------------
    def on_press(self, pos, event=None):
        p = (int(pos.x()), int(pos.y()))
        if self.mode == MODE_RECT:
            if self.rect is not None:
                h = self._rect_handle(p)
                if h == "inside":
                    self._drag_mode = "move"
                    self._drag0 = self.rect
                    self._press = p
                    return
                if h is not None:
                    self._drag_mode = "resize"
                    self._handle = h
                    self._drag0 = self.rect
                    self._press = p
                    return
            self._drag_mode = "new"
            self._drag0 = None
            self._press = p
            self._cur = p
            return

        # ---- 多边形模式 ----
        if self._verts:
            # 点回起点 = 闭合（与多边形工具一致）
            if len(self._verts) >= 3 and self._near(p, self._verts[0]):
                self._close_poly()
                return
            self._verts.append(p)
            self._cursor = p
            self._refresh_ui()
            self.canvas.viewport().update()
            return
        if self.poly:
            vi = self._poly_vertex_hit(p)
            if vi is not None:
                self._drag_mode = "vertex"
                self._vi = vi
                self._drag0 = list(self.poly)
                self._press = p
                return
            if point_in_polygon(self.poly, p):
                self._drag_mode = "move"
                self._drag0 = list(self.poly)
                self._press = p
                return
        # 空白处（或窗口外的点击）：开始画新的多边形窗口
        self.poly = None
        self._verts = [p]
        self._cursor = p
        self._mask_key = None
        self._drag_mode = None
        self._refresh_ui()
        self.canvas.viewport().update()

    def on_move(self, pos, event=None):
        p = (int(pos.x()), int(pos.y()))
        mode = self._drag_mode
        if self.mode == MODE_POLY and not mode:
            if self._verts:
                self._cursor = p
                self.canvas.viewport().update()
            return
        if mode == "new":
            self._cur = p
            self.canvas.viewport().update()
            return
        if mode == "move":
            dx, dy = p[0] - self._press[0], p[1] - self._press[1]
            if self.mode == MODE_RECT:
                x0, y0, x1, y1 = self._drag0
                self.rect = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
            else:
                self.poly = [(x + dx, y + dy) for x, y in self._drag0]
                self._refresh_ui()
            self._mask_key = None
            self.canvas.viewport().update()
            return
        if mode == "resize":
            dx, dy = p[0] - self._press[0], p[1] - self._press[1]
            x0, y0, x1, y1 = self._drag0
            if "w" in self._handle:
                x0 = min(x0 + dx, x1 - 1)
            if "e" in self._handle:
                x1 = max(x1 + dx, x0 + 1)
            if "n" in self._handle:
                y0 = min(y0 + dy, y1 - 1)
            if "s" in self._handle:
                y1 = max(y1 + dy, y0 + 1)
            self.rect = (x0, y0, x1, y1)
            self._mask_key = None
            self.canvas.viewport().update()
            return
        if mode == "vertex":
            self.poly = list(self._drag0)
            self.poly[self._vi] = p
            self._mask_key = None
            self._refresh_ui()
            self.canvas.viewport().update()

    def on_release(self, pos, event=None):
        p = (int(pos.x()), int(pos.y()))
        if self._drag_mode == "new":
            x0, x1 = sorted((self._press[0], p[0]))
            y0, y1 = sorted((self._press[1], p[1]))
            if x1 - x0 >= 1 and y1 - y0 >= 1:
                self.rect = (x0, y0, x1, y1)
                self._mask_key = None
                self._sync_spins()
                self._set_msg("窗口已就绪：拖手柄调整，Enter / 双击挖除")
                self._notify_window()
            else:
                self._set_msg("拖出一个矩形窗口（至少 2×2 格）")
        elif self._drag_mode in ("move", "resize", "vertex"):
            if self.mode == MODE_RECT and self.rect is not None:
                self._sync_spins()
                self._notify_window()
            self._set_msg("窗口已调整：Enter / 双击挖除")
        self._drag_mode = None
        self._drag0 = None
        self._press = None
        self._cur = None
        self._handle = None
        self._vi = None
        self.canvas.viewport().update()

    def on_right_click(self, pos, event=None):
        if self.mode == MODE_POLY and self._verts:
            self._close_poly()

    def on_double_click(self, pos, event=None):
        """双击画布 = 确认挖除（与 Enter 同效）。"""
        if self._verts:
            self._close_poly()
            return
        self._apply_all()

    def on_key(self, event):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if self._verts:
                self._close_poly()
            else:
                self._apply_all()
            return
        if key == Qt.Key_Backspace and self._verts:
            self._verts.pop()
            self._refresh_ui()
            self.canvas.viewport().update()

    def _close_poly(self):
        if len(self._verts) < 3:
            self._set_msg("多边形窗口至少需要 3 个顶点")
            return
        self.poly = list(self._verts)
        self._verts = []
        self._cursor = None
        self._mask_key = None
        self._refresh_ui()
        self._set_msg("窗口已就绪：拖顶点调整，Enter / 双击挖除")
        self.canvas.viewport().update()

    def cancel(self):
        self._reset_window()

    def deactivate(self):
        self._drag_mode = None
        self._verts = []
        self._cursor = None

    def _notify_window(self):
        """窗口最终确定后通知宿主（演示页回填参数用）。"""
        cb = self.window_changed
        if callable(cb) and self.rect is not None:
            cb(tuple(self.rect))

    # ---- 命中判定 ----
    @staticmethod
    def _near(p, q) -> bool:
        return abs(p[0] - q[0]) <= 1 and abs(p[1] - q[1]) <= 1

    def _rect_handle(self, p):
        """矩形窗口手柄命中：角/边中点返回名称，内部返回 'inside'。

        手柄画在框线上，右/下在闭区间外沿 x1+1 / y1+1——命中判定跟画的一致，
        否则"看得见却抓不住"。
        """
        x0, y0, x1, y1 = self.rect
        ox1, oy1 = x1 + 1, y1 + 1
        cx, cy = (x0 + ox1) / 2.0, (y0 + oy1) / 2.0
        handles = (("nw", x0, y0), ("n", cx, y0), ("ne", ox1, y0),
                   ("e", ox1, cy), ("se", ox1, oy1), ("s", cx, oy1),
                   ("sw", x0, oy1), ("w", x0, cy))
        for name, hx, hy in handles:
            if abs(p[0] - hx) <= _HANDLE_TOL and \
                    abs(p[1] - hy) <= _HANDLE_TOL:
                return name
        if x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
            return "inside"
        return None

    def _poly_vertex_hit(self, p):
        for i, v in enumerate(self.poly or []):
            if abs(p[0] - v[0]) <= 1 and abs(p[1] - v[1]) <= 1:
                return i
        return None

    # ------------------------------------------------------------------
    # 叠层：裁剪窗口（含手柄与确认提示）
    # ------------------------------------------------------------------
    def draw_overlay(self, painter):
        from core.shapes import SIM
        if self.mode == MODE_POLY:
            self._draw_poly_overlay(painter, SIM)
            return
        if self._drag_mode == "new" and self._press and self._cur:
            rx0, rx1 = sorted((self._press[0], self._cur[0]))
            ry0, ry1 = sorted((self._press[1], self._cur[1]))
        elif self.rect is not None:
            rx0, ry0, rx1, ry1 = self.rect
        else:
            return              # 窗口尚未定义：不画任何预设红框
        painter.setPen(QPen(CLIP_COLOR, 1, Qt.DashLine))
        painter.setBrush(QBrush(CLIP_FILL))
        painter.drawRect(rx0 * SIM, ry0 * SIM,
                         (rx1 - rx0 + 1) * SIM, (ry1 - ry0 + 1) * SIM)
        if not self._drag_mode:
            self._draw_rect_handles(painter, SIM, (rx0, ry0, rx1, ry1))
            self._draw_hint(painter, (rx0, ry0, rx1, ry1), SIM)

    def _draw_rect_handles(self, painter, SIM, r):
        x0, y0, x1, y1 = r
        # 手柄落在窗口框线上：右/下是闭区间外沿 (x1+1)/(y1+1)，
        # 用 x1 会缩进窗口内一格，和虚线框对不齐（用户反馈：边界显示）
        ox1, oy1 = x1 + 1, y1 + 1
        cx, cy = (x0 + ox1) / 2.0, (y0 + oy1) / 2.0
        pts = ((x0, y0), (cx, y0), (ox1, y0), (ox1, cy),
               (ox1, oy1), (cx, oy1), (x0, oy1), (x0, cy))
        painter.setPen(QPen(CLIP_COLOR, 1))
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        for x, y in pts:
            painter.drawRect(int(x * SIM) - 3, int(y * SIM) - 3, 6, 6)

    def _draw_poly_overlay(self, painter, SIM):
        """多边形窗口：闭合显示；布点中显示折线 + 到鼠标的橡皮筋。"""
        pts = self._verts if self._verts else (self.poly or [])
        if not pts:
            return
        poly = QPolygonF([QPointF(x * SIM, y * SIM) for x, y in pts])
        painter.setPen(QPen(CLIP_COLOR, 1, Qt.DashLine))
        if not self._verts:
            painter.setBrush(QBrush(CLIP_FILL))
            painter.drawPolygon(poly)          # 已闭合：整块半透明高亮
        else:
            painter.setBrush(Qt.NoBrush)
            painter.drawPolyline(poly)
            if self._cursor is not None:
                # 橡皮筋：最后一个点连到鼠标（正在布点）
                painter.setPen(QPen(CLIP_COLOR, 1, Qt.DotLine))
                painter.drawLine(QPointF(pts[-1][0] * SIM, pts[-1][1] * SIM),
                                 QPointF(self._cursor[0] * SIM,
                                         self._cursor[1] * SIM))
        painter.setPen(QPen(CLIP_COLOR, 1))
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        for x, y in pts:
            painter.drawRect(x * SIM - 3, y * SIM - 3, 6, 6)
        if not self._verts:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            self._draw_hint(painter, (min(xs), min(ys), max(xs), max(ys)), SIM)

    def _draw_hint(self, painter, bbox, SIM):
        """窗口下方提示：应用/演示模式都支持 Enter 直接挖除（可撤销）。"""
        text = ("拖动窗口 / 手柄调整 → Enter 播放判定后挖除"
                if self.preview_only
                else "Enter / 双击 挖除  ·  Esc 取消")
        f = QFont(painter.font())
        f.setPixelSize(11)
        f.setBold(True)
        painter.setFont(f)
        fm = QFontMetricsF(f)
        tw = fm.horizontalAdvance(text) + 14
        th = fm.height() + 6
        x = bbox[0] * SIM
        y = (bbox[3] + 1) * SIM + 8
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(229, 72, 77, 230)))
        painter.drawRoundedRect(QRectF(x, y, tw, th), 4, 4)
        painter.setPen(QPen(QColor("#FFFFFF")))
        painter.drawText(QRectF(x, y, tw, th), Qt.AlignCenter, text)

    # ------------------------------------------------------------------
    # 挖除执行（确认后才生效）
    # ------------------------------------------------------------------
    def _apply_all(self, keep_window: bool = False):
        # 演示页接管：先播判定动画，播完宿主再调回来（_hook_applying）真正挖除
        if not self._hook_applying and callable(self.confirm_hook) and \
                self.confirm_hook():
            return
        if not self.window_vertices():
            self._set_msg("请先定义裁剪窗口（矩形拖拽 / 多边形布点）")
            return
        mask = self.window_pixels()
        window = self.window_vertices()          # 几何窗口（世界坐标多边形）
        doc = self.canvas.document
        shapes = [s for s in doc.shapes if s.visible]
        entries = []                     # [(shape, before, after)]
        total = 0
        processed = {id(s) for s in shapes}

        for s in shapes:
            outline, fill = rasterize(s)
            hit = {p for p in outline if p in mask}
            hit.update(p for p in fill if p in mask)
            if not hit:
                continue
            before = snapshot(s)
            s.erased |= hit
            # 几何挖除区域：窗口多边形随图元一起变换（旋转/缩放后仍是
            # 干净的一块，不会像像素采样那样漏格 → 残留黑散点）
            s.cuts.append([(int(x), int(y)) for x, y in window])
            entries.append((s, before, snapshot(s)))
            total += len(hit)

        # 依附于被挖图元的油漆桶填充：同一窗口也要挖掉（像素一并纳入撤销快照）
        for f in doc.shapes:
            if not isinstance(f, RasterFillShape) or f.owner is None:
                continue
            if id(f.owner) not in processed or id(f) in processed:
                continue
            hit = {p for p in f.pixels if p in mask}
            if not hit:
                continue
            before = snapshot(f)
            f.erased |= hit
            f.cuts.append([(int(x), int(y)) for x, y in window])
            entries.append((f, before, snapshot(f)))
            total += len(hit)

        if not entries:
            self._set_msg("窗口内没有可挖除的图元像素")
            return

        # 整组挖除合成一条命令：Ctrl+Z 一次完整还原
        doc.do(ClipShapesCommand(doc, [], entries))
        self.canvas._render_base()
        self.canvas.document_changed.emit()
        # 演示页保留窗口（便于重播/继续调整），应用模式挖完即清除窗口
        if not keep_window and not self.preview_only:
            self._reset_window()
        self._set_msg(f"已挖除 {len(entries)} 个图元的窗口内部分"
                      f"（{total} 像素，Ctrl+Z 可撤销）")

    # ------------------------------------------------------------------
    # 裁剪执行（演示页播完）：裁去窗口【内】，保留窗口外
    # ------------------------------------------------------------------
    def apply_crop(self, subjects, rect, keep_window: bool = False):
        """区域裁剪：裁掉窗口【内】的像素，窗口外原样保留。

        与 _apply_all（窗口内消失的区域挖除）方向一致——本模块的"裁剪"
        就是挖掉窗口覆盖的那片区域；演示页的四页动画末帧也按同一口径，
        播完必须落到同一个结果上，否则动画和画布对不上。
        只作用于本次演示对象，画布上其它图元不受影响。
        返回 [(shape, before, after), ...] 供重播前还原。
        """
        if not subjects:
            self._set_msg("画布上没有可裁剪的图元")
            return []
        x0, y0, x1, y1 = rect

        def inside(p):
            return x0 <= p[0] <= x1 and y0 <= p[1] <= y1

        doc = self.canvas.document
        entries = []                     # [(shape, before, after)]
        total = 0
        for s in subjects:
            if not s.visible:
                continue
            outline, fill = rasterize(s)
            out = {p for p in set(outline) | set(fill) if inside(p)}
            if not out or out <= s.erased:
                continue
            before = snapshot(s)
            s.erased |= out
            # 几何挖除区域（窗口矩形）：随图元一起变换，旋转后仍是干净一块
            s.cuts.append([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
            entries.append((s, before, snapshot(s)))
            total += len(out)
        # 依附于被裁图元的油漆桶填充：一起按窗口裁剪
        ids = {id(s) for s in subjects}
        for f in doc.shapes:
            if not isinstance(f, RasterFillShape) or f.owner is None:
                continue
            if id(f.owner) not in ids:
                continue
            out = {p for p in f.pixels if inside(p)}
            if not out or out <= f.erased:
                continue
            before = snapshot(f)
            f.erased |= out
            f.cuts.append([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
            entries.append((f, before, snapshot(f)))
            total += len(out)

        if not entries:
            self._set_msg("裁剪完成：窗口内已无可裁部分")
            return []

        doc.do(ClipShapesCommand(doc, [], entries))
        self.canvas._render_base()
        self.canvas.document_changed.emit()
        # 播完/确认后红框必须消失：演示模式（preview_only）也不例外，
        # 否则裁剪结果已经落到画布上、红色窗口却还盖在上面
        if not keep_window:
            self._reset_window()
        self._set_msg(f"已裁剪 {len(entries)} 个图元：窗口内 {total} 像素已裁掉"
                      f"（保留窗口外，Ctrl+Z 可撤销）")
        return entries

    # ------------------------------------------------------------------
    # 全局回车入口（焦点在窗口参数框时，回车到不了画布）
    # ------------------------------------------------------------------
    def commit_window(self) -> bool:
        """主窗口回车路由调用：先把参数框内容写回窗口，再执行挖除。

        返回 False = 当前没有可确认的窗口（回车照常交给其它控件）。
        """
        if not self.window_vertices():
            return False
        if self.rect is not None and self._spins:
            for sb in self._spins.values():
                if self._alive(sb):
                    sb.interpretText()     # 正在编辑的坐标先落到窗口
        self._apply_all()
        return True
