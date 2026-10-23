# -*- coding: utf-8 -*-
"""
=====================================================================
 core/document.py  —  图元文档（画布内容的数据模型 + 撤销/重做栈）
=====================================================================
职责：
  - 持有画布上全部图元 shapes（参数化存储，见 core/shapes.py）；
  - 通过命令（core/commands.py）执行一切修改 → 自动获得撤销/重做；
  - 纯数据 + 命令栈，不依赖 Qt（可无头测试）。

undo/redo 栈的行为（与主流软件一致）：
  - do(cmd)：执行命令，压入撤销栈，并【清空重做栈】
    （新操作会使 redo 分支失效）；
  - undo()：从撤销栈弹出命令反向执行，压入重做栈；
  - redo()：从重做栈弹出命令重新执行，压回撤销栈。
=====================================================================
"""

from typing import List

from core.commands import Command
from core.shapes import Shape


class Document:
    """画布文档：图元列表 + 双栈撤销/重做。"""

    def __init__(self):
        self.shapes: List[Shape] = []      # 当前图元（按绘制顺序）
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []

    # ---------- 执行 ----------
    def do(self, cmd: Command):
        """执行一个命令并记入撤销栈。之后 redo 分支失效（主流软件惯例）。"""
        cmd.do()
        self._undo_stack.append(cmd)
        self._redo_stack.clear()

    # ---------- 撤销 / 重做 ----------
    def undo(self) -> bool:
        """撤销最近一次操作。返回是否发生了撤销。"""
        if not self._undo_stack:
            return False
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        return True

    def redo(self) -> bool:
        """重做最近一次被撤销的操作。返回是否发生了重做。"""
        if not self._redo_stack:
            return False
        cmd = self._redo_stack.pop()
        cmd.do()
        self._undo_stack.append(cmd)
        return True

    def undo_until(self, target: Command) -> bool:
        """连续撤销直到 target 也被撤销（模式切换的批量恢复用）。

        沿途的命令（如演示期间的绘制）一并撤销；返回是否遇到了 target。
        """
        while self._undo_stack:
            cmd = self._undo_stack.pop()
            cmd.undo()
            self._redo_stack.append(cmd)
            if cmd is target:
                return True
        return False

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    @property
    def undo_name(self) -> str:
        """撤销栈顶的操作名（状态栏提示用，如 '撤销: 绘制'）。"""
        return self._undo_stack[-1].name if self._undo_stack else ""

    @property
    def redo_name(self) -> str:
        return self._redo_stack[-1].name if self._redo_stack else ""
