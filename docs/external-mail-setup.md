# DataVault 외부 메일 설정

## 구성

- 사내 주소(`@datavault.local`)는 MySQL에 바로 저장됩니다.
- 외부 주소 발송은 Resend의 HTTPS API를 사용합니다.
- 외부 수신 메일은 Resend 웹훅을 거쳐 MySQL에 저장됩니다.
- Render 서비스는 `Free` 플랜을 그대로 사용합니다. Render Free가 차단하는 SMTP
  포트 대신 허용되는 HTTPS 요청을 사용하므로 별도 유료 Render 플랜이 필요하지 않습니다.

Resend 무료 플랜은 월 3,000통, 하루 100통 한도입니다. 한도를 넘으면 Resend 요금제 변경이
필요하지만 Render 플랜과는 별개입니다.

## 1. Resend 발신 도메인 연결

1. Resend에서 무료 계정을 만듭니다.
2. Domains에서 소유한 실제 도메인을 추가합니다.
3. Resend가 안내하는 SPF와 DKIM DNS 레코드를 도메인 DNS에 등록합니다.
4. 도메인 상태가 `Verified`인지 확인합니다.
5. API Keys에서 발송 권한이 있는 키를 만듭니다.

Resend 테스트 도메인 `onboarding@resend.dev`는 계정 소유자의 주소로만 시험 발송할 수
있습니다. Gmail을 포함한 모든 정상 이메일 주소로 보내려면 본인 도메인을 검증해야 합니다.

현재 무료 설정은 `onboarding@resend.dev`를 사용하므로 Resend 계정 소유자 이메일로 보내는
시험 발송만 가능합니다. 유료 기능은 사용하지 않았으며, 소유한 도메인이 생기기 전까지 외부
수신과 임의 주소 발송은 비활성 상태로 유지합니다.

## 2. Render 환경변수

Render의 `main-server-project` 서비스에서 Environment에 다음 값을 설정합니다.

| 이름 | 값 또는 설명 |
| --- | --- |
| `MAIL_PROVIDER` | `resend` |
| `RESEND_API_KEY` | Resend에서 만든 API 키 |
| `RESEND_FROM_DOMAIN` | 검증한 발신 도메인(예: `example.com`) |
| `RESEND_FROM_ADDRESS` | 선택 사항. 고정 발신 주소를 쓸 때만 입력 |
| `MAIL_PUBLIC_DOMAIN` | 외부 수신에 사용할 도메인 |
| `RESEND_WEBHOOK_SECRET` | Resend 웹훅의 Signing secret (`whsec_...`) |
| `MAIL_ALLOW_CLASSIFIED_EXTERNAL` | 기본값 `false` |

사용자별 발신 주소를 사용하려면 `RESEND_FROM_ADDRESS`를 비워 둡니다. 그러면
`admin@example.com`처럼 로그인 사용자 ID를 발신 주소로 사용합니다. 고정 주소만 쓰려면
`RESEND_FROM_ADDRESS=noreply@example.com`을 설정합니다.

## 3. 외부 수신 설정

1. Resend Domains에서 Receiving을 활성화하고 안내되는 MX 레코드를 DNS에 등록합니다.
2. Resend Webhooks에서 다음 엔드포인트를 추가합니다.

```text
https://main-server-project.onrender.com/api/mail/inbound
```

3. 최소 `email.received` 이벤트를 선택합니다.
4. 발송 상태도 표시하려면 `email.sent`, `email.delivered`, `email.delivery_delayed`,
   `email.bounced`, `email.complained`, `email.failed`도 선택합니다.
5. 웹훅 Signing secret을 Render의 `RESEND_WEBHOOK_SECRET`에 입력합니다.

DataVault는 웹훅의 Svix 서명을 검증한 뒤 Resend API에서 본문과 첨부 파일을 가져옵니다.
서명이 다르거나 5분 이상 지난 요청은 거부합니다.

## 4. 배포와 확인

1. Render에서 환경변수를 저장하고 서비스를 재배포합니다.
2. DataVault에서 Gmail 등 외부 주소로 테스트 메일을 보냅니다.
3. Resend의 Emails 화면에서 `Delivered` 상태인지 확인합니다.
4. 수신 주소 `사용자ID@MAIL_PUBLIC_DOMAIN`으로 답장을 보내 받은 메일함을 확인합니다.

`datavault.local`은 인터넷 DNS 도메인이 아니므로 외부 메일 송수신에 사용할 수 없습니다.
외부 송수신에는 반드시 소유하고 DNS를 수정할 수 있는 실제 도메인이 필요합니다.
