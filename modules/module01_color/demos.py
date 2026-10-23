# -*- coding: utf-8 -*-
"""
=====================================================================
 modules/module01_color/demos.py — 模块一（颜色模型）演示页
=====================================================================
模块一是颜色模型教学：RGB 立方体 / HSV 六棱锥 / RGB⇄HSV 转换推导。
颜色模型不需要像素画板——本模块的演示页是"交互可视化页"（kind =
"widget"）：整个画布区被替换为一个自包含控件，参数直接在画面内
调节；右侧公式卡照常显示，播放控制禁用（没有步骤流概念）。

三个页面：
  RgbCubePage    RGB 颜色立方体（斜二测投影 + 8 顶点标注 + 当前色定位）
  HsvConePage    HSV 六棱锥（3D 可旋转：顶面六边形 + 锥尖黑 + 当前色定位）
  ConvertPage    RGB⇄HSV 转换过程推导（逐步代入实数 + 反向验证）
=====================================================================
"""

from typing import Callable, Dict, List
import math

from PySide6.QtCore import Qt, QPointF, QRectF, QSizeF
from PySide6.QtGui import (QColor, QPainter, QPen, QBrush, QPolygonF,
                           QImage, QFont, QLinearGradient)
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QSlider,
                               QVBoxLayout, QHBoxLayout, QGridLayout)

from ui import theme
from modules.module01_color.view3d import RotatingCanvas


# =====================================================================
# 颜色数学（教学用实现，与 ui/color_dialog 的换算保持同一口径）
# =====================================================================
def rgb_to_hsv(r: int, g: int, b: int):
    """RGB(0-255) → (H 0-360°, S 0-100, V 0-100)。教科书六棱锥定义。"""
    rp, gp, bp = r / 255, g / 255, b / 255
    mx, mn = max(rp, gp, bp), min(rp, gp, bp)
    d = mx - mn
    # V = 三个分量的最大值；S = Δ / Max（Max=0 时无色，S=0）
    v = mx
    s = 0.0 if mx == 0 else d / mx
    if d == 0:
        h = 0.0                          # 灰色轴上色相无定义，约定 0°
    elif mx == rp:
        h = 60 * (((gp - bp) / d) % 6)   # Max=R：基准区，落在 0±60°
    elif mx == gp:
        h = 60 * ((bp - rp) / d + 2)     # Max=G：+120° 区
    else:
        h = 60 * ((rp - gp) / d + 4)     # Max=B：+240° 区
    return h, s * 100, v * 100


def hsv_to_rgb(h: float, s: float, v: float):
    """(H°, S 0-100, V 0-100) → RGB(0-255)。上述公式的逆运算。"""
    s /= 100
    v /= 100
    c = v * s                            # 纯色分量（chroma）
    x = c * (1 - abs((h / 60) % 2 - 1))  # 中间分量
    m = v - c
    i = int(h // 60) % 6
    rp, gp, bp = [(c, x, 0), (x, c, 0), (0, c, x),
                  (0, x, c), (x, 0, c), (c, 0, x)][i]
    return (round((rp + m) * 255), round((gp + m) * 255),
            round((bp + m) * 255))


def _hex(r, g, b) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


# =====================================================================
# 演示页描述结构（演示壳按 kind="widget" 分支装载）
# =====================================================================
class ColorPage:
    """一个无画板演示页的自描述：工厂函数创建整页交互控件。

    用普通类而非 dataclass：演示壳拿页面对象当字典键（目录按钮
    反查），需要默认的按身份哈希。
    """

    def __init__(self, title: str, icon: str, variables: Dict[str, str],
                 formula: str, factory: Callable[[], QWidget]):
        self.title = title
        self.icon = icon
        self.variables = variables            # 右侧"决策项监视"说明行
        self.formula = formula                # 右侧公式卡全文
        self.factory = factory                # 创建页面控件
        self.kind = "widget"                  # 演示壳分支标记（区别于画布页）


# =====================================================================
# 公共小件：标签 + 彩色滑杆一行
# =====================================================================
class _SliderRow(QWidget):
    """一行参数滑杆：名称（带通道色）+ 滑杆 + 数值。"""

    def __init__(self, name: str, color: str, lo: int, hi: int, val: int,
                 suffix: str = "", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lab = QLabel(name)
        lab.setFixedWidth(56)
        lab.setStyleSheet(f"color:{color}; font-weight:600;")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(lo, hi)
        self.slider.setValue(val)
        self.slider.setStyleSheet(
            f"QSlider::groove:horizontal {{ height:6px; border-radius:3px;"
            f"  background:{theme.BORDER}; }}"
            f"QSlider::sub-page:horizontal {{ background:{color};"
            f"  border-radius:3px; }}"
            f"QSlider::handle:horizontal {{ width:14px; margin:-5px 0;"
            f"  border-radius:8px; background:white;"
            f"  border:1px solid {theme.BORDER}; }}")
        self.val_lab = QLabel(f"{val}{suffix}")
        self.val_lab.setObjectName("mono")
        self.val_lab.setFixedWidth(52)
        self.val_lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(lab)
        lay.addWidget(self.slider, stretch=1)
        lay.addWidget(self.val_lab)
        self.slider.valueChanged.connect(
            lambda v: self.val_lab.setText(f"{v}{suffix}"))

    def value(self) -> int:
        return self.slider.value()


class _Swatch(QWidget):
    """当前颜色大色块 + 下方 HEX 文本。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor("#4F6EF7")
        self.setFixedHeight(64)

    def set_color(self, c: QColor):
        self._color = QColor(c)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect().adjusted(0, 0, -1, -1)
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.setBrush(QBrush(self._color))
        p.drawRoundedRect(QRectF(r).adjusted(4, 2, -4, -12), 8, 8)


def rgb_to_cmy(r: int, g: int, b: int):
    """RGB(0-255) → CMY 互补量（各 0-100）。

    C=100×(1−R')、M=100×(1−G')、Y=100×(1−B')，
    与 RGB 严格一一互补；不引入黑版 K，避免两套黑量口径冲突。
    """
    return ((1 - r / 255) * 100, (1 - g / 255) * 100,
            (1 - b / 255) * 100)


class _PlaneView(QWidget):
    """三视图小窗：单位平面的双色渐变 + 四角标注 + 当前色投影点。

    u 轴向右、v 轴向上，各 ∈[0,1]。渐变按四角颜色双线性插值
    （96×96 位图只建一次，角点颜色固定）；当前点单独绘制。
    支持 点击/拖动 直接调节（on_pick(u, v) 回调）。
    """

    # 四周留白：左 34（纵轴标注）上 24（上角标注）右 14 下 44（标题+横轴）
    M_L, M_T, M_R, M_B = 34, 24, 14, 44

    def __init__(self, title: str, corners, ax_x: str, ax_y: str,
                 parent=None, on_pick=None):
        super().__init__(parent)
        self._title = title
        self._corners = corners          # [(u, v, 短标注, QColor)]
        self._ax_x, self._ax_y = ax_x, ax_y
        self._on_pick = on_pick          # 可交互：回调 on_pick(u, v)
        self._pt = (0.5, 0.5)            # 当前色投影 (u, v)
        self._pt_color = QColor("#4F6EF7")
        self._img = None
        self._pressed = False
        self.setMinimumSize(160, 190)
        if on_pick is not None:
            self.setCursor(Qt.PointingHandCursor)

    def set_point(self, u: float, v: float, color):
        """当前色投影点：color 接受 QColor 或 (r,g,b) 元组。"""
        self._pt = (max(0.0, min(1.0, u)), max(0.0, min(1.0, v)))
        self._pt_color = QColor(*color) if isinstance(color, tuple) \
            else QColor(color)
        self.update()

    def _geometry(self) -> QRectF:
        """渐变正方形区域（按四周留白计算，保证标注不被裁剪）。"""
        s = min(self.width() - self.M_L - self.M_R,
                self.height() - self.M_T - self.M_B)
        return QRectF(self.M_L + (self.width() - self.M_L - self.M_R - s) / 2,
                      self.M_T + (self.height() - self.M_T - self.M_B - s) / 2,
                      s, s)

    def _uv_at(self, pos):
        """控件坐标 → (u, v)，钳制到 [0,1]。"""
        r = self._geometry()
        u = (pos.x() - r.x()) / max(1.0, r.width())
        v = 1 - (pos.y() - r.y()) / max(1.0, r.height())
        return (max(0.0, min(1.0, u)), max(0.0, min(1.0, v)))

    def _handle_pick(self, u, v):
        """统一入口：更新投影点并回调（鼠标与测试共用）。"""
        self._pt = (u, v)
        self.update()
        if self._on_pick is not None:
            self._on_pick(u, v)

    def mousePressEvent(self, e):
        if self._on_pick is None:
            return
        self._pressed = True
        u, v = self._uv_at(e.position())
        self._handle_pick(u, v)

    def mouseMoveEvent(self, e):
        if self._on_pick is None or not self._pressed:
            return
        u, v = self._uv_at(e.position())
        self._handle_pick(u, v)

    def mouseReleaseEvent(self, _e):
        self._pressed = False

    def _bilinear(self) -> QImage:
        """四角颜色双线性插值位图（角点固定 → 只建一次）。"""
        if self._img is not None:
            return self._img
        n = 144                             # 分辨率够高，缩放后无明显块感
        img = QImage(n, n, QImage.Format_RGB32)
        cs = [(u, v, QColor(c)) for u, v, _l, c in self._corners]
        for y in range(n):
            v = 1 - y / (n - 1)              # 图像行向下 = v 减小
            for x in range(n):
                u = x / (n - 1)
                r = g = b = 0.0
                for cu, cv, col in cs:
                    w = (u if cu > 0.5 else 1 - u) * \
                        (v if cv > 0.5 else 1 - v)
                    r += col.red() * w
                    g += col.green() * w
                    b += col.blue() * w
                img.setPixel(x, y, QColor(int(r), int(g), int(b)).rgb())
        self._img = img
        return img

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self._geometry()
        # 平面渐变（映射拉伸绘制 96px 位图）
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.drawImage(rect, self._bilinear())
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(rect)
        # 四角：本色圆点 + 短标注（放进留白区，不再被裁剪）
        p.setFont(QFont(theme.UI_FONT, 8))
        for u, v, lab, col in self._corners:
            pos = QPointF(rect.x() + u * rect.width(),
                          rect.y() + (1 - v) * rect.height())
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(col))
            p.drawEllipse(pos, 3.5, 3.5)
            p.setPen(QPen(QColor(theme.TEXT_2), 1))
            if u < 0.5:                       # 左侧角：标注放圆点左边
                anchor = QPointF(pos.x() - 30, pos.y() - 7)
                flag = Qt.AlignRight
            else:                             # 右侧角：放圆点右边
                anchor = QPointF(pos.x() + 8, pos.y() - 7)
                flag = Qt.AlignLeft
            if v > 0.5:
                anchor.setY(pos.y() - 16)
            else:
                anchor.setY(pos.y() + 7)
            p.drawText(QRectF(anchor.x(), anchor.y(), 42, 14), flag, lab)
        # 当前色投影点
        u, v = self._pt
        pos = QPointF(rect.x() + u * rect.width(),
                      rect.y() + (1 - v) * rect.height())
        p.setPen(QPen(QColor(theme.TEXT_1), 1))
        p.setBrush(QBrush(self._pt_color))
        p.drawEllipse(pos, 5, 5)
        p.setPen(QPen(QColor(255, 255, 255), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(pos, 5, 5)
        # 标题 + 轴标注（固定在各自留白带内）
        p.setPen(QPen(QColor(theme.TEXT_1), 1))
        p.drawText(QRectF(0, self.height() - 22, self.width(), 18),
                   Qt.AlignCenter, self._title)
        p.setPen(QPen(QColor(theme.TEXT_2), 1))
        p.drawText(QRectF(rect.x(), rect.y() + rect.height() + 3,
                          rect.width(), 14), Qt.AlignRight, f"{self._ax_x} →")
        p.drawText(QRectF(2, rect.y() - 14, self.M_L - 6, 14),
                   Qt.AlignRight, f"{self._ax_y} ↑")


class _TopViewHex(QWidget):
    """六棱锥俯视图：顶面六边形（六纯色扇区）+ 当前色方位点。

    当前点在俯视图中的极径 = S×V（锥体水平投影半径），角 = H。
    点击/拖动 → 回调 on_pick(H, S)（V 不变）。
    """

    HUE_VERTICES = [("红", 0), ("黄", 60), ("绿", 120),
                    ("青", 180), ("蓝", 240), ("品红", 300)]

    def __init__(self, parent=None, on_pick=None):
        super().__init__(parent)
        self._hsv = (230.0, 68.0, 97.0)
        self._on_pick = on_pick
        self._pressed = False
        self.setMinimumSize(160, 190)
        if on_pick is not None:
            self.setCursor(Qt.PointingHandCursor)

    def set_hsv(self, hsv):
        self._hsv = hsv
        self.update()

    def _center_radius(self):
        c = QPointF(self.width() / 2, (self.height() - 24) / 2 + 6)
        R = min(self.width() / 2 - 34, (self.height() - 24) / 2 - 14)
        return c, max(40.0, R)

    def _handle_pick(self, pos):
        """点击/拖动 → 极角 = H，极径 = S（0~100），回调保持 V。"""
        c, R = self._center_radius()
        dx, dy = pos.x() - c.x(), c.y() - pos.y()
        h = math.degrees(math.atan2(dy, dx)) % 360
        s = max(0.0, min(100.0, math.hypot(dx, dy) / R * 100))
        h_deg, _s, v_n = self._hsv
        self._hsv = (h, s, v_n)              # 即时反馈，主页面会回填
        self.update()
        if self._on_pick is not None:
            self._on_pick(h, s)

    def mousePressEvent(self, e):
        if self._on_pick is None:
            return
        self._pressed = True
        self._handle_pick(e.position())

    def mouseMoveEvent(self, e):
        if self._on_pick is None or not self._pressed:
            return
        self._handle_pick(e.position())

    def mouseReleaseEvent(self, _e):
        self._pressed = False

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        h_deg, s_n, v_n = self._hsv
        c, R = self._center_radius()
        # 六边形色轮：6 个顶点间渐变三角拼合（真六边形直边，
        # 与 3D 六棱锥顶面形状一致；圆形扇区画风不符，已弃用）
        verts = []
        for _name, deg in self.HUE_VERTICES:
            t = math.radians(deg)
            verts.append(QPointF(c.x() + R * math.cos(t),
                                 c.y() - R * math.sin(t)))
        p.setPen(Qt.NoPen)
        for i in range(6):
            j = (i + 1) % 6
            deg_i = self.HUE_VERTICES[i][1]
            deg_j = self.HUE_VERTICES[j][1]
            g = QLinearGradient(verts[i], verts[j])
            g.setColorAt(0, QColor(*hsv_to_rgb(deg_i, 100, 100)))
            g.setColorAt(1, QColor(*hsv_to_rgb(deg_j, 100, 100)))
            p.setBrush(QBrush(g))
            p.drawPolygon(QPolygonF([c, verts[i], verts[j]]))
        p.setPen(QPen(QColor(theme.TEXT_2), 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(QPolygonF(verts))
        # 六顶点本色圆点 + 名称（画在扇区外侧留白带）
        p.setFont(QFont(theme.UI_FONT, 8))
        for i, (name, deg) in enumerate(self.HUE_VERTICES):
            t = math.radians(deg)
            pos = verts[i]
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(*hsv_to_rgb(deg, 100, 100))))
            p.drawEllipse(pos, 3.5, 3.5)
            p.setPen(QPen(QColor(theme.TEXT_2), 1))
            lx = 6 if math.cos(t) >= -0.01 else -36
            ly = -14 if math.sin(t) > 0.35 else (6 if math.sin(t) < -0.35 else -7)
            p.drawText(QRectF(pos.x() + lx, pos.y() + ly, 30, 14),
                       Qt.AlignLeft, name)
        # 中心白点（锥轴顶）
        p.setBrush(QBrush(QColor(255, 255, 255)))
        p.drawEllipse(c, 3, 3)
        # 当前色点：极角 H，极径 S×V
        rad = math.radians(h_deg)
        rr = R * max(0.02, s_n / 100 * v_n / 100)
        pos = QPointF(c.x() + rr * math.cos(rad), c.y() - rr * math.sin(rad))
        rgb = hsv_to_rgb(h_deg, s_n, v_n)
        p.setPen(QPen(QColor(theme.TEXT_1), 1))
        p.setBrush(QBrush(QColor(*rgb)))
        p.drawEllipse(pos, 5, 5)
        p.setPen(QPen(QColor(255, 255, 255), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(pos, 5, 5)
        p.setPen(QPen(QColor(theme.TEXT_1), 1))
        p.drawText(QRectF(0, self.height() - 20, self.width(), 18),
                   Qt.AlignCenter, "俯视图（六边形色轮）")


class _SVSection(QWidget):
    """六棱锥轴截面（过轴的 S-V 三角形）：上边纯色、左顶白、下顶黑，
    当前色点按 (S,V) 定位。点击/拖动 → on_pick(S, V)。"""

    # 留白：左 22 上 24 右 34 下 40（角标注 + 标题各占一条带）
    M_L, M_T, M_R, M_B = 22, 24, 34, 40

    def __init__(self, parent=None, on_pick=None):
        super().__init__(parent)
        self._hsv = (230.0, 68.0, 97.0)
        self._img = None                 # (H, size, 位图) 缓存
        self._on_pick = on_pick
        self._pressed = False
        self.setMinimumSize(160, 190)
        if on_pick is not None:
            self.setCursor(Qt.PointingHandCursor)

    def set_hsv(self, hsv):
        self._hsv = hsv
        self.update()

    def _geometry(self) -> QRectF:
        s = min(self.width() - self.M_L - self.M_R,
                self.height() - self.M_T - self.M_B)
        return QRectF(self.M_L + (self.width() - self.M_L - self.M_R - s) / 2,
                      self.M_T + (self.height() - self.M_T - self.M_B - s) / 2,
                      s, s)

    def _triangle(self, rect: QRectF) -> QPolygonF:
        """S-V 截面三角形轮廓（屏幕坐标）。"""
        return QPolygonF([rect.topLeft(),
                          QPointF(rect.x() + rect.width(), rect.y()),
                          QPointF(rect.x() + rect.width() / 2,
                                  rect.y() + rect.height())])

    def _sv_at(self, pos):
        """控件坐标 → 重心坐标 (S, V)，仅三角形内有效。"""
        r = self._geometry()
        n = r.width()
        Wp = QPointF(r.x(), r.y())
        Pp = QPointF(r.x() + n, r.y())
        Kp = QPointF(r.x() + n / 2, r.y() + n)
        px, py = pos.x() - Wp.x(), pos.y() - Wp.y()
        ax, ay = Pp.x() - Wp.x(), Pp.y() - Wp.y()
        bx, by = Kp.x() - Wp.x(), Kp.y() - Wp.y()
        det = ax * by - ay * bx
        if det == 0:
            return None
        s = (px * by - py * bx) / det
        t = (ax * py - ay * px) / det
        if s < 0 or t < 0 or s + t > 1:
            return None
        return (s * 100, (1 - t) * 100)

    def _handle_pick(self, pos):
        sv = self._sv_at(pos)
        if sv is None:
            return                       # 三角形外不响应（防误拖跳变）
        h_deg = self._hsv[0]
        self._hsv = (h_deg, sv[0], sv[1])
        self.update()
        if self._on_pick is not None:
            self._on_pick(sv[0], sv[1])

    def mousePressEvent(self, e):
        if self._on_pick is None:
            return
        self._pressed = True
        self._handle_pick(e.position())

    def mouseMoveEvent(self, e):
        if self._on_pick is None or not self._pressed:
            return
        self._handle_pick(e.position())

    def mouseReleaseEvent(self, _e):
        self._pressed = False

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        h_deg, s_n, v_n = self._hsv
        rect = self._geometry()
        w, h_ = rect.width(), rect.height()
        tri = self._triangle(rect)
        # ---- 截面着色 = 两层矢量渐变精确解（反走样知识点，ppt08）：
        # HSV 在固定 H 下线性于 v → color(s,v) = v·[(1−s)·白 + s·纯色]。
        # ① 先铺 s 渐变：白 →（沿 s 增大方向）→ 纯色；
        #    s = x − 0.5y（单位三角形），渐变轴端点取 s=0 与 s=1 两点。
        # ② 再叠垂直黑幕：alpha = 1−v（t = y，随 y 线性）→ 乘出 V 维。
        # 矢量填充天然抗锯齿，拖动零重算开销。
        gs = QLinearGradient(QPointF(rect.x(), rect.y()),
                             QPointF(rect.x() + 0.8 * w, rect.y() - 0.4 * h_))
        gs.setColorAt(0, QColor(255, 255, 255))
        gs.setColorAt(1, QColor(*hsv_to_rgb(h_deg, 100, 100)))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(gs))
        p.drawPolygon(tri)
        gb = QLinearGradient(rect.x(), rect.y(), rect.x(), rect.y() + h_)
        gb.setColorAt(0, QColor(0, 0, 0, 0))
        gb.setColorAt(1, QColor(0, 0, 0, 255))
        p.setBrush(QBrush(gb))
        p.drawPolygon(tri)
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(tri)
        p.drawRect(rect)
        # 角标注（放进留白带：白=左上外、纯色=右上外、黑=下顶点外）
        p.setFont(QFont(theme.UI_FONT, 8))
        p.setPen(QPen(QColor(theme.TEXT_2), 1))
        Wp = QPointF(rect.x(), rect.y())
        Pp = QPointF(rect.x() + w, rect.y())
        Kp = QPointF(rect.x() + w / 2, rect.y() + h_)
        p.drawText(QRectF(0, Wp.y() - 16, self.M_L + 30, 14),
                   Qt.AlignRight, "白")
        p.drawText(QRectF(Pp.x() - 6, Pp.y() - 16, self.M_R + 20, 14),
                   Qt.AlignLeft, "纯色")
        p.drawText(QRectF(Kp.x() - 40, Kp.y() + 4, 80, 14),
                   Qt.AlignHCenter, "黑")
        # 当前色点：p = W + s·(P−W) + (1−v)·(K−W)
        pos = (Wp + (Pp - Wp) * (s_n / 100) +
               (Kp - Wp) * (1 - v_n / 100))
        rgb = hsv_to_rgb(h_deg, s_n, v_n)
        p.setPen(QPen(QColor(theme.TEXT_1), 1))
        p.setBrush(QBrush(QColor(*rgb)))
        p.drawEllipse(pos, 5, 5)
        p.setPen(QPen(QColor(255, 255, 255), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(pos, 5, 5)
        p.setPen(QPen(QColor(theme.TEXT_1), 1))
        p.drawText(QRectF(0, self.height() - 22, self.width(), 18),
                   Qt.AlignCenter, "轴截面（S-V 三角形）")


class _HueRing(QWidget):
    """色轮：360° 平滑色环（120 个 3° 扇区）+ 当前 H 指针 + 中心当前色
    圆盘。点击/拖动环带 → on_pick(H)。对应归档转换工具的色轮观感。"""

    def __init__(self, parent=None, on_pick=None):
        super().__init__(parent)
        self._hsv = (230.0, 68.0, 97.0)
        self._on_pick = on_pick
        self._pressed = False
        self.setMinimumSize(160, 190)
        if on_pick is not None:
            self.setCursor(Qt.PointingHandCursor)

    def set_hsv(self, hsv):
        self._hsv = hsv
        self.update()

    def _center_radius(self):
        c = QPointF(self.width() / 2, (self.height() - 22) / 2 + 4)
        R = min(self.width() / 2 - 12, (self.height() - 22) / 2 - 10)
        return c, max(40.0, R)

    def _handle_pick(self, pos):
        c, R = self._center_radius()
        dx, dy = pos.x() - c.x(), c.y() - pos.y()
        rr = math.hypot(dx, dy)
        if not (R * 0.40 <= rr <= R * 1.08):
            return                       # 只响应环带，中心盘不响应
        h = math.degrees(math.atan2(dy, dx)) % 360
        h0, s, v = self._hsv
        self._hsv = (h, s, v)
        self.update()
        if self._on_pick is not None:
            self._on_pick(h)

    def mousePressEvent(self, e):
        if self._on_pick is None:
            return
        self._pressed = True
        self._handle_pick(e.position())

    def mouseMoveEvent(self, e):
        if self._on_pick is None or not self._pressed:
            return
        self._handle_pick(e.position())

    def mouseReleaseEvent(self, _e):
        self._pressed = False

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        h_deg, s_n, v_n = self._hsv
        c, R = self._center_radius()
        # 平滑色环：120 个 3° 扇区
        p.setPen(Qt.NoPen)
        for i in range(120):
            a0 = i * 3
            p.setBrush(QBrush(QColor(*hsv_to_rgb(a0 + 1.5, 100, 100))))
            p.drawPie(QRectF(c.x() - R, c.y() - R, R * 2, R * 2),
                      int(a0 * 16), int(3.25 * 16))
        # 中心挖出圆环，圆盘放当前颜色
        p.setBrush(QBrush(QColor(theme.CARD)))
        p.drawEllipse(c, R * 0.58, R * 0.58)
        rgb = hsv_to_rgb(h_deg, s_n, v_n)
        p.setBrush(QBrush(QColor(*rgb)))
        p.drawEllipse(c, R * 0.52, R * 0.52)
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, R * 0.52, R * 0.52)
        # H 指针：环心 → 纯色位置
        rad = math.radians(h_deg)
        tip = QPointF(c.x() + R * math.cos(rad), c.y() - R * math.sin(rad))
        p.setPen(QPen(QColor(255, 255, 255), 2))
        p.drawLine(c, tip)
        p.setPen(QPen(QColor(theme.TEXT_1), 1))
        p.drawEllipse(tip, 4, 4)
        p.setPen(QPen(QColor(theme.TEXT_1), 1))
        p.drawText(QRectF(0, self.height() - 22, self.width(), 18),
                   Qt.AlignCenter,
                   f"色轮 H = {h_deg:.0f}°（点击/拖动环带）")


# =====================================================================
# 页面 1：RGB 颜色立方体
# =====================================================================
class RgbCubePage(QWidget):
    """RGB 立方体交互页：斜二测投影 + 8 顶点标注 + 当前色在立方体内定位。

    布局：左侧立方体画布（自绘），右侧 R/G/B 滑杆 + 色块 + HEX。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rgb = (79, 110, 247)
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        # ---- 左：3D 立方体 + 三视图（正视/俯视/侧视平面投影） ----
        left = QVBoxLayout()
        left.setSpacing(6)
        self.cube = _CubeCanvas(self)
        left.addWidget(self.cube, stretch=1)
        # 三视图：正视图=沿 B 轴看 R-G 面；俯视图=沿 G 轴看 R-B 面；
        # 侧视图=沿 R 轴看 G-B 面——与 3D 视角一一对应。
        # 点击/拖动平面图 = 直接调那两个分量（第三分量不变）
        self._views = []
        row = QHBoxLayout()
        row.setSpacing(6)
        for title, corners, ax_x, ax_y, pick in (
                ("正视图（R-G 面）· 可拖动",
                 [(0, 0, "黑", "#000000"), (1, 0, "红", "#FF0000"),
                  (1, 1, "黄", "#FFFF00"), (0, 1, "绿", "#00FF00")],
                 "R", "G", lambda u, v: self._set_two(0, u, 1, v)),
                ("俯视图（R-B 面）· 可拖动",
                 [(0, 0, "黑", "#000000"), (1, 0, "红", "#FF0000"),
                  (1, 1, "品红", "#FF00FF"), (0, 1, "蓝", "#0000FF")],
                 "R", "B", lambda u, v: self._set_two(0, u, 2, v)),
                ("侧视图（G-B 面）· 可拖动",
                 [(0, 0, "黑", "#000000"), (1, 0, "蓝", "#0000FF"),
                  (1, 1, "青", "#00FFFF"), (0, 1, "绿", "#00FF00")],
                 "B", "G", lambda u, v: self._set_two(2, u, 1, v))):
            v = _PlaneView(title, corners, ax_x, ax_y, on_pick=pick)
            self._views.append(v)
            row.addWidget(v, stretch=1)
        left.addLayout(row)
        root.addLayout(left, stretch=1)

        side = QVBoxLayout()
        side.setSpacing(6)
        title = QLabel("RGB 颜色立方体")
        title.setObjectName("cardTitle")
        side.addWidget(title)

        # ---- 加色组：R/G/B（0–255） ----
        lab = QLabel("加色 RGB（光的三原色，0–255）")
        lab.setObjectName("moduleHint")
        side.addWidget(lab)
        self._rows = []
        for name, col, val in (("R 红", "#E5484D", self._rgb[0]),
                               ("G 绿", "#30A46C", self._rgb[1]),
                               ("B 蓝", "#3B6FF6", self._rgb[2])):
            row2 = _SliderRow(name, col, 0, 255, val)
            row2.slider.valueChanged.connect(self._on_change)
            self._rows.append(row2)
            side.addWidget(row2)

        # ---- 减色组：C/M/Y（0–100），与 RGB 严格互补 ----
        lab = QLabel("减色 CMY（C/M/Y = RGB 互补量，0–100）")
        lab.setObjectName("moduleHint")
        side.addWidget(lab)
        self._cmy_rows = []
        for i, (name, col) in enumerate((("C 青", "#00AEEF"),
                                         ("M 品红", "#EC008C"),
                                         ("Y 黄", "#F5C400"))):
            row3 = _SliderRow(name, col, 0, 100, 0)
            row3.slider.valueChanged.connect(
                lambda _v, idx=i: self._on_cmy_slider(idx))
            self._cmy_rows.append(row3)
            side.addWidget(row3)
        self._guard = False                  # 双向同步防回环标志

        tip = QLabel("C/M/Y = RGB 的互补量（C=100−R，M=100−G，\n"
                     "Y=100−B）。拖任意一侧滑杆，另一侧\n"
                     "三个分量同步换算。")
        tip.setObjectName("secondary")
        tip.setWordWrap(True)
        side.addWidget(tip)

        # ---- 底部：当前颜色大展示（加色/减色两种读数） ----
        side.addStretch()
        self.swatch = _Swatch()
        self.swatch.setFixedHeight(76)
        side.addWidget(self.swatch)
        self.hex_lab = QLabel()
        self.hex_lab.setObjectName("mono")
        self.hex_lab.setAlignment(Qt.AlignCenter)
        side.addWidget(self.hex_lab)
        self.cmy_lab = QLabel()
        self.cmy_lab.setObjectName("mono")
        self.cmy_lab.setAlignment(Qt.AlignCenter)
        self.cmy_lab.setStyleSheet(f"color: {theme.TEXT_2};")
        side.addWidget(self.cmy_lab)
        w = QFrame()
        w.setFixedWidth(292)
        w.setLayout(side)
        root.addWidget(w)

        self._on_change()

    def _on_change(self):
        """RGB 滑杆变化 → 换算 CMY 回写滑杆 + 刷新全部显示。"""
        if self._guard:
            return
        self._guard = True
        self._rgb = tuple(r.value() for r in self._rows)
        # 回写 CMY 滑杆（差值 ≥1 才写，避免换算抖动）
        for row, val in zip(self._cmy_rows, rgb_to_cmy(*self._rgb)):
            if abs(row.slider.value() - val) >= 1:
                row.slider.setValue(int(round(val)))
        self._update_displays()
        self._guard = False

    def _on_cmy_slider(self, which):
        """CMY 滑杆变化 → 反推对应 RGB 分量（C/M/Y 与 RGB 一一互补）。"""
        if self._guard:
            return
        self._guard = True
        rgb = list(self._rgb)
        rgb[which] = round(255 * (1 - self._cmy_rows[which].value() / 100.0))
        self._rgb = tuple(rgb)
        if abs(self._rows[which].slider.value() - rgb[which]) >= 1:
            self._rows[which].slider.setValue(rgb[which])
        self._update_displays()
        self._guard = False

    def _update_displays(self):
        """按 self._rgb 刷新色块/读数/立方体/三视图/CMY 读数行。"""
        self.swatch.set_color(QColor(*self._rgb))
        self.hex_lab.setText(_hex(*self._rgb))
        c, m, y = rgb_to_cmy(*self._rgb)
        self.cmy_lab.setText(f"CMY ({c:.0f}%, {m:.0f}%, {y:.0f}%)")
        self.cube.set_rgb(self._rgb)
        r, g, b = (v / 255 for v in self._rgb)
        self._views[0].set_point(r, g, self._rgb)   # 正视图：R-G
        self._views[1].set_point(r, b, self._rgb)   # 俯视图：R-B
        self._views[2].set_point(b, g, self._rgb)   # 侧视图：G-B

    def _set_two(self, i1: int, v1: float, i2: int, v2: float):
        """三视图拖动 → 设置对应两个分量（第三分量保持不变）。"""
        self._rows[i1].slider.setValue(int(round(max(0.0, min(1.0, v1)) * 255)))
        self._rows[i2].slider.setValue(int(round(max(0.0, min(1.0, v2)) * 255)))


def _cube_geometry():
    """立方体 8 顶点 + 12 条棱（两顶点仅一维不同）。"""
    C = [(r, g, b) for r in (0, 1) for g in (0, 1) for b in (0, 1)]
    E = [(a, b) for a in C for b in C
         if sum(abs(x - y) for x, y in zip(a, b)) == 1]
    return C, E


class _CubeCanvas(RotatingCanvas):
    """RGB 单位立方体（真 3D，可拖拽旋转，对应课程 PPT 第 13 页）。

    世界坐标 = RGB 坐标系：x=R，y=G（上），z=B。六个面按角点颜色
    半透明渐变填充（画家算法排序），画黑→白主对角线虚线与当前色
    定位点——拖到沿对角线方向看，就是 PPT 第 20 页的六边形外形。
    """

    CORNER_NAMES = {  # 8 顶点：RGB 顶点 + 互补的 CMY 三原色（同 PPT）
        (0, 0, 0): "黑(0,0,0)", (1, 0, 0): "红(1,0,0)",
        (0, 1, 0): "绿(0,1,0)", (0, 0, 1): "蓝(0,0,1)",
        (1, 1, 0): "黄Y(1,1,0)", (1, 0, 1): "品红M(1,0,1)",
        (0, 1, 1): "青C(0,1,1)", (1, 1, 1): "白(1,1,1)",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rgb = (79, 110, 247)
        self.center3d = (0.5, 0.5, 0.5)    # 立方体质心 → 屏幕中心

    def set_rgb(self, rgb):
        self._rgb = rgb
        self.update()

    # ---- 几何表（模块级函数生成：类体内推导式看不到类属性） ----
    CORNERS, EDGES = _cube_geometry()
    FACES = [  # 六个面：4 角点按序围成四边形
        [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)],   # R=1
        [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)],   # R=0
        [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)],   # G=1 顶面
        [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)],   # G=0 底面
        [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],   # B=1
        [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)],   # B=0
    ]

    def render(self, p: QPainter):
        P = {c: self.p3d(c)[0] for c in self.CORNERS}
        D = {c: self.p3d(c)[1] for c in self.CORNERS}
        # 深度归一化（0=最远 1=最近）：棱线/顶点按远近分轻重，
        # 消除线框图的深度含糊（怪异感的主要来源）
        dvals = list(D.values())
        dmin, dmax = min(dvals), max(dvals)

        def t(c):
            return (D[c] - dmin) / (dmax - dmin) if dmax > dmin else 0.5

        # ---- 1. R/G/B 坐标轴箭头（画在面之下，像从模型背后伸出） ----
        for vec, col, name in (((1.45, 0, 0), "#E5484D", "R"),
                               ((0, 1.45, 0), "#30A46C", "G"),
                               ((0, 0, 1.45), "#3B6FF6", "B")):
            self.draw_axis_arrow(p, self.p3d((0, 0, 0))[0],
                                 self.p3d(vec)[0], col, name)
        # ---- 2. 六个面：对角两点颜色渐变半透明填充，远→近 ----
        faces = sorted(self.FACES,
                       key=lambda q: sum(D[v] for v in q) / 4)
        for quad in faces:
            c0 = QColor(*(255 * v for v in quad[0]))
            c2 = QColor(*(255 * v for v in quad[2]))
            c0.setAlpha(88)
            c2.setAlpha(36)
            g = QLinearGradient(P[quad[0]], P[quad[2]])
            g.setColorAt(0, c0)
            g.setColorAt(1, c2)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(g))
            p.drawPolygon(QPolygonF([P[v] for v in quad]))
        # ---- 3. 12 条棱：远细淡 / 近粗浓（深度线索） ----
        p.setBrush(Qt.NoBrush)
        for a, b in self.EDGES:
            k = (t(a) + t(b)) / 2
            p.setPen(QPen(QColor(theme.TEXT_2).lighter(150 if k < 0.5 else 100),
                          1.1 + 0.9 * k))
            p.drawLine(P[a], P[b])
        # ---- 4. 黑→白主对角线（灰度轴，PPT 虚线强调） ----
        p.setPen(QPen(QColor(theme.ACCENT), 1.6, Qt.DashLine))
        p.drawLine(P[(0, 0, 0)], P[(1, 1, 1)])
        # 标注放对角线中点旁（避开"白"顶点标注）
        mid = (P[(0, 0, 0)] + P[(1, 1, 1)]) / 2
        p.setPen(QPen(QColor(theme.ACCENT), 1))
        p.drawText(QRectF(mid.x() + 8, mid.y() - 8, 60, 16),
                   Qt.AlignLeft, "灰度轴")
        # ---- 5. 8 顶点：本色圆点 + 名称（远处淡化缩小） ----
        p.setFont(QFont(theme.UI_FONT, 9))
        center = QPointF(self.width() / 2, self.height() / 2)
        for c in sorted(self.CORNERS, key=lambda c: D[c]):
            pos = P[c]
            k = t(c)
            dot = 3.4 + 1.8 * k
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(*(255 * v for v in c))))
            p.drawEllipse(pos, dot, dot)
            _pc = QColor(theme.TEXT_1)
            _pc.setAlpha(120 + int(110 * k))
            p.setPen(QPen(_pc, 1))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(pos, dot, dot)
            outward = QPointF(pos.x() - center.x(), pos.y() - center.y())
            self.draw_label(p, pos, self.CORNER_NAMES[c], outward,
                            dim=1.0 - 0.55 * (1 - k))
        # ---- 6. 当前色定位点 + 到三个相邻面的投影虚线 ----
        r, g, b = (v / 255 for v in self._rgb)
        cur, _ = self.p3d((r, g, b))
        p.setPen(QPen(QColor(theme.ACCENT), 1.2, Qt.DotLine))
        p.drawLine(cur, self.p3d((r, g, 0))[0])   # 落到 B=0 面
        p.drawLine(cur, self.p3d((r, 0, b))[0])   # 落到 G=0 面
        p.drawLine(cur, self.p3d((0, g, b))[0])   # 落到 R=0 面
        # 三层环提高任意底色下的可辨识度：深描边 → 白描边 → 色芯
        p.setPen(QPen(QColor(theme.TEXT_1), 1))
        p.setBrush(QBrush(QColor(*self._rgb)))
        p.drawEllipse(cur, 8, 8)
        p.setPen(QPen(QColor(255, 255, 255), 2))
        p.drawEllipse(cur, 6, 6)


# =====================================================================
# 页面 2：HSV 色环 + 六棱锥截面
# =====================================================================
class HsvConePage(QWidget):
    """HSV 交互页：左侧 = 六棱锥 3D 视图（可拖拽旋转）+ 俯视图 /
    轴截面两张平面图，右侧 H/S/V 滑杆。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hsv = (230.0, 68.0, 97.0)
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        # ---- 左：3D 六棱锥 + 两张平面对应图（均可拖动调参） ----
        left = QVBoxLayout()
        left.setSpacing(6)
        self.field = _HexconeCanvas(self)
        left.addWidget(self.field, stretch=1)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.top_view = _TopViewHex(on_pick=self._set_hs)   # 拖动 → H,S
        self.sv_view = _SVSection(on_pick=self._set_sv)     # 拖动 → S,V
        for v in (self.top_view, self.sv_view):
            v.setFixedSize(330, 225)
        row.addStretch(1)
        row.addWidget(self.top_view)
        row.addWidget(self.sv_view)
        row.addStretch(1)
        left.addLayout(row)
        root.addLayout(left, stretch=1)

        side = QVBoxLayout()
        side.setSpacing(10)
        title = QLabel("HSV 颜色空间")
        title.setObjectName("cardTitle")
        side.addWidget(title)
        self._rows = []
        for name, col, lo, hi, val, suf in (
                ("H 色相", "#E5484D", 0, 360, int(self._hsv[0]), "°"),
                ("S 饱和", theme.ACCENT, 0, 100, int(self._hsv[1]), ""),
                ("V 明度", "#F5A623", 0, 100, int(self._hsv[2]), "")):
            row2 = _SliderRow(name, col, lo, hi, val, suf)
            row2.slider.valueChanged.connect(self._on_change)
            self._rows.append(row2)
            side.addWidget(row2)
        self.swatch = _Swatch()
        side.addWidget(self.swatch)
        self.hex_lab = QLabel()
        self.hex_lab.setObjectName("mono")
        self.hex_lab.setAlignment(Qt.AlignCenter)
        side.addWidget(self.hex_lab)
        tip = QLabel("六棱锥即 HSV 空间（PPT 第 16/20 页）：\n"
                     "顶面六边形 = V=1，六个顶点按 H 依次为\n"
                     "红→黄→绿→青→蓝→品红，中心白(1,0)；\n"
                     "锥尖 = 黑(0,0)，V 轴过锥心垂直向上。\n"
                     "下方俯视图/截面图均可点击拖动调参。")
        tip.setObjectName("secondary")
        tip.setWordWrap(True)
        side.addWidget(tip)
        side.addStretch()
        w = QFrame()
        w.setFixedWidth(280)
        w.setLayout(side)
        root.addWidget(w)
        self._on_change()

    def _on_change(self):
        self._hsv = tuple(float(r.value()) for r in self._rows)
        rgb = hsv_to_rgb(*self._hsv)
        self.swatch.set_color(QColor(*rgb))
        self.hex_lab.setText(_hex(*rgb))
        self.field.set_hsv(self._hsv)
        self.top_view.set_hsv(self._hsv)
        self.sv_view.set_hsv(self._hsv)

    def _set_hs(self, h: float, s: float):
        """俯视图拖动 → 设 H、S（V 不变）。"""
        self._rows[0].slider.setValue(int(round(h)) % 360)
        self._rows[1].slider.setValue(int(round(s)))

    def _set_sv(self, s: float, v: float):
        """轴截面拖动 → 设 S、V（H 不变）。"""
        self._rows[1].slider.setValue(int(round(s)))
        self._rows[2].slider.setValue(int(round(v)))


class _HexconeCanvas(RotatingCanvas):
    """HSV 六棱锥（真 3D，可拖拽旋转，对应课程 PPT 第 16/20 页）。

    几何（与 PPT 一致）：锥尖 = 黑(0,0) 在下；顶面 = V=1 的正六边形，
    六个顶点按 H 依次为 红0°/黄60°/绿120°/青180°/蓝240°/品红300°，
    六边形中心 = 白(1,0)；V 轴过锥心垂直向上。
    侧面上任一点 = 纯色加黑（向锥尖），水平截面 = 随 V 缩小的六边形，
    当前颜色点按 (H,S,V) 定位在锥内。
    """

    HUE_VERTICES = [("红", 0), ("黄", 60), ("绿", 120),
                    ("青", 180), ("蓝", 240), ("品红", 300)]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hsv = (230.0, 68.0, 97.0)
        self.center3d = (0.0, 0.55, 0.0)   # 锥体质心（锥尖 0 → 顶面 1）居中

    def set_hsv(self, hsv):
        self._hsv = hsv
        self.update()

    @staticmethod
    def _hue_vec(deg: float, radius: float = 1.0, v: float = 1.0):
        """色相角 → 锥体世界坐标（顶面半径 1，V 轴 = y）。"""
        t = math.radians(deg)
        return (radius * math.cos(t), v, radius * math.sin(t))

    def render(self, p: QPainter):
        apex = (0, 0, 0)                      # 黑
        white = (0, 1, 0)                     # 白（顶面中心）
        top = [(name, deg, self._hue_vec(deg)) for name, deg in
               self.HUE_VERTICES]
        P = {i: self.p3d(v)[0] for i, (_, _, v) in enumerate(top)}
        Pw, Pa = self.p3d(white)[0], self.p3d(apex)[0]
        Dtop = [self.p3d(v)[1] for _, _, v in top]
        dapex = self.p3d(apex)[1]
        # 深度归一化（0=最远 1=最近）：棱线/顶点按远近分轻重
        dmin, dmax = min(Dtop + [dapex]), max(Dtop + [dapex])

        def t(i):
            return ((Dtop[i] - dmin) / (dmax - dmin)) if dmax > dmin else 0.5

        # ---- 1. V / S 轴箭头（画在锥体之下，避免穿模感） ----
        self.draw_axis_arrow(p, Pa, self.p3d((0, 1.5, 0))[0],
                             theme.TEXT_2, "V")
        self.draw_axis_arrow(p, Pa, self.p3d((1.15, 0, 0))[0],
                             theme.TEXT_2, "S")
        # ---- 2. 六个侧面：相邻两顶点纯色渐变（远→近） ----
        sides = []
        for i in range(6):
            j = (i + 1) % 6
            depth = (Dtop[i] + Dtop[j] + dapex) / 3
            sides.append((depth, i, j))
        sides.sort(key=lambda x: x[0])
        for _d, i, j in sides:
            _ni, deg_i, _ = top[i]
            _nj, deg_j, _ = top[j]
            ci = QColor(*hsv_to_rgb(deg_i, 100, 100))
            cj = QColor(*hsv_to_rgb(deg_j, 100, 100))
            ci.setAlpha(110)
            cj.setAlpha(110)
            pa = P[i]
            pb = P[j]
            g = QLinearGradient((pa + pb) / 2, Pa)
            g.setColorAt(0, ci)
            g.setColorAt(1, QColor(20, 20, 20, 130))   # 锥尖趋黑（加黑=色调）
            p.setPen(QPen(QColor(theme.TEXT_2), 1.2))
            p.setBrush(QBrush(g))
            p.drawPolygon(QPolygonF([P[i], P[j], Pa]))
        # ---- 3. 顶面六边形：白色半透明（V=1 全平面） ----
        hexa = QPolygonF([P[i] for i in range(6)])
        p.setPen(QPen(QColor(theme.TEXT_2), 1.4))
        p.setBrush(QColor(255, 255, 255, 44))
        p.drawPolygon(hexa)
        # ---- 4. V=0.5 中间截面虚线六边形（水平截面随 V 缩小） ----
        p.setPen(QPen(QColor(theme.TEXT_2), 1, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        mid = [self.p3d(self._hue_vec(d, 0.5, 0.5))[0]
               for _, d, _ in top]
        p.drawPolygon(QPolygonF(mid))
        # ---- 5. 侧棱（锥尖 → 六顶点）：远细淡 / 近粗浓 ----
        for i in range(6):
            k = t(i)
            p.setPen(QPen(QColor(theme.TEXT_2).lighter(150 if k < 0.5 else 100),
                          1.1 + 0.9 * k))
            p.drawLine(Pa, P[i])
        h_deg, s_n, v_n = self._hsv
        # ---- 6. H 角弧：S 轴（0°）转到当前色相方向的水平弧 ----
        arc = [self.p3d(self._hue_vec(t2, 0.42, 0.0))[0]
               for t2 in range(0, int(h_deg) + 1,
                               max(1, int(h_deg) // 24 or 1))]
        if h_deg > 3:
            p.setPen(QPen(QColor(theme.ACCENT), 1.6))
            p.setBrush(Qt.NoBrush)
            p.drawPolyline(QPolygonF(arc))
        p.setPen(QPen(QColor(theme.ACCENT), 1))
        amid = self.p3d(self._hue_vec(h_deg / 2 + 14, 0.62, 0.0))[0]
        p.drawText(QRectF(amid.x() - 30, amid.y() - 10, 60, 20),
                   Qt.AlignCenter, f"H={h_deg:.0f}°")
        # ---- 7. 顶点本色圆点 + 名称（远处淡化缩小）；中心白点 ----
        p.setFont(QFont(theme.UI_FONT, 9))
        center = QPointF(self.width() / 2, self.height() / 2)
        for i in sorted(range(6), key=lambda i2: Dtop[i2]):
            name, deg, _v = top[i]
            pos = P[i]
            k = t(i)
            dot = 3.4 + 1.8 * k
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(*hsv_to_rgb(deg, 100, 100))))
            p.drawEllipse(pos, dot, dot)
            _pc = QColor(theme.TEXT_1)
            _pc.setAlpha(120 + int(110 * k))
            p.setPen(QPen(_pc, 1))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(pos, dot, dot)
            self.draw_label(p, pos, name,
                            QPointF(pos.x() - center.x(),
                                    pos.y() - center.y()),
                            dim=1.0 - 0.55 * (1 - k))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(255, 255, 255)))
        p.drawEllipse(Pw, 4, 4)
        p.setPen(QPen(QColor(theme.TEXT_1), 1))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(Pw, 4, 4)
        self.draw_label(p, Pw, "白(1,0)", QPointF(0, -1))
        p.setPen(QPen(QColor(theme.TEXT_1), 1))
        self.draw_label(p, Pa, "黑(0,0)", QPointF(0, 1))
        # ---- 7. 当前色点：锥内定位 + 混色射线 ----
        cur_v = self._hue_vec(h_deg, max(0.02, s_n), v_n)
        cur, _ = self.p3d(cur_v)
        pure = self._hue_vec(h_deg, 1.0, v_n)         # 同 V 截面上的纯色点
        p.setPen(QPen(QColor(theme.TEXT_2), 1, Qt.DotLine))
        p.drawLine(self.p3d((0, v_n, 0))[0], cur)     # 白轴 → 当前（加白方向）
        p.drawLine(cur, Pa)                           # 当前 → 锥尖（加黑方向）
        p.drawLine(self.p3d(pure)[0], cur)            # 纯色 → 当前（降饱和）
        rgb = hsv_to_rgb(h_deg, s_n, v_n)
        # 三层环提高任意底色下的可辨识度：深描边 → 白描边 → 色芯
        p.setPen(QPen(QColor(theme.TEXT_1), 1))
        p.setBrush(QBrush(QColor(*rgb)))
        p.drawEllipse(cur, 8, 8)
        p.setPen(QPen(QColor(255, 255, 255), 2))
        p.drawEllipse(cur, 6, 6)
        self.draw_label(p, cur, f"S={s_n:.0f} V={v_n:.0f}",
                        QPointF(cur.x() - center.x(),
                                cur.y() - center.y()),
                        color=theme.ACCENT)


# =====================================================================
# 页面 3：RGB⇄HSV 转换过程推导
# =====================================================================
class ConvertPage(QWidget):
    """转换过程推导页：色轮 + S-V 截面（可拖，HSV→RGB 反向写回），
    拖 R/G/B 逐步代入公式算 H/S/V 并反向验证——归档"转换过程可视化"
    的移植升级版：RGB 与 HSV 双向可调。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rgb = (220, 60, 80)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("RGB ⇄ HSV 转换过程（双向可调，实时代入）")
        title.setObjectName("cardTitle")
        root.addWidget(title)

        # ---- 1. 可视化行：色轮 + 轴截面（居中，均可拖动） ----
        views = QHBoxLayout()
        views.setSpacing(16)
        self.ring = _HueRing(on_pick=self._on_ring_pick)
        self.sv_view = _SVSection(on_pick=self._on_sv_pick)
        for v in (self.ring, self.sv_view):
            v.setFixedSize(320, 235)
        views.addStretch(1)
        views.addWidget(self.ring)
        views.addWidget(self.sv_view)
        views.addStretch(1)
        root.addLayout(views)

        # ---- 2. RGB 滑杆（全宽三行，不再挤窄列） ----
        self._rows = []
        for name, col, val in (("R 红", "#E5484D", self._rgb[0]),
                               ("G 绿", "#30A46C", self._rgb[1]),
                               ("B 蓝", "#3B6FF6", self._rgb[2])):
            r = _SliderRow(name, col, 0, 255, val)
            r.slider.valueChanged.connect(self._on_change)
            self._rows.append(r)
            root.addWidget(r)

        # ---- 3. 当前颜色展示条：大色块 + HEX/CMY 读数 ----
        crow = QHBoxLayout()
        crow.setSpacing(14)
        self.swatch = _Swatch()
        self.swatch.setFixedHeight(56)
        crow.addWidget(self.swatch, stretch=1)
        colv = QVBoxLayout()
        colv.setSpacing(2)
        self.hex_lab = QLabel()
        self.hex_lab.setObjectName("mono")
        colv.addWidget(self.hex_lab)
        self.cmy_lab = QLabel()
        self.cmy_lab.setObjectName("mono")
        self.cmy_lab.setStyleSheet(f"color: {theme.TEXT_2};")
        colv.addWidget(self.cmy_lab)
        crow.addLayout(colv)
        root.addLayout(crow)

        # ---- 4. 色相条（可点击/拖动直接调 H） ----
        self.hue_bar = _HueBar(on_pick=self._on_ring_pick)
        root.addWidget(self.hue_bar)

        # ---- 5. 推导面板 ----
        self.derive = QLabel()
        self.derive.setTextFormat(Qt.PlainText)
        self.derive.setStyleSheet(
            f"font-family: {theme.UI_FONT}; font-size: 13px;"
            f" color: {theme.TEXT_1}; background: {theme.BG_WINDOW};"
            f" border: 1px solid {theme.BORDER}; border-radius: 8px;"
            f" padding: 12px;")
        self.derive.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.derive.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        root.addWidget(self.derive, stretch=1)
        self._on_change()

    # ---- HSV 侧拖动 → 反向写回 RGB 滑杆（互相转换的"互相"） ----
    def _on_ring_pick(self, h: float):
        _r, s, v = rgb_to_hsv(*self._cur_rgb())
        self._apply_hsv(h, s, v)

    def _on_sv_pick(self, s: float, v: float):
        h, _s, _v = rgb_to_hsv(*self._cur_rgb())
        self._apply_hsv(h, s, v)

    def _cur_rgb(self):
        return tuple(x.value() for x in self._rows)

    def _apply_hsv(self, h: float, s: float, v: float):
        r, g, b = hsv_to_rgb(h, s, v)
        for row, val in zip(self._rows, (r, g, b)):
            row.slider.setValue(val)

    def _on_change(self):
        r, g, b = (x.value() for x in self._rows)
        h, s, v = rgb_to_hsv(r, g, b)
        rp, gp, bp = r / 255, g / 255, b / 255
        mx, mn = max(rp, gp, bp), min(rp, gp, bp)
        d = mx - mn
        who = "R" if mx == rp else ("G" if mx == gp else "B")
        if d == 0:
            h_line = "H：Δ = 0（灰色，无色相，约定 H = 0°）"
        elif mx == rp:
            h_line = (f"H：Max=R → H = 60°×(({gp:.3f}−{bp:.3f})/{d:.3f} mod 6)"
                      f" = {h:.1f}°")
        elif mx == gp:
            h_line = (f"H：Max=G → H = 60°×(({bp:.3f}−{rp:.3f})/{d:.3f}+2)"
                      f" = {h:.1f}°")
        else:
            h_line = (f"H：Max=B → H = 60°×(({rp:.3f}−{gp:.3f})/{d:.3f}+4)"
                      f" = {h:.1f}°")
        rr, gg, bb = hsv_to_rgb(h, s, v)
        ok = "一致 ✓" if (rr, gg, bb) == (r, g, b) else \
            f"偏差 ({rr},{gg},{bb})（四舍五入误差）"
        self.derive.setText(
            f"输入 RGB = ({r}, {g}, {b})\n"
            f"\n"
            f"① 归一化   R'={rp:.3f}  G'={gp:.3f}  B'={bp:.3f}\n"
            f"② 求最值   Max = {mx:.3f} ({who})   Min = {mn:.3f}"
            f"   Δ = {d:.3f}\n"
            f"③ V 明度   V = Max = {mx:.3f} → {v:.0f}\n"
            f"④ S 饱和   S = Δ/Max = {d:.3f}/{mx:.3f}"
            f" = {s:.0f}" + ("  （Max=0 时 S=0）\n" if mx == 0 else "\n") +
            f"⑤ H 色相   {h_line}\n"
            f"\n"
            f"结果  HSV = ({h:.1f}°, {s:.0f}, {v:.0f})"
            f"   HEX = {_hex(r, g, b)}\n"
            f"反向验证  HSV→RGB = ({rr}, {gg}, {bb})  与输入{ok}")
        self.swatch.set_color(QColor(r, g, b))
        self.hex_lab.setText(_hex(r, g, b))
        c2, m2, y2 = rgb_to_cmy(r, g, b)
        self.cmy_lab.setText(f"CMY ({c2:.0f}%, {m2:.0f}%, {y2:.0f}%)")
        self.hue_bar.set_hue(h)
        self.ring.set_hsv((h, s, v))
        self.sv_view.set_hsv((h, s, v))


class _HueBar(QWidget):
    """0-360° 色相条 + 当前 H 游标。位图只建一次。
    点击/拖动色条 → on_pick(H)，与色轮/滑杆同一联动回路。"""

    def __init__(self, parent=None, on_pick=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self._hue = 0.0
        self._img = None
        self._on_pick = on_pick
        self._pressed = False
        if on_pick is not None:
            self.setCursor(Qt.PointingHandCursor)
            self.setToolTip("点击/拖动色条调整色相 H")

    def set_hue(self, h: float):
        self._hue = h
        self.update()

    def _handle_pick(self, pos):
        if self.width() <= 0:
            return
        h = max(0.0, min(359.9, pos.x() / self.width() * 360))
        self._hue = h
        self.update()
        if self._on_pick is not None:
            self._on_pick(h)

    def mousePressEvent(self, e):
        if self._on_pick is None:
            return
        self._pressed = True
        self._handle_pick(e.position())

    def mouseMoveEvent(self, e):
        if self._on_pick is None or not self._pressed:
            return
        self._handle_pick(e.position())

    def mouseReleaseEvent(self, _e):
        self._pressed = False

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        bar_h = h - 16
        if self._img is None or self._img.width() != w:
            img = QImage(w, 1, QImage.Format_RGB32)
            for x in range(w):
                img.setPixel(x, 0, QColor(*hsv_to_rgb(x / w * 360, 100, 100)).rgb())
            self._img = img
        p.drawImage(QRectF(0, 2, w, bar_h), self._img,
                    QRectF(0, 0, w, 1))
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(0, 2, w - 1, bar_h - 1))
        # 游标：当前 H 处竖线 + 顶部倒三角
        x = self._hue / 360 * w
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(QColor(theme.TEXT_1), 2))
        p.drawLine(QPointF(x, 2), QPointF(x, 2 + bar_h))
        p.setBrush(QBrush(QColor(theme.TEXT_1)))
        p.drawPolygon(QPolygonF([QPointF(x - 5, 0), QPointF(x + 5, 0),
                                 QPointF(x, 8)]))


# =====================================================================
# 模块演示页出口（演示壳通过 module.create_demos() 取走）
# =====================================================================
def create_demos() -> List[ColorPage]:
    """模块一的 3 个交互演示页（无画板）。"""
    return [
        ColorPage(
            title="RGB 颜色立方体",
            icon="grid",
            variables={"R/G/B": "三个分量各 0–255，对应立方体三根轴",
                       "顶点": "8 个顶点 = 黑/白 + 三原色 + 两两混合",
                       "主对角线": "黑(0,0,0) → 白(255,255,255) 灰度轴"},
            formula=("RGB 立方体\n"
                     "任意色 C = (R, G, B)，R,G,B ∈ [0,255]\n"
                     "三原色相加混合：\n"
                     "  R+G=黄  G+B=青  B+R=品红\n"
                     "  R+G+B=白（全 1）／黑（全 0）"),
            factory=RgbCubePage,
        ),
        ColorPage(
            title="HSV 六棱锥",
            icon="palette",
            variables={"H": "色相 0–360°，顶面六边形顶点角",
                       "S": "饱和度 0–100，到中心竖轴的距离",
                       "V": "明度 0–100，六棱锥高度（锥尖黑）"},
            formula=("HSV 六棱锥（PPT：从 RGB 立方体演变）\n"
                     "沿 RGB 立方体 白→黑 对角线看过去 = 顶面六边形\n"
                     "顶面 V=1：红0° 黄60° 绿120° 青180° 蓝240° 品红300°\n"
                     "锥尖黑(0,0)，中心白(1,0)，V 轴过锥心\n"
                     "S：到中心竖轴的水平距离（锥面=1，轴=0）\n"
                     "V：高度（顶面全纯色，向下渐黑=色调）\n"
                     "人眼调色直觉：先选色相，再调深浅浓淡"),
            factory=HsvConePage,
        ),
        ColorPage(
            title="RGB⇄HSV 转换推导",
            icon="compare",
            variables={"R'G'B'": "先归一化到 0–1",
                       "Max/Min/Δ": "三分量最大/最小/差",
                       "V/S/H": "由 Max、Δ、Max 位置逐步导出"},
            formula=("RGB → HSV\n"
                     "V = Max(R',G',B')\n"
                     "S = Δ/Max（Δ=0 时 S=0）\n"
                     "Max=R: H = 60°×((G'−B')/Δ mod 6)\n"
                     "Max=G: H = 60°×((B'−R')/Δ + 2)\n"
                     "Max=B: H = 60°×((R'−G')/Δ + 4)\n"
                     "HSV → RGB：C=V·S，X=C(1−|(H/60)mod2−1|)，\n"
                     "按 H 所在 60° 区段取 (C,X,0) 排列再 +m=V−C"),
            factory=ConvertPage,
        ),
    ]
