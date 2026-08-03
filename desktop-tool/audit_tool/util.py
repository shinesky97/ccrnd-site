# -*- coding: utf-8 -*-
"""공통 유틸리티. 원본 불변 원칙: 원본 파일에 쓰기 금지, 산출물은 항상 새 경로."""
import hashlib
import json
import os
import re
from datetime import datetime, date


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def now_iso():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def ensure_tool_dir(folder):
    d = os.path.join(folder, '_audit_tool')
    os.makedirs(d, exist_ok=True)
    return d


def safe_out_path(path):
    """동명 파일이 있으면 덮어쓰지 않고 _v2, _v3 …를 붙인다."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f'{base}_v{n}{ext}'):
        n += 1
    return f'{base}_v{n}{ext}'


def jsonl_append(path, record):
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')


def parse_year(text):
    m = re.search(r'(?<!\d)(20[0-9]{2})(?!\d)', str(text))
    return int(m.group(1)) if m else None


def is_fye(value, fye):
    """셀 값이 특정 결산일(date)인지 판정 (datetime/date/문자열 허용)."""
    if isinstance(value, datetime):
        return value.date() == fye
    if isinstance(value, date):
        return value == fye
    if isinstance(value, str):
        s = value.strip().replace('.', '-').replace('/', '-')
        return s.startswith(fye.isoformat())
    return False


def patch_openpyxl_korean():
    """한국어 엑셀 파일 호환 패치.

    국내 회계 프로그램이 만든 xlsx의 열 정의에 'phonetic' 속성이 있으면 openpyxl이
    (3.1.5 기준) 일반 모드 로드에 실패한다. 해당 속성만 무시하도록 패치한다.
    (xlwings/Excel 경로에는 영향 없음. 열 phonetic 속성은 산출물에서 제거됨)
    """
    from openpyxl.worksheet.dimensions import ColumnDimension
    if getattr(ColumnDimension, '_phonetic_patched', False):
        return
    orig = ColumnDimension.__init__

    def _init(self, worksheet, *args, **kw):
        kw.pop('phonetic', None)
        orig(self, worksheet, *args, **kw)

    ColumnDimension.__init__ = _init
    ColumnDimension._phonetic_patched = True


GISU_PAT = re.compile(r'제\s*(\d+)\s*(\(\s*(당|전)\s*\))?\s*기')
YEAR_PAT = re.compile(r'(?<!\d)(20[0-9]{2})(?!\d)')


def bump_period_label(text, gisu_delta=1, year_delta=1):
    """'제 12(당) 기', '제 12 기 2025년 12월 31일 현재' 등의 라벨에서 기수·연도를 증가.
    한글 접미사 앞 \\b 미동작 문제를 피하기 위해 lookaround 사용."""
    out = GISU_PAT.sub(lambda m: m.group(0).replace(m.group(1), str(int(m.group(1)) + gisu_delta), 1), text)
    out = YEAR_PAT.sub(lambda m: str(int(m.group(1)) + year_delta), out)
    changed = out != text
    return out, changed
