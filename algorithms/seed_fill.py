# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/seed_fill.py  —  扫描线种子填充（边界填充，4-连通）
=====================================================================
原理（ppt07 种子填充的经典扫描线实现）：
  从种子点出发，向左右扩展出一个连续 span（不碰边界像素），
  填充该 span；再检查上下两行同一区间内未被填充的连续段，
  作为新种子压栈，直到没有新种子。

  填充严格被 boundary（已画轮廓的像素集合）挡住，不会越界。
  connectivity=4/8 对应四联通/八联通——注意泄漏方向：
  1px 对角缝隙挡得住 4-联通、挡不住 8-联通（后者可走对角穿缝）。

双出口（规范契约①）：
  scanline_seed_fill()       -> 最终像素列表
  scanline_seed_fill_steps() -> 步骤流（每步 = 一个 span 的整段像素）
=====================================================================
"""

from typing import Callable, List, Set, Tuple

from algorithms.steps import Step, expand_steps

Point = Tuple[int, int]


def scanline_seed_fill_steps(seed: Point, boundary: Set[Point],
                             bounds: Tuple[int, int, int, int],
                             connectivity: int = 4) -> List[Step]:
    """
    种子填充步骤流。

    seed         种子点（必须不在边界上）
    boundary     边界像素集合（已画轮廓的像素）
    bounds       (x0, y0, x1, y1) 填充允许范围（右/下开区间，防无限扩散）
    connectivity 4 或 8（连通方式）：
                   4-连通只向上下左右扩散，1px 对角缝隙挡得住（不泄漏，
                   但正交 1px 空洞仍会漏）；
                   8-连通额外含对角方向，对角缝隙挡不住（会穿缝泄漏）。

    返回 [] 表示种子在边界上/范围外（无有效填充）。
    """
    x0, y0, x1, y1 = bounds
    conn = 1 if connectivity == 8 else 0   # 上下行种子检查的扩展量
    sx, sy = seed
    if not (x0 <= sx < x1 and y0 <= sy < y1) or (sx, sy) in boundary:
        return []

    filled: Set[Point] = set()
    steps: List[Step] = []
    stack: List[Point] = [(sx, sy)]
    k = 0

    while stack:
        x, y = stack.pop()
        if (x, y) in filled or (x, y) in boundary:
            continue
        # 向左找 span 左端
        xl = x
        while xl - 1 >= x0 and (xl - 1, y) not in boundary \
                and (xl - 1, y) not in filled:
            xl -= 1
        # 向右找 span 右端
        xr = x
        while xr + 1 < x1 and (xr + 1, y) not in boundary \
                and (xr + 1, y) not in filled:
            xr += 1
        # 填充整段
        span = [(xx, y) for xx in range(xl, xr + 1)]
        filled.update(span)
        k += 1
        steps.append(Step(
            span,
            {"y": y, "x0": xl, "x1": xr, "段": f"{k}"},
            f"扫描线 y={y}：span [{xl},{xr}] 填充 {len(span)} 像素",
        ))
        # 上下两行在 span 邻域内找未填充的连续段 → 新种子
        #   4-连通：只查 [xl,xr]；8-连通：查 [xl-1,xr+1]（对角相邻也算连通）
        #   窗口钳制在 bounds 内，防止泄漏填充无限向外行军
        for ny in (y - 1, y + 1):
            if not (y0 <= ny < y1):
                continue
            xx = max(x0, xl - conn)
            xend = min(x1 - 1, xr + conn)
            while xx <= xend:
                if (xx, ny) not in boundary and (xx, ny) not in filled:
                    nx = xx
                    while nx + 1 <= xend and (nx + 1, ny) not in boundary \
                            and (nx + 1, ny) not in filled:
                        nx += 1
                    stack.append((xx, ny))
                    xx = nx + 1
                else:
                    xx += 1
    return steps


def scanline_seed_fill(seed: Point, boundary: Set[Point],
                       bounds: Tuple[int, int, int, int],
                       connectivity: int = 4) -> List[Point]:
    """种子填充最终像素列表（由步骤流展开，保证两版本一致）。"""
    return expand_steps(scanline_seed_fill_steps(seed, boundary, bounds,
                                                 connectivity))


def seed_fill_wave_steps(seed: Point, boundary: Set[Point],
                         bounds: Tuple[int, int, int, int],
                         connectivity: int = 4) -> List[Step]:
    """种子填充步骤流——【波前扩散】版（教学演示专用）。

    与 scanline_seed_fill_steps 填充同一连通区域（最终像素一致），
    但步骤顺序 = BFS 距离分层：每步 = 从种子向外的一整圈波前。
    4-联通波前呈菱形、8-联通呈方形，扩散方向差异一目了然——
    这是"扫描线顺序"版本表现不出来的教学特征。
    """
    from collections import deque
    x0, y0, x1, y1 = bounds
    sx, sy = seed
    if not (x0 <= sx < x1 and y0 <= sy < y1) or (sx, sy) in boundary:
        return []
    if connectivity == 8:
        nbrs = ((-1, 0), (1, 0), (0, -1), (0, 1),
                (-1, -1), (1, -1), (-1, 1), (1, 1))
    else:
        nbrs = ((-1, 0), (1, 0), (0, -1), (0, 1))
    seen = {(sx, sy)}
    wave = [(sx, sy)]
    steps: List[Step] = []
    d = 0
    while wave:
        steps.append(Step(
            sorted(wave),
            {"波前": d, "新增": len(wave)},
            f"第 {d} 圈扩散：新增 {len(wave)} 像素"))
        nxt = []
        for (x, y) in wave:
            for dx, dy in nbrs:
                p = (x + dx, y + dy)
                if (x0 <= p[0] < x1 and y0 <= p[1] < y1
                        and p not in seen and p not in boundary):
                    seen.add(p)
                    nxt.append(p)
        wave = nxt
        d += 1
    return steps
