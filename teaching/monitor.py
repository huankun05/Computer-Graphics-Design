# -*- coding: utf-8 -*-
"""
=====================================================================
 teaching/monitor.py  —  决策项监视面板
=====================================================================
通用 key-value 监视器（规范 3.2）：表格行由"变量说明字典"决定——
  {"x": "x", "err": "误差项 err", "p": "决策项 p"}
每步 update(values, note) 刷新数值行 + 底部人话解释行。
键在当前步缺失时显示 "—"（如椭圆的区域 1 无 p2）。

值若是数值矩阵（如变换页的 3×3 仿射矩阵），该行改用 MatrixView
矢量绘制：方括号 + 等宽右对齐的数值列，不再挤成一行字符串。
=====================================================================
"""

from PySide6.QtCore import Qt, QPointF, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from ui import theme


class MatrixView(QWidget):
    """矩阵矢量图：方括号 + 按列右对齐的等宽数值。

    不用 Unicode 的 ⎡⎢⎣ 字形——Consolas 没有这些码位，回退字体后
    括号与数字常对不齐；这里方括号用 QPainter 画线，数字用等宽字体。
    行/列任意，单元格接受 str 或数字（数字按 2 位小数格式化）。
    """

    _GAP = 12          # 列间距
    _ARM = 6           # 方括号横臂长度
    _PAD = 6           # 方括号与首/末列间距
    _LINE_H = 18

    def __init__(self, parent=None, text_color: str = "", size: int = 12,
                 indent: int = 0):
        super().__init__(parent)
        self.setObjectName(f"matrix_{id(self):x}")
        self.setStyleSheet(
            f"QWidget#matrix_{id(self):x} {{ background: transparent; }}")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._rows: list = []
        self._x0 = 2 + indent                     # 左缩进（公式卡里略缩进）
        self._color = QColor(text_color or theme.ACCENT)
        font = QFont()
        font.setFamilies(["Consolas", "Courier New", "monospace"])
        font.setPixelSize(size)
        self._font = font

    # ------------------------------------------------------------------
    def set_rows(self, rows):
        """rows = [[单元格, …], …]；数字保留 2 位小数，字符串原样。"""
        self._rows = [[f"{c:.2f}" if isinstance(c, float) else str(c)
                       for c in row] for row in rows]
        self.updateGeometry()
        self.update()

    def _cols_widths(self):
        fm = QFontMetrics(self._font)
        cols = max((len(r) for r in self._rows), default=0)
        widths = [max((fm.horizontalAdvance(r[c]) for r in self._rows
                       if c < len(r)), default=0) for c in range(cols)]
        return cols, widths

    def sizeHint(self) -> QSize:
        cols, widths = self._cols_widths()
        if cols == 0:
            return QSize(0, 0)
        w = sum(widths) + self._GAP * (cols - 1) + 2 * (self._ARM + self._PAD)
        h = len(self._rows) * self._LINE_H + 6
        return QSize(int(w) + self._x0 + 2, int(h))

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    # ------------------------------------------------------------------
    def paintEvent(self, _e):
        if not self._rows:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setFont(self._font)
        cols, widths = self._cols_widths()
        block_w = sum(widths) + self._GAP * (cols - 1)
        x_left = float(self._x0)
        x_content = x_left + self._ARM + self._PAD
        top = (self.height() - len(self._rows) * self._LINE_H) / 2.0
        bottom = top + len(self._rows) * self._LINE_H

        # ---- 方括号：竖线 + 上下横臂（左括号朝右、右括号朝左）----
        p.setPen(QPen(QColor(theme.TEXT_2), 1.2))
        for left in (True, False):
            x = x_left if left else x_content + block_w + self._PAD
            arm = self._ARM if left else -self._ARM
            p.drawLine(QPointF(x, top), QPointF(x, bottom))
            p.drawLine(QPointF(x, top), QPointF(x + arm, top))
            p.drawLine(QPointF(x, bottom), QPointF(x + arm, bottom))

        # ---- 单元格：按列右对齐，行内垂直居中 ----
        p.setPen(self._color)
        cx = x_content
        for c in range(cols):
            for r, row in enumerate(self._rows):
                if c >= len(row):
                    continue
                p.drawText(QRectF(cx, top + r * self._LINE_H,
                                  widths[c], self._LINE_H),
                           Qt.AlignRight | Qt.AlignVCenter, row[c])
            cx += widths[c] + self._GAP


def _matrix_rows(v):
    """把"数值矩形矩阵"转成字符串行；不是矩阵则返回 None。

    只认至少 2×2、每行等长、全为 int/float 的序列——避免把其它
    模块里的普通列表值误当矩阵（那些值本来就是展示文本）。
    """
    if not isinstance(v, (list, tuple)) or len(v) < 2:
        return None
    if not all(isinstance(r, (list, tuple)) for r in v):
        return None
    cols = len(v[0])
    if cols < 2 or any(len(r) != cols for r in v):
        return None
    if not all(isinstance(c, (int, float)) for r in v for c in r):
        return None
    return [[f"{c:.2f}" for c in r] for r in v]


class MonitorPanel(QFrame):
    """决策项监视器：变量名 | 当前值 行集 + 解释行。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 裸 QFrame 会被全局 QSS 涂成灰底直角块——透明化露出白卡片
        self.setObjectName(f"monitor_{id(self):x}")
        self.setStyleSheet(
            f"QFrame#monitor_{id(self):x} {{ background: transparent; }}")
        self._labels = {}                       # 键 → (值 QLabel, MatrixView)
        self._grid = QGridLayout()
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(12)
        self._grid.setVerticalSpacing(4)
        self._grid.setColumnMinimumWidth(0, 92)   # 变量名对齐
        self._grid.setColumnStretch(1, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        root.addLayout(self._grid)

        self.note_label = QLabel("")
        self.note_label.setObjectName("secondary")
        self.note_label.setWordWrap(True)
        root.addWidget(self.note_label)

    # ------------------------------------------------------------------
    def set_desc(self, desc: dict):
        """按变量说明字典重建行集（切换演示页时调用）。"""
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._labels.clear()
        for row, (key, cn) in enumerate(desc.items()):
            name = QLabel(cn if cn else key)
            name.setObjectName("secondary")
            val = QLabel("—")
            val.setObjectName("mono")
            val.setWordWrap(True)       # 长值（交点列表/情形统计）换行不撑破面板
            val.setStyleSheet(
                f"font-family: {theme.MONO_FONT}; font-size: 12px; "
                f"color: {theme.ACCENT}; font-weight: bold;")
            mat = MatrixView(self)
            mat.setVisible(False)
            self._grid.addWidget(name, row, 0)
            self._grid.addWidget(val, row, 1)
            self._grid.addWidget(mat, row, 1)   # 与 val 同格：按值类型二选一
            self._labels[key] = (val, mat)
        self.note_label.setText("")

    def update_values(self, values: dict, note: str = ""):
        """刷新一行决策状态（缺失键显示 —；矩阵值画成矩阵）。"""
        for key, (label, mat) in self._labels.items():
            v = values.get(key, "—")
            rows = _matrix_rows(v)
            if rows is None:
                label.setText(str(v))
                label.setVisible(True)
                mat.setVisible(False)
            else:
                mat.set_rows(rows)
                mat.setVisible(True)
                label.setVisible(False)
        self.note_label.setText(note or "")

    def clear(self):
        for label, mat in self._labels.values():
            mat.setVisible(False)
            label.setText("—")
            label.setVisible(True)
        self.note_label.setText("")
