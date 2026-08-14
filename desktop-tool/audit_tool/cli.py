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
    s = sub.add_parser('inject')
    s.add_argument('folder'); s.add_argument('--execute', action='store_true')
    s.add_argument('--no-excel', action='store_true')
    s.add_argument('--year', type=int, help='대상 연도 열 (기본: 결정값의 당기_연도)')
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

    if a.cmd == 'inject':
        import os
        import shutil
        from datetime import datetime
        from . import inject as inject_mod
        from .engine import pick_engine
        from .util import ensure_tool_dir, jsonl_append, now_iso, sha256_file
        dec = decisions.load(a.folder)
        if dec is None:
            print("결정값.json이 없습니다. 먼저 'init'을 실행하십시오.")
            return 1
        year = a.year or dec['사전'].get('당기_연도')
        if not year:
            print('당기_연도가 없습니다. 결정값을 입력하거나 --year를 지정하십시오.')
            return 1
        trial = os.path.join(a.folder, decisions.output_name(dec, '정산표'))
        if not os.path.exists(trial):
            print(f'당기 정산표가 없습니다: {trial}\n먼저 roll을 실행하십시오.')
            return 1
        scan = runner.exclude_tool_outputs(identify.scan_folder(a.folder), dec)
        raws = scan['found']['raw_data']
        if len(raws) != 1:
            print(f'전산자료(Raw)를 특정하지 못했습니다 (후보 {len(raws)}개).')
            return 1
        prior = runner._pick_prior(scan['found']['trial_sheet'],
                                   dec['사전'].get('전기_연도'))
        plan, rpt = inject_mod.plan_inject(trial, raws[0]['path'], int(year),
                                           name_source=prior['path'] if prior else None)
        print('\n'.join(rpt))
        tool_dir = ensure_tool_dir(a.folder)
        with open(os.path.join(tool_dir, f'주입리포트_{year}.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(rpt))
        if not plan.ops:
            print('\n주입할 항목이 없습니다.')
            return 1
        if not a.execute:
            print('\n(Dry-run입니다. --execute 로 실행 시 대상 파일을 백업 후 수정합니다)')
            return 0
        backups = os.path.join(tool_dir, 'backups')
        os.makedirs(backups, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        bak = os.path.join(backups, f'{stamp}_{os.path.basename(trial)}')
        shutil.copy2(trial, bak)
        engine = pick_engine(not a.no_excel)
        applied = engine.execute(plan)
        jsonl_append(os.path.join(tool_dir, 'runlog.jsonl'),
                     {'time': now_iso(), 'action': 'inject', 'target': trial,
                      'backup': bak, 'raw': raws[0]['path'],
                      'raw_sha256': sha256_file(raws[0]['path']),
                      'engine': engine.name, 'ops_applied': applied, 'status': 'ok'})
        print(f'\n✔ 주입 완료: {applied}건 (백업: {bak})')
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
