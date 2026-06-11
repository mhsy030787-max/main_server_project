# Python Backend

Python 표준 라이브러리만 사용하는 백엔드입니다.

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

```bash
HOST=0.0.0.0 python3 backend/app.py
```

문서, 권한, 사용자, 등급, 로그, 알림, 파일 전송 화면은 현재 프론트엔드 로컬 상태로 동작합니다.
