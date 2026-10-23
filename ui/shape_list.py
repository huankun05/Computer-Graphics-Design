# -*- coding: utf-8 -*-
"""
=====================================================================
 ui/shape_list.py  —  图元列表面板（应用模式"图层"卡的主体）
=====================================================================
对标主流画板的图层面板（轻量版）：
  - 每行 = 一个图元：类型图标（按图元颜色染色）+ 名称
    + 眼睛开关（显隐）+ 删除钮；
  - 单击行 → 画布上显示虚线包围盒（选中态）；
  - 列表最新图元在最上（与 PS 图层一致：顶层 = 后画的）；
  - 删除/显隐都作用于 canvas（走命令/重绘），面板自身不持有状态。
面板在 canvas.document_changed / shape_count_changed 时整表重建。
=====================================================================
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QToolButton, QStackedWidget,
)

from ui import theme
from ui.icons import icon
from core.shapes import (
    LineShape, CircleShape, EllipseShape, PolygonShape,
)

# 图元 kind → 图标名 + 中文名（列表显示用）
_CLOSED_KINDS = {"circle", "circle_mid", "circle_dda", "ellipse", "polygon"}

_KIND_META = {
    "line_dda":       ("line", "DDA 直线"),
    "line_bresenham": ("line", "Bresenham 直线"),
    "circle":         ("circle", "中点圆"),
    "circle_mid":     ("circle", "中点圆"),
    "circle_dda":     ("circle", "DDA 圆"),
    "raster_fill":    ("fill", "种子填充区域"),
    "ellipse":        ("ellipse", "中点椭圆"),
    "polygon":        ("polygon", "扫描线填充"),
}


class ShapeListPanel(QWidget):
    """图元列表卡片内容。绑定一个 CanvasView 使用。"""

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self._syncing = False          # 防止重建列表时递归触发信号
        self.setObjectName("shapeListPanel")   # 不在白卡片里露灰底
        self.setStyleSheet(
            "QWidget#shapeListPanel { background: transparent; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        # 空状态提示 / 列表 二选一显示
        from ui.widgets import make_transparent
        self.stack = QStackedWidget()
        make_transparent(self.stack)       # 裸 QStackedWidget 也会被涂灰
        self.list = QListWidget()
        self.list.setObjectName("shapeList")
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.currentRowChanged.connect(self._on_row_selected)
        # 画布侧选中（选择工具/列表 双向联动）
        canvas.selection_changed.connect(self._on_canvas_selection)
        self.empty_label = QLabel("画布为空\n\n选择左侧工具开始绘制")
        self.empty_label.setObjectName("secondary")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.stack.addWidget(self.empty_label)   # index 0
        self.stack.addWidget(self.list)          # index 1
        root.addWidget(self.stack)

    # ------------------------------------------------------------------
    def rebuild(self):
        """整表重建（文档变化时调用）。保持原选中项（若还存在）。"""
        if self._syncing:
            return
        self._syncing = True
        try:
            prev = self.canvas._selected_shape
            self.list.clear()
            shapes = self.canvas.document.shapes
            # 最上层（后画的）显示在最前
            for idx in range(len(shapes) - 1, -1, -1):
                self._add_row(idx, shapes[idx])
            self.stack.setCurrentWidget(self.list if shapes else self.empty_label)
            # 恢复选中
            if prev is not None and prev in shapes:
                self.list.setCurrentRow(len(shapes) - 1 - shapes.index(prev))
            else:
                self.canvas.set_selected_shape(None)
                self.list.setCurrentRow(-1)
        finally:
            self._syncing = False

    def _add_row(self, idx: int, shape):
        """构造一行：图标 + 名称 + 眼睛 + 删除。"""
        item = QListWidgetItem()
        item.setData(Qt.UserRole, idx)
        self.list.addItem(item)

        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(8, 3, 4, 3)
        lay.setSpacing(6)

        icon_name, cn_name = _KIND_META.get(shape.kind, ("sparkle", shape.kind))
        ic = QLabel()
        ic.setPixmap(icon(icon_name, color=shape.color.name(), size=16).pixmap(16, 16))
        lay.addWidget(ic)

        name = QLabel(f"{cn_name} {idx + 1}")
        if not shape.visible:
            name.setStyleSheet(f"color:{theme.TEXT_3};")
        lay.addWidget(name)
        lay.addStretch()

        # 填充⇄描边切换（仅闭合图元显示）
        if shape.kind in _CLOSED_KINDS:
            fill_btn = QToolButton()
            fill_btn.setObjectName("headerBtn")
            fill_btn.setToolTip("填充 / 描边")
            fill_btn.setFixedSize(22, 22)
            fill_btn.setCursor(Qt.PointingHandCursor)

            def _fill_icon(filled: bool, col: str):
                from PySide6.QtGui import QColor as _QC
                return icon("fill", color=col if filled else theme.TEXT_3, size=15)

            fill_btn.setIcon(_fill_icon(shape.fill, shape.color.name()))
            fill_btn.clicked.connect(lambda _=False, i=idx, b=fill_btn:
                                     self._toggle_fill(i, b))
            lay.addWidget(fill_btn)

        # 眼睛开关（显隐）
        eye = QToolButton()
        eye.setObjectName("headerBtn")
        eye.setIcon(icon("eye" if shape.visible else "eye-off",
                         size=15))
        eye.setFixedSize(22, 22)
        eye.setToolTip("显示/隐藏")
        eye.clicked.connect(lambda _=False, i=idx: self._toggle_visible(i))
        lay.addWidget(eye)

        # 删除
        trash = QToolButton()
        trash.setObjectName("headerBtn")
        trash.setIcon(icon("trash", color=theme.TEXT_2, size=15))
        trash.setFixedSize(22, 22)
        trash.setToolTip("删除")
        trash.clicked.connect(lambda _=False, i=idx: self._remove(i))
        lay.addWidget(trash)

        self.list.setItemWidget(item, row)

    # ------------------------------------------------------------------
    def _on_row_selected(self, row):
        if self._syncing:
            return
        shapes = self.canvas.document.shapes
        if row < 0 or row >= self.list.count():
            self.canvas.set_selected_shape(None)
            return
        idx = self.list.item(row).data(Qt.UserRole)
        self.canvas.set_selected_shape(shapes[idx])

    def _on_canvas_selection(self, shape):
        """画布选中 → 列表高亮对应行（选择工具点选时）。"""
        if self._syncing:
            return
        shapes = self.canvas.document.shapes
        self._syncing = True
        try:
            if shape is not None and shape in shapes:
                self.list.setCurrentRow(len(shapes) - 1 - shapes.index(shape))
            else:
                self.list.setCurrentRow(-1)
        finally:
            self._syncing = False

    def _toggle_fill(self, idx: int, btn):
        """行内 填充⇄描边 切换（走命令栈，可撤销）。"""
        shape = self.canvas.document.shapes[idx]
        self.canvas.set_shape_fill(shape, not shape.fill)
        self.rebuild()

    def _toggle_visible(self, idx: int):
        shape = self.canvas.document.shapes[idx]
        shape.visible = not shape.visible
        self.canvas._render_base()          # 隐藏只是不画，不进撤销栈（轻操作）
        self.rebuild()

    def _remove(self, idx: int):
        shape = self.canvas.document.shapes[idx]
        if self.canvas._selected_shape is shape:
            self.canvas.set_selected_shape(None)
        self.canvas.remove_shape(shape)      # 走命令栈，可撤销
