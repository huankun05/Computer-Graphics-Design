# -*- coding: utf-8 -*-
"""
=====================================================================
 core/commands.py  —  撤销/重做命令（Command 模式）
=====================================================================
对图元文档（core/document.py）的每一次修改都封装成一个命令对象：

  命令 = do()（执行） + undo()（反向执行） + name（给人看的状态名）

Document.do(cmd) 执行命令并把它压入撤销栈；Document.undo()/redo()
在撤销栈与重做栈之间搬运命令。画布只需在命令执行/反向执行后重建
受影响的像素层即可，自己不用管"怎么撤销"。

新增可撤销操作（如模块四的"变换图元"）时：写一个新 Command 子类即可，
文档与画布的撤销机制零修改。
=====================================================================
"""

from typing import List

from core.shapes import Shape


class Command:
    """可撤销命令基类。子类实现 do()/undo()，并可给 name 赋中文操作名。"""
    name: str = "操作"

    def do(self):       # 执行（首次生效）
        raise NotImplementedError

    def undo(self):     # 反向执行（撤销）
        raise NotImplementedError


class AddShapeCommand(Command):
    """向文档追加一个图元（画布上的正常绘制提交）。"""
    name = "绘制"

    def __init__(self, document, shape: Shape):
        self._doc = document
        self._shape = shape

    def do(self):
        self._doc.shapes.append(self._shape)

    def undo(self):
        self._doc.shapes.remove(self._shape)


class AddShapesCommand(Command):
    """一次提交多个图元（如直线算法对比的两条线），撤销一步整体回退。"""
    name = "绘制"

    def __init__(self, document, shapes):
        self._doc = document
        self._shapes = list(shapes)

    def do(self):
        self._doc.shapes.extend(self._shapes)

    def undo(self):
        del self._doc.shapes[-len(self._shapes):]


class RemoveShapeCommand(Command):
    """从文档移除一个图元（图元列表删除）。"""
    name = "删除图元"

    def __init__(self, document, shape: Shape):
        self._doc = document
        self._shape = shape

    def do(self):
        self._doc.shapes.remove(self._shape)

    def undo(self):
        # 按原位置插回：remove 前记录的索引，保证顺序还原
        self._doc.shapes.insert(self._index, self._shape)

    # 记录移除前的位置，undo 时精确还原
    def capture(self):
        self._index = self._doc.shapes.index(self._shape)


class RemoveShapesCommand(Command):
    """一次移除一组图元（删除边界连同它的填充，整体一步撤销）。"""
    name = "删除图元"

    def __init__(self, document, shapes):
        self._doc = document
        self._shapes = list(shapes)
        self._indices = []

    def capture(self):
        self._indices = [self._doc.shapes.index(s) for s in self._shapes]

    def do(self):
        for s in self._shapes:
            self._doc.shapes.remove(s)

    def undo(self):
        # 按原位置从大到小插回也能保序；这里按原索引升序逐个插回
        for s, i in sorted(zip(self._shapes, self._indices),
                           key=lambda t: t[1]):
            self._doc.shapes.insert(i, s)


class MoveShapeCommand(Command):
    """几何变换图元（快照式：do/undo 分别写入新/旧几何参数）。

    移动与缩放共用本命令（快照里就是变换后的参数）。
    """
    name = "移动图元"

    def __init__(self, document, shape, before: dict, after: dict,
                 name: str = "移动图元"):
        self._doc = document
        self._shape = shape
        self._before, self._after = before, after
        self.name = name

    def do(self):
        from core.shapes import restore
        restore(self._shape, self._after)

    def undo(self):
        from core.shapes import restore
        restore(self._shape, self._before)


class GroupMoveCommand(Command):
    """一次变换一组联动图元（如边界 + 它的填充整体移动/缩放）。

    entries = [(shape, before_snap, after_snap), ...]，一步撤销整组还原。
    """
    name = "移动图元"

    def __init__(self, document, entries, name: str = "移动图元"):
        self._doc = document
        self._entries = [(s, dict(b), dict(a)) for s, b, a in entries]
        self.name = name

    def do(self):
        from core.shapes import restore
        for s, _b, a in self._entries:
            restore(s, a)

    def undo(self):
        from core.shapes import restore
        for s, b, _a in self._entries:
            restore(s, b)


class SetFillCommand(Command):
    """切换图元填充模式（两阶段填充：画好轮廓 → 确认后填充）。"""
    name = "填充"

    def __init__(self, document, shape, on: bool):
        self._doc = document
        self._shape = shape
        self._on = on

    def do(self):
        self._shape.fill = self._on

    def undo(self):
        self._shape.fill = not self._on


class ErasePixelsCommand(Command):
    """像素擦除（快照式：do/undo 分别写入擦除后/前的掩码）。"""
    name = "擦除像素"

    def __init__(self, document, shape, before: set, after: set):
        self._doc = document
        self._shape = shape
        self._before, self._after = set(before), set(after)

    def do(self):
        self._shape.erased = set(self._after)

    def undo(self):
        self._shape.erased = set(self._before)


class ClearCommand(Command):
    """清空文档（保留快照，撤销时整体恢复）。"""
    name = "清空画布"

    def __init__(self, document):
        self._doc = document
        self._snapshot: List[Shape] = []

    def do(self):
        self._snapshot = list(self._doc.shapes)
        self._doc.shapes.clear()

    def undo(self):
        self._doc.shapes.extend(self._snapshot)


class ReplaceAllCommand(Command):
    """整体替换文档内容（打开工程文件时用），撤销即恢复原图元。"""
    name = "打开工程"

    def __init__(self, document, new_shapes: List[Shape]):
        self._doc = document
        self._new = list(new_shapes)   # 拷贝一份，避免与文档共享可变列表
        self._old: List[Shape] = []

    def do(self):
        self._old = list(self._doc.shapes)
        self._doc.shapes[:] = self._new

    def undo(self):
        self._doc.shapes[:] = self._old
