# AI 회계감사 지원 시스템 (ai-audit-assistant)

한국 공인회계사가 사용하는 AI 기반 회계감사 **지원** 프로그램.

AI가 감사의견을 확정하거나 보고서를 발행하는 시스템이 아니다. 회계사가 승인한 감사계획과
중요성 기준에 따라 일반적인 감사절차를 체계적으로 수행하고, 감사증거와 판단 근거를 정리하여
**감사조서와 감사보고서 초안**을 생성한다.

> 참고: 본 프로젝트는 별도 저장소(`ai-audit-assistant`, 비공개)로 분리 예정이다.
> 현재는 설계 단계 산출물이 이 브랜치에 있다.

## 핵심 설계 원칙

1. **환각 금지** — 입력자료에 없는 증거·거래·금액을 만들지 않는다.
2. **인간 통제** — 중요성, 유의적/부정위험, 표본 수, 감사차이 평가, 감사의견은 회계사 승인 게이트를 통과해야 한다.
3. **증거 추적성** — 모든 결론은 원천자료(파일·시트·셀·페이지)에 링크된다. 근거 없는 결론은 저장 불가.
4. **재현성** — 동일 입력 → 동일 출력. seed·계산식·프롬프트 버전·모델 버전 기록.
5. **원본 불변** — 원본자료는 읽기 전용, SHA-256 해시로 무결성 검증.

## 문서

| 문서 | 내용 |
|---|---|
| [docs/initial-design.md](docs/initial-design.md) | 초기 설계서 (아키텍처, 데이터 흐름, MVP 순서, 확정 결정사항) |
| [docs/product-requirements.md](docs/product-requirements.md) | 요구사항 정본 |
| [docs/audit-methodology.md](docs/audit-methodology.md) | 감사 방법론 (워크플로우, 중요성, 표본, 이상탐지 규칙) |
| [docs/data-model.md](docs/data-model.md) | 데이터 모델 |
| [docs/security-model.md](docs/security-model.md) | 보안 모델 (RBAC, 저장소, AI 송신 정책, 감사로그) |
| [docs/human-review-policy.md](docs/human-review-policy.md) | 자동화 가능 절차 / 회계사 승인 필수 판단의 구분 (정본) |
| [docs/report-generation-policy.md](docs/report-generation-policy.md) | 감사보고서 생성 정책 |

## 기술 스택

Backend: Python + FastAPI + SQLAlchemy + PostgreSQL · Frontend: Next.js + TypeScript ·
파일 저장: Google Drive (StorageInterface 추상화, dev는 로컬) · AI: Anthropic API ·
테스트: pytest · 배포: Docker

## 현재 상태

- [x] 초기 설계서 및 발주자 결정사항 확정
- [x] 상세 정책 문서 작성
- [ ] MVP 1: 자료 검증과 위험식별 파이프라인 (구현 순서: docs/initial-design.md §7)
- [ ] MVP 2: 핵심 실증절차
- [ ] MVP 3: 완료와 보고
