# -*- coding: utf-8 -*-
"""
algorithms — 计算机图形学纯算法层（零 Qt 依赖）。

每个算法模块提供双出口（见 steps.py 契约①）：
  xxx()       最终像素列表 —— 渲染与回归测试用
  xxx_steps() 步骤流 list[Step] —— 演示模式逐步动画用
"""
