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
GUIDE_MOVE = "#7C3AED"     # 线段/图形自身的变化（紫）：端点移动、当前处理的边


def point_guide(xy: Pixel, label: str = "", color: str = GUIDE_HIT) -> dict:
    """点注记（交点、端点、轴心、映射点）。"""
    return {"kind": "point", "xy": (int(xy[0]), int(xy[1])),
            "label": label, "color": color}


def line_guide(a: Pixel, b: Pixel, color: str = GUIDE_REF,
               dash: bool = True, width: float = 1.6) -> dict:
    """线注记（边界线、连线、扫描线）。width 可加粗用于"当前处理的那条边"。"""
    return {"kind": "line", "a": (int(a[0]), int(a[1])),
            "b": (int(b[0]), int(b[1])), "color": color, "dash": dash,
            "width": float(width)}


def boundary_guide(a: Pixel, b: Pixel, color: str = GUIDE_REF,
                   dash: bool = True, width: float = 1.6) -> dict:
    """窗口边界线注记——坐标按【格子边缘】解释，而不是格心。

    与 line_guide 的区别：line_guide 穿过格心（扫描线、连线用它对），
    而裁剪的边界必须压在格子的边上。窗口是闭区间 x0..x1，连续外沿
    恰是 x0 与 x1+1——画在格心上会和红色窗口框差半格（用户反馈：
    "边界显示有问题"）。
    """
    return {"kind": "boundary", "a": (int(a[0]), int(a[1])),
            "b": (int(b[0]), int(b[1])), "color": color, "dash": dash,
            "width": float(width)}


def edge_guide(rect: Tuple[int, int, int, int], side: str,
               color: str = GUIDE_MARK, label: str = "") -> dict:
    """当前正在使用的那条窗口边（整条高亮，画在红框外侧 2px）。

    裁剪演示的关键是"这一轮用的哪条边"：只画窗口外的延长段太短，
    看不清；整条压在红框上又会把红框染色（用户反馈）。折中方案 =
    沿这条边、在红框外侧偏移 2px 画一条更粗的实线，红框始终完整。
    side ∈ left / right / top / bottom。
    """
    return {"kind": "edge", "rect": tuple(int(v) for v in rect),
            "side": side, "color": color, "label": label}


def arrow_guide(a: Pixel, b: Pixel, color: str = GUIDE_MARK) -> dict:
    """箭头注记（P → P′ 的位移）。"""
    return {"kind": "arrow", "a": (int(a[0]), int(a[1])),
            "b": (int(b[0]), int(b[1])), "color": color}


def border_extension_segments(rect: Tuple[int, int, int, int], ext: int = 5):
    """窗口四条边 → 只画在窗口【外侧】的延长线段（8 段）。

    9 区划分、逐边判定用的边界线与窗口框线是同一位置：若整条画上去，
    灰色/橙色线会压在红色窗口框上（用户反馈"演示中边界颜色全变了"）。
    这里把每条边拆成窗口外的两截，红框本身保持完整可见。
    坐标按格子边缘（右/下 = x1+1 / y1+1），与 boundary_guide 口径一致。

    返回 [(边名, a, b), ...]，边名 ∈ left/right/top/bottom。
    """
    rx0, ry0, rx1, ry1 = rect
    ox1, oy1 = rx1 + 1, ry1 + 1          # 闭区间 → 连续外边界
    bx0, by0, bx1, by1 = rx0 - ext, ry0 - ext, ox1 + ext, oy1 + ext
    return [("left", (rx0, by0), (rx0, ry0)),
            ("left", (rx0, oy1), (rx0, by1)),
            ("right", (ox1, by0), (ox1, ry0)),
            ("right", (ox1, oy1), (ox1, by1)),
            ("top", (bx0, ry0), (rx0, ry0)),
            ("top", (ox1, ry0), (bx1, ry0)),
            ("bottom", (bx0, oy1), (rx0, oy1)),
            ("bottom", (ox1, oy1), (bx1, oy1))]


def rect_guide(xy: Tuple[int, int, int, int],
               color: str = "#E5484D") -> dict:
    """矩形注记（裁剪窗口边框）。xy = (x0, y0, x1, y1)。"""
    return {"kind": "rect", "xy": tuple(int(v) for v in xy), "color": color}


def polygon_guide(points, color: str = GUIDE_HIT, dash: bool = True,
                  width: float = 2.2) -> dict:
    """多边形轮廓注记（Sutherland-Hodgman 的"当前结果多边形"）。

    与 Step.pixels 分离：逐边裁剪的中间多边形是算法的演算产物，
    若混进像素，演示层就会与"原图像素"求交而被整段过滤掉
    （用户反馈：看不到逐顶点生长的过程）。顶点按格心绘制，首尾自动闭合。
    """
    return {"kind": "polygon",
            "points": [(int(p[0]), int(p[1])) for p in points],
            "color": color, "dash": dash, "width": float(width)}


def label_guide(xy: Pixel, text: str, color: str = GUIDE_REF,
                align: str = "left", valign: str = "above") -> dict:
    """文字注记（挂在某个像素位置旁边）。

    align：left / center / right —— 文字相对锚点的水平对齐；
    valign：above / middle / below —— 相对锚点格的垂直位置。
    默认保持旧行为（锚点右侧、格子之上）；分区标签用 center+middle
    才能真正居中在区域里，边界名用 right/left 才能贴边而不压到窗口。
    """
    return {"kind": "label", "xy": (int(xy[0]), int(xy[1])),
            "text": str(text), "color": color,
            "align": align, "valign": valign}


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

    # 显示用的浅色像素（填充区）：必须是 pixels 的子集。
    # 演示层用淡色画这一部分、用主色画其余 —— 否则填充和轮廓同一颜色，
    # 分不清哪是图形边界、哪是填充（用户反馈）。不参与任何几何判定，
    # 也不影响"末帧像素 = 几何结果"的契约。
    tint: List[Pixel] = field(default_factory=list)


def expand_steps(steps: List["Step"]) -> List[Pixel]:
    """把步骤流展开成最终像素列表（按生成顺序，含重复——与逐点绘制一致）。"""
    return [px for step in steps for px in step.pixels]
