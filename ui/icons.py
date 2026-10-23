# -*- coding: utf-8 -*-
"""
=====================================================================
 ui/icons.py  —  矢量图标系统（内嵌 SVG，规范 4.4 / 决策 D9）
=====================================================================
所有图标为 Feather 风格线性 SVG（viewBox 24，圆头描边），代码内嵌
字符串，经 QSvgRenderer 渲染为高分辨率 QIcon（4x 物理像素，任意
DPI 与缩放下都清晰）。无外部资源文件依赖。

用法：
    from ui.icons import icon
    btn.setIcon(icon("circle"))                  # 默认灰
    btn.setIcon(icon("circle", color=ACCENT))    # 指定颜色（选中态）
=====================================================================
"""

from PySide6.QtCore import Qt, QByteArray, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

# 图标默认色（与 theme.ICON_DEFAULT 一致；此处独立常量避免循环导入）
_DEFAULT = "#5C6370"

# ---------------------------------------------------------------------
# 图标路径定义（stroke 内容片段；stroke 颜色由模板注入）
# ---------------------------------------------------------------------
_PATHS = {
    # 应用标志：钢笔工具笔尖
    "logo": '<path d="M12 19l7-7 3 3-7 7-3-3z"/>'
            '<path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/>'
            '<path d="M2 2l7.586 7.586"/><circle cx="11" cy="11" r="2"/>',
    # 直线（两端点圆点）
    "line": '<line x1="5" y1="19" x2="19" y2="5"/>'
            '<circle cx="5" cy="19" r="1.4"/><circle cx="19" cy="5" r="1.4"/>',
    "circle": '<circle cx="12" cy="12" r="8"/>',
    "ellipse": '<ellipse cx="12" cy="12" rx="9" ry="6"/>',
    "polygon": '<polygon points="12 3 21 9.5 17.5 20 6.5 20 3 9.5"/>',
    # 填充（水滴）
    "fill": '<path d="M12 2.7s6 6.3 6 10.3a6 6 0 0 1-12 0c0-4 6-10.3 6-10.3z"/>',
    "undo": '<polyline points="3 7 3 13 9 13"/>'
            '<path d="M21 17a9 9 0 0 0-15-6.7L3 13"/>',
    "redo": '<polyline points="21 7 21 13 15 13"/>'
            '<path d="M3 17a9 9 0 0 1 15-6.7L21 13"/>',
    "trash": '<polyline points="3 6 5 6 21 6"/>'
             '<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>'
             '<path d="M10 11v6"/><path d="M14 11v6"/>'
             '<path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>',
    "open": '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    "archive": '<path d="M21 8v13H3V8"/><path d="M1 3h22v5H1z"/><path d="M10 12h4"/>',
    "image": '<rect x="3" y="3" width="18" height="18" rx="2"/>'
             '<circle cx="8.5" cy="8.5" r="1.5"/>'
             '<path d="M21 15l-5-5L5 21"/>',
    "grid": '<rect x="3" y="3" width="18" height="18" rx="2"/>'
            '<path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>',
    "axis": '<path d="M12 2v20"/><path d="M2 12h20"/>'
            '<circle cx="12" cy="12" r="7" stroke-dasharray="2 3"/>',
    "fit": '<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M16 3h3a2 2 0 0 1 2 2v3"/>'
           '<path d="M8 21H5a2 2 0 0 1-2-2v-3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>',
    "zoom100": '<circle cx="11" cy="11" r="7"/>'
               '<path d="M21 21l-4.3-4.3"/><path d="M8 11h6"/>',
    "zoom-in": '<circle cx="11" cy="11" r="7"/>'
               '<path d="M21 21l-4.3-4.3"/><path d="M8 11h6"/><path d="M11 8v6"/>',
    "zoom-out": '<circle cx="11" cy="11" r="7"/>'
                '<path d="M21 21l-4.3-4.3"/><path d="M8 11h6"/>',
    # 演示模式播放控制（阶段四使用，先备齐）
    "play": '<polygon points="7 4 20 12 7 20"/>',
    "pause": '<line x1="9" y1="5" x2="9" y2="19"/><line x1="15" y1="5" x2="15" y2="19"/>',
    "step-back": '<polygon points="19 20 9 12 19 4"/><line x1="5" y1="19" x2="5" y2="5"/>',
    "step-fwd": '<polygon points="5 4 15 12 5 20"/><line x1="19" y1="5" x2="19" y2="19"/>',
    "replay": '<polyline points="1 4 1 10 7 10"/>'
              '<path d="M3.5 15a9 9 0 1 0 2-9.4L1 10"/>',
    "compare": '<rect x="3" y="3" width="13" height="13" rx="2"/>'
               '<rect x="8" y="8" width="13" height="13" rx="2"/>',
    "palette": '<path d="M12 3a9 9 0 1 0 0 18h1a2 2 0 0 0 0-4h-1a1 1 0 0 1 0-2h5a4 4 0 0 0 4-4c0-4.4-4-8-9-8z"/>'
               '<circle cx="7.5" cy="10.5" r="1"/><circle cx="12" cy="7.5" r="1"/>'
               '<circle cx="16.5" cy="10.5" r="1"/>',
    "eye": '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>'
           '<circle cx="12" cy="12" r="3"/>',
    "eye-off": '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>'
               '<path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>'
               '<path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>',
    "eraser": '<path d="M20 20H9L4 15a2 2 0 0 1 0-2.8L12.2 4a2 2 0 0 1 2.8 0l5 5a2 2 0 0 1 0 2.8L13 19"/>'
              '<path d="M6.5 10.5l7 7"/>',
    "cursor": '<path d="M4 3l7.07 16.97 2.51-7.39 7.39-2.51L4 3z"/>',
    "chev-down": '<polyline points="6 9 12 15 18 9"/>',
    "chev-up": '<polyline points="6 15 12 9 18 15"/>',
    "sparkle": '<path d="M12 3l2.2 5.2L19.5 10l-5.3 1.8L12 17l-2.2-5.2L4.5 10l5.3-1.8z"/>',
}


def _svg(content: str, color: str, stroke: float) -> str:
    """包上 SVG 外壳（描边圆头，fill 全部透明）。"""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="{stroke}" '
            f'stroke-linecap="round" stroke-linejoin="round">{content}</svg>')


def icon(name: str, color: str = _DEFAULT, size: int = 20,
         stroke: float = 2.0) -> QIcon:
    """
    按名称生成 QIcon。
    渲染在 4x 物理分辨率上再以 DevicePixelRatio=4 声明，
    保证高 DPI 缩放（125%/150%）下边缘锐利。
    """
    scale = 4
    px = size * scale
    renderer = QSvgRenderer(QByteArray(_svg(_PATHS[name], color, stroke).encode()))
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    renderer.render(p, QRectF(0, 0, px, px))
    p.end()
    pm.setDevicePixelRatio(scale)
    return QIcon(pm)


def has_icon(name: str) -> bool:
    """模块声明 icon 键名时先检查（不存在则回退默认图标）。"""
    return name in _PATHS
