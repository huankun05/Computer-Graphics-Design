# -*- mode: python ; coding: utf-8 -*-


# 注意：modules/ 由注册表动态 import（importlib），必须显式声明 hiddenimports，
# 否则打包后的程序找不到课程模块（模块目录为空）。
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'modules',                             # 课程模块包（registry 动态扫描）
        'modules.module01_color.module',       # 模块一：颜色模型（动态注册）
        'modules.module02_primitives.module',  # 模块二：基本图元（动态注册）
        'PySide6.QtSvg',                       # SVG 矢量图标渲染
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='图形画板',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
