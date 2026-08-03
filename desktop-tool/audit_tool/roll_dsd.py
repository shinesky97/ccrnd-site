# -*- coding: utf-8 -*-
"""DSD(.dsd = ZIP[contents.xml + meta.xml]) 이월 세팅.

- 재무제표 셀: TE(ACODE=표준계정코드, ADELIM=열위치) — 당기열(1,2) 값을 전기열(3,4)로
  이동 후 당기열 비움.
- 기수·연도 라벨(제 N(당) 기, 'N년 M월 D일 현재' 등) 치환.
- 감사보고서일 등 사후 결정값 자리는 [입력 필요]로 공란화 (기본값 주입 금지).
- 편집기 버전이 테스트된 버전과 다르면 경고 (DART 편집기 업데이트 대응).
"""
import re
import zipfile
import xml.etree.ElementTree as ET

TESTED_VERSIONS = {'editver': '5.107', 'formula': '6.0'}
CUR_COLS, PRV_COLS = ('1', '2'), ('3', '4')
PERIOD_HINT = re.compile(r'제\s*\d+\s*(\(\s*(당|전)\s*\))?\s*기|20[0-9]{2}년|현재|부터|까지')
MAX_LABEL_LEN = 60  # 이보다 긴 텍스트는 본문 문단으로 보고 치환하지 않음(검토 목록으로)


def _bump(text, gisu_delta, year_delta):
    out = re.sub(r'제\s*(\d+)\s*(\(\s*(?:당|전)\s*\))?\s*기',
                 lambda m: m.group(0).replace(m.group(1), str(int(m.group(1)) + gisu_delta), 1),
                 text)
    out = re.sub(r'(?<!\d)(20[0-9]{2})(?!\d)', lambda m: str(int(m.group(1)) + year_delta), out)
    return out


def roll(src_dsd, out_dsd, gisu_delta=1, year_delta=1):
    """이월 실행. 원본 미수정, 새 .dsd 생성. 결과 요약 dict 반환."""
    with zipfile.ZipFile(src_dsd) as z:
        contents = z.read('contents.xml')
        meta = z.read('meta.xml')

    warnings = []
    mtext = meta.decode('utf-8', errors='replace')
    m = re.search(r'editver="([^"]+)"', mtext)
    if m and m.group(1) != TESTED_VERSIONS['editver']:
        warnings.append(f"DART 편집기 버전({m.group(1)})이 테스트된 버전"
                        f"({TESTED_VERSIONS['editver']})과 다릅니다. 생성물 오픈 확인 필요.")

    root = ET.fromstring(contents)

    # 1) 재무제표 값 이동 (ACODE 행 단위)
    rows = {}
    for te in root.iter('TE'):
        acode, adelim = te.get('ACODE'), te.get('ADELIM')
        if acode and adelim and adelim.isdigit():
            rows.setdefault(acode, {}).setdefault(adelim, []).append(te)
    moved = cleared = 0
    for cols in rows.values():
        for cur, prv in zip(CUR_COLS, PRV_COLS):
            for ce, pe in zip(cols.get(cur, []), cols.get(prv, [])):
                pe.text = ce.text
                if ce.text and ce.text.strip():
                    moved += 1
                ce.text = ''
                cleared += 1

    # 2) 기수·연도 라벨 치환 (짧은 라벨만; 본문 문단은 검토 목록)
    label_changes, review_texts = 0, []
    for e in root.iter():
        if e.tag not in ('TD', 'TH', 'TE', 'P', 'SPAN') or not e.text:
            continue
        if not PERIOD_HINT.search(e.text):
            continue
        if len(e.text.strip()) <= MAX_LABEL_LEN:
            new = _bump(e.text, gisu_delta, year_delta)
            if new != e.text:
                e.text = new
                label_changes += 1
        else:
            review_texts.append(e.text.strip()[:80])

    # 3) 사후 결정값 자리 공란화 — 감사보고서일
    date_cleared = 0
    for e in root.iter():
        if e.text and '감사보고서일(' in e.text:
            e.text = re.sub(r'감사보고서일\(\s*\d{4}년\s*\d{1,2}월\s*\d{1,2}일\s*\)',
                            '감사보고서일([입력 필요])', e.text)
            date_cleared += 1

    new_contents = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    with zipfile.ZipFile(out_dsd, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('contents.xml', new_contents)
        z.writestr('meta.xml', meta)

    return {
        'moved_cells': moved, 'cleared_cells': cleared,
        'label_changes': label_changes, 'report_date_cleared': date_cleared,
        'review_texts': review_texts[:50],
        'review_note': ('본문 문단(의견·강조사항 등)은 전기 텍스트가 남아 있습니다. '
                        '검토 목록의 문단은 반드시 확인·수정하십시오.'),
        'warnings': warnings,
    }
