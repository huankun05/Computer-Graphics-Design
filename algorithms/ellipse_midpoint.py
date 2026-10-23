# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/ellipse_midpoint.py  —  中点椭圆生成算法
=====================================================================
椭圆方程: (x/rx)^2 + (y/ry)^2 = 1

椭圆关于 x 轴、y 轴对称，只需画第一象限，再四对称复制。

第一象限又分两个区域，分界点为斜率 = -1 处：
  区域 1：从 (0, ry) 开始，|斜率| > 1，x 走大步；
  区域 2：从分界点开始，|斜率| < 1，y 走大步。

  区域 1 决策项 p1：
      初值 p1 = ry*ry - rx*rx*ry + rx*rx/4
      若 p1 < 0：p1 += 2*ry*ry*x + ry*ry
      若 p1 ≥ 0：p1 += 2*ry*ry*x + ry*ry - 2*rx*rx*y；y 自减 1
      退出条件：2*ry*ry*x >= 2*rx*rx*y

  区域 2 决策项 p2（从区域 1 结束的 (x,y) 开始）：
      初值 p2 = ry*ry*(x+0.5)^2 + rx*rx*(y-1)^2 - rx*rx*ry*ry
      若 p2 > 0：p2 += rx*rx - 2*rx*rx*y
      若 p2 ≤ 0：p2 += rx*rx - 2*rx*rx*y + 2*ry*ry*x；x 自增 1
      退出条件：y < 0

双出口（规范契约①）：
  midpoint_ellipse()       -> 最终像素列表（渲染用）
  midpoint_ellipse_steps() -> 步骤流（每步 4 个对称像素 + 决策项/区域）
两个出口的像素输出【完全一致】，由 render_test.py 像素级回归保证。
=====================================================================
"""

from typing import List, Tuple

from algorithms.steps import Step, expand_steps

Pixel = Tuple[int, int]


def midpoint_ellipse_steps(cx: int, cy: int, rx: int, ry: int) -> List[Step]:
    """以 (cx,cy) 为中心，rx/ry 为 x/y 半轴，生成椭圆周【步骤流】。"""
    step_list: List[Step] = []
    rx, ry = abs(rx), abs(ry)
    if rx == 0 and ry == 0:
        # 退化情况：双半轴为 0 就是中心一个点
        return [Step([(cx, cy)], {"区域": "-", "x": 0, "y": 0}, "rx=ry=0，退化为中心点")]

    def sym_pixels(px: int, py: int) -> List[Pixel]:
        """四对称写点（第一象限点 → 四个象限）。"""
        return [
            (cx + px, cy + py),
            (cx - px, cy + py),
            (cx + px, cy - py),
            (cx - px, cy - py),
        ]

    x = 0
    y = ry
    rx2 = rx * rx
    ry2 = ry * ry

    # ---------- 区域 1：|斜率| > 1，x 走大步 ----------
    p1 = ry2 - rx2 * ry + (rx2 >> 2)   # 初值
    step_list.append(Step(sym_pixels(x, y),
                          {"区域": 1, "x": x, "y": y, "p1": p1},
                          f"起点 (0,{ry})，p1 = ry² - rx²·ry + rx²/4 = {p1}"))
    while 2 * ry2 * x < 2 * rx2 * y:
        x += 1
        if p1 < 0:
            # 中点在椭圆内，x 继续大步走，y 不动
            p1 += 2 * ry2 * x + ry2
            note = f"区域1: p1={p1} < 0 → y 不变，p1 += 2ry²x + ry²"
        else:
            # 中点在椭圆外，y 向内收一步
            y -= 1
            p1 += 2 * ry2 * x + ry2 - 2 * rx2 * y
            note = f"区域1: p1 ≥ 0 → y-1，p1 += 2ry²x + ry² - 2rx²y"
        step_list.append(Step(sym_pixels(x, y),
                              {"区域": 1, "x": x, "y": y, "p1": p1}, note))

    # ---------- 区域 2：|斜率| <= 1，y 走大步 ----------
    # 从区域 1 结束的 (x,y) 重新初始化 p2（不额外画点，保持像素输出与单次遍历一致）
    p2 = int(ry2 * (x + 0.5) ** 2 + rx2 * (y - 1) ** 2 - rx2 * ry2)
    first_r2 = True
    while y >= 0:
        y -= 1
        if p2 > 0:
            # 中点在椭圆外，y 继续大步走，x 不动
            p2 += rx2 - 2 * rx2 * y
            note = f"区域2: p2={p2} > 0 → x 不变，p2 += rx² - 2rx²y"
        else:
            # 中点在椭圆内，x 向外走一步
            x += 1
            p2 += rx2 - 2 * rx2 * y + 2 * ry2 * x
            note = f"区域2: p2 ≤ 0 → x+1，p2 += rx² - 2rx²y + 2ry²x"
        if first_r2:
            # 区域切换信息并入本步解释（决策项 p2 由区域 1 末点重算）
            note = f"切换区域2，p2 重算 = {p2}；" + note
            first_r2 = False
        step_list.append(Step(sym_pixels(x, y),
                              {"区域": 2, "x": x, "y": y, "p2": p2}, note))

    return step_list


def midpoint_ellipse(cx: int, cy: int, rx: int, ry: int) -> List[Pixel]:
    """以 (cx,cy) 为中心，rx/ry 为 x/y 半轴，生成椭圆周像素点（最终结果）。"""
    return expand_steps(midpoint_ellipse_steps(cx, cy, rx, ry))
