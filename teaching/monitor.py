# -*- coding: utf-8 -*-
"""
=====================================================================
 teaching/monitor.py  —  决策项监视面板
=====================================================================
通用 key-value 监视器（规范 3.2）：表格行由"变量说明字典"决定——
  {"x": "x", "err": "误差项 err", "p": "决策项 p"}
每步 update(values, note) 刷新数值行 + 底部人话解释行。
键在当前步缺失时显示 "—"（如椭圆的区域 1 无 p2）。
=====================================================================
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QLabel, QVBoxLayout,
)

from ui import theme


class MonitorPanel(QFrame):
    """决策项监视器：变量名 | 当前值 行集 + 解释行。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 裸 QFrame 会被全局 QSS 涂成灰底直角块——透明化露出白卡片
        self.setObjectName(f"monitor_{id(self):x}")
        self.setStyleSheet(
            f"QFrame#monitor_{id(self):x} {{ background: transparent; }}")
        self._labels = {}                       # 键 → 值 QLabel
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
            val.setStyleSheet(
                f"font-family: {theme.MONO_FONT}; font-size: 12px; "
                f"color: {theme.ACCENT}; font-weight: bold;")
            self._grid.addWidget(name, row, 0)
            self._grid.addWidget(val, row, 1)
            self._labels[key] = val
        self.note_label.setText("")

    def update_values(self, values: dict, note: str = ""):
        """刷新一行决策状态（缺失键显示 —）。"""
        for key, label in self._labels.items():
            v = values.get(key, "—")
            label.setText(str(v))
        self.note_label.setText(note or "")

    def clear(self):
        for label in self._labels.values():
            label.setText("—")
        self.note_label.setText("")
