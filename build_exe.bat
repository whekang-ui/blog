@echo off
REM ============================================================
REM  네이버 블로그 자동화 - Windows .exe 빌드 스크립트 (원클릭)
REM  사용법: 이 파일을 더블클릭하거나, cmd 에서 build_exe.bat 실행
REM ============================================================
setlocal
cd /d "%~dp0"
chcp 65001 >nul

echo [1/4] 필수 라이브러리 설치...
python -m pip install -r requirements.txt || goto :error
python -m pip install pyinstaller || goto :error

echo [2/4] 이전 빌드 정리...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo [3/4] PyInstaller 빌드...
python -m PyInstaller packaging\naver_blog.spec || goto :error

echo [4/4] 배포 폴더 구성(설정/예시 파일 복사)...
copy /y config.example.json dist\ >nul
copy /y .env.example dist\ >nul
copy /y README.md dist\ >nul
if not exist dist\assets mkdir dist\assets
if not exist dist\user_photos mkdir dist\user_photos

echo.
echo ============================================================
echo  완료!  dist\NaverBlogAutomation.exe 가 만들어졌습니다.
echo.
echo  실행 전 dist 폴더 안에서 아래를 준비하세요:
echo   1) .env.example  -^>  .env  로 복사 후 ANTHROPIC_API_KEY 입력
echo   2) config.example.json  -^>  config.json  으로 복사 후 정보 입력
echo   3) assets\ 폴더에 에디터 버튼 캡처 PNG 넣기(발행 자동화용)
echo  그런 다음 NaverBlogAutomation.exe 더블클릭!
echo ============================================================
goto :eof

:error
echo.
echo [오류] 빌드 중 문제가 발생했습니다. 위 메시지를 확인하세요.
exit /b 1
