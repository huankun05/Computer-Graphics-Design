# -*- coding: utf-8 -*-
"""
=====================================================================
 smoke_test.py  —  离屏启动烟测（框架层自检，无真实窗口弹出）
=====================================================================
验证项（阶段一验收标准）：
  1. 主窗口可构建：模块发现 → 工具加载 → 面板/画布初始化；
  2. 五种工具可激活、可产生预览、可提交图元；
  3. 撤销/重做命令栈行为正确（含清空恢复、redo 失效规则）；
  4. save_image 导出 PNG 成功（阶段一修复的 bug）；
  5. drawForeground 批量预览绘制路径无异常（drawPoints/drawRects）。
在 build/烟测/ 下留档截图。开发辅助脚本，不随作业交付。
=====================================================================
"""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QPushButton, QToolButton

from core.canvas_view import CanvasView, IMAGE_W, IMAGE_H
from core.shapes import (LineShape, CircleShape, PolygonShape, KIND_LINE_DDA,
                         KIND_POLYGON, KIND_RASTER_FILL)
from core.registry import discover, all_modules

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build", "烟测")
os.makedirs(OUT, exist_ok=True)

app = QApplication.instance() or QApplication(sys.argv)

errors = []


def expect(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        errors.append(msg)


# ---------------------------------------------------------------------
# 1. 模块发现与工具加载
# ---------------------------------------------------------------------
print("[1] 模块注册表")
discover()
mods = all_modules()
expect(len(mods) >= 2, f"发现 {len(mods)} 个模块: {[m.name for m in mods]}")
tool_classes = [c for m in mods for c in m.tool_classes]
expect(len(tool_classes) == 8, f"工具类共 {len(tool_classes)} 个（应为 8：填充合一）")

# ---------------------------------------------------------------------
# 2. 画布 + 工具交互（预览 → 提交）
# ---------------------------------------------------------------------
print("[2] 画布与工具交互")
canvas = CanvasView()
tools = [cls(canvas) for cls in tool_classes]

# 拖拽类工具（直线/圆/椭圆）：按下 → 拖拽预览 → 松开提交
for tool in tools[:3]:
    canvas.set_tool(tool)
    tool.on_press(QPointF(200, 200))
    tool.on_move(QPointF(500, 350))
    expect(canvas.preview_shape is not None, f"{tool.name}: 拖拽产生预览")
    canvas._refresh_preview()               # 手动驱动节流定时器逻辑
    expect(len(canvas._preview_pixels) > 0, f"{tool.name}: 预览像素已计算")
    tool.on_release(QPointF(500, 350))

# 多边形工具：逐点点击，2 点出预览，3 点右键闭合提交
poly_tool = tools[3]
canvas.set_tool(poly_tool)
poly_tool.on_press(QPointF(200, 200))
expect(canvas.preview_shape is not None and len(canvas.preview_shape.vertices) == 1,
       "扫描线填充: 单顶点显示落点与顶点标记")
poly_tool.on_press(QPointF(600, 250))
canvas._refresh_preview()
expect(canvas.preview_shape is not None and len(canvas._preview_pixels) > 0,
       "扫描线填充: 两顶点出折线预览")
poly_tool.on_press(QPointF(400, 500))
poly_tool.on_right_click(QPointF(0, 0))     # 右键闭合 → 提交填充

# 直线算法对比工具：一拖提交两条（DDA 橙 + Bresenham 蓝紫）
cmp_tool = tools[4]
canvas.set_tool(cmp_tool)
cmp_tool.on_press(QPointF(100, 300))
cmp_tool.on_move(QPointF(500, 150))
cmp_tool.on_release(QPointF(500, 150))
expect(len(canvas.document.shapes) == 6,
       f"3 拖拽+多边形+对比对 共提交 6 图元（实际 {len(canvas.document.shapes)}）")
last_two = list(canvas.document.shapes[-2:])   # 立刻取样（后续检查会追加图元）

# 算法下拉：切换直线算法 → 提交的 kind 跟随
canvas.set_algorithm("line_bresenham")
canvas.set_tool(tools[0])
tools[0].on_press(QPointF(100, 600))
tools[0].on_release(QPointF(400, 500))
expect(canvas.shapes[-1].kind == "line_bresenham", "算法下拉切 Bresenham → 提交 kind 跟随")
canvas.set_algorithm("line_dda")

# 填充开关：填充态下圆提交即实心；描边态只画轮廓；按钮可对已画图元补填
from core.rasterizer import rasterize as _rz
canvas.set_tool(tools[1])
canvas.fill_mode = True
tools[1].on_press(QPointF(600, 600))
tools[1].on_release(QPointF(650, 650))
circ = canvas.shapes[-1]
expect(circ.fill and len(_rz(circ)[1]) > 0, "填充态：圆提交即实心（内部像素非空）")
canvas.fill_mode = False
canvas.set_tool(tools[1])
tools[1].on_press(QPointF(600, 250))
tools[1].on_release(QPointF(640, 290))
circ2 = canvas.shapes[-1]
expect(not circ2.fill and len(_rz(circ2)[1]) == 0, "描边态：只画轮廓")
canvas.set_selected_shape(circ2)
canvas.toggle_fill_selected()
expect(circ2.fill and len(_rz(circ2)[1]) > 0, "选中后填充按钮补填（可撤销）")
n0 = len(canvas.shapes)          # 记录基准（供撤销段使用）
dda_s = next(s for s in last_two if s.kind == "line_dda")
bre_s = next(s for s in last_two if s.kind == "line_bresenham")
expect({s.color.name().upper() for s in last_two} == {"#F76B15", "#3E63DD"}
       and dda_s.p0 == bre_s.p0 and dda_s.p1 == bre_s.p1
       and {s.inset for s in last_two} == {0, 5},
       "对比工具同位双层（蓝满格+橙内芯，坐标完全一致）")

# 坐标吸附：鼠标 (210,215) → 模拟像素 (10,10)（一格 = 一像素）
# mapToScene 依赖滚动/变换，先复位视图到原点再验证换算
canvas.resetTransform()
canvas.horizontalScrollBar().setValue(0)
canvas.verticalScrollBar().setValue(0)
from core.shapes import SIM, GRID_W, GRID_H
pos = canvas._to_pos(type("E", (), {"position": lambda self: __import__("PySide6.QtCore",
    fromlist=["QPointF"]).QPointF(210, 215)})())
expect((pos.x(), pos.y()) == (10, 10), f"坐标吸附到模拟像素格 {pos.x()},{pos.y()}")

# ---------------------------------------------------------------------
# 3. 撤销 / 重做命令栈
# ---------------------------------------------------------------------
print("[3] 撤销/重做")
# 填充命令可撤销（独立画布验证原子性）
from core.canvas_view import CanvasView as _CV
cv3 = _CV()
cv3.add_shape(LineShape(kind="line_dda", color=QColor("#000"), p0=(1, 1), p1=(9, 9)))
c2 = None
from core.shapes import CircleShape as _CS, KIND_CIRCLE_MID as _KM
c2 = _CS(kind=_KM, color=QColor("#123"), width=1)
c2.center = (5, 5); c2.r = 3
cv3.add_shape(c2)
cv3.set_selected_shape(c2)
cv3.toggle_fill_selected()
expect(c2.fill, "填充命令生效")
cv3.undo()
expect(not c2.fill, "填充命令可撤销")
cv3.redo()
expect(c2.fill, "填充命令可重做")

# 移动命令可撤销（快照式）
from core.shapes import translate as _tr, snapshot as _snap
line_shape = cv3.shapes[0]
before = _snap(line_shape)
_tr(line_shape, 3, 2)
after = _snap(line_shape)
from core.commands import MoveShapeCommand
cmd = MoveShapeCommand(cv3.document, line_shape, before, after)
cmd.do()
expect(line_shape.p0 == (before["p0"][0] + 3, before["p0"][1] + 2), "移动命令 do 生效")
cmd.undo()
expect(line_shape.p0 == before["p0"], "移动命令 undo 精确还原")

# 对比对原子性：独立画布上单命令一次退 2、重做一次恢复 2
from core.canvas_view import CanvasView as _CV
cv2 = _CV()
cv2.add_shapes([
    LineShape(kind="line_dda", color=QColor("#F76B15"), p0=(5, 5), p1=(20, 10)),
    LineShape(kind="line_bresenham", color=QColor("#3E63DD"), p0=(5, 5), p1=(20, 10)),
])
nb = len(cv2.shapes)
cv2.undo()
expect(len(cv2.shapes) == nb - 2, "对比对一次撤销整体退 2")
cv2.redo()
expect(len(cv2.shapes) == nb, "对比对重做一次恢复 2")
canvas.add_shape(LineShape(kind=KIND_LINE_DDA, color=QColor("#000")))  # 新操作
expect(not canvas.document.can_redo, "新操作后 redo 分支失效（主流惯例）")

# ---------------------------------------------------------------------
# 4. 保存 PNG（阶段一修复项）
# ---------------------------------------------------------------------
print("[4] 导出 PNG")
png_path = os.path.join(OUT, "smoke_export.png")
expect(canvas.save_image(png_path) and os.path.exists(png_path),
       f"save_image 导出成功: {png_path}")

# ---------------------------------------------------------------------
# 5. 主窗口构建 + 预览前景层批量绘制路径
# ---------------------------------------------------------------------
print("[5] 主窗口与前景渲染")
from ui.main_window import MainWindow
win = MainWindow()
win.show()
app.processEvents()

# 给画布一个宽线宽预览（走 drawRects 分支）并强制渲染一帧
# 注意：工具必须绑定 win.canvas（前面 tools[] 绑定的是裸 canvas）
win.canvas.set_pen_width(5)
line_tool = win._tool_classes[0](win.canvas)
win.canvas.set_tool(line_tool)
line_tool.on_press(QPointF(100, 100))
line_tool.on_move(QPointF(900, 700))
win.canvas._refresh_preview()
pix = win.canvas.grab().toImage()
expect(not pix.isNull() and pix.width() > 0, "画布 grab 渲染成功（前景层无异常）")
win.canvas.grab().save(os.path.join(OUT, "smoke_mainwindow.png"))

# 1px 线宽预览（drawPoints 分支）
win.canvas.set_pen_width(1)
win.canvas._refresh_preview()
app.processEvents()
win.canvas.grab().save(os.path.join(OUT, "smoke_mainwindow_thin.png"))
expect(len(win.canvas._preview_pixels) > 0, "1px 预览 drawPoints 分支正常")
win.close()

# ---------------------------------------------------------------------
# 6. 阶段二/三新增：显隐、选中、工程文件、Shift 约束、多边形键盘、UI 状态
# ---------------------------------------------------------------------
print("[6] 新增交互与工程文件")
from PySide6.QtCore import QEvent, Qt as Qt2
from PySide6.QtGui import QKeyEvent
from core.shapes import EllipseShape, KIND_ELLIPSE, KIND_CIRCLE
from modules.module02_primitives.tools import (
    LineTool, EllipseTool, PolygonTool, _snap_45,
)


def _fake_shift_event(pressed: bool):
    """构造带/不带 Shift 修饰键的伪事件（只用于 modifiers() 判断）。"""
    class _E:
        def modifiers(self):
            return Qt2.ShiftModifier if pressed else Qt2.NoModifier
    return _E()

# 6.1 图元显隐
doc_shapes = list(canvas.document.shapes)
doc_shapes[0].visible = False
canvas._render_base()
expect(not doc_shapes[0].visible, "图元 visible=False 生效")
doc_shapes[0].visible = True
canvas._render_base()

# 6.2 选中包围盒（模拟像素 ×SIM = 真实位图包围盒）
sel = doc_shapes[1]
canvas.set_selected_shape(sel)
bbox = canvas._shape_bbox(sel)
expect(bbox is not None and bbox[0] <= bbox[2] and bbox[1] <= bbox[3]
       and bbox[0] % SIM == 0,
       f"选中包围盒按模拟像素对齐 {bbox}")
canvas.set_selected_shape(None)

# 6.3 工程文件 .gpad 往返
from core import project_file
gpad = os.path.join(OUT, "smoke_roundtrip.gpad")
project_file.save_project(gpad, doc_shapes)
loaded = project_file.load_project(gpad)
expect(len(loaded) == len(doc_shapes), f"工程往返图元数一致（{len(loaded)}）")
expect(all(a.kind == b.kind for a, b in zip(loaded, doc_shapes)),
       "工程往返图元类型一致")
# 打开工程（ReplaceAll 可撤销）
n_before = len(canvas.document.shapes)
canvas.open_project(gpad)
expect(len(canvas.shapes) == n_before, "open_project 整体替换文档")
canvas.undo()
expect(len(canvas.shapes) == n_before, "打开工程可撤销（恢复原图元）")
canvas.redo()

# 6.4 Shift 约束：45° 吸附
from PySide6.QtCore import QPointF as QPF
snapped = _snap_45(QPF(100, 100), QPF(160, 115))   # 接近 15° → 吸附到 0°
expect(abs(snapped[1] - 100) <= 1, f"Shift 45° 吸附生效 {snapped}")

# 6.5 椭圆 Shift → 正圆
et = EllipseTool(canvas)
et._center = QPF(100, 100)
s = et._shape(QPF(180, 150), _fake_shift_event(True))
expect(s.rx == s.ry == 80, f"椭圆 Shift 约束为正圆 rx=ry={s.rx}")
s2 = et._shape(QPF(180, 150), None)
expect((s2.rx, s2.ry) == (80, 50), f"无 Shift 保持自由比例 {s2.rx}x{s2.ry}")

# 6.6 多边形 Backspace / Enter
pt = PolygonTool(canvas)
pt.on_press(QPF(100, 100))
pt.on_press(QPF(300, 120))
pt.on_press(QPF(250, 300))
ke = QKeyEvent(QEvent.KeyPress, Qt2.Key_Backspace, Qt2.NoModifier)
pt.on_key(ke)
expect(len(pt._verts) == 2, "Backspace 回退一个顶点")
pt.on_press(QPF(260, 310))
ke2 = QKeyEvent(QEvent.KeyPress, Qt2.Key_Return, Qt2.NoModifier)
pt.on_key(ke2)
expect(len(pt._verts) == 0, "Enter 闭合提交并清空顶点")
esc = QKeyEvent(QEvent.KeyPress, Qt2.Key_Escape, Qt2.NoModifier)
canvas.set_tool(pt)
pt.on_press(QPF(1, 1))
pt.cancel()
expect(len(pt._verts) == 0, "Esc 取消清空顶点")

# 6.7 主窗口 UI 状态
expect(len(win._tool_classes) == 8, "主窗口工具加载 8 个（填充合一）")
cmp_tool = win._tool_classes[4]
expect(cmp_tool.name == "算法对比" and len(cmp_tool.algorithm_options) == 2,
       "对比工具：可选直线/圆两种对比对")
# 视图卡按钮点击回归（曾因卡片嵌套被遮挡失效）
win._app_canvas.scale(0.6, 0.6)
fit_btn = next(b for b in win.findChildren(QPushButton) if "适配窗口" in b.text())
fit_btn.click(); app.processEvents()
z1 = win._app_canvas.transform().m11()
expect(abs(z1 - 1.0) < 0.2 or z1 > 0.6, f"适配窗口按钮可操作（缩放={z1:.2f}）")
zoom_btn = next(b for b in win.findChildren(QPushButton) if b.text().strip() == "100%")
zoom_btn.click(); app.processEvents()
expect(abs(win._app_canvas.transform().m11() - 1.0) < 0.01, "100% 按钮可操作")
win.show()                        # [5] 末尾关闭了窗口，UI 可见性检查前重开
app.processEvents()
win._activate_tool(0)
expect(win.algo_combo.isVisible() and win.algo_combo.count() == 2,
       "直线工具：算法下拉可见 2 项（DDA/Bresenham）")
win._activate_tool(4)
expect(win.algo_combo.isVisible() and win.algo_combo.count() == 2,
       "对比工具：算法下拉 2 项（直线对/圆对）")
win._activate_tool(1)
expect(win.algo_combo.isVisible() and win.algo_combo.count() == 2,
       "圆工具：算法下拉 2 项（中点圆/DDA 圆）")
expect(win.btn_fill.isEnabled(),
       "未选中图元 + 圆工具：填充按钮可用（切填充⇄描边提交态）")
win._activate_tool(0)
expect(not win.btn_fill.isEnabled(), "直线工具：填充按钮禁用（不支持填充）")
win._activate_tool(1)
expect("#222222" in win.color_block.styleSheet().lower()
       or win.color_block.styleSheet() == "",
       "右栏颜色块样式已刷新（含当前色）")
expect(win.mode_seg._buttons[1].isEnabled(), "演示模式切换钮存在（占位页）")
win._use_color(QColor("#123456"))
expect(win.hex_label.text() == "#123456", "选色后 HEX 同步")

expect(win._recent_colors[0].lower() == "#123456", "最近使用颜色前插")
from ui.color_table import ColorTable
ct = win.color_table
expect(isinstance(ct, ColorTable), "颜色卡主体为颜色表（HSV 色板）")
ct.set_color(QColor("#FF8000"))
c_picked = ct.color()
win._use_color(c_picked)
expect(win.canvas.pen_color == c_picked, "颜色表选色 → 画笔颜色同步")
win._use_color(QColor("#123456"))   # 恢复基准色，供后续断言使用
win.canvas.add_shape(LineShape(kind=KIND_LINE_DDA, color=QColor("#000000"),
                               p0=(0, 0), p1=(10, 10)))
expect(win.canvas.document.can_undo, "撤销按钮态数据源正常")

# 6.8 新 UI 截图留档（阶段二观感核对）
win.show()
app.processEvents()
win.canvas.clear_all()
app.processEvents()
win.grab().save(os.path.join(OUT, "smoke_ui_v5.png"))

# ---------------------------------------------------------------------
# 7. 阶段四：演示模式（网格修复 / 模块目录 / 播放器 / 监视器 / 像素层）
# ---------------------------------------------------------------------
# ================================================================
# [6b] 真实事件驱动交互复现（构造 QMouseEvent 走完整事件路径）
# ================================================================
print("[6b] 真实事件驱动交互")
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtCore import QEvent, QPointF as _QPF, Qt as _Qt
from PySide6.QtCore import QEvent as _QEvent

def _mouse(t, x, y, btn=_Qt.LeftButton, mods=_Qt.NoModifier):
    return QMouseEvent(t, _QPF(x, y), _QPF(x, y), btn, _Qt.NoButton, mods)

cv = win.canvas
cv.resize(1100, 700); app.processEvents()
sb_h, sb_v = cv.horizontalScrollBar(), cv.verticalScrollBar()

print("  1) 空格+拖拽 平移")
QTest.keyPress(win, _Qt.Key_Space); app.processEvents()
h0, v0 = sb_h.value(), sb_v.value()
cv.mousePressEvent(_mouse(_QEvent.MouseButtonPress, 400, 300))
cv.mouseMoveEvent(_mouse(_QEvent.MouseMove, 300, 200))
cv.mouseReleaseEvent(_mouse(_QEvent.MouseButtonRelease, 300, 200))
app.processEvents()
dh, dv = sb_h.value() - h0, sb_v.value() - v0
expect(abs(dh) > 0 and abs(dv) > 0, f"空格+拖拽平移（位移 h{dh} v{dv}）")
QTest.keyRelease(win, _Qt.Key_Space); app.processEvents()

print("  2) 中键拖拽 平移")
h0, v0 = sb_h.value(), sb_v.value()
cv.mousePressEvent(_mouse(_QEvent.MouseButtonPress, 400, 300, _Qt.MiddleButton))
cv.mouseMoveEvent(_mouse(_QEvent.MouseMove, 300, 200, _Qt.MiddleButton))
cv.mouseReleaseEvent(_mouse(_QEvent.MouseButtonRelease, 300, 200,
                            _Qt.MiddleButton))
app.processEvents()
dh, dv = sb_h.value() - h0, sb_v.value() - v0
expect(abs(dh) > 0 and abs(dv) > 0, f"中键拖拽平移（位移 h{dh} v{dv}）")

print("  3) 选中图元 按住拖拽移动")
win._activate_tool(0)
t = win._tool_classes[0](win._app_canvas); win._app_canvas.set_tool(t)
t.on_press(_QPF(10, 7)); t.on_release(_QPF(20, 15))     # 模拟像素 (10,7)-(20,15)
s = win._app_canvas.shapes[0]
win._app_canvas.set_selected_shape(s); app.processEvents()
p0b = s.p0
vp_pos = cv.mapFromScene(_QPF(15 * 20 + 10, 11 * 20 + 10))
vp2 = cv.mapFromScene(_QPF(18 * 20 + 10, 14 * 20 + 10))
cv.mousePressEvent(_mouse(_QEvent.MouseButtonPress, vp_pos.x(), vp_pos.y()))
cv.mouseMoveEvent(_mouse(_QEvent.MouseMove, vp2.x(), vp2.y()))
cv.mouseReleaseEvent(_mouse(_QEvent.MouseButtonRelease, vp2.x(), vp2.y()))
app.processEvents()
expect(s.p0 == (13, 10) and s.p1 == (23, 18),
       f"选中后按住拖拽移动（p0={s.p0}→{s.p1}）")
win._app_canvas.set_selected_shape(None)

print("  4) SE 手柄缩放（真实鼠标）")
win._activate_tool(1)
c = win._tool_classes[1](win._app_canvas); win._app_canvas.set_tool(c)
c.on_press(_QPF(30, 30)); c.on_release(_QPF(40, 30))
sc = win._app_canvas.shapes[-1]
win._app_canvas.set_selected_shape(sc); app.processEvents()
bbox = win._app_canvas._sel_bbox()
hp = _QPF(bbox[2], (bbox[1] + bbox[3]) / 2)
hpos = cv.mapFromScene(hp)
vp3 = cv.mapFromScene(_QPF(hp.x() + 100, hp.y()))
cv.mousePressEvent(_mouse(_QEvent.MouseButtonPress, hpos.x(), hpos.y()))
cv.mouseMoveEvent(_mouse(_QEvent.MouseMove, vp3.x(), vp3.y()))
cv.mouseReleaseEvent(_mouse(_QEvent.MouseButtonRelease, vp3.x(), vp3.y()))
app.processEvents()
expect(sc.r > 10 and sc.center == (30, 30),
       f"E 手柄向右拖：等比放大 r 10→{sc.r}，圆心定点不动")

print("[6c] 右栏窄宽回归（内容体不得被最宽行撑出视口）")
win.resize(960, 640); app.processEvents()
_scroll = win._right_scroll
_body_w = _scroll.widget().width()
_vp_w = _scroll.viewport().width()
expect(_body_w <= _vp_w,
       f"右栏内容宽度 ≤ 视口（body {_body_w} ≤ {_vp_w}，无水平裁切）")
win.resize(1280, 800); app.processEvents()

print("  [6d] 窗口拖动区（页眉/状态栏/选项条/右栏空白处）")
_calls = []
_qh = win.windowHandle()
_qh.startSystemMove = lambda: _calls.append(1)   # 桩在 QWindow 包装对象上
def _press_at(w, x, y):
    QApplication.sendEvent(w, QMouseEvent(QEvent.MouseButtonPress,
        QPointF(x, y), QPointF(x, y), _Qt.LeftButton, _Qt.NoButton,
        _Qt.NoModifier))
from PySide6.QtWidgets import QStatusBar as _QSB
_vis_sb = [b for b in win.findChildren(_QSB) if b in win._drag_widgets][0]
_press_at(_vis_sb, 200, 13)
_press_at(win.options_bar, 5, 5)
_press_at(win.right_panel, 5, 5)
class _HE:
    def button(self): return _Qt.LeftButton
win._header_press(_HE())
expect(len(_calls) == 4,
       f"页眉/状态栏/选项条/右栏 空白按下均触发窗口拖动（触发 {_calls}）")

print("  [6e] 缩放滑杆联动（视图卡）")
win._activate_tool(0); app.processEvents()   # 回直线工具
_z0 = win.canvas.transform().m11()
win.zoom_slider.setValue(200); app.processEvents()
expect(abs(win.canvas.transform().m11() - _z0 * 2) < 0.02,
       "缩放滑杆拖到 200% → 画布 2 倍缩放")
win.canvas.zoom_100(); app.processEvents()
expect(win.zoom_slider.value() == 100 and win.zoom_lab.text() == "100%",
       "画布缩放变化 → 滑杆/读数回同步（100%）")

print("[7] 演示模式")
from algorithms.steps import Step

# 7.1 网格移到前景层后可见性（逻辑验证：开关与前景绘制不异常，含 800% 极限缩放）
win.canvas.show_grid = True
win.canvas.show_axis = True
win.canvas.scale(8.0, 8.0)                    # 旧版此处网格步长计算会死循环
app.processEvents()
win.canvas.grab()
win.canvas.zoom_100()
expect(True, "网格前景层绘制 + 800% 极限缩放无死循环")

# 7.2 演示页加载
demo_view = win.demo_view
expect(len(demo_view._all_pages) == 9,
       f"演示页 {len(demo_view._all_pages)} 个（模块一 3 + 模块二 6）")
from modules.module02_primitives.demos import (CircleDemo, LineDemo,
                                               CompareDemo, PolygonDemo, FillDemo)
gd = next(d for d in demo_view._all_pages if isinstance(d, CompareDemo))
# 直线：DDA vs Bresenham
lsteps = gd.make_steps({"shape": "line", "a": "line_dda", "b": "line_bresenham",
                        "x0": 10, "y0": 28, "x1": 48, "y1": 12})
expect({s.values.get("算法") for s in lsteps} == {"DDA", "Bresenham"}
       and {s.values.get("inset") for s in lsteps} == {0, 5}
       and len(lsteps) > 50, f"自选对比·直线 {len(lsteps)} 步双色双层")
# 圆：中点 vs DDA 采样
csteps = gd.make_steps({"shape": "circle", "a": "circle_mid", "b": "circle_dda",
                        "cx": 30, "cy": 20, "r": 9})
expect({s.values.get("算法") for s in csteps} == {"中点圆", "DDA 圆（采样）"},
       "自选对比·圆 双算法")
# 相同算法 → 无输出
expect(gd.make_steps({"shape": "circle", "a": "circle_mid", "b": "circle_mid",
                      "cx": 30, "cy": 20, "r": 9}) == [], "相同算法提示无输出")
# 填充对比：没有用户选定的封闭图形 → 不生成（不再回落内置示例多边形）
expect(gd.make_steps({"shape": "fill", "a": "scanline", "b": "seed4"}) == [],
       "填充对比无选定对象 → 无输出（不回落实例多边形）")
# 填充对比分阶段：先完整播算法A，再叠加算法B（阶段切换至多 1 次）
from core.shapes import PolygonShape as _PSyn, KIND_POLYGON as _KP
gd._fill_shape = _PSyn(kind=_KP,
                       vertices=[(20, 8), (42, 8), (42, 22), (20, 22)])
_fcmp = gd.make_steps({"shape": "fill", "a": "scanline", "b": "seed4"})
_fseq = [s.values.get("算法") for s in _fcmp]
_fswitch = sum(1 for i in range(1, len(_fseq)) if _fseq[i] != _fseq[i - 1])
expect(len(_fseq) > 4 and _fswitch <= 1
       and _fseq[0] == "扫描线" and _fseq[-1] == "种子·4联通",
       f"填充对比分阶段播放（{len(_fseq)} 步，阶段切换 {_fswitch} 次）")
expect(any("波前" in s.values for s in _fcmp),
       "种子对比按波前扩散步骤播放（不是被摊平成扫描线）")
expect({s.values.get("inset") for s in _fcmp} == {0, 5}
       and {s.values.get("color") for s in _fcmp}
       == {"#3E63DD", "#F76B15"},
       "填充对比双色双层（A 满格蓝 / B 内缩橙）")
gd._fill_shape = None
from algorithms.circle_dda import dda_circle
from algorithms.circle_midpoint import midpoint_circle
expect(len(dda_circle(0, 0, 20)) > 40 and len(midpoint_circle(0, 0, 20)) > 40,
       "两种圆算法均有输出")
# DDA 圆封闭性：8-连通 BFS 应走完整个轮廓（连通分量=1）
from collections import deque as _dq
for rr in (9, 20, 45):
    px = set(dda_circle(0, 0, rr))
    start = next(iter(px))
    seen = {start}
    q = _dq([start])
    while q:
        x, y = q.popleft()
        for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1),
                       (x+1, y+1), (x+1, y-1), (x-1, y+1), (x-1, y-1)):
            if (nx, ny) in px and (nx, ny) not in seen:
                seen.add((nx, ny)); q.append((nx, ny))
    expect(seen == px, f"DDA 圆 r={rr} 轮廓封闭（8-连通连通分量=1）")

# 7.3 模式独立：双画布互不干扰
n_app = len(win._app_canvas.shapes)
win._on_mode_changed(1)
app.processEvents()
expect(win.body_stack.currentIndex() == 1, "切到演示模式")
expect(len(demo_view.canvas.shapes) == 0, "演示画布初始空白（独立画布）")
expect(len(win._app_canvas.shapes) == n_app, "应用画布图元原样保留（互不干扰）")
expect(not demo_view.player.is_playing, "进入演示不自动播放（无预画内容）")

# 7.3a 模块一（颜色模型）：无画板交互页，舞台切换 / 播放禁用 / 画布页还原
from modules.module01_color.demos import RgbCubePage, HsvConePage, ConvertPage
wpages = [d for d in demo_view._all_pages
          if getattr(d, "kind", "canvas") == "widget"]
expect(len(wpages) == 3, f"模块一交互页 {len(wpages)} 个（应为 3）")
first = demo_view.current_demo
expect(getattr(first, "kind", "canvas") == "widget"
       and demo_view._stage.currentIndex() == 1,
       "默认第一页 = 模块一交互页（舞台显示页面控件）")
demo_view._on_page_button(wpages[2], demo_view._page_buttons[wpages[2]])
app.processEvents()
host_w = (demo_view._page_host_lay.itemAt(0).widget()
          if demo_view._page_host_lay.count() else None)
expect(isinstance(host_w, ConvertPage), "转换推导页装载到舞台")
expect(not demo_view._play_btns[2].isEnabled()
       and not demo_view.speed_slider.isEnabled(),
       "无画板页播放控制/速度整体禁用")
expect(not demo_view.card_params.isVisible()
       and not demo_view.card_monitor.isVisible()
       and not demo_view.card_play.isVisible()
       and demo_view.card_concept.isVisible(),
       "无画板页面板独立：参数/监视/播放隐藏，概念说明显示")
expect("归一化" in demo_view.concept_label.text()
       and "line-height" in demo_view.concept_label.text(),
       "概念说明卡内容来自页面的 variables（富文本行距）")
gd_page = next(d for d in demo_view._all_pages if isinstance(d, CircleDemo))
demo_view._on_page_button(gd_page, demo_view._page_buttons[gd_page])
app.processEvents()
expect(demo_view._stage.currentIndex() == 0, "切回画布页：舞台恢复画布")

# 7.3c 零动画原则：点击演示页不生成不播放；点播放 = 按当前参数生成并播
expect(len(demo_view.player.steps) == 0 and not demo_view.player.is_playing,
       "点击演示页零动画（装载参数卡，不生成不播放）")
demo_view.play_pause(); app.processEvents()
expect(len(demo_view.player.steps) > 0 and demo_view.player.is_playing,
       "点播放 → 按当前参数生成并播放（用户主动）")
demo_view.player.pause()
# 直线页算法下拉：切换 → 公式卡/步骤跟随
line_page = next(d for d in demo_view._all_pages if isinstance(d, LineDemo))
demo_view._on_page_button(line_page, demo_view._page_buttons[line_page])
app.processEvents()
expect(demo_view.canvas.tool is not None,
       "直线页联动画布工具（PAGE_TOOL 键名回归：手绘可用）")
_ld = demo_view.current_demo
expect(_ld.algo == "dda" and "DDA" in demo_view.formula_label.text(),
       "直线页默认 DDA（公式跟随）")
_ld._combo.setCurrentIndex(1)
demo_view._regenerate(); app.processEvents()
expect(_ld.algo == "bresenham"
       and "Bresenham" in demo_view.formula_label.text()
       and len(demo_view.player.steps) > 0,
       "直线页算法下拉切 Bresenham → 公式/步骤跟随")
# 圆页算法下拉：选 DDA 圆 → 手绘圆按 DDA 角度采样回放（非中点 8 对称）
circle_page = next(d for d in demo_view._all_pages if isinstance(d, CircleDemo))
demo_view._on_page_button(circle_page, demo_view._page_buttons[circle_page])
app.processEvents()
_cd = demo_view.current_demo
_cd._combo.setCurrentIndex(1)          # DDA 圆（角度采样）
demo_view._regenerate(); app.processEvents()
_ctc = demo_view.canvas.tool           # 页面联动后的圆工具
_ctc.on_press(QPointF(40, 20)); _ctc.on_release(QPointF(52, 20))
app.processEvents()
_circ = [s for s in demo_view.canvas.shapes if isinstance(s, CircleShape)][-1]
from algorithms.circle_dda import dda_circle_steps as _dcs
expect(_circ.kind == "circle_dda"
       and len(demo_view.player.steps) == len(_dcs(40, 20, 12)),
       "圆页选 DDA → 手绘圆按 DDA 角度采样回放（非中点 8 对称）")
demo_view.canvas.clear_all(); app.processEvents()   # 清测试圆，恢复空画布

# 7.3b 模块一：颜色换算回归 + 3D 视角拖拽
from modules.module01_color.demos import rgb_to_hsv, hsv_to_rgb
_ok = True
for _rgb, _hsv in ((((255, 0, 0)), (0, 100, 100)), ((0, 255, 0), (120, 100, 100)),
                   ((0, 0, 255), (240, 100, 100)), ((255, 255, 0), (60, 100, 100)),
                   ((0, 255, 255), (180, 100, 100)), ((255, 0, 255), (300, 100, 100)),
                   ((0, 0, 0), (0, 0, 0)), ((255, 255, 255), (0, 0, 100))):
    _got = rgb_to_hsv(*_rgb)
    if any(abs(a - b) > 0.6 for a, b in zip(_got, _hsv)):
        _ok = False
expect(_ok, "rgb_to_hsv：三原色/三补色/黑白 两端点全对")
_ok = all(tuple(hsv_to_rgb(*rgb_to_hsv(*c))) == tuple(c)
          for c in ((79, 110, 247), (220, 60, 80), (12, 200, 130), (1, 2, 3)))
expect(_ok, "HSV⇄RGB 往返一致（含极暗色）")
from modules.module01_color.demos import rgb_to_cmy
_ok = (tuple(round(v) for v in rgb_to_cmy(255, 0, 0)) == (0, 100, 100)
       and tuple(round(v) for v in rgb_to_cmy(255, 255, 255)) == (0, 0, 0)
       and tuple(round(v) for v in rgb_to_cmy(0, 0, 0)) == (100, 100, 100)
       and tuple(round(v) for v in rgb_to_cmy(64, 64, 64)) == (75, 75, 75))
expect(_ok, "rgb_to_cmy：红/白/黑/灰 互补量全对")
demo_view._on_page_button(wpages[0], demo_view._page_buttons[wpages[0]])
app.processEvents()
_cube_pg = demo_view._page_host_lay.itemAt(0).widget()
from modules.module01_color.demos import _PlaneView, _TopViewHex, _SVSection
expect(len(_cube_pg.findChildren(_PlaneView)) == 3,
       "RGB 立方体页含三视图 3 张")
_cmy0 = _cube_pg.cmy_lab.text()
_cube_pg._rows[0].slider.setValue(200)
app.processEvents()
expect("CMY" in _cmy0 and _cube_pg.cmy_lab.text() != _cmy0,
       "CMY 读数随滑杆联动更新")
# 灰色：C/M/Y 必须严格等于 RGB 互补量（64 → 75）
_cube_pg._rows[0].slider.setValue(64)
_cube_pg._rows[1].slider.setValue(64)
_cube_pg._rows[2].slider.setValue(64)
app.processEvents()
expect([r.slider.value() for r in _cube_pg._cmy_rows] == [75, 75, 75],
       "RGB 灰 64 → CMY 互补量 75（不再有 K 干扰）")
# C/M/Y → RGB 反向：C=30 → R=178，读数与三根滑杆一致
_cube_pg._rows[0].slider.setValue(255)
_cube_pg._rows[1].slider.setValue(0)
_cube_pg._rows[2].slider.setValue(0)
app.processEvents()
_cube_pg._cmy_rows[0].slider.setValue(30)
app.processEvents()
expect(_cube_pg._rows[0].slider.value() == 178,
       "CMY→RGB 反向同步（C=30 → R=178）")
expect(_cube_pg.cmy_lab.text() == "CMY ("
       + ", ".join(f"{r.value()}%" for r in _cube_pg._cmy_rows) + ")",
       "CMY 读数与三根滑杆完全一致")
# RGB→CMY：青 (0,255,255) → C=100
_cube_pg._rows[0].slider.setValue(0)
_cube_pg._rows[1].slider.setValue(255)
_cube_pg._rows[2].slider.setValue(255)
app.processEvents()
expect(abs(_cube_pg._cmy_rows[0].slider.value() - 100) <= 1,
       f"RGB→CMY 滑杆同步（青 C={_cube_pg._cmy_rows[0].slider.value()}）")
_cube_pg._cmy_rows[0].slider.setValue(0)
app.processEvents()
expect(_cube_pg._rows[0].slider.value() == 255,
       "CMY→RGB 反向同步（C=0 → R 回 255）")
# 三视图可交互：在正视图中拾取 → R/G 两分量跟随
_front = _cube_pg._views[0]
_cube_pg._rows[0].slider.setValue(10)
_cube_pg._rows[1].slider.setValue(10)
_front._handle_pick(0.5, 0.5)
app.processEvents()
expect(abs(_cube_pg._rows[0].slider.value() - 128) <= 1
       and abs(_cube_pg._rows[1].slider.value() - 128) <= 1,
       "正视图点击拾取 → R/G 滑杆跟随（三视图可调）")
# HSV 俯视图拾取 → H/S 滑杆跟随（用控件自身几何构造 90° 拾取点）
demo_view._on_page_button(wpages[1], demo_view._page_buttons[wpages[1]])
app.processEvents()
_hex_pg = demo_view._page_host_lay.itemAt(0).widget()
import math as _math
_tv = _hex_pg.top_view
_c, _R = _tv._center_radius()
_t = _math.radians(90)
_tv._handle_pick(QPointF(_c.x() + _R * 0.8 * _math.cos(_t),
                         _c.y() - _R * 0.8 * _math.sin(_t)))
app.processEvents()
expect(_hex_pg._rows[0].slider.value() == 90,
       f"俯视图拾取 → H 滑杆跟随（H={_hex_pg._rows[0].slider.value()}）")
_hex_pg.sv_view._handle_pick(QPointF(
    _hex_pg.sv_view._geometry().x() + _hex_pg.sv_view._geometry().width() * 0.75,
    _hex_pg.sv_view._geometry().y() + _hex_pg.sv_view._geometry().height() * 0.3))
app.processEvents()
expect(abs(_hex_pg._rows[1].slider.value() - 60) <= 1,
       f"轴截面拾取 → S 滑杆跟随（S={_hex_pg._rows[1].slider.value()}）")
# 转换页：色相条点击 → H 推导联动
demo_view._on_page_button(wpages[2], demo_view._page_buttons[wpages[2]])
app.processEvents()
_cp = demo_view._page_host_lay.itemAt(0).widget()
_cp.hue_bar._handle_pick(QPointF(_cp.hue_bar.width() * 0.5, 10))
app.processEvents()
expect("180" in _cp.derive.text(),
       "色相条拾取 → H 推导联动（180°）")
demo_view._on_page_button(wpages[1], demo_view._page_buttons[wpages[1]])
app.processEvents()
_hex_pg = demo_view._page_host_lay.itemAt(0).widget()
expect(_hex_pg.findChild(_TopViewHex) is not None
       and _hex_pg.findChild(_SVSection) is not None,
       "HSV 页含俯视图 + 轴截面两张平面图")
demo_view._on_page_button(wpages[1], demo_view._page_buttons[wpages[1]])
app.processEvents()
from modules.module01_color.demos import _HexconeCanvas
_hex = demo_view._page_host_lay.itemAt(0).widget().findChild(_HexconeCanvas)
expect(_hex is not None, "六棱锥 3D 画布在页面内")
_yaw0, _pitch0 = _hex.yaw, _hex.pitch
def _me(t, x, y):
    return QMouseEvent(t, _QPF(x, y), _QPF(x, y), _Qt.LeftButton,
                       _Qt.NoButton, _Qt.NoModifier)
_hex.mousePressEvent(_me(_QEvent.MouseButtonPress, 300, 300))
_hex.mouseMoveEvent(_me(_QEvent.MouseMove, 380, 340))
_hex.mouseReleaseEvent(_me(_QEvent.MouseButtonRelease, 380, 340))
app.processEvents()
expect(_hex.yaw != _yaw0 and _hex.pitch != _pitch0,
       "六棱锥拖拽旋转视角生效")
_hex.mousePressEvent(_me(_QEvent.MouseButtonPress, 300, 300))
_hex.mouseMoveEvent(_me(_QEvent.MouseMove, 220, 260))
_hex.mouseReleaseEvent(_me(_QEvent.MouseButtonRelease, 220, 260))
app.processEvents()
expect(abs(_hex.yaw - _yaw0) < 0.2, "反方向拖回：视角还原（可逆）")
win._on_mode_changed(0)
app.processEvents()
expect(win.body_stack.currentIndex() == 0, "切回应用模式")
expect(len(win._app_canvas.shapes) == n_app, "切回应用模式：应用图元原样保留")
expect(len(demo_view.canvas.shapes) == 0, "演示画布内容独立保留")

# 7.4 播放器 + 像素层：装入 DDA 步骤流并推进一步
from algorithms.line_dda import dda_line_steps
steps = dda_line_steps(100, 100, 500, 400)
demo_view.canvas.demo.reset()
demo_view.player.load(steps)
demo_view.player.pause()
demo_view.player.step_forward()               # index 0
expect(demo_view.player.index == 0, "播放器单步前进到第 1 步")
expect(len(demo_view.canvas.demo._cur) == 1, "像素层当前步 1 个像素")
demo_view.player.step_forward()               # index 1（增量路径）
expect(len(demo_view.canvas.demo._done.get(list(demo_view.canvas.demo._done)[0], [])) == 1
       if demo_view.canvas.demo._done else False, "前一步沉淀为已完成像素")
demo_view.player.step_back()                  # 回退 → 整层重建
expect(demo_view.player.index == 0 and len(demo_view.canvas.demo._cur) == 1
       and not demo_view.canvas.demo._done, "回退后整层重建到第 1 步")

# 7.5 演示页生成：对比页每步带颜色标记（模拟像素坐标下 ~百步内）
from modules.module02_primitives.demos import CompareDemo, FillDemo


# 7.6 填充演示页：默认顶点生成整行步骤；三种填充算法均可出步骤
fd = FillDemo()
fsteps = fd.make_steps(fd.collect())
expect(len(fsteps) >= 10, f"填充演示 {len(fsteps)} 行步骤")
expect(all("y" in s.values for s in fsteps[:5]), "填充步骤带扫描线 y 状态")
fd.algo = "seed4"
fseed4 = fd.make_steps(fd.collect())
fd.algo = "seed8"
fseed8 = fd.make_steps(fd.collect())
expect(len(fseed4) > 0 and len(fseed8) > 0,
       f"种子填充演示（4联通 {len(fseed4)} 步 / 8联通 {len(fseed8)} 步）")
fd.algo = "scanline"

# 7.5a 填充⇄描边按钮：无选中 → 切换工具提交态；多边形提交跟随开关
win._app_canvas.set_selected_shape(None)   # 无选中前提（手柄缩放测试留下的选中）
win._activate_tool(3)
before = win.canvas.fill_mode
win.btn_fill.click()
expect(win.canvas.fill_mode != before, "无选中时填充按钮切换工具提交态")
win._activate_tool(6)
fp2 = win._tool_classes[3](win._app_canvas)
win._app_canvas.set_tool(fp2)
fp2.on_press(QPointF(500, 100)); fp2.on_press(QPointF(560, 110))
fp2.on_press(QPointF(540, 150)); fp2.on_right_click(QPointF(0, 0))
expect(win._app_canvas.shapes[-1].fill == win.canvas.fill_mode,
       "多边形提交跟随填充⇄描边开关")
win.btn_fill.click()                 # 恢复

# 7.5a-2 选中闭合图元的填充切换（回归：set_shape_fill 曾未定义 → 按钮无响应）
win._activate_tool(1)
_ct = win._tool_classes[1](win._app_canvas)
win._app_canvas.set_tool(_ct)
_ct.on_press(QPointF(700, 700)); _ct.on_release(QPointF(716, 700))
_circ = win._app_canvas.shapes[-1]
win._app_canvas.set_selected_shape(_circ)
app.processEvents()
_f0 = _circ.fill
win.btn_fill.click(); app.processEvents()
expect(_circ.fill != _f0, "选中圆点填充按钮 → 填充态翻转（含圆算法键）")
win._app_canvas.undo(); app.processEvents()
expect(_circ.fill == _f0, "选中图元填充切换可撤销")
win._app_canvas.set_selected_shape(None)

# 7.5a-3 圆工具激活时点填充（回归：圆工具漏声明 supports_fill → 按钮禁用）
win._activate_tool(1); app.processEvents()
expect(win.btn_fill.isEnabled(),
       "圆工具激活时填充按钮可用（supports_fill 已声明）")
_ct2 = win._tool_classes[1](win._app_canvas)
win._app_canvas.set_tool(_ct2)
_ct2.on_press(QPointF(900, 700)); _ct2.on_release(QPointF(920, 700))
_c2 = win._app_canvas.shapes[-1]
_m0 = win.canvas.fill_mode
win.btn_fill.click(); app.processEvents()
expect(win.canvas.fill_mode != _m0 and _c2.fill != _m0,
       "圆工具点填充 → 模式翻转 + 最近画的圆同步翻转")
win.btn_fill.click(); app.processEvents()   # 恢复模式与圆状态

# 7.5b 填充工具（4/8 联通）：斜缝菱形边界 → 4联通被对角缝隙挡住 / 8联通穿缝泄漏
_poly = tools[3]
canvas.set_tool(_poly)
canvas.fill_mode = False
canvas.clear_all()
for pt in [(31, 28), (33, 30), (31, 32), (29, 30)]:
    _poly.on_press(QPointF(*pt))
_poly.on_right_click(QPointF(0, 0))            # 菱形边界（四条对角边，8-连通环）
fill_tool = tools[7]
canvas.set_tool(fill_tool)
canvas.algorithm = "seed4"
fill_tool.on_press(QPointF(31, 30))            # 菱形内部种子
res4 = canvas.shapes[-1]
expect(res4.kind == "raster_fill", "四联通：提交光栅填充图元")
inside4 = all(29 <= x <= 33 and 28 <= y <= 32 for x, y in res4.pixels)
expect(inside4 and len(res4.pixels) > 0,
       f"四联通：8-连通环内被挡住不泄漏（{len(res4.pixels)} 像素）")
expect(len(res4.pixels) < 500, "泄漏被钳制在有限区域（不渲染全画布）")
canvas.undo()                              # 撤销四联通填充，还原空腔
canvas.algorithm = "seed8"
fill_tool.on_press(QPointF(31, 30))
res8 = canvas.shapes[-1]
expect(res8 is not res4 and res8.kind == "raster_fill", "八联通：重新提交光栅填充")
leaked8 = any(not (29 <= x <= 33 and 28 <= y <= 32) for x, y in res8.pixels)
expect(leaked8, f"八联通：经对角缝隙泄漏（填充 {len(res8.pixels)} 像素）")
canvas.fill_mode = True

# 7.5b2 油漆桶·扫描线填充：点中多边形内部 → 该多边形整体逐行填充
canvas.set_tool(tools[3])
for _vx, _vy in ((100, 100), (170, 100), (170, 150), (100, 150)):
    tools[3].on_press(QPointF(_vx, _vy))
tools[3].on_right_click(QPointF(0, 0))          # 闭合矩形多边形
_poly = canvas.shapes[-1]
canvas.set_tool(tools[7])                        # 油漆桶
canvas.algorithm = "scanline"
tools[7].on_press(QPointF(130, 120))
_scan = canvas.shapes[-1]
expect(_scan.kind == KIND_RASTER_FILL and len(_scan.pixels) > 500
       and (130, 120) in _scan.pixels,
       f"油漆桶扫描线填充：多边形整体 {len(_scan.pixels)} 像素（含种子）")
canvas.algorithm = "seed4"                       # 恢复默认算法

# 7.5c 橡皮擦双模式：整体删除 + 像素擦除
canvas.clear_all()
canvas.set_tool(tools[0])
tools[0].on_press(QPointF(100, 100))
tools[0].on_release(QPointF(300, 200))             # 一条测试直线
er = tools[6]
canvas.set_tool(er)
n_before = len(canvas.shapes)
target = canvas.shapes[0]
canvas.algorithm = "whole"
er.on_press(QPointF(target.p0[0] + 5, target.p0[1] + 2))   # 点中线
expect(len(canvas.shapes) == n_before - 1, "整体删除模式：点击删除命中图元")
canvas.undo()
expect(len(canvas.shapes) == n_before, "整体删除可撤销")
canvas.algorithm = "pixel"
target2 = canvas.shapes[0]
mid = target2.p0
er.on_press(QPointF(mid[0], mid[1]))
er.on_release(QPointF(mid[0], mid[1]))
expect(mid in target2.erased, "像素擦除：掩码记录")
from core.rasterizer import rasterize as _rz2
expect(mid not in set(_rz2(target2)[0]), "被擦像素不再输出")
canvas.undo()
expect(mid not in target2.erased, "像素擦除可撤销")

# 7.6b 选择/移动工具：点选 + 拖拽移动 + 列表联动
sel_tool = tools[5]
canvas.set_tool(sel_tool)
canvas.clear_all()
canvas.set_tool(tools[0])
tools[0].on_press(QPointF(100, 100))
tools[0].on_release(QPointF(300, 200))     # 一条线 (5,5)-(15,10)
canvas.set_tool(sel_tool)
sel_tool.on_press(QPointF(200, 150))      # 第一次按下：选中
sel_tool.on_release(QPointF(200, 150))
expect(canvas._selected_shape is canvas.shapes[0], "选择工具点选命中图元")
sel_tool.on_press(QPointF(200, 150))      # 第二次按下（已选中）→ 进入移动
sel_tool.on_move(QPointF(220, 170))
sel_tool.on_move(QPointF(260, 190))
sel_tool.on_release(QPointF(260, 190))
expect(canvas.shapes[0].p0 == (160, 140),
       f"拖拽移动提交（p0={canvas.shapes[0].p0}，原 (100,100)+位移(60,40)）")
expect(canvas.document.can_undo, "移动入撤销栈")
sel_tool.on_press(QPointF(1000, 700))     # 空白处
expect(canvas._selected_shape is None, "空白点击取消选中")

# 7.7 可增长画布：向负方向绘制 → 纸自动扩张
tools[0].on_press(QPointF(-90, -60))
tools[0].on_move(QPointF(-40, -20))
tools[0].on_release(QPointF(-40, -20))
expect(canvas.base_image.width() > 1200, "向负方向绘制 → 纸面自动扩展")
expect(canvas.pix_item.pos().x() < 0, "base 位图原点随扩展移动")
expect(canvas._shape_bbox(canvas.shapes[-1])[0] < 0, "负坐标图元包围盒正确")
canvas.clear_all()
expect(canvas.base_image.width() == 1200 and canvas.pix_item.pos().x() == 0,
       "清空后纸面复位到锚定 60×40")

# 7.8 画布拾取回放：演示模式下手动划线 → 自动步骤动画
win._on_mode_changed(1)
app.processEvents()
demo_view.player.pause()
win.canvas.add_shape(LineShape(kind=KIND_LINE_DDA, color=QColor("#111111"),
                               p0=(10, 10), p1=(45, 28)))
expect(len(demo_view.player.steps) > 0, "演示模式手动划线 → 自动装入步骤流")
cd = demo_view.current_demo
from modules.module02_primitives.demos import LineDemo
expect(isinstance(cd, LineDemo), "自动切到直线演示页")
expect([cd._spins[k].value() for k in ("x0", "y0", "x1", "y1")] == [10, 10, 45, 28],
       "首尾值读回参数卡 (10,10)-(45,28)")
from PySide6.QtCore import QElapsedTimer
tm = QElapsedTimer()
tm.start()
while tm.elapsed() < 600:
    app.processEvents()
demo_view.player.pause()
expect(demo_view.player.index >= 0, "回放正在步进")
# 对比工具提交的两条线也能回放（双色交错）
win.canvas.add_shapes([LineShape(kind="line_dda", color=QColor("#F76B15"),
                                 p0=(5, 5), p1=(30, 20)),
                       LineShape(kind="line_bresenham", color=QColor("#3E63DD"),
                                 p0=(5, 5), p1=(30, 20))])
expect({s.values.get("算法") for s in demo_view.player.steps} == {"DDA", "Bresenham"},
       "对比工具的图元对回放为双色交错步骤流")

# 7.9 演示画布描边化 + 多边形/填充页分离
expect(demo_view.canvas.fill_mode is False, "演示画布手绘图元一律描边")
from modules.module02_primitives.tools import FillTool
from modules.module02_primitives.demos import PolygonDemo
cvf = demo_view.canvas
def _me2(t, x, y, btn=_Qt.LeftButton):
    return QMouseEvent(t, QPointF(x, y), QPointF(x, y), btn,
                       _Qt.NoButton, _Qt.NoModifier)

# ---- 多边形页：自由画边界（描边），闭合 → 逐边回放 ----
poly_page = next(d for d in demo_view._all_pages if isinstance(d, PolygonDemo))
demo_view._on_page_button(poly_page, demo_view._page_buttons[poly_page])
app.processEvents()
expect(isinstance(demo_view.canvas.tool, PolygonTool),
       "多边形页 → 多边形工具（描边自由画）")
for _sx, _sy in ((300, 500), (500, 500), (500, 650), (300, 650)):
    _v = cvf.mapFromScene(QPointF(_sx, _sy))
    cvf.mousePressEvent(_me2(_QEvent.MouseButtonPress, _v.x(), _v.y()))
    cvf.mouseReleaseEvent(_me2(_QEvent.MouseButtonRelease, _v.x(), _v.y()))
_vr = cvf.mapFromScene(QPointF(0, 0))
cvf.mousePressEvent(_me2(_QEvent.MouseButtonPress, _vr.x(), _vr.y(),
                         _Qt.RightButton))
cvf.mouseReleaseEvent(_me2(_QEvent.MouseButtonRelease, _vr.x(), _vr.y(),
                           _Qt.RightButton))
app.processEvents()
from core.shapes import RasterFillShape as _RFS, PolygonShape as _PS
_poly = [s for s in cvf.shapes if isinstance(s, _PS)][-1]
expect(len(_poly.vertices) == 4 and not _poly.fill,
       "多边形闭合提交（描边，不自动填充）")
expect(len(demo_view.player.steps) > 0, "多边形手绘 → 逐边生成回放")

# ---- 填充页：油漆桶点内部（算法随下拉）----
fill_page = next(d for d in demo_view._all_pages if isinstance(d, FillDemo))
demo_view._on_page_button(fill_page, demo_view._page_buttons[fill_page])
app.processEvents()
expect(isinstance(demo_view.canvas.tool, FillTool),
       "填充页 → 油漆桶（在已画边界上点内部填充）")
_vi = cvf.mapFromScene(QPointF(400, 560))
cvf.mousePressEvent(_me2(_QEvent.MouseButtonPress, _vi.x(), _vi.y()))
cvf.mouseReleaseEvent(_me2(_QEvent.MouseButtonRelease, _vi.x(), _vi.y()))
app.processEvents()
_fshapes = [s for s in cvf.shapes if isinstance(s, _RFS)]
expect(_fshapes and 40 <= len(_fshapes[-1].pixels) <= 120
       and (400 // 20, 560 // 20) in _fshapes[-1].pixels,
       f"油漆桶点内部 → 填充图元（{len(_fshapes[-1].pixels) if _fshapes else 0} 像素，含种子）")
expect(len(demo_view.player.steps) > 0, "填充过程按扩散顺序自动回放")

# ---- 回归：重播前先撤销上次填充（重播 = 还原 → 从零再演示）----
_fsh = _fshapes[-1]
demo_view.player.to_end()
demo_view._on_replay_finished()        # 播完：图元恢复显示（保留结果语义）
app.processEvents()
expect(_fsh.visible, "填充回放播完：结果保留可见")
demo_view.replay()                     # 重播按钮路径
app.processEvents()
expect(not _fsh.visible and demo_view._had_hidden,
       "重播：先撤销上次填充（来源图元重新隐藏，从零重放）")
demo_view.player.pause()
demo_view._on_replay_finished()
expect(_fsh.visible, "重播播完：结果再次保留可见")
demo_view.play_pause()                 # 播完再按播放 = 从头播放
app.processEvents()
expect(not _fsh.visible and demo_view.player.is_playing,
       "播完按播放：同样先撤销最终画面再从头重放")
demo_view.player.pause()
demo_view._on_replay_finished()

# ---- 回归：对比页手绘圆 → 立即自动播放双色对比（此前停在"待播"，像"没有对比"）----
demo_view._on_page_button(gd, demo_view._page_buttons[gd])
gd._on_shape_changed(1)                # 形状=圆（算法 A=中点圆 / B=DDA 采样）
demo_view._sync_tool(gd)
app.processEvents()
from modules.module02_primitives.tools import CircleTool as _CT2
expect(isinstance(demo_view.canvas.tool, _CT2), "对比页选圆 → 圆工具")
_ct2 = demo_view.canvas.tool
_ct2.on_press(QPointF(29, 7)); _ct2.on_release(QPointF(38, 7))
app.processEvents()
expect(gd._shape_key == "circle" and gd._spins["cx"].value() == 29
       and gd._spins["r"].value() == 9, "手绘圆坐标读回对比参数")
expect(len(demo_view.player.steps) > 0 and demo_view.player.is_playing,
       f"对比页手绘圆 → 双色对比自动回放（{len(demo_view.player.steps)} 步）")
expect(demo_view.progress_label.wordWrap(), "进度提示自动换行（不溢出边框）")
# ---- 圆对比 = 双算法实色图元对（常驻画布，像直线对比对一样不变黑）----
from core.shapes import CircleShape as _CS2
def _cname(s):
    c = s.color
    return (c.name() if hasattr(c, "name") else str(c)).upper()
_pairs = [s for s in cvf.shapes if isinstance(s, _RFS)
          and _cname(s) in ("#3E63DD", "#F76B15")]
_cmpA = next(s for s in _pairs if _cname(s) == "#3E63DD")
_cmpB = next(s for s in _pairs if _cname(s) == "#F76B15")
expect(_cmpB.owner is _cmpA and not _cmpA.visible and not _cmpB.visible
       and len(_cmpA.pixels) > 30 and len(_cmpB.pixels) > 30,
       "对比圆提交为双算法实色图元对（成组、回放中隐藏）")
expect(all(not (isinstance(s, _CS2) and s.center == (29, 7))
           for s in cvf.shapes), "黑色原圆已被图元对替换（不残留）")
demo_view.player.to_end()
demo_view._on_replay_finished()
expect(_cmpA.visible and demo_view.canvas.demo._solid
       and bool(demo_view.canvas.demo._done),
       "对比回放播完：图元对恢复，结果定格为不透明实色叠层")
demo_view.replay()
app.processEvents()
expect(not _cmpA.visible, "对比重播：再次收起、从零重放")
demo_view.player.pause()
demo_view._on_replay_finished()

# ---- 填充对比：先画边界 → 点击内部选定对象 → 双色对比（无示例回落）----
from modules.module02_primitives.tools import PolygonTool as _PT2
from core.shapes import PolygonShape as _PS2
demo_view.player.pause()
demo_view.player.load([])                      # 清掉上一轮对比步骤
demo_view.canvas.set_tool(_PT2(demo_view.canvas))
_pt2 = demo_view.canvas.tool
for _pt in ((20, 5), (40, 5), (40, 15), (20, 15)):
    _pt2.on_press(QPointF(*_pt))
_pt2.on_right_click(QPointF(0, 0))             # 闭合多边形
app.processEvents()
_poly_cmp = [s for s in cvf.shapes if isinstance(s, _PS2)][-1]
expect(gd._fill_shape is None and gd._shape_key == "fill"
       and not demo_view.player.is_playing
       and type(demo_view.canvas.tool).__name__ == "FillTool",
       "对比页画多边形 → 等待点击内部选定对象（不自动播放）")
# 算法下拉真正生效：B 可切到种子·8（不再固定播默认那一对）
gd.combo_b.setCurrentIndex(2)
app.processEvents()
expect(gd._algo_b == "seed8", "算法 B 下拉切到种子·8 已写回状态")
gd.combo_b.setCurrentIndex(1)                  # 换回种子·4 继续后续断言
app.processEvents()
# 没有选定对象时点播放：零生成，绝不出现内置示例
demo_view.play_pause()
app.processEvents()
expect(not demo_view.player.steps, "填充对比无选定对象点播放 → 零生成（不出示例）")
# 点击内部：油漆桶填充 → 登记该多边形 → 自动双色对比回放
_fill_tool = demo_view.canvas.tool
_fill_tool.on_press(QPointF(30, 10))
app.processEvents()
expect(gd._fill_shape is _poly_cmp and demo_view.player.is_playing,
       "点击内部选定我画的多边形 → 自动双色对比回放")
expect(_poly_cmp.visible, "填充对比回放期间黑色边界保持可见（不再消失）")
_cmp_xs = [px[0] for st in demo_view.player.steps for px in st.pixels]
expect(_cmp_xs and min(_cmp_xs) >= 18 and max(_cmp_xs) <= 42,
       f"填充对比像素落在手绘多边形范围（x {min(_cmp_xs)}~{max(_cmp_xs)}）")
from core.rasterizer import rasterize as _rz2
_cmp_outline = set(_rz2(_poly_cmp)[0])
_cmp_all = {px for st in demo_view.player.steps for px in st.pixels}
expect(not (_cmp_all & _cmp_outline),
       "填充对比不覆盖边界像素（黑色边界保持可见）")
expect(any("波前" in st.values for st in demo_view.player.steps),
       "种子算法按波前扩散回放（与扫描线过程不同）")
demo_view.player.pause()
demo_view.to_end()
app.processEvents()
_done_colors = {c for (c, _ins) in demo_view.canvas.demo._done}
expect(_done_colors == {"#3E63DD", "#F76B15"},
       f"最终画面同时保留两种算法颜色（{sorted(_done_colors)}）")
demo_view._on_replay_finished()

# ---- 选择图元按钮 + 选中即操控（普通圆页：黑色圆的选中/重播/移动回放）----
_cd_page = next(d for d in demo_view._all_pages if isinstance(d, CircleDemo))
demo_view._on_page_button(_cd_page, demo_view._page_buttons[_cd_page])
app.processEvents()
_ct5 = demo_view.canvas.tool       # 圆页联动圆工具
_ct5.on_press(QPointF(50, 20)); _ct5.on_release(QPointF(59, 20))  # 普通圆
app.processEvents()
_plain = [s for s in cvf.shapes if isinstance(s, _CS2)][-1]
demo_view.player.pause()
demo_view._on_replay_finished()    # 手画即回放播完：圆恢复显示再选择
demo_view.btn_select.click()
app.processEvents()
from modules.module02_primitives.tools import SelectMoveTool as _SMT
expect(isinstance(demo_view.canvas.tool, _SMT), "选择图元按钮 → 选择/移动工具")
demo_view.canvas.tool.on_press(QPointF(59, 20))   # 点轮廓选中
expect(demo_view.canvas._selected_shape is _plain,
       "选择工具点击圆 → 图元选中（可拖动/微调）")
demo_view.replay()   # 选中即操控：重播演示选中对象
app.processEvents()
expect(demo_view.player.steps and not _plain.visible
       and demo_view.player.is_playing,
       "选中圆后重播：按选中圆从零回放（图元收起）")
demo_view.player.pause()
demo_view._on_replay_finished()
demo_view.canvas.begin_move(QPointF(59, 20))
demo_view.canvas.update_move(QPointF(65, 26))    # 拖 6 格
demo_view.canvas.end_move()
app.processEvents()
expect(getattr(_plain, "center", (0, 0)) == (56, 26),
       f"拖动选中圆到新位置（中心 {getattr(_plain, 'center', '?')}）")
demo_view.replay()
app.processEvents()
expect(demo_view.current_demo is _cd_page
       and _cd_page._spins["cx"].value() == 56
       and _cd_page._spins["cy"].value() == 26
       and not _plain.visible and demo_view.player.is_playing,
       "移动选中圆后重播：按新几何回放（参数同步 56,26）")
demo_view.player.pause()
demo_view._on_replay_finished()
demo_view._clear_demo_canvas()

# ---- 回归：填充与边界整体联动（移动随动/整体删除/一步撤销）----
from modules.module02_primitives.tools import CircleTool as _CT4, \
    FillTool as _FT4
_ac = win._app_canvas          # 应用模式画布（演示画布提交会触发回放隐藏）
_ac.set_tool(_CT4(_ac))
_ac.tool.on_press(QPointF(400, 300)); _ac.tool.on_release(QPointF(409, 300))
_gc_circle = _ac.shapes[-1]
_ac.set_algorithm("seed4")
_ac.set_tool(_FT4(_ac))
_ac.tool.on_press(QPointF(400, 300))
app.processEvents()
_gc = [s for s in _ac.shapes if isinstance(s, _RFS)][-1]
expect(_gc.owner is _gc_circle, "油漆桶填充归属边界图元（整体联动）")
_gp0 = sorted(_gc.pixels)
_ac.set_selected_shape(_gc_circle)
_ac.begin_move(QPointF(409, 300))
_ac.update_move(QPointF(412, 303))
_ac.end_move()
app.processEvents()
expect(sorted(_gc.pixels) == [(x + 3, y + 3) for x, y in _gp0]
       and _gc_circle.center == (403, 303),
       "移动边界 → 填充整体随动（同增量）")
_ac.undo()
expect(sorted(_gc.pixels) == _gp0 and _gc_circle.center == (400, 300),
       "撤销一步：边界与填充一起还原")
_ac.remove_shape(_gc_circle)
expect(all(s is not _gc and s is not _gc_circle for s in _ac.shapes),
       "删除边界 → 填充整体同删")
_ac.undo()
expect(any(s is _gc for s in _ac.shapes)
       and any(s is _gc_circle for s in _ac.shapes),
       "撤销删除 → 边界与填充一并恢复")
_ac.remove_shape(_gc_circle)       # 清理（填充随边界一起离场）

# 2b. 选色对话框：HEX 三段交互 + 颜色表联动
from ui.color_dialog import ColorDialog
dlg = ColorDialog(QColor("#FF0000"))
dlg.show(); app.processEvents()
expect(dlg.hex_edit.text() == "#FF0000", "对话框 HEX 初始显示")
dlg.hex_edit._enter_edit()
expect(not dlg.hex_edit.isReadOnly(), "双击后进入可编辑")
dlg.hex_edit.setText("#00FF00")
from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import QEvent, Qt as Qt4
dlg.hex_edit.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt4.Key_Return,
                                     Qt4.NoModifier))
expect(dlg._g == 255 and dlg._r == 0, "回车应用 → 跳转到 #00FF00")
expect(dlg.hex_edit.isReadOnly(), "应用后回到只读展示")
dlg.hex_edit._enter_edit()
dlg.hex_edit.setText("XYZ")
dlg.hex_edit._exit_edit(apply=True)
expect(dlg.hex_edit.text() == "#00FF00", "非法输入自动还原")
dlg.close()

from ui.widgets import CollapsibleCard
cards = win.findChildren(CollapsibleCard)
expect(len(cards) >= 6, f"可折叠信息卡 {len(cards)} 张（应用 3 + 演示 4）")
secs = win._app_page.findChildren(CollapsibleCard)
shape_secs = [c for c in secs if c.header.text() == "图元"]
in_card = [w for sec in shape_secs for w in sec.findChildren(QToolButton)
           if w.toolTip() and "清空" in w.toolTip()]
expect(len(in_card) == 1, "图元卡标题行有一键清空按钮")
expect(not [c for c in cards if c.findChildren(CollapsibleCard)],
       "折叠卡无嵌套（右栏三层套娃 bug 修复）")
hidden_before = cards[0].body.isHidden()
cards[0].toggle()
expect(cards[0].body.isHidden() != hidden_before, "点击标题收缩/展开生效")
cards[0].toggle()

win.grab().save(os.path.join(OUT, "smoke_ui_demo.png"))
win.close()

print("=" * 50)
if errors:
    print(f"烟测 FAIL ✗：{len(errors)} 项未通过")
    sys.exit(1)
print("烟测 PASS ✓ —— 全部检查项通过")
