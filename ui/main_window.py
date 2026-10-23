# -*- coding: utf-8 -*-
"""
=====================================================================
 ui/main_window.py  —  主窗口 v5（应用模式 UI 成品，规范 3.1/四/五节）
=====================================================================
布局（对标 Photoshop/Figma 的主流画板结构）：
  顶栏  headerBar：logo+标题 | 模式切换(应用/演示) | 打开/存工程/导出/撤销/重做
  左栏  rail 52px：图标工具钮（SVG，checked 主题色浅底）
  中间：工具选项条(40px，随工具切换) + 画布（桌面衬底上的白纸）
  右栏  260px 三卡片：颜色（色块+HEX+最近8色）/ 图元列表 / 视图
  状态栏：坐标/缩放/图元/提示（等宽字体）

交互（规范 5.1）：1~5 切工具、Ctrl+Z/Y、Ctrl+0 适配、Ctrl+1 100%、
Delete 删除选中图元、Tab 收起面板、右键菜单；Shift 约束/Esc 取消在
画布与工具层实现（canvas_view.py + module02/tools.py）。

模式切换：演示模式当前为占位页（阶段四实现），切换机制本版接通。
=====================================================================
"""

from collections import deque

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QToolButton, QButtonGroup,
    QLabel, QFrame, QFileDialog, QMessageBox, QStatusBar, QPushButton,
    QStackedWidget, QMenu, QComboBox, QSizePolicy, QToolTip, QApplication,
    QGridLayout, QSlider,
)

from core.canvas_view import CanvasView
from core.registry import discover, all_modules
from core import project_file
from ui import theme
from ui.icons import icon
from ui.widgets import CollapsibleCard, SegmentedControl, TogglePill, h_divider, stretch
from ui.shape_list import ShapeListPanel
from ui.demo_view import DemoView
from ui.color_dialog import ColorDialog

# 工具类 → 图标键（icon_name 由各工具类自声明，规范契约②）
DEFAULT_RECENT = ["#222222", "#F76B15", "#4F6EF7", "#46A758",
                  "#E5484D", "#8E4EC6", "#0EA5E9", "#FACC15"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("图形画板")
        self.setWindowIcon(icon("logo", color=theme.ACCENT))
        self.resize(1440, 860)

        # ---- 模块注册表：加载全部模块的工具（框架不写死实验） ----
        discover()
        self._tool_classes = []
        for m in all_modules():
            self._tool_classes.extend(m.tool_classes)
        self._current_tool = None

        # 双模式独立画布：应用/演示各有自己的画布与图元文档，互不干扰
        self._app_canvas = CanvasView()
        self._demo_canvas = CanvasView()
        self._recent_colors = deque(DEFAULT_RECENT, maxlen=8)

        # ================= 顶栏 =================
        root = QVBoxLayout(self._central())
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        # ================= 主体（应用页 / 演示页 切换） =================
        self.body_stack = QStackedWidget()
        self.body_stack.addWidget(self._build_app_page())      # index 0
        # 演示页：持有独立的演示画布（与应用画布互不干扰）
        self.demo_view = DemoView()
        self.body_stack.addWidget(self.demo_view)              # index 1
        root.addWidget(self.body_stack, stretch=1)

        # ================= 状态栏 =================
        root.addWidget(self._build_statusbar())

        # ---- 画布信号（两块画布接同一组处理器，处理器读"活动画布"） ----
        for cv in (self._app_canvas, self._demo_canvas):
            cv.cursor_changed.connect(self._on_cursor)
            cv.zoom_changed.connect(self._on_zoom)
            cv.shape_count_changed.connect(self._on_count)
            cv.document_changed.connect(self._on_document_changed)
            cv.context_requested.connect(self._show_canvas_menu)
            cv.selection_changed.connect(self._on_selection_changed)

        # ---- Ctrl 组合快捷键（活动画布动态路由） ----
        for seq, slot in [
            ("Ctrl+Z", lambda: self.canvas.undo()),
            ("Ctrl+Y", lambda: self.canvas.redo()),
            ("Ctrl+0", lambda: self.canvas.fit_view()),
            ("Ctrl+1", lambda: self.canvas.zoom_100()),
            ("Ctrl+S", lambda: self._export_png()),
            ("Ctrl+Shift+S", lambda: self._save_project()),
            ("Ctrl+O", lambda: self._open_project()),
            ("Ctrl+Delete", lambda: self.canvas.clear_all()),
        ]:
            QShortcut(QKeySequence(seq), self, activated=slot)
        QShortcut(QKeySequence("Tab"), self, activated=self._toggle_panels)
        QShortcut(QKeySequence("F1"), self, activated=self._show_help)
        QShortcut(QKeySequence("?"), self, activated=self._show_help)
        # 单键（1~8/V/E/K/Delete/+/-/空格/方向键）统一走事件过滤器路由
        # （输入框内打字不拦截），见 eventFilter
        self.installEventFilter(self)

        # 默认选第一个工具并刷新一次按钮态
        self._activate_tool(0)
        self._on_document_changed()

    @property
    def canvas(self):
        """当前活动画布（应用模式=应用画布；演示模式=演示画布）。"""
        if getattr(self, "body_stack", None) is not None and \
                self.body_stack.currentIndex() == 1:
            return self.demo_view.canvas
        return self._app_canvas

    # ==================================================================
    # 顶栏
    # ==================================================================
    def _central(self) -> QWidget:
        central = QWidget()
        self.setCentralWidget(central)
        return central

    def _build_header(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("headerBar")
        bar.setFixedHeight(48)
        # 页眉空白处按住拖动 = 移动窗口；双击 = 最大化/还原（系统标题栏之外的多余拖拽区）
        bar.mousePressEvent = self._header_press
        bar.mouseDoubleClickEvent = self._header_double_click
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(10)

        logo = QLabel()
        logo.setPixmap(icon("logo", color=theme.ACCENT, size=22).pixmap(22, 22))
        lay.addWidget(logo)
        title = QLabel("图形画板")
        title.setObjectName("appTitle")
        lay.addWidget(title)

        lay.addWidget(stretch())

        # 模式切换（演示模式阶段四开放，先占位）
        self.mode_seg = SegmentedControl(["应用模式", "演示模式"])
        self.mode_seg.changed.connect(self._on_mode_changed)
        self.mode_seg.set_enabled_at(1, True, "演示模式：算法步骤动画 / 决策项监视 / DDA-Bresenham 对比")
        lay.addWidget(self.mode_seg)

        lay.addWidget(stretch())

        for name, tip, slot in [
            ("open",    "打开工程 (Ctrl+O)", self._open_project),
            ("archive", "保存工程 (Ctrl+Shift+S)", self._save_project),
            ("image",   "导出 PNG (Ctrl+S)", self._export_png),
        ]:
            lay.addWidget(self._header_btn(name, tip, slot))

        sep = h_divider()
        sep.setFixedHeight(20)
        lay.addWidget(sep)

        self.btn_undo = self._header_btn("undo", "撤销 (Ctrl+Z)", self.canvas.undo)
        self.btn_redo = self._header_btn("redo", "重做 (Ctrl+Y)", self.canvas.redo)
        lay.addWidget(self.btn_undo)
        lay.addWidget(self.btn_redo)

        help_btn = QPushButton("?")
        help_btn.setObjectName("headerBtn")
        help_btn.setFixedSize(30, 30)
        help_btn.setToolTip("快捷键速查 (F1)")
        help_btn.setCursor(Qt.PointingHandCursor)
        help_btn.clicked.connect(self._show_help)
        lay.addWidget(help_btn)
        return bar

    def _header_press(self, e):
        """页眉空白处按下 → 系统级移动窗口。

        注意不要再做 childAt 过滤：e.position() 是页眉局部坐标，
        传给主窗口的 childAt 是两套坐标系，几乎总会"查到子控件"
        而拦掉拖动（表现为只有最顶上一条能拖）。可交互子控件
        （按钮等）会先消费自己的按下事件，走到这里的都是空白处。
        """
        if e.button() == Qt.LeftButton:
            handle = self.windowHandle()
            if handle is not None:
                handle.startSystemMove()

    def _header_double_click(self, e):
        """双击页眉 → 最大化 / 还原。"""
        if e.button() == Qt.LeftButton:
            self.showNormal() if self.isMaximized() else self.showMaximized()

    def _enable_window_drag(self, *widgets):
        """扩展窗口拖动区：让这些容器的空白处按住左键即可移动窗口。

        无边框窗口只有页眉可拖时，窗口开在屏幕角落会很难救回来。
        子控件（按钮/滑杆/开关/列表等）会先消费自己的按下事件，
        因此只有空白处会触发拖动，不影响任何交互。
        """
        for w in widgets:
            def _press(e, _w=w):
                if e.button() == Qt.LeftButton:
                    handle = self.windowHandle()
                    if handle is not None:
                        handle.startSystemMove()
            w.mousePressEvent = _press

    def _header_btn(self, icon_name: str, tip: str, slot) -> QToolButton:
        b = QToolButton()
        b.setObjectName("headerBtn")
        b.setIcon(icon(icon_name, size=18))
        b.setFixedSize(30, 30)
        b.setToolTip(tip)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    # ==================================================================
    # 应用模式页：左 rail + 中间(选项条+画布) + 右栏
    # ==================================================================
    def _build_app_page(self) -> QWidget:
        page = QWidget()
        body = QHBoxLayout(page)
        body.setContentsMargins(10, 10, 10, 6)
        body.setSpacing(10)

        body.addWidget(self._build_rail())

        center = QVBoxLayout()
        center.setSpacing(8)
        center.addWidget(self._build_options_bar())
        center.addWidget(self._app_canvas, stretch=1)
        self._app_center = center          # 模式切换时把画布移回这里
        body.addLayout(center, stretch=1)

        body.addWidget(self._build_right_panel())

        self._app_page = page           # Tab 收起面板时经 layout() 定位左右栏
        return page

    def _build_rail(self) -> QFrame:
        rail = QFrame()
        self.rail = rail                    # 引用保留：模式切换时随画布重父级
        rail.setObjectName("rail")
        rail.setFixedWidth(52)
        lay = QVBoxLayout(rail)
        lay.setContentsMargins(6, 8, 6, 8)
        lay.setSpacing(4)

        self._rail_group = QButtonGroup(self)
        self._rail_group.setExclusive(True)
        self._rail_buttons = []
        for i, cls in enumerate(self._tool_classes):
            b = QToolButton()
            b.setObjectName("railBtn")
            b.setIcon(icon(getattr(cls, "icon_name", "sparkle"), size=20))
            b.setFixedSize(40, 40)
            b.setCheckable(True)
            b.setToolTip(f"{cls.name}（{i + 1}）\n{cls.cursor_hint}")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, idx=i: self._activate_tool(idx))
            self._rail_group.addButton(b, i)
            lay.addWidget(b)
            self._rail_buttons.append(b)

        self._rail_buttons[0].setChecked(True)
        lay.addStretch()
        self._enable_window_drag(rail)       # 左栏空白可拖动窗口
        return rail

    def _build_options_bar(self) -> QFrame:
        bar = QFrame()
        self.options_bar = bar               # 引用保留：模式切换时随画布重父级
        bar.setObjectName("optionsBar")
        bar.setFixedHeight(44)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(10)

        self.opt_icon = QLabel()
        self.opt_name = QLabel("")
        self.opt_name.setObjectName("optToolName")
        lay.addWidget(self.opt_icon)
        lay.addWidget(self.opt_name)
        lay.addWidget(h_divider())

        # 颜色快选块（点击打开选色对话框）
        # 算法下拉（随工具切换内容；无可选算法的工具隐藏）
        algo_lab = QLabel("算法")
        algo_lab.setObjectName("secondary")
        lay.addWidget(algo_lab)
        self.algo_combo = QComboBox()
        self.algo_combo.setMinimumWidth(180)
        self.algo_combo.currentIndexChanged.connect(self._on_algorithm_selected)
        lay.addWidget(self.algo_combo)
        self._algo_label = algo_lab

        # 填充⇄描边切换：选中闭合图元时作用于它；否则作用于工具的提交状态
        self.btn_fill = QPushButton("填充")
        self.btn_fill.setObjectName("primaryBtn")
        self.btn_fill.setToolTip("填充⇄描边（显示当前状态，点击切换；作用于选中图元或当前工具）")
        self.btn_fill.setCursor(Qt.PointingHandCursor)
        self.btn_fill.clicked.connect(self._on_fill_clicked)
        self._sync_fill_btn()
        lay.addWidget(self.btn_fill)

        self.opt_color = QFrame()
        self.opt_color.setFixedSize(30, 22)
        self.opt_color.setCursor(Qt.PointingHandCursor)
        self.opt_color.setToolTip("画笔颜色（点击修改）")
        self.opt_color.mousePressEvent = lambda e: self._pick_color()
        self._update_color_widgets()
        lay.addWidget(self.opt_color)

        tip = QLabel("一格 = 一个模拟像素")
        tip.setObjectName("optHint")
        lay.addWidget(tip)

        lay.addWidget(stretch())
        self.opt_hint = QLabel("")
        self.opt_hint.setObjectName("optHint")
        lay.addWidget(self.opt_hint)
        self._enable_window_drag(bar)        # 选项条空白可拖动窗口
        return bar

    def _build_right_panel(self) -> QWidget:
        # 右栏 = 一张整体卡片，内含 颜色/图元/视图 三个可折叠分节；
        # 颜色/视图分节固定内容高度，图元分节吸收剩余空间。
        from PySide6.QtWidgets import QSizePolicy
        panel = QFrame()
        panel.setObjectName("card")
        panel.setFixedWidth(260)
        self.right_panel = panel           # 引用：窄宽裁切回归测试用
        # 内容装进滚动容器：窗口矮时右栏向下滚动延伸，控件永不互相挤压重叠
        from PySide6.QtWidgets import QScrollArea
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 顶部分配：内容按自然高度从顶部堆叠（折叠的卡紧凑并排，
        # 剩余空间落到底部），而不是被拉伸铺满视口导致卡片间出大空隙
        scroll.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QWidget#rightPanelBody { background: transparent; }")
        body = QWidget()
        body.setObjectName("rightPanelBody")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(4)
        scroll.setWidget(body)
        outer.addWidget(scroll)
        self._right_scroll = scroll

        # ---- 分节一：颜色（固定高度；当前色行 + 颜色表 + 最近使用） ----
        color_sec = CollapsibleCard("颜色", flat=True, expanded=True)
        color_sec.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        lay.addWidget(color_sec)
        c_lay = color_sec.body_lay

        cur_row = QHBoxLayout()
        cur_row.setSpacing(8)
        self.color_block = QFrame()
        self.color_block.setFixedSize(22, 22)
        self.color_block.setToolTip("当前颜色（点击打开选色器）")
        self.color_block.setCursor(Qt.PointingHandCursor)
        self.color_block.mousePressEvent = lambda e: self._pick_color()
        cur_row.addWidget(self.color_block)
        self.hex_label = QLabel("#222222")
        self.hex_label.setObjectName("mono")
        self.hex_label.setCursor(Qt.PointingHandCursor)
        self.hex_label.setToolTip("单击复制 HEX（双击编辑请开选色器）")

        def _copy_hex_label(_e=None):
            QApplication.clipboard().setText(self.hex_label.text())
            QToolTip.showText(
                self.hex_label.mapToGlobal(self.hex_label.rect().center()),
                "已复制 " + self.hex_label.text(), self.hex_label)

        self.hex_label.mousePressEvent = _copy_hex_label
        cur_row.addWidget(self.hex_label)
        cur_row.addStretch()
        more_btn = QPushButton("更多颜色…")
        more_btn.setToolTip("打开 RGB/HSV 选色器")
        more_btn.clicked.connect(self._pick_color)
        cur_row.addWidget(more_btn)
        c_lay.addLayout(cur_row)

        from ui.color_table import ColorTable
        self.color_table = ColorTable(self.canvas.pen_color)
        self.color_table.colorChanged.connect(
            lambda c: (self.canvas.set_pen_color(c),
                       self._update_color_widgets()))
        c_lay.addWidget(self.color_table)

        self._recent_row_lay = QHBoxLayout()
        self._recent_row_lay.setSpacing(4)
        self._recent_row_host = QWidget()
        _host_lay = QVBoxLayout(self._recent_row_host)
        _host_lay.setContentsMargins(0, 0, 0, 0)
        _host_lay.addLayout(self._recent_row_lay)
        self._rebuild_recent_row()
        c_lay.addWidget(self._recent_row_host)
        rl = QLabel("最近使用")
        rl.setObjectName("secondary")
        c_lay.addWidget(rl)

        # ---- 分节二：图元（吸收剩余空间；标题行带一键清空） ----
        shape_sec = CollapsibleCard("图元", flat=True, expanded=True,
                                    expands=True)
        # 图元卡高拉伸权重：展开时吸收剩余空间；折叠时被 maxHeight
        # 压到标题条高度，剩余空间全部落到末尾的 addStretch（见下）
        lay.addWidget(shape_sec, stretch=10)
        clear_btn = QToolButton()
        clear_btn.setObjectName("headerBtn")
        clear_btn.setToolTip("一键清空（可撤销）")
        clear_btn.setIcon(icon("trash", size=15))
        clear_btn.setFixedSize(22, 22)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self.canvas.clear_all)
        shape_sec.set_header_extra(clear_btn)
        s_lay = shape_sec.body_lay
        self.shape_panel = ShapeListPanel(self._app_canvas)
        s_lay.addWidget(self.shape_panel, stretch=1)
        empty_tip = QLabel("单击行选中；画布按住拖动移动；方向键微调")
        empty_tip.setObjectName("secondary")
        empty_tip.setWordWrap(True)
        s_lay.addWidget(empty_tip)

        # ---- 分节三：视图（固定高度） ----
        view_sec = CollapsibleCard("视图", flat=True, expanded=True)
        view_sec.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        lay.addWidget(view_sec)
        v_lay = view_sec.body_lay
        for text, attr in [("网格", "show_grid"), ("坐标轴", "show_axis")]:
            row = QHBoxLayout()
            lab = QLabel(text)
            lab.setObjectName("secondary")
            row.addWidget(lab)
            row.addStretch()
            tgl = TogglePill()
            tgl.toggled.connect(
                lambda on, a=attr: self._toggle_view_attr(a, on))
            row.addWidget(tgl)
            v_lay.addLayout(row)

        # 视图按钮 2×2 网格：四个按钮单行最小宽 ~258px 超过面板视口
        # 244px，会把整个右栏内容体撑宽导致右侧控件全部被裁（问题 #52）
        view_grid = QGridLayout()
        view_grid.setHorizontalSpacing(4)
        view_grid.setVerticalSpacing(4)
        fit_btn = QPushButton(" 适配窗口")
        fit_btn.setIcon(icon("fit", size=14))
        fit_btn.setToolTip("Ctrl+0")
        fit_btn.clicked.connect(lambda: self.canvas.fit_view())
        zoom_btn = QPushButton(" 100%")
        zoom_btn.setIcon(icon("zoom100", size=14))
        zoom_btn.setToolTip("Ctrl+1")
        zoom_btn.clicked.connect(lambda: self.canvas.zoom_100())
        zout_btn = QPushButton()
        zout_btn.setIcon(icon("zoom-out", size=14))
        zout_btn.setToolTip("缩小（− 键）")
        zout_btn.clicked.connect(lambda: self.canvas.zoom_step(1 / 1.15))
        zin_btn = QPushButton()
        zin_btn.setIcon(icon("zoom-in", size=14))
        zin_btn.setToolTip("放大（+ 键）")
        zin_btn.clicked.connect(lambda: self.canvas.zoom_step(1.15))
        view_grid.addWidget(fit_btn, 0, 0)
        view_grid.addWidget(zoom_btn, 0, 1)
        view_grid.addWidget(zout_btn, 1, 0)
        view_grid.addWidget(zin_btn, 1, 1)
        v_lay.addLayout(view_grid)

        # ---- 缩放滑杆：与 +/− 按钮、滚轮、100% 双向联动（10%–800%） ----
        srow = QHBoxLayout()
        srow.setSpacing(6)
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 800)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setToolTip("缩放比例（也可用 +/− 按钮或滚轮）")
        self.zoom_slider.valueChanged.connect(
            lambda v: self.canvas.zoom_to(v / 100))
        self.zoom_lab = QLabel("100%")
        self.zoom_lab.setObjectName("mono")
        self.zoom_lab.setFixedWidth(42)
        self.zoom_lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        srow.addWidget(self.zoom_slider, stretch=1)
        srow.addWidget(self.zoom_lab)
        v_lay.addLayout(srow)

        # 末尾低权重 stretch：没有卡片能吸收剩余空间时（如全部折叠），
        # 空白统一落在底部，三张折叠卡紧凑并排堆在上方（用户期望的"栅栏"）
        lay.addStretch(1)

        # 构建完成统一刷新一次颜色控件（修复初始化顺序导致色块无色）
        self._update_color_widgets()

        self._enable_window_drag(panel)      # 右栏空白可拖动窗口
        return panel

    def _make_swatch(self, hex_color: str) -> QFrame:
        """最近使用色的小色块按钮。"""
        sw = QFrame()
        sw.setFixedSize(20, 20)
        sw.setCursor(Qt.PointingHandCursor)
        sw.setToolTip(hex_color)
        sw.setStyleSheet(
            f"background:{hex_color};border:1px solid {theme.BORDER};"
            f"border-radius:4px;")
        sw.mousePressEvent = lambda e, c=hex_color: self._use_color(QColor(c))
        return sw

    # ==================================================================
    # 状态栏
    # ==================================================================
    def _build_statusbar(self) -> QStatusBar:
        status = QStatusBar()
        status.setSizeGripEnabled(False)
        status.setFixedHeight(26)
        self.setStatusBar(status)
        # QStatusBar 的 C++ 事件处理会遮住实例级 mousePressEvent 覆写，
        # 改走事件过滤器接空白处按下（其余容器用 _enable_window_drag 即可）
        if getattr(self, "_drag_widgets", None) is None:
            self._drag_widgets = set()
        self._drag_widgets.add(status)
        status.installEventFilter(self)
        self.lbl_pos = QLabel("坐标 (—, —)")
        self.lbl_zoom = QLabel("缩放 100%")
        self.lbl_count = QLabel("图元 0")
        self.lbl_hint = QLabel("")
        for w in (self.lbl_pos, self.lbl_zoom, self.lbl_count, self.lbl_hint):
            status.addPermanentWidget(w)
        return status

    # ==================================================================
    # 工具激活 / 选项条刷新
    # ==================================================================
    def _activate_tool(self, idx: int):
        cls = self._tool_classes[idx]
        tool = cls(self.canvas)
        self.canvas.set_tool(tool)
        self._current_tool = tool
        self._rail_buttons[idx].setChecked(True)

        # 选项条随工具切换
        self.opt_icon.setPixmap(
            icon(getattr(cls, "icon_name", "sparkle"),
                 color=theme.ACCENT, size=18).pixmap(18, 18))
        self.opt_name.setText(cls.name)
        self.opt_hint.setText(cls.cursor_hint)
        self.lbl_hint.setText(cls.cursor_hint)
        self._sync_fill_btn()
        self._sync_algo_icon()               # 橡皮擦等工具图标随算法联动

        # 算法下拉：按工具声明的可选项重建（无选项则隐藏）
        opts = getattr(cls, "algorithm_options", [])
        self.algo_combo.blockSignals(True)
        self.algo_combo.clear()
        self._algo_keys = [k for k, _ in opts]
        for _k, label in opts:
            self.algo_combo.addItem(label)
        has_algo = bool(opts)
        self.algo_combo.setVisible(has_algo)
        self._algo_label.setVisible(has_algo)
        if has_algo:
            cur = self.canvas.algorithm
            self.algo_combo.setCurrentIndex(
                self._algo_keys.index(cur) if cur in self._algo_keys else 0)
            self.canvas.set_algorithm(self._algo_keys[self.algo_combo.currentIndex()])
        self.algo_combo.blockSignals(False)



    # ==================================================================
    # 颜色 / 线宽
    # ==================================================================
    def _pick_color(self):
        dlg = ColorDialog(self.canvas.pen_color, self)
        if dlg.exec():
            self._use_color(dlg.selected_color())

    def _use_color(self, c: QColor):
        """应用颜色（预设/最近使用/对话框共用入口）。"""
        self.canvas.set_pen_color(c)
        self._update_color_widgets()
        # 最近使用去重后前插，并刷新色块行
        name = c.name().lower()
        if name in [x.lower() for x in self._recent_colors]:
            for x in list(self._recent_colors):
                if x.lower() == name:
                    self._recent_colors.remove(x)
                    break
        self._recent_colors.appendleft(c.name())
        self._rebuild_recent_row()

    def _update_color_widgets(self):
        name = self.canvas.pen_color.name()
        # 右栏在选项条之后才构建，缺哪个刷哪个
        for attr in ("color_block", "opt_color"):
            w = getattr(self, attr, None)
            if w is not None:
                w.setStyleSheet(
                    f"background:{name};border:1px solid {theme.BORDER};"
                    f"border-radius:6px;")
        if getattr(self, "hex_label", None) is not None:
            self.hex_label.setText(name.upper())
        ct = getattr(self, "color_table", None)
        if ct is not None:
            ct.blockSignals(True)
            ct.set_color(self.canvas.pen_color)
            ct.blockSignals(False)

    def _rebuild_recent_row(self):
        """重建"最近使用"色块行（颜色变化后调用）。"""
        while self._recent_row_lay.count():
            item = self._recent_row_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for c in self._recent_colors:
            self._recent_row_lay.addWidget(self._make_swatch(c))

    def _on_algorithm_selected(self, idx: int):
        """算法下拉 → 画布当前算法（提交图元时由工具读取）。"""
        if 0 <= idx < len(getattr(self, "_algo_keys", [])):
            key = self._algo_keys[idx]
            self.canvas.set_algorithm(key)
            self._sync_algo_icon(key)

    def _sync_algo_icon(self, algo_key: str = None):
        """选项条图标随算法联动：工具声明 algo_icon 映射时，
        按当前算法键切换图标（如橡皮擦 像素=橡皮 / 整体=垃圾桶）。"""
        tool_cls = type(self._current_tool) if self._current_tool else None
        if tool_cls is None:
            return
        mapping = getattr(tool_cls, "algo_icon", None)
        if not mapping:
            return
        if algo_key is None:
            algo_key = getattr(self.canvas, "algorithm", None)
        name = mapping.get(algo_key, getattr(tool_cls, "icon_name", "sparkle"))
        self.opt_icon.setPixmap(
            icon(name, color=theme.ACCENT, size=18).pixmap(18, 18))

    _CLOSED_KINDS = ("circle", "circle_mid", "circle_dda", "ellipse", "polygon")

    def _sync_fill_btn(self):
        """填充按钮显示【当前状态】（当前是什么就显示什么，点击切换）：
        选中闭合图元 → 跟随图元填充态；否则跟随工具提交态。"""
        s = self.canvas._selected_shape
        if s is not None and s.kind in self._CLOSED_KINDS:
            self.btn_fill.setEnabled(True)
            self.btn_fill.setText("填充" if s.fill else "描边")
        else:
            tool_fill = getattr(self._current_tool, "supports_fill", False) \
                if self._current_tool else False
            self.btn_fill.setEnabled(tool_fill)
            self.btn_fill.setText("填充" if getattr(self.canvas, "fill_mode", True)
                                  else "描边")

    def _on_fill_clicked(self):
        """填充按钮：优先作用于选中的闭合图元；否则切换工具提交态，
        并把新模式同步应用到该工具最近绘制的图元上——只改模式不动
        已画的图元，用户会以为切换没生效（画好的圆纹丝不动）。"""
        s = self.canvas._selected_shape
        if s is not None and s.kind in self._CLOSED_KINDS:
            self.canvas.set_shape_fill(s, not s.fill)
        else:
            new_mode = not getattr(self.canvas, "fill_mode", True)
            self.canvas.fill_mode = new_mode
            shapes = self.canvas.document.shapes
            kinds = getattr(self._current_tool, "applies_kinds", None)
            if shapes and kinds and shapes[-1].kind in kinds:
                self.canvas.set_shape_fill(shapes[-1], new_mode)
        self._sync_fill_btn()

    def _on_selection_changed(self, shape):
        """选中变化 → 填充按钮态刷新。"""
        self._sync_fill_btn()

    def _on_width(self, v: int):
        """线宽已随模拟像素体系固定为 1（一格=一像素），保留接口兼容。"""
        self.canvas.set_pen_width(v)

    # ==================================================================
    # 视图开关 / 模式 / 面板
    # ==================================================================
    def _toggle_view_attr(self, attr: str, on: bool, btn=None):
        setattr(self.canvas, attr, on)
        self.canvas.viewport().update()

    def _on_mode_changed(self, idx: int):
        # 双模式独立：应用/演示各有自己的画布与图元，切换只换栈页
        if idx == 1:
            self.demo_view.on_mode_entered()
        self.body_stack.setCurrentIndex(idx)
        self._on_document_changed()      # 按钮态随活动画布刷新

    _INPUT_WIDGETS = None

    def eventFilter(self, obj, event):
        """全局单键路由（焦点无关；输入框内打字不拦截）：

        空格=平移（按住）/ K=演示播放暂停 / 1~8=切工具 / V=选择 / E=橡皮擦 /
        Delete=删除选中 / +-=缩放步进 / ←→↑↓=演示单步或图元微调。
        Ctrl 组合键由 QShortcut 处理。
        另：_drag_widgets 里的容器（状态栏）空白处左键按下 = 拖动窗口。
        """
        from PySide6.QtCore import QEvent, Qt as Qt2
        if event.type() == QEvent.MouseButtonPress and \
                event.button() == Qt2.LeftButton and \
                obj in getattr(self, "_drag_widgets", ()):
            handle = self.windowHandle()
            if handle is not None:
                handle.startSystemMove()
            return False                  # 不拦截，保持原事件流
        if event.type() not in (QEvent.KeyPress, QEvent.KeyRelease):
            return super().eventFilter(obj, event)
        if self._is_input_widget(obj):
            return super().eventFilter(obj, event)   # 输入框内：按键属于文本
        key = event.key()

        # ---- 空格：任何模式下按住 = 平移 ----
        if key == Qt2.Key_Space and not event.isAutoRepeat():
            if event.type() == QEvent.KeyPress:
                self.canvas.press_space()
            else:
                self.canvas.release_space()
            return True

        # ---- 方向键：演示模式未选中 → 单步；选中图元 → 微调 ----
        if key in (Qt2.Key_Left, Qt2.Key_Right, Qt2.Key_Up, Qt2.Key_Down)                 and event.type() == QEvent.KeyPress and not event.isAutoRepeat():
            if self.body_stack.currentIndex() == 1 and                     self.canvas._selected_shape is None:
                if key in (Qt2.Key_Left, Qt2.Key_Right):
                    if key == Qt2.Key_Left:
                        self.demo_view.step_back()
                    else:
                        self.demo_view.step_forward()
                    return True
            if self.canvas._selected_shape is not None:
                d = {Qt2.Key_Left: (-1, 0), Qt2.Key_Right: (1, 0),
                     Qt2.Key_Up: (0, -1), Qt2.Key_Down: (0, 1)}[key]
                self.canvas.nudge_selected(*d)
                return True

        # ---- 其余单键只在按下时触发 ----
        if event.type() != QEvent.KeyPress or event.isAutoRepeat():
            return super().eventFilter(obj, event)
        if key == Qt2.Key_V:
            self._activate_select_tool()
            return True
        if key == Qt2.Key_E:
            self._activate_eraser_tool()
            return True
        if key == Qt2.Key_Delete:
            self._delete_selected()
            return True
        if key == Qt2.Key_K and self.body_stack.currentIndex() == 1:
            self.demo_view.play_pause()
            return True
        if key in (Qt2.Key_Plus, Qt2.Key_Equal):
            self.canvas.zoom_step(1.15)
            return True
        if key == Qt2.Key_Minus:
            self.canvas.zoom_step(1 / 1.15)
            return True
        if Qt2.Key_1 <= key <= Qt2.Key_9:
            idx = key - Qt2.Key_1
            if idx < len(self._tool_classes):
                self._activate_tool(idx)
                return True
        return super().eventFilter(obj, event)

    def _is_input_widget(self, obj) -> bool:
        """按键目标是否为输入类控件（空格/方向键留给控件自身）。"""
        from PySide6.QtWidgets import (QAbstractButton, QComboBox, QLineEdit,
                                       QListWidget, QSpinBox, QTextEdit)
        t = obj
        while t is not None:
            if isinstance(t, (QAbstractButton, QComboBox, QLineEdit,
                              QSpinBox, QTextEdit, QListWidget)):
                return True
            t = t.parent()
        return False

    def _activate_select_tool(self):
        """V：切到选择/移动工具。"""
        for i, cls in enumerate(self._tool_classes):
            if cls.__name__ == "SelectMoveTool":
                self._activate_tool(i)
                return

    def _show_help(self):
        """F1 / ?：快捷键速查表。"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
        dlg = QDialog(self)
        dlg.setWindowTitle("快捷键速查")
        dlg.setMinimumWidth(560)
        lay = QVBoxLayout(dlg)
        groups = [
            ("通用", [
                ("1 ~ 8", "切换工具（直线/圆/椭圆/多边形/直线对比/选择/填充多边形/橡皮擦）"),
                ("V", "选择 / 移动工具"),
                ("E", "橡皮擦"),
                ("Ctrl+Delete", "清空画布"),
                ("Ctrl+Z / Ctrl+Y", "撤销 / 重做"),
                ("Ctrl+0 / Ctrl+1", "适配窗口 / 100%"),
                ("Ctrl+S / Ctrl+Shift+S / Ctrl+O", "导出 PNG / 保存工程 / 打开工程"),
                ("Delete", "删除选中的图元"),
                ("Tab", "收起/展开两侧面板（应用模式）"),
                ("Esc", "取消进行中的绘制 / 移动"),
                ("方向键", "微调选中的图元（任意工具下）"),
                ("Shift + 拖拽", "约束：直线 45° 吸附 / 椭圆变正圆"),
                ("滚轮", "以指针为中心缩放"),
                ("空格 + 拖拽 / 中键拖拽", "平移画布（应用/演示模式）"),
                ("画布右键", "上下文菜单"),
                ("颜色卡 HEX", "单击复制 · 双击编辑 · 回车应用（对话框内）"),
            ]),
            ("演示模式", [
                ("空格", "播放 / 暂停"),
                ("← / →", "单步后退 / 前进"),
                ("点击模块目录", "选择算法演示页"),
                ("画布上直接绘制", "自动切换到对应算法页并回放"),
                ("选中图元后点填充", "追加填充阶段动画"),
            ]),
        ]
        for title, rows in groups:
            g = QLabel(f"<b style='color:{theme.ACCENT}; font-size:13px'>"
                       f"{title}</b>")
            g.setTextFormat(Qt.RichText)
            lay.addWidget(g)
            # 键帽样式：浅底色块 + 主题色文字（Qt 富文本不支持圆角边框，
            # 用 td 底色近似键帽）；说明列用 UI 字体，行距放宽
            table = ("<table width='100%' cellspacing='0' cellpadding='0'>")
            for k, d in rows:
                table += (
                    "<tr>"
                    f"<td width='150' style='padding:2px 6px'>"
                    f"<span style='background-color:{theme.ACCENT_TINT};"
                    f" color:{theme.ACCENT_PRESS}; font-weight:600'>"
                    f"{k}</span></td>"
                    f"<td style='color:{theme.TEXT_2}; padding:2px 0 2px 10px'>"
                    f"{d}</td>"
                    "</tr>")
            table += "</table>"
            lab = QLabel(table)
            lab.setTextFormat(Qt.RichText)
            lab.setStyleSheet(
                f"font-family: {theme.UI_FONT}; font-size: 13px;")
            lay.addWidget(lab)
        close = QPushButton("关闭")
        close.clicked.connect(dlg.accept)
        lay.addWidget(close, alignment=Qt.AlignRight)
        dlg.exec()

    def _toggle_panels(self):
        """Tab：沉浸模式（仅应用模式；收起/展开左右栏）。"""
        if self.body_stack.currentIndex() != 0:
            return
        body = self._app_page.layout()
        rail = body.itemAt(0).widget()
        right = body.itemAt(2).widget()
        rail.setVisible(not rail.isVisible())
        right.setVisible(not right.isVisible())

    # ==================================================================
    # 文件动作（工程 / 导出）
    # ==================================================================
    def _save_project(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存工程", "绘图.gpad", project_file.PROJECT_SUFFIX)
        if not path:
            return
        try:
            project_file.save_project(path, self.canvas.document.shapes)
            QMessageBox.information(self, "保存成功", f"工程已保存到:\n{path}")
        except OSError as e:
            QMessageBox.warning(self, "保存失败", f"写入失败:\n{e}")

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开工程", "", project_file.PROJECT_SUFFIX)
        if not path:
            return
        try:
            self.canvas.open_project(path)
            self._use_color(self.canvas.pen_color)   # 刷新颜色显示
        except Exception as e:                            # noqa: BLE001 统一提示
            QMessageBox.warning(self, "打开失败", f"无法读取工程文件:\n{e}")

    def _export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出画布", "canvas.png",
                                              "PNG 图片 (*.png)")
        if not path:
            return
        if self.canvas.save_image(path):
            QMessageBox.information(self, "导出成功", f"已保存到:\n{path}")
        else:
            QMessageBox.warning(self, "导出失败", "文件写入失败，请检查路径。")

    def _delete_selected(self):
        sel = self.canvas._selected_shape
        if sel is not None:
            self.canvas.set_selected_shape(None)
            self.canvas.remove_shape(sel)

    # ==================================================================
    # 画布右键菜单
    # ==================================================================
    def _show_canvas_menu(self, global_pos):
        menu = QMenu(self)
        menu.addAction("适配窗口", self.canvas.fit_view, "Ctrl+0")
        menu.addAction("缩放 100%", self.canvas.zoom_100, "Ctrl+1")
        menu.addSeparator()
        act_undo = menu.addAction("撤销", self.canvas.undo, "Ctrl+Z")
        act_undo.setEnabled(self.canvas.document.can_undo)
        act_redo = menu.addAction("重做", self.canvas.redo, "Ctrl+Y")
        act_redo.setEnabled(self.canvas.document.can_redo)
        menu.addSeparator()
        menu.addAction("清空画布", self.canvas.clear_all)
        menu.addAction("导出 PNG", self._export_png, "Ctrl+S")
        menu.exec(global_pos)

    # ==================================================================
    # 状态栏 / 按钮态刷新
    # ==================================================================
    def _on_cursor(self, x, y):
        self.lbl_pos.setText(f"坐标 ({x}, {y})")
        if self._current_tool:
            s = self._current_tool.status()
            self.lbl_hint.setText(s.replace("\n", "  ") if s else
                                  self._current_tool.cursor_hint)

    def _on_zoom(self, z):
        self.lbl_zoom.setText(f"缩放 {int(z * 100)}%")
        # 缩放滑杆反向同步（blockSignals 防 回写→再触发 死循环）：
        # 任何来源（滚轮/+−/适配窗口/滑杆自身）改动缩放都汇聚到这里
        if getattr(self, "zoom_slider", None) is not None:
            self.zoom_slider.blockSignals(True)
            self.zoom_slider.setValue(max(10, min(800, int(z * 100))))
            self.zoom_slider.blockSignals(False)
            self.zoom_lab.setText(f"{int(z * 100)}%")

    def _on_count(self, n):
        self.lbl_count.setText(f"图元 {n}")
        self.shape_panel.rebuild()

    def _on_document_changed(self):
        self.btn_undo.setEnabled(self.canvas.document.can_undo)
        self.btn_redo.setEnabled(self.canvas.document.can_redo)
        self.lbl_count.setText(f"图元 {len(self.canvas.document.shapes)}")
        self.shape_panel.rebuild()
        self._on_selection_changed(self.canvas._selected_shape)
