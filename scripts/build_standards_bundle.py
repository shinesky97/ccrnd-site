"""cpawork 회계기준서 데이터(standards_data/) → 홈페이지 업로드용 번들 1개.

사용법:
    python scripts/build_standards_bundle.py <cpawork>/webapp/app/standards_data  standards-bundle.json

만들어진 번들은 저장소에 커밋하지 마세요(기준서 원문 — 저작권: 한국회계기준원).
/standards/ 페이지에 관리자로 로그인한 뒤 '데이터 올리기'로 Firebase에 올립니다.
"""
import base64, gzip, json, sys
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])
manifest = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
items = []
for it in manifest["items"]:
    raw = (src / it["file"]).read_bytes()
    doc = json.loads(gzip.decompress(raw))
    items.append({
        "framework": it["framework"], "code": str(it["code"]), "title": it["title"],
        "version": it.get("version", ""), "source_file": it.get("source_file", ""),
        "sort": doc.get("sort", 9999), "paragraphs": it.get("paragraphs", 0), "sha": it.get("sha", ""),
        "gz": base64.b64encode(raw).decode("ascii"),
    })
bundle = {"format": "ccrnd-standards-bundle", "version": 1, "updated": manifest.get("updated", ""), "items": items}
out.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
print(f"{len(items)}개 기준서 → {out} ({out.stat().st_size/1e6:.1f}MB), 최대 gz {max(len(base64.b64decode(i['gz'])) for i in items)/1e3:.0f}KB")
