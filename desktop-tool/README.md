# 외감 실무 자동화 도구 (audit_tool)

한국 공인회계사 외부감사 실무용 로컬 데스크톱 도구.

- **① 초기세팅(이월)**: 당기 외감 폴더를 지정하면 전기 DSD·정산표·일반조서·계정별조서를
  자동 식별하고, 당기 파일(조서·정산표·DSD)을 생성한다. 원본은 절대 수정하지 않는다.
- **② 진행현황**: `C 회계감사` 루트를 스캔해 외감 대상(★) 업체 목록을 만들고,
  8단계(조회서 안내→…→인쇄 및 청구) 진행현황을 관리·대시보드로 출력한다.

## 설치 (Windows)

```bat
pip install openpyxl xlwings
```

- `xlwings`는 Excel이 설치된 PC에서 권장 (수식·서식·차트 완전 보존, 열 삽입 지원).
  없으면 openpyxl로 동작하되 정산표 열 삽입 단계는 수동 처리로 안내된다.

## 실행

GUI:
```bat
python -m audit_tool.gui
```

CLI:
```bat
python -m audit_tool identify "D:\...\2026년 기말감사"
python -m audit_tool init     "D:\...\2026년 기말감사"   :: 결정값.json 생성
python -m audit_tool roll     "D:\...\2026년 기말감사"   :: Dry-run
python -m audit_tool roll     "D:\...\2026년 기말감사" --execute
python -m audit_tool progress scan "C:\...\C 회계감사"
python -m audit_tool progress set  "C:\...\C 회계감사" C-35 2026 3 "전산자료 수령"
python -m audit_tool progress dash "C:\...\C 회계감사" 2026
```

## 사용 순서 (초기세팅)

1. 당기 외감 폴더에 전기 파일(DSD·정산표·일반조서·계정별조서)과 당기 Raw를 넣는다.
2. `identify` → 자동 식별 결과 확인.
3. `init` → `_audit_tool/결정값.json` 생성. **사전 결정값(기수·연도·결산일·전기수치
   확정여부)을 직접 확인·입력**한다. 프로그램은 제안만 하고 결정하지 않는다.
4. `roll` (Dry-run) → 생성될 파일·작업 목록·열 탐지 결과를 확인.
5. `roll --execute` → 당기 파일 생성. 실행 내역은 `_audit_tool/runlog.jsonl`에
   원본 해시와 함께 기록된다.

## 원칙

- 원본 미수정: 산출물은 항상 새 파일. 동명 파일은 `_v2`로 생성(덮어쓰지 않음).
- 감사판단(감사보고서일·감사의견·강조사항·계속기업 결론)은 프로그램이 넣지 않는다.
  DSD 이월 시 해당 자리는 `[입력 필요]`로 표시되며, 사후 결정값 미입력 상태에서는
  보고서 확정 단계를 진행하지 않는다.
- 추측 금지: 파일·열 판별이 모호하면 실행하지 않고 사용자 확인을 요구한다.
- DART 편집기 업데이트 주의: 테스트된 편집기 버전과 다르면 경고를 출력한다.
  생성된 .dsd는 편집기에서 열어 확인 후 사용한다.

## 구조

```
audit_tool/
├── identify.py   # D1: 폴더 스캔·파일 자동 식별 (시트 구성·DSD XML 내용 기반)
├── decisions.py  # 결정값(사전/사후) 관리 + 게이트
├── engine.py     # 작업 계획(Plan) + 실행 엔진 (xlwings 우선, openpyxl 폴백)
├── roll_dsd.py   # DSD 이월 (ACODE/ADELIM 기반, docs/dsd-format.md 참조)
├── roll_xlsx.py  # 일반조서·계정별조서·정산표 이월 계획
├── runner.py     # 오케스트레이션 + 실행 로그(runlog.jsonl)
├── progress.py   # 다업체 8단계 진행현황 + 대시보드 HTML
├── cli.py        # 명령행 인터페이스
└── gui.py        # tkinter GUI (탭: 초기세팅/진행현황)
```
