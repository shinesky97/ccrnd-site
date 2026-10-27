"""한국회계기준원 PDF 원문 → cpawork standards_data 갱신.

cpawork 의 PDF 경로는 줄바꿈된 문단번호를 놓치므로, PDF 줄을 HWP 원문처럼
'문단번호\t본문' 블록으로 재구성한 뒤 cpawork 의 구조화(segment)를 그대로 쓴다.
기존 번들의 문단번호 목록(구번들 git ref)을 참고해 문단 시작을 판정한다.

    python scripts/kasb_pdf_to_cpawork.py <cpawork>/webapp 원문.zip <구번들 git ref>
    python scripts/build_standards_bundle.py <cpawork>/webapp/app/standards_data standards-bundle.json

필요 패키지: pypdf, olefile, pyyaml, sqlalchemy (cpawork 모듈 import 용)
"""
import gzip, json, re, subprocess, sys
from pathlib import Path

WEBAPP, SRC, REF = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(WEBAPP))
from app import standards, standards_hwp, standards_parse as sp  # noqa: E402
from pypdf import PdfReader  # noqa: E402
import io  # noqa: E402

NUM = sp._NUM
LINE_NO = re.compile(rf"^({NUM}) (?=\S)")
PAGE_NO = re.compile(r"^\s*-\s*\d+\s*-\s*$")
END = ("다.", "다", ".", ":", "：")
PART_HEAD = re.compile(r"^(부록\s?[A-Z가-힣]|적용사례|실무적용사례|실무적용지침|결론도출근거|.{0,30}결론도출근거$|소수의견|.{0,30}의 반대$|국제회계기준과의 관계|제[·⋅․]개정 경과|이 기준서의 개요|실무지침$|.{0,40}회계기준위원회의 의결)")
BODY_START = re.compile(r"^[가-힣‘'“\"(\[「<]")
LIST_STRONG = re.compile(r"^(?:[⑴-⒇㈎-㈝①-⑳]|\(\d+(?:-\d+)?\)|\([가-힣]\)|[가-힣]\.|\d+\)|[-•▪○※])\s?(?=\S)")
LIST = re.compile(r"^(?:[⑴-⒇㈎-㈝①-⑳•▪○※]|\(\d+\)|\([가-힣]\)|[가-힣]\.\s|\d+\)\s)")


def known_set(fw, code):
    r = subprocess.run(["git", "-C", str(WEBAPP), "show", f"{REF}:webapp/app/standards_data/{fw}/{code}.json.gz"],
                       capture_output=True)
    if r.returncode:
        return set()
    return {u["no"] for u in json.loads(gzip.decompress(r.stdout))["units"] if u["no"]}


def successor(prev, cand):
    return bool(prev) and sp._is_successor(prev, cand)


def same_series_up(last_by_head, cand):
    c = sp._NO_PARTS_RE.match(cand)
    if not c:
        return False
    n, prev = int(c.group(2)), last_by_head.get(c.group(1))
    if prev is None:
        return n <= 3 and c.group(3) == ""  # 새 계열의 시작
    return prev < n <= prev + 12


WRAP_BODY = re.compile(r"^(?:참조|및\s|과\s|와\s|에서|에\s|의\s|을\s|를\s|부터|까지|[)~∼,.⑴-⒇㈎-㈝])")
WRAP_PREV = ("문단", " 및", "~", "∼")


def pdf_blocks(data, known):
    lines = []
    for page in PdfReader(io.BytesIO(data)).pages:
        for ln in (page.extract_text() or "").split("\n"):
            if PAGE_NO.match(ln) or not ln.strip():
                continue
            lines.append(ln)
    lens = sorted(len(x.strip()) for x in lines if len(x.strip()) > 10)
    W = lens[int(len(lens) * 0.8)] if lens else 40

    def short(k):  # 줄 폭이 눈에 띄게 짧으면 문단·항목·제목의 끝
        return len(lines[k].strip()) < 0.72 * W

    # 1차: 문단 시작 줄 판정
    starts, last_no, prev_end, last_by_head = {}, None, True, {}
    for i, raw in enumerate(lines):
        s = raw.strip()
        m = LINE_NO.match(s)
        no = m.group(1) if m else None
        if no:
            body = s[m.end():]
            bogus = re.fullmatch(r"\d+[XY]\d*|(19|20)\d\d|IFRS\d+|IAS\d+", no) is not None
            hangul = re.search(r"[가-힣]", body[:25]) is not None and not re.match(r"[\d,.()%\s-]+(\s|$)", body[:12])
            prev = lines[i - 1].strip() if i else ""
            prev_ok = prev_end or prev.endswith(")") or LIST.match(prev) is not None or (i > 0 and short(i - 1))
            wrap = WRAP_BODY.match(body) is not None or (i > 0 and lines[i - 1].rstrip().endswith(WRAP_PREV))
            if bogus or wrap or not hangul or (len(body) < 8 and not body.startswith("[")):
                ok = False
            elif no in known or successor(last_no, no):
                ok = prev_ok
            else:
                ok = prev_end and (not no.isdigit() or same_series_up(last_by_head, no))
            if ok:
                starts[i] = (no, s[m.end():]); last_no = no
                pm = sp._NO_PARTS_RE.match(no)
                if pm:
                    last_by_head[pm.group(1)] = int(pm.group(2))
        prev_end = s.endswith(END) or i in starts and False or (len(s) <= 40 and not s.endswith(END) and prev_end)
    # 2차: 문단 시작 바로 앞(또는 그 앞 제목 앞)의 짧은 줄은 제목
    heads = set()
    for i in sorted(starts, reverse=True):
        j = i - 1
        while j > 0 and j not in starts and short(j) and not lines[j].strip().endswith(END + (")",)) \
                and not LIST.match(lines[j].strip()) and i - j <= 3 \
                and (lines[j - 1].strip().endswith(END + (")",)) or short(j - 1) or j - 1 in heads):
            heads.add(j); j -= 1
    blocks, cur, prev_end = [], None, True

    def flush():
        nonlocal cur
        if cur is not None:
            blocks.append({"t": "p", "text": re.sub(r"[ \u00a0]+", " ", cur).strip()})
        cur = None

    for i, raw in enumerate(lines):
        s = raw.strip()
        if i in starts:
            flush(); no, body = starts[i]; cur = no + "\t" + body
        elif i in heads:
            flush(); blocks.append({"t": "p", "text": s})
        elif len(s) <= 40 and PART_HEAD.match(s) and not s.endswith(END):
            flush(); blocks.append({"t": "p", "text": s})
        elif cur is not None and (LIST_STRONG.match(s) or short(i - 1)):
            cur = cur.rstrip() + "\n" + s  # 항목·정의·줄바꿈은 같은 문단 안 새 줄로
        elif cur is None:
            cur = s
        else:
            if cur.endswith((".", ",", ":", ";", "·")) is True and cur[-1:] != " " and not s[:1] in ".,)":
                cur += " "
            cur = cur + s
        if cur is not None and raw.endswith(" ") and not cur.endswith(" "):
            cur += " "
        prev_end = s.endswith(END)
    flush()
    return blocks


orig_extract = standards_hwp.extract_blocks


def extract_blocks(filename, data):
    if data[:5] != b"%PDF-":
        return orig_extract(filename, data)
    info = sp.identify(filename) or {}
    return pdf_blocks(data, known_set(info.get("framework"), info.get("code")))


standards_hwp.extract_blocks = extract_blocks
if hasattr(standards, "extract_blocks"):
    standards.extract_blocks = extract_blocks

docs = []
for name, data in standards.iter_source_files(SRC.name, SRC.read_bytes()):
    doc = standards.build_doc(name, data)
    doc["title"] = {"1118": "재무제표 표시와 공시"}.get(doc["code"], doc["title"]) if doc["framework"] == "kifrs" else doc["title"]
    docs.append(doc)
    print(f"  {doc['framework']:5} {doc['code']:>6}  문단 {sum(1 for u in doc['units'] if u['no']):5}  {doc['title']}")
m = standards.write_bundle(docs)
print("총", len(m["items"]))
