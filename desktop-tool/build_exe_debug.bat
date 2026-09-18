@echo off
rem ============================================================
rem  Debug build: console window stays open and shows errors.
rem  Use this when AuditTool.exe does not start - the console
rem  version prints the actual error message.
rem  Output: dist\AuditTool_debug.exe
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller openpyxl || goto :error
python -m PyInstaller --noconfirm --clean --onefile --console --name AuditTool_debug ^
  --exclude-module xlwings --exclude-module win32com --exclude-module pandas ^
  run_app.py || goto :error
echo.
echo   dist\AuditTool_debug.exe created.
echo   Run it from cmd to see error messages:
echo     dist\AuditTool_debug.exe
pause
exit /b 0
:error
echo Build FAILED.
pause
exit /b 1
