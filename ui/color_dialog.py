# -*- coding: utf-8 -*-
"""
=====================================================================
 ui/color_dialog.py  —  RGB/HSV 联动选色对话框（v2 分区版）
=====================================================================
布局（四个分区，消除堆叠混乱）：
  ① 选色区      HSV 二维色板 + 色相条（点击/拖拽连续选色）
  ② 当前颜色    预览块 + HEX 字段
                HEX 交互：单击=复制到剪贴板；双击=进入编辑；
                          回车=跳转到对应颜色；Esc/失焦=还原
  ③ 数值微调    RGB（左列）与 HSV（右列）滑块并排，双向实时联动
  ④ 预设颜色    十个常用色格
=====================================================================
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSlider, QLabel, QPushButton,
    QGridLayout, QFrame, QLineEdit, QApplication, QToolTip,
)

from ui import theme
from ui.color_table import ColorTable


# ---------------------------------------------------------------------
# HEX 字段：单击复制 / 双击编辑 / 回车应用 / Esc与失焦还原
# ---------------------------------------------------------------------
class HexField(QLineEdit):
    """只读展示 HEX；双击进入编辑，回车应用，单击复制。"""

    def __init__(self, get_color, apply_color, parent=None):
        super().__init__(parent)
        self._get_color = get_color
        self._apply_color = apply_color
        self._editing = False
        self.setReadOnly(True)
        self.setObjectName("hexField")
        self.setCursor(Qt.PointingHandCursor)

    # ---- 状态切换 ----
    def update_text(self, text: str):
        """外部刷新显示（编辑中不打断用户输入）。"""
        if not self._editing:
            self.setText(text)

    def _enter_edit(self):
        self._editing = True
        self.setReadOnly(False)
        self.setCursor(Qt.IBeamCursor)
        self.selectAll()
        self.setFocus()

    def _exit_edit(self, apply: bool):
        if not self._editing:
            return
        self._editing = False
        self.setReadOnly(True)
        self.setCursor(Qt.PointingHandCursor)
        if apply:
            c = self._parse(self.text())
            if c.isValid():
                self._apply_color(c)
        self.update_text(self._get_color().name().upper())

    @staticmethod
    def _parse(text: str) -> QColor:
        t = text.strip().lstrip("#")
        if len(t) == 3:
            t = "".join(ch * 2 for ch in t)
        ok = len(t) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in t)
        return QColor("#" + t) if ok else QColor()

    # ---- 事件 ----
    onCopied = None   # 回调：复制后由宿主展示内联反馈

    def mousePressEvent(self, e):
        if self.isReadOnly():
            # 单击：复制 HEX 到剪贴板
            QApplication.clipboard().setText(self.text())
            if callable(self.onCopied):
                self.onCopied(f"已复制 {self.text()}")
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if self.isReadOnly():
            self._enter_edit()
            e.accept()
            return
        super().mouseDoubleClickEvent(e)

    def keyPressEvent(self, e):
        if self._editing:
            if e.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._exit_edit(apply=True)
                e.accept()
                return
            if e.key() == Qt.Key_Escape:
                self._exit_edit(apply=False)
                e.accept()
                return
        super().keyPressEvent(e)

    def focusOutEvent(self, e):
        self._exit_edit(apply=False)
        super().focusOutEvent(e)


def _sec_label(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setStyleSheet(
        f"color: {theme.ACCENT}; font-size: 12px; font-weight: bold; "
        f"background: transparent;")
    return lab


class ColorDialog(QDialog):
    def __init__(self, initial: QColor, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择颜色（RGB / HSV 联动）")
        self.setMinimumWidth(560)
        self._r, self._g, self._b = initial.red(), initial.green(), initial.blue()
        self._updating = False

        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ================= ① 选色区 =================
        root.addWidget(_sec_label("① 选色区（点击 / 拖拽）"))
        self.color_table = ColorTable(QColor(self._r, self._g, self._b))
        self.color_table.colorChanged.connect(self._on_table_pick)
        root.addWidget(self.color_table)

        # ================= ② 当前颜色 + HEX =================
        root.addWidget(_sec_label(
            "② 当前颜色与 HEX（单击复制 · 双击编辑 · 回车应用）"))
        cur_row = QHBoxLayout()
        self.preview = QFrame()
        self.preview.setFixedHeight(36)
        cur_row.addWidget(self.preview, stretch=1)
        self.hex_edit = HexField(lambda: QColor(self._r, self._g, self._b),
                                 self._apply_hex)
        self.hex_edit.setFixedWidth(150)
        self.hex_edit.setObjectName("mono")
        self.hex_edit.onCopied = self.show_copy_feedback
        cur_row.addWidget(self.hex_edit)
        self.copy_feedback = QLabel("")
        self.copy_feedback.setStyleSheet(
            f"color: {theme.SUCCESS}; background: transparent; font-size: 12px;")
        cur_row.addWidget(self.copy_feedback)
        root.addLayout(cur_row)

        # ================= ③ 数值微调（RGB | HSV 并排） =================
        root.addWidget(_sec_label("③ 数值微调"))
        cols = QHBoxLayout()
        cols.setSpacing(16)

        rgb_col = QVBoxLayout()
        rgb_head = QLabel("<b>RGB（0~255）</b>")
        rgb_head.setStyleSheet("background: transparent;")
        rgb_col.addWidget(rgb_head)
        self.sliders = {}
        rgb_grid = QGridLayout()
        for i, (name, val, color) in enumerate([
                ("R", self._r, theme.CH_R),
                ("G", self._g, theme.CH_G),
                ("B", self._b, theme.CH_B)]):
            lab = QLabel(name)
            sld = QSlider(Qt.Horizontal)
            sld.setRange(0, 255)
            sld.setValue(val)
            sld.setStyleSheet(
                f"QSlider::groove:horizontal{{background:{color};height:6px;"
                f"border-radius:3px;}}")
            val_lab = QLabel(str(val))
            val_lab.setObjectName("mono")
            val_lab.setFixedWidth(34)
            val_lab.setAlignment(Qt.AlignRight)
            sld.valueChanged.connect(lambda v, n=name, l=val_lab:
                                     self._on_rgb(n, v, l))
            rgb_grid.addWidget(lab, i, 0)
            rgb_grid.addWidget(sld, i, 1)
            rgb_grid.addWidget(val_lab, i, 2)
            self.sliders[name] = (sld, val_lab)
        rgb_col.addLayout(rgb_grid)
        cols.addLayout(rgb_col)

        hsv_col = QVBoxLayout()
        hsv_head = QLabel("<b>HSV（0~360 / 0~100）</b>")
        hsv_head.setStyleSheet("background: transparent;")
        hsv_col.addWidget(hsv_head)
        self.hsv_sliders = {}
        hsv_grid = QGridLayout()
        h, s, v = rgb_to_hsv(self._r, self._g, self._b)
        for i, (name, val, rng, color) in enumerate([
                ("H", int(h), 359, theme.CH_H),
                ("S", int(s * 100), 100, theme.CH_S),
                ("V", int(v * 100), 100, theme.CH_V)]):
            lab = QLabel(name)
            sld = QSlider(Qt.Horizontal)
            sld.setRange(0, rng)
            sld.setValue(val)
            sld.setStyleSheet(
                f"QSlider::groove:horizontal{{background:{color};height:6px;"
                f"border-radius:3px;}}")
            val_lab = QLabel(str(val))
            val_lab.setObjectName("mono")
            val_lab.setFixedWidth(34)
            val_lab.setAlignment(Qt.AlignRight)
            sld.valueChanged.connect(lambda v2, n=name, l=val_lab:
                                     self._on_hsv(n, v2, l))
            hsv_grid.addWidget(lab, i, 0)
            hsv_grid.addWidget(sld, i, 1)
            hsv_grid.addWidget(val_lab, i, 2)
            self.hsv_sliders[name] = (sld, val_lab, rng)
        hsv_col.addLayout(hsv_grid)
        cols.addLayout(hsv_col)
        root.addLayout(cols)

        # ================= ④ 预设颜色 =================
        root.addWidget(_sec_label("④ 预设颜色"))
        preset_row = QHBoxLayout()
        for hexc in ["#FFFFFF", "#C0C4CC", "#8A919F", "#222222",
                     "#E5484D", "#F76B15", "#F5D90A", "#46A758",
                     "#3E63DD", "#8E4EC6"]:
            btn = QPushButton()
            btn.setFixedSize(30, 26)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(hexc)
            btn.setStyleSheet(
                f"background:{hexc};border:1px solid {theme.BORDER};"
                f"border-radius:4px;")
            btn.clicked.connect(lambda _=False, c=hexc: self._set_rgb(QColor(c)))
            preset_row.addWidget(btn)
        root.addLayout(preset_row)

        # ================= 按钮 =================
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok = QPushButton("确定")
        ok.setObjectName("primaryBtn")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        root.addLayout(btn_row)

        self._refresh_ui()

        # 反馈定时器（复制提示 1.2s 自动消失）
        from PySide6.QtCore import QTimer
        self._fb_timer = QTimer(self)
        self._fb_timer.setSingleShot(True)
        self._fb_timer.setInterval(1200)
        self._fb_timer.timeout.connect(lambda: self.copy_feedback.setText(""))

    def mousePressEvent(self, e):
        # 点击对话框任意处 → HEX 脱离编辑状态（还原未提交输入）
        if getattr(self, "hex_edit", None) is not None:
            self.hex_edit._exit_edit(apply=False)
        super().mousePressEvent(e)

    def show_copy_feedback(self, text: str):
        self.copy_feedback.setText(text)
        self._fb_timer.start()

    # ------------------------------------------------------------------
    def _on_table_pick(self, c: QColor):
        self._set_rgb(c)

    def _apply_hex(self, c: QColor):
        self._set_rgb(c)

    def _on_rgb(self, name, v, lab):
        if self._updating:
            return
        lab.setText(str(v))
        setattr(self, f"_{name.lower()}", v)
        self._refresh_ui()

    def _on_hsv(self, name, v, lab):
        if self._updating:
            return
        lab.setText(str(v))
        h = self.hsv_sliders["H"][0].value()
        s = self.hsv_sliders["S"][0].value() / 100.0
        vv = self.hsv_sliders["V"][0].value() / 100.0
        self._r, self._g, self._b = hsv_to_rgb(h, s, vv)
        self._refresh_ui()

    def _set_rgb(self, c: QColor):
        self._r, self._g, self._b = c.red(), c.green(), c.blue()
        self._refresh_ui()

    def _set_sliders(self, c: QColor):
        """颜色同步到 RGB/HSV 滑块（屏蔽信号，避免递归）。"""
        for name, val in (("R", c.red()), ("G", c.green()), ("B", c.blue())):
            sld, val_lab = self.sliders[name]
            sld.blockSignals(True)
            sld.setValue(val)
            val_lab.setText(str(val))
            sld.blockSignals(False)
        h, s, v = rgb_to_hsv(c.red(), c.green(), c.blue())
        for name, val in (("H", int(h)), ("S", int(s * 100)), ("V", int(v * 100))):
            sld, val_lab, _rng = self.hsv_sliders[name]
            sld.blockSignals(True)
            sld.setValue(val)
            val_lab.setText(str(val))
            sld.blockSignals(False)

    def _refresh_ui(self):
        self._updating = True
        color = QColor(self._r, self._g, self._b)
        self.preview.setStyleSheet(
            f"background:{color.name()};border:1px solid {theme.BORDER};"
            f"border-radius:6px;")
        self._set_sliders(color)
        h, s, v = rgb_to_hsv(self._r, self._g, self._b)
        self.preview.setToolTip(
            f"RGB({self._r},{self._g},{self._b})  "
            f"HSV({int(h)}°,{int(s*100)}%,{int(v*100)}%)")
        if getattr(self, "color_table", None) is not None:
            self.color_table.set_color(color)
        if getattr(self, "hex_edit", None) is not None:
            self.hex_edit.update_text(color.name().upper())
        self._updating = False

    def selected_color(self) -> QColor:
        return QColor(self._r, self._g, self._b)


# ---------------------------------------------------------------------
# RGB → HSV（本文件滑块联动用；课程版算法在 algorithms/color_convert）
# ---------------------------------------------------------------------
def rgb_to_hsv(r: int, g: int, b: int):
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(rf, gf, bf), min(rf, gf, bf)
    df = mx - mn
    if df < 1e-6:
        h = 0.0
    elif mx == rf:
        h = (60 * ((gf - bf) / df) + 360) % 360
    elif mx == gf:
        h = (60 * ((bf - rf) / df) + 120) % 360
    else:
        h = (60 * ((rf - gf) / df) + 240) % 360
    s = 0.0 if mx < 1e-6 else df / mx
    return h, s, mx


def hsv_to_rgb(h: float, s: float, v: float):
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c
    if h < 60:
        rp, gp, bp = c, x, 0
    elif h < 120:
        rp, gp, bp = x, c, 0
    elif h < 180:
        rp, gp, bp = 0, c, x
    elif h < 240:
        rp, gp, bp = 0, x, c
    elif h < 300:
        rp, gp, bp = x, 0, c
    else:
        rp, gp, bp = c, 0, x
    return int((rp + m) * 255), int((gp + m) * 255), int((bp + m) * 255)
