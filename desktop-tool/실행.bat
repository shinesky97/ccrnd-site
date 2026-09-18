@echo off
rem ============================================================
rem  exe 빌드 없이 바로 실행 (Python 필요)
rem  처음 한 번은 라이브러리 설치 때문에 시간이 걸릴 수 있습니다.
rem  Excel이 설치된 PC면 xlwings 엔진(서식·도형 완전 보존)을 사용합니다.
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"
python -m pip install --quiet openpyxl xlwings
python run_app.py
if errorlevel 1 pause
