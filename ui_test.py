# -*- coding: utf-8 -*-
"""离屏截主窗口 UI 图。"""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from ui.main_window import MainWindow
from main import LIGHT_QSS

app = QApplication(sys.argv)
app.setStyleSheet(LIGHT_QSS)
win = MainWindow()
win.resize(1280, 800)
win.show()

# 等事件循环跑一轮后截图
def shot():
    pix = win.grab()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "运行截图", "test_00_主界面初始.png")
    pix.save(out)
    print("saved:", out)
    app.quit()

QTimer.singleShot(500, shot)
sys.exit(app.exec())
