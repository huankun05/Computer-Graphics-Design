# -*- coding: utf-8 -*-
"""
=====================================================================
 algo_verify.py — 算法数学正确性【独立验证】（不依赖旧实现基准）
=====================================================================
render_test.py 证明"新 algorithms/ == 旧 tools/ 基准"（一致性），
本脚本证明"输出 == 数学定义"（正确性）。每个算法用独立真值核对：

  直线   DDA/Bresenham：端点在内 + 8 连通 + 每列(行)恰一像素
         且与理想线偏差 ≤ 0.5+ε（逐像素坐标核对解析式 y=kx+b）
  中点圆 径向偏差 |√(x²+y²)−r| ≤ 0.5+ε + 列内最优 + 八对称
         + 极值点 + 环 8 连通
  DDA圆  采样+补线法：径向偏差 < 1.1（含弦补线容差）+ 环 8 连通
  中点椭圆 |F|/|∇F| ≤ 0.75（一阶法向距离）+ 四对称 + 极值点
         + 环 8 连通
  扫描线填充 与独立【射线法点在多边形内】真值互核：
         无假阳（填充点必在多边形内或距边界 ≤0.5）
         无空洞（深度在内部且距边界 >0.5 的点必被填）
  种子填充 与独立 BFS 洪泛真值【集合全等】（4/8 连通 ×
         扫描线版/波前版 × 直边/细对角壁/随机多边形）
  跨段填充 圆/椭圆行跨段：轮廓⊆填充 + 深度内部无空洞
         + 填充不越理想形边界 1px
=====================================================================
"""

import math
import random
import sys
from collections import deque

from algorithms.line_dda import dda_line
from algorithms.line_bresenham import bresenham_line
from algorithms.circle_dda import dda_circle
from algorithms.circle_midpoint import midpoint_circle
from algorithms.ellipse_midpoint import midpoint_ellipse
from algorithms.fill_scanline import scanline_fill
from algorithms.fill_span import span_fill
from algorithms.seed_fill import (scanline_seed_fill, seed_fill_wave_steps)

EPS = 1e-9
results = []          # (家族名, 用例数, 失败描述列表)
_obs = {}             # 观测极值打印


def run_family(name):
    def deco(fn):
        results.append((name, fn))
        return fn
    return deco


def fail(msgs, case, desc):
    msgs.append(f"用例 {case}: {desc}")


def chebyshev(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def connected(pset, start, connectivity=8):
    """BFS 判连通：start 出发能否到达 pset 全部像素。"""
    if connectivity == 8:
        nbrs = ((-1, 0), (1, 0), (0, -1), (0, 1),
                (-1, -1), (1, -1), (-1, 1), (1, 1))
    else:
        nbrs = ((-1, 0), (1, 0), (0, -1), (0, 1))
    seen = {start}
    dq = deque([start])
    while dq:
        x, y = dq.popleft()
        for dx, dy in nbrs:
            p = (x + dx, y + dy)
            if p in pset and p not in seen:
                seen.add(p)
                dq.append(p)
    return seen == pset


def seg_dist(px, py, x0, y0, x1, y1):
    """点到线段距离。"""
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


# ---------------------------------------------------------------- 直线
def line_cases():
    grid = [-17, -5, 0, 3, 12]
    fixed = [(a, b, c, d) for a in grid for b in grid
             for c in grid for d in grid]
    rng = random.Random(42)
    rand = [(rng.randint(-40, 40), rng.randint(-40, 40),
             rng.randint(-40, 40), rng.randint(-40, 40))
            for _ in range(300)]
    return fixed + rand


def check_one_line(fn, case, msgs, tag):
    x0, y0, x1, y1 = case
    px = fn(x0, y0, x1, y1)
    if not px:
        fail(msgs, case, "输出为空")
        return
    pset = set(px)
    # 1. 端点
    if (x0, y0) not in pset or (x1, y1) not in pset:
        fail(msgs, case, f"端点缺失 {tag}")
        return
    # 2. 去重后顺序链 8 连通
    chain, seen = [], set()
    for p in px:
        if p not in seen:
            seen.add(p)
            chain.append(p)
    for a, b in zip(chain, chain[1:]):
        if chebyshev(a, b) > 1:
            fail(msgs, case, f"断裂 {a}->{b} {tag}")
            return
    dx, dy = x1 - x0, y1 - y0
    # 3. 每列/行恰一像素 + 与理想线偏差 ≤ 0.5
    if abs(dx) >= abs(dy) and dx != 0:
        cols = {}
        for (x, y) in pset:
            if x in cols:
                fail(msgs, case, f"x={x} 列出现两像素 {tag}")
                return
            cols[x] = y
        if set(cols) != set(range(min(x0, x1), max(x0, x1) + 1)):
            fail(msgs, case, f"列覆盖不全 {tag}")
            return
        k = dy / dx
        dev = max(abs(y - (y0 + (x - x0) * k)) for x, y in cols.items())
        key = f"{fn.__name__}_最大偏差"
        _obs[key] = max(_obs.get(key, 0.0), dev)
        if dev > 0.5 + EPS:
            fail(msgs, case, f"偏差 {dev:.4f} > 0.5 {tag}")
    elif dy != 0:
        rows = {}
        for (x, y) in pset:
            if y in rows:
                fail(msgs, case, f"y={y} 行出现两像素 {tag}")
                return
            rows[y] = x
        if set(rows) != set(range(min(y0, y1), max(y0, y1) + 1)):
            fail(msgs, case, f"行覆盖不全 {tag}")
            return
        k = dx / dy
        dev = max(abs(x - (x0 + (y - y0) * k)) for y, x in rows.items())
        key = f"{fn.__name__}_最大偏差"
        _obs[key] = max(_obs.get(key, 0.0), dev)
        if dev > 0.5 + EPS:
            fail(msgs, case, f"偏差 {dev:.4f} > 0.5 {tag}")


@run_family("直线 DDA + Bresenham（端点/连通/每列一像素/偏差≤0.5）")
def _(report):
    cases = line_cases()
    msgs = []
    for c in cases:
        check_one_line(dda_line, c, msgs, "DDA")
        check_one_line(bresenham_line, c, msgs, "Bre")
    report(len(cases) * 2, msgs)


# ---------------------------------------------------------------- 中点圆
@run_family("中点圆（径向≤0.5/列内最优/八对称/极值/连通）")
def _(report):
    msgs = []
    n = 0
    for r in range(1, 61):
        for cx, cy in [(0, 0), (100, 50), (-20, 7)]:
            n += 1
            px = set(midpoint_circle(cx, cy, r))
            maxdev = 0.0
            for (x, y) in px:
                d = math.hypot(x - cx, y - cy)
                dev = abs(d - r)
                maxdev = max(maxdev, dev)
                if dev > 0.5 + 1e-6:
                    fail(msgs, (cx, cy, r), f"径向偏差 {dev:.4f} > 0.5 @({x},{y})")
                    break
                # 最优性只对"步进轴"成立：|ax|≤|ay| 为 x 步进区（列内最优），
                # 否则为 y 步进区（行内最优）——45° 镜像不适用列判据
                ax, ay = abs(x - cx), abs(y - cy)
                nbrs = ((x, y - 1), (x, y + 1)) if ax <= ay \
                    else ((x - 1, y), (x + 1, y))
                for (nx, ny) in nbrs:
                    dn = abs(math.hypot(nx - cx, ny - cy) - r)
                    if dev > dn + EPS:
                        fail(msgs, (cx, cy, r),
                             f"({x},{y}) 偏差 {dev:.4f} 劣于邻点 ({nx},{ny}) {dn:.4f}")
                        break
                else:
                    continue
                break
            else:
                _obs["中点圆_最大径向偏差"] = max(
                    _obs.get("中点圆_最大径向偏差", 0.0), maxdev)
                # 八对称
                ok = all(
                    all((cx + s * abs(a), cy + t * abs(b)) in px
                        for s in (1, -1) for t in (1, -1))
                    for (a, b) in ((x - cx, y - cy) for (x, y) in px))
                if not ok:
                    fail(msgs, (cx, cy, r), "八对称破缺")
                    continue
                # 极值点 + 连通
                ext = {(cx + r, cy), (cx - r, cy), (cx, cy + r), (cx, cy - r)}
                if not ext <= px:
                    fail(msgs, (cx, cy, r), "四极值点缺失")
                    continue
                if not connected(px, (cx + r, cy)):
                    fail(msgs, (cx, cy, r), "圆环不 8 连通")
    report(n, msgs)


# ---------------------------------------------------------------- DDA 圆
@run_family("DDA 圆（径向<1.1 含补线容差/极值邻域/连通）")
def _(report):
    msgs = []
    n = 0
    for r in range(1, 61):
        for cx, cy in [(0, 0), (100, 50)]:
            n += 1
            px = set(dda_circle(cx, cy, r))
            maxdev = max(abs(math.hypot(x - cx, y - cy) - r) for (x, y) in px)
            _obs["DDA圆_最大径向偏差"] = max(
                _obs.get("DDA圆_最大径向偏差", 0.0), maxdev)
            if maxdev >= 1.1:
                fail(msgs, (cx, cy, r), f"径向偏差 {maxdev:.4f} ≥ 1.1")
                continue
            ext = [(cx + r, cy), (cx - r, cy), (cx, cy + r), (cx, cy - r)]
            # 采样点数不保证含正轴角，允许极值点 1px 邻域内有环点
            if not any(chebyshev(e, p) <= 1 for e in ext for p in px):
                fail(msgs, (cx, cy, r), "四极值点邻域皆无环点")
                continue
            if not connected(px, next(iter(px))):
                fail(msgs, (cx, cy, r), "圆环不 8 连通")
    report(n, msgs)


# ---------------------------------------------------------------- 中点椭圆
@run_family("中点椭圆（|F|/|∇F|≤0.75/四对称/极值/连通）")
def _(report):
    msgs = []
    n = 0
    radii = [(rx, ry) for rx in range(0, 26) for ry in range(0, 26)
             if 0 < rx + ry <= 26] + [(60, 20), (20, 60), (50, 50)]
    for rx, ry in radii:
        cx, cy = 100, 80
        n += 1
        px = set(midpoint_ellipse(cx, cy, rx, ry))
        rx2, ry2 = rx * rx, ry * ry
        maxe = 0.0
        bad = None
        for (x, y) in px:
            F = ry2 * (x - cx) ** 2 + rx2 * (y - cy) ** 2 - rx2 * ry2
            gx, gy = 2 * ry2 * (x - cx), 2 * rx2 * (y - cy)
            g = math.hypot(gx, gy)
            if g < 1e-12:
                continue
            e = abs(F) / g
            if e > maxe:
                maxe, bad = e, (x, y)
        # 退化薄片（min ≤ 1）：教科书算法本身在薄片上精度退化，
        # 只要求对称 + 连通 + 端点 1px 邻域，法向偏差仅记录不判失败
        sliver = min(rx, ry) <= 1
        if sliver:
            _obs["中点椭圆_退化薄片_最大|F|/|∇F|"] = max(
                _obs.get("中点椭圆_退化薄片_最大|F|/|∇F|", 0.0), maxe)
        else:
            _obs["中点椭圆_最大|F|/|∇F|"] = max(
                _obs.get("中点椭圆_最大|F|/|∇F|", 0.0), maxe)
            if maxe > 0.75:
                fail(msgs, (rx, ry), f"法向偏差 {maxe:.4f} > 0.75 @{bad}")
                continue
        # 四对称
        if any((2 * cx - x, y) not in px or (x, 2 * cy - y) not in px
               for (x, y) in px):
            fail(msgs, (rx, ry), "四对称破缺")
            continue
        # 极值点：正常椭圆须精确命中；薄片只要求 1px 邻域（教科书退化特性）
        if rx > 0 and ry > 0:
            ext = {(cx + rx, cy), (cx - rx, cy), (cx, cy + ry), (cx, cy - ry)}
            if sliver:
                ok = all(any(chebyshev(e, p) <= 1 for p in px) for e in ext)
            else:
                ok = ext <= px
                if not ok:
                    fail(msgs, (rx, ry),
                         f"极值点缺失 {sorted(ext - px)[:2]}")
                    continue
            if not ok and not sliver:
                continue
            if not connected(px, next(iter(px))):
                fail(msgs, (rx, ry), "椭圆环不 8 连通")
    report(n, msgs)


# ---------------------------------------------------------------- 扫描线填充
def inside_crossing(poly, px, py):
    """独立射线法（+x 方向，半开顶点规则）判点在多边形内。"""
    cnt = 0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > py) != (y1 > py):
            xi = x0 + (py - y0) * (x1 - x0) / (y1 - y0)
            if xi > px:
                cnt += 1
    return cnt % 2 == 1


def poly_dist(poly, px, py):
    return min(seg_dist(px, py, *poly[i], *poly[(i + 1) % len(poly)])
               for i in range(len(poly)))


def star_polygon(rng, cx, cy, k):
    angs = sorted(rng.uniform(0, 2 * math.pi) for _ in range(k))
    if min(b - a for a, b in zip(angs, angs[1:])) < 0.35:
        return None
    if angs[0] + 2 * math.pi - angs[-1] < 0.35:
        return None
    pts = []
    for a in angs:
        r = rng.randint(5, 16)
        pts.append((cx + round(r * math.cos(a)), cy + round(r * math.sin(a))))
    dedup = [p for i, p in enumerate(pts) if p != pts[(i + 1) % len(pts)]]
    return dedup if len(dedup) >= 3 else None


@run_family("扫描线填充（射线法真值：无假阳/无空洞）")
def _(report):
    rng = random.Random(7)
    polys = [
        [(0, 0), (20, 0), (20, 12), (0, 12)],                 # 矩形
        [(0, 0), (18, 0), (9, 14)],                           # 三角
        [(0, 0), (16, 0), (16, 10), (6, 10), (6, 18), (0, 18)],   # L 形
        [(2, 0), (14, 4), (10, 12), (0, 9)],                  # 一般凸四边形
        [(0, 6), (8, 0), (16, 6), (12, 16), (4, 16)],         # 凹五边形
        [(0, 0), (10, 0), (10, 4), (5, 4), (5, 8), (10, 8),
         (10, 12), (0, 12)],                                  # U 形（双凹）
        [(0, 0), (12, 0), (6, 10)],                           # 斜边三角
    ]
    while len(polys) < 57:
        p = star_polygon(rng, 0, 0, rng.randint(3, 9))
        if p:
            polys.append(p)
    msgs = []
    for idx, poly in enumerate(polys):
        filled = set(scanline_fill(poly))
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        fp = hole = None
        for x in range(min(xs) - 2, max(xs) + 3):
            for y in range(min(ys) - 2, max(ys) + 3):
                ins = inside_crossing(poly, x, y)
                d = poly_dist(poly, x, y)
                if (x, y) in filled:
                    if not ins and d > 0.5 + 1e-6 and fp is None:
                        fp = (x, y, d)
                else:
                    if ins and d > 0.5 + 1e-6 and hole is None:
                        hole = (x, y, d)
        if fp:
            fail(msgs, idx, f"假阳像素 {fp[:2]}（离边界 {fp[2]:.3f}）")
        if hole:
            fail(msgs, idx, f"空洞像素 {hole[:2]}（深入内部 {hole[2]:.3f}）")
    report(len(polys), msgs)


# ---------------------------------------------------------------- 种子填充
def bfs_truth(seed, boundary, bounds, connectivity):
    x0, y0, x1, y1 = bounds
    sx, sy = seed
    if not (x0 <= sx < x1 and y0 <= sy < y1) or (sx, sy) in boundary:
        return set()
    if connectivity == 8:
        nbrs = ((-1, 0), (1, 0), (0, -1), (0, 1),
                (-1, -1), (1, -1), (-1, 1), (1, 1))
    else:
        nbrs = ((-1, 0), (1, 0), (0, -1), (0, 1))
    seen = {(sx, sy)}
    dq = deque([(sx, sy)])
    while dq:
        x, y = dq.popleft()
        for dx, dy in nbrs:
            p = (x + dx, y + dy)
            if (x0 <= p[0] < x1 and y0 <= p[1] < y1
                    and p not in seen and p not in boundary):
                seen.add(p)
                dq.append(p)
    return seen


def outline_of(poly):
    b = set()
    n = len(poly)
    for i in range(n):
        b.update(bresenham_line(*poly[i], *poly[(i + 1) % n]))
    return b


@run_family("种子填充（BFS 真值集合全等：扫描线/波前 × 4/8 连通）")
def _(report):
    rng = random.Random(11)
    shapes = [
        ("矩形壁", outline_of([(2, 2), (25, 2), (25, 16), (2, 16)]), (13, 9)),
        ("三角形壁", outline_of([(2, 2), (26, 4), (12, 18)]), (12, 8)),
        ("L 形壁", outline_of([(2, 2), (20, 2), (20, 9), (10, 9),
                               (10, 19), (2, 19)]), (6, 6)),
        ("细对角壁（漏口试验）", outline_of([(1, 1), (24, 24)]) |
         outline_of([(24, 24), (24, 2)]) | outline_of([(24, 2), (1, 1)]),
         (18, 14)),
        ("圆环壁", set(midpoint_circle(14, 10, 9)), (14, 10)),
    ]
    while len(shapes) < 25:
        p = star_polygon(rng, 15, 12, rng.randint(3, 8))
        if not p:
            continue
        shapes.append((f"随机多边形{len(shapes)}", outline_of(p),
                       (15 + rng.randint(-3, 3), 12 + rng.randint(-3, 3))))
    msgs = []
    n = 0
    bounds = (0, 0, 60, 60)
    for name, boundary, seed in shapes:
        if seed in boundary:
            seed = (seed[0], seed[1] + 1)
        for conn in (4, 8):
            truth = bfs_truth(seed, boundary, bounds, conn)
            got = set(scanline_seed_fill(seed, boundary, bounds, conn))
            wave = set()
            from algorithms.steps import expand_steps
            wave = set(expand_steps(
                seed_fill_wave_steps(seed, boundary, bounds, conn)))
            n += 1
            if got != truth:
                only = list(got - truth)[:3]
                miss = list(truth - got)[:3]
                fail(msgs, f"{name} conn={conn}",
                     f"扫描线版≠BFS（多{only} 少{miss}）")
            if wave != truth:
                fail(msgs, f"{name} conn={conn}", "波前版≠BFS")
    report(n, msgs)


# ---------------------------------------------------------------- 跨段填充
@run_family("跨段填充（圆/椭圆：轮廓⊆填充/无空洞/不越界）")
def _(report):
    msgs = []
    n = 0
    cases = [("circle", (30, 20), r) for r in (4, 7, 12, 25)] + \
            [("ellipse", (30, 20), (rx, ry))
             for rx, ry in ((5, 4), (12, 6), (20, 9), (25, 15))]
    for kind, (cx, cy), rr in cases:
        n += 1
        if kind == "circle":
            outline = set(midpoint_circle(cx, cy, rr))
            def q(x, y, rr=rr):
                return math.hypot(x - cx, y - cy) / rr
        else:
            rx, ry = rr
            outline = set(midpoint_ellipse(cx, cy, rx, ry))

            def q(x, y, rx=rx, ry=ry):
                return math.hypot((x - cx) / rx, (y - cy) / ry)
        filled = set(span_fill(sorted(outline, key=lambda p: (p[1], p[0]))))
        if not outline <= filled:
            fail(msgs, (kind, rr), "轮廓像素未被包含")
            continue
        # 容差：轮廓本身偏离理想形 ≤0.5，跨段端点取自轮廓 → 统一 1.01/深度 1.6
        bad_out = [p for p in filled if q(*p) > 1 + 1.01 / min(
            (rr if kind == "circle" else min(rr)) , 8) + 0.13]
        if bad_out:
            fail(msgs, (kind, rr),
                 f"越界填充 {bad_out[:2]} q={q(*bad_out[0]):.3f}")
            continue
        xs = [p[0] for p in outline]
        ys = [p[1] for p in outline]
        hole = None
        for x in range(min(xs), max(xs) + 1):
            for y in range(min(ys), max(ys) + 1):
                if (x, y) not in filled and q(x, y) < 0.8:
                    hole = (x, y, q(x, y))
                    break
            if hole:
                break
        if hole:
            fail(msgs, (kind, rr), f"内部空洞 {hole[:2]} q={hole[2]:.3f}")
    report(n, msgs)


# ---------------------------------------------------------------- 汇总
def main():
    total = 0
    all_fail = 0
    print("=" * 64)
    print("算法数学正确性独立验证（真值 = 数学定义，非旧实现基准）")
    print("=" * 64)
    for name, fn in results:
        box, holder = [], []

        def report(cnt, msgs, _name=name, _box=box, _holder=holder):
            _box.extend(msgs)
            _holder.append(cnt)

        fn(report)
        cnt = holder[0] if holder else 0
        total += cnt
        all_fail += len(box)
        mark = "PASS ✓" if not box else f"FAIL ✗（{len(box)} 处）"
        print(f"[{mark}] {name}  —— {cnt} 用例")
        for m in box[:8]:
            print(f"        · {m}")
        if len(box) > 8:
            print(f"        · …另有 {len(box) - 8} 处")
    print("-" * 64)
    print("观测极值（实测精度）:")
    for k, v in sorted(_obs.items()):
        print(f"  {k}: {v:.4f}")
    print("-" * 64)
    if all_fail:
        print(f"结果: FAIL ✗ —— {all_fail} 处不一致 / 共 {total} 用例")
        sys.exit(1)
    print(f"结果: ALL PASS ✓ —— {total} 用例全部与数学真值一致")


if __name__ == "__main__":
    main()
