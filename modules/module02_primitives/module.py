# -*- coding: utf-8 -*-
"""
=====================================================================
 modules/module02_primitives/module.py — 模块二声明：基本图元生成
=====================================================================
课程模块二（当前实验：实验一 基本图元绘制）。
导入本文件即向注册表声明模块（规范契约②）。
=====================================================================
"""

from core.registry import ModuleSpec, register
from modules.module02_primitives.tools import (
    LineTool, CircleTool, EllipseTool, PolygonTool, CompareLineTool,
    SelectMoveTool, EraserTool, FillTool,
)
from modules.module02_primitives.demos import create_demos

MODULE = ModuleSpec(
    id="module02_primitives",
    name="基本图元生成",
    icon="shapes",
    order=2,
    status="current",
    tool_classes=[
        LineTool,              # 直线（算法下拉：DDA / Bresenham）
        CircleTool,            # 圆（中点圆 / DDA 圆，支持填充）
        EllipseTool,           # 椭圆（中点椭圆，支持填充）
        PolygonTool,           # 多边形描边（是否填充跟随选项条开关）
        CompareLineTool,       # 一拖同画 DDA+Bresenham 同位双层对比
        SelectMoveTool,        # 选择/移动（点选、拖拽、方向键微调）
        EraserTool,            # 橡皮擦（像素擦除 / 整体删除）
        FillTool,              # 填充（油漆桶：点边界内部，四/八联通可选）
    ],
    create_demos=create_demos,  # 演示页：5 算法步进动画 + DDA/Bres 对比
)

register(MODULE)
