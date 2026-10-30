# -*- coding: utf-8 -*-
"""
=====================================================================
 modules/module03_transform2d/tools.py — 模块三：二维几何变换工具
=====================================================================
交互（选中即变换，全部走 3×3 仿射矩阵，整组一步撤销）：
  · 单击选中 / Shift+单击加选减选 / 空白拖拽框选
  · 包围盒内拖动 = 平移；8 方位手柄 = 缩放（按住 Shift 等比）；
    包围盒上方环形箭头 = 旋转（按住 Shift 吸附 15°）
  · 旋转/缩放的定点一律是"所选图元的包围盒中心"（任何图元都先被矩形框住）
  · 面板数值变换：平移 dx/dy（dy 正 = 向上）、旋转角、缩放百分比（等比）

拖拽变换时包围盒下方会实时显示角度/比例/位移读数。

圆/椭圆旋转时按椭圆协方差矩阵解析式重参数化（圆旋转即椭圆），
所以旋转任意角度轮廓都不失真（见 core/shapes.transform_shape）。
=====================================================================
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDoubleSpinBox, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QSpinBox, QVBoxLayout)

import math

from algorithms import transform2d as tf
from core.tool_base import ToolBase


def _enter_spin(base_cls):
    """数值框按回车即应用（不必再点右侧按钮），其余按键行为不变。"""

    class _EnterSpin(base_cls):
        def __init__(self, on_enter, parent=None):
            super().__init__(parent)
            self._on_enter = on_enter

        def keyPressEvent(self, e):
            if e.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.interpretText()          # 提交正在输入的文字
                if self._on_enter:
                    self._on_enter()
                e.accept()
                return
            super().keyPressEvent(e)

    return _EnterSpin


_EnterSpinBox = _enter_spin(QSpinBox)
_EnterDoubleSpinBox = _enter_spin(QDoubleSpinBox)


def _group(title: str):
    """面板里的一组（竖排：标题 + 一行控件）。"""
    box = QFrame()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("secondary")
    lay.addWidget(t)
    row = QHBoxLayout()
    row.setSpacing(6)
    lay.addLayout(row)
    return box, row


def _divider():
    """组间竖分隔线（与选项条同款 1px 细线），避免几组按钮看串。"""
    line = QLabel()
    line.setObjectName("optDivider")
    line.setFixedSize(1, 30)
    return line


class Transform2DTool(ToolBase):
    """选择 + 平移/旋转/缩放（支持多选、框选，定点为包围盒中心）。"""

    name = "二维变换"
    icon_name = "cursor"
    cursor_hint = ("单击选中 / Shift 加选 / 空白框选；拖包围盒内平移，"
                   "手柄缩放（Shift 等比），顶部箭头旋转（Shift 吸附 15°）")
    handles_shift_selection = True

    def __init__(self, canvas):
        super().__init__(canvas)
        self._rubber = False
        self._msg = None
        self._msg_text = ""
        # 面板"当前值"：本次选中以来的累计旋转角 / 累计缩放比例
        # （选中变化即归零，之后拖拽/输入都在这个基准上累加）
        self._cur_angle = 0.0
        self._cur_scale = 1.0
        # 面板控件（工具可能在演示模式下不带面板使用，统一置空防误访问）
        self._dx = None
        self._dy = None
        self._angle = None
        self._scale = None

    # ------------------------------------------------------------------
    # 画布交互：选择 / 框选
    # ------------------------------------------------------------------
    def on_press(self, pos, event=None):
        shift = bool(event.modifiers() & Qt.ShiftModifier) if event else False
        hit = self.canvas.hit_test(pos)
        if hit is None:
            if not shift:
                self.canvas.set_selection([])
            self.canvas.begin_rubber(pos, additive=shift)
            self._rubber = True
            return
        if shift:
            self.canvas.toggle_selected(hit)
        else:
            sel = self.canvas.selection
            if not any(hit is s for s in sel):
                self.canvas.set_selected_shape(hit)

    def on_move(self, pos, event=None):
        if self._rubber:
            self.canvas.update_rubber(pos)

    def on_release(self, pos, event=None):
        if self._rubber:
            self._rubber = False
            self.canvas.end_rubber()

    def cancel(self):
        self._rubber = False
        self.canvas.cancel_rubber()

    def status(self):
        n = len(self.canvas.selection)
        if n == 0:
            return "未选中图元：单击选择，Shift 加选，空白拖拽框选"
        return f"已选 {n} 个图元 · 定点 = 包围盒中心 · 拖动/手柄/面板均可变换"

    # ------------------------------------------------------------------
    # 专属面板：数值变换
    # ------------------------------------------------------------------
    def panel_widget(self):
        box = QFrame()
        box.setObjectName("transformPanel")
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        # --- 平移（dy 正 = 向上，与数学习惯一致；画布内部 y 向下由矩阵取负） ---
        g, row = _group("平移")
        self._dx = _EnterSpinBox(self._apply_translate)
        self._dx.setRange(-999, 999)
        self._dx.setValue(4)
        self._dx.setToolTip("水平位移（模拟像素格数，正数向右）；回车直接应用")
        self._dy = _EnterSpinBox(self._apply_translate)
        self._dy.setRange(-999, 999)
        self._dy.setValue(0)
        self._dy.setToolTip("垂直位移（正数向上，负数向下）；回车直接应用")
        for lab, w in (("dx", self._dx), ("dy", self._dy)):
            row.addWidget(QLabel(lab))
            row.addWidget(w)
        b = QPushButton("移动")
        b.setToolTip("按 dx/dy 平移选中图元（dy 正 = 向上）")
        b.clicked.connect(self._apply_translate)
        row.addWidget(b)
        lay.addWidget(g)
        lay.addWidget(_divider())

        # --- 旋转（定点 = 包围盒中心；显示当前累计角度，1° 一档） ---
        g, row = _group("旋转")
        self._angle = _EnterDoubleSpinBox(self._apply_rotate)
        self._angle.setRange(-360.0, 360.0)
        self._angle.setDecimals(0)
        self._angle.setSingleStep(1.0)       # -360°~360°，逐度可调
        self._angle.setValue(0.0)
        self._angle.setSuffix(" °")
        self._angle.setToolTip(
            "当前累计旋转角（选中后归零）；正角 = 顺时针，绕包围盒中心；回车直接应用")
        row.addWidget(self._angle)
        b = QPushButton("旋转")
        b.setToolTip("旋转到该角度（相对当前角度计算差值）")
        b.clicked.connect(self._apply_rotate)
        row.addWidget(b)
        lay.addWidget(g)
        lay.addWidget(_divider())

        # --- 缩放（单值 = 当前比例，按差值缩放） ---
        g, row = _group("缩放")
        self._scale = _EnterDoubleSpinBox(self._apply_scale)
        self._scale.setRange(5.0, 800.0)
        self._scale.setDecimals(0)
        self._scale.setSingleStep(1.0)
        self._scale.setValue(100.0)
        self._scale.setSuffix(" %")
        self._scale.setToolTip(
            "当前累计缩放比例（选中后回到 100%）；x/y 两轴同因子（等比），"
            "绕包围盒中心；回车直接应用")
        row.addWidget(self._scale)
        b = QPushButton("缩放")
        b.setToolTip("缩放到该百分比（相对当前比例计算差值，保持长宽比）")
        b.clicked.connect(self._apply_scale)
        row.addWidget(b)
        lay.addWidget(g)

        # 操作反馈与用法提示共用一格（宽度稳定，不会把面板撑开）
        self._msg = QLabel("Shift+手柄=两轴同因子（长宽比不变）")
        self._msg.setObjectName("optHint")
        lay.addWidget(self._msg)
        lay.addStretch()

        # 拖拽变换结束 → 回填"当前值"；换选 → 基准归零
        self.canvas.transform_dragged.connect(self._on_dragged)
        self.canvas.selection_changed.connect(self._on_selection_changed)
        return box

    # ---- 当前值回填 ----
    @staticmethod
    def _alive(w) -> bool:
        """面板控件是否仍存活（切走工具后面板被销毁，信号回调不能再碰）。"""
        if w is None:
            return False
        try:
            from shiboken6 import isValid
            return isValid(w)
        except Exception:
            return True

    def _on_dragged(self, mode: str, a: float, b: float):
        """画布拖拽结束后把最新角度/比例写回面板。"""
        if mode == "rotate":
            # 归一到 (-180, 180]，避免连续旋转后跳出输入框范围
            self._cur_angle = (self._cur_angle + a + 180.0) % 360.0 - 180.0
            if not self._alive(self._angle):
                return
            self._angle.blockSignals(True)
            self._angle.setValue(round(self._cur_angle))
            self._angle.blockSignals(False)
        else:
            # 非等比拖拽用几何平均代表整体比例（面板只有单值）
            f = math.sqrt(max(1e-6, abs(a) * abs(b)))
            self._cur_scale = min(8.0, max(0.05, self._cur_scale * f))
            if not self._alive(self._scale):
                return
            self._scale.blockSignals(True)
            self._scale.setValue(round(self._cur_scale * 100.0))
            self._scale.blockSignals(False)

    def _on_selection_changed(self, _shape=None):
        """换选后"当前值"重新以 0° / 100% 为基准。"""
        self._cur_angle = 0.0
        self._cur_scale = 1.0
        if self._alive(self._angle):
            self._angle.blockSignals(True)
            self._angle.setValue(0.0)
            self._angle.blockSignals(False)
        if self._alive(self._scale):
            self._scale.blockSignals(True)
            self._scale.setValue(100.0)
            self._scale.blockSignals(False)

    def _set_msg(self, text: str):
        """面板内操作反馈（成功/未选中/无变化都明确提示）。"""
        self._msg_text = text
        if self._alive(self._msg):
            self._msg.setText(text)

    # ---- 三个应用按钮 → 统一走 canvas.transform_selection ----
    def _apply_translate(self):
        if not self.canvas.selection:
            self._set_msg("请先选中图元")
            return
        dx, dy = self._dx.value(), self._dy.value()
        if dx == 0 and dy == 0:
            self._set_msg("dx/dy 均为 0")
            return
        # 面板约定 dy 正 = 向上；画布 y 轴向下，故矩阵里取负
        ok = self.canvas.transform_selection(
            tf.translation(dx, -dy), "平移图元")
        self._set_msg(f"已移动 dx={dx}, dy={dy}（↑）" if ok
                      else "几何无变化")

    def _apply_rotate(self):
        if not self.canvas.selection:
            self._set_msg("请先选中图元")
            return
        target = self._angle.value()
        delta = target - self._cur_angle       # 输入的是目标角 → 只转差值
        if abs(delta) < 1e-6:
            self._set_msg(f"当前就是 {target:g}°")
            return
        piv = self.canvas.pivot_point()
        if piv is None:
            return
        ok = self.canvas.transform_selection(
            tf.around(piv, tf.rotation(delta)), "旋转图元")
        if ok:
            self._cur_angle = target
            self._set_msg(f"当前角度 {target:g}°（绕包围盒中心）")
        else:
            self._set_msg("旋转后无变化")

    def _apply_scale(self):
        if not self.canvas.selection:
            self._set_msg("请先选中图元")
            return
        target = self._scale.value() / 100.0
        factor = target / self._cur_scale if self._cur_scale > 0 else 1.0
        if abs(factor - 1.0) < 1e-6:
            self._set_msg(f"当前就是 {target * 100:g}%")
            return
        piv = self.canvas.pivot_point()
        if piv is None:
            return
        ok = self.canvas.transform_selection(
            tf.around(piv, tf.scaling(factor, factor)), "缩放图元")
        if ok:
            self._cur_scale = target
            self._set_msg(f"当前比例 {target * 100:g}%（等比）")
        else:
            self._set_msg("几何无变化")
