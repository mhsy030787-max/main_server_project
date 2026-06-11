# Python Backend

Python 기반 백엔드입니다. 회원가입 사용자는 MySQL 설정이 있으면 MySQL `users` 테이블에 저장하고, 설정이 없으면 로컬 개발용 메모리 저장소를 사용합니다.

## 실행

```bash
python3 backend/app.py
```

브라우저에서 접속:

```text
http://127.0.0.1:8000
```

## 테스트 계정

```text
admin / 1234
leader / 1234
staff / 1234
```

서버 시작 시 MySQL `users` 테이블이 비어 있으면 위 기본 계정을 자동으로 생성합니다.

## MySQL 사용자 테이블

`schema.sql`의 구조를 사용합니다. 서버가 시작될 때 테이블이 없으면 자동으로 생성합니다.

필요한 환경변수:

```bash
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=main_server_project
MYSQL_USER=root
MYSQL_PASSWORD=비밀번호
```

또는 다음처럼 `DATABASE_URL` 하나로 설정할 수 있습니다.

```bash
DATABASE_URL=mysql://사용자:비밀번호@호스트:3306/데이터베이스명
```

로컬 실행 전 의존성 설치:

```bash
pip install -r requirements.txt
```

## 인증 API

- `POST /api/login`
- `POST /api/refresh`
- `POST /api/register`
- `POST /api/logout`
- `GET /api/me`
- `GET /api/sessions`
- `POST /api/sessions/revoke`

## 인증 방식

- 로그인 성공 시 Access JWT를 응답 본문으로 제공합니다.
- Refresh Token은 HttpOnly 쿠키로 저장합니다.
- Access JWT가 만료되면 `POST /api/refresh`로 새 토큰을 발급합니다.
- 서버는 Refresh Token 기반 세션을 메모리에서 관리합니다.

## Render 배포

Render에서는 `render.yaml`을 사용하거나 다음 Start Command를 설정합니다.

Build Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
HOST=0.0.0.0 python3 backend/app.py
```

문서, 권한, 사용자, 등급, 로그, 알림, 파일 전송 화면은 현재 프론트엔드 로컬 상태로 동작합니다.
