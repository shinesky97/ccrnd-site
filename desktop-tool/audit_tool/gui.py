# -*- coding: utf-8 -*-
"""tkinter GUI — 파일 지정 방식.

[① 이월 생성] 좌측: 전기 파일 슬롯(DSD·정산표·계정별조서·일반조서·전산자료) + 기본정보
              우측: 생성된 당기 파일 목록 + 다운로드
[② 진행현황] 다업체 8단계 관리

실행: python -m audit_tool.gui  (exe: AuditTool.exe)
"""
import os
import shutil
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__, progress, runner

SLOTS = [
    ('dsd',     '전기 감사보고서 DSD', [('DSD 파일', '*.dsd'), ('모든 파일', '*.*')], True),
    ('trial',   '전기 정산표',         [('엑셀', '*.xlsx *.xlsm')], True),
    ('account', '전기 계정별조서',      [('엑셀', '*.xlsx *.xlsm')], True),
    ('general', '전기 일반조서 (선택)', [('엑셀', '*.xlsx *.xlsm')], False),
    ('raw',     '당기 전산자료 (선택 — 있으면 정산표에 당기 숫자 주입)',
     [('엑셀', '*.xlsx *.xlsm')], False),
]
INFO_FIELDS = ['회사명', '전기_기수', '전기_연도', '전기_결산일',
               '당기_기수', '당기_연도', '당기_결산일']


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'외감 실무 자동화 도구 v{__version__}')
        self.geometry('1020x680')
        self.report_callback_exception = self._on_error
        self.slot_vars = {}
        self.info_vars = {}
        self.generated = []
        self.outdir = None
        nb = ttk.Notebook(self)
        nb.pack(fill='both', expand=True)
        self.tab_roll = ttk.Frame(nb)
        self.tab_prog = ttk.Frame(nb)
        nb.add(self.tab_roll, text='① 이월 생성')
        nb.add(self.tab_prog, text='② 진행현황')
        self._build_roll_tab()
        self._build_prog_tab()
        self.after(600, self._check_update_quietly)

    # ---------------- 공통 ----------------
    def _on_error(self, exc_type, exc, tb):
        import traceback
        err = ''.join(traceback.format_exception(exc_type, exc, tb))
        try:
            self._println('\n✘ 오류 발생:\n' + err)
        except Exception:
            pass
        messagebox.showerror('오류', str(exc) + '\n\n(상세 내용은 로그 창 참조)')

    def _println(self, s=''):
        def do():
            self.log.insert('end', s + '\n')
            self.log.see('end')
        self.after(0, do)

    def _check_update_quietly(self):
        def worker():
            try:
                from . import updater
                rv = updater.remote_version()
                if rv and rv != __version__:
                    self._println(f'※ 새 버전 v{rv}이 있습니다 (현재 v{__version__}). '
                                  f'[업데이트] 버튼으로 갱신하십시오.')
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _update(self):
        from . import updater
        status = updater.run(log=self._println,
                             confirm=lambda m: messagebox.askyesno('업데이트', m))
        if status == 'updated':
            messagebox.showinfo('업데이트 완료',
                                '프로그램을 닫았다가 다시 실행하면 새 버전이 적용됩니다.')

    # ---------------- ① 이월 생성 탭 ----------------
    def _build_roll_tab(self):
        f = self.tab_roll
        top = ttk.Frame(f); top.pack(fill='both', expand=True, padx=10, pady=8)

        # 좌측: 파일 슬롯 + 기본정보
        left = ttk.LabelFrame(top, text=' 1. 전기 파일 지정 ')
        left.pack(side='left', fill='both', expand=True, padx=(0, 6))
        for i, (key, label, ftypes, required) in enumerate(SLOTS):
            ttk.Label(left, text=('* ' if required else '') + label)\
                .grid(row=i * 2, column=0, sticky='w', padx=8, pady=(8 if i == 0 else 4, 0))
            var = tk.StringVar()
            self.slot_vars[key] = var
            ent = ttk.Entry(left, textvariable=var, width=52, state='readonly')
            ent.grid(row=i * 2 + 1, column=0, sticky='we', padx=8)
            ttk.Button(left, text='파일 선택', width=9,
                       command=lambda k=key, t=ftypes: self._pick(k, t))\
                .grid(row=i * 2 + 1, column=1, padx=(4, 8))
        base = len(SLOTS) * 2
        ttk.Separator(left).grid(row=base, column=0, columnspan=2, sticky='we', pady=8)
        info = ttk.Frame(left); info.grid(row=base + 1, column=0, columnspan=2,
                                          sticky='we', padx=8)
        ttk.Label(info, text='2. 기본 정보 (DSD 선택 시 자동 채움 — 확인·수정하십시오)',
                  font=('', 9, 'bold')).grid(row=0, column=0, columnspan=4, sticky='w')
        for i, key in enumerate(INFO_FIELDS):
            r, c = divmod(i, 2)
            ttk.Label(info, text=key.replace('_', ' ')).grid(row=r + 1, column=c * 2,
                                                             sticky='w', pady=2)
            v = tk.StringVar()
            self.info_vars[key] = v
            ttk.Entry(info, textvariable=v, width=18).grid(row=r + 1, column=c * 2 + 1,
                                                           sticky='w', padx=(4, 14))
        self.confirmed_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left, variable=self.confirmed_var,
                        text='전기 감사후 수치가 확정되었습니다 (미확정이면 이월 무의미)')\
            .grid(row=base + 2, column=0, columnspan=2, sticky='w', padx=8, pady=(6, 0))
        btnrow = ttk.Frame(left); btnrow.grid(row=base + 3, column=0, columnspan=2, pady=10)
        ttk.Button(btnrow, text='▶ 생성하기', command=self._generate).pack(side='left')
        ttk.Button(btnrow, text='업데이트', command=self._update).pack(side='left', padx=8)

        # 우측: 생성 결과
        right = ttk.LabelFrame(top, text=' 3. 생성된 당기 파일 ')
        right.pack(side='left', fill='both', expand=True)
        self.out_list = tk.Listbox(right, height=12)
        self.out_list.pack(fill='both', expand=True, padx=8, pady=8)
        rbtn = ttk.Frame(right); rbtn.pack(pady=(0, 8))
        ttk.Button(rbtn, text='다운로드 (저장 위치 선택)',
                   command=self._download).pack(side='left', padx=4)
        ttk.Button(rbtn, text='폴더 열기', command=self._open_outdir).pack(side='left')

        # 하단: 로그
        self.log = tk.Text(f, wrap='word', height=12)
        self.log.pack(fill='both', expand=False, padx=10, pady=(0, 8))

    def _pick(self, key, ftypes):
        p = filedialog.askopenfilename(title='파일 선택', filetypes=ftypes)
        if not p:
            return
        self.slot_vars[key].set(p)
        if key == 'dsd':
            self._prefill_from_dsd(p)

    def _prefill_from_dsd(self, path):
        try:
            from .identify import _inspect_dsd
            d = _inspect_dsd(path)
        except Exception:
            return
        def put(key, val):
            if val is not None and not self.info_vars[key].get().strip():
                self.info_vars[key].set(str(val))
        put('회사명', d.get('company'))
        if d.get('doc_name') and '감사보고서' not in d['doc_name']:
            self._println(f"⚠ 선택한 DSD 문서가 '{d['doc_name']}'입니다. "
                          f"감사보고서 DSD가 맞는지 확인하십시오.")
        if d.get('fiscal_no'):
            put('전기_기수', d['fiscal_no'])
            put('당기_기수', d['fiscal_no'] + 1)
        if d.get('year'):
            put('전기_연도', d['year'])
            put('당기_연도', d['year'] + 1)
            put('전기_결산일', f"{d['year']}-12-31")
            put('당기_결산일', f"{d['year'] + 1}-12-31")
        self._println('기본 정보를 DSD에서 자동 채움 — 값을 확인하십시오.')

    def _collect_info(self):
        info = {k: v.get().strip() for k, v in self.info_vars.items()}
        # 당기 값 자동 유도
        try:
            if not info['당기_기수'] and info['전기_기수']:
                info['당기_기수'] = str(int(info['전기_기수']) + 1)
            if not info['당기_연도'] and info['전기_연도']:
                info['당기_연도'] = str(int(info['전기_연도']) + 1)
            if not info['전기_결산일'] and info['전기_연도']:
                info['전기_결산일'] = f"{info['전기_연도']}-12-31"
            if not info['당기_결산일'] and info['당기_연도']:
                info['당기_결산일'] = f"{info['당기_연도']}-12-31"
        except ValueError:
            pass
        for k, v in info.items():
            self.info_vars[k].set(v)
        missing = [k for k, v in info.items() if not v]
        return info, missing

    def _generate(self):
        files = {k: (v.get() or None) for k, v in self.slot_vars.items()}
        if not any(files[k] for k in ('dsd', 'trial', 'account', 'general')):
            return messagebox.showwarning('안내', '전기 파일을 하나 이상 선택하십시오.')
        info, missing = self._collect_info()
        if missing:
            return messagebox.showwarning(
                '안내', '기본 정보 미입력: ' + ', '.join(m.replace('_', ' ') for m in missing))
        if not self.confirmed_var.get():
            return messagebox.showwarning(
                '안내', "'전기 감사후 수치 확정' 확인란에 체크해야 생성할 수 있습니다.")
        self.out_list.delete(0, 'end')
        self.generated = []
        self.outdir = tempfile.mkdtemp(prefix='외감이월_')
        self.log.delete('1.0', 'end')
        self._println('=== 당기 파일 생성 시작 ===')

        def worker():
            try:
                outputs = runner.rollforward_files(files, info, self.outdir,
                                                   log=self._println)
            except Exception as e:
                import traceback
                self._println('✘ 생성 실패:\n' + traceback.format_exc())
                self.after(0, lambda: messagebox.showerror('실패', str(e)))
                return
            self.generated = outputs
            def done():
                for p in outputs:
                    self.out_list.insert('end', os.path.basename(p))
                if outputs:
                    self._println(f'\n=== 완료: {len(outputs)}개 파일 생성 ===')
                    self._println('[다운로드] 버튼으로 원하는 위치에 저장하십시오. '
                                  'DSD는 DART 편집기에서 열어 확인이 필요합니다.')
                else:
                    self._println('\n생성된 파일이 없습니다. 로그를 확인하십시오.')
            self.after(0, done)
        threading.Thread(target=worker, daemon=True).start()

    def _download(self):
        if not self.generated:
            return messagebox.showwarning('안내', '먼저 [생성하기]를 실행하십시오.')
        dst = filedialog.askdirectory(title='저장할 폴더 선택')
        if not dst:
            return
        saved = []
        for p in self.generated:
            target = os.path.join(dst, os.path.basename(p))
            if os.path.exists(target):
                base, ext = os.path.splitext(target)
                n = 2
                while os.path.exists(f'{base}_v{n}{ext}'):
                    n += 1
                target = f'{base}_v{n}{ext}'
            shutil.copy2(p, target)
            saved.append(os.path.basename(target))
        # 리포트류도 함께 저장
        if self.outdir:
            for fn in os.listdir(self.outdir):
                if fn.endswith(('.txt', '.jsonl')):
                    shutil.copy2(os.path.join(self.outdir, fn), os.path.join(dst, fn))
        self._println(f'✔ 저장 완료 ({dst}): ' + ', '.join(saved))
        messagebox.showinfo('저장 완료', f'{len(saved)}개 파일을 저장했습니다.\n{dst}')

    def _open_outdir(self):
        if not self.outdir:
            return
        try:
            os.startfile(self.outdir)          # Windows
        except (AttributeError, OSError):
            self._println(f'생성 폴더: {self.outdir}')

    # ---------------- ② 진행현황 탭 ----------------
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
            self.tree.insert('', 'end', iid=c['code'],
                             values=(f"{c['code']} {c['company']}", label))

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
            os.startfile(out)
        except (AttributeError, OSError):
            pass


def main():
    App().mainloop()


if __name__ == '__main__':
    main()
