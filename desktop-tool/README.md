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

- `xlwings`는 Excel이 설치된 PC에서 권장 (수식·서식·차트·도형 완전 보존).
  없으면 openpyxl로 동작한다.

## 업데이트

한 번 설치한 뒤에는 zip을 다시 받을 필요가 없다.

- GUI 오른쪽 위 **[업데이트]** 버튼, 또는 **`업데이트.bat` 더블클릭**
- GitHub 저장소의 최신 코드를 받아 설치 폴더에 덮어쓴다.
  결정값·로그·진행현황 등 사용자 데이터는 유지되고, 이전 코드는 `_backup/`에 보관된다.
- 프로그램 시작 시 새 버전이 있으면 로그 창에 안내가 표시된다.
- exe로 쓰는 경우: 소스 폴더에서 `업데이트.bat` 실행 후 `build_exe.bat`로 exe만 다시
  만들면 된다 (실행.bat 방식이면 업데이트 즉시 적용).
- 저장소를 비공개로 전환한 경우: 설치 폴더에 `github_token.txt`를 만들고 GitHub
  토큰(fine-grained PAT, Contents read 권한)을 넣으면 계속 동작한다.

## 실행 방법 3가지 (쉬운 순)

### ① 실행.bat (권장 — 빌드 불필요)

`desktop-tool` 폴더의 **`실행.bat` 더블클릭**. Python으로 GUI가 바로 뜬다.
Excel이 설치된 PC면 xlwings 엔진(서식·차트·도형 완전 보존)을 자동 사용한다.

### ② exe로 만들기

`build_exe.bat` 더블클릭 → `dist\AuditTool.exe` 생성 (수 분 소요).
- exe에는 빌드 안정성을 위해 xlwings가 **제외**되어 있어 openpyxl 엔진으로 동작한다
  (수식·값 처리는 동일. 차트·도형이 많은 양식은 산출물 확인 필요 — 원본은 항상 무수정).
- **exe가 실행되지 않을 때**:
  1. Windows SmartScreen 파란 창이 뜨면: "추가 정보" → "실행" 클릭.
  2. 백신이 exe를 격리했는지 확인 (PyInstaller 단일 exe는 오탐이 흔함) → 예외 등록.
  3. exe 옆에 `audit_tool_error.log` 파일이 생겼는지 확인 — 오류 내용이 기록된다.
  4. 그래도 원인을 모르면 `build_exe_debug.bat`로 콘솔 버전(`AuditTool_debug.exe`)을
     만들어 cmd에서 실행하면 오류 메시지가 화면에 보인다. 그 내용을 알려주면 된다.

### ③ 명령행

**exe/GUI 사용법**: 실행 → [찾기]로 당기 외감 폴더 선택 → **[▶ 전체 실행]** 버튼.
- 처음 실행하는 폴더면 결정값 입력 창이 뜬다 → 기수·연도·결산일·전기수치_확정여부를
  확인·저장하고 [▶ 전체 실행]을 다시 누른다.
- 이후: Dry-run 내용 확인창 → [예] → 이월 실행 → 주입 내용 확인창 → [예] → 완료.
- 모든 단계는 원본을 수정하지 않고, 실행 내역은 `_audit_tool/runlog.jsonl`에 남는다.

CLI:
```bat
python -m audit_tool all      "D:\...\2026년 기말감사"   :: 원클릭 (대화식 확인)
python -m audit_tool all      "D:\...\2026년 기말감사" --yes
python -m audit_tool identify "D:\...\2026년 기말감사"
python -m audit_tool init     "D:\...\2026년 기말감사"   :: 결정값.json 생성
python -m audit_tool roll     "D:\...\2026년 기말감사"   :: Dry-run
python -m audit_tool roll     "D:\...\2026년 기말감사" --execute
python -m audit_tool inject   "D:\...\2026년 기말감사" --execute
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
