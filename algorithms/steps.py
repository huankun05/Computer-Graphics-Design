# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/steps.py  —  算法步骤流数据结构（教学演示的统一契约）
=====================================================================
本文件定义"步骤流"（Step stream）数据结构，是整个演示模式的基础契约：

  任何光栅化算法（DDA / Bresenham / 中点圆 / 中点椭圆 / 扫描线填充，
  以及未来课程的反走样 / 裁剪 / Bezier）除了返回最终像素列表外，
  还要能返回【一步一步的生成过程】list[Step]：

    - 每一步 = 一个决策时刻：本步点亮哪些像素 + 决策变量的当前值
      + 一句人话解释；
    - 演示模式的播放器（teaching/player.py）只认识 list[Step]，
      因此任何算法只要输出步骤流，就自动获得：
      逐步动画、决策项监视、单步回放、速度控制……
      —— 演示引擎不需要知道算法内部是什么。

设计约束（见《项目规范》契约①）：
  - 本包（algorithms/）内禁止 import Qt，保持纯 Python，
    可独立测试、可直接摘出来贴进实验报告；
  - 坐标一律 int 像素坐标（画布坐标系，原点左上）。
=====================================================================
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# 像素坐标类型：(x, y)，均为 int
Pixel = Tuple[int, int]

# ---------------------------------------------------------------------
# 辅助图元（guides）：算法演算的"黑板注记"，不属于算法输出像素
# ---------------------------------------------------------------------
# 教学演示需要看到判定依据（窗口边框、交点、轴心、源点→目标点等），
# 但这些不是算法产生的像素，不能混进 Step.pixels（否则会污染
# "末帧像素 = 几何结果"的双出口一致性）。因此统一放进 Step.guides，
# 由演示叠层单独渲染。全部用纯 dict 描述，algorithms/ 仍不依赖 Qt：
#   {"kind": "point", "xy": (x, y), "label": "P", "color": "#RRGGBB"}
#   {"kind": "line",  "a": (x, y), "b": (x, y), "dash": bool, "color": ...}
#   {"kind": "arrow", "a": (x, y), "b": (x, y), "color": ...}
#   {"kind": "rect",  "xy": (x0, y0, x1, y1), "color": ...}
#   {"kind": "label", "xy": (x, y), "text": "...", "color": ...}
GUIDE_REF = "#8A94A6"      # 辅助/轴心（灰）
GUIDE_MARK = "#F76B15"     # 源状态/待观察（橙）
GUIDE_HIT = "#3E63DD"      # 算法产出/交点（蓝）


def point_guide(xy: Pixel, label: str = "", color: str = GUIDE_HIT) -> dict:
    """点注记（交点、端点、轴心、映射点）。"""
    return {"kind": "point", "xy": (int(xy[0]), int(xy[1])),
            "label": label, "color": color}


def line_guide(a: Pixel, b: Pixel, color: str = GUIDE_REF,
               dash: bool = True) -> dict:
    """线注记（边界线、连线、扫描线）。"""
    return {"kind": "line", "a": (int(a[0]), int(a[1])),
            "b": (int(b[0]), int(b[1])), "color": color, "dash": dash}


def arrow_guide(a: Pixel, b: Pixel, color: str = GUIDE_MARK) -> dict:
    """箭头注记（P → P′ 的位移）。"""
    return {"kind": "arrow", "a": (int(a[0]), int(a[1])),
            "b": (int(b[0]), int(b[1])), "color": color}


def rect_guide(xy: Tuple[int, int, int, int],
               color: str = "#E5484D") -> dict:
    """矩形注记（裁剪窗口边框）。xy = (x0, y0, x1, y1)。"""
    return {"kind": "rect", "xy": tuple(int(v) for v in xy), "color": color}


def label_guide(xy: Pixel, text: str, color: str = GUIDE_REF) -> dict:
    """文字注记（挂在某个像素位置旁边）。"""
    return {"kind": "label", "xy": (int(xy[0]), int(xy[1])),
            "text": str(text), "color": color}


@dataclass
class Step:
    """算法的一个决策步骤（演示动画的一帧）。"""

    # 本步点亮的像素（通常 1 个；八对称点是 8 个；扫描线的一行是一段批量像素）
    pixels: List[Pixel]

    # 决策变量快照，键名由各算法自定（通用字典，监视器"有啥显啥"）：
    #   直线: {"x","y","err","e2"}   圆: {"x","y","p"}
    #   椭圆: {"x","y","p1","区域"}   填充: {"y","交点数"}
    #   未来的反走样可带灰度、裁剪可带区域编码、Bezier 可带中间点 —— 同构
    values: Dict = field(default_factory=dict)

    # 本步的人话解释（监视器副显示行），如 "e2 = -6 ≥ 0 → x 步进"
    note: str = ""

    # 演算注记（窗口边框、交点、轴心、箭头、标签）——只用于显示，
    # 不进入最终像素，保证"末帧像素 = 几何结果"的双出口一致性。
    # 放在最后：保持 Step(pixels, values, note) 的既有位置参数调用不变。
    guides: List[dict] = field(default_factory=list)


def expand_steps(steps: List["Step"]) -> List[Pixel]:
    """把步骤流展开成最终像素列表（按生成顺序，含重复——与逐点绘制一致）。"""
    return [px for step in steps for px in step.pixels]
