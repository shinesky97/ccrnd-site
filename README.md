# 공인회계사 손슬기 홈페이지

사업비 정산·세무·회계 인사이트를 나누는 개인 홈페이지입니다.
**Jekyll + GitHub Pages** 로 빌드되는 정적 사이트이며, 커스텀 도메인은 `www.ccrnd.com` 입니다.

전체 설계 배경은 [`DESIGN.md`](DESIGN.md) 를 참고하세요.

---

## 새 글 올리는 방법 (가장 중요)

글 하나 = 마크다운 파일 하나입니다.

1. `_posts/_TEMPLATE.md` 를 복사합니다.
2. 파일명을 `_posts/YYYY-MM-DD-영문주소.md` 형식으로 짓습니다.
   - 예) `_posts/2026-08-15-vat-early-refund.md`
   - **앞의 날짜 형식은 필수**입니다.
3. 파일 맨 위 설정을 채웁니다.

   ```yaml
   ---
   layout: post
   title: "글 제목"
   date: 2026-08-15
   category: tax          # settlement | tax | accounting | notice
   tags: [부가세, 환급]
   summary: "목록·공유 시 보이는 한 줄 요약"
   author: 손슬기
   ---
   ```
4. 그 아래에 마크다운으로 본문을 씁니다.
5. 커밋/푸시(또는 GitHub 웹에서 바로 커밋)하면 **몇 분 내 자동 게시**됩니다.

> 터미널 없이 **GitHub 웹사이트에서 `_posts` 폴더 → "Add file" → "Create new file"** 로도
> 글을 올릴 수 있습니다.

### 카테고리(분류) 코드

| 코드 | 이름 |
|------|------|
| `settlement` | 사업비·정산 실무 |
| `tax` | 세무 정보 |
| `accounting` | 회계·결산 정보 |
| `notice` | 공지·자료실 |

---

## 폴더 구조

```
_config.yml        사이트 설정(제목·메뉴·카테고리·연락처)
CNAME              커스텀 도메인 (www.ccrnd.com)
index.html         홈
about.md           소개
contact.html       문의 폼
downloads.md       자료실
insights/          인사이트 목록(전체 + 카테고리별)
_posts/            ★ 글(.md) — 여기에 파일만 추가하면 게시
_layouts/          페이지 템플릿
_includes/         머리글·바닥글·직인·글카드 조각
assets/css/        스타일시트
assets/files/      배포용 서식·PDF (자료실)
```

---

## 로컬 미리보기 (선택)

```bash
bundle install
bundle exec jekyll serve
# http://localhost:4000 에서 확인
```

한글이 포함되어 있으므로 UTF-8 로케일에서 빌드하세요.
(문제 발생 시 `export LANG=C.UTF-8 LC_ALL=C.UTF-8`)

---

## 배포 설정 (최초 1회)

GitHub 저장소 **Settings → Pages** 에서:

1. **Source**: Deploy from a branch
2. **Branch**: `main` / `/(root)`
3. **Custom domain**: `www.ccrnd.com` (CNAME 파일이 이미 포함되어 있음)
4. 도메인 DNS 에 `www` → `<사용자>.github.io` CNAME 레코드 등록,
   `Enforce HTTPS` 체크

> 현재 작업은 `claude/accountant-homepage-design-zu1ce3` 브랜치에 올라가 있습니다.
> `main` 에 병합한 뒤 위 Pages 설정을 적용하면 게시됩니다.

---

## 글쓰기 관리자 (Pages CMS)

터미널·마크다운 없이 웹에서 글을 쓸 수 있습니다.

1. [app.pagescms.org](https://app.pagescms.org) 접속 → **GitHub 로그인**
2. `shinesky97/ccrnd-site` 저장소 선택 (최초 1회 권한 허용)
3. **인사이트 글 → 새 글** → 제목·날짜·분류·본문 입력 → **Save/Publish**
   → 자동으로 `_posts/`에 커밋되고, 몇 분 뒤 사이트에 게시됩니다.

설정은 저장소의 `.pages.yml` 에 정의되어 있습니다.

---

## 분야별 뉴스 브리핑 자동화 (검토 후 발행)

`.github/workflows/news-digest.yml` + `scripts/news-digest.mjs` 가
**월·수·금 아침**에 세무·회계·정부보조사업 분야 최신 뉴스(Google News RSS)를
수집해 **브리핑 초안**을 만들고, **PR로 올립니다.**

- PR 내용을 확인하고 **병합(Merge)** 하면 사이트에 게시됩니다. (그냥 닫으면 게시 안 됨)
- 즉시 테스트: **Actions 탭 → "뉴스 브리핑 자동 초안" → Run workflow**
- 수집 주기 변경: 워크플로우의 `cron` 값 수정
- 중복 방지 기록: `_data/news_seen.json` (최근 500건 URL)

### ⚠️ 최초 1회 설정 (필수)

PR을 자동으로 열 수 있도록, 저장소 **Settings → Actions → General →
Workflow permissions** 에서:

1. **Read and write permissions** 선택
2. **Allow GitHub Actions to create and approve pull requests** 체크 → Save

(이 설정을 안 하면 워크플로우가 뉴스는 모으지만 PR 생성에서 실패합니다.)
