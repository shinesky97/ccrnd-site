# SEO 개편 체크리스트 & 변경 요약

회계법인 창천 정산검증센터(www.ccrnd.com) — 공공기관·전문기관 담당자의
"정산 회계법인 찾기" 검색 상위노출을 위한 SEO 전면 개편 내역입니다.

## 타깃 검색어

**1차:** 위탁정산 회계법인 · 연구개발비 정산 회계법인 · 정산검증 회계법인 · 사업비 정산 용역 · 국고보조금 정산검증
**2차:** 정부보조금 정산 회계법인 · R&D 정산 · RISE 사업비 정산 · 지자체 보조금 정산검증 · 테크노파크 정산 · 기금사업 정산검증 · 수의계약 회계법인 · 정산 수수료

## 변경 요약

### 브랜딩 (전체 리브랜딩)
- 사이트명 `공인회계사 손슬기` → **`회계법인 창천 정산검증센터`** (헤더·푸터·`_config.yml`·JSON-LD)
- 손슬기 = 담당/책임 공인회계사로 표기, 연락처 `010-4353-2560` / `seulgison@atcc.co.kr`
- 네비게이션을 정산 서비스 중심으로 재구성

### 페이지 구조
- **메인(`index.html`)** — title "위탁정산·정산검증 전문 회계법인 | 회계법인 창천 정산검증센터", h1에 핵심 검색어, 첫 화면에 ①수행 분야 실적 ②대응 가능 업무 ③수의계약 안내 배치
- **신설 랜딩 5종** (각 고유 title≤60·description≤150·h1, 본문 1,500자+, FAQ 6개, FAQPage 스키마):
  - `/rnd-settlement/` 연구개발비 위탁정산 (혁신법 제13조)
  - `/subsidy-verification/` 국고·지자체 보조금 정산검증 (보조금법 제27조 제2항·제27조의2)
  - `/rise-settlement/` RISE·지역사업 사업비 정산
  - `/fund-settlement/` 기금사업·출연사업 정산
  - `/private-contract/` 수의계약 절차 안내 (국가계약법 시행령 제26조)
- 메인↔랜딩, 랜딩↔랜딩 내부링크 상호 연결(각 랜딩 하단 "관련 서비스", 푸터 전 랜딩 링크)

### 기술적 SEO
- **JSON-LD**: 전 페이지 `AccountingService`(name·주소·email·areaServed KR), 각 랜딩에 `FAQPage`
- **title/canonical/OG/Twitter**: jekyll-seo-tag 단일 관리(중복 `<title>` 제거) → 전 페이지 canonical·Open Graph·Twitter Card 자동 출력
- **sitemap.xml**(jekyll-sitemap) 자동 생성, **robots.txt** 는 `/admin/` 만 차단·사이트맵 안내
- **meta keywords** 타깃 검색어로 갱신, 각 페이지 고유 description
- 시맨틱 HTML(header/nav/main/article/footer), 반응형 유지
- GSC 소유확인 자리: `_config.yml` `google_site_verification`(주석) + 레이아웃 안내 주석

### 법령 인용 (DB 검증 완료)
- 국가연구개발혁신법 제13조 = 연구개발비 지급·사용·정산(제8항: 단계 종료 후 3개월 내 정산)
- 보조금법 **제27조 제2항** = 정산보고서 적정성 검증 / **제27조의2** = 10억원 이상 회계감사
- 국가계약법 시행령 제26조 = 수의계약(제2호 차목 전문용역 / 제5호 가목 소액·특수지식 용역)

## 등록 체크리스트 (배포 후 담당자 실행)

### 구글 Search Console
- [ ] 속성 추가(URL 접두어 `https://www.ccrnd.com`)
- [ ] 소유확인 코드 → `_config.yml` `google_site_verification` 주석 해제 후 입력 → 배포 → 확인
- [ ] `sitemap.xml` 제출
- [ ] 홈·랜딩 5종 URL 검사 → 색인 생성 요청

### 네이버 서치어드바이저
- [ ] 사이트 등록(`https://www.ccrnd.com`)
- [ ] 소유확인(`naver_verification` — 기존 값 유지 중이면 그대로)
- [ ] `sitemap.xml` 제출 / (선택) `feed.xml` 제출

### 배포·운영
- [ ] `main` 병합 후 GitHub Pages 재배포 확인
- [ ] 실적(`index.html`)의 익명 표기를 실제 수행 범위에 맞게 최종 검수(과장·허위 금지)
- [ ] 필요 시 실명 공개 가능한 레퍼런스로 교체

## 완료 기준 자가점검
- [x] 신설 페이지 전부 내부링크 상호 연결
- [x] 각 title 60자 이내·고유, description 150자 이내·고유
- [x] 빌드 후 전 페이지 렌더 확인, 깨진 내부링크 0건
- [x] FAQPage·AccountingService JSON-LD 유효성 확인
