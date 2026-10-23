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


def expand_steps(steps: List["Step"]) -> List[Pixel]:
    """把步骤流展开成最终像素列表（按生成顺序，含重复——与逐点绘制一致）。"""
    return [px for step in steps for px in step.pixels]
