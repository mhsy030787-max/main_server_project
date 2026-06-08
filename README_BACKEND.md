# Python Backend

Python 표준 라이브러리만 사용하는 임시 백엔드입니다.

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
- `POST /api/register`
- `POST /api/logout`
- `GET /api/me`

문서, 권한, 사용자, 등급, 로그, 알림, 파일 전송 화면은 현재 프론트엔드 로컬 상태로 동작합니다.
