# -*- coding: utf-8 -*-
"""
=====================================================================
 main.py  —  图形画板入口
=====================================================================
职责极薄：高 DPI 策略 + 挂载主题（ui/theme.py 设计系统）+ 启动主窗口。
=====================================================================
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui import theme


def main():
    # 高 DPI 缩放按系统实际倍率透传（125%/150% 屏不模糊）
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    # 基底字体给明确 point 字号：Windows 系统默认字体是像素字号
    # （pointSize=-1），QSS 的 font-size:XXpx 应用时 Qt 内部换算会
    # 反复告警 "Point size <= 0 (-1)"
    app.setFont(QFont(theme.UI_FONT, 10))
    theme.apply(app)                 # 全套设计系统（token + QSS，规范 4 节）
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
