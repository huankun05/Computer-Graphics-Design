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

# 播放速度范围（步/秒）。
# 下限取 0.1：一步 10 秒——判定/求交这类演算步骤有时必须逐帧盯着看，
# 整数档（最低 1 步/秒）仍嫌快（用户反馈："在最低速度下感觉都比较快"）。
MIN_FPS = 0.1
MAX_FPS = 240.0


class DemoPlayer(QObject):
    """步骤流播放器：QTimer 驱动的索引推进器。"""

    index_changed = Signal(int, bool)
    state_changed = Signal(bool)
    finished = Signal()              # 播放到最后一步（供宿主做收尾，如恢复图元显示）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.steps = []
        self.index = -1                 # -1 = 尚未开始
        self.fps = 30.0                 # 步/秒（默认放慢，单步演算看得清）
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
        self._timer.start(self._interval())
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

    def set_fps(self, fps):
        """设置播放速度（步/秒）。支持小数：0.1 步/秒 = 每步 10 秒。"""
        self.fps = max(MIN_FPS, min(MAX_FPS, float(fps)))
        if self._timer.isActive():      # 播放中调速立即生效
            self._timer.start(self._interval())

    def _interval(self) -> int:
        """一步的间隔毫秒数。

        最小 10ms：速度再高也不能把事件循环打爆（0 间隔会卡死界面）。
        """
        return max(10, int(round(1000.0 / max(self.fps, MIN_FPS))))

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
