# -*- coding: utf-8 -*-
"""
=====================================================================
 core/shapes.py  —  图元数据结构定义
=====================================================================
本文件定义画布上所有可持久化图元的数据类。

设计要点：
  - 图元只保存【几何参数 + 算法名 + 样式】，不保存像素位图；
  - 每次重绘时，由对应的算法函数根据几何参数重新计算像素，
    这样后续课程的"二维几何变换 / 裁剪"只需要修改几何参数，
    再触发重绘即可，不需要操作位图。
=====================================================================
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from PySide6.QtGui import QColor

# ------------------------------------------------------------------
# 画布几何常量（模拟像素体系）
# ------------------------------------------------------------------
# 位图真实分辨率 1200×800；SIM=20 表示 1 个"模拟像素"占 20×20 位图。
# 算法（DDA/Bresenham 等）运行在 60×40 的模拟像素网格上，
# 每个算法输出像素渲染为一个 SIM×SIM 的方块 —— 网格即像素格，
# 教学时直接看到教科书式的阶梯像素（规范：一个网格 = 一个像素）。
SIM = 20
IMAGE_W, IMAGE_H = 1200, 800
GRID_W, GRID_H = IMAGE_W // SIM, IMAGE_H // SIM   # 逻辑分辨率 60×40


# ------------------------------------------------------------------
# 图元类型枚举（字符串常量，方便序列化）
# ------------------------------------------------------------------
KIND_RASTER_FILL    = "raster_fill"     # 种子填充结果（存像素清单）
KIND_LINE_DDA       = "line_dda"
KIND_LINE_BRESENHAM = "line_bresenham"
KIND_CIRCLE         = "circle"          # 旧键，兼容旧工程文件（= 中点圆）
KIND_CIRCLE_MID     = "circle_mid"      # 中点圆
KIND_CIRCLE_DDA     = "circle_dda"      # DDA 圆（角度采样）
KIND_ELLIPSE        = "ellipse"
KIND_POLYGON        = "polygon"


# ------------------------------------------------------------------
# 几何变换 / 快照（选择移动工具与命令栈共用）
# ------------------------------------------------------------------
# 统一走 algorithms/transform2d.py 的仿射矩阵，避免每种图元各写一套
# 平移/缩放公式；旋转、非等比缩放、错切以后都复用同一入口。
from algorithms import transform2d as tf


def _round_point(p) -> Tuple[int, int]:
    """浮点坐标 → 模拟像素整数坐标（四舍五入）。"""
    return int(round(p[0])), int(round(p[1]))


def _map_erased(shape: "Shape", m: tf.Mat3):
    """擦除掩码跟随几何一起变换（否则移动后擦除洞会留在原地）。"""
    if shape.erased:
        shape.erased = {_round_point(tf.apply(m, p)) for p in shape.erased}


def _replace_circle_with_ellipse(shape: "CircleShape",
                                 cx, cy, rx, ry, angle):
    """圆在非等比变换后原地转成椭圆（保持对象身份，选择状态不丢）。"""
    shape.__class__ = EllipseShape
    shape.__dict__.pop("r", None)
    shape.center = _round_point((cx, cy))
    shape.rx = max(1, int(round(rx)))
    shape.ry = max(1, int(round(ry)))
    shape.angle = tf.normalize_angle(angle)


def transform_shape(shape: "Shape", m: tf.Mat3):
    """对图元做任意仿射变换（就地修改，含擦除掩码）。

    直线/多边形：直接变换顶点，保证参数化存储；
    圆/椭圆：用协方差矩阵特征分解精确换算半轴与旋转角，
              圆在非等比缩放下自动变成椭圆；
    光栅填充：映射像素清单与种子（允许负坐标，不做 0 钳制）。
    """
    _map_erased(shape, m)
    if isinstance(shape, LineShape):
        shape.p0 = _round_point(tf.apply(m, shape.p0))
        shape.p1 = _round_point(tf.apply(m, shape.p1))
    elif isinstance(shape, CircleShape):
        cx, cy, rx, ry, ang = tf.ellipse_from_matrix(
            shape.center[0], shape.center[1], shape.r, shape.r, 0.0, m)
        if abs(rx - ry) <= 0.75:                 # 仍接近正圆 → 保持圆
            shape.center = _round_point((cx, cy))
            shape.r = max(1, int(round((rx + ry) / 2.0)))
        else:                                     # 非等比 → 精确转椭圆
            _replace_circle_with_ellipse(shape, cx, cy, rx, ry, ang)
    elif isinstance(shape, EllipseShape):
        cx, cy, rx, ry, ang = tf.ellipse_from_matrix(
            shape.center[0], shape.center[1], shape.rx, shape.ry,
            getattr(shape, "angle", 0.0), m)
        shape.center = _round_point((cx, cy))
        shape.rx = max(1, int(round(rx)))
        shape.ry = max(1, int(round(ry)))
        shape.angle = tf.normalize_angle(ang)
    elif isinstance(shape, PolygonShape):
        shape.vertices = [_round_point(tf.apply(m, v))
                          for v in shape.vertices]
    elif isinstance(shape, RasterFillShape):
        shape.seed = _round_point(tf.apply(m, shape.seed))
        shape.pixels = [_round_point(tf.apply(m, p)) for p in shape.pixels]


def translate(shape: "Shape", dx: int, dy: int):
    """把图元几何参数整体平移（就地修改，擦除掩码同步移动）。"""
    transform_shape(shape, tf.translation(dx, dy))


def snapshot(shape: "Shape") -> dict:
    """抓取几何参数快照（深拷贝，供命令 undo/redo 精确还原）。

    额外记录 __cls__ 与 erased：圆↔椭圆转换、擦除掩码变换后
    撤销/取消都能恢复到变换前的类型与掩码。
    """
    snap = {"__cls__": type(shape), "erased": set(shape.erased)}
    if isinstance(shape, LineShape):
        snap.update(p0=shape.p0, p1=shape.p1)
    elif isinstance(shape, CircleShape):
        snap.update(center=shape.center, r=shape.r)
    elif isinstance(shape, EllipseShape):
        snap.update(center=shape.center, rx=shape.rx, ry=shape.ry,
                    angle=getattr(shape, "angle", 0.0))
    elif isinstance(shape, PolygonShape):
        snap.update(vertices=list(shape.vertices))
    elif isinstance(shape, RasterFillShape):
        snap.update(seed=shape.seed, pixels=list(shape.pixels))
    return snap


def restore(shape: "Shape", snap: dict):
    """按快照还原几何参数（必要时恢复图元类型）。"""
    cls = snap.get("__cls__")
    if cls is not None and shape.__class__ is not cls:
        shape.__class__ = cls
        # 清理另一类型才有的字段，避免残留属性干扰后续保存/判定
        if cls is CircleShape:
            for k in ("rx", "ry", "angle"):
                shape.__dict__.pop(k, None)
        elif cls is EllipseShape:
            shape.__dict__.pop("r", None)
    for k, v in snap.items():
        if k == "__cls__":
            continue
        setattr(shape, k, v)


def _anchor_of(snap: dict, anchor: tuple = None):
    """取缩放定点：显式 anchor 优先，否则圆心/中点/质心。"""
    if anchor is not None:
        return float(anchor[0]), float(anchor[1])
    if "center" in snap:
        return float(snap["center"][0]), float(snap["center"][1])
    if "p0" in snap:
        return ((snap["p0"][0] + snap["p1"][0]) / 2.0,
                (snap["p0"][1] + snap["p1"][1]) / 2.0)
    if "vertices" in snap and snap["vertices"]:
        vs = snap["vertices"]
        return (sum(v[0] for v in vs) / len(vs),
                sum(v[1] for v in vs) / len(vs))
    if "pixels" in snap and snap["pixels"]:
        px = snap["pixels"]
        return (sum(p[0] for p in px) / len(px),
                sum(p[1] for p in px) / len(px))
    return 0.0, 0.0


def scale_snapshot(kind: str, snap: dict, fx: float,
                   fy: float = None, anchor: tuple = None) -> dict:
    """按系数缩放一份几何快照（返回新快照，不改原图元）。

    fx/fy   X/Y 轴缩放系数（fy 缺省 = 等比）；
    anchor  定点（缩放围绕的点），缺省 = 形状自身的圆心/中点/质心。
    系数钳制在 0.05~20，防止缩没或爆掉。

    与旧实现相比：
      - 圆在 fx≠fy 时按真实仿射变换转成椭圆，而不是只乘 fx；
      - 椭圆支持旋转角，旋转后的非等比缩放也能正确换算；
      - 光栅填充不再把负坐标钳到 0；
      - 擦除掩码随几何一起缩放。
    """
    fx = max(0.05, min(20.0, float(fx)))
    fy = fx if fy is None else max(0.05, min(20.0, float(fy)))
    ax, ay = _anchor_of(snap, anchor)
    m = tf.around((ax, ay), tf.scaling(fx, fy))
    out = dict(snap)

    if "erased" in out:
        out["erased"] = {_round_point(tf.apply(m, p))
                         for p in out["erased"]}

    if "r" in out:                                   # 圆
        cx, cy, nrx, nry, ang = tf.ellipse_from_matrix(
            out["center"][0], out["center"][1], out["r"], out["r"], 0.0, m)
        out["center"] = _round_point((cx, cy))
        if abs(nrx - nry) <= 0.75:                   # 仍接近正圆
            out["r"] = max(1, int(round((nrx + nry) / 2.0)))
            out["__cls__"] = CircleShape
        else:                                         # 非等比 → 椭圆
            out.pop("r", None)
            out.update(rx=max(1, int(round(nrx))),
                       ry=max(1, int(round(nry))),
                       angle=tf.normalize_angle(ang),
                       __cls__=EllipseShape)
    elif "rx" in out:                                # 椭圆（含旋转角）
        cx, cy, nrx, nry, ang = tf.ellipse_from_matrix(
            out["center"][0], out["center"][1], out["rx"], out["ry"],
            out.get("angle", 0.0), m)
        out["center"] = _round_point((cx, cy))
        out["rx"] = max(1, int(round(nrx)))
        out["ry"] = max(1, int(round(nry)))
        out["angle"] = tf.normalize_angle(ang)
        out["__cls__"] = EllipseShape
    elif "p0" in out:                                # 直线
        out["p0"] = _round_point(tf.apply(m, out["p0"]))
        out["p1"] = _round_point(tf.apply(m, out["p1"]))
    elif "vertices" in out:                          # 多边形
        out["vertices"] = [_round_point(tf.apply(m, v))
                           for v in out["vertices"]]
    elif "pixels" in out:                            # 光栅填充
        out["pixels"] = [_round_point(tf.apply(m, p))
                         for p in out["pixels"]]
        out["seed"] = _round_point(tf.apply(m, out["seed"]))
    return out


@dataclass
class Shape:
    """所有图元的基类。"""
    kind: str                                   # 图元类型
    color: QColor = field(default_factory=lambda: QColor("#e0e0e0"))
    width: int = 1                              # 线宽（模拟像素体系下固定 1 格）
    visible: bool = True                        # 显隐（图元列表眼睛开关）
    fill: bool = False                          # 填充模式（闭合形状：圆/椭圆/多边形）
    inset: int = 0                              # 内缩渲染（分层显示用）
    erased: set = field(default_factory=set)    # 橡皮擦擦除掩码（模拟像素坐标集合）


@dataclass
class LineShape(Shape):
    """直线段。p0 -> p1，像素整数坐标。"""
    p0: Tuple[int, int] = (0, 0)
    p1: Tuple[int, int] = (0, 0)


@dataclass
class CircleShape(Shape):
    """圆。center=(cx,cy)，r 为半径。"""
    center: Tuple[int, int] = (0, 0)
    r: int = 0


@dataclass
class EllipseShape(Shape):
    """椭圆。center=(cx,cy)，rx/ry 为半轴，angle 为主轴旋转角（度）。"""
    center: Tuple[int, int] = (0, 0)
    rx: int = 0
    ry: int = 0
    angle: float = 0.0      # 屏幕坐标下正角 = 视觉顺时针


@dataclass
class RasterFillShape(Shape):
    """种子/扫描线填充结果：直接存储填充像素清单（填充是光栅操作）。"""
    seed: Tuple[int, int] = (0, 0)
    pixels: List[Tuple[int, int]] = field(default_factory=list)
    owner: "Shape" = None    # 归属的边界图元：移动/缩放/删除整体联动
    conn: Optional[int] = None   # 种子填充连通性（4/8），扫描线填充为 4
    algo: Optional[str] = None   # 生成算法：seed4 / seed8 / scanline


@dataclass
class PolygonShape(Shape):
    """多边形顶点列表（用于扫描线填充）。fill 继承基类（False=只画边框）。"""
    vertices: List[Tuple[int, int]] = field(default_factory=list)
