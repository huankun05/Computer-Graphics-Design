# -*- coding: utf-8 -*-
"""
=====================================================================
 modules/module03_transform2d/module.py — 模块三声明：二维几何变换
=====================================================================
课程实验二（几何变换 + 裁剪）的变换部分。
导入本文件即向注册表声明模块（规范契约②）。
=====================================================================
"""

from core.registry import ModuleSpec, register
from modules.module03_transform2d.tools import Transform2DTool
from modules.module03_transform2d.demos import create_demos

MODULE = ModuleSpec(
    id="module03_transform2d",
    name="二维几何变换",
    icon="cursor",
    order=3,
    status="current",
    tool_classes=[
        Transform2DTool,       # 选择/多选/框选 + 平移/旋转/缩放 + 数值面板
    ],
    create_demos=create_demos,  # 演示页：平移/旋转/缩放/复合
)

register(MODULE)
