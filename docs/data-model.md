# 데이터 모델 (Data Model)

- 버전: 1.0 · 기준일: 2026-07-30
- 공통 규칙: 금액 = `NUMERIC(20,2)` (Decimal), 시각 = `TIMESTAMPTZ`, PK = UUID(엔터티) 또는
  BIGSERIAL(로그). 모든 업무 데이터는 `engagement_id`로 스코프된다.
- 요약 ERD와 테이블 목록은 initial-design.md §5 참조. 이 문서는 MVP 1 구현 대상 테이블의
  필드 수준 정의를 담는다. (MVP 2~3 테이블은 해당 MVP 착수 시 상세화)

## 1. 조직·업무

### users
| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | UUID PK | |
| name, email | TEXT | email UNIQUE |
| role | ENUM | admin / partner / manager / senior / staff / reviewer / client |
| password_hash | TEXT | argon2 |
| is_active | BOOL | |

### clients — 피감사회사
id, name, business_no(사업자번호, UNIQUE), industry, fiscal_year_end, created_at

### engagements — 감사업무 (모든 데이터의 최상위 스코프)
id, client_id FK, name, period_start, period_end, basis_framework(기본 'K-GAAP'),
prior_auditor, prior_opinion, partner_id FK(users), status(ENUM: 워크플로우 상태), created_at

### engagement_members
engagement_id FK, user_id FK, role_in_engagement — PK(engagement_id, user_id).
모든 API는 이 테이블로 접근 스코프를 검사한다.

## 2. 자료·근거

### documents — 원본 (불변)
id, engagement_id FK, doc_type(ENUM: trial_balance/general_ledger/journal/fs/…),
filename, sha256(64자), storage_uri(Drive file id 또는 로컬 경로), size_bytes,
uploaded_by FK, uploaded_at, version. **UPDATE/DELETE 없음** — 재업로드는 새 행(version+1).

### document_extractions
id, document_id FK, extractor_version, status(pending/ok/failed/needs_review),
issues JSONB, started_at, finished_at

### ingestion_issues
id, document_id FK, issue_type(ENUM: unbalanced/unit_mixed/column_unmapped/duplicate/corrupt/
negative_balance/encoding), severity(block/warn), detail JSONB, resolved_by FK NULL, resolved_at

### trial_balance_lines — 정규화 시산표
id, engagement_id, document_id FK, period(current/prior), account_code, account_name,
debit NUMERIC, credit NUMERIC, opening NUMERIC NULL, closing NUMERIC NULL, row_ref(원본 행 위치)

### gl_entries — 정규화 총계정원장/분개장
id, engagement_id, document_id FK, entry_no, entry_date, posted_at NULL(입력시각),
account_code, account_name, debit, credit, description, counterparty NULL,
preparer NULL, approver NULL, row_ref

### account_mappings — 계정과목 매핑
account_code, name_ko, name_en, statement_line(FS 표시 라인), category(자산/부채/자본/수익/비용),
is_contra BOOL. 시드 데이터로 관리, 미매핑 계정은 ingestion_issue(column_unmapped)로 반려.

### evidence_items — 근거의 원자 단위
id, engagement_id, document_id FK, locator JSONB(예: {"sheet":"시산표","cell_range":"C5:C5"} 또는
{"page":12}), extracted_value TEXT, value_numeric NUMERIC NULL, extracted_by(engine/ai/human),
created_at. **모든 결론·플래그·조서가 이 테이블을 참조한다.**

### reconciliations — 대사 결과
id, engagement_id, type(tb_gl/tb_fs/gl_fs/population_gl), left_ref JSONB, right_ref JSONB,
left_amount, right_amount, difference(계산 컬럼), status(matched/unmatched/resolved),
resolved_note, evidence_refs UUID[]

## 3. 감사 판단·절차 (MVP 1 범위)

### materiality
id, engagement_id, version, basis('avg_assets_revenue' 기본), benchmark_amount(자산·매출 평균),
rate(기본 0.01), overall, performance, trivial_threshold, specific JSONB NULL,
proposed_by('system'), approved_by FK NULL, approved_at NULL, status.
**approved_at IS NULL이면 어떤 후속 절차도 이 행을 참조할 수 없다** (서비스 계층 강제).

### analytical_results
id, engagement_id, analysis_type, account_code, current_amount, prior_amount,
variance, variance_pct, threshold_rule(규칙 ID+버전), flagged BOOL, evidence_refs UUID[]

### anomalies — 이상분개·이상항목
id, engagement_id, source(je_test/analytics), rule_id(JE-01 등), rule_version,
gl_entry_ids UUID[], amount, pct_of_materiality, detection_detail JSONB,
evidence_refs UUID[], proposed_follow_up TEXT, status, assignee FK NULL

### risks
risk_id(표시용 채번), id UUID, engagement_id, level(fs/assertion), account_code NULL,
assertions TEXT[](E/O,C,A,CO,CL,R&O,V,P&D), description, rationale,
inherent_risk(low/med/high), control_risk(low/med/high), is_significant BOOL,
is_fraud_risk BOOL, related_controls, planned_response, required_evidence,
assignee FK, reviewer FK, status, proposed_by(ai/human), ai_task_id FK NULL,
approved_by FK NULL, approved_at NULL

### audit_programs
id, engagement_id, account_area(20개 영역 ENUM), objective, assertions TEXT[],
risk_ids UUID[], procedures JSONB(절차 목록: 유형/설명/상태/담당),
status, prepared_by, reviewed_by, approval_status

## 4. 조서·검토

### working_papers
wp_no(채번), id, engagement_id, title, purpose, related_risk_ids UUID[],
related_assertions TEXT[], population_ref JSONB NULL, sample_ref UUID NULL,
procedures_performed TEXT, source_document_ids UUID[], results TEXT,
exceptions TEXT NULL, further_procedures TEXT NULL, conclusion TEXT,
**conclusion_evidence_refs UUID[]** — 비어 있으면 NEEDS_REVIEW 이후 상태로 전이 불가(하드 블록),
preparer FK, prepared_at, reviewer FK NULL, reviewed_at NULL,
attachments UUID[], version, status(ENUM 10종), created_at

### wp_versions
id, wp_id FK, version, snapshot JSONB, changed_by, change_reason, created_at.
COMPLETED/LOCKED 조서 변경 시 필수 생성.

### review_notes
id, wp_id FK, author FK, note, status(open/resolved), resolved_by NULL, resolution NULL, timestamps

## 5. AI·승인·로그

### ai_tasks
id, engagement_id, task_type, prompt_version, model, input_refs JSONB,
raw_response_masked TEXT, structured_output JSONB, schema_id, schema_valid BOOL,
confidence(low/medium/high), status(stored/rejected/needs_review), processed_at

### approvals — 모든 승인의 단일 원장
id, engagement_id, subject_type(materiality/risk/sample/program/wp/difference/report/engagement),
subject_id UUID, action(approve/reject/rework), decided_by FK, decided_at,
rationale TEXT NOT NULL. 자기승인은 INSERT 전 서비스 계층에서 거부.

### audit_trail — append-only, 해시 체인
id BIGSERIAL, engagement_id NULL(시스템 이벤트), actor FK NULL, action, entity_type, entity_id,
before JSONB(마스킹), after JSONB(마스킹), occurred_at, prev_hash CHAR(64), row_hash CHAR(64).
앱 DB 계정에 UPDATE/DELETE 권한 없음. row_hash = SHA-256(prev_hash ‖ 정규화된 행 내용).

## 6. MVP 2~3 예약 테이블 (착수 시 상세화)

samples, sample_items, confirmations, audit_differences, estimates_reviews,
going_concern_indicators, related_parties, subsequent_events, contingencies,
completion_checklist, report_drafts — 필드 개요는 initial-design.md §5.3~5.4 참조.

## 7. 상태 ENUM (공통)

NOT_STARTED, IN_PROGRESS, WAITING_FOR_CLIENT, NEEDS_REVIEW, REVIEW_COMMENT,
REWORK_REQUIRED, CLEARED, PARTNER_APPROVAL_REQUIRED, COMPLETED, LOCKED

전이 규칙은 workflow 모듈이 단일 소스로 관리하며, 모든 전이는 권한 검사 + 전제조건 검사 +
audit_trail 기록을 통과해야 한다.
