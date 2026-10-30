# -*- coding: utf-8 -*-
"""
=====================================================================
 modules/module04_clipping/module.py — 模块四声明：二维区域裁剪
=====================================================================
课程实验二（几何变换 + 裁剪）的裁剪部分。
导入本文件即向注册表声明模块（规范契约②）。
=====================================================================
"""

from core.registry import ModuleSpec, register
from modules.module04_clipping.tools import ClipTool
from modules.module04_clipping.demos import create_demos

MODULE = ModuleSpec(
    id="module04_clipping",
    name="区域裁剪",
    icon="crop",
    order=4,
    status="current",
    tool_classes=[
        ClipTool,              # 矩形/多边形窗口 + 像素掩膜挖除（可撤销）
    ],
    create_demos=create_demos,  # 演示页：Cohen / Liang-Barsky / Hodgman
)

register(MODULE)
