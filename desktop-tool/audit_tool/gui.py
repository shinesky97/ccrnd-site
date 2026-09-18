# -*- coding: utf-8 -*-
"""tkinter GUI — [① 초기세팅] [② 진행현황] 두 탭.

실행: python -m audit_tool.gui
CLI와 동일한 엔진을 사용한다. (이 파일은 Windows에서 동작 확인 필요)
"""
import json
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import decisions, identify, progress, runner


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('외감 실무 자동화 도구')
        self.geometry('880x640')
        self.report_callback_exception = self._on_error   # 버튼 동작 중 오류도 표시
        nb = ttk.Notebook(self)
        nb.pack(fill='both', expand=True)
        self.tab_roll = ttk.Frame(nb)
        self.tab_prog = ttk.Frame(nb)
        nb.add(self.tab_roll, text='① 초기세팅 (이월)')
        nb.add(self.tab_prog, text='② 진행현황')
        self._build_roll_tab()
        self._build_prog_tab()

    def _on_error(self, exc_type, exc, tb):
        import traceback
        err = ''.join(traceback.format_exception(exc_type, exc, tb))
        try:
            self._println('\n✘ 오류 발생:\n' + err)
        except Exception:
            pass
        messagebox.showerror('오류', str(exc) + '\n\n(상세 내용은 로그 창 참조)')

    # ---------------- 초기세팅 탭 ----------------
    def _build_roll_tab(self):
        f = self.tab_roll
        top = ttk.Frame(f); top.pack(fill='x', padx=10, pady=8)
        ttk.Label(top, text='대상 폴더:').pack(side='left')
        self.folder_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.folder_var, width=70).pack(side='left', padx=6)
        ttk.Button(top, text='찾기', command=self._pick_folder).pack(side='left')

        btns = ttk.Frame(f); btns.pack(fill='x', padx=10)
        run_btn = ttk.Button(btns, text='▶ 전체 실행 (식별→이월→주입)', command=self._run_all)
        run_btn.pack(side='left')
        ttk.Separator(btns, orient='vertical').pack(side='left', fill='y', padx=8)
        ttk.Button(btns, text='파일 식별', command=self._identify).pack(side='left')
        ttk.Button(btns, text='결정값 입력', command=self._decisions).pack(side='left', padx=4)
        ttk.Button(btns, text='이월 미리보기', command=lambda: self._roll(False)).pack(side='left')
        ttk.Button(btns, text='이월 실행', command=lambda: self._roll(True)).pack(side='left', padx=4)
        ttk.Button(btns, text='숫자 주입', command=self._inject).pack(side='left')

        self.log = tk.Text(f, wrap='word', height=28)
        self.log.pack(fill='both', expand=True, padx=10, pady=8)

    def _pick_folder(self):
        d = filedialog.askdirectory(title='당기 외감 폴더 선택')
        if d:
            self.folder_var.set(d)

    def _println(self, s=''):
        self.log.insert('end', s + '\n')
        self.log.see('end')
        self.update_idletasks()

    def _identify(self):
        folder = self.folder_var.get()
        if not folder:
            return messagebox.showwarning('안내', '폴더를 먼저 선택하십시오.')
        self._println('=== 파일 식별 ===')
        scan = identify.scan_folder(folder)
        self._println(identify.summarize(scan))

    def _decisions(self):
        folder = self.folder_var.get()
        if not folder:
            return messagebox.showwarning('안내', '폴더를 먼저 선택하십시오.')
        dec = decisions.load(folder)
        if dec is None:
            scan = identify.scan_folder(folder)
            dec = decisions.template(prefill=decisions.prefill_from_scan(scan))
            path = decisions.save(folder, dec)
            self._println(f'결정값 파일을 생성했습니다: {path}')
        DecisionDialog(self, folder, dec, on_saved=self._println)

    def _roll(self, execute):
        folder = self.folder_var.get()
        if not folder:
            return messagebox.showwarning('안내', '폴더를 먼저 선택하십시오.')
        dec = decisions.load(folder)
        if dec is None:
            return messagebox.showwarning('안내', "먼저 '결정값 입력/확인'을 실행하십시오.")
        missing, errors = decisions.validate_pre(dec)
        if missing or errors:
            for m in missing:
                self._println(f'✋ 사전 결정값 미입력: {m}')
            for e in errors:
                self._println(f'✘ {e}')
            return
        plans, dsd_job, problems = runner.build_plans(folder, dec)
        self._println(runner.dry_run_report(plans, dsd_job, problems))
        if not execute:
            return
        if problems:
            return messagebox.showerror('실행 불가', '해결 필요 항목이 있습니다. 로그를 확인하십시오.')
        if not messagebox.askyesno('실행 확인',
                                   '위 Dry-run 내용대로 당기 파일을 생성합니다.\n'
                                   '원본은 수정되지 않습니다. 진행할까요?'):
            return
        threading.Thread(target=lambda: runner.execute(
            folder, dec, plans, dsd_job, log=self._println), daemon=True).start()

    def _run_all(self):
        """원클릭: 식별 → 결정값 검증 → 이월(확인) → 주입(확인)."""
        folder = self.folder_var.get()
        if not folder:
            return messagebox.showwarning('안내', '폴더를 먼저 선택하십시오.')
        self.log.delete('1.0', 'end')
        res = runner.run_all(folder, prefer_excel=True, log=self._println,
                             confirm=lambda m: messagebox.askyesno('확인', m))
        if res['status'] == 'need_decisions':
            self._println('\n→ 결정값 입력 창을 엽니다. 저장 후 [▶ 전체 실행]을 다시 누르십시오.')
            DecisionDialog(self, folder, decisions.load(folder), on_saved=self._println)
        elif res['status'] == 'done':
            messagebox.showinfo('완료', '전체 작업이 끝났습니다.\n'
                                '생성물과 _audit_tool/주입리포트를 확인하십시오.\n'
                                'DSD는 DART 편집기에서 열어 확인이 필요합니다.')

    def _inject(self):
        from . import inject as inject_mod
        folder = self.folder_var.get()
        if not folder:
            return messagebox.showwarning('안내', '폴더를 먼저 선택하십시오.')
        dec = decisions.load(folder)
        if dec is None or not dec['사전'].get('당기_연도'):
            return messagebox.showwarning('안내', '결정값(당기_연도)을 먼저 입력하십시오.')
        res = inject_mod.run_for_folder(folder, dec, execute=False, log=self._println)
        if res['status'] != 'dry_run':
            return
        if not messagebox.askyesno('주입 실행',
                                   f"{res['ops']}개 항목을 정산표 당기 열에 주입합니다.\n"
                                   '대상 파일은 백업 후 수정됩니다. 진행할까요?'):
            return
        inject_mod.run_for_folder(folder, dec, execute=True, log=self._println)

    # ---------------- 진행현황 탭 ----------------
    def _build_prog_tab(self):
        f = self.tab_prog
        top = ttk.Frame(f); top.pack(fill='x', padx=10, pady=8)
        ttk.Label(top, text='관리 루트(C 회계감사):').pack(side='left')
        self.root_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.root_var, width=55).pack(side='left', padx=6)
        ttk.Button(top, text='찾기', command=self._pick_root).pack(side='left')
        ttk.Label(top, text='연도:').pack(side='left', padx=(12, 2))
        self.year_var = tk.StringVar(value='')
        ttk.Entry(top, textvariable=self.year_var, width=6).pack(side='left')
        ttk.Button(top, text='업체 스캔', command=self._scan_clients).pack(side='left', padx=6)
        ttk.Button(top, text='대시보드 생성', command=self._dashboard).pack(side='left')

        mid = ttk.Frame(f); mid.pack(fill='both', expand=True, padx=10, pady=6)
        self.tree = ttk.Treeview(mid, columns=('company', 'stage'), show='headings', height=18)
        self.tree.heading('company', text='회사')
        self.tree.heading('stage', text='현재 단계(확정)')
        self.tree.pack(side='left', fill='both', expand=True)

        right = ttk.Frame(mid); right.pack(side='left', fill='y', padx=8)
        ttk.Label(right, text='단계 확정:').pack(anchor='w')
        for i, s in enumerate(progress.STAGES):
            ttk.Button(right, text=f'{i+1}. {s}', width=18,
                       command=lambda i=i: self._set_stage(i)).pack(anchor='w', pady=1)

    def _pick_root(self):
        d = filedialog.askdirectory(title='C 회계감사 루트 선택')
        if d:
            self.root_var.set(d)

    def _scan_clients(self):
        root = self.root_var.get()
        if not root:
            return
        state = progress.load_state(root)
        year = self.year_var.get()
        self.tree.delete(*self.tree.get_children())
        for c in progress.scan_clients(root):
            key = f"{c['code']}:{year}"
            st = state['clients'].get(key, {}).get('stage')
            label = f"{st+1}.{progress.STAGES[st]}" if st is not None else '-'
            self.tree.insert('', 'end', iid=c['code'], values=(f"{c['code']} {c['company']}", label))

    def _set_stage(self, idx):
        sel = self.tree.selection()
        root, year = self.root_var.get(), self.year_var.get()
        if not sel or not root or not year:
            return messagebox.showwarning('안내', '업체 선택·루트·연도를 확인하십시오.')
        progress.set_stage(root, sel[0], year, idx)
        self._scan_clients()

    def _dashboard(self):
        root, year = self.root_var.get(), self.year_var.get()
        if not root or not year:
            return
        out = progress.dashboard_html(root, year)
        messagebox.showinfo('완료', f'대시보드 생성:\n{out}')
        try:
            os.startfile(out)  # Windows
        except (AttributeError, OSError):
            pass


class DecisionDialog(tk.Toplevel):
    """결정값 입력 폼 — 각 항목에 '무엇을 결정하는지' 설명 표시."""

    def __init__(self, master, folder, dec, on_saved=None):
        super().__init__(master)
        self.title('결정값 입력 (프로그램은 결정하지 않습니다)')
        self.folder, self.dec, self.on_saved = folder, dec, on_saved
        self.vars = {}
        row = 0
        ttk.Label(self, text='[사전 결정값 — 초기세팅 실행에 필수]',
                  font=('', 10, 'bold')).grid(row=row, column=0, columnspan=3,
                                              sticky='w', padx=8, pady=(8, 2)); row += 1
        for key, desc in decisions.PRE_FIELDS:
            ttk.Label(self, text=key).grid(row=row, column=0, sticky='w', padx=8)
            v = tk.StringVar(value='' if dec['사전'].get(key) is None else str(dec['사전'][key]))
            self.vars[('사전', key)] = v
            ttk.Entry(self, textvariable=v, width=24).grid(row=row, column=1, padx=4)
            ttk.Label(self, text=desc, foreground='#57606a').grid(row=row, column=2, sticky='w')
            row += 1
        ttk.Label(self, text='[사후 결정값 — 감사판단: 보고서 단계 전 입력. 기본값 없음]',
                  font=('', 10, 'bold')).grid(row=row, column=0, columnspan=3,
                                              sticky='w', padx=8, pady=(10, 2)); row += 1
        for key, desc in decisions.POST_FIELDS:
            ttk.Label(self, text=key).grid(row=row, column=0, sticky='w', padx=8)
            v = tk.StringVar(value='' if dec['사후'].get(key) is None else str(dec['사후'][key]))
            self.vars[('사후', key)] = v
            ttk.Entry(self, textvariable=v, width=24).grid(row=row, column=1, padx=4)
            ttk.Label(self, text=desc, foreground='#57606a').grid(row=row, column=2, sticky='w')
            row += 1
        ttk.Button(self, text='저장', command=self._save).grid(row=row, column=1, pady=10)

    def _save(self):
        for (section, key), var in self.vars.items():
            s = var.get().strip()
            if s == '':
                self.dec[section][key] = None
            elif s.lower() in ('true', 'false'):
                self.dec[section][key] = (s.lower() == 'true')
            elif s.isdigit():
                self.dec[section][key] = int(s)
            else:
                self.dec[section][key] = s
        path = decisions.save(self.folder, self.dec)
        if self.on_saved:
            self.on_saved(f'결정값 저장: {path}')
        self.destroy()


def main():
    App().mainloop()


if __name__ == '__main__':
    main()
