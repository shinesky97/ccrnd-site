# -*- coding: utf-8 -*-
"""결정값 관리 — 프로그램은 결정하지 않고, 발주자(회계사)가 입력한 값만 사용한다.

- 사전 결정값: 초기세팅 실행에 필수 (미입력 시 실행 불가)
- 사후 결정값: 감사 판단 사항. 기본값 없음. 미입력 시 보고서 확정 단계 차단.
"""
import json
import os
from datetime import date

from .util import ensure_tool_dir

FILENAME = '결정값.json'

# 각 항목: (키, 설명 — 무엇을 결정하는 것인지, 어디에 반영되는지)
PRE_FIELDS = [
    ('회사명', '피감사회사 상호. 모든 산출물 헤더에 반영'),
    ('전기_연도', '전기(이월 원천) 회계연도. 예: 2025'),
    ('전기_기수', '전기 기수(제N기). DSD·정산표 기수 치환의 기준'),
    ('당기_연도', '당기 회계연도. 산출물 파일명·라벨에 반영'),
    ('당기_기수', '당기 기수(제N기)'),
    ('당기_결산일', '당기 결산일(YYYY-MM-DD). 조서·DSD 표지에 반영'),
    ('전기_결산일', '전기 결산일(YYYY-MM-DD). 조서의 날짜 치환 기준'),
    ('전기수치_확정여부', '전기 감사후 수치가 확정되었는지(true/false). false면 이월 중단'),
]
POST_FIELDS = [
    ('감사보고서일', '감사보고서 일자. 회계사가 확정. DSD 본문에 반영'),
    ('감사의견', '적정/한정/부적정/의견거절. 회계사만 선택 가능. 기본값 없음'),
    ('강조사항', '강조사항·기타사항 문단 (없으면 "해당없음" 명시 입력)'),
    ('계속기업결론', '계속기업 관련 결론 (회계사 판단)'),
    ('주주총회일', 'DSD SUMMARY(GMSH_DATE)에 반영'),
]

DEFAULT_FILE_RULES = {
    '일반조서': 'wp_일반조서_{당기_연도}.xlsx',
    '계정별조서': 'wp_4000_계정별조서_{당기_연도}.xlsx',
    '정산표': 'wp_8600A_정산표_{당기_연도}.xlsx',
    'DSD': 'FY{당기_연도}_{회사명}_DSD.dsd',
}


def template(prefill=None):
    d = {
        '_설명': {k: v for k, v in PRE_FIELDS + POST_FIELDS},
        '사전': {k: None for k, _ in PRE_FIELDS},
        '사후': {k: None for k, _ in POST_FIELDS},
        '파일명규칙': dict(DEFAULT_FILE_RULES),
        '옵션': {'작성자유지': True, '검토일자삭제': True},
    }
    d['사전']['전기수치_확정여부'] = None
    if prefill:
        d['사전'].update({k: v for k, v in prefill.items() if k in d['사전']})
    return d


def path_for(folder):
    return os.path.join(ensure_tool_dir(folder), FILENAME)


def load(folder):
    p = path_for(folder)
    if not os.path.exists(p):
        return None
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def save(folder, data):
    p = path_for(folder)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return p


def prefill_from_scan(scan):
    """식별 결과에서 사전 결정값 제안 (확정은 사용자)."""
    pre = {}
    dsds = scan['found'].get('dsd') or []
    if dsds:
        d = dsds[0]['detail']
        if d.get('company'):
            pre['회사명'] = d['company']
        if d.get('fiscal_no'):
            pre['전기_기수'] = d['fiscal_no']
            pre['당기_기수'] = d['fiscal_no'] + 1
        if d.get('year'):
            pre['전기_연도'] = d['year']
            pre['당기_연도'] = d['year'] + 1
            pre['전기_결산일'] = f"{d['year']}-12-31"
            pre['당기_결산일'] = f"{d['year'] + 1}-12-31"
    return pre


def validate_pre(data):
    """사전 결정값 검증. (missing, errors) 반환 — 비어 있으면 실행 불가."""
    missing, errors = [], []
    pre = data.get('사전', {})
    for k, _ in PRE_FIELDS:
        if pre.get(k) in (None, ''):
            missing.append(k)
    if pre.get('전기수치_확정여부') is False:
        errors.append('전기 감사후 수치가 미확정(false) — 확정 후 이월하십시오.')
    for k in ('전기_결산일', '당기_결산일'):
        v = pre.get(k)
        if v:
            try:
                date.fromisoformat(str(v))
            except ValueError:
                errors.append(f'{k} 형식 오류(YYYY-MM-DD 필요): {v}')
    if pre.get('전기_기수') and pre.get('당기_기수'):
        if int(pre['당기_기수']) != int(pre['전기_기수']) + 1:
            errors.append('당기_기수가 전기_기수+1이 아닙니다. 의도한 값인지 확인 필요.')
    return missing, errors


def post_gate(data):
    """사후 결정값 게이트 — 미입력 목록 반환. 비어 있지 않으면 보고서 확정 단계 진행 금지."""
    post = data.get('사후', {})
    return [k for k, _ in POST_FIELDS if post.get(k) in (None, '')]


def output_name(data, kind):
    rule = data.get('파일명규칙', DEFAULT_FILE_RULES).get(kind, DEFAULT_FILE_RULES[kind])
    ctx = dict(data.get('사전', {}))
    ctx['회사명'] = str(ctx.get('회사명') or '회사').replace('주식회사', '').strip() or '회사'
    return rule.format(**ctx)
