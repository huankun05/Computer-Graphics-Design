# -*- coding: utf-8 -*-
"""
=====================================================================
 algorithms/transform2d.py  —  二维仿射变换数学内核（纯 Python）
=====================================================================
本模块只做数学：3×3 齐次矩阵、平移/旋转/缩放、矩阵复合、
点变换、矩阵求逆，以及【椭圆参数在任意仿射变换下的精确换算】。

约定：
  - 画布使用屏幕坐标系（y 轴向下），因此标准旋转矩阵
        [cosθ  -sinθ]
        [sinθ   cosθ]
    在视觉上表现为【顺时针】旋转，θ 为正即顺时针；
  - 矩阵作用于列向量 p = (x, y, 1)^T；
  - compose(A, B) 表示先做 B、再做 A（A @ B）。

椭圆变换原理：
  椭圆可写成参数形式 p(t) = c + R(θ)·diag(rx, ry)·(cos t, sin t)。
  令协方差矩阵 M = R·diag(rx², ry²)·R^T，经过线性部分 A 后
  M' = A·M·A^T；对 M' 做 2×2 对称矩阵特征分解即可还原
  新的半轴与旋转角。该方法对旋转、非等比缩放、错切都精确成立。
=====================================================================
"""

from __future__ import annotations

import math
from typing import Tuple

Mat3 = Tuple[Tuple[float, float, float],
             Tuple[float, float, float],
             Tuple[float, float, float]]

_EPS = 1e-9


# ---------------------------------------------------------------------
# 矩阵构造
# ---------------------------------------------------------------------
def identity() -> Mat3:
    """单位矩阵。"""
    return ((1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0))


def translation(dx: float, dy: float) -> Mat3:
    """平移矩阵。"""
    return ((1.0, 0.0, float(dx)),
            (0.0, 1.0, float(dy)),
            (0.0, 0.0, 1.0))


def rotation(angle_deg: float) -> Mat3:
    """旋转矩阵（屏幕坐标下正角 = 视觉顺时针）。"""
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return ((c, -s, 0.0),
            (s, c, 0.0),
            (0.0, 0.0, 1.0))


def scaling(sx: float, sy: float = None) -> Mat3:
    """缩放矩阵；sy 缺省表示等比缩放。"""
    sy = sx if sy is None else sy
    return ((float(sx), 0.0, 0.0),
            (0.0, float(sy), 0.0),
            (0.0, 0.0, 1.0))


def multiply(a: Mat3, b: Mat3) -> Mat3:
    """矩阵乘法 a @ b。"""
    return tuple(
        tuple(a[i][0] * b[0][j] + a[i][1] * b[1][j] +
              a[i][2] * b[2][j] for j in range(3))
        for i in range(3)
    )  # type: ignore[return-value]


def compose(*mats: Mat3) -> Mat3:
    """按参数从左到右复合：compose(A, B, C) 等价于 A @ B @ C。

    作用到点上时 C 最先执行，A 最后执行。
    """
    out = identity()
    for m in mats:
        out = multiply(out, m)
    return out


def around(pivot: Tuple[float, float], m: Mat3) -> Mat3:
    """把线性/缩放类变换绕 pivot 执行（先移到原点，变换，再移回）。"""
    px, py = float(pivot[0]), float(pivot[1])
    return compose(translation(px, py), m, translation(-px, -py))


# ---------------------------------------------------------------------
# 点变换 / 求逆
# ---------------------------------------------------------------------
def apply(m: Mat3, p: Tuple[float, float]) -> Tuple[float, float]:
    """变换一个点，返回浮点坐标。"""
    x, y = float(p[0]), float(p[1])
    return (m[0][0] * x + m[0][1] * y + m[0][2],
            m[1][0] * x + m[1][1] * y + m[1][2])


def apply_int(m: Mat3, p: Tuple[float, float]) -> Tuple[int, int]:
    """变换一个点并取整（模拟像素坐标）。"""
    x, y = apply(m, p)
    return int(round(x)), int(round(y))


def inverse(m: Mat3) -> Mat3:
    """仿射矩阵求逆（第三行固定为 0,0,1）。"""
    a, b, tx = m[0]
    c, d, ty = m[1]
    det = a * d - b * c
    if abs(det) < _EPS:
        raise ValueError("矩阵不可逆（行列式接近 0）")
    ia, ib = d / det, -b / det
    ic, id_ = -c / det, a / det
    itx = -(ia * tx + ib * ty)
    ity = -(ic * tx + id_ * ty)
    return ((ia, ib, itx),
            (ic, id_, ity),
            (0.0, 0.0, 1.0))


# ---------------------------------------------------------------------
# 椭圆参数变换
# ---------------------------------------------------------------------
def normalize_angle(angle_deg: float) -> float:
    """把角度归一化到 [0, 180)：椭圆旋转 180° 与 0° 等价。"""
    a = math.fmod(float(angle_deg), 180.0)
    if a < 0:
        a += 180.0
    if a >= 180.0:
        a -= 180.0
    return a


def ellipse_covariance(rx: float, ry: float, angle_deg: float) -> tuple:
    """返回椭圆的 2×2 协方差矩阵 (a, b, c)，对应 [[a, b], [b, c]]。"""
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    rx2, ry2 = rx * rx, ry * ry
    m00 = c * c * rx2 + s * s * ry2
    m01 = c * s * (rx2 - ry2)
    m11 = s * s * rx2 + c * c * ry2
    return m00, m01, m11


def ellipse_from_matrix(cx: float, cy: float, rx: float, ry: float,
                        angle_deg: float, m: Mat3
                        ) -> Tuple[float, float, float, float, float]:
    """把椭圆参数经过仿射矩阵 m 变换，返回新的 (cx, cy, rx, ry, angle)。

    线性部分 A = m[:2, :2]；协方差 M' = A·M·A^T；
    再对 M' 做对称矩阵特征分解，得到新的半轴与主轴方向。
    """
    ncx, ncy = apply(m, (cx, cy))
    a11, a12 = m[0][0], m[0][1]
    a21, a22 = m[1][0], m[1][1]

    m00, m01, m11 = ellipse_covariance(rx, ry, angle_deg)
    # A·M
    am00 = a11 * m00 + a12 * m01
    am01 = a11 * m01 + a12 * m11
    am10 = a21 * m00 + a22 * m01
    am11 = a21 * m01 + a22 * m11
    # (A·M)·A^T
    n00 = am00 * a11 + am01 * a12
    n01 = am00 * a21 + am01 * a22
    n11 = am10 * a21 + am11 * a22

    # 对称矩阵特征值：λ = (trace ± sqrt(trace² - 4det)) / 2
    trace = n00 + n11
    det = n00 * n11 - n01 * n01
    disc = max(0.0, trace * trace - 4.0 * det)
    root = math.sqrt(disc)
    lam1 = max(0.0, (trace + root) / 2.0)     # 大特征值 → 长半轴
    lam2 = max(0.0, (trace - root) / 2.0)     # 小特征值 → 短半轴
    nrx = math.sqrt(lam1)
    nry = math.sqrt(lam2)

    # 主轴方向：tan(2θ) = 2b / (a - d)
    if abs(n01) < _EPS and abs(n00 - n11) < _EPS:
        nangle = 0.0
    else:
        nangle = 0.5 * math.degrees(math.atan2(2.0 * n01, n00 - n11))
    nangle = normalize_angle(nangle)
    return ncx, ncy, nrx, nry, nangle
