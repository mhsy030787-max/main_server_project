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

Render에서 회원가입 정보를 MySQL에 저장하려면 Render 대시보드의 Environment에 외부 MySQL 접속 정보를 넣어야 합니다. Render 서버는 내 Mac의 `127.0.0.1` MySQL에 접근할 수 없으므로, Aiven, Railway, AWS RDS, Oracle Cloud, 개인 VPS MySQL처럼 외부에서 접속 가능한 MySQL 주소가 필요합니다.

환경변수는 `DATABASE_URL` 하나로 넣거나, MySQL 항목을 나누어 넣을 수 있습니다.

```text
DATABASE_URL=mysql://사용자:비밀번호@외부_MySQL_주소:3306/main_server_project
```

또는:

```text
MYSQL_HOST=외부_MySQL_주소
MYSQL_PORT=3306
MYSQL_DATABASE=main_server_project
MYSQL_USER=DB_사용자
MYSQL_PASSWORD=DB_비밀번호
MYSQL_SSL_MODE=REQUIRED
```

`MYSQL_SSL_MODE=REQUIRED`는 Aiven처럼 SSL 접속을 요구하는 MySQL 서비스에서 사용합니다.

배포 후 아래 주소에서 저장소 연결 상태를 확인합니다.

```text
https://main-server-project.onrender.com/api/health
```

정상 연결이면 다음처럼 나와야 합니다.

```json
{"ok": true, "storage": "mysql", "mysqlConfigured": true}
```

`storage`가 `memory`라면 Render에 MySQL 환경변수가 없거나, 접속 정보가 틀린 상태입니다.

문서, 권한, 사용자, 등급, 로그, 알림, 파일 전송 화면은 현재 프론트엔드 로컬 상태로 동작합니다.
