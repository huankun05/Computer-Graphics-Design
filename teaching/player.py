# -*- coding: utf-8 -*-
"""
=====================================================================
 teaching/player.py  —  算法步骤播放器（演示模式的心脏）
=====================================================================
只认识 list[Step]（契约①），与具体算法完全解耦——任何算法的步骤流
装进来即获得：播放/暂停/单步前进后退/重放/调速/跳转。

信号：
  index_changed(int, bool)  当前步索引变化；(index, 是否增量前进)
                            —— 增量前进时叠层只 advance 一步（O(步)），
                               回退/跳转时视图层整层重建（罕见路径）
  state_changed(bool)       播放/暂停态（切换播放按钮图标）
=====================================================================
"""

from PySide6.QtCore import QObject, QTimer, Signal


class DemoPlayer(QObject):
    """步骤流播放器：QTimer 驱动的索引推进器。"""

    index_changed = Signal(int, bool)
    state_changed = Signal(bool)
    finished = Signal()              # 播放到最后一步（供宿主做收尾，如恢复图元显示）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.steps = []
        self.index = -1                 # -1 = 尚未开始
        self.fps = 60                   # 步/秒
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    def load(self, steps):
        """装入新的步骤流（自动暂停并归零）。"""
        self.pause()
        self.steps = steps
        self._set_index(-1)

    def play(self):
        if not self.steps:
            return
        if self.index >= len(self.steps) - 1:
            self._set_index(0)          # 播到底再按 = 从头播放
        self._timer.start(max(1, int(1000 / self.fps)))
        self.state_changed.emit(True)

    def pause(self):
        if self._timer.isActive():
            self._timer.stop()
            self.state_changed.emit(False)

    def toggle(self):
        self.pause() if self._timer.isActive() else self.play()

    def extend(self, more_steps):
        """追加步骤（如填充阶段），从当前播放位置继续。"""
        self.steps = list(self.steps) + list(more_steps)

    def replay(self):
        self._set_index(0)
        self.play()

    # ------------------------------------------------------------------
    def step_forward(self):
        """单步前进（暂停状态下）。"""
        self.pause()
        self._set_index(min(self.index + 1, len(self.steps) - 1))

    def step_back(self):
        """单步回退（暂停状态下，视图层整层重建）。"""
        self.pause()
        self._set_index(max(self.index - 1, -1))

    def to_end(self):
        self.pause()
        self._set_index(len(self.steps) - 1)

    def set_fps(self, fps: int):
        self.fps = max(1, int(fps))
        if self._timer.isActive():      # 播放中调速立即生效
            self._timer.start(max(1, int(1000 / self.fps)))

    @property
    def is_playing(self) -> bool:
        return self._timer.isActive()

    # ------------------------------------------------------------------
    def _tick(self):
        if self.index >= len(self.steps) - 1:
            self.pause()                # 播完停在最后一步（保持全亮）
            self.finished.emit()
            return
        self._set_index(self.index + 1)

    def _set_index(self, i: int):
        i = max(-1, min(i, len(self.steps) - 1))
        incremental = (i == self.index + 1)   # 恰好前进一步 → 视图层可增量
        self.index = i
        self.index_changed.emit(i, incremental)
