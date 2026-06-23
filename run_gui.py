"""PyInstaller .exe 진입점.

`python -m src.gui` 는 패키지 상대임포트를 쓰므로 PyInstaller 의 단일 스크립트 진입점으로는
부적합하다. 이 파일을 진입점으로 삼아 GUI 를 띄운다.

개발 중 실행:  python run_gui.py
빌드:          build_exe.bat  (내부에서 packaging/naver_blog.spec 사용)
"""

from __future__ import annotations

from src.gui import main

if __name__ == "__main__":
    raise SystemExit(main())
