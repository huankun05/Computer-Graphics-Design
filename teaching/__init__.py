# -*- coding: utf-8 -*-
"""
teaching — 演示模式引擎（通用，与具体算法解耦）。

组成：
  steps.py 契约在 algorithms/（Step 步骤流）；
  player.py       播放器：播放/暂停/单步/重放/调速
  monitor.py      决策项监视面板（通用 key-value）
  pixel_layer.py  画布像素演示层（已生成染色 + 当前步闪烁）
任何算法只要输出 list[Step]，三者即自动可用（规范契约①）。
"""
