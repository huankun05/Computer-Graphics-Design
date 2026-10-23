# -*- coding: utf-8 -*-
"""
=====================================================================
 core/registry.py  —  课程模块注册表（自动发现，主框架零修改）
=====================================================================
规范契约②：每次实验 = modules/ 下一个 moduleXX_* 文件夹，其中 module.py
在导入时调用 register() 声明自己。主框架（主窗口/演示模式）只向注册表
要"全部模块"，永远不写死任何具体实验。

模块声明（ModuleSpec）：
  id / name / icon / order / status   —— 元数据（演示目录排序与灰显）
  tool_classes                        —— 应用模式的绘图工具类列表
  create_demos(canvas)                —— 演示模式页面工厂（阶段四启用）

用法（框架侧）：
  registry.discover()                       # 一次性扫描（幂等）
  for m in registry.all_modules(): ...      # 按 order 排序的全部模块
=====================================================================
"""

import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import Callable, List

# ---------------------------------------------------------------------
# 模块声明结构
# ---------------------------------------------------------------------
@dataclass
class ModuleSpec:
    id: str                       # 如 "module02_primitives"
    name: str                     # 如 "基本图元生成"（演示目录显示名）
    icon: str                     # icons.py 键名（阶段二启用，暂用字符）
    order: int                    # 课程顺序（模块一=1）
    status: str                   # "done" | "current" | "future"（目录灰显）
    tool_classes: list = field(default_factory=list)   # 工具类（非实例）
    create_demos: Callable = None # 演示页工厂（阶段四）

    @property
    def is_future(self) -> bool:
        return self.status == "future"


# ---------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------
_MODULES: List[ModuleSpec] = []
_discovered = False


def register(spec: ModuleSpec):
    """模块在自身 module.py 末尾调用，声明自己。"""
    global _MODULES
    if any(m.id == spec.id for m in _MODULES):
        return                    # 重复导入幂等
    _MODULES.append(spec)


def discover():
    """扫描 modules/module*/package，导入其 module.py（导入即注册）。幂等。"""
    global _discovered
    if _discovered:
        return
    _discovered = True
    import modules as modules_pkg
    for info in pkgutil.iter_modules(modules_pkg.__path__):
        if info.name.startswith("module"):
            importlib.import_module(f"modules.{info.name}.module")


def all_modules() -> List[ModuleSpec]:
    """全部已注册模块，按课程顺序排序。"""
    return sorted(_MODULES, key=lambda m: m.order)


def all_tool_classes() -> list:
    """应用模式工具栏的全部工具类（Σ 各模块的 tool_classes）。"""
    classes = []
    for m in all_modules():
        classes.extend(m.tool_classes)
    return classes
