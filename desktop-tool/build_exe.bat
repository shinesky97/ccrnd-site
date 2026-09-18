@echo off
rem ============================================================
rem  Build AuditTool.exe (Windows only)
rem  Usage: double-click this file, or run in cmd:
rem     build_exe.bat
rem  Output: dist\AuditTool.exe  (single file, no console window)
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"

echo [1/3] Installing build dependencies...
pip install --upgrade pyinstaller openpyxl xlwings || goto :error

echo [2/3] Building exe (this can take a few minutes)...
pyinstaller --noconfirm --clean --onefile --windowed --name AuditTool ^
  --hidden-import xlwings --collect-submodules xlwings ^
  run_app.py || goto :error

echo [3/3] Done.
echo.
echo   dist\AuditTool.exe  created.
echo   Copy it anywhere (e.g. Desktop) and double-click to run.
echo.
pause
exit /b 0

:error
echo.
echo Build FAILED. Check the messages above.
pause
exit /b 1
