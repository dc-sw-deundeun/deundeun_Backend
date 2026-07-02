# 마이페이지 API

> 기준일: 2026-07-03
> Base URL: `/api/v1/my`
> 인증: 모든 엔드포인트에 `Authorization: Bearer <access_token>` 헤더 필요

---

## 구현 현황

| 기능 | 상태 | 엔드포인트 |
|------|------|-----------|
| 연동 앱 목록 조회 | ✅ 구현 완료 | `GET /my/connected-apps` |
| 연동 앱 상태 토글 | ✅ 구현 완료 | `PATCH /my/connected-apps/{provider}` |
| 알림 설정 조회 | ✅ 구현 완료 | `GET /my/notification-settings` |
| 알림 설정 업데이트 | ✅ 구현 완료 | `PATCH /my/notification-settings` |
| 비밀번호 변경 | ✅ 기존 Auth API 사용 | `POST /auth/password/reset/request` + `confirm` |
| 프로필 조회 | 🚧 stub (501) | `GET /my/profile` |
| 앱 잠금 설정 | 🚧 stub (501) | `GET/PATCH /my/app-lock` |
| 문의 접수 | 🚧 stub (501) | `POST /my/support` |
| 계정 삭제 | 🚧 stub (501) | `DELETE /my/account` |

---

## 비밀번호 변경

기존 Auth API를 사용합니다. 별도 My 엔드포인트는 없습니다.

```
1. POST /api/v1/auth/password/reset/request   ← 이메일로 인증 코드 발송
         ↓ (이메일에서 인증 코드 확인)
2. POST /api/v1/auth/password/reset/confirm   ← 인증 코드 + 새 비밀번호로 변경
```

자세한 요청/응답 스펙은 Auth API를 참조하세요.

---

## API 목록

### GET /my/connected-apps

연동 앱 목록과 각 앱의 연동 상태를 반환합니다.

지원 provider:

| provider 값 | 앱 이름 |
|------------|---------|
| `APPLE_HEALTH` | 애플 건강 |
| `SAMSUNG_HEALTH` | 삼성 헬스 |
| `GOOGLE_FIT` | 구글 피트니스 |

**Response**

```json
{
  "apps": [
    { "provider": "APPLE_HEALTH", "status": "DISCONNECTED" },
    { "provider": "SAMSUNG_HEALTH", "status": "CONNECTED" },
    { "provider": "GOOGLE_FIT", "status": "DISCONNECTED" }
  ]
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `apps[].provider` | `string` | 앱 식별자 |
| `apps[].status` | `string` | `CONNECTED` / `DISCONNECTED` |

한 번도 설정하지 않은 앱은 `DISCONNECTED`로 반환됩니다.

---

### PATCH /my/connected-apps/{provider}

연동 앱 상태를 `CONNECTED ↔ DISCONNECTED`로 토글합니다.

**Path Parameter**

| 파라미터 | 값 |
|---------|-----|
| `provider` | `APPLE_HEALTH` / `SAMSUNG_HEALTH` / `GOOGLE_FIT` |

**Request Body**: 없음

**Response**

```json
{ "provider": "SAMSUNG_HEALTH", "status": "CONNECTED" }
```

**에러**

| HTTP | 상황 |
|------|------|
| 400 | 지원하지 않는 provider 값 |

---

### GET /my/notification-settings

현재 사용자의 알림 설정을 반환합니다.

알림 설정이 존재하지 않는 경우 모든 항목을 `true`로 자동 초기화하여 반환합니다.

**Response**

```json
{
  "mission_alarm_enabled": true,
  "record_alarm_enabled": true,
  "email_alarm_enabled": false,
  "push_alarm_enabled": true
}
```

| 필드 | 화면 이름 | 기본값 |
|------|----------|--------|
| `mission_alarm_enabled` | 미션 리마인드 | `true` |
| `record_alarm_enabled` | 기록 리마인드 | `true` |
| `email_alarm_enabled` | 식단 기록 알림 | `true` |
| `push_alarm_enabled` | 주간 리포트 | `true` |

---

### PATCH /my/notification-settings

알림 설정을 부분 업데이트합니다. 변경할 항목만 포함해 전송하세요.

**Request**

모든 필드 optional. 포함하지 않은 필드는 변경되지 않습니다.

```json
{
  "mission_alarm_enabled": false,
  "push_alarm_enabled": false
}
```

**Response**: `GET /my/notification-settings`와 동일한 전체 설정 반환

---

## curl 예시

```bash
TOKEN="<access_token>"
BASE="http://localhost:8000/api/v1"

# 연동 앱 목록 조회
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/my/connected-apps" | jq

# 삼성 헬스 연동 토글
curl -s -X PATCH -H "Authorization: Bearer $TOKEN" "$BASE/my/connected-apps/SAMSUNG_HEALTH" | jq

# 알림 설정 조회
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/my/notification-settings" | jq

# 미션 리마인드 끄기
curl -s -X PATCH \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mission_alarm_enabled": false}' \
  "$BASE/my/notification-settings" | jq
```
