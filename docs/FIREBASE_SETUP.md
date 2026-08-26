# 비공개 상담 게시판 설정 가이드 (Firebase · 무료)

방문자가 `/contact/` (문의하기)로 보낸 내용이 **게시판(Firestore)에도 보관**되고,
손슬기님만 `/admin/` 에서 **로그인 후 열람**합니다. 아래 순서대로 1회만 설정하면 됩니다.

## 1. Firebase 프로젝트 만들기
1. https://console.firebase.google.com 접속 → **프로젝트 추가**
2. 프로젝트 이름 입력(예: `ccrnd-consult`) → 만들기 (Google Analytics는 꺼도 됨)

## 2. Firestore 데이터베이스 만들기
1. 왼쪽 메뉴 **빌드 → Firestore Database → 데이터베이스 만들기**
2. **프로덕션 모드**로 시작 → 위치는 `asia-northeast3(서울)` 권장

## 3. 보안 규칙 넣기 (중요)
1. Firestore Database → **규칙(Rules)** 탭
2. 저장소의 [`firestore.rules`](../firestore.rules) 내용을 **전부 복사해 붙여넣기**
3. 파일 안의 `ADMIN_EMAIL_여기에` 를 **본인(관리자) 이메일**로 바꾸기
4. **게시(Publish)**

## 4. 로그인(Authentication) 설정
1. 왼쪽 메뉴 **빌드 → Authentication → 시작하기**
2. **로그인 방법 → 이메일/비밀번호 → 사용 설정 → 저장**
3. **Users 탭 → 사용자 추가** → 관리자 이메일 + 비밀번호 입력해 계정 생성
   (이 이메일이 3번에서 넣은 `ADMIN_EMAIL`과 같아야 합니다)

## 5. 웹앱 설정값 가져오기
1. 왼쪽 위 **⚙️ 프로젝트 설정 → 일반** 탭
2. 아래 **내 앱**에서 **웹(</>)** 아이콘으로 앱 추가 (별칭 아무거나)
3. 표시되는 `firebaseConfig` 에서 **apiKey / authDomain / projectId / appId** 값 확인

## 6. 사이트에 설정값 넣기
`_config.yml` 의 `firebase:` 항목에 위 값을 채우고, `adminEmail`에 관리자 이메일 입력:

```yaml
firebase:
  apiKey: "AIza...."
  authDomain: "ccrnd-consult.firebaseapp.com"
  projectId: "ccrnd-consult"
  appId: "1:1234...:web:abcd..."
  adminEmail: "본인이메일@example.com"
```

> 이 값들은 **공개돼도 안전**합니다. 실제 보안은 3번의 보안 규칙 + 4번 로그인으로 지켜집니다.
> 값만 알려주시면 제가 대신 넣어 배포해 드립니다.

## 7. 확인
- `www.ccrnd.com/contact/` → 문의 전송 테스트
- `www.ccrnd.com/admin/` → 관리자 이메일/비밀번호로 로그인 → 접수 글 확인·삭제

## 무료 한도
Firebase 무료(Spark) 요금제로 개인 상담 게시판 용도는 **충분**합니다.
(문서 읽기/쓰기 일 수만 건 무료) 카드 등록 없이 사용할 수 있습니다.
