# -*- coding: utf-8 -*-
"""
=====================================================================
 core/tool_base.py  —  绘图工具插件基类 v2
=====================================================================
每个绘图工具继承此基类。子类除了实现 press/move/release，
还可以实现：
  - formula()  -> 返回该工具的数学公式说明（右侧面板显示）
  - status()   -> 返回当前实时状态（如决策项 p 的当前值）
=====================================================================
"""

from PySide6.QtCore import QPointF


class ToolBase:
    name: str = "未命名工具"
    cursor_hint: str = ""
    icon: str = "✏"        # 工具栏图标（Unicode）
    # 能力声明（主窗口/画布据此启用交互）------------------------------
    handles_shift_selection: bool = False  # Shift+点击交给工具（多选加减）
    algorithm_options: list = []         # [(算法键, 显示名)]
    is_drawing: bool = False             # 工具是否正处于"多点绘制中"（Backspace 归工具）

    def __init__(self, canvas):
        self.canvas = canvas

    # 子类钩子
    def on_press(self, pos: QPointF, event=None): pass
    def on_move(self, pos: QPointF, event=None): pass   # event: QMouseEvent，Shift 约束用
    def on_release(self, pos: QPointF, event=None): pass
    def on_right_click(self, pos: QPointF, event=None): pass
    def on_double_click(self, pos: QPointF, event=None): pass   # 双击确认等
    def on_key(self, event): pass       # 画布键盘事件透传（多边形 Backspace/Enter 等）
    def cancel(self): pass              # Esc：取消进行中的操作，清空工具内部状态
    def deactivate(self): pass

    # 工具专属面板（选项条下方一行）：返回 None 则不显示
    def panel_widget(self):
        return None

    # 画布叠层自绘（裁剪窗口等）：fn(painter)，scene 坐标
    def draw_overlay(self, painter):
        pass

    # 教学演示：公式说明
    def formula(self) -> str:
        return ""

    # 教学演示：实时状态（决策项值等）
    def status(self) -> str:
        return ""
