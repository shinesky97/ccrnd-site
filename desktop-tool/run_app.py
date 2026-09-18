# -*- coding: utf-8 -*-
"""exe 진입점 — PyInstaller 빌드 대상. GUI를 실행한다.

시작 단계 오류(모듈 누락 등)도 반드시 사용자에게 보이도록:
- exe 옆에 audit_tool_error.log 기록
- 팝업(messagebox)으로 오류 표시
"""
import os
import sys
import traceback


def _error_log_path():
    if getattr(sys, 'frozen', False):          # PyInstaller exe
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'audit_tool_error.log')


def _report_error(err_text):
    path = _error_log_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(err_text)
    except OSError:
        path = '(로그 저장 실패)'
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showerror(
            '외감 자동화 도구 — 실행 오류',
            f'프로그램 시작 중 오류가 발생했습니다.\n\n'
            f'오류 로그: {path}\n\n{err_text[-1200:]}')
        root.destroy()
    except Exception:
        print(err_text)
        try:
            input('\n[Enter]를 누르면 종료합니다...')
        except EOFError:
            pass


def main():
    try:
        from audit_tool.gui import main as gui_main
        gui_main()
    except Exception:
        _report_error(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
