# -*- coding: utf-8 -*-
"""
=====================================================================
 ui/theme.py  —  设计系统唯一出处（色彩 token + 字体 + 全套 QSS）
=====================================================================
规范 4 节：整个软件的观感由本文件决定，其他任何地方不允许散落
setStyleSheet（色块类动态样式除外）。

设计语言：与模块一（归档 RGB/HSV 工具 v2.0）统一的现代浅色体系——
浅灰底 + 白卡片 + 蓝紫主题色 + 等宽字体数值 + 4px 间距网格。
=====================================================================
"""

# =====================================================================
# 色彩 token（规范 4.1）
# =====================================================================
BG_WINDOW   = "#F5F6F8"    # 窗口底
BG_SURROUND = "#EDEFF3"    # 画布衬底（桌面感）
CARD        = "#FFFFFF"    # 卡片
BORDER      = "#E7E9EF"    # 卡片/分隔线边框
PAPER_EDGE  = "#D9DEE7"    # 画布"纸"边缘

TEXT_1      = "#1F2329"    # 主文字
TEXT_2      = "#8A919F"    # 次要文字
TEXT_3      = "#B3BAC5"    # 禁用/占位
ICON_DEFAULT= "#5C6370"    # 图标默认色

ACCENT       = "#4F6EF7"   # 主题色（蓝紫，与归档统一）
ACCENT_HOVER = "#6B86FF"
ACCENT_PRESS = "#3D5AF1"
ACCENT_TINT  = "#EEF2FF"   # 选中浅底
HOVER_TINT   = "#F0F2F6"   # 悬停浅灰

SUCCESS = "#46A758"
WARNING = "#F5A623"
DANGER  = "#E5484D"

# 通道色（渐变滑块/演示层，规范 4.1）
CH_R, CH_G, CH_B = "#E5484D", "#46A758", "#3E63DD"
CH_H, CH_S, CH_V = "#F76B15", "#8E4EC6", "#687076"

PREVIEW_HEX = "#F76B15"    # 预览像素（橙）
DEMO_CURRENT = ACCENT       # 演示当前像素
MONO_FONT   = '"Consolas", "Courier New", monospace'
UI_FONT     = '"Microsoft YaHei UI", "Segoe UI", sans-serif'


# =====================================================================
# 全套 QSS
# 说明：QSS 里 {} 很多，为避免 f-string 双花括号地狱，
#       这里用 @TOKEN 占位 + 末尾统一替换。
# =====================================================================
_QSS = """
* { outline: none; }

QWidget {
    background-color: @BG_WINDOW;
    color: @TEXT_1;
    font-family: @UI_FONT;
    font-size: 13px;
}

/* ---------- 顶栏 ---------- */
QFrame#headerBar {
    background: @BG_WINDOW;
    border-bottom: 1px solid @BORDER;
}
QLabel#appTitle {
    font-size: 15px;
    font-weight: bold;
    color: @TEXT_1;
    background: transparent;
}
QLabel#appSub {
    font-size: 11px;
    color: @TEXT_2;
    background: transparent;
}

/* ---------- 卡片体系 ---------- */
QFrame#card {
    background: @CARD;
    border: 1px solid @BORDER;
    border-radius: 10px;
}
QLabel#cardTitle {
    color: @TEXT_2;
    font-size: 12px;
    font-weight: bold;
    background: transparent;
    letter-spacing: 1px;
}

/* ---------- 左侧图标工具栏 ---------- */
QFrame#rail {
    background: @CARD;
    border: 1px solid @BORDER;
    border-radius: 10px;
}
QToolButton#railBtn {
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 0;
}
QToolButton#railBtn:hover {
    background: @HOVER_TINT;
}
QToolButton#railBtn:checked {
    background: @ACCENT_TINT;
}

/* ---------- 工具选项条 ---------- */
QFrame#optionsBar {
    background: @CARD;
    border: 1px solid @BORDER;
    border-radius: 10px;
}
QLabel#optToolName {
    font-size: 13px;
    font-weight: bold;
    background: transparent;
}
QLabel#optDivider {
    color: @BORDER;
    background: @BORDER;
    max-width: 1px;
}
QLabel#optHint {
    color: @TEXT_2;
    font-size: 12px;
    background: transparent;
}

/* ---------- 通用按钮 ---------- */
QPushButton {
    background: @CARD;
    border: 1px solid @BORDER;
    border-radius: 6px;
    padding: 6px 12px;
    color: @TEXT_1;
}
QPushButton:hover {
    background: @HOVER_TINT;
    border-color: @ACCENT;
    color: @ACCENT;
}
QPushButton:pressed {
    background: @ACCENT_TINT;
}
QPushButton:disabled {
    color: @TEXT_3;
    border-color: @BORDER;
    background: @BG_WINDOW;
}
QPushButton#primaryBtn {
    background: @ACCENT;
    border: none;
    color: #FFFFFF;
    font-weight: bold;
}
QPushButton#primaryBtn:hover { background: @ACCENT_HOVER; }
QPushButton#primaryBtn:pressed { background: @ACCENT_PRESS; }

/* 顶栏图标按钮 */
QToolButton#headerBtn {
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px;
}
QToolButton#headerBtn:hover { background: @HOVER_TINT; }
QToolButton#headerBtn:pressed { background: @ACCENT_TINT; }
QToolButton#headerBtn:disabled { background: transparent; }

/* 开关胶囊（视图卡） */
QPushButton#toggleBtn {
    background: @HOVER_TINT;
    border: 1px solid @BORDER;
    border-radius: 10px;
    padding: 2px 0;
    color: @TEXT_2;
    font-size: 12px;
}
QPushButton#toggleBtn:checked {
    background: @ACCENT_TINT;
    border-color: @ACCENT;
    color: @ACCENT;
    font-weight: bold;
}

/* ---------- 分段控件（模式切换） ---------- */
QFrame#segHolder {
    background: #E9EBF0;
    border-radius: 15px;
}
QPushButton#segBtn {
    background: transparent;
    border: none;
    border-radius: 12px;
    padding: 5px 16px;
    color: @TEXT_2;
    font-weight: bold;
}
QPushButton#segBtn:checked {
    background: @CARD;
    color: @ACCENT;
}
QPushButton#segBtn:disabled {
    color: @TEXT_3;
}

/* ---------- 输入类控件（圆角统一） ---------- */
QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox, QDateEdit, QTimeEdit {
    background: #FFFFFF;
    border: 1px solid @BORDER;
    border-radius: 6px;
    padding: 3px 8px;
    color: @TEXT_1;
    selection-background-color: @ACCENT_TINT;
    selection-color: @ACCENT;
}
QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover, QComboBox:hover {
    border-color: #C9CED8;
}
QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus {
    border-color: @ACCENT;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    width: 16px;
    border: none;
    background: transparent;
}
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    background: @CARD;
    border: 1px solid @BORDER;
    border-radius: 6px;
    selection-background-color: @ACCENT_TINT;
    selection-color: @ACCENT;
}
QListWidget, QTreeWidget, QListView, QTreeView {
    background: transparent;
    border: none;
}

/* ---------- 演示模块目录（分节 + 演示页行） ---------- */
QFrame#flatCard {
    background: transparent;
    border: none;
}
QPushButton#pageRow {
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 6px 8px;
    text-align: left;
    color: @TEXT_1;
}
QPushButton#pageRow:hover {
    background: @HOVER_TINT;
}
QPushButton#pageRow:checked {
    background: @ACCENT_TINT;
    color: @ACCENT;
    font-weight: bold;
}
QPushButton#cardHeader:disabled {
    color: @TEXT_3;
}
QLabel#moduleHint {
    color: @TEXT_3;
    font-size: 12px;
}
QScrollArea {
    border: none;
    background: transparent;
}

/* ---------- 滑块 ---------- */
QSlider { background: transparent; }
QSlider::groove:horizontal {
    height: 6px;
    border-radius: 3px;
    background: @BORDER;
}
QSlider::handle:horizontal {
    background: #FFFFFF;
    width: 16px; height: 16px;
    margin: -5px 0;
    border-radius: 8px;
    border: 1px solid #C9CED8;
}
QSlider::handle:horizontal:hover {
    border-color: @ACCENT;
}
QSlider::sub-page:horizontal {
    background: transparent;
}

/* ---------- 图元列表 ---------- */
QListWidget#shapeList {
    background: transparent;
    border: none;
}
QListWidget#shapeList::item {
    height: 32px;
    border-radius: 6px;
    margin: 1px 0;
    color: @TEXT_1;
}
QListWidget#shapeList::item:selected {
    background: @ACCENT_TINT;
}
QListWidget#shapeList::item:hover:!selected {
    background: @HOVER_TINT;
}

/* ---------- 滚动条（纤细圆角） ---------- */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #C9CED8;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #AEB6C2; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #C9CED8;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background: #AEB6C2; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

/* ---------- 画布视口（整张无限画布统一白色） ---------- */
QGraphicsView {
    background: #FFFFFF;
    border: none;
}

/* ---------- 折叠卡片头 ---------- */
QPushButton#cardHeader {
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 3px 4px;
    text-align: left;
    font-weight: bold;
    font-size: 12px;
    color: @TEXT_2;
    letter-spacing: 1px;
}
QPushButton#cardHeader:hover {
    color: @ACCENT;
}

/* ---------- 右键菜单 ---------- */
QMenu {
    background: @CARD;
    border: 1px solid @BORDER;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 6px;
}
QMenu::item:selected {
    background: @ACCENT_TINT;
    color: @ACCENT;
}
QMenu::separator {
    height: 1px;
    background: @BORDER;
    margin: 4px 6px;
}

/* ---------- 状态栏 ---------- */
QStatusBar {
    background: transparent;
    border-top: 1px solid @BORDER;
    color: @TEXT_2;
}
QStatusBar::item { border: none; }
QStatusBar QLabel {
    color: @TEXT_2;
    font-family: @MONO_FONT;
    font-size: 12px;
    background: transparent;
    padding: 0 8px;
}

/* ---------- 其他 ---------- */
QToolTip {
    background: @CARD;
    color: @TEXT_1;
    border: 1px solid @BORDER;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
}
QLabel { color: @TEXT_1; background: transparent; }
QLabel#secondary { color: @TEXT_2; font-size: 12px; }
QLabel#mono { font-family: @MONO_FONT; font-weight: 600; }
"""


def build_qss() -> str:
    """把 @TOKEN 占位替换为真实 token 值，返回完整样式表。"""
    tokens = {
        "@BG_WINDOW": BG_WINDOW, "@BG_SURROUND": BG_SURROUND,
        "@CARD": CARD, "@BORDER": BORDER,
        "@TEXT_1": TEXT_1, "@TEXT_2": TEXT_2, "@TEXT_3": TEXT_3,
        "@ACCENT": ACCENT, "@ACCENT_HOVER": ACCENT_HOVER,
        "@ACCENT_PRESS": ACCENT_PRESS, "@ACCENT_TINT": ACCENT_TINT,
        "@HOVER_TINT": HOVER_TINT,
        "@UI_FONT": UI_FONT, "@MONO_FONT": MONO_FONT,
    }
    qss = _QSS
    # 长 token 先替换：@ACCENT 是 @ACCENT_TINT 的前缀，
    # 若先替换会把后者破坏成 "#4F6EF7_TINT" 这类非法颜色
    for k in sorted(tokens, key=len, reverse=True):
        qss = qss.replace(k, tokens[k])
    return qss


def apply(app):
    """给 QApplication 挂全套样式（main.py 调用一次即可）。"""
    app.setStyleSheet(build_qss())
