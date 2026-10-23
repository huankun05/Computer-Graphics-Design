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
from typing import List, Tuple
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
# 几何参数的平移 / 快照（选择移动工具与 MoveShapeCommand 共用）
# ------------------------------------------------------------------
def translate(shape: "Shape", dx: int, dy: int):
    """把图元几何参数整体平移（就地修改）。"""
    if isinstance(shape, LineShape):
        shape.p0 = (shape.p0[0] + dx, shape.p0[1] + dy)
        shape.p1 = (shape.p1[0] + dx, shape.p1[1] + dy)
    elif isinstance(shape, CircleShape):
        shape.center = (shape.center[0] + dx, shape.center[1] + dy)
    elif isinstance(shape, EllipseShape):
        shape.center = (shape.center[0] + dx, shape.center[1] + dy)
    elif isinstance(shape, PolygonShape):
        shape.vertices = [(x + dx, y + dy) for x, y in shape.vertices]
    elif isinstance(shape, RasterFillShape):
        shape.seed = (shape.seed[0] + dx, shape.seed[1] + dy)
        shape.pixels = [(x + dx, y + dy) for x, y in shape.pixels]


def snapshot(shape: "Shape") -> dict:
    """抓取几何参数快照（深拷贝，供命令 undo/redo 精确还原）。"""
    if isinstance(shape, LineShape):
        return {"p0": shape.p0, "p1": shape.p1}
    if isinstance(shape, CircleShape):
        return {"center": shape.center, "r": shape.r}
    if isinstance(shape, EllipseShape):
        return {"center": shape.center, "rx": shape.rx, "ry": shape.ry}
    if isinstance(shape, PolygonShape):
        return {"vertices": list(shape.vertices)}
    if isinstance(shape, RasterFillShape):
        return {"seed": shape.seed, "pixels": list(shape.pixels)}
    return {}


def restore(shape: "Shape", snap: dict):
    """按快照还原几何参数。"""
    for k, v in snap.items():
        setattr(shape, k, v)


def scale_snapshot(kind: str, snap: dict, fx: float,
                   fy: float = None, anchor: tuple = None) -> dict:
    """按系数缩放一份几何快照（返回新快照，不改原图元）。

    fx/fy   X/Y 轴缩放系数（fy 缺省 = 等比）；
    anchor  定点（缩放围绕的点），缺省 = 形状自身的圆心/中点/质心：
            圆/椭圆以圆心为定点（半径/半轴 ×系数）；
            直线以中点、多边形以质心为定点。
    系数钳制在 0.05~20，防止缩没或爆掉。
    """
    fx = max(0.05, min(20.0, fx))
    fy = fx if fy is None else max(0.05, min(20.0, fy))
    out = {k: (tuple(v) if isinstance(v, tuple) else
               [tuple(p) for p in v] if isinstance(v, list) else v)
           for k, v in snap.items()}
    if "r" in out:                                   # 圆：圆心定点，等比
        out["r"] = max(1, int(round(out["r"] * fx)))
    elif "rx" in out:                                # 椭圆：圆心定点
        out["rx"] = max(1, int(round(out["rx"] * fx)))
        out["ry"] = max(1, int(round(out["ry"] * fy)))
    elif "p0" in out:                                # 直线
        ax, ay = (anchor if anchor else
                  ((out["p0"][0] + out["p1"][0]) / 2,
                   (out["p0"][1] + out["p1"][1]) / 2))
        for k in ("p0", "p1"):
            out[k] = (int(round(ax + (out[k][0] - ax) * fx)),
                      int(round(ay + (out[k][1] - ay) * fy)))
    elif "vertices" in out:                          # 多边形
        vs = out["vertices"]
        ax = sum(v[0] for v in vs) / len(vs)
        ay = sum(v[1] for v in vs) / len(vs)
        ax, ay = (anchor if anchor else (ax, ay))
        out["vertices"] = [(int(round(ax + (x - ax) * fx)),
                            int(round(ay + (y - ay) * fy))) for x, y in vs]
    elif "pixels" in out:                            # 光栅填充（像素集合）
        px = out["pixels"]
        if anchor:
            ax, ay = anchor
        else:
            ax = sum(p[0] for p in px) / len(px)
            ay = sum(p[1] for p in px) / len(px)
        out["pixels"] = [(max(0, int(round(ax + (x - ax) * fx))),
                          max(0, int(round(ay + (y - ay) * fy))))
                         for x, y in px]
        sx, sy = out["seed"]
        out["seed"] = (max(0, int(round(ax + (sx - ax) * fx))),
                       max(0, int(round(ay + (sy - ay) * fy))))
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
    """椭圆。center=(cx,cy)，rx/ry 分别为 x/y 方向半轴。"""
    center: Tuple[int, int] = (0, 0)
    rx: int = 0
    ry: int = 0


@dataclass
class RasterFillShape(Shape):
    """种子/扫描线填充结果：直接存储填充像素清单（填充是光栅操作）。"""
    seed: Tuple[int, int] = (0, 0)
    pixels: List[Tuple[int, int]] = field(default_factory=list)
    owner: "Shape" = None    # 归属的边界图元：移动/缩放/删除整体联动


@dataclass
class PolygonShape(Shape):
    """多边形顶点列表（用于扫描线填充）。fill 继承基类（False=只画边框）。"""
    vertices: List[Tuple[int, int]] = field(default_factory=list)
