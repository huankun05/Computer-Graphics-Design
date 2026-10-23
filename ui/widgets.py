# -*- coding: utf-8 -*-
"""
=====================================================================
 ui/widgets.py  —  自绘/精修通用控件（规范 4.5）
=====================================================================
Card             白卡片容器（圆角10 + 边框 + 标题行）
SegmentedControl 胶囊分段控件（应用模式/演示模式切换）
GradientSlider   渐变轨道滑块（归档同款：彩色渐变槽 + 白色圆钮）
TogglePill       "开/关"胶囊开关（视图卡用）
h_divider()      选项条竖分隔线
=====================================================================
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QWidget,
    QSizePolicy, QToolButton,
)

from ui import theme
from ui.icons import icon


class CollapsibleCard(QFrame):
    """可折叠白卡片：点击标题行收缩/展开（信息面板统一交互）。"""

    def __init__(self, title: str = "", expanded: bool = True, parent=None,
                 flat: bool = False, expands: bool = False):
        super().__init__(parent)
        # flat=True：无卡片边框（嵌在另一张卡内的分节用）
        # expands=True：展开时吸收剩余空间，收缩时降级为固定高度（不占位）
        self.setObjectName("flatCard" if flat else "card")
        self._expands = expands
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 10)
        root.setSpacing(6)

        # ---- 标题行（整行可点；右侧可挂扩展控件，如"清空"按钮） ----
        self._header_row = QHBoxLayout()
        self._header_row.setContentsMargins(0, 0, 0, 0)
        self._header_row.setSpacing(4)
        self.header = QPushButton(title)
        self.header.setObjectName("cardHeader")
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.setIcon(icon("chev-down" if expanded else "chev-up", size=14))
        self.header.clicked.connect(self.toggle)
        self._header_row.addWidget(self.header, stretch=1)
        root.addLayout(self._header_row)
        self._header_extra = None

        # ---- 内容体（透明：裸 QWidget 会被全局 QSS 涂成灰底直角块） ----
        self.body = QWidget()
        make_transparent(self.body)
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.body_lay.setSpacing(6)
        root.addWidget(self.body)
        self._expanded = expanded
        self.body.setVisible(expanded)
        if expands:
            from PySide6.QtWidgets import QSizePolicy
            self.setSizePolicy(QSizePolicy.Preferred,
                               QSizePolicy.Expanding if expanded
                               else QSizePolicy.Fixed)

    def set_header_extra(self, w: QWidget):
        """在标题行右侧挂一个小控件（如图元卡的"清空"按钮）。"""
        if self._header_extra is not None:
            self._header_row.removeWidget(self._header_extra)
            self._header_extra.deleteLater()
        self._header_extra = w
        self._header_row.addWidget(w)

    def toggle(self):
        self.set_expanded(not self._expanded)

    def set_expanded(self, on: bool):
        self._expanded = on
        self.body.setVisible(on)
        self.header.setIcon(icon("chev-down" if on else "chev-up", size=14))
        if self._expands:
            from PySide6.QtWidgets import QSizePolicy
            self.setSizePolicy(QSizePolicy.Preferred,
                               QSizePolicy.Expanding if on else QSizePolicy.Fixed)
        # 折叠时把卡片高度物理压到一条标题栏：全部折叠后应像"栅栏"
        # 一样紧凑并排堆在上方，而不是各自残留一块空白占位
        # （仅 body.setVisible(False) 不够——布局仍会给收起的卡留旧高度）
        if on:
            self.setMaximumHeight(16777215)          # QWIDGETSIZE_MAX
        else:
            marg = self.layout().contentsMargins()
            self.setMaximumHeight(self.header.sizeHint().height()
                                  + marg.top() + marg.bottom() + 4)


class Card(QFrame):
    """白卡片：标题 + 内容 VBox。（简单场合用；可折叠用 CollapsibleCard）"""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)
        if title:
            t = QLabel(title)
            t.setObjectName("cardTitle")
            lay.addWidget(t)
        self.body = lay

    @staticmethod
    def add_title(lay: QVBoxLayout, text: str):
        """在任意布局里插一个卡片标题（轻量场合用）。"""
        t = QLabel(text)
        t.setObjectName("cardTitle")
        lay.addWidget(t)


class SegmentedControl(QFrame):
    """胶囊分段控件。signal changed(int)：选中段索引。"""

    changed = Signal(int)

    def __init__(self, items: list, current: int = 0, parent=None):
        super().__init__(parent)
        self.setObjectName("segHolder")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self._buttons = []
        for i, text in enumerate(items):
            b = QPushButton(text)
            b.setObjectName("segBtn")
            b.setCheckable(True)
            b.setChecked(i == current)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, idx=i: self._on_click(idx))
            lay.addWidget(b)
            self._buttons.append(b)

    def _on_click(self, idx):
        # 单选语义：点击已选中项不重复发信号
        if not self._buttons[idx].isChecked():
            self._buttons[idx].setChecked(True)
            return
        for j, b in enumerate(self._buttons):
            b.setChecked(j == idx)
        self.changed.emit(idx)

    def set_current(self, idx: int):
        for j, b in enumerate(self._buttons):
            b.setChecked(j == idx)

    def set_enabled_at(self, idx: int, enabled: bool, tip: str = ""):
        """单独控制某一段的可用态（未开放的演示模块灰显）。"""
        self._buttons[idx].setEnabled(enabled)
        self._buttons[idx].setToolTip(tip)


class GradientSlider(QSlider):
    """渐变轨道滑块：qlineargradient 槽 + QSS 白色圆钮（theme 提供钮样式）。"""

    def __init__(self, stops: list, min_v=0, max_v=100, value=0, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.setRange(min_v, max_v)
        self.setValue(value)
        self.setFixedHeight(20)
        self.set_gradient(stops)

    def set_gradient(self, stops: list):
        """stops: 颜色列表（2~7 个），沿轨道从左到右渐变。"""
        n = len(stops)
        parts = []
        for i, c in enumerate(stops):
            if n == 1:
                parts.append(f"stop:0 {c}")
                break
            parts.append(f"stop:{i / (n - 1):.3f} {c}")
        self.setStyleSheet(
            "QSlider::groove:horizontal { height: 8px; border-radius: 4px; "
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            + ", ".join(parts) + "); }"
        )


def TogglePill(text_on="开", text_off="关", checked=True) -> QPushButton:
    """视图开关胶囊：选中态 accent 浅底，文字随状态切换。"""
    b = QPushButton(text_on if checked else text_off)
    b.setObjectName("toggleBtn")
    b.setCheckable(True)
    b.setChecked(checked)
    b.setFixedWidth(44)
    b.setCursor(Qt.PointingHandCursor)

    def _sync(checked_now):
        b.setText(text_on if checked_now else text_off)

    b.toggled.connect(_sync)
    return b


def h_divider() -> QFrame:
    """选项条里的 1px 竖分隔线。"""
    line = QFrame()
    line.setObjectName("optDivider")
    line.setFixedSize(1, 18)
    return line


def make_transparent(w: QWidget) -> QWidget:
    """让容器类 QWidget 自身透明（露出白卡片底色）。

    注意：裸 setStyleSheet("background:transparent") 会级联到全部子控件
    （Qt 样式表裸声明作用于自身+后代），必须用 objectName 选择器只作用自身。
    """
    w.setObjectName(f"transparent_{id(w):x}")
    w.setStyleSheet(f"QWidget#transparent_{id(w):x} {{ background: transparent; }}")
    return w


def stretch():
    """HBox/VBox 弹簧小工具（必须透明——裸 QWidget 会被全局 QSS 涂成灰底，
    在白色卡片里表现为"突兀的灰色蒙版直角块"）。"""
    s = QWidget()
    s.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    s.setStyleSheet("background: transparent;")
    return s
