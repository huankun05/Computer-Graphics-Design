# -*- coding: utf-8 -*-
"""
=====================================================================
 modules/module01_color/module.py — 模块一声明：颜色模型
=====================================================================
课程模块一（第一次作业 RGB/HSV 颜色转换工具，已归档并移植）：
  - 应用模式：色板/选色器由框架提供（ui/color_dialog.py），本模块无绘图工具；
  - 演示模式：3 个"交互可视化页"（阶段五，见规范 D10）——
    RGB 立方体 / HSV 色环与锥截面 / RGB⇄HSV 转换推导。
    页面 kind="widget"：不需要像素画板，演示壳把画布区整个换成
    页面控件，播放控制禁用——每个模块的形态完全独立。
=====================================================================
"""

from core.registry import ModuleSpec, register
from modules.module01_color.demos import create_demos

MODULE = ModuleSpec(
    id="module01_color",
    name="颜色模型",
    icon="palette",
    order=1,
    status="done",
    tool_classes=[],              # 无绘图工具（选色器是框架级能力）
    create_demos=create_demos,    # 阶段五已接入：3 个无画板交互页
)

register(MODULE)
