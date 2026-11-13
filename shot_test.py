# -*- coding: utf-8 -*-
"""
=====================================================================
 shot_test.py — 模块三（变换）/ 模块四（裁剪）实拍截图
=====================================================================
用真实窗口渲染（Qt 原生平台 + 窗口挪到屏幕外：不打扰桌面，又能拿到
系统字体——本机 offscreen 插件取不到字体，中文会变方框），脚本化复现
界面上真实看到的样子：

  · 应用模式：变换工具的选中框 / 8 手柄 / 旋转手柄 / 拖拽读数 / 数值面板；
  · 演示模式：平移 / 旋转 / 缩放 / 复合变换 四页；
  · 演示模式：Cohen / 中点分割 / Liang / S-H 多边形 / W-A 双边 五页；
  · 应用模式：区域裁剪窗口 / 挖除结果 / 裁剪后旋转（几何随图元走）。

输出到 运行截图/，文件名供 gen_report2.py 的图号顺序引用。
=====================================================================
"""

import math
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication

from core.shapes import CircleShape, LineShape, PolygonShape
from ui import theme
from ui.main_window import MainWindow

OUT = os.path.join(BASE, "运行截图")
os.makedirs(OUT, exist_ok=True)

BLUE = QColor("#4F6EF7")
ORANGE = QColor("#F76B15")
TEAL = QColor("#12A594")

app = QApplication(sys.argv)
app.setFont(QFont(theme.UI_FONT, 10))
theme.apply(app)

win = MainWindow()
win.resize(1500, 940)
win.move(-4000, -4000)        # 真窗口，但挪到屏幕外，不打扰桌面
win.show()


def pump(n=6):
    """跑一轮事件循环，等布局/重绘落地。

    顺带把 Qt 的延迟删除（deleteLater）清掉：切演示页时监视器会重建
    行集，旧行是 deleteLater 掉的，只有真正处理了 DeferredDelete 事件
    它们才会消失——否则截图里会叠着上一页的文字（真机事件循环会处理，
    这里要手动补一次）。
    """
    for _ in range(n):
        app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def shot(name):
    pump()
    path = os.path.join(OUT, name)
    win.grab().save(path)
    print("saved:", name)


def tool_index(cls):
    for i, c in enumerate(win._tool_classes):
        if c is cls:
            return i
    raise KeyError(cls.__name__)


# =====================================================================
# 一、应用模式：二维变换交互
# =====================================================================
from modules.module03_transform2d.tools import Transform2DTool

win._activate_tool(tool_index(Transform2DTool))
pump()

poly = PolygonShape(kind="polygon", color=BLUE, fill=True,
                    vertices=[(8, 10), (30, 6), (38, 24), (16, 30)])
line = LineShape(kind="line_bresenham", color=ORANGE,
                 p0=(6, 36), p1=(46, 32))
circ = CircleShape(kind="circle_mid", color=TEAL, center=(47, 13), r=9)
for s in (poly, line, circ):
    win.canvas.add_shape(s)

win.canvas.set_selection([poly, line, circ])
win.canvas.fit_to_rect(0, 0, 58 * 20, 44 * 20, pad=80)
pump()
shot("m3_01_二维变换_选中与手柄.png")

# --- 模拟"拖旋转手柄"：包围盒下方实时显示角度读数 ---
bbox = win.canvas._sel_bbox()
rh = win.canvas._rotate_handle(bbox)
if rh is not None:
    cv = win.canvas
    # begin_rotate / update_move 收【模拟像素坐标】，场景坐标要除以 SIM
    cv.begin_rotate(QPointF(rh[0] / 20.0, rh[1] / 20.0))
    cx = (bbox[0] + bbox[2]) / 2.0 / 20.0
    cy = (bbox[1] + bbox[3]) / 2.0 / 20.0
    r = 26.0
    ang = math.radians(45)
    cv.update_move(QPointF(cx + r * math.cos(ang), cy + r * math.sin(ang)))
    nb = cv._sel_bbox()
    cv.fit_to_rect(nb[0], nb[1], nb[2], nb[3], pad=150)
    pump()
    shot("m3_02_二维变换_拖拽旋转读数.png")
    cv.cancel_move()
    pump()

# --- 变换面板（数值变换）---
panel = win.tool_panel_host
if panel is not None and panel.isVisible():
    pump()
    panel.grab().save(os.path.join(OUT, "m3_03_二维变换_数值面板.png"))
    print("saved: m3_03_二维变换_数值面板.png")

# =====================================================================
# 二、演示模式：模块三 四页
# =====================================================================
win._on_mode_changed(1)
pump()
dv = win.demo_view

# 演示画布上准备被演示的图元（演示对象 = 画布上选中的图元）
src = PolygonShape(kind="polygon", color=BLUE, fill=True,
                   vertices=[(14, 10), (38, 6), (46, 28), (20, 34)])
dv.canvas.add_shape(src)
dv.canvas.set_selected_shape(src)
pump()

from modules.module03_transform2d.demos import (ComposeDemo, RotateDemo,
                                                ScaleDemo, TranslateDemo)


def demo_shot(page_cls, name, index=None, decompose=False):
    """切到指定演示页 → 生成步骤流 → 停在指定帧 → 截图。"""
    page = next(d for d in dv._all_pages if isinstance(d, page_cls))
    dv._on_page_button(page, dv._page_buttons[page])
    pump()
    if decompose:
        cb = getattr(dv.current_demo, "_decomp", None)
        if cb is not None:
            cb.setChecked(True)
    dv._regenerate(fit=True, autoplay=False)
    pump()
    n = len(dv.player.steps)
    if n == 0:
        print("!! 无步骤流:", name)
        return
    k = n - 1 if index is None else max(0, min(index, n - 1))
    dv.player._set_index(k)
    pump()
    shot(name)
    print(f"   步骤数={n} 当前帧={k + 1}/{n} 阶段="
          f"{dv.player.steps[k].values.get('阶段', '—')}")


demo_shot(TranslateDemo, "m3_04_平移变换演示.png", index=8)
demo_shot(RotateDemo, "m3_05_旋转变换演示_分解三阶段.png",
          index=12, decompose=True)
demo_shot(ScaleDemo, "m3_06_缩放变换演示_分解三阶段.png",
          index=12, decompose=True)
demo_shot(ComposeDemo, "m3_07_复合变换演示_五阶段.png", index=20)

# =====================================================================
# 三、演示模式：模块四 五页
# =====================================================================
from modules.module04_clipping.demos import (CohenDemo, LiangDemo,
                                             MidpointDemo,
                                             PolygonClipDemo,
                                             PolygonClipWADemo)

# 清掉模块三演示用过的图元：裁剪页的截图只要"被裁对象 + 裁剪窗口"，
# 画面干净才看得清判定过程（否则两个多边形叠在一起，谁被裁都看不清）。
dv.canvas.clear_all()
pump()

# 线段裁剪三页的被裁对象：一条斜穿窗口的直线
clip_line = LineShape(kind="line_bresenham", color=BLUE,
                       p0=(4, 38), p1=(54, 6))
dv.canvas.add_shape(clip_line)
dv.canvas.set_selected_shape(clip_line)
pump()


def clip_shot(page_cls, name, index=None, poly_window=None, subject=None):
    """切到裁剪演示页 → 生成步骤流 → 停在指定帧 → 截图。

    poly_window: 画一个多边形窗口（顶点表），切到"多边形窗口"模式；
    subject:     换被裁对象（多边形裁剪页只接受封闭图形）。
    """
    page = next(d for d in dv._all_pages if isinstance(d, page_cls))
    dv._on_page_button(page, dv._page_buttons[page])
    pump()
    demo = dv.current_demo
    if subject is not None:
        dv.canvas.set_selected_shape(subject)
    if poly_window is not None:
        demo._on_window_kind(1)          # 切到"多边形窗口"
        # 程序化切换不会自动更新分段控件的选中态 → 手动对上，
        # 否则截图里"矩形窗口"还是高亮的，与画布上的多边形窗口矛盾
        seg = getattr(demo, "_win_seg", None)
        if seg is not None:
            seg.set_current(1)
        pump()
        tool = dv.canvas.tool
        tool.poly = list(poly_window)
        tool._notify_window()
        pump()
    dv._regenerate(fit=True, autoplay=False)
    pump()
    n = len(dv.player.steps)
    if n == 0:
        print("!! 无步骤流:", name)
        return
    k = n - 1 if index is None else max(0, min(index, n - 1))
    dv.player._set_index(k)
    pump()
    shot(name)
    print(f"   步骤数={n} 当前帧={k + 1}/{n} 阶段="
          f"{dv.player.steps[k].values.get('阶段', '—')}"
          f"  段={dv.player.steps[k].values.get('段', '—')}")


clip_shot(CohenDemo, "m4_01_编码裁剪_Cohen-Sutherland.png", index=1)
clip_shot(MidpointDemo, "m4_02_中点分割裁剪.png", index=3)
clip_shot(LiangDemo, "m4_03_参数裁剪_Liang-Barsky.png", index=2)

# 多边形裁剪两页：被裁对象 = 封闭多边形（把直线撤掉，画面干净）
dv.canvas.remove_shape(clip_line)
clip_poly = PolygonShape(kind="polygon", color=BLUE, fill=True,
                          vertices=[(6, 8), (30, 4), (52, 16),
                                    (44, 36), (14, 38)])
dv.canvas.add_shape(clip_poly)
pump()

clip_shot(PolygonClipDemo, "m4_04_多边形裁剪_逐边S-H.png",
          index=3, subject=clip_poly)
# W-A：窗口画成一个【凹】多边形（逐边裁剪页会拒绝凹窗口，这里正是它的用武之地）
clip_shot(PolygonClipWADemo, "m4_05_多边形裁剪_双边W-A.png",
          index=3, subject=clip_poly,
          poly_window=[(18, 6), (46, 6), (46, 20), (32, 30), (18, 22)])

# =====================================================================
# 四、应用模式：区域裁剪（挖除 + 裁剪后旋转）
# =====================================================================
win._on_mode_changed(0)          # 回到应用模式：应用图元整体恢复
pump()

from modules.module04_clipping.tools import ClipTool

win._activate_tool(tool_index(ClipTool))
pump()

tool = win.canvas.tool
tool.rect = (18, 8, 42, 32)
tool._refresh_ui()
win.canvas.fit_to_rect(0, 0, 58 * 20, 44 * 20, pad=80)
pump()
shot("m4_06_区域裁剪_窗口就绪.png")

tool.commit_window()              # Enter 确认 → 挖除窗口内部分
pump()
shot("m4_07_区域裁剪_挖除结果.png")

# --- 裁剪后旋转：挖掉的区域应跟着图元走（干净一块，不残留黑散点）---
from algorithms import transform2d as tf

win.canvas.set_selection([poly])
pump()
piv = win.canvas.pivot_point()
if piv is not None:
    win.canvas.transform_selection(
        tf.around(piv, tf.rotation(30)), "旋转图元")
    pump()
    win.canvas.fit_to_rect(0, 0, 58 * 20, 44 * 20, pad=80)
    pump()
    shot("m4_08_裁剪后旋转_几何随图元走.png")

print("=== 全部截图完成 ===")
