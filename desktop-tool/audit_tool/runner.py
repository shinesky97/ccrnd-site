# -*- coding: utf-8 -*-
"""초기세팅(Rollforward) 오케스트레이션: 식별 → 결정값 검증 → 계획 → Dry-run/실행 → 로그."""
import os
from datetime import date

from . import identify, decisions, roll_dsd, roll_xlsx
from .engine import pick_engine
from .util import ensure_tool_dir, jsonl_append, now_iso, safe_out_path, sha256_file


def exclude_tool_outputs(scan, dec):
    """도구가 생성한 당기 산출물이 '전기 후보'로 재식별되는 것을 방지."""
    outs = {decisions.output_name(dec, k)
            for k in ('일반조서', '계정별조서', '정산표', 'DSD')}
    for kind, entries in scan['found'].items():
        scan['found'][kind] = [
            e for e in entries
            if not any(os.path.basename(e['path']).startswith(os.path.splitext(o)[0])
                       for o in outs)]
    return scan


def _pick_prior(entries, prior_year):
    """전기 연도와 일치하는 파일 선택. 모호하면 None (사용자 지정 필요)."""
    if not entries:
        return None
    match = [e for e in entries if e.get('year') == prior_year]
    if len(match) == 1:
        return match[0]
    if len(entries) == 1 and not match:
        return entries[0]  # 연도 판별 실패했지만 후보가 유일
    return None


def build_plans(folder, dec, scan=None, allow_insert=True):
    """실행 계획 수립. (plans, dsd_job, problems) 반환.
    allow_insert=False면 정산표 열 삽입 단계를 제외한다(openpyxl 엔진 호환)."""
    scan = scan or identify.scan_folder(folder)
    scan = exclude_tool_outputs(scan, dec)
    pre = dec['사전']
    prior_year = int(pre['전기_연도'])
    prior_fye = date.fromisoformat(str(pre['전기_결산일']))
    cur_fye = date.fromisoformat(str(pre['당기_결산일']))
    problems, plans, dsd_job = [], [], None

    def out_path(kind):
        return safe_out_path(os.path.join(folder, decisions.output_name(dec, kind)))

    e = _pick_prior(scan['found']['general_wp'], prior_year)
    if e:
        plans.append(('일반조서', roll_xlsx.plan_general_wp(
            e['path'], out_path('일반조서'), prior_fye, cur_fye,
            keep_authors=dec['옵션'].get('작성자유지', True))))
    else:
        problems.append('전기 일반조서를 특정하지 못함 (없거나 후보가 여러 개)')

    e = _pick_prior(scan['found']['account_wp'], prior_year)
    if e:
        plans.append(('계정별조서', roll_xlsx.plan_account_wp(
            e['path'], out_path('계정별조서'), prior_fye, cur_fye, pre['회사명'])))
    else:
        problems.append('전기 계정별조서를 특정하지 못함')

    e = _pick_prior(scan['found']['trial_sheet'], prior_year)
    if e:
        plans.append(('정산표', roll_xlsx.plan_trial_sheet(
            e['path'], out_path('정산표'), prior_year=prior_year)))
    else:
        problems.append('전기 정산표를 특정하지 못함')

    # DSD는 감사보고서 문서만 이월 대상 (기업개황자료·중요성금액 등 기타 DSD는 제외)
    dsds = scan['found']['dsd']
    report_dsds = [e for e in dsds
                   if e['detail'].get('doc_code') == '00760'
                   or '감사보고서' in (e['detail'].get('doc_name') or '')]
    other_dsds = [e for e in dsds if e not in report_dsds]
    e = _pick_prior(report_dsds or dsds, prior_year)
    if e:
        dsd_job = {'src': e['path'], 'out': out_path('DSD'),
                   'gisu_delta': int(pre['당기_기수']) - int(pre['전기_기수']),
                   'year_delta': int(pre['당기_연도']) - int(pre['전기_연도']),
                   'others': [os.path.basename(o['path']) for o in other_dsds]}
    else:
        problems.append('전기 DSD(감사보고서)를 특정하지 못함')

    return plans, dsd_job, problems


def dry_run_report(plans, dsd_job, problems):
    lines = ['=== Dry-run: 실행 전 확인 ===']
    for name, plan in plans:
        lines.append(f'\n[{name}]')
        lines.append(plan.describe())
    if dsd_job:
        lines.append(f"\n[DSD]\n원본: {os.path.basename(dsd_job['src'])}"
                     f"\n생성: {os.path.basename(dsd_job['out'])}"
                     f"\n기수 +{dsd_job['gisu_delta']}, 연도 +{dsd_job['year_delta']},"
                     f" 당기열→전기열 이동, 감사보고서일 [입력 필요] 처리")
        if dsd_job.get('others'):
            lines.append('※ 기타 DSD(자동 이월 제외 — 수동 처리): '
                         + ', '.join(dsd_job['others']))
    for p in problems:
        lines.append(f'\n✋ 해결 필요: {p}')
    return '\n'.join(lines)


def execute(folder, dec, plans, dsd_job, prefer_excel=True, log=print):
    """계획 실행 + 실행 로그 기록. 원본은 수정하지 않는다."""
    tool_dir = ensure_tool_dir(folder)
    logfile = os.path.join(tool_dir, 'runlog.jsonl')
    engine = pick_engine(prefer_excel)
    log(f'실행 엔진: {engine.name}')
    if engine.name == 'openpyxl':
        log('  ⚠ openpyxl 엔진: 차트·도형이 많은 양식은 산출물에서 일부 요소가 빠질 수 '
            '있습니다. 산출물을 열어 확인하고, 필요하면 Excel 설치 PC에서 실행.bat로 '
            '실행하십시오(xlwings 엔진).')
    results = []
    for name, plan in plans:
        rec = {'time': now_iso(), 'action': 'rollforward', 'target': name,
               'src': plan.src, 'src_sha256': sha256_file(plan.src),
               'out': plan.out, 'engine': engine.name}
        try:
            applied = engine.execute(plan)
            rec.update(status='ok', ops_applied=applied,
                       warnings=plan.warnings, manual=plan.manual)
            log(f'✔ {name}: {applied}건 적용 → {os.path.basename(plan.out)}')
            for m in plan.manual:
                log(f'  ✋ 수동 처리 필요: {m}')
        except Exception as ex:
            rec.update(status='error', error=str(ex))
            log(f'✘ {name} 실패: {ex}')
        jsonl_append(logfile, rec)
        results.append(rec)

    if dsd_job:
        rec = {'time': now_iso(), 'action': 'rollforward', 'target': 'DSD',
               'src': dsd_job['src'], 'src_sha256': sha256_file(dsd_job['src']),
               'out': dsd_job['out']}
        try:
            summary = roll_dsd.roll(dsd_job['src'], dsd_job['out'],
                                    dsd_job['gisu_delta'], dsd_job['year_delta'])
            rec.update(status='ok', **{k: v for k, v in summary.items() if k != 'review_texts'})
            log(f"✔ DSD: 값이동 {summary['moved_cells']}셀, 라벨 {summary['label_changes']}건"
                f" → {os.path.basename(dsd_job['out'])}")
            for w in summary['warnings']:
                log(f'  ⚠ {w}')
            log(f"  ⚠ {summary['review_note']}")
        except Exception as ex:
            rec.update(status='error', error=str(ex))
            log(f'✘ DSD 실패: {ex}')
        jsonl_append(logfile, rec)
        results.append(rec)
    return results


def rollforward_files(files, info, outdir, prefer_excel=True, log=print):
    """파일을 사용자가 직접 지정하는 이월 방식 (폴더 자동식별을 쓰지 않음 — GUI 슬롯 UI용).

    files: {'dsd','trial','account','general','raw'} → 경로 또는 None
    info : {'회사명','전기_기수','전기_연도','전기_결산일','당기_기수','당기_연도','당기_결산일'}
    반환 : 생성된 파일 경로 리스트. 원본 미수정, outdir에 새 파일 생성.
    """
    from datetime import date as _date

    from . import inject as inject_mod
    from .engine import pick_engine
    from .util import jsonl_append, now_iso, safe_out_path, sha256_file

    prior_fye = _date.fromisoformat(str(info['전기_결산일']))
    cur_fye = _date.fromisoformat(str(info['당기_결산일']))
    prior_year = int(info['전기_연도'])
    cur_year = int(info['당기_연도'])
    company = str(info.get('회사명') or '회사').replace('주식회사', '').strip() or '회사'
    os.makedirs(outdir, exist_ok=True)
    logfile = os.path.join(outdir, '생성로그.jsonl')
    outputs = []

    plans = []
    if files.get('general'):
        plans.append(('일반조서', roll_xlsx.plan_general_wp(
            files['general'], safe_out_path(os.path.join(outdir, f'wp_일반조서_{cur_year}.xlsx')),
            prior_fye, cur_fye)))
    if files.get('account'):
        plans.append(('계정별조서', roll_xlsx.plan_account_wp(
            files['account'],
            safe_out_path(os.path.join(outdir, f'wp_4000_계정별조서_{cur_year}.xlsx')),
            prior_fye, cur_fye, info.get('회사명'))))
    if files.get('trial'):
        plans.append(('정산표', roll_xlsx.plan_trial_sheet(
            files['trial'],
            safe_out_path(os.path.join(outdir, f'wp_8600A_정산표_{cur_year}.xlsx')),
            prior_year=prior_year)))

    engine = pick_engine(prefer_excel)
    log(f'실행 엔진: {engine.name}')
    trial_out = None
    for name, plan in plans:
        rec = {'time': now_iso(), 'action': 'rollforward_files', 'target': name,
               'src': plan.src, 'src_sha256': sha256_file(plan.src),
               'out': plan.out, 'engine': engine.name}
        try:
            applied = engine.execute(plan)
            rec.update(status='ok', ops_applied=applied,
                       warnings=plan.warnings, manual=plan.manual)
            outputs.append(plan.out)
            if name == '정산표':
                trial_out = plan.out
            log(f'✔ {name}: {applied}건 적용 → {os.path.basename(plan.out)}')
            for m in plan.manual:
                log(f'  ✋ 수동 확인: {m}')
        except Exception as ex:
            rec.update(status='error', error=str(ex))
            log(f'✘ {name} 실패: {ex}')
        jsonl_append(logfile, rec)

    if files.get('dsd'):
        out = safe_out_path(os.path.join(outdir, f'FY{cur_year}_{company}_DSD.dsd'))
        rec = {'time': now_iso(), 'action': 'rollforward_files', 'target': 'DSD',
               'src': files['dsd'], 'src_sha256': sha256_file(files['dsd']), 'out': out}
        try:
            summary = roll_dsd.roll(files['dsd'], out,
                                    int(info['당기_기수']) - int(info['전기_기수']),
                                    cur_year - prior_year)
            rec.update(status='ok',
                       **{k: v for k, v in summary.items() if k != 'review_texts'})
            outputs.append(out)
            log(f"✔ DSD: 값이동 {summary['moved_cells']}셀, 라벨 {summary['label_changes']}건"
                f" → {os.path.basename(out)}")
            for w in summary['warnings']:
                log(f'  ⚠ {w}')
            log(f"  ⚠ {summary['review_note']}")
        except Exception as ex:
            rec.update(status='error', error=str(ex))
            log(f'✘ DSD 실패: {ex}')
        jsonl_append(logfile, rec)

    if files.get('raw') and trial_out:
        log('\n— 당기 전산자료 주입 —')
        try:
            plan, rpt = inject_mod.plan_inject(trial_out, files['raw'], cur_year,
                                               name_source=files['trial'])
            log('\n'.join(rpt))
            with open(os.path.join(outdir, f'주입리포트_{cur_year}.txt'), 'w',
                      encoding='utf-8') as f:
                f.write('\n'.join(rpt))
            if plan.ops:
                applied = engine.execute(plan)
                log(f'✔ 주입 완료: {applied}건')
            jsonl_append(logfile, {'time': now_iso(), 'action': 'inject',
                                   'target': trial_out, 'raw': files['raw'],
                                   'raw_sha256': sha256_file(files['raw']),
                                   'ops': len(plan.ops), 'status': 'ok'})
        except Exception as ex:
            log(f'✘ 주입 실패: {ex}')
    elif files.get('raw'):
        log('⚠ 전산자료가 지정되었지만 정산표가 없어 주입을 건너뜁니다.')

    return outputs


def run_all(folder, prefer_excel=True, log=print, confirm=None):
    """원클릭 파이프라인: 식별 → 결정값 검증 → 이월(확인 후) → 당기 숫자 주입(확인 후).

    confirm(message) -> bool  : 사용자 확인 콜백. None이면 Dry-run까지만 수행.
    반환 dict의 status: need_decisions / blocked / dry_run / cancelled / done
    """
    from . import inject as inject_mod

    dec = decisions.load(folder)
    scan = identify.scan_folder(folder)
    log('=== 1단계: 파일 식별 ===')
    log(identify.summarize(scan))

    if dec is None:
        dec = decisions.template(prefill=decisions.prefill_from_scan(scan))
        decisions.save(folder, dec)
        log('\n결정값 파일이 없어 새로 만들었습니다 (_audit_tool/결정값.json).')
        log('사전 결정값(기수·연도·결산일·전기수치_확정여부)을 확인·입력한 뒤 다시 실행하십시오.')
        return {'status': 'need_decisions', 'dec': dec}
    missing, errors = decisions.validate_pre(dec)
    if missing or errors:
        for m in missing:
            log(f'✋ 사전 결정값 미입력: {m} — {dict(decisions.PRE_FIELDS)[m]}')
        for e in errors:
            log(f'✘ {e}')
        return {'status': 'need_decisions', 'dec': dec, 'missing': missing, 'errors': errors}

    scan = exclude_tool_outputs(scan, dec)
    plans, dsd_job, problems = build_plans(folder, dec, scan)
    log('\n=== 2단계: 이월(초기세팅) ===')
    log(dry_run_report(plans, dsd_job, problems))
    if problems:
        log('\n✘ 해결 필요 항목이 있어 중단합니다.')
        return {'status': 'blocked', 'problems': problems}
    if confirm is None:
        return {'status': 'dry_run'}
    if not confirm('위 Dry-run 내용대로 당기 파일을 생성합니다.\n'
                   '원본은 수정되지 않습니다. 진행할까요?'):
        return {'status': 'cancelled'}
    execute(folder, dec, plans, dsd_job, prefer_excel=prefer_excel, log=log)

    log('\n=== 3단계: 정산표 당기 숫자 주입 ===')
    if not scan['found']['raw_data']:
        log('당기 전산자료(Raw)가 없어 주입을 건너뜁니다. 자료 수령 후 주입을 실행하십시오.')
        return {'status': 'done', 'inject': 'skipped'}
    res = inject_mod.run_for_folder(folder, dec, execute=False,
                                    prefer_excel=prefer_excel, log=log)
    if res['status'] != 'dry_run':
        return {'status': 'done', 'inject': res['status']}
    if not confirm(f"{res['ops']}개 항목을 정산표 당기 열에 주입합니다.\n"
                   '대상 파일은 백업 후 수정됩니다. 진행할까요?'):
        return {'status': 'done', 'inject': 'cancelled'}
    res = inject_mod.run_for_folder(folder, dec, execute=True,
                                    prefer_excel=prefer_excel, log=log)
    log('\n=== 완료 ===')
    log('생성물 확인: 당기 조서·정산표·DSD + _audit_tool/주입리포트. '
        'DSD는 DART 편집기에서 열어 확인하십시오.')
    return {'status': 'done', 'inject': res['status']}
