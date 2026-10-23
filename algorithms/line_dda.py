# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/line_dda.py  —  DDA 直线生成算法（任意斜率）
=====================================================================
DDA (Digital Differential Analyzer，数值微分法)：

  直线方程: y = k*x + b
  取步长 = max(|dx|, |dy|)，使 x 或 y 每步增量为 1；
  另一坐标按斜率做浮点增量，再四舍五入取整作为像素坐标。

  优点：思路直观，增量式计算；
  缺点：每步都有浮点运算，取整耗时。

双出口（规范契约①）：
  dda_line()       -> 最终像素列表（渲染用）
  dda_line_steps() -> 步骤流 list[Step]（演示模式用，逐步动画 + 决策量）
两个出口的像素输出【完全一致】，由 render_test.py 像素级回归保证。
=====================================================================
"""

from typing import List, Tuple

from algorithms.steps import Step, expand_steps

Pixel = Tuple[int, int]


def dda_line_steps(x0: int, y0: int, x1: int, y1: int) -> List[Step]:
    """
    DDA 算法完整步骤流。
    自动处理任意斜率（|k|<1 与 |k|>=1 两种情况）。
    每步记录：本步像素 + 浮点坐标/增量 + 步数进度。
    """
    dx = x1 - x0
    dy = y1 - y0

    # 水平/垂直/退化情况：直接返回单个端点（一步完成）
    if dx == 0 and dy == 0:
        return [Step([(x0, y0)], {"x": x0, "y": y0}, "重合点，直接输出")]

    # 步数 = 较长那条边的像素数，保证每步至少有一个坐标走 1 像素
    steps = max(abs(dx), abs(dy))

    # 每步的浮点增量
    x_inc = dx / steps
    y_inc = dy / steps

    step_list: List[Step] = []
    x = float(x0)
    y = float(y0)
    for i in range(steps + 1):
        # round() 是 DDA 的取整方式（四舍五入）
        px, py = int(round(x)), int(round(y))
        step_list.append(Step(
            [(px, py)],
            {"x": px, "y": py, "xf": round(x, 2), "yf": round(y, 2),
             "步": f"{i}/{steps}"},
            f"浮点({x:.2f},{y:.2f}) → 四舍五入 ({px},{py})",
        ))
        x += x_inc
        y += y_inc
    return step_list


def dda_line(x0: int, y0: int, x1: int, y1: int) -> List[Pixel]:
    """
    在 (x0,y0) 与 (x1,y1) 之间用 DDA 算法生成像素点列表（最终结果）。
    由步骤流展开而来，保证与逐步版本逐像素一致。
    """
    return expand_steps(dda_line_steps(x0, y0, x1, y1))
