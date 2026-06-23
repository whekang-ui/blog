# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 스펙 — 네이버 블로그 자동화 GUI 를 단일 .exe 로 빌드.

빌드(Windows): 프로젝트 루트에서
    pip install pyinstaller
    pyinstaller packaging/naver_blog.spec
산출물: dist/NaverBlogAutomation.exe

참고:
- 진입점은 run_gui.py.
- onefile + windowed(콘솔창 없음).
- config.json/.env/assets/ 는 exe 에 포함하지 않는다(사용자가 exe 옆에 두고 수정). config.py 가
  동결 시 exe 폴더를 기준으로 이들을 찾는다.
"""

import sys
from pathlib import Path

# 동적 import 라 PyInstaller 가 놓칠 수 있는 모듈을 명시.
hiddenimports = [
    "anthropic",
    "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
    "pyautogui",
    "pyperclip",
    "pygetwindow",
    "cv2",
    "dotenv",
    "requests",
    # GUI
    "tkinter", "tkinter.ttk", "tkinter.messagebox",
]

# 용량을 줄이기 위해 미사용 대형 패키지 제외.
excludes = ["matplotlib", "numpy.testing", "pytest"]

# 사용자가 채운 설정을 exe 안에 구워넣는다(있을 때만). 옆에 같은 파일이 있으면 그게 우선.
# (공개 저장소에는 .env/config.json 이 커밋되지 않으므로, 빌드하는 PC의 실제 파일만 포함됨)
import os
datas = []
for _f in (".env", "config.json"):
    if os.path.exists(_f):
        datas.append((_f, "."))

block_cipher = None

a = Analysis(
    ["run_gui.py"],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="NaverBlogAutomation",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,        # GUI 앱이므로 콘솔창 숨김
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="packaging/app.ico",  # 아이콘이 있으면 주석 해제
)
