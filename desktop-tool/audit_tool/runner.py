# -*- coding: utf-8 -*-
"""초기세팅(Rollforward) 오케스트레이션: 식별 → 결정값 검증 → 계획 → Dry-run/실행 → 로그."""
import os
from datetime import date

from . import identify, decisions, roll_dsd, roll_xlsx
from .engine import pick_engine
from .util import ensure_tool_dir, jsonl_append, now_iso, safe_out_path, sha256_file


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
        plan = roll_xlsx.plan_trial_sheet(e['path'], out_path('정산표'),
                                          insert_history_col=allow_insert)
        if not allow_insert:
            plan.manual.append('AR 이력 열 삽입은 제외됨(Excel 엔진 아님) — 수동 삽입 필요')
        plans.append(('정산표', plan))
    else:
        problems.append('전기 정산표를 특정하지 못함')

    e = _pick_prior(scan['found']['dsd'], prior_year)
    if e:
        dsd_job = {'src': e['path'], 'out': out_path('DSD'),
                   'gisu_delta': int(pre['당기_기수']) - int(pre['전기_기수']),
                   'year_delta': int(pre['당기_연도']) - int(pre['전기_연도'])}
    else:
        problems.append('전기 DSD를 특정하지 못함')

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
    for p in problems:
        lines.append(f'\n✋ 해결 필요: {p}')
    return '\n'.join(lines)


def execute(folder, dec, plans, dsd_job, prefer_excel=True, log=print):
    """계획 실행 + 실행 로그 기록. 원본은 수정하지 않는다."""
    tool_dir = ensure_tool_dir(folder)
    logfile = os.path.join(tool_dir, 'runlog.jsonl')
    engine = pick_engine(prefer_excel)
    log(f'실행 엔진: {engine.name}')
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
