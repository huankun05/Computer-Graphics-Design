# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/midpoint_clip.py — 中点分割裁剪（Midpoint Subdivision）
=====================================================================
与 Cohen-Sutherland 共用同一套 4 位区域码做接受/舍弃判定；
不同的是【不求交点解析式】，而是对窗口外端点反复二分：

  取中点 M，算 M 的区域码：
    · M 与外端点同侧（code(M) & code(外端点) ≠ 0）→ 外端点移到 M
    · 否则（M 在窗内或异侧）                      → 内端点移到 M
  区间长度 ≤ 1 像素时即达显示分辨率精度，内端点近似为边界交点。

优点：只用移位/加减（除以 2），无乘除法，适合硬件实现——这是它
在课程里与 Cohen-Sutherland、Liang-Barsky 并列的原因。

双出口约定（契约②）：midpoint_clip() 返回几何，
midpoint_clip_steps() 的末步像素与几何结果逐像素一致。
=====================================================================
"""

from typing import List, Optional, Tuple

from algorithms.cohen_sutherland import _clamp, code_text, region_code
from algorithms.line_bresenham import bresenham_line
from algorithms.steps import (GUIDE_HIT, GUIDE_MARK, GUIDE_MOVE, GUIDE_REF,
                              Step, arrow_guide, label_guide, point_guide,
                              rect_guide)

Rect = Tuple[int, int, int, int]
Seg = Tuple[int, int, int, int]


def _bisect(px: float, py: float, qx: float, qy: float, rect: Rect,
            trace: Optional[list] = None) -> Tuple[float, float]:
    """中点二分：p 为窗口外端点、q 为另一端点，返回 p 侧的边界点。

    不变式：每轮看中点 M 的区域码——与外端点 p 同侧则 p→M，
    否则 q→M；区间 ≤1 像素（显示分辨率）时 q 即近似边界交点。
    trace 不为 None 时逐轮记录 (mx, my, m_code, same_side)，
    供步骤流回放同一过程（保证两个出口逐像素一致）。
    """
    rounds = 0
    while (abs(px - qx) > 1 or abs(py - qy) > 1) and rounds < 64:
        mx, my = (px + qx) / 2.0, (py + qy) / 2.0
        mc = region_code(mx, my, rect)
        same = bool(mc & region_code(px, py, rect))
        if trace is not None:
            trace.append((mx, my, mc, same))
        if same:
            px, py = mx, my
        else:
            qx, qy = mx, my
        rounds += 1
    return qx, qy


def midpoint_clip(x0: int, y0: int, x1: int, y1: int,
                  rect: Rect) -> Optional[Seg]:
    """中点分割裁剪；返回窗口内线段，完全在外返回 None。"""
    c0 = region_code(x0, y0, rect)
    c1 = region_code(x1, y1, rect)
    if not (c0 | c1):
        return x0, y0, x1, y1
    if c0 & c1:
        return None
    rx0, ry0, rx1, ry1 = rect
    ax, ay, bx, by = float(x0), float(y0), float(x1), float(y1)
    if c0:
        ax, ay = _bisect(ax, ay, bx, by, rect)
    if c1:
        bx, by = _bisect(bx, by, ax, ay, rect)
    # 与 Cohen 几何出口一致：四舍五入可能推出半格，钳回窗口内
    return (_clamp(int(round(ax)), rx0, rx1),
            _clamp(int(round(ay)), ry0, ry1),
            _clamp(int(round(bx)), rx0, rx1),
            _clamp(int(round(by)), ry0, ry1))


def midpoint_clip_steps(x0: int, y0: int, x1: int, y1: int,
                        rect: Rect) -> List[Step]:
    """中点分割步骤流：编码判定 → 逐轮二分（区间肉眼可见地收缩）→ 接受。

    与 Cohen/Liang 同一约定：Step.pixels 只放当前线段像素，
    窗口边框/端点/中点放 guides；values 给全区域码、中点码与区间长度。
    """
    rx0, ry0, rx1, ry1 = rect
    frame = rect_guide(rect)
    fx0, fy0, fx1, fy1 = float(x0), float(y0), float(x1), float(y1)
    c0 = region_code(fx0, fy0, rect)
    c1 = region_code(fx1, fy1, rect)
    marks = [point_guide((x0, y0), f"{c0:04b}", GUIDE_MARK),
             point_guide((x1, y1), f"{c1:04b}", GUIDE_MARK)]
    base = {"区域码0": code_text(c0), "区域码1": code_text(c1),
            "与 / 或": f"{c0 & c1:04b} / {c0 | c1:04b}",
            "端点0": (x0, y0), "端点1": (x1, y1),
            "中点": "—", "中点码": "—", "区间": "—", "轮次": "—"}
    seg0 = sorted(set(bresenham_line(x0, y0, x1, y1)))
    if not (c0 | c1):
        return [Step(seg0, {**base, "判定": "接受"},
                     "或 = 0000 → 整段接受（无需二分）",
                     guides=[frame, *marks])]
    if c0 & c1:
        return [Step(seg0, {**base, "判定": "舍弃"},
                     f"与 = {c0 & c1:04b} ≠ 0000 → 同侧，整段舍弃",
                     guides=[frame, *marks])]

    steps = [Step(seg0, {**base, "判定": "求交"},
                  "或 ≠ 0000、与 = 0000 → 不求交点，"
                  "对窗口外端点做中点二分",
                  guides=[frame, *marks])]

    ax, ay, bx, by = fx0, fy0, fx1, fy1
    total = 0
    done_pts = []                # 已完成的那一端求得的边界点（交替的另一半）
    for which in (0, 1):
        code = c0 if which == 0 else c1
        if not code:
            continue
        side = "起点" if which == 0 else "终点"
        if which == 0:
            px, py, qx, qy = ax, ay, bx, by
        else:
            px, py, qx, qy = bx, by, ax, ay
        trace = []
        ex, ey = _bisect(px, py, qx, qy, rect, trace)
        for rnd, (mx, my, mc, same) in enumerate(trace, 1):
            total += 1
            # 记录"这一轮改的是谁"：同侧改外端点 P，否则改内端点 Q
            mover = (px, py) if same else (qx, qy)
            if same:
                px, py = mx, my
            else:
                qx, qy = mx, my
            span = max(abs(px - qx), abs(py - qy))
            cur = sorted(set(bresenham_line(
                int(round(px)), int(round(py)),
                int(round(qx)), int(round(qy)))))
            pi = (int(round(px)), int(round(py)))
            qi = (int(round(qx)), int(round(qy)))
            mi = (int(round(mx)), int(round(my)))
            mi_old = (int(round(mover[0])), int(round(mover[1])))
            # 当前轮次的说明贴在区间中点下方；箭头从"被移动的端点"指向 M，
            # 并把另一端标出来 —— 交替求两端点的过程一眼可见（用户反馈）
            mid_lab = ((pi[0] + qi[0]) // 2, (pi[1] + qi[1]) // 2)
            steps.append(Step(
                cur,
                {"区域码0": code_text(region_code(ax, ay, rect)),
                 "区域码1": code_text(region_code(bx, by, rect)),
                 "与 / 或": "—", "端点0": (int(round(ax)), int(round(ay))),
                 "端点1": (int(round(bx)), int(round(by))),
                 "中点": mi, "中点码": f"{mc:04b}",
                 "区间": f"{span:.1f}", "轮次": total, "判定": "二分",
                 "当前": f"二分{side}"},
                f"二分{side}侧第 {rnd} 轮：中点 ({mx:.1f}, {my:.1f}) "
                f"码 {mc:04b} → "
                f"{'与外端点同侧，外端点 P 移到中点' if same else '不在同侧，内端点 Q 移到中点'}",
                guides=[frame,
                        point_guide(pi, "P", GUIDE_MARK),
                        point_guide(qi, "Q", GUIDE_REF),
                        point_guide(mi, "M", GUIDE_HIT),
                        arrow_guide(mi_old, mi, GUIDE_MOVE),
                        label_guide(mid_lab, f"第{rnd}轮 · 二分{side}",
                                    GUIDE_MARK, align="center",
                                    valign="below"),
                        *[point_guide(p, "交点", GUIDE_HIT)
                          for p in done_pts]]))
        if which == 0:
            ax, ay = ex, ey
        else:
            bx, by = ex, ey
        done_pts.append((_clamp(int(round(ex)), rx0, rx1),
                         _clamp(int(round(ey)), ry0, ry1)))

    # 接受尾步与几何出口一致：钳回窗口内再画线（双出口契约）
    iax, iay = _clamp(int(round(ax)), rx0, rx1), _clamp(int(round(ay)), ry0, ry1)
    ibx, iby = _clamp(int(round(bx)), rx0, rx1), _clamp(int(round(by)), ry0, ry1)
    final = sorted(set(bresenham_line(iax, iay, ibx, iby)))
    steps.append(Step(
        final,
        {"区域码0": "0000 内", "区域码1": "0000 内", "与 / 或": "0000 / 0000",
         "端点0": (iax, iay), "端点1": (ibx, iby),
         "中点": "—", "中点码": "—", "区间": "≤1 像素",
         "轮次": total, "判定": "接受", "当前": "收敛"},
        f"两端点都二分 {total} 轮收敛到像素精度 → 整段接受",
        guides=[frame, point_guide((iax, iay), "P0", GUIDE_HIT),
                point_guide((ibx, iby), "P1", GUIDE_HIT)]))
    return steps
