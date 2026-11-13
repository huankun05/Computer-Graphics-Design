# -*- coding: utf-8 -*-
"""生成实验报告用的 6 张算法流程图 + 1 张总体架构图。

风格与运行截图/fig03_DDA流程.png、fig01_系统总体架构.png 保持一致：
白底、圆角矩形=开始/结束、矩形=处理、菱形=判断，深灰蓝边框与箭头，
中文无衬线字体，dpi 200。

用法： python build/gen_flows.py
"""
from __future__ import annotations

import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle  # noqa: E402

# ---------------------------------------------------------------- 常量
DPI = 200
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "运行截图")

C_BORDER = "#4A5568"   # 边框 / 箭头
C_TEXT = "#1F2937"     # 正文
C_LABEL = "#6B7280"    # 是 / 否 等分支标注
C_PROC = "#EAF1FB"     # 处理框
C_START = "#E6F4EA"    # 开始 / 结束
C_DEC = "#FFF4E0"      # 判断框
C_NOTE = "#F3F0FA"     # 外围产物（虚线框）

LW = 1.2               # 线宽（磅）
FS = 10                # 正文字号
PITCH = 38             # 框内行距（像素）
RADIUS = 20            # 圆角矩形半径（像素）

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "Noto Sans SC", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False


# ---------------------------------------------------------------- 画布
class Canvas:
    """以「像素」为坐标的绘图助手：x 向右、y 向下。"""

    def __init__(self, w: int, h: int):
        self.w = w
        self.h = h
        self.fig = plt.figure(figsize=(w / DPI, h / DPI), dpi=DPI)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, w)
        self.ax.set_ylim(h, 0)
        self.ax.axis("off")
        self.fig.patch.set_facecolor("white")

    # ---------------------------------------------------------- 基础图元
    def _lines(self, cx, cy, lines, fs=FS, color=C_TEXT, pitch=PITCH):
        n = len(lines)
        for i, s in enumerate(lines):
            self.ax.text(
                cx, cy + (i - (n - 1) / 2.0) * pitch, s,
                ha="center", va="center", fontsize=fs, color=color, zorder=5,
            )

    def node(self, x, y, w, h, lines, kind="proc", fs=FS, pitch=PITCH, radius=RADIUS):
        """x/y 为左上角。kind: start|end（圆角）、proc（矩形）、dec（菱形）。"""
        if kind in ("start", "end"):
            patch = FancyBboxPatch(
                (x, y), w, h,
                boxstyle="round,pad=0,rounding_size=%g" % radius,
                facecolor=C_START, edgecolor=C_BORDER, linewidth=LW, zorder=2,
            )
        elif kind == "dec":
            pts = [(x + w / 2, y), (x + w, y + h / 2), (x + w / 2, y + h), (x, y + h / 2)]
            patch = Polygon(pts, closed=True, facecolor=C_DEC,
                            edgecolor=C_BORDER, linewidth=LW, zorder=2)
        else:
            patch = Rectangle((x, y), w, h, facecolor=C_PROC,
                              edgecolor=C_BORDER, linewidth=LW, zorder=2)
        self.ax.add_patch(patch)
        self._lines(x + w / 2, y + h / 2, lines, fs=fs, pitch=pitch)
        return (x + w / 2, y + h / 2)

    def dashed_node(self, x, y, w, h, lines, fs=FS, pitch=PITCH, radius=16):
        patch = FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0,rounding_size=%g" % radius,
            facecolor=C_NOTE, edgecolor=C_BORDER, linewidth=LW,
            linestyle=(0, (4, 2.4)), zorder=2,
        )
        self.ax.add_patch(patch)
        self._lines(x + w / 2, y + h / 2, lines, fs=fs, pitch=pitch)
        return (x + w / 2, y + h / 2)

    # ---------------------------------------------------------- 箭头
    @staticmethod
    def _unit(p0, p1):
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy) or 1.0
        return dx / L, dy / L

    def _head(self, p0, p1, head=11.0, color=C_BORDER):
        ux, uy = self._unit(p0, p1)
        bx, by = p1[0] - ux * head, p1[1] - uy * head
        px, py = -uy, ux
        hw = head * 0.6
        self.ax.add_patch(Polygon(
            [p1, (bx + px * hw, by + py * hw), (bx - px * hw, by - py * hw)],
            closed=True, facecolor=color, edgecolor=color, linewidth=0, zorder=3))

    def arrow(self, p0, p1, head=11.0, color=C_BORDER, lw=LW):
        ux, uy = self._unit(p0, p1)
        base = (p1[0] - ux * head, p1[1] - uy * head)
        self.ax.add_line(Line2D([p0[0], base[0]], [p0[1], base[1]],
                                color=color, linewidth=lw, zorder=3))
        self._head(p0, p1, head, color)

    def path(self, points, head=11.0, color=C_BORDER, lw=LW, dashed=False):
        """折线箭头：points 为折点列表，最后一段带箭头。"""
        for i in range(len(points) - 2):
            self.ax.add_line(Line2D([points[i][0], points[i + 1][0]],
                                    [points[i][1], points[i + 1][1]],
                                    color=color, linewidth=lw,
                                    linestyle=(0, (3, 2)) if dashed else "-", zorder=3))
        self.arrow(points[-2], points[-1], head=head, color=color, lw=lw)

    def dashed_line(self, p0, p1, color=C_BORDER, lw=LW):
        self.ax.add_line(Line2D([p0[0], p1[0]], [p0[1], p1[1]], color=color,
                                linewidth=lw, linestyle=(0, (3, 2)), zorder=3))

    # ---------------------------------------------------------- 文字
    def label(self, x, y, text, fs=9, color=C_LABEL, ha="center", va="center"):
        self.ax.text(x, y, text, ha=ha, va=va, fontsize=fs, color=color, zorder=6)

    def note(self, x, y, text, fs=9, color=C_LABEL, ha="center"):
        self.ax.text(x, y, text, ha=ha, va="center", fontsize=fs, color=color, zorder=6)

    def dot(self, x, y, color=C_BORDER, r=4.0):
        self.ax.add_patch(plt.Circle((x, y), r, facecolor=color,
                                     edgecolor=color, linewidth=0, zorder=4))

    def save(self, name):
        path = os.path.join(OUT, name)
        self.fig.savefig(path, dpi=DPI, facecolor="white")
        plt.close(self.fig)
        print("saved:", path)
        return path


# ---------------------------------------------------------------- fig08
def fig08():
    """二维变换总体流程。"""
    c = Canvas(1160, 1200)
    MC = 560

    c.node(450, 40, 220, 76, ["开始"], "start")
    c.node(260, 146, 600, 76, ["用户交互：选择图元", "单击 / Shift 加选 / 框选"])
    c.node(260, 252, 600, 64, ["确定定点 c = 所选图元包围盒中心"])
    c.node(400, 346, 320, 120, ["变换类型？"], "dec")

    # 三条分支
    bx = [(40, "构造平移矩阵", "T(dx, dy)", "平移"),
          (425, "构造旋转矩阵", "R(θ)", "旋转"),
          (810, "构造缩放矩阵", "S(sx, sy)", "缩放")]
    for x0, t1, t2, tag in bx:
        c.node(x0, 510, 270, 70, [t1, t2])
        tx = x0 + 135
        c.arrow((MC, 466), (tx, 508))
        c.label(MC + (tx - MC) * 0.55, 466 + (508 - 466) * 0.55 - 14, tag)

    c.node(260, 620, 600, 88,
           ["绕定点复合：M = T(c) · [R(θ) 或 S(sx,sy)] · T(−c)",
            "（平移时 T(c) 与 T(−c) 相消，退化为 T(dx,dy)）"])
    for tx in (175, 560, 945):
        c.arrow((tx, 580), (tx + (-225 if tx < MC else 225 if tx > MC else 0), 618))

    c.node(260, 738, 600, 100,
           ["应用到图元几何参数",
            "直线 / 多边形：变换顶点坐标",
            "圆 / 椭圆：协方差矩阵特征分解 → 换算半轴与旋转角"])
    c.node(260, 868, 600, 64, ["按几何参数重新光栅化 → 重绘"])
    c.node(260, 962, 600, 76,
           ["写入命令栈（整组变换记为一条命令）", "可一次 Ctrl+Z 撤销"])
    c.node(450, 1068, 220, 76, ["结束"], "end")

    c.arrow((MC, 116), (MC, 144))
    c.arrow((MC, 222), (MC, 250))
    c.arrow((MC, 316), (MC, 344))
    c.arrow((MC, 708), (MC, 736))
    c.arrow((MC, 838), (MC, 866))
    c.arrow((MC, 932), (MC, 960))
    c.arrow((MC, 1038), (MC, 1066))
    return c.save("fig08_二维变换总体流程.png")


# ---------------------------------------------------------------- fig09
def fig09():
    """绕轴心旋转三阶段分解。"""
    c = Canvas(1160, 880)
    MC = 440

    c.node(330, 36, 220, 72, ["开始"], "start")
    c.node(130, 132, 620, 64, ["输入：轴心 c = (cx, cy)、转角 θ"])
    c.node(130, 226, 620, 76, ["① M1 = T(−c)：把轴心 c 搬到原点 O"])
    c.node(130, 342, 620, 76, ["② M2 = R(θ) · M1：绕原点 O 旋转 θ"])
    c.node(130, 458, 620, 76, ["③ M3 = T(c) · M2：把原点 O 搬回轴心 c"])
    c.node(130, 574, 620, 88,
           ["M3 即最终变换矩阵 M = T(c) · R(θ) · T(−c)",
            "取样点 P 经 M 映射为 P′"])
    c.node(330, 702, 220, 72, ["结束"], "end")

    for y0, y1 in ((108, 130), (196, 224), (302, 340), (418, 456), (534, 572), (662, 700)):
        c.arrow((MC, y0), (MC, y1))

    # ① 轴心 c → 原点 O（虚线）
    c.dot(860, 264)
    c.label(860, 244, "c")
    c.path([(868, 264), (1010, 264)], dashed=True)
    c.dot(1026, 264)
    c.label(1026, 244, "O")
    c.note(939, 240, "T(−c)")

    # ② 绕原点 O 旋转 θ
    c.dot(945, 380)
    c.label(945, 360, "O")
    c.ax.annotate("", xy=(1040, 404), xytext=(940, 404),
                  arrowprops=dict(arrowstyle="-|>", color=C_BORDER, lw=LW,
                                  mutation_scale=13,
                                  connectionstyle="arc3,rad=-0.45"), zorder=4)
    c.note(1000, 424, "R(θ)")

    # ③ 原点 O → 轴心 c（虚线）
    c.dot(860, 496)
    c.label(860, 476, "O")
    c.path([(868, 496), (1010, 496)], dashed=True)
    c.dot(1026, 496)
    c.label(1026, 476, "c")
    c.note(939, 472, "T(c)")

    c.note(MC, 824, "三阶段按顺序相乘：先把轴心搬走 → 再绕原点旋转 → 最后搬回原位")
    return c.save("fig09_绕轴心旋转三阶段分解.png")


# ---------------------------------------------------------------- fig10
def fig10():
    """Cohen-Sutherland 编码裁剪。"""
    c = Canvas(1240, 1060)
    MC = 480

    c.node(370, 36, 220, 72, ["开始"], "start")
    c.node(200, 138, 560, 80,
           ["输入线段端点 P0(x0,y0)、P1(x1,y1)",
            "矩形窗口 (x0′, y0′) − (x1′, y1′)"])
    c.node(200, 248, 560, 72, ["计算两端点的 4 位区域码"])
    c.node(400, 380, 360, 120, ["code0 | code1 == 0000 ?"], "dec")
    c.node(400, 550, 360, 120, ["code0 & code1 != 0000 ?"], "dec")
    c.node(200, 700, 560, 76, ["取窗口外的那个端点", "按其区域码所指的边界求交"])
    c.node(200, 806, 560, 76, ["用交点替换该端点", "回到「计算区域码」重新编码"])

    # 区域码图例
    c.node(820, 212, 360, 150,
           ["区域码 D3 D2 D1 D0", "D3 下 1000 · D2 上 0100", "D1 右 0010 · D0 左 0001"],
           fs=9, pitch=36)
    c.dashed_line((762, 284), (818, 284))

    c.node(820, 390, 360, 60, ["整段接受（输出）"])
    c.node(820, 580, 360, 60, ["同侧在外，整段舍弃"])
    c.node(820, 940, 360, 72, ["结束"], "end")

    c.arrow((MC, 108), (MC, 136))
    c.arrow((MC, 218), (MC, 246))
    c.arrow((MC, 320), (MC, 378))
    c.arrow((MC, 500), (MC, 548))
    c.label(MC + 22, 524, "否")
    c.arrow((MC, 670), (MC, 698))
    c.label(MC + 22, 684, "否")

    c.arrow((760, 440), (818, 440))
    c.label(789, 422, "是")
    c.arrow((760, 610), (818, 610))
    c.label(789, 592, "是")

    # 整段接受 → 结束（右侧绕行）
    c.path([(1182, 420), (1210, 420), (1210, 976), (1182, 976)])
    # 整段舍弃 → 结束
    c.arrow((1000, 642), (1000, 938))

    # 循环回「计算区域码」
    c.path([(198, 844), (120, 844), (120, 284), (198, 284)])

    c.note(MC, 906, "每轮至少消去 1 位，最多 4 轮")
    return c.save("fig10_Cohen-Sutherland编码裁剪.png")


# ---------------------------------------------------------------- fig11
def fig11():
    """Liang-Barsky 参数裁剪。"""
    c = Canvas(1360, 1600)
    MC = 520

    c.node(410, 30, 220, 66, ["开始"], "start")
    c.node(240, 126, 560, 76, ["参数化：P(t) = P0 + t·(P1−P0)，t ∈ [0,1]", "dx = P1.x − P0.x，dy = P1.y − P0.y"])
    c.node(240, 232, 560, 60, ["初始化 u0 = 0、u1 = 1"])
    c.node(240, 322, 560, 76, ["依次处理四条边界", "左 x=rx0 · 右 x=rx1 · 上 y=ry0 · 下 y=ry1"])
    c.node(240, 428, 560, 76, ["p = (−dx, dx, −dy, dy)", "q = (x0−rx0, rx1−x0, y0−ry0, ry1−y0)"])

    c.node(340, 534, 360, 120, ["p == 0 ?"], "dec")
    c.node(930, 534, 340, 120, ["q < 0 ?"], "dec")

    c.node(240, 694, 560, 76, ["t = q / p（该边界的交点参数）", "（t 落在 [0,1] 内时有效）"])
    c.node(950, 694, 300, 60, ["整段舍弃"])
    c.node(950, 784, 300, 60, ["跳过该边界"])

    c.node(340, 784, 360, 120, ["p < 0 ?"], "dec")
    c.node(100, 944, 220, 60, ["u0 = max(u0, t)"], fs=9)
    c.node(720, 944, 220, 60, ["u1 = min(u1, t)"], fs=9)
    c.node(140, 1034, 740, 60, ["更新后的参数区间 [u0, u1]"])
    c.node(340, 1144, 360, 120, ["u0 > u1 ?"], "dec")
    c.node(100, 1194, 220, 60, ["整段舍弃（区间为空）"], fs=9)
    c.node(240, 1304, 560, 60, ["下一条边界（共 4 条）"])
    c.node(240, 1394, 560, 70, ["输出 t ∈ [u0, u1] 对应的线段", "P0 + u0·D → P0 + u1·D"])
    c.node(410, 1494, 220, 66, ["结束"], "end")

    c.arrow((MC, 96), (MC, 124))
    c.arrow((MC, 202), (MC, 230))
    c.arrow((MC, 292), (MC, 320))
    c.arrow((MC, 398), (MC, 426))
    c.arrow((MC, 504), (MC, 532))

    # p == 0 ?
    c.arrow((700, 594), (928, 594))
    c.label(814, 576, "是")
    c.arrow((MC, 654), (MC, 692))
    c.label(MC + 22, 672, "否")

    # q < 0 ?
    c.arrow((1100, 654), (1100, 692))
    c.label(1122, 672, "是")
    c.path([(1272, 594), (1310, 594), (1310, 814), (1252, 814)])
    c.label(1298, 576, "否")

    # p < 0 ?
    c.path([(338, 844), (210, 844), (210, 942)])
    c.label(274, 826, "是")
    c.path([(702, 844), (830, 844), (830, 942)])
    c.label(766, 826, "否")

    c.arrow((210, 1004), (210, 1032))
    c.arrow((830, 1004), (830, 1032))
    c.arrow((MC, 1094), (MC, 1142))

    # u0 > u1 ?
    c.arrow((338, 1204), (322, 1204))
    c.label(330, 1186, "是")
    c.arrow((MC, 1264), (MC, 1302))
    c.label(MC + 22, 1282, "否")

    # 循环回「依次处理四条边界」
    c.path([(238, 1334), (40, 1334), (40, 360), (238, 360)])
    c.note(70, 860, "还有边界", ha="left")

    # 跳过该边界 → 下一条边界
    c.path([(1100, 846), (1100, 1334), (802, 1334)])

    # 舍弃分支 → 结束
    c.path([(948, 724), (900, 724), (900, 1528), (632, 1528)])
    c.path([(210, 1256), (210, 1528), (408, 1528)])

    c.arrow((MC, 1464), (MC, 1492))
    return c.save("fig11_Liang-Barsky参数裁剪.png")


# ---------------------------------------------------------------- fig12
def fig12():
    """Sutherland-Hodgman 逐边裁剪。"""
    c = Canvas(1240, 1160)
    MC = 460

    c.node(350, 30, 220, 66, ["开始"], "start")
    c.node(200, 126, 520, 84,
           ["输入被裁多边形顶点序列 P（浮点）", "凸窗口各边对应的半平面"])
    c.node(200, 240, 520, 84,
           ["对窗口的每条边（半平面）依次处理", "取当前顶点序列，遍历每条边 (S, E)"])
    c.node(200, 354, 520, 66, ["分类：S、E 是否在半平面内？"])

    # 四种内外组合的小表
    c.note(985, 258, "四种内外组合的输出")
    c.node(780, 276, 410, 52, ["内 → 内：输出 E"], fs=9, pitch=30)
    c.node(780, 328, 410, 52, ["内 → 外：输出交点（E 与该边求交）"], fs=9, pitch=30)
    c.node(780, 380, 410, 52, ["外 → 内：输出交点，再输出 E"], fs=9, pitch=30)
    c.node(780, 432, 410, 52, ["外 → 外：不输出"], fs=9, pitch=30)
    c.dashed_line((722, 387), (778, 360))

    c.node(200, 450, 520, 66, ["得到该半平面处理后的新顶点序列"])
    c.node(280, 536, 360, 120, ["还有下一条半平面？"], "dec")
    c.node(200, 686, 520, 66, ["所有半平面处理完毕 → 新顶点序列即交集多边形"])
    c.node(280, 800, 360, 120, ["顶点序列为空？"], "dec")
    c.node(780, 830, 360, 60, ["无交集"])
    c.node(200, 950, 520, 66, ["输出交集多边形"])
    c.node(350, 1046, 220, 66, ["结束"], "end")

    c.arrow((MC, 96), (MC, 124))
    c.arrow((MC, 210), (MC, 238))
    c.arrow((MC, 324), (MC, 352))
    c.arrow((MC, 420), (MC, 448))

    # 循环回「对窗口的每条边」
    c.path([(278, 596), (120, 596), (120, 282), (198, 282)])
    c.label(198, 578, "是")

    c.arrow((MC, 656), (MC, 684))
    c.label(MC + 22, 670, "否")

    c.arrow((MC, 752), (MC, 798))
    c.arrow((640, 860), (778, 860))
    c.label(709, 842, "是")
    c.arrow((MC, 920), (MC, 948))
    c.label(MC + 22, 934, "否")

    c.arrow((MC, 1016), (MC, 1044))
    c.path([(960, 892), (960, 1078), (572, 1078)])
    return c.save("fig12_Sutherland-Hodgman逐边裁剪.png")


# ---------------------------------------------------------------- fig13
def fig13():
    """Weiler-Atherton 双边裁剪。"""
    c = Canvas(1240, 1540)
    MC = 460

    c.node(350, 30, 220, 66, ["开始"], "start")
    c.node(200, 126, 520, 84,
           ["输入被裁多边形 P、窗口多边形 W", "W 可为任意简单多边形（含凹）"])
    c.node(200, 240, 520, 84,
           ["归一化：把 W 定向为逆时针", "按有向面积判断，为负则反向"])
    c.node(200, 354, 520, 66, ["对 P 的每条边"])
    c.node(200, 450, 520, 84, ["与 W 的各条边求交", "按参数 t 排序切分成若干子段"])
    c.node(200, 564, 520, 66, ["取子段中点，用射线法判断该点是否在 W 内"])
    c.node(200, 660, 520, 84,
           ["在 W 内 → 标记为「输出边界候选」", "并记录交点处是【进入】还是【离开】W"])
    c.node(280, 784, 360, 120, ["P 的边处理完毕？"], "dec")
    c.node(200, 934, 520, 84,
           ["对 W 的边落在 P 内的部分同样处理", "（交界的另一半）"])
    c.node(200, 1048, 520, 84,
           ["把输出段按「进入点 → 离开点 → 下一段」", "首尾相接成闭合环"])
    c.node(280, 1172, 360, 120, ["闭环是否存在？"], "dec")
    c.node(780, 1202, 360, 60, ["输出交集多边形"])
    c.node(200, 1322, 520, 60, ["无交集"])
    c.node(350, 1420, 220, 66, ["结束"], "end")

    c.arrow((MC, 96), (MC, 124))
    c.arrow((MC, 210), (MC, 238))
    c.arrow((MC, 324), (MC, 352))
    c.arrow((MC, 420), (MC, 448))
    c.arrow((MC, 534), (MC, 562))
    c.arrow((MC, 630), (MC, 658))
    c.arrow((MC, 744), (MC, 782))

    # P 的边循环
    c.path([(278, 844), (120, 844), (120, 387), (198, 387)])
    c.label(198, 826, "否")

    c.arrow((MC, 904), (MC, 932))
    c.label(MC + 22, 918, "是")
    c.arrow((MC, 1018), (MC, 1046))
    c.arrow((MC, 1132), (MC, 1170))

    c.arrow((640, 1232), (778, 1232))
    c.label(709, 1214, "是")
    c.arrow((MC, 1292), (MC, 1320))
    c.label(MC + 22, 1306, "否")

    c.arrow((MC, 1382), (MC, 1418))
    c.path([(960, 1264), (960, 1452), (572, 1452)])
    return c.save("fig13_Weiler-Atherton双边裁剪.png")


# ---------------------------------------------------------------- 架构图
def fig_arch():
    """二维变换与裁剪总体架构。"""
    c = Canvas(1580, 1240)
    LX, LW = 70, 880          # 层框
    DX, DW = 1080, 440        # 外围产物框

    c.node(LX, 36, LW, 184,
           ["表现层 ui/",
            "主窗口（应用模式 / 演示模式双模式）· 图标工具栏 · 像素画布 CanvasView",
            "右栏折叠卡：颜色 / 图元 / 视图、参数 / 算法公式",
            "决策项监视 / 播放控制 · 演示壳 DemoView"], pitch=34)

    c.node(LX, 260, LW, 184,
           ["课程模块层 modules/",
            "module03_transform2d：变换工具 Transform2DTool + 4 个演示页",
            "module04_clipping：裁剪工具 ClipTool + 5 个演示页",
            "每个模块在自己的 module.py 里 register() 声明，主框架不写死任何具体实验"],
           pitch=34)

    c.node(LX, 484, LW, 218,
           ["核心层 core/",
            "CanvasView 五层渲染：背景层 base / 预览层 preview / 选中层 / 手柄层 / 注记层",
            "Document + 命令栈（撤销 / 重做）· Shape 图元模型",
            "参数化存储 + erased 擦除掩码 + cuts 裁剪几何区",
            "transform_selection（整组变换记为一条命令）"], pitch=34)

    c.node(LX, 742, LW, 218,
           ["算法层 algorithms/（零 GUI 依赖，每个算法双出口：几何 + 步骤流）",
            "transform2d（3×3 仿射矩阵 / 求逆 / 椭圆协方差换算）",
            "cohen_sutherland · midpoint_clip · liang_barsky",
            "sutherland_hodgman · weiler_atherton",
            "window_mask（任意多边形窗口掩膜）"], pitch=34)

    c.node(LX, 1000, LW, 184,
           ["教学引擎层 teaching/",
            "DemoPlayer（步骤播放器：播放 / 暂停 / 单步 / 跳转 / 调速）",
            "MonitorPanel（决策项监视 + MatrixView 矩阵矢量图）",
            "PixelLayer（像素层 / 参照层 / 注记层）"], pitch=34)

    for y0, y1, tag in ((220, 260, "调用工具"),
                        (444, 484, "读写文档 / 提交命令"),
                        (702, 742, "调用几何算法"),
                        (960, 1000, "提供步骤流")):
        c.arrow((530, y0), (530, y1))
        c.label(545, (y0 + y1) / 2, tag, ha="left")

    c.dashed_node(DX, 484, DW, 218,
                  ["交付与验证",
                   "PyInstaller onefile exe + 源码",
                   "5 个自动化测试脚本",
                   "transform / clip / smoke /",
                   "render / algo_verify"], pitch=34)

    c.dashed_node(DX, 1000, DW, 150,
                  ["教学演示",
                   "每页一个算法 → 步骤流 →",
                   "逐帧动画 + 决策项实时显示"], pitch=34)

    c.arrow((LX + LW, 593), (DX, 593))
    c.label(1015, 576, "自动化测试")
    c.arrow((LX + LW, 1075), (DX, 1075))
    c.label(1015, 1058, "逐帧渲染")
    return c.save("fig07_二维变换与裁剪总体架构.png")


# ---------------------------------------------------------------- main
def main():
    os.makedirs(OUT, exist_ok=True)
    fig08()
    fig09()
    fig10()
    fig11()
    fig12()
    fig13()
    fig_arch()


if __name__ == "__main__":
    main()
