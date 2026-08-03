# -*- coding: utf-8 -*-
"""CLI: python -m audit_tool <command>

  identify <폴더>                 파일 자동 식별 결과 표시
  init <폴더>                     결정값.json 생성(식별 결과로 제안값 채움)
  roll <폴더> [--execute]         이월 세팅 (기본 Dry-run; --execute로 실행)
                [--no-excel]      xlwings(Excel) 대신 openpyxl 강제
  progress scan <루트>            업체 목록(★ 외감 대상) 표시
  progress set <루트> <관리번호> <연도> <단계번호1-8> [메모]
  progress dash <루트> <연도>     진행현황 대시보드 HTML 생성
"""
import argparse
import json
import sys

from . import decisions, identify, progress, runner


def main(argv=None):
    p = argparse.ArgumentParser(prog='audit_tool', description='외감 실무 자동화 도구')
    sub = p.add_subparsers(dest='cmd', required=True)

    s = sub.add_parser('identify');  s.add_argument('folder')
    s = sub.add_parser('init');      s.add_argument('folder')
    s = sub.add_parser('roll')
    s.add_argument('folder'); s.add_argument('--execute', action='store_true')
    s.add_argument('--no-excel', action='store_true')
    s = sub.add_parser('progress')
    s.add_argument('sub', choices=['scan', 'set', 'dash'])
    s.add_argument('args', nargs='*')

    a = p.parse_args(argv)

    if a.cmd == 'identify':
        scan = identify.scan_folder(a.folder)
        print('식별 결과:')
        print(identify.summarize(scan))
        return 0

    if a.cmd == 'init':
        scan = identify.scan_folder(a.folder)
        pre = decisions.prefill_from_scan(scan)
        dec = decisions.template(prefill=pre)
        path = decisions.save(a.folder, dec)
        print(f'결정값 파일 생성: {path}')
        print('제안값(식별 기반 — 반드시 확인·수정 후 저장하십시오):')
        print(json.dumps(dec['사전'], ensure_ascii=False, indent=2))
        print('\n※ 전기수치_확정여부(true/false)는 직접 입력해야 합니다.')
        return 0

    if a.cmd == 'roll':
        dec = decisions.load(a.folder)
        if dec is None:
            print("결정값.json이 없습니다. 먼저 'init'을 실행하고 값을 확인하십시오.")
            return 1
        missing, errors = decisions.validate_pre(dec)
        if missing or errors:
            for m in missing:
                print(f'✋ 사전 결정값 미입력: {m} — {dict(decisions.PRE_FIELDS)[m]}')
            for e in errors:
                print(f'✘ {e}')
            return 1
        scan = identify.scan_folder(a.folder)
        allow_insert = not a.no_excel
        plans, dsd_job, problems = runner.build_plans(a.folder, dec, scan,
                                                      allow_insert=allow_insert)
        print(runner.dry_run_report(plans, dsd_job, problems))
        if not a.execute:
            print('\n(Dry-run입니다. 내용 확인 후 --execute 로 실행하십시오)')
            return 0
        if problems:
            print('\n✘ 해결 필요 항목이 있어 실행하지 않습니다.')
            return 1
        runner.execute(a.folder, dec, plans, dsd_job, prefer_excel=not a.no_excel)
        return 0

    if a.cmd == 'progress':
        if a.sub == 'scan':
            for c in progress.scan_clients(a.args[0]):
                print(f"  {c['code']} {c['company']} {'★' if c['external'] else ''}")
        elif a.sub == 'set':
            root, code, year, stage = a.args[:4]
            memo = a.args[4] if len(a.args) > 4 else ''
            idx = int(stage) - 1
            if not 0 <= idx < len(progress.STAGES):
                print('단계번호는 1~8'); return 1
            progress.set_stage(root, code, year, idx, memo)
            print(f'{code} {year} → {idx+1}.{progress.STAGES[idx]} 확정')
        elif a.sub == 'dash':
            out = progress.dashboard_html(a.args[0], a.args[1])
            print(f'대시보드 생성: {out}')
        return 0


if __name__ == '__main__':
    sys.exit(main())
