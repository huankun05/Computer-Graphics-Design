# -*- coding: utf-8 -*-
"""
=====================================================================
 ui/demo_view.py  —  演示模式页（左：模块目录 | 中：画布 | 右：教学面板）
=====================================================================
组装规范 3.2 的演示模式布局。通用壳只依赖两个契约：
  契约① list[Step]（算法步骤流）→ 播放器 / 监视器 / 像素层
  契约② DemoSpec（模块演示页声明）→ 参数卡 / 公式 / 变量说明
工作流：
  选页 → 重建参数卡 → 收集参数生成步骤流 → 装入播放器 →
  自动适配画布到生成范围 → 自动播放；改参数即重新生成重放。
=====================================================================
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QFrame, QSlider, QToolButton, QSpinBox, QLineEdit, QPushButton,
    QScrollArea, QComboBox,
)

import html as _html

from core.registry import all_modules
from teaching.player import DemoPlayer
from teaching.monitor import MonitorPanel
from ui import theme
from ui.icons import icon


def _rich_text(text: str, line_height: str = "160%") -> str:
    """纯文本 → 带行距的富文本（QLabel 的 PlainText 无法设行距）。"""
    body = _html.escape(text).replace("\n", "<br>")
    return f"<div style='line-height:{line_height}'>{body}</div>"


def _raster_fill_steps(shape):
    """油漆桶填充图元 → 回放步骤流（顺序随来源算法）：

    · 扫描线填充：逐行扫描顺序（y 递增、行内 x 递增、连续段合并）；
    · 种子填充（4/8 联通）：从种子向外的 BFS 波前扩散顺序，
      每步 = 距种子一整圈波前（4联通菱形 / 8联通方形）。
    """
    from algorithms.steps import Step
    px_set = set(shape.pixels)
    algo = getattr(shape, "algo", "seed4")
    if algo == "scanline":
        rows = {}
        for x, y in shape.pixels:
            rows.setdefault(y, []).append(x)
        steps = []
        for y in sorted(rows):
            xs = sorted(rows[y])
            run = [xs[0]]
            for x in xs[1:]:
                if x == run[-1] + 1:
                    run.append(x)
                else:
                    steps.append(Step([(px, y) for px in run],
                                      {"y": y, "阶段": "内部填充"}, None))
                    run = [x]
            steps.append(Step([(px, y) for px in run],
                              {"y": y, "阶段": "内部填充"}, None))
        return steps
    # ---- 种子填充：BFS 波前扩散 ----
    seed = getattr(shape, "seed", None)
    if seed not in px_set:
        seed = next(iter(px_set))
    conn = getattr(shape, "conn", 4)
    nbrs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if conn == 8:
        nbrs += [(-1, -1), (1, -1), (-1, 1), (1, 1)]
    seen = {seed}
    wave = [seed]
    steps = []
    d = 0
    while wave:
        steps.append(Step(sorted(wave),
                          {"波前": d, "新增像素": len(wave),
                           "阶段": "内部填充"}, None))
        nxt = []
        for (x, y) in wave:
            for dx, dy in nbrs:
                p = (x + dx, y + dy)
                if p in px_set and p not in seen:
                    seen.add(p)
                    nxt.append(p)
        wave = nxt
        d += 1
    return steps
from ui.widgets import Card, CollapsibleCard, h_divider
from modules.module02_primitives.demos import (
    LineDemo, CircleDemo, EllipseDemo, PolygonDemo, FillDemo, CompareDemo,
    steps_for_shape, fill_steps_for_shape,
)
from modules.module02_primitives.tools import (
    LineTool, CircleTool, EllipseTool, PolygonTool, CompareLineTool,
    FillTool,
)
from algorithms.steps import Step
from algorithms.steps import Step
from core.shapes import (
    LineShape, CircleShape, EllipseShape, PolygonShape,
    KIND_LINE_DDA, KIND_LINE_BRESENHAM, SIM,
)


class DemoView(QWidget):
    """演示模式整页。画布由主窗口在模式切换时移入 canvas_slot。"""

    # 演示页 → 绘制工具映射：点选演示页 = 同时选中对应的绘制方式
    # （页内算法下拉的算法同步到画布工具，见 _sync_tool）
    PAGE_TOOL = {
        "LineDemo":       ("line", "line_dda"),
        "CircleDemo":     ("circle", "circle_mid"),
        "EllipseDemo":    ("ellipse", None),
        "PolygonDemo":    ("polygon", None),   # 多边形演示页 → 多边形描边绘制
        "FillDemo":       ("fill", None),      # 填充演示页 → 油漆桶（点内部填充）
        "CompareDemo":    ("compare", None),
    }
    # 演示页 (类名, kind) → 画布算法键（页内下拉切换后联动画布工具算法）。
    # 注意按页类名分键：直线页的 "dda" 与圆页的 "dda" 含义不同
    KIND_TO_ALGO = {("LineDemo", "dda"): "line_dda",
                    ("LineDemo", "bresenham"): "line_bresenham",
                    ("CircleDemo", "mid"): "circle_mid",
                    ("CircleDemo", "dda"): "circle_dda",
                    ("FillDemo", "scanline"): "scanline",
                    ("FillDemo", "seed4"): "seed4",
                    ("FillDemo", "seed8"): "seed8"}

    def __init__(self, parent=None):
        super().__init__(parent)
        # 演示模式独立画布（与应用模式互不干扰）
        from core.canvas_view import CanvasView
        self.canvas = CanvasView()
        # 演示画布手绘图元一律描边：算法演示只看轮廓像素，
        # 实心填充会把要演示的算法像素盖住（填充是独立的操作）
        self.canvas.fill_mode = False
        # 演示模式无法换颜色：填充固定用主题蓝，与黑色边界明显区分
        self.canvas.fill_color = theme.ACCENT
        self.player = DemoPlayer(self)
        self.current_demo = None
        self._replay_shapes = []      # 正在"从无到有"回放的图元（回放中隐藏）
        self._replay_source = []      # 当前步骤流的来源图元（重放前重新隐藏）
        self._keep_overlay_at_finish = False   # 对比页：播完保留双色结果叠层
        self._had_hidden = False
        self._applied_index = -2      # 叠层已应用到的步（-2 = 未应用）
        self._all_pages = []          # [DemoSpec]

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 6)
        root.setSpacing(10)

        # ---- 左：课程模块目录（演示模式的唯一左侧面板） ----
        root.addWidget(self._build_module_list())

        # ---- 中：舞台（画布页 / 无画板交互页 二选一显示） ----
        # 模块一的颜色模型页不需要像素画板（kind="widget"），
        # 装载时把画布换成页面控件；画布页再切回来。
        center = QVBoxLayout()
        center.setSpacing(0)
        self.canvas_slot = QVBoxLayout()
        self.canvas_slot.setContentsMargins(0, 0, 0, 0)
        from PySide6.QtWidgets import QStackedWidget
        self._stage = QStackedWidget()
        self._stage.addWidget(self.canvas)           # index 0：画布页
        self._page_host = QWidget()                  # index 1：交互页容器
        self._page_host_lay = QVBoxLayout(self._page_host)
        self._page_host_lay.setContentsMargins(0, 0, 0, 0)
        self._stage.addWidget(self._page_host)
        self.canvas_slot.addWidget(self._stage)
        center.addLayout(self.canvas_slot, stretch=1)
        root.addLayout(center, stretch=1)

        # 演示模式空格 = 播放/暂停；←/→ = 单步
        self.canvas.demo_arrow.connect(lambda d: self.step_back() if d < 0
                                       else self.step_forward())
        self.player.finished.connect(self._on_replay_finished)

        # ---- 右：教学面板 ----
        root.addWidget(self._build_teaching_panel())

        # ---- 播放器信号 ----
        self.player.index_changed.connect(self._on_index_changed)
        self.player.state_changed.connect(self._on_state_changed)

        # ---- 画布拾取回放：演示页可见时，手动绘制的图元自动重放 ----
        self.canvas.shapes_committed.connect(self._on_shapes_committed)
        # 两阶段填充：演示模式下点"填充"→ 填充阶段步骤追加到回放末尾继续播
        self.canvas.fill_toggled.connect(self._on_fill_toggled)

        self._built = False           # 首次显示时自动选第一个演示页

    # ==================================================================
    # 左栏：模块目录
    # ==================================================================
    def _build_module_list(self) -> QFrame:
        box = QFrame()
        box.setObjectName("card")
        box.setFixedWidth(210)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)

        t = QLabel("课程模块")
        t.setObjectName("cardTitle")
        lay.addWidget(t)

        # 滚动区：每个模块一个可折叠分节（点标题收起/展开其演示页）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setObjectName("moduleListBody")
        container.setStyleSheet(
            "QWidget#moduleListBody { background: transparent; }")
        self._modules_lay = QVBoxLayout(container)
        self._modules_lay.setContentsMargins(0, 0, 0, 0)
        self._modules_lay.setSpacing(6)
        scroll.setWidget(container)
        lay.addWidget(scroll, stretch=1)

        hint = QLabel("每次实验一个模块\n未开放模块随课程解锁")
        hint.setObjectName("secondary")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self._page_buttons = {}      # DemoSpec → 目录行按钮
        self._fill_module_list()
        return box

    def _fill_module_list(self):
        """注册表 → 可折叠分节：每个模块一节，演示页为节内行。"""
        self._all_pages.clear()
        cn = "一二三四五六七八"
        for m in all_modules():
            title = f"模块{cn[m.order - 1]} · {m.name}"
            section = CollapsibleCard(
                title, expanded=(m.status in ("done", "current")), flat=True)
            if m.status == "future":
                section.header.setEnabled(False)
                section.header.setText(title + " — 下章解锁")
                note = QLabel("　本章完成后开放")
                note.setObjectName("moduleHint")
                section.body_lay.addWidget(note)
            else:
                demos = m.create_demos() if m.create_demos else []
                if not demos:
                    note = QLabel("　演示页将在后续阶段接入")
                    note.setObjectName("moduleHint")
                    section.body_lay.addWidget(note)
                for d in demos:
                    b = QPushButton("  " + d.title)
                    b.setObjectName("pageRow")
                    b.setIcon(icon(d.icon, size=15))
                    b.setCheckable(True)
                    b.setCursor(Qt.PointingHandCursor)
                    b.clicked.connect(lambda _=False, dd=d, bb=b:
                                      self._on_page_button(dd, bb))
                    section.body_lay.addWidget(b)
                    self._page_buttons[d] = b
                    self._all_pages.append(d)
            self._modules_lay.addWidget(section)
        self._modules_lay.addStretch()

    def _on_page_button(self, demo, btn):
        """目录行点击：互斥选中并加载该演示页。"""
        for d, b in self._page_buttons.items():
            b.setChecked(d is demo)
        self._load_page(demo)

    # ==================================================================
    # 右栏：参数卡 / 公式卡 / 监视器 / 播放控制
    # ==================================================================
    def _build_teaching_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("card")
        panel.setFixedWidth(290)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        # 教学内容放进滚动容器：卡片保持自然高度，超高时滚动而非互相挤压溢出
        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        body_host = QWidget()
        body_host.setObjectName("teachBody")
        body_host.setStyleSheet(
            "QWidget#teachBody { background: transparent; }")
        lay = QVBoxLayout(body_host)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)
        scroll.setWidget(body_host)
        outer.addWidget(scroll)

        # ---- 参数卡（可折叠） ----
        self.card_params = CollapsibleCard("参数")
        self.params_lay = self.card_params.body_lay
        self.params_lay.setSpacing(4)
        lay.addWidget(self.card_params)

        # ---- 公式卡（可折叠） ----
        self.card_formula = CollapsibleCard("算法公式")
        self.formula_label = QLabel("")
        self.formula_label.setWordWrap(True)
        # 中文为主的公式文本用 UI 字体（Consolas 无中文字形，回退后
        # 笔画瘦、观感差）；行距用富文本 line-height 拉开
        self.formula_label.setTextFormat(Qt.RichText)
        self.formula_label.setStyleSheet(
            f"font-family: {theme.UI_FONT}; font-size: 13px;"
            f" color: {theme.SUCCESS};")
        self.card_formula.body_lay.addWidget(self.formula_label)
        lay.addWidget(self.card_formula)

        # ---- 监视器（可折叠） ----
        self.card_monitor = CollapsibleCard("决策项监视")
        self.monitor = MonitorPanel()
        self.card_monitor.body_lay.addWidget(self.monitor)
        lay.addWidget(self.card_monitor)

        # ---- 概念说明（仅无画板交互页显示，如模块一颜色模型） ----
        self.card_concept = CollapsibleCard("概念说明")
        self.card_concept.setVisible(False)
        self.concept_label = QLabel("")
        self.concept_label.setWordWrap(True)
        self.concept_label.setTextFormat(Qt.RichText)
        self.concept_label.setStyleSheet(
            f"font-family: {theme.UI_FONT}; font-size: 13px;"
            f" color: {theme.TEXT_1};")
        self.card_concept.body_lay.addWidget(self.concept_label)
        lay.addWidget(self.card_concept)

        lay.addStretch()

        # ---- 播放控制（可折叠卡） ----
        self.card_play = CollapsibleCard("播放控制")
        lay.addWidget(self.card_play)
        play_lay = self.card_play.body_lay
        # 选择图元：切到选择/移动工具（箭头），点选某个图元后可拖动/微调
        self.btn_select = QPushButton("  选择图元")
        self.btn_select.setIcon(icon("cursor", size=15))
        self.btn_select.setToolTip(
            "选择/移动工具：点击选中图元，重播/播放即演示它；"
            "再按住拖动移动，方向键微调 1 格")
        self.btn_select.setCursor(Qt.PointingHandCursor)
        self.btn_select.clicked.connect(self._activate_select)
        play_lay.addWidget(self.btn_select)
        clear_btn = QPushButton("清空演示画布")
        clear_btn.setToolTip("清空演示模式的所有图元并停止回放")
        clear_btn.clicked.connect(self._clear_demo_canvas)
        play_lay.addWidget(clear_btn)

        # ---- 进度 ----
        self.progress_label = QLabel("—")
        self.progress_label.setObjectName("mono")
        # 长提示（如"手绘图元已转入对比参数…"）自动换行，防止溢出卡片边框
        self.progress_label.setWordWrap(True)
        play_lay.addWidget(self.progress_label)

        # ---- 播放控制 ----
        row = QHBoxLayout()
        row.setSpacing(4)
        self._play_btns = []                 # 引用：无画板页整体禁用

        def btn(name, tip, slot):
            b = QToolButton()
            b.setObjectName("headerBtn")
            b.setIcon(icon(name, size=17))
            b.setFixedSize(32, 32)
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(slot)
            row.addWidget(b)
            self._play_btns.append(b)
            return b

        btn("replay", "重放（无动画时先按当前参数生成）", self.replay)
        btn("step-back", "单步后退", self.step_back)
        self.btn_play = btn("play", "播放/暂停 (K)", self.play_pause)
        btn("step-fwd", "单步前进", self.step_forward)
        btn("step-fwd", "跳到末尾", self.to_end)

        play_lay.addLayout(row)

        # ---- 速度 ----
        srow = QHBoxLayout()
        slabel = QLabel("速度")
        slabel.setObjectName("secondary")
        srow.addWidget(slabel)
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(5, 240)
        self.speed_slider.setValue(60)
        self.speed_slider.valueChanged.connect(
            lambda v: (self.player.set_fps(v),
                       self.speed_lab.setText(f"{v} 步/秒")))
        srow.addWidget(self.speed_slider, stretch=1)
        self.speed_lab = QLabel("60 步/秒")
        self.speed_lab.setObjectName("mono")
        srow.addWidget(self.speed_lab)
        play_lay.addLayout(srow)

        # 参数改动 → 防抖重生成
        self._regen_timer = QTimer(self)
        self._regen_timer.setSingleShot(True)
        self._regen_timer.setInterval(300)
        self._regen_timer.timeout.connect(self._on_regen_timeout)
        return panel

    # ==================================================================
    # 页面选择 / 参数生成 / 播放联动
    # ==================================================================
    def on_shown(self, autoplay: bool = False):
        """首次切到演示模式：自动选第一个演示页（默认不自动播放）。"""
        if not self._built and self._all_pages:
            self._built = True
            first = self._all_pages[0]
            self._page_buttons[first].setChecked(True)
            self._load_page(first, autoplay=autoplay)

    def on_mode_entered(self):
        """每次进入演示模式（纸面已清空）调用。

        零动画原则：不自动生成、不自动播放——画布保持空白，
        一切由用户自己操作（手绘回放 / 点播放=按当前参数生成并播 /
        改参数即时重生成）。
        """
        if self.current_demo is None:
            self.on_shown(autoplay=False)

    def _load_page(self, demo, regenerate=False, autoplay=True):
        """切换演示页：重建参数卡 + 公式/监视器。

        regenerate=False：稍后手动生成；autoplay=False：只装载不播放。
        无画板交互页（kind="widget"，如模块一颜色模型）走独立装载：
        画布区整个换成页面控件，参数在画面内调节，播放控制禁用。
        """
        self.player.pause()
        self.current_demo = demo
        is_widget = getattr(demo, "kind", "canvas") == "widget"
        # 面板随页型切换：模块一等交互页没有参数卡/决策项监视/播放控制
        # （参数在画面内、无步骤流概念），换上"概念说明"卡
        self.card_params.setVisible(not is_widget)
        self.card_monitor.setVisible(not is_widget)
        self.card_play.setVisible(not is_widget)
        self.card_concept.setVisible(is_widget)
        if is_widget:
            self.concept_label.setText(_rich_text(
                "\n".join(f"· {k}：{v}" for k, v in demo.variables.items()),
                "175%"))
        # 重建参数卡（递归清理：嵌套布局里的控件也要销毁，否则残留重叠）
        self._clear_layout(self.params_lay)
        if not is_widget:
            demo.build_params(self.params_lay)
            # 参数控件变化 → 防抖重生成。注意必须"调用" start()：
            # 此前 QComboBox 连接写成 lambda: self._regen_timer.start
            # （返回方法对象而不调用），下拉切换从不触发生成——
            # DDA 圆变 8 对称、填充全扫描线、对比页换形状无反应皆源于此。
            # 另：QSpinBox 直连 start 会把滑杆值当毫秒，一并改为定间隔。
            for w in self._param_widgets():
                if isinstance(w, QSpinBox):
                    w.valueChanged.connect(
                        lambda _v: self._regen_timer.start())
                elif isinstance(w, QLineEdit):
                    w.textChanged.connect(
                        lambda _t: self._regen_timer.start())
                elif isinstance(w, QComboBox):
                    w.currentIndexChanged.connect(
                        lambda _i=0: self._regen_timer.start())
        self.formula_label.setText(_rich_text(demo.formula))
        self.monitor.set_desc(demo.variables)
        # 播放控制：无步骤流概念的无画板页整体禁用（含速度滑杆）
        for b in getattr(self, "_play_btns", []):
            b.setEnabled(not is_widget)
        if hasattr(self, "speed_slider"):
            self.speed_slider.setEnabled(not is_widget)
        if is_widget:
            self._mount_widget(demo)
            return
        # 画布页：舞台切回画布；页面即工具（自由画布拾取的入口）
        self._stage.setCurrentIndex(0)
        self._sync_tool(demo)

        self._restore_replay_shapes()  # 切页前恢复上一轮回放的图元显示
        skip = getattr(self, "_skip_next_regen", False)
        self._skip_next_regen = False
        if regenerate and not skip:
            self._regenerate(fit=True, autoplay=autoplay)   # 用户主动选页

    def _mount_widget(self, demo):
        """装载无画板交互页：舞台切到页面容器，画布叠层清干净。"""
        while self._page_host_lay.count():
            it = self._page_host_lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)    # 立即脱离父级（deleteLater 有延迟）
                w.deleteLater()
        self._page_host_lay.addWidget(demo.factory())
        self._stage.setCurrentIndex(1)
        self.canvas.demo.reset()
        self._restore_replay_shapes()
        self._replay_source = []
        self._applied_index = -1
        self.monitor.clear()
        self.progress_label.setText("— 交互页（无需播放）")

    @staticmethod
    def _clear_layout(lay):
        """递归清空布局：销毁子控件与子布局（防切页残留重叠）。"""
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            sub = item.layout()
            if sub is not None:
                DemoView._clear_layout(sub)
                sub.deleteLater()

    def _sync_tool(self, demo):
        """按演示页把演示画布的绘制工具切到对应形状与算法。

        页内算法下拉（demo.algo）优先：直线页 dda/bresenham、圆页
        mid/dda、填充页 scanline/seed4/seed8 都同步成画布工具算法，
        手绘回放才用对算法（此前 PAGE_TOOL 默认值优先级写反，
        页面下拉选了 DDA 圆手绘仍按中点圆 8 对称回放）。
        """
        kind_algo = self.PAGE_TOOL.get(type(demo).__name__)
        if kind_algo is None:
            return
        kind, algo = kind_algo
        if kind == "compare":
            # 对比页工具随所选形状：我们自己画，画什么对比什么
            kind = {"line": "compare", "circle": "circle",
                    "fill": "fill"}.get(getattr(demo, "_shape_key", "line"),
                                        "compare")
        page_algo = getattr(demo, "algo", None)
        mapped = self.KIND_TO_ALGO.get((type(demo).__name__, page_algo))
        if mapped:
            algo = mapped
        # 填充对比：画布上还没有封闭图形 → 先给多边形工具画边界；
        # 已有封闭图形 → 给油漆桶，点击内部选定对象（B 方案：必须点选）
        has_closed = any(isinstance(s, (PolygonShape, CircleShape, EllipseShape))
                         for s in self.canvas.shapes)
        if kind == "fill" and isinstance(demo, CompareDemo) and not has_closed:
            kind = "polygon"
        cls = {"line": LineTool, "circle": CircleTool, "ellipse": EllipseTool,
               "polygon": PolygonTool, "compare": CompareLineTool,
               "fill": FillTool}[kind]
        if algo:
            self.canvas.set_algorithm(algo)
        self.canvas.set_tool(cls(self.canvas))
        if isinstance(demo, CompareDemo) and \
                getattr(demo, "_shape_key", "") == "fill":
            self.progress_label.setText(
                "点击封闭图形内部 → 对该图形做双色填充对比" if has_closed
                else "先画一个封闭多边形（闭合）→ 再点击内部做填充对比")
        elif isinstance(demo, FillDemo):
            has_boundary = any(isinstance(s, PolygonShape)
                               for s in self.canvas.shapes)
            self.progress_label.setText(
                "在已有边界内部点击填充（算法随上方下拉）" if has_boundary
                else "先用「多边形」页画边界，再回本页点击内部填充")

    def _restore_replay_shapes(self):
        """恢复被回放隐藏的图元显示并重画底图（幂等）。"""
        for s in getattr(self, "_replay_shapes", []):
            s.visible = True
        if getattr(self, "_replay_shapes", None):
            self._replay_shapes = []
        if getattr(self, "_had_hidden", False):
            self.canvas._render_base()
            self._had_hidden = False

    def _rehide_for_replay(self):
        """重播/播完再按播放前：重新隐藏步骤流的来源图元。

        播完时 _on_replay_finished 会恢复图元显示（保留最终画面），
        但"从头再放"必须先撤销这个最终画面——否则上次的填充结果
        一直铺在底图上，重播变成在成品上叠画，看不到从无到有。
        无来源（参数生成的演示）或图元已隐藏时是幂等空操作。
        """
        src = [s for s in getattr(self, "_replay_source", [])
               if any(s is x for x in self.canvas.shapes)]
        if not src or all(not s.visible for s in src):
            return
        self._replay_shapes = list(src)
        for s in self._replay_shapes:
            s.visible = False
        self.canvas._render_base()
        self._had_hidden = True

    def _on_replay_finished(self):
        """回放播完：恢复图元在底图的最终显示（从无到有收尾）。

        手绘回放（有被隐藏的已提交图元）：清演示叠层、恢复底图。
        参数生成的演示（播放按钮生成、无实体图元）：保留最终画面
        不清空——否则播完瞬间一片空白，用户看不到填充/绘制结果。
        对比页（第三十八轮）：图元恢复显示但【双色结果叠层保留】——
        直线对比对靠两个彩色图元天然显示两种结果，圆/填充的对比
        只存在于叠层上，清掉就只剩一种颜色（用户反馈）。
        """
        if self._replay_shapes:
            if self._keep_overlay_at_finish:
                self._keep_overlay_at_finish = False
                self.canvas.demo.solidify()     # 定格为不透明实色（与直线对比观感一致）
                self._restore_replay_shapes()   # 图元恢复可选中（视觉上被实色结果覆盖）
                return
            self.canvas.demo.reset()
            self._restore_replay_shapes()

    def _activate_select(self):
        """播放控制的"选择图元"按钮：切到选择/移动工具（箭头）。

        点击选中某个图元 → 再按住拖动移动 / 8 方位手柄缩放 /
        方向键微调 1 格（均为画布既有能力，此处只是给演示模式一个入口）。
        """
        from modules.module02_primitives.tools import SelectMoveTool
        self.canvas.set_tool(SelectMoveTool(self.canvas))
        self.progress_label.setText(
            "选择模式：点击图元选中（重播/播放即演示它），"
            "再按住拖动移动，方向键微调 1 格")

    def _replay_selected(self) -> bool:
        """有选中图元时，重播/播放以【选中的图元】为准（从无到有）。

        用户选择图元就是为了操控它：选中某个图元（包括刚拖动/缩放完）
        再按重播，按它当前几何重新生成步骤流回放——而不是重放上一轮
        装载的旧步骤。返回 True 表示已按选中图元处理。
        """
        s = getattr(self.canvas, "_selected_shape", None)
        if s is None or not self._is_canvas_page():
            return False
        from core.shapes import RasterFillShape
        if isinstance(s, RasterFillShape):
            target = next((d for d in self._all_pages
                           if isinstance(d, FillDemo)), None)
            if target is None:
                return False
            if target is not self.current_demo:
                self._select_page_silent(target)
            steps = _raster_fill_steps(s)
            variables = {"阶段": "边界→填充",
                         "算法": getattr(s, "algo", "scanline")}
        else:
            result = steps_for_shape([s])
            target = self._page_for_shapes([s])
            if result is None or target is None:
                return False
            if target is not self.current_demo:
                self._select_page_silent(target)
            target.apply_geometry([s])          # 当前几何读回参数卡
            steps, variables = result
        self._restore_replay_shapes()
        self._replay_shapes = [s]
        self._replay_source = [s]
        s.visible = False
        self.canvas._render_base()
        self._had_hidden = True
        self.player.pause()
        self.canvas.demo.reset()
        self._applied_index = -1
        self.monitor.set_desc(variables)
        self.player.load(steps)
        self.player.play()
        self.progress_label.setText(
            f"已按选中图元回放（重播可再看，Esc 取消选择）")
        return True

    def _clear_demo_canvas(self):
        """清空演示画布：停回放、清叠层、清图元。"""
        self.player.pause()
        self.player.load([])
        self.canvas.demo.reset()
        self._restore_replay_shapes()
        self._replay_source = []
        for d in self._all_pages:     # 填充对比的区域登记一并失效
            if isinstance(d, CompareDemo):
                d._fill_shape = None
        self._applied_index = -1
        self.monitor.clear()
        self._update_progress(-1)
        self.canvas.clear_all()

    def _param_widgets(self):
        """参数卡里的全部输入控件（跨嵌套布局收集）。"""
        out = []

        def walk(lay):
            for i in range(lay.count()):
                it = lay.itemAt(i)
                w = it.widget()
                if w is not None:
                    out.append(w)
                sub = it.layout()
                if sub is not None:
                    walk(sub)

        walk(self.params_lay)
        return out

    def _on_regen_timeout(self):
        """参数防抖到点：对比页零动画——只失效旧步骤（点播放才生成）；
        其余画布页按参数即时重生成并自动播放。"""
        if isinstance(self.current_demo, CompareDemo):
            self._sync_tool(self.current_demo)   # 工具随所选形状切换
            self.player.pause()
            self.player.load([])
            self._applied_index = -1
            self.canvas.demo.reset()
            self._update_progress(-1)
            if getattr(self.current_demo, "_shape_key", "") == "fill":
                self.progress_label.setText(
                    "点击封闭图形内部 → 自动对该图形做双色填充对比"
                    if getattr(self.current_demo, "_fill_shape", None) is not None
                    else "先画一个封闭多边形（闭合）→ 再点击内部做填充对比")
            else:
                self.progress_label.setText(
                    "参数已更新 → 点播放按当前参数生成对比")
            return
        self._regenerate(fit=False, autoplay=True)

    def _regenerate(self, fit: bool = False, autoplay: bool = True):
        """收集参数 → 步骤流 → 播放器装入（autoplay 决定是否立即播放）。

        fit 仅在主动选择演示页时为 True；改参数/手画回放不放大视图。
        """
        if self.current_demo is None:
            return
        if getattr(self.current_demo, "kind", "canvas") == "widget":
            return                # 无画板交互页没有步骤流，参数即画面
        # 页内算法下拉切换 → 画布工具算法即时跟随（直线/圆/填充皆然）
        self._sync_tool(self.current_demo)
        # 填充对比必须先有用户选定的封闭图形：没有就不生成任何步骤
        # （不再回落内置示例多边形，用户明确要求对自己画的图形做对比）
        if isinstance(self.current_demo, CompareDemo) and \
                getattr(self.current_demo, "_shape_key", "") == "fill" and \
                getattr(self.current_demo, "_fill_shape", None) is None:
            self.player.pause()
            self.player.load([])
            self.canvas.demo.reset()
            self._applied_index = -1
            self._update_progress(-1)
            self.progress_label.setText(
                "先画一个封闭多边形（闭合）→ 再点击内部做填充对比")
            return
        from modules.module02_primitives.demos import FillDemo
        if isinstance(self.current_demo, FillDemo) and self.canvas.shapes:
            # 填充页已有手绘边界：参数面板只切油漆桶算法，
            # 不生成参数演示步骤（那会清掉用户正在操作的画布）
            return
        steps = self.current_demo.make_steps(self.current_demo.collect())
        self.player.pause()
        self.canvas.demo.reset()
        self._applied_index = -1
        self._replay_source = []      # 参数生成的步骤没有实体来源图元
        self._keep_overlay_at_finish = False
        self.player.load(steps)
        # 公式卡/监视器说明随算法刷新（如直线页 DDA⇄Bresenham 切换）
        self.formula_label.setText(_rich_text(self.current_demo.formula))
        self.monitor.set_desc(self.current_demo.variables)
        self.monitor.clear()
        self._update_progress(-1)
        if not steps:
            self.progress_label.setText("无输出（检查参数）")
            return
        if fit:
            # 主动选页时才对准生成范围（步骤像素是模拟像素坐标 → ×SIM）
            xs = [px[0] for s in steps for px in s.pixels]
            ys = [px[1] for s in steps for px in s.pixels]
            self.canvas.fit_to_rect(min(xs) * SIM, min(ys) * SIM,
                                    (max(xs) + 1) * SIM, (max(ys) + 1) * SIM)
        if autoplay:
            self.player.play()

    # ------------------------------------------------------------------
    def _on_index_changed(self, index: int, incremental: bool):
        steps = self.player.steps
        if index < 0:
            self.canvas.demo.reset()
            self._applied_index = -1
            self.monitor.clear()
            self._update_progress(-1)
            return
        if incremental and index == self._applied_index + 1:
            step = steps[index]
            self.canvas.demo.advance(step, self._step_color(step))
        elif index != self._applied_index:
            # 跳转/回退：整层重建
            self.canvas.demo.reset()
            for s in steps[:index + 1]:
                self.canvas.demo.advance(s, self._step_color(s))
        self._applied_index = index
        step = steps[index]
        self.monitor.update_values(step.values, step.note)
        self._update_progress(index)

    def _step_color(self, step) -> str:
        return step.values.get("color", theme.ACCENT)

    def _on_state_changed(self, playing: bool):
        self.btn_play.setIcon(icon("pause" if playing else "play", size=17))

    def _update_progress(self, index: int):
        n = len(self.player.steps)
        self.progress_label.setText(
            f"第 {index + 1 if index >= 0 else 0} / {n} 步")

    # 演示模式内空格 = 播放/暂停（画布的空格平移在演示页让位）
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Space:
            if getattr(self.current_demo, "kind", "canvas") != "widget":
                self.play_pause()
                e.accept()
                return
        super().keyPressEvent(e)

    # ---- 播放语义（零动画原则的"用户主动"入口） ----------------------
    def _is_canvas_page(self) -> bool:
        return getattr(self.current_demo, "kind", "canvas") == "canvas"

    def _ensure_generated(self):
        """无步骤时按当前参数生成（不自动播放）——播放类按钮的前置。"""
        if not self.player.steps and self._is_canvas_page():
            self._regenerate(fit=False, autoplay=False)

    def play_pause(self):
        """空格/K/播放按钮：选中图元优先（操控谁就演示谁）；无步骤先生成
        再播放（fit=True 自动把视图对准生成内容）；有步骤则暂停/继续；
        播完再按 = 从头播放，先撤销最终画面。"""
        if not self.player.steps and self._is_canvas_page():
            self._regenerate(fit=True, autoplay=True)
            return
        if self._replay_selected():
            return
        self._rehide_for_replay()
        self.player.toggle()

    def replay(self):
        if self._replay_selected():     # 选中图元优先：按它当前几何回放
            return
        if not self.player.steps and self._is_canvas_page():
            self._regenerate(fit=True, autoplay=True)
            return
        self._rehide_for_replay()   # 先撤销上次播完恢复的画面，再从零重放
        self.player.replay()

    def step_back(self):
        self._ensure_generated()
        self.player.step_back()

    def step_forward(self):
        self._ensure_generated()
        self.player.step_forward()

    def to_end(self):
        if self._replay_selected():     # 选中图元优先：生成后跳到末帧
            self.player.pause()
            self.player.to_end()
            return
        if not self.player.steps and self._is_canvas_page():
            self._regenerate(fit=True, autoplay=False)
            self.player.to_end()
            return
        self.player.to_end()

    # ==================================================================
    # 画布拾取回放：手动划线/画圆后自动把该图元转成步骤动画重放
    # ==================================================================
    def _on_shapes_committed(self, shapes):
        """画布拾取：手动绘制 → 自动切页 + 首尾值读回参数卡 + 按真实图元回放。

        回放不走参数重生成，而是用 steps_for_shape(shapes)——
        这样填充图元是两阶段动画（先轮廓后填充），对比对是双色双层。
        """
        if not self.isVisible():        # 应用模式下绘制不触发回放
            return
        self._keep_overlay_at_finish = False   # 非对比路径播完照常清叠层
        if isinstance(self.current_demo, FillDemo):
            self._handle_fill_page_commit(shapes)
            return
        if isinstance(self.current_demo, CompareDemo):
            self._handle_compare_page_commit(shapes)
            return
        target = self._page_for_shapes(shapes)
        result = steps_for_shape(shapes)
        if target is None or result is None:
            return
        if target is not self.current_demo:
            self._select_page_silent(target)   # 切页（只重建参数卡，不播放）
        target.apply_geometry(shapes)          # 首尾值读回参数卡
        steps, variables = result
        # 从无到有：隐藏刚画的图元（底图清空），像素在叠层上逐步生长，播完恢复
        self._restore_replay_shapes()
        self._replay_shapes = list(shapes)
        self._replay_source = list(shapes)
        for s in self._replay_shapes:
            s.visible = False
        self.canvas._render_base()
        self._had_hidden = True
        self.player.pause()
        self.canvas.demo.reset()
        self._applied_index = -1
        self.monitor.set_desc(variables)
        self.player.load(steps)
        self.player.play()

    def _handle_fill_page_commit(self, shapes):
        """填充页专属交互（像应用模式那样：先画边界，再油漆桶点中填充）：

        · 多边形边界刚闭合 → 自动切油漆桶（算法=页面下拉当前值）；
        · 油漆桶点击 → 填充图元提交 → 像素按扩散顺序逐步回放
          （填充图元隐藏，边界保持可见，播完恢复）。
        再点一次"填充"页目录行 → 回到多边形工具画下一个边界。
        """
        from core.shapes import RasterFillShape
        from modules.module02_primitives.tools import FillTool
        fill_shape = next((s for s in reversed(shapes)
                           if isinstance(s, RasterFillShape)), None)
        if fill_shape is None:
            # 边界刚闭合 → 切油漆桶等待点内部（不自动扫描线填充）
            if not isinstance(self.canvas.tool, FillTool):
                self.canvas.set_tool(FillTool(self.canvas))
            self.progress_label.setText("边界已闭合 → 点击多边形内部填充（油漆桶）")
            return
        # 油漆桶结果 → 按扩散顺序回放（像素顺序即波前顺序）
        self._restore_replay_shapes()
        self._replay_shapes = [fill_shape]
        self._replay_source = [fill_shape]
        fill_shape.visible = False
        self.canvas._render_base()
        self._had_hidden = True
        self.player.pause()
        self.canvas.demo.reset()
        self._applied_index = -1
        self.monitor.set_desc({"阶段": "边界→填充",
                               "算法": getattr(self.current_demo,
                                               "algo", "scanline")})
        self.player.load(_raster_fill_steps(fill_shape))
        self.player.play()

    def _handle_compare_page_commit(self, shapes):
        """对比页手绘：几何读回对比参数并自动双色回放。

        · 直线/圆：常规对比（圆替换为双算法实色图元对，常驻画布）；
        · 多边形 / 油漆桶填充转移：登记为填充对比的区域——填充对比
          用【我画的对象】而非预制多边形（用户反馈）。
        """
        from core.shapes import (LineShape, CircleShape, RasterFillShape,
                                 PolygonShape, KIND_RASTER_FILL)
        s = shapes[0]
        cmpd = self.current_demo
        if not isinstance(cmpd, CompareDemo):
            return
        if isinstance(s, RasterFillShape):
            owner = getattr(s, "owner", None)   # 油漆桶归属的边界图元
            if owner is None:
                return
            cmpd._fill_shape = owner
            cmpd._shape_key = "fill"
            cmpd.shape_combo.blockSignals(True)
            cmpd.shape_combo.setCurrentIndex(2)
            cmpd.shape_combo.blockSignals(False)
            # 只收起这次填充结果：黑色边界始终留在画布上（用户要求
            # 填充动画期间边界不能消失），播完填充结果恢复可见
            hide_shapes = [s]
        elif isinstance(s, PolygonShape) and len(s.vertices) >= 3:
            # B 方案：闭合多边形只是"画好了边界"，还必须点击内部填充
            # 来选定对比对象——这里不自动生成对比，先切油漆桶等待点选
            from modules.module02_primitives.tools import FillTool
            cmpd._fill_shape = None       # 新边界：旧的对比对象作废
            cmpd._shape_key = "fill"
            cmpd.shape_combo.blockSignals(True)
            cmpd.shape_combo.setCurrentIndex(2)
            cmpd.shape_combo.blockSignals(False)
            cmpd._sync_shape_widgets()   # 算法 A/B 清单切成填充算法
            if not isinstance(self.canvas.tool, FillTool):
                self.canvas.set_tool(FillTool(self.canvas))
            self.progress_label.setText(
                "边界已闭合 → 点击图形内部：对该图形做填充并双色对比")
            return
        elif isinstance(s, (LineShape, CircleShape)):
            cmpd.apply_geometry([s])          # 坐标 + 形状/算法读回
            hide_shapes = list(shapes)
        else:
            return
        if cmpd._shape_key == "fill":
            # 保留用户在下拉里选的算法 A/B；只有无效时才回落默认组合
            valid = {k for k, _n in cmpd.COMPARE_SHAPES[2][2]}
            if cmpd._algo_a not in valid or cmpd._algo_b not in valid:
                cmpd._algo_a, cmpd._algo_b = "scanline", "seed4"
            cmpd._sync_shape_widgets()
        steps = cmpd.make_steps(cmpd.collect())
        if not steps:
            return
        # 圆对比对齐直线做法：把黑色圆替换为两算法结果的【实色图元对】
        #（满格蓝紫 = 算法A，内缩橙芯 = 算法B，成组联动）——结果常驻
        # 画布、多组共存，不随叠层清空变回黑色（用户反馈）
        if isinstance(s, CircleShape):
            from modules.module02_primitives.demos import (BRE_COLOR,
                                                           DDA_COLOR)
            pa, pb = set(), set()
            for st in steps:
                tgt = pa if st.values.get("color") == BRE_COLOR else pb
                tgt.update(st.pixels)
            pair_a = RasterFillShape(kind=KIND_RASTER_FILL,
                                     color=BRE_COLOR, width=1)
            pair_a.pixels = sorted(pa)
            pair_b = RasterFillShape(kind=KIND_RASTER_FILL,
                                     color=DDA_COLOR, width=1)
            pair_b.inset = 5
            pair_b.pixels = sorted(pb)
            pair_b.owner = pair_a             # 拖动/缩放/删除整体联动
            self.canvas.remove_shape(s)
            self.canvas.add_shapes([pair_a, pair_b])
            hide_shapes = [pair_a, pair_b]
        # 从无到有：手绘图元回放期间收起，双色对比从零生长，播完恢复；
        # 重播/播完再按播放经 _replay_source 重新收起（与填充页同语义）。
        # 第三十轮"保持可见"是为配合装载待播（隐藏+暂停=画面空白被误读
        # 为"画不出来"）；本轮装载即自动播放，收起不再产生空白期。
        self._restore_replay_shapes()
        self._replay_shapes = list(hide_shapes)
        self._replay_source = list(hide_shapes)
        for s in self._replay_shapes:
            s.visible = False
        self.canvas._render_base()
        self._had_hidden = True
        self.player.pause()
        self.canvas.demo.reset()
        self._applied_index = -1
        self._keep_overlay_at_finish = True   # 播完保留双色对比结果
        self.monitor.set_desc(cmpd.variables)
        self.player.load(steps)
        self._sync_tool(self.current_demo)   # 工具跟随图元类型
        self.player.play()
        self.progress_label.setText(
            "手绘图元已转入对比参数 → 双色对比回放中（重播可再看）")

    def _on_fill_toggled(self, shape):
        """演示模式点"填充"：填充阶段步骤追加到回放末尾（轮廓播完后接着播填充）。"""
        if not self.isVisible() or shape is None or not shape.fill:
            return
        self._keep_overlay_at_finish = False
        result = fill_steps_for_shape(shape)
        if not result:
            return
        steps, variables = result
        tagged = [Step(s.pixels, {**s.values, "阶段": "内部填充"}, s.note)
                  for s in steps]
        self._replay_shapes = list(getattr(self, "_replay_shapes", []))
        if shape not in self._replay_shapes:
            self._replay_shapes.append(shape)
            if shape not in self._replay_source:
                self._replay_source.append(shape)
            shape.visible = False
            self.canvas._render_base()
            self._had_hidden = True
        self.monitor.set_desc(variables)
        self.player.extend(tagged)
        self.player.play()

    def _page_for_shapes(self, shapes):
        """图元 → 对应演示页；无法识别返回 None。"""
        if steps_for_shape(shapes) is None:
            return None
        if len(shapes) == 2:
            cls = CompareDemo
        else:
            s = shapes[0]
            if isinstance(s, LineShape):
                cls = LineDemo
            elif isinstance(s, CircleShape):
                cls = CircleDemo
            elif isinstance(s, EllipseShape):
                cls = EllipseDemo
            elif isinstance(s, PolygonShape):
                cls = PolygonDemo
            else:
                cls = FillDemo
        for d in self._all_pages:
            if isinstance(d, cls):
                return d
        return None

    def _select_page_silent(self, demo):
        """程序化切页（加载但跳过默认参数的自动播放与视图适配）。"""
        for d, b in self._page_buttons.items():
            b.setChecked(d is demo)
        self._load_page(demo, regenerate=False)
