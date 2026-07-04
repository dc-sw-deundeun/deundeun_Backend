# Home / Today Mission API

> 기준일: 2026-07-04
> 인증: 모든 프론트 사용 엔드포인트에 `Authorization: Bearer <access_token>` 헤더 필요

## 목적

홈 화면은 사용자 정보, 캐릭터 성장 상태, 오늘의 미션, 알림 카운트를 한 번에 렌더링한다. `HomeService`는 각 도메인 서비스를 조합하며, 홈 전용 DB 테이블은 만들지 않는다.

현재 Phase 6 범위:

- `GET /api/v1/home`: 홈 화면 전체 데이터
- `GET /api/v1/home/summary`: 홈 상단/위젯용 축약 데이터
- `GET /api/v1/missions/today`: 사용자 timezone 기준 오늘 미션

아직 후속 Phase 범위:

- 미션 완료/인증/캘린더/주간 통계
- 알림 저장/읽음 처리
- 미션 완료에 따른 실제 EXP 지급 루프

---

## GET /api/v1/home

홈 화면에 필요한 데이터를 한 번에 반환한다. 캐릭터 블록은 `/api/v1/characters/me`, 오늘 미션 블록은 `/api/v1/missions/today`와 같은 핵심 값을 사용한다.

### Response data

| 필드 | 타입 | 설명 |
|------|------|------|
| `user.id` | `int` | 사용자 ID |
| `user.nickname` | `string` | 닉네임 |
| `user.onboarding_step` | `string` | 현재 온보딩 단계 |
| `user.onboarding_completed` | `boolean` | 온보딩 완료 여부 |
| `character` | `object` | 캐릭터 성장 상태. `/characters/me` 응답과 같은 shape |
| `today_missions` | `object` | 오늘 미션 집계. `/missions/today` 응답과 같은 shape |
| `unread_notification_count` | `int` | Phase 7 전까지 항상 `0` |

예시:

```json
{
  "success": true,
  "message": "요청이 성공했습니다.",
  "data": {
    "user": {
      "id": 1,
      "nickname": "든든이",
      "onboarding_step": "COMPLETED",
      "onboarding_completed": true
    },
    "character": {
      "user_id": 1,
      "level": 1,
      "total_exp": 0,
      "current_level_exp": 0,
      "exp_to_next_level": 100,
      "progress_ratio": 0.0,
      "owned_animals": [
        {
          "animal_code": "frog",
          "name": "개구리",
          "unlocked_level": 1,
          "unlocked_at": "2026-07-02T12:00:00Z"
        }
      ],
      "updated_at": "2026-07-02T12:00:00Z"
    },
    "today_missions": {
      "date": "2026-07-02",
      "total": 1,
      "completed": 0,
      "items": [
        {
          "mission_id": 1,
          "template_code": "DEFAULT_SELF_CHECK",
          "title": "오늘의 건강 체크",
          "description": "오늘 하루 건강 상태를 스스로 확인해 보세요.",
          "category": "HEALTH",
          "verification_mode": "SELF_CHECK",
          "xp_reward": 10,
          "status": "ASSIGNED",
          "assigned_date": "2026-07-02",
          "source_record_id": 3
        }
      ]
    },
    "unread_notification_count": 0
  },
  "error_code": null
}
```

---

## GET /api/v1/home/summary

홈 상단 또는 작은 위젯에 필요한 최소 수치만 반환한다.

### Response data

| 필드 | 타입 | 설명 |
|------|------|------|
| `nickname` | `string` | 닉네임 |
| `level` | `int` | 캐릭터 레벨 |
| `total_exp` | `int` | 누적 EXP |
| `progress_ratio` | `float` | 현재 레벨 진행도 |
| `owned_animal_count` | `int` | 보유 동물 수 |
| `today_mission_total` | `int` | 오늘 미션 총 개수 |
| `today_mission_completed` | `int` | 오늘 완료된 미션 수 |
| `unread_notification_count` | `int` | Phase 7 전까지 항상 `0` |

---

## GET /api/v1/missions/today

사용자 `timezone` 기준 오늘 배정된 미션을 반환한다. 분석 callback 또는 HealthMetric 흐름에서 생성된 `UserMission` row를 읽는다.

### Response data

| 필드 | 타입 | 설명 |
|------|------|------|
| `date` | `date` | 사용자 timezone 기준 조회 날짜 |
| `total` | `int` | 오늘 미션 총 개수 |
| `completed` | `int` | `status == "COMPLETED"` 미션 수 |
| `items[].mission_id` | `int` | 사용자 미션 ID |
| `items[].template_code` | `string` | 미션 템플릿 코드 |
| `items[].title` | `string` | 미션 제목 |
| `items[].description` | `string\|null` | 미션 설명 |
| `items[].category` | `string` | 카테고리 |
| `items[].verification_mode` | `string` | 검증 방식 |
| `items[].xp_reward` | `int` | 미션 보상 EXP 값 |
| `items[].status` | `string` | 현재 상태 |
| `items[].assigned_date` | `date` | 배정일 |
| `items[].source_record_id` | `int\|null` | 미션 생성 원천 검진 기록 |

---

## 구현 메모

- 캐릭터 프로필이 없는 기존 사용자는 `/home` 또는 `/characters/me` 호출 시 기본 프로필과 `frog` 보유 row가 lazy 생성된다.
- 온보딩 완료 시에도 캐릭터 기본 프로필을 미리 생성한다.
- Home은 `UserRepository`, `CharacterService`, `MissionService`를 조합한다.
- 알림 수는 Notification Phase 전까지 저장소 조회 없이 `0`으로 고정한다.
