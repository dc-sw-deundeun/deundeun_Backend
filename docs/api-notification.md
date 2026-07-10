# Notification Inbox API

> 기준일: 2026-07-06
> Base URL: `/api/v1/notifications`
> 인증: 모든 엔드포인트에 `Authorization: Bearer <access_token>` 헤더 필요

## 목적

알림함은 시스템 이벤트를 사용자별 inbox row로 저장하고, 프론트가 목록과 읽음 상태를 관리할 수 있게 한다.

알림 **설정** 정본은 My API의 `GET/PATCH /api/v1/my/notification-settings`입니다. `/api/v1/notifications/settings`는 제공하지 않습니다.

`GET /notifications`는 목록 조회만 수행하며 자동으로 읽음 처리하지 않습니다. 알림 탭/상세 진입 등 프론트에서 읽음으로 간주하는 순간에는 반드시 `PATCH /notifications/{notification_id}/read`를 호출한 뒤 목록 상태와 홈 배지를 갱신해야 합니다.

## 구현 현황

| 기능 | 상태 | API |
|------|------|-----|
| 알림 목록 | 구현 완료 | `GET /notifications` |
| 알림 읽음 처리 | 구현 완료 | `PATCH /notifications/{notification_id}/read` |
| 알림 설정 | My에서 구현 | `GET/PATCH /my/notification-settings` |
| 미션 리마인드 발송 | 구현 완료(자동) | 백엔드 스케줄러(매시 정각) |

## GET /notifications

인증된 사용자의 알림함을 최신순으로 조회한다.

### Query

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `limit` | `int` | `20` | 1~100 |
| `offset` | `int` | `0` | 0 이상 |
| `unread_only` | `bool` | `false` | `true`면 미읽음 알림만 반환 |

### Response data

| 필드 | 타입 | 설명 |
|------|------|------|
| `items` | `Notification[]` | 알림 목록 |
| `total` | `int` | 현재 필터 조건의 전체 개수 |
| `unread_count` | `int` | 사용자의 전체 미읽음 개수 |
| `limit` | `int` | 요청 limit |
| `offset` | `int` | 요청 offset |

`Notification`

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | `int` | 알림 ID |
| `type` | `string` | `ANALYSIS_COMPLETED`, `LEVEL_UP` 등 |
| `title` | `string` | 알림 제목 |
| `body` | `string` | 알림 본문 |
| `deep_link` | `string\|null` | 앱 이동 링크 |
| `read_at` | `string\|null` | 읽음 시각. `null`이면 미읽음 |
| `created_at` | `string` | 생성 시각 |

예시:

```json
{
  "success": true,
  "message": "요청이 성공했습니다.",
  "data": {
    "items": [
      {
        "id": 1,
        "type": "ANALYSIS_COMPLETED",
        "title": "건강 분석이 완료됐어요",
        "body": "건강 지표 분석 결과를 확인해 보세요.",
        "deep_link": "deundeun://health-metrics/analyses/12",
        "read_at": null,
        "created_at": "2026-07-06T12:00:00Z"
      }
    ],
    "total": 1,
    "unread_count": 1,
    "limit": 20,
    "offset": 0
  },
  "error_code": null
}
```

## PATCH /notifications/{notification_id}/read

본인 알림을 읽음 처리한다.

- 이미 읽은 알림은 멱등하게 동일한 `read_at`을 반환한다.
- 본인 알림이 아니거나 존재하지 않으면 `404 NOTIFICATION_NOT_FOUND`.
- 목록 조회만으로는 `read_at`이 갱신되지 않는다.

### Response data

`GET /notifications`의 item과 동일한 shape을 반환한다.

## 생성되는 MVP 이벤트

| type | 생성 조건 | deep_link | preference |
|------|-----------|-----------|------------|
| `ANALYSIS_COMPLETED` | `POST /health-metrics/analyses` 저장 성공 | `deundeun://health-metrics/analyses/{analysis_id}` | always-on |
| `LEVEL_UP` | `CharacterService.gain_exp` 결과 `leveled_up=true` | `deundeun://characters/me` | always-on |
| `MISSION_REMINDER` | 백엔드 스케줄러(매시 정각 tick)가 생성 | `deundeun://missions/{mission_id}` | `mission_alarm_enabled` |

`POST /api/v1/missions/{mission_id}/complete`는 완료 즉시 `xp_reward`만큼 캐릭터 EXP를 지급하며, 레벨업 시 `LEVEL_UP` 알림을 생성한다. `DELETE /api/v1/missions/{mission_id}/complete`(완료 취소)는 지급된 XP를 대칭적으로 회수한다.

## 미션 리마인드 알림 (자동, 매시 정각)

프론트가 직접 호출하는 발송 API는 없다. 백엔드 스케줄러(`run_mission_notification_tick`)가 매시 정각에 실행되며:

- 유저 로컬 시각 기준 `execution.time`의 시(`HH`)가 현재 시각과 일치하는 `ASSIGNED` 미션에 대해 `MISSION_REMINDER` 알림을 생성한다(`COMPLETED` 미션은 제외).
- `mission_alarm_enabled=false`인 유저는 스킵한다.
- `(user_id, type, source, source_id)` 유니크 제약(`ON CONFLICT DO NOTHING`)으로 같은 시각에 여러 번 tick이 돌아도 알림은 1건만 생성된다(멱등).
- 유저 1명의 처리 실패가 다른 유저에게 전파되지 않는다(유저별 `try/except`).
