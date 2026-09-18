@echo off
rem ============================================================
rem  Build AuditTool.exe (Windows only)
rem  Usage: double-click this file.
rem  Output: dist\AuditTool.exe  (single file, no console window)
rem
rem  Note: xlwings is intentionally EXCLUDED from the exe for
rem  build reliability. The exe uses the openpyxl engine.
rem  To use the Excel(xlwings) engine, run via 실행.bat instead.
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"

echo [1/3] Installing build dependencies...
python -m pip install --upgrade pyinstaller openpyxl || goto :error

echo [2/3] Building exe (this can take a few minutes)...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name AuditTool ^
  --exclude-module xlwings --exclude-module win32com --exclude-module pandas ^
  run_app.py || goto :error

echo [3/3] Done.
echo.
echo   dist\AuditTool.exe  created.
echo   Copy it anywhere (e.g. Desktop) and double-click to run.
echo   If Windows SmartScreen blocks it: "추가 정보" - "실행" 클릭.
echo.
pause
exit /b 0

:error
echo.
echo Build FAILED. Check the messages above.
pause
exit /b 1
