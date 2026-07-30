# AI 기반 회계감사 지원 시스템 — 초기 설계서 (Initial Design)

- 문서 버전: 0.2
- 작성일: 2026-07-29 / 개정일: 2026-07-30
- 상태: **발주자 검토 완료, 핵심 결정사항 확정** — 상세 설계 문서 작성 및 MVP 1 착수 가능
- 근거 문서: 발주자 요구사항 명세 (2026-07-29 접수), 발주자 결정사항 (2026-07-30 접수)

## 확정된 결정사항 (2026-07-30)

| # | 항목 | 결정 |
|---|---|---|
| 1 | 적용 회계기준 기본값 | **일반기업회계기준(K-GAAP)**. K-IFRS는 확장 옵션 |
| 2 | 전체 중요성 계산 기본 공식 | **(자산총액 + 매출총액) ÷ 2 × 1%**. 수행중요성·명백히 경미한 기준의 기본 비율(75% / 5%)은 제안값이며, 모든 값은 여전히 Partner 승인 필수 |
| 3 | 표본 수 추천 공식 | Claude 추천안 채택: **비통계적 보증계수 방식** (상세: docs/audit-methodology.md §7) |
| 4 | 파일 저장소 | **원천자료 저장과 산출물 백업 모두 Google Drive** (S3 대체). 저장소 추상화 계층으로 구현 |
| 5 | AI 데이터 송신 정책 | **원문 그대로 송신**. 단, 상충점과 권고사항은 docs/security-model.md §4 참조 (주민등록번호 등 고유식별정보 자동 마스킹은 기본 유지 권고, 로그 마스킹은 원 요구사항대로 유지) |
| 6 | 저장소 분리 | **별도 저장소(ai-audit-assistant, 비공개)로 분리** 확정. 생성 완료 시 본 브랜치의 문서·구조를 그대로 이전 |

미결 사항: §10의 A4(이상분개 임계값), A5(조서번호 체계), A6(완료 체크리스트 정본), B7(배포 환경), B9(작업 큐 — 권장안: Postgres 경량 큐), B10(OCR), B11(사용자 규모), C12~C14, D16. 이들은 MVP 1 진행 중 기본안으로 제안 후 확정한다.

---

## 목차

1. [프로젝트 목표와 범위](#1-프로젝트-목표와-범위)
2. [자동화 가능한 절차와 자동화하면 안 되는 판단의 구분](#2-자동화-가능한-절차와-자동화하면-안-되는-판단의-구분)
3. [시스템 아키텍처](#3-시스템-아키텍처)
4. [데이터 흐름도](#4-데이터-흐름도)
5. [핵심 데이터베이스 테이블](#5-핵심-데이터베이스-테이블)
6. [사용자 역할과 승인체계](#6-사용자-역할과-승인체계)
7. [MVP 구현 순서](#7-mvp-구현-순서)
8. [주요 위험과 통제방안](#8-주요-위험과-통제방안)
9. [예상 폴더 구조](#9-예상-폴더-구조)
10. [구현 전 발주자가 결정해야 하는 사항](#10-구현-전-발주자가-결정해야-하는-사항)

---

## 1. 프로젝트 목표와 범위

### 1.1 목표

한국 공인회계사가 사용하는 **AI 기반 회계감사 지원(assistance) 프로그램**을 구축한다.

핵심 포지셔닝:

> AI는 감사의견을 결정하는 주체가 아니라, **회계사가 승인한 감사계획과 중요성 기준 아래에서
> 반복적·체계적 감사절차를 수행하고, 감사증거와 판단 근거를 추적 가능한 형태로 정리하여
> 감사조서와 감사보고서 "초안"을 생성하는 보조 도구**이다.

시스템이 달성해야 하는 가치:

| 가치 | 설명 |
|---|---|
| 절차의 체계화 | 수임 → 이해 → 중요성 → 위험평가 → 실증절차 → 완료 → 보고서 초안까지 표준 워크플로우 강제 |
| 증거 추적성 | 모든 결론은 원천자료(파일·시트·셀·페이지)와 수행절차에 링크. 근거 없는 결론은 저장 불가 |
| 인간 통제(Human-in-the-loop) | 유의적 판단(중요성, 유의적 위험, 부정위험, 표본 수, 감사차이 평가, 감사의견)은 회계사 승인 필수 |
| 재현성 | 동일 입력 → 동일 출력. 표본 seed, 계산식, 프롬프트 버전, 모델 버전을 모두 기록 |
| 감사품질 문서화 | 감사기준(회계감사기준/ISA 정합)의 문서화 요구를 전자조서 구조로 반영 |

### 1.2 명시적 비목표 (Out of Scope)

시스템이 **하지 않는 것**:

- AI 단독의 감사의견 확정, 감사보고서 최종 발행
- 입력자료에 없는 거래·계정·금액·계약·통제·감사증거의 생성(환각 금지)
- 자료 부족 시의 추정·단정 (→ "자료 부족 / 추가 확인 필요 / 담당자 판단 필요"로 표시)
- 조회서 발송·외부회신의 진위 판단 자동화
- 원본자료의 수정 (읽기 전용 보존)
- 중요성·표본 수·위험등급의 자동 확정 (계산안·추천안 제시까지만)
- 초기 버전에서: 연결감사, 내부회계관리제도(ICFR) 감사, IT 일반통제(ITGC) 테스트 자동화, 그룹감사 (확장 가능한 구조만 확보)

### 1.3 범위 (초기 버전)

- **대상 입력자료**: 요구사항 §2의 20종 자료 (시산표, 총계정원장, 분개장, 재무제표, 각종 명세, 조회서, 의사록, 경영진확인서 등)
- **파일 형식**: XLSX, CSV, PDF, DOCX (HWP는 PDF/DOCX 변환본으로 수용)
- **감사 워크플로우**: 요구사항 §3의 A~K 11개 모듈
- **계정과목**: 요구사항 §3.F의 20개 계정 영역 (MVP 단계별 순차 지원)
- **언어**: 한국어 우선, 계정과목 한/영 매핑 테이블 유지
- **회계·감사기준**: 일반기업회계기준(K-GAAP) 기본, K-IFRS 확장 옵션. 대한민국 회계감사기준(ISA 기반)

---

## 2. 자동화 가능한 절차와 자동화하면 안 되는 판단의 구분

이 구분은 시스템 전체의 헌법이다. 코드 레벨에서는 각 산출물에
`requires_professional_judgment: bool`과 `reviewer_approval_required: bool` 필드로 구현되며,
승인 게이트(approval gate)를 통과하지 않은 판단은 후속 단계에서 참조할 수 없다.
정본은 docs/human-review-policy.md 이다.

### 2.1 완전 자동화 가능 (AI/시스템 수행 → 회계사 검토는 사후적)

**기계적 검증·계산·대사 — 정답이 존재하는 절차:**

- 파일 형식·인코딩·스키마 검증, 원본 해시 저장
- 시산표 차변·대변 합계 검증
- 시산표 ↔ 총계정원장 ↔ 재무제표 상호 대사
- 전기 대비 증감액·증감률 계산
- 비율분석(매출총이익률, 회전율 등), 월별·분기별 추이 집계
- 음수 잔액·비정상 잔액 탐지, 단위(원/천원/백만원) 혼재 탐지
- 중복 분개, 정수 금액, 휴일·비업무시간 입력, 결산일 전후 거래 등 **규칙 기반** 이상분개 플래그
- 모집단 완전성 검증(합계 대사), seed 기반 무작위·계통 표본 **추출 실행** (표본 수 확정은 제외)
- 중요성 기준별 **계산안** 산출 (기준·비율 확정은 제외)
- 중요성 초과 계정 목록화(중요계정 후보 식별)
- 감사차이의 개별·누적 합산, 중요성 대비 비율 계산, 수정분개·미수정왜곡표시 요약표 생성
- 조서 서식 채우기, 상태·이력·버전 관리, 체크리스트 미완료 항목 집계

**AI 보조 생성 — 초안·후보·요약 (반드시 "제안" 상태로 저장):**

- 사업모델·계약·의사록 요약, 전기 대비 변동사항 서술 초안
- 위험 "후보" 제안 (risk candidate)
- 계정별 감사프로그램 초안 생성 (표준 템플릿 + 식별된 위험 매핑)
- 이상항목에 대한 추가 감사절차 제안
- 조서 서술부 초안, 보고서 문단 초안 (템플릿 + 구조화 결론 기반)
- 회사 설명과 원천자료 간 불일치 플래그

### 2.2 회계사 승인 필수 (AI는 제안까지만 — 승인 게이트)

| # | 판단 사항 | AI의 역할 한계 | 승인 권한 |
|---|---|---|---|
| 1 | 수임/계약 유지 결정 | 체크리스트 결과 집계까지 | Engagement Partner |
| 2 | 독립성·이해상충 결론 | 체크리스트 응답 정리까지 | Engagement Partner |
| 3 | 중요성·수행중요성·명백히 경미한 기준 | 기준별 계산안 제시까지 | Partner (또는 Manager 제안 + Partner 승인) |
| 4 | 유의적 위험·부정위험 지정 | 후보 제안 + 근거 정리까지 | Partner |
| 5 | 위험평가 결과(고유·통제위험 등급) | 후보 등급 제안까지 | Manager 이상 |
| 6 | 표본 수·표본설계 확정 | 입력값 기반 추천안까지 | Manager 이상 |
| 7 | 회계추정치의 합리성 결론 | 재계산·범위 비교까지 | Manager 이상 |
| 8 | 감사차이의 왜곡표시 분류·수정 요구 여부 | 집계·비율 계산까지 | Manager 제안 + Partner 결론 |
| 9 | 계속기업 관련 결론 | 경고신호 목록화까지 | Partner |
| 10 | 특수관계자 완전성 결론 | 식별·대사 결과 정리까지 | Partner |
| 11 | 외부조회 회신의 진위·차이 해소 | 차이 계산·목록화까지 | 담당자 수행 + Manager 검토 |
| 12 | 각 조서의 결론(Sign-off) | 초안 작성까지 | 작성자 → 검토자 → (필요시) Partner |
| 13 | **감사의견 선택 및 보고서 확정** | 구조화 결론 요약 + 선택지 제시까지 | **Partner 단독, 명시적 선택 + 최종 승인** |
| 14 | COMPLETED/LOCKED 조서의 변경 | 불가 — 새 버전 생성만 가능 | 검토자 재승인 필요 |

### 2.3 자동화 금지 (시스템이 시도조차 하지 않는 것)

- 감사의견의 자동 결정·자동 기본값 설정 (기본값 없음 — 반드시 명시적 선택)
- 조회서 회신의 진위 판단
- 존재하지 않는 증거·거래의 생성
- 회계사 계정 권한의 자동 상승, 승인 단계 우회
- 원본 파일의 수정·삭제

---

## 3. 시스템 아키텍처

### 3.1 전체 구성

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js + TypeScript)                                │
│  감사 대시보드 · 조서 편집기 · 검토/승인 UI · 클라이언트 포털      │
└───────────────┬─────────────────────────────────────────────────┘
                │ HTTPS (JWT, RBAC)
┌───────────────▼─────────────────────────────────────────────────┐
│  Backend API (Python + FastAPI)                                 │
│  ┌───────────────┐ ┌───────────────┐ ┌────────────────────────┐ │
│  │ Auth / RBAC   │ │ Engagement    │ │ Approval Workflow      │ │
│  │               │ │ Management    │ │ (상태기계 + 승인게이트) │ │
│  ├───────────────┤ ├───────────────┤ ├────────────────────────┤ │
│  │ Ingestion     │ │ Audit Engine  │ │ Working Paper          │ │
│  │ (파일 검증·   │ │ (대사·분석·   │ │ (조서 생성·버전·       │ │
│  │  파싱·해시)   │ │  이상탐지 등  │ │  근거링크 검증)        │ │
│  │               │ │  결정적 로직) │ │                        │ │
│  ├───────────────┤ ├───────────────┤ ├────────────────────────┤ │
│  │ AI Orchestr.  │ │ Sampling      │ │ Report Drafting        │ │
│  │ (Anthropic    │ │ (seed 기반    │ │ (템플릿 + 구조화 결론) │ │
│  │  API 게이트)  │ │  재현 가능)   │ │                        │ │
│  └───────────────┘ └───────────────┘ └────────────────────────┘ │
│  횡단 관심사: Audit Trail(불변 로그) · JSON Schema 검증 ·        │
│               PII 마스킹 · Decimal 금액 처리                     │
└───────┬───────────────┬───────────────────┬─────────────────────┘
        │               │                   │
┌───────▼──────┐ ┌──────▼──────────┐ ┌──────▼───────────────┐
│ PostgreSQL   │ │ Task Queue      │ │ Storage              │
│ (업무 데이터  │ │ (비동기 작업:   │ │ (dev: 로컬 /         │
│  + 감사로그)  │ │  파싱·분석·AI)  │ │  운영: Google Drive) │
│              │ │                 │ │ 원본 read-only +     │
│              │ │                 │ │ 해시 검증            │
└──────────────┘ └─────────────────┘ └──────────────────────┘
                        │
                 ┌──────▼──────────┐
                 │ Anthropic API   │  ← 송신 정책: security-model.md §4,
                 │ (Claude)        │     요청/응답 원문·모델·프롬프트버전 저장
                 └─────────────────┘
```

### 3.2 계층 설계 원칙

**핵심 분리: "결정적(deterministic) 감사 엔진"과 "AI 계층"의 격리**

1. **Audit Engine (결정적 로직)** — 대사, 검증, 계산, 이상탐지 규칙, 표본추출, 집계.
   pandas + Decimal 기반 순수 함수. AI를 전혀 호출하지 않으며, 단위테스트로 100% 검증 가능.
   *감사증거의 수치적 사실은 전부 이 계층에서 확정된다.*
2. **AI Orchestration 계층** — 요약·서술·후보 제안만 담당. 출력은 반드시 JSON Schema 검증을
   통과해야 저장되고, `evidence_refs`가 비어 있거나 `confidence`가 낮으면 자동으로 검토대상 분류.
   AI가 수치를 "말하는" 것은 허용하되, 저장 시 Audit Engine이 원천자료에서 재검증한 값만 사실로 기록.
3. **Approval Workflow 계층** — 상태기계. 모든 상태 전이는 권한 검사 + 전제조건 검사
   (예: 근거 링크 없는 조서는 NEEDS_REVIEW로 전이 불가) + 감사로그 기록을 통과해야 한다.
4. **Ingestion 계층** — 파일 수령 즉시 SHA-256 해시 저장, 원본은 불변 저장, 파싱 결과는
   별도 정규화 테이블에 저장(원본과 파싱본의 분리). 파싱 실패·열이름 변경·단위 의심은
   `ingestion_issues`로 기록하고 담당자 확인을 요구.

### 3.3 기술 스택 검토 (요구안 대비)

| 영역 | 요구안 | 검토 의견 | 채택안 |
|---|---|---|---|
| Backend | Python + FastAPI | 적합. 데이터 처리(pandas)·AI SDK 생태계와 일치 | **채택** |
| DB | PostgreSQL | 적합. JSONB(AI 구조화 출력), 파티셔닝(감사로그), row-level 무결성에 강함 | **채택** |
| ORM | SQLAlchemy | 적합 (2.x + Alembic 마이그레이션) | **채택** |
| Task queue | Celery | 적합하나 초기 규모에는 무겁다. **대안: 동일 Postgres를 브로커로 쓰는 경량 큐(예: procrastinate/dramatiq)** — 인프라 1개(Redis) 절감, 트랜잭션 일관성 유리. 단, Celery는 레퍼런스가 풍부 | MVP 1: **Postgres 기반 경량 큐 권장**, 규모 확대 시 Celery 전환 가능한 인터페이스로 추상화. §10 결정사항 |
| Frontend | React 또는 Next.js | **Next.js(App Router) + TypeScript** 권장 — 폼·테이블 중심 업무 UI, 코드 분할, 국문 UI | **Next.js 채택** |
| 파일 저장 | 로컬/S3 분리 | **발주자 결정으로 Google Drive 채택** (원천자료 + 산출물 백업). StorageInterface 추상화: dev=로컬 파일시스템, 운영=Google Drive API(서비스 계정 + 전용 공유드라이브). 원본 불변성은 해시 기록 + 앱 수정 API 부재 + 주기적 해시 재검증으로 보강 | **Google Drive 채택** |
| Excel | openpyxl, pandas | 적합. 대용량 원장은 `read_only` 스트리밍 + 청크 처리 | **채택** |
| PDF | 텍스트 추출 + 페이지 근거 | pypdf/pdfplumber. 스캔 PDF는 OCR 필요 여부만 플래그(초기엔 OCR 미포함, §10 결정사항) | **채택(+OCR은 보류)** |
| DOCX | python-docx | 적합 | **채택** |
| AI | Anthropic API | 적합. 모델·프롬프트 버전·원문 저장, 구조화 출력(JSON Schema) 강제 | **채택** |
| 인증 | RBAC | JWT + 서버측 세션 무효화, 역할·업무별 이중 스코프(role × engagement 멤버십) | **채택** |
| 감사로그 | 불변 로그 | append-only 테이블 + 이전 행 해시 체인(변조 탐지). DB 권한으로 UPDATE/DELETE 차단 | **채택** |
| 테스트 | pytest | + hypothesis(속성 테스트: 대사·표본 재현성), factory 기반 픽스처 | **채택** |
| 배포 | Docker | docker-compose(dev) → 운영 형태는 §10 결정사항(온프레미스 vs 클라우드) | **채택** |

### 3.4 AI 호출 계약 (모든 AI 태스크 공통)

모든 AI 태스크는 다음 봉투(envelope)로 저장된다 (스키마: schemas/ai_envelope.v1.json):

```json
{
  "task_type": "risk_candidate_generation",
  "prompt_version": "risk-cand-v1.3",
  "model": "claude-...",
  "input_refs": ["doc:123#sheet=시산표!A1:F200"],
  "raw_response": "...(원문, 저장 시 PII 마스킹)",
  "structured_output": {
    "conclusion": "...",
    "confidence": "high | medium | low",
    "evidence_refs": ["evid:456", "..."],
    "source_locations": [{"file": "...", "sheet": "...", "cell_range": "..."}],
    "calculations": [],
    "assumptions": [],
    "missing_information": [],
    "exceptions": [],
    "proposed_follow_up": [],
    "requires_professional_judgment": true,
    "reviewer_approval_required": true
  },
  "schema_id": "risk_candidate.v1",
  "schema_valid": true,
  "processed_at": "..."
}
```

- `schema_valid = false` → 저장하지 않고 재처리 큐 또는 사용자 검토 상태로 전환
- `confidence = low` 또는 `evidence_refs = []` → 자동으로 `NEEDS_REVIEW` 분류
- AI 송신 정책은 security-model.md §4 (원문 송신 확정 + 고유식별정보 마스킹 권고)

---

## 4. 데이터 흐름도

### 4.1 자료 수령 → 검증 → 정규화

```
[Client User/감사팀 업로드]
      │
      ▼
(1) 원본 저장  ──►  Storage (read-only, SHA-256 해시 기록)
      │
      ▼
(2) 형식 검증  ──►  실패 시: ingestion_issues 기록 + 업로더에게 반려
      │                (형식 오류, 열이름 불일치, 인코딩, 손상)
      ▼
(3) 파싱·정규화 ──►  trial_balance_lines / gl_entries / ... 정규화 테이블
      │                (원본은 절대 수정하지 않음; 별도 사본에 정규화)
      ▼
(4) 데이터 품질 검사
      ├─ 차변·대변 합계 검증
      ├─ 단위 혼재 탐지 (원/천원/백만원)
      ├─ 중복·음수·공백 탐지
      └─ 계정과목 한/영 매핑
      │
      ▼
(5) 상호 대사  ──►  reconciliations 테이블 (시산표↔원장↔재무제표)
      │                불일치 → exceptions 생성 → 담당자 배정
      ▼
(6) 분석 준비 완료 (상태: 자료 검증됨)
```

### 4.2 감사 수행 흐름 (승인 게이트 표시: ◆)

```
A. 수임·독립성 ──◆ Partner 수임 승인 ──► B. 기업 이해 (AI 요약 + 불일치 플래그)
                                              │
                                              ▼
                              C. 중요성: 시스템 계산안 제시 ──◆ 회계사 입력/승인
                                              │
                                              ▼
                              D. 위험평가: AI 위험후보 제안 ──◆ 유의적/부정위험 Partner 승인
                                              │
                                              ▼
                              E. 분석적 절차 + 이상분개 탐지 (결정적 엔진)
                                              │  이상항목 → 추가절차 제안(AI) → 담당자 배정
                                              ▼
                              F. 계정별 감사프로그램 생성(AI 초안) ──◆ Manager 승인
                                              │
                                              ▼
                              G. 표본선정: 추천안 제시 ──◆ 표본 수 승인 ──► seed 기반 추출
                                              │
                                              ▼
                              H. 조회·증빙검사 (담당자 수행, 시스템은 대사·차이계산·미회신 관리)
                                              │
                                              ▼
                              I. 감사차이 집계 ──◆ 분류·평가 승인 ──► 수정분개/SUM 요약표
                                              │
                                              ▼
                              J. 완료절차 체크리스트 (전 항목 통과 필수)
                                              │
                                              ▼
                              K. 보고서 초안: 필수 입력값 + 구조화 결론 ──◆ 의견 선택 + Partner 최종 승인
```

### 4.3 조서 생성·검토 흐름

```
절차 수행 결과 (Audit Engine 산출 + AI 초안)
      │
      ▼
조서 초안 생성 (조서번호 자동 채번, 근거 링크 자동 연결)
      │
      ▼
[검증 게이트] 결론 ↔ evidence_refs 연결 확인
      │   연결 없음 → NEEDS_REVIEW 전이 불가 (하드 블록)
      ▼
작성자 서명 → NEEDS_REVIEW → 검토자 코멘트(REVIEW_COMMENT)
      │                          │
      │                          ▼
      │                    REWORK_REQUIRED → (수정 후 재제출)
      ▼
CLEARED → (유의적 영역) PARTNER_APPROVAL_REQUIRED → COMPLETED → LOCKED
      │
      └─ LOCKED 후 변경 필요 시: 새 버전 생성 + 변경이력 + 재승인
```

모든 화살표(상태 전이)는 `audit_trail`에 (누가, 언제, 무엇을, 이전값→새값, 사유) append-only 기록.

---

## 5. 핵심 데이터베이스 테이블

필드 수준 정의는 docs/data-model.md 참조. 금액 컬럼은 전부 `NUMERIC(20, 2)` (Decimal), 시각은 `TIMESTAMPTZ`.

### 5.1 조직·업무

| 테이블 | 핵심 컬럼 | 비고 |
|---|---|---|
| `users` | id, name, email, role, is_active | 역할: §6 참조 |
| `clients` | id, name, business_no, industry, fiscal_year_end | 피감사회사 |
| `engagements` | id, client_id, period_start/end, prior_auditor, prior_opinion, status, partner_id | 감사업무 단위. 모든 데이터의 최상위 스코프 |
| `engagement_members` | engagement_id, user_id, role_in_engagement | RBAC 이중 스코프 |
| `independence_checks` | engagement_id, item, answer, answered_by, partner_conclusion | 수임 단계 |

### 5.2 자료·근거

| 테이블 | 핵심 컬럼 | 비고 |
|---|---|---|
| `documents` | id, engagement_id, doc_type, filename, sha256, storage_uri, uploaded_by, is_original(항상 true), version | 원본 불변 |
| `document_extractions` | document_id, extractor_version, status, issues(JSONB) | 파싱 결과 메타 |
| `trial_balance_lines` | engagement_id, document_id, account_code, account_name, debit, credit, period | 정규화 시산표 |
| `gl_entries` | engagement_id, document_id, entry_no, date, account, debit, credit, description, created_time, preparer | 정규화 원장/분개장 |
| `account_mappings` | account_code, name_ko, name_en, statement_line, category | 한/영·FS라인 매핑 |
| `evidence_items` | id, engagement_id, document_id, locator(JSONB: sheet/cell/page), extracted_value, extracted_by(engine/ai/human) | **모든 결론이 가리키는 근거의 원자 단위** |
| `reconciliations` | engagement_id, type(TB↔GL 등), left_ref, right_ref, difference, status | 대사 결과 |
| `ingestion_issues` | document_id, issue_type(단위혼재/열변경/손상/중복 등), detail, resolved_by | 품질 이슈 |

### 5.3 감사 판단·절차

| 테이블 | 핵심 컬럼 | 비고 |
|---|---|---|
| `materiality` | engagement_id, basis(avg_assets_revenue 기본), benchmark_amount, rate, overall, performance, trivial_threshold, proposed_by(system), approved_by, approved_at, version | 승인 전 값은 어디에서도 참조 불가 |
| `risks` | risk_id, engagement_id, account, assertion, description, rationale, inherent_risk, control_risk, is_significant, is_fraud_risk, related_controls, planned_response, required_evidence, assignee, reviewer, status, proposed_by(ai/human), approved_by | 요구사항 §3.D 필드 전체 |
| `analytical_results` | engagement_id, analysis_type, account, current, prior, variance, variance_pct, threshold_rule, flagged, evidence_refs | 분석적 절차 |
| `anomalies` | engagement_id, source(je_test 등), rule_id, gl_entry_ref, amount, pct_of_materiality, detection_rule, evidence_refs, proposed_follow_up, status | 이상항목 |
| `audit_programs` | engagement_id, account_area, objective, assertions, risks(FK), procedures(JSONB), status, prepared_by, reviewed_by, approval_status | 계정별 프로그램 |
| `samples` | id, engagement_id, program_id, population_ref, population_total, reconciled_to_gl(bool), method(전수/목적/무작위/계통/MUS), seed, recommended_size, approved_size, approved_by, exclusions(JSONB: 사유 포함) | 재현 가능 표본 |
| `sample_items` | sample_id, source_ref, tested, result, exception_ref | 개별 표본 |
| `confirmations` | engagement_id, type(은행/채권채무/변호사), counterparty, sent_date, response_date, book_amount, confirmed_amount, difference, alternative_procedure_ref, status(미회신 관리) | 조회 |
| `audit_differences` | adjustment_id, engagement_id, account, debit, credit, amount, category(사실/판단/추정), found_in_procedure, cause, fs_impact, tax_impact, corrected(bool), uncorrected_reason, pct_of_materiality, cumulative_impact, disclosure_impact, accountant_conclusion, review_status | 요구사항 §3.I 전체 |
| `estimates_reviews`, `going_concern_indicators`, `related_parties`, `subsequent_events`, `contingencies` | (영역별 상세는 data-model.md) | MVP 2~3 |

### 5.4 조서·검토·보고서

| 테이블 | 핵심 컬럼 | 비고 |
|---|---|---|
| `working_papers` | wp_no, engagement_id, title, purpose, related_risks(FK[]), related_assertions, population_ref, sample_ref, procedures_performed, source_documents(FK[]), results, exceptions, further_procedures, conclusion, conclusion_evidence_refs(FK[] — **비어 있으면 완료 전이 불가**), preparer, prepared_at, reviewer, reviewed_at, review_notes, note_resolutions, attachments, version, status | 요구사항 §4 전체 필드 |
| `wp_versions` | wp_id, version, snapshot(JSONB), changed_by, change_reason | LOCKED 후 변경은 새 버전 |
| `review_notes` | wp_id, author, note, status(open/resolved), resolved_by, resolution | 검토의견 및 해소 |
| `report_drafts` | engagement_id, framework(기본 K-GAAP), auditing_standards, statements_covered, balance_date, period, mgmt_responsibility, tcwg_responsibility, auditor_responsibility, **opinion_type(기본값 없음, NULL 시 생성 불가)**, modification_basis, eom_om_paragraphs(JSONB), going_concern_paragraph, kam(JSONB, 확장용), report_date, auditor_info, partner_final_approval_by/at, status | 요구사항 §3.K 필수 입력 전체 |
| `completion_checklist` | engagement_id, item_code, required(bool), status, evidence_ref, checked_by | 전 항목 통과 전 보고서 생성 차단 |

### 5.5 AI·로그·승인

| 테이블 | 핵심 컬럼 | 비고 |
|---|---|---|
| `ai_tasks` | id, engagement_id, task_type, prompt_version, model, input_refs, raw_response_masked, structured_output(JSONB), schema_id, schema_valid, confidence, processed_at | §3.4 봉투 |
| `approvals` | id, engagement_id, subject_type(materiality/risk/sample/difference/report...), subject_id, action, decided_by, decided_at, decision, rationale | 모든 승인의 단일 원장 |
| `audit_trail` | id(BIGSERIAL), engagement_id, actor, action, entity_type, entity_id, before(JSONB, 마스킹), after(JSONB, 마스킹), occurred_at, prev_hash, row_hash | **append-only + 해시 체인**. DB 계정에 UPDATE/DELETE 권한 미부여 |

---

## 6. 사용자 역할과 승인체계

### 6.1 역할 정의

| 역할 | 주요 권한 | 금지 사항 |
|---|---|---|
| **Admin** | 사용자·시스템 설정 관리 | 감사 판단·승인 불가(감사 데이터 접근은 설정 목적 최소화) |
| **Engagement Partner** | 수임 결정, 중요성 승인, 유의적/부정위험 승인, 감사차이 최종 결론, **감사의견 선택·보고서 최종 승인**, LOCK | — |
| **Manager** | 위험평가·표본·프로그램 승인, 조서 검토, 감사차이 평가 제안 | 의견 선택, 수임 결정 |
| **Senior** | 절차 수행, 조서 작성, Staff 조서 1차 검토 | 유의적 판단 승인 |
| **Staff** | 절차 수행, 조서 작성, 자료 업로드 | 검토·승인 전반 |
| **Read-only Reviewer** | 전체 열람(품질관리검토자·심리실 용도) | 일체의 작성·변경·승인 불가 |
| **Client User** | 요청자료 제출, 질의 답변 | 감사 데이터·조서·위험·차이·의견 관련 일체 접근 불가 |

권한은 `role × engagement_members` 이중 검사: 해당 업무에 배정되지 않은 사용자는 역할과 무관하게 접근 불가.

### 6.2 승인 매트릭스 (핵심 게이트)

| 승인 대상 | 작성/제안 | 검토 | 최종 승인 |
|---|---|---|---|
| 수임·독립성 결론 | Staff/Senior 집계 | Manager | **Partner** |
| 중요성 3종 | 시스템 계산안 | Manager | **Partner** |
| 위험평가(일반) | AI 후보 + Staff/Senior | — | **Manager** |
| 유의적 위험·부정위험 | AI 후보 + Manager | — | **Partner** |
| 감사프로그램 | AI 초안 + 작성자 | — | **Manager** |
| 표본 수·설계 | 시스템 추천안 | — | **Manager** |
| 조서(일반) | Staff/Senior | Senior/Manager | Manager |
| 조서(유의적 영역: 계속기업·부정·특수관계자·추정) | 작성자 | Manager | **Partner** |
| 감사차이 분류·평가 | 시스템 집계 + Manager | — | **Partner** |
| 완료 체크리스트 | 시스템 집계 | Manager | **Partner** |
| **감사의견·보고서** | 시스템 초안(의견 필드는 공란) | Manager | **Partner (명시적 선택 + 승인, 위임 불가)** |

구현 규칙:
- 자기승인 금지: `preparer == reviewer` 또는 `proposer == approver`인 전이는 시스템이 거부
- 승인은 반드시 `approvals` 테이블에 사유와 함께 기록
- 승인되지 않은 상위 게이트(예: 중요성 미승인)에 의존하는 하위 절차는 시작 자체가 차단됨

---

## 7. MVP 구현 순서

### MVP 1 — "자료 검증과 위험식별 파이프라인" (요구사항 §11 MVP 1의 15개 항목)

구현 순서 (각 단계는 테스트 + 샘플데이터 검증 통과 후 다음 단계 진행):

| 순서 | 항목 | 산출물 |
|---|---|---|
| 1-1 | 프로젝트 골격: FastAPI + Postgres + Next.js + Docker, RBAC 인증, audit_trail 기반 | 로그인·역할·불변로그 동작 |
| 1-2 | 회사·감사업무 등록 (clients, engagements, members) | 업무 생성 UI/API |
| 1-3 | 파일 업로드 + 원본 불변 저장 + 해시 + 형식 검증 | 시산표/원장 XLSX·CSV 수용 |
| 1-4 | 시산표·원장 파싱 정규화 + 데이터 품질 검증(차대 검증, 단위 탐지, 중복, 열 매핑) | ingestion_issues 리포트 |
| 1-5 | 시산표↔원장 대사 + (전기)재무제표 대사 | reconciliations + 불일치 예외 |
| 1-6 | 중요성 입력·계산안·승인 게이트 | materiality 승인 워크플로우 |
| 1-7 | 전기 대비 변동분석 + 중요계정 자동 식별 | analytical_results |
| 1-8 | 이상분개 탐지 (규칙 엔진: 휴일·정수·중복·결산 전후 등) | anomalies + 근거 링크 |
| 1-9 | AI 계층: 봉투·스키마 검증·마스킹 게이트 → 위험 후보 생성 | risks(제안 상태) |
| 1-10 | 계정별 감사프로그램 초안 생성 (템플릿 + 위험 매핑) | audit_programs |
| 1-11 | 감사조서 초안 생성 + 근거링크 하드 블록 | working_papers |
| 1-12 | 검토·승인 워크플로우 (상태기계 전체) + 미해결사항 대시보드 | 상태 전이 + 대시보드 |

**MVP 1 완료 기준**: 요구사항 §10 품질검증 데이터 중 시산표·원장 관련 8종
(정상, 차대불일치, 중복분개, 결산일 후 매출, 음수 채권, 거래처명 불일치, 단위 혼재, FS↔TB 불일치)이
전부 의도된 결과를 산출하고, 근거 없는 조서 완료가 차단됨을 통합테스트로 증명.

### MVP 2 — "핵심 실증절차"
매출·매출채권 감사 → 현금·금융기관조회 → 표본선정(승인 게이트 포함) → 유형자산 → 매입채무·차입금 → 감사차이 관리(수정분개·SUM 자동 생성).

### MVP 3 — "완료와 보고"
재고자산 → 충당부채·추정치 → 법인세 → 특수관계자 → 후속사건 → 계속기업 → 주석 체크리스트 → 완료절차 → 감사보고서 초안(의견 선택 + Partner 승인 게이트).

각 MVP 사이에 발주자(회계사) 검수 게이트를 둔다.

---

## 8. 주요 위험과 통제방안

### 8.1 AI·감사품질 위험

| # | 위험 | 통제방안 |
|---|---|---|
| 1 | **환각**: 존재하지 않는 거래·증거·금액 생성 | AI 출력의 모든 수치·참조는 Audit Engine이 원천자료에서 재검증한 것만 사실로 저장. `evidence_refs` 없는 결론은 저장 단계에서 거부. JSON Schema 검증 실패 시 폐기 |
| 2 | **자동화 편향**: 회계사가 AI 제안을 무비판 수용 | 모든 AI 산출물에 "AI 제안" 라벨 + confidence 표시. 승인 화면에 원천 근거 병렬 표시. 승인 사유 입력 필수. 일괄 승인(bulk approve) 기능 제공 안 함 |
| 3 | AI가 판단 영역을 침범 (의견 암시 등) | 프롬프트에 금지 지시 + 출력 스키마에 의견 필드 자체가 없음 + 보고서 의견 필드는 AI 쓰기 경로 부재(코드 레벨 차단) |
| 4 | 낮은 품질 출력의 무검토 유입 | `confidence=low` 또는 근거 빈약 → 자동 NEEDS_REVIEW. 스키마 불일치 → 재처리/사용자 검토 |
| 5 | 프롬프트·모델 변경으로 결과 비재현 | 모델 ID·프롬프트 버전·원문·시각 저장. 버전 변경은 릴리스 노트에 기록 |
| 6 | 감사기준 문서화 요건 미충족 조서 | 조서 필수 필드 + 완료 체크리스트 하드 블록. 결론-근거 연결 강제 |

### 8.2 데이터·처리 위험

| # | 위험 | 통제방안 |
|---|---|---|
| 7 | 부동소수점 오차 | 전 금액 Decimal/NUMERIC. float 사용을 lint/hook로 차단 |
| 8 | 단위 혼재(원/천원/백만원) | 자릿수 분포·상호 대사 기반 탐지 → 확정은 담당자. 문서별 단위 메타데이터 필수 |
| 9 | 열이름 변경·서식 다양성 | 열 매핑 프로파일 + 미매핑 열은 ingestion_issue로 반려(추측 매핑 금지) |
| 10 | 파일 손상·중복 업로드 | 해시 중복 탐지, 파싱 실패 시 명시적 반려 |
| 11 | 원본 훼손 | 원본은 저장소에 불변 저장, 애플리케이션에 수정 API 부재, 해시 재검증 |
| 12 | 재현 불가능한 표본·계산 | seed·계산식·필터 조건 전부 저장. 속성 테스트로 재현성 검증 |

### 8.3 보안·정보보호 위험

| # | 위험 | 통제방안 |
|---|---|---|
| 13 | 고객정보·개인정보의 외부 유출 (AI API 포함) | 발주자 결정으로 AI 송신은 원문 허용. 단 ① 주민등록번호 등 고유식별정보는 송신 전 자동 마스킹 기본 유지(권고, 설정으로 제어), ② 로그·audit_trail은 원 요구사항대로 마스킹 후 저장, ③ 감사계약 시 제3자 처리위탁 고지 필요(docs/security-model.md §4) |
| 14 | API key·비밀번호 노출 | 환경변수/시크릿 매니저만 사용. pre-commit + hook로 시크릿 패턴 커밋 차단 |
| 15 | 권한 상승·업무 간 데이터 접근 | role × engagement 이중 스코프, 모든 API에 스코프 검사, Client User 라우트 물리적 분리 |
| 16 | 감사로그 변조 | append-only + 해시 체인 + DB 권한에서 UPDATE/DELETE 제거 |
| 17 | 승인 우회 | 승인 게이트는 API 계층이 아닌 도메인 계층에서 강제(프론트 우회 불가). 자기승인 거부 |
| 18 | 외부회신 위·변조 | 시스템은 진위 판단을 하지 않음을 UI에 명시. 수령 경로·담당자 기록만 관리 |

### 8.4 프로젝트 위험

| # | 위험 | 통제방안 |
|---|---|---|
| 19 | 범위 과대(20개 계정 × 11개 모듈 동시 구현) | MVP 게이트 엄수. MVP 1 검수 전 MVP 2 착수 금지 |
| 20 | 실제 감사 실무와 UI/용어 불일치 | 각 MVP 검수를 발주 회계사가 직접 수행, 용어집(한/영) 우선 확정 |
| 21 | 규제 변화(감사기준 개정) | 체크리스트·템플릿을 코드가 아닌 데이터(버전 관리되는 시드 데이터)로 관리 |

---

## 9. 예상 폴더 구조

```
ai-audit-assistant/
├── CLAUDE.md                        # 핵심 원칙·금지사항만 간결히
├── README.md
├── docs/
│   ├── initial-design.md            # 본 문서
│   ├── product-requirements.md      # 요구사항 정본
│   ├── audit-methodology.md         # 워크플로우 A~K, 주장·절차 매핑, 표본 공식
│   ├── data-model.md                # 전체 ERD·테이블 정의
│   ├── security-model.md            # RBAC, 마스킹, 로그 정책, AI 송신 정책
│   ├── human-review-policy.md       # 자동화/승인 구분의 정본
│   └── report-generation-policy.md  # 보고서 필수 입력·의견 선택 정책
├── schemas/                         # AI 구조화 출력 JSON Schema (버전 관리)
│   ├── ai_envelope.v1.json
│   ├── risk_candidate.v1.json
│   └── ...
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/                    # 설정, 보안, Decimal 유틸, 마스킹
│   │   ├── auth/                    # 인증·RBAC·engagement 스코프
│   │   ├── ingestion/               # 파일 검증·해시·파싱·정규화 (판단 로직 없음)
│   │   ├── audit_engine/            # 결정적 감사 로직 (AI 미호출, 순수 함수)
│   │   │   ├── reconciliation.py
│   │   │   ├── analytics.py
│   │   │   ├── je_anomaly_rules.py
│   │   │   ├── materiality_calc.py
│   │   │   └── sampling.py
│   │   ├── ai/                      # Anthropic 호출, 봉투, 스키마 검증, 프롬프트 버전
│   │   │   └── prompts/             # 버전 태그된 프롬프트
│   │   ├── workflow/                # 상태기계, 승인 게이트, 자기승인 차단
│   │   ├── working_papers/          # 조서 생성·버전·근거링크 검증
│   │   ├── reporting/               # 보고서 템플릿·초안 (의견 쓰기 경로 없음)
│   │   ├── storage/                 # StorageInterface: Local / GoogleDrive
│   │   ├── models/                  # SQLAlchemy 모델
│   │   ├── api/                     # 라우터 (team / client 분리)
│   │   └── audit_trail/             # append-only 로그·해시체인
│   ├── alembic/
│   └── pyproject.toml
├── frontend/
│   ├── app/                         # Next.js App Router
│   │   ├── (team)/                  # 감사팀 화면: 대시보드·조서·검토·승인
│   │   └── (client)/                # Client User 포털 (물리적 분리)
│   ├── components/
│   └── lib/
├── tests/
│   ├── unit/                        # audit_engine 순수 함수 테스트
│   ├── integration/                 # 업로드→대사→조서 파이프라인
│   ├── quality_scenarios/           # 요구사항 §10의 12종 시나리오
│   └── conftest.py
├── sample-data/                     # 테스트 데이터 (가공의 회사, 실데이터 금지)
│   ├── normal/
│   ├── unbalanced_tb/
│   ├── duplicate_je/
│   ├── unit_mixed/
│   └── ...
├── .claude/
│   ├── skills/                      # import-trial-balance, reconcile-ledger, calculate-materiality,
│   │                                #  perform-analytical-review, detect-journal-entry-anomalies,
│   │                                #  assess-account-risk, design-audit-procedure, select-audit-sample,
│   │                                #  evaluate-audit-differences, prepare-working-paper,
│   │                                #  perform-completion-check, draft-audit-report
│   ├── agents/                      # audit-planning, journal-entry-testing, revenue-audit,
│   │                                #  financial-instruments, tax-review, going-concern,
│   │                                #  disclosure-review, audit-report-review, data-quality, security-review
│   └── hooks/                       # 테스트 미통과 완료 차단, 스키마 검증, 근거 없는 결론 차단,
│                                    #  승인 없는 의견 차단, 시크릿 커밋 차단, PII 로그 차단, 원본 수정 차단
├── docker-compose.yml
└── .env.example                     # 실제 키 없음
```

---

## 10. 구현 전 발주자가 결정해야 하는 사항

**2026-07-30 결정 완료**: A1(회계기준=일반기업회계기준), A2(중요성 공식=(자산총액+매출총액)/2×1%),
A3(표본 공식=Claude 추천안 위임 → 비통계적 보증계수 방식 채택), B8(AI 송신=원문),
파일 저장소=Google Drive, D15(별도 저장소 분리). 상단 "확정된 결정사항" 표 참조.

### 미결 사항 (MVP 1 진행 중 기본안 제안 후 확정)

#### A. 감사 방법론 관련

4. **이상분개 탐지 규칙의 기본 임계값** — 예: "결산일 전후 N일", "정수 금액 기준", "비업무시간 정의(휴일 목록 포함)".
   기본안: audit-methodology.md §5.
5. **조서번호 체계** — 법인에서 사용하는 채번 규칙(예: A-100, B-200 계열)이 있으면 그대로 반영.
6. **완료 체크리스트 항목의 정본** — 감사기준 기반 기본안을 시스템이 제시하되, 법인 정책 반영 필요.

#### B. 시스템·인프라 관련

7. **배포 환경** — 온프레미스(법인 내부 서버) vs 클라우드(국내 리전). 고객정보 보관 위치 정책과 직결.
   *권장: 초기엔 단일 서버 Docker Compose, 위치는 발주자 정책 따름.*
9. **작업 큐 선택** — Celery+Redis vs Postgres 기반 경량 큐. *권장: MVP 1은 Postgres 기반 경량 큐(§3.3).*
10. **스캔 PDF의 OCR 지원 여부** — 초기 버전 포함 여부. *권장: MVP 3 이후로 연기, 우선 "OCR 필요" 플래그만.*
11. **사용자 규모와 동시 업무 수** — 인프라 사이징과 멀티테넌시(법인 1개 vs 여러 법인) 설계에 영향.
    *권장: 단일 법인 가정으로 시작.*

#### C. 데이터·보안 관련

12. **개인정보 마스킹 범위의 확정** — 고유식별정보 외에 급여 데이터의 개인 식별 정보 처리 수준 (security-model.md §6).
13. **자료 보존 연한** — 감사조서 보존 의무(외감법상 8년 등)에 맞춘 보존·파기 정책.
14. **Client User 포털의 MVP 포함 여부** — MVP 1에서는 감사팀 업로드만으로 시작할지.
    *권장: 클라이언트 포털은 MVP 2 이후.*

#### D. 저장소 관련

16. **브랜치·배포 전략** — main 보호, PR 리뷰 정책.

---

## 다음 단계

1. ~~발주자가 본 문서를 검토하고 §10의 결정사항에 답변~~ (완료, 2026-07-30)
2. ~~결정 반영하여 상세 정책 문서 작성~~ (완료 — docs/ 참조)
3. 별도 저장소(ai-audit-assistant) 생성 및 이전
4. MVP 1 구현 착수 (1-1 프로젝트 골격부터, §7의 순서대로)
