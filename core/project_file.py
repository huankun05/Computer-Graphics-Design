# -*- coding: utf-8 -*-
"""
=====================================================================
 core/project_file.py  —  画板工程文件读写（.gpad，JSON 格式）
=====================================================================
工程 = 全部图元的【参数列表】（不存像素位图），可保存/打开教学示例。
格式：
    {
      "app": "图形画板",
      "version": 1,
      "shapes": [
        {"kind": "line_dda", "color": "#222222", "width": 1,
         "p0": [x, y], "p1": [x, y]},
        {"kind": "circle", ..., "center": [x, y], "r": 120},
        {"kind": "ellipse", ..., "center": [...], "rx": 100, "ry": 60},
        {"kind": "polygon", ..., "vertices": [[x,y],...], "fill": true}
      ]
    }
未来新增图元类型只需扩展 _SAVERS/_LOADERS 两张表。
=====================================================================
"""

import json
import os
from typing import List

from PySide6.QtGui import QColor

from core.shapes import (
    Shape, LineShape, CircleShape, EllipseShape, PolygonShape,
    RasterFillShape,
    KIND_LINE_DDA, KIND_LINE_BRESENHAM, KIND_CIRCLE, KIND_CIRCLE_MID,
    KIND_CIRCLE_DDA, KIND_ELLIPSE, KIND_POLYGON, KIND_RASTER_FILL,
)

# 圆类算法键 → CircleShape（rasterizer 再按 kind 分派具体算法）
_CIRCLE_KINDS = (KIND_CIRCLE, KIND_CIRCLE_MID, KIND_CIRCLE_DDA)

PROJECT_SUFFIX = "画板工程 (*.gpad)"


# ---------------------------------------------------------------------
# 图元 → dict
# ---------------------------------------------------------------------
def _shape_to_dict(idx: int, s: Shape, all_shapes: List[Shape]) -> dict:
    d = {"kind": s.kind, "color": s.color.name(), "width": s.width,
         "visible": s.visible, "fill": s.fill}
    if s.inset:
        d["inset"] = s.inset
    if getattr(s, "erased", None):
        d["erased"] = sorted(s.erased)
    if getattr(s, "cuts", None):
        # 裁剪窗口（几何区域）：顶点可能带小数（窗口被旋转/缩放过）
        d["cuts"] = [[list(v) for v in poly] for poly in s.cuts]
    owner = getattr(s, "owner", None)
    if owner is not None:
        for j, cand in enumerate(all_shapes):
            if cand is owner:                    # 身份比较（dataclass 值相等会误配）
                d["owner"] = j
                break
    if isinstance(s, LineShape):
        d["p0"] = list(s.p0)
        d["p1"] = list(s.p1)
    elif isinstance(s, CircleShape):
        d["center"] = list(s.center)
        d["r"] = s.r
    elif isinstance(s, EllipseShape):
        d["center"] = list(s.center)
        d["rx"], d["ry"] = s.rx, s.ry
        d["angle"] = round(float(getattr(s, "angle", 0.0)), 4)
    elif isinstance(s, PolygonShape):
        d["vertices"] = [list(v) for v in s.vertices]
        d["fill"] = s.fill
    elif isinstance(s, RasterFillShape):
        d["seed"] = list(s.seed)
        d["pixels"] = [list(p) for p in s.pixels]
        if s.conn is not None:
            d["conn"] = int(s.conn)
        if s.algo is not None:
            d["algo"] = s.algo
    return d


def _dict_to_shape(d: dict) -> Shape:
    kind = d.get("kind", "")
    color = QColor(d.get("color", "#222222"))
    width = int(d.get("width", 1))
    visible = bool(d.get("visible", True))
    s: Shape
    if kind in (KIND_LINE_DDA, KIND_LINE_BRESENHAM):
        s = LineShape(kind=kind, color=color, width=width)
        s.p0 = tuple(d["p0"])
        s.p1 = tuple(d["p1"])
    elif kind in _CIRCLE_KINDS:
        s = CircleShape(kind=kind, color=color, width=width)
        s.center = tuple(d["center"])
        s.r = int(d["r"])
    elif kind == KIND_ELLIPSE:
        s = EllipseShape(kind=kind, color=color, width=width)
        s.center = tuple(d["center"])
        s.rx, s.ry = int(d["rx"]), int(d["ry"])
        s.angle = float(d.get("angle", 0.0))    # 旧工程缺省 0°
    elif kind == KIND_POLYGON:
        s = PolygonShape(kind=kind, color=color, width=width)
        s.vertices = [tuple(v) for v in d["vertices"]]
        s.fill = bool(d.get("fill", True))     # 旧工程多边形默认填充
    elif kind == KIND_RASTER_FILL:
        s = RasterFillShape(kind=kind, color=color, width=width)
        s.seed = tuple(d.get("seed", (0, 0)))
        s.pixels = [tuple(p) for p in d.get("pixels", [])]
        s.conn = d.get("conn")
        s.algo = d.get("algo")
    else:
        raise ValueError(f"未知图元类型: {kind}")
    s.visible = visible
    s.inset = int(d.get("inset", 0))
    s.erased = set(tuple(e) for e in d.get("erased", []))
    # 裁剪窗口（几何挖除区域）：旧工程文件没有这个键 → 空列表
    s.cuts = [[(float(x), float(y)) for x, y in poly]
              for poly in d.get("cuts", [])]
    if kind != KIND_POLYGON:
        s.fill = bool(d.get("fill", False))    # 圆/椭圆填充默认关
    return s


# ---------------------------------------------------------------------
# 文件读写
# ---------------------------------------------------------------------
def save_project(path: str, shapes: List[Shape]) -> bool:
    """保存工程文件。失败抛 OSError，由调用方提示。"""
    lst = list(shapes)
    data = {
        "app": "图形画板",
        "version": 2,       # v2：椭圆 angle / 填充 conn+algo / 光栅填充像素
        "shapes": [_shape_to_dict(i, s, lst) for i, s in enumerate(lst)],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return True


def load_project(path: str) -> List[Shape]:
    """读取工程文件，返回图元列表。格式错误抛 ValueError/OSError/KeyError。"""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "shapes" not in data:
        raise ValueError("不是有效的画板工程文件")
    out = [_dict_to_shape(d) for d in data["shapes"]]
    # 二遍恢复填充的归属链接（owner 存的是图元索引）
    for d, s in zip(data["shapes"], out):
        idx = d.get("owner")
        if isinstance(idx, int) and 0 <= idx < len(out):
            s.owner = out[idx]
    return out
