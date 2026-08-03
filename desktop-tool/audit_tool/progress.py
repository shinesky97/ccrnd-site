# -*- coding: utf-8 -*-
"""다업체 외부감사 진행현황 관리 (8단계).

- 업체 목록: 루트 폴더(예: 'C 회계감사') 하위 폴더 스캔. 폴더명 끝 ★ = 외부감사 대상.
- 상태 저장: <root>/_audit_tool/진행현황.json (변경 이력 append)
- 단계는 사용자가 확정. 파일 신호 기반 '추정'은 참고 표시만 한다.
"""
import json
import os
import re

from .util import ensure_tool_dir, now_iso

STAGES = ['조회서 안내', '감사자료 요청', '자료 다운 완료', '보고서 초안완료',
          '심리 완료', '보고서 송부', '공시', '인쇄 및 청구']

FOLDER_PAT = re.compile(r'^([A-Z]-\d+)\s*(.+?)(★?)$')


def state_path(root):
    return os.path.join(ensure_tool_dir(root), '진행현황.json')


def load_state(root):
    p = state_path(root)
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    return {'clients': {}, 'history': []}


def save_state(root, state):
    with open(state_path(root), 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def scan_clients(root, external_only=True):
    """하위 폴더에서 업체 목록 파싱. ★=외부감사 대상."""
    clients = []
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        if not os.path.isdir(full) or name.startswith(('_', '.')):
            continue
        m = FOLDER_PAT.match(name)
        if not m:
            continue
        code, company, star = m.group(1), m.group(2).strip(), bool(m.group(3))
        if external_only and not star:
            continue
        clients.append({'code': code, 'company': company, 'external': star, 'folder': full})
    return clients


def estimate_stage(client_folder, year):
    """파일 신호 기반 단계 '추정' (참고용 — 확정은 사용자만).
    반환: (추정 단계 index 0-7 또는 None, 근거)"""
    year_dirs = [d for d in os.listdir(client_folder)
                 if os.path.isdir(os.path.join(client_folder, d)) and str(year) in d]
    if not year_dirs:
        return None, '당기 연도 폴더 없음'
    target = os.path.join(client_folder, year_dirs[0])
    names = []
    for r, _, fs in os.walk(target):
        names += [f for f in fs]
    joined = ' '.join(names)
    if re.search(r'심리|발행요청', joined):
        return 4, '심리/발행요청 파일 존재'
    if re.search(r'\.dsd', joined, re.I) and re.search(r'보고서|감사보고서', joined):
        return 3, 'DSD·보고서 파일 존재'
    if re.search(r'원장|분개장|전산|raw', joined, re.I):
        return 2, '전산자료 파일 존재'
    if re.search(r'요청자료|자료요청', joined):
        return 1, '자료요청 파일 존재'
    if re.search(r'조회서', joined):
        return 0, '조회서 파일 존재'
    return None, '신호 없음'


def set_stage(root, code, year, stage_index, memo=''):
    state = load_state(root)
    key = f'{code}:{year}'
    entry = state['clients'].setdefault(key, {'stage': None, 'stages_done': {}, 'memo': ''})
    entry['stage'] = stage_index
    entry['stages_done'][str(stage_index)] = now_iso()
    if memo:
        entry['memo'] = memo
    state['history'].append({'time': now_iso(), 'key': key,
                             'stage': stage_index, 'stage_name': STAGES[stage_index], 'memo': memo})
    save_state(root, state)
    return entry


def dashboard_html(root, year, out_path=None):
    """업체×단계 매트릭스 HTML 생성 (자체완결형)."""
    clients = scan_clients(root)
    state = load_state(root)
    rows = []
    for c in clients:
        key = f"{c['code']}:{year}"
        confirmed = state['clients'].get(key, {}).get('stage')
        est, why = estimate_stage(c['folder'], year)
        cells = []
        for i, _ in enumerate(STAGES):
            if confirmed is not None and i <= confirmed:
                cells.append('<td class="done">●</td>')
            elif confirmed is None and est is not None and i <= est:
                cells.append('<td class="est" title="추정: %s">◐</td>' % why)
            else:
                cells.append('<td></td>')
        label = '확정' if confirmed is not None else ('추정' if est is not None else '-')
        rows.append(f"<tr><td>{c['code']}</td><td>{c['company']}</td>"
                    f"<td>{label}</td>{''.join(cells)}</tr>")
    ths = ''.join(f'<th>{i+1}.{s}</th>' for i, s in enumerate(STAGES))
    html = f"""<meta charset="utf-8"><title>외부감사 진행현황 {year}</title>
<style>body{{font-family:'Malgun Gothic',sans-serif;margin:24px;background:#f6f8fa}}
h1{{font-size:20px}} table{{border-collapse:collapse;background:#fff;font-size:13px}}
th,td{{border:1px solid #d0d7de;padding:6px 10px;text-align:center}}
td.done{{background:#dafbe1;color:#1a7f37;font-weight:bold}}
td.est{{background:#fff8c5;color:#9a6700}}
.note{{color:#57606a;font-size:12px;margin-top:10px}}</style>
<h1>외부감사 진행현황 — {year} (외감 대상 ★ {len(clients)}개사)</h1>
<table><tr><th>관리번호</th><th>회사</th><th>상태</th>{ths}</tr>{''.join(rows)}</table>
<div class="note">● 사용자 확정 · ◐ 파일 신호 기반 추정(참고용 — 클릭 확정 필요) ·
생성 {now_iso()}</div>"""
    out = out_path or os.path.join(ensure_tool_dir(root), f'진행현황_{year}.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    return out
