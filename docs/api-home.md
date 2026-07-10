# Home / Today Mission API

> 기준일: 2026-07-06
> 인증: 모든 프론트 사용 엔드포인트에 `Authorization: Bearer <access_token>` 헤더 필요

## 목적

홈 화면은 사용자 정보, 캐릭터 성장 상태, 오늘의 미션, 알림 카운트를 한 번에 렌더링한다. `HomeService`는 각 도메인 서비스를 조합하며, 홈 전용 DB 테이블은 만들지 않는다.

현재 구현 범위:

- `GET /api/v1/home`: 홈 화면 전체 데이터
- `GET /api/v1/home/summary`: 홈 상단/위젯용 축약 데이터
- `GET /api/v1/missions/today`: 사용자 timezone 기준 오늘 미션
- `POST /api/v1/missions/{mission_id}/complete`: 미션 self-report 완료
- `DELETE /api/v1/missions/{mission_id}/complete`: 미션 완료(인증) 취소
- Notification inbox 기반 `unread_notification_count`

아직 후속 Phase 범위:

- 미션 인증(웨어러블 자동 인증)
- push / 리마인드 알림 worker
- 미션 완료→EXP→LEVEL_UP (Phase 5 확장, Phase 7과 별도)

> 미션 조회 API(날짜별/주간/월간/총계)는 구현됨 — 아래 "미션 조회 API" 참조.

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
| `unread_notification_count` | `int` | Notification inbox의 미읽음 알림 수 |

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
      "total": 2,
      "completed": 0,
      "items": [
        {
          "mission_id": 1,
          "template_code": "DEFAULT_SELF_CHECK",
          "title": "오늘의 건강 체크",
          "status": "ASSIGNED",
          "assigned_date": "2026-07-02",
          "xp_reward": 10,
          "completed_at": null,
          "source_record_id": 3,
          "rationale": "",
          "mission_type": "",
          "difficulty": 1,
          "execution": { "when": "", "duration_min": null, "time": "" },
          "grounded_on": [],
          "source": "generated",
          "description": "오늘 하루 건강 상태를 스스로 확인해 보세요.",
          "category": "HEALTH",
          "verification_mode": "SELF_CHECK"
        },
        {
          "mission_id": 2,
          "template_code": "walk_after_meal",
          "title": "식후 15분 걷기",
          "status": "ASSIGNED",
          "assigned_date": "2026-07-02",
          "xp_reward": 20,
          "completed_at": null,
          "source_record_id": null,
          "rationale": "고혈압 관리를 위해 식후 가벼운 운동이 도움이 됩니다.",
          "mission_type": "exercise",
          "difficulty": 2,
          "execution": { "when": "식후", "duration_min": 15, "time": "13:00" },
          "grounded_on": ["고혈압->심혈관질환"],
          "source": "generated",
          "description": null,
          "category": null,
          "verification_mode": null
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
| `unread_notification_count` | `int` | Notification inbox의 미읽음 알림 수 |

---

## GET /api/v1/missions/today

사용자 `timezone` 기준 오늘 배정된 미션을 반환한다. 미션은 **두 출처**에서 온다 — 응답 shape은 같지만 출처별로 채워지는 필드가 다르다.

1. **레거시 템플릿 기반**(`#24` 기본미션, `assign_default_mission` 등 legacy Analysis 경로가 생성): DB `mission_templates` 행과 연결됨(`template_id` 존재).
2. **엔진 생성**(스케줄러가 매일 PKG 기반으로 생성, `app.domains.mission.scheduler`): DB 템플릿 행이 없음(`template_id = NULL`), 내용은 LLM/규칙 기반으로 그날그날 만들어짐. **미션 생성 자체는 REST API가 아니라 백그라운드 스케줄러(매시 틱)로 동작** — 이 엔드포인트는 조회만 한다.

### Response data

| 필드 | 타입 | 설명 |
|------|------|------|
| `date` | `date` | 사용자 timezone 기준 조회 날짜 |
| `total` | `int` | 오늘 미션 총 개수 |
| `completed` | `int` | `status == "COMPLETED"` 미션 수 |
| `items[].mission_id` | `int` | 사용자 미션 ID |
| `items[].template_code` | `string\|null` | 미션 템플릿 코드(엔진 생성분은 provenance 문자열, 레거시는 `mission_templates.code`) |
| `items[].title` | `string` | 미션 제목 |
| `items[].status` | `"ASSIGNED"\|"COMPLETED"` | 현재 상태 |
| `items[].assigned_date` | `date` | 배정일 |
| `items[].xp_reward` | `int` | 미션 보상 EXP. 엔진 생성분은 **난이도 기반**(difficulty×10 = 10/20/30). 레거시는 템플릿 `default_xp`. (완료→캐릭터 EXP 지급 루프는 Phase 5 미연결) |
| `items[].completed_at` | `string\|null` | 완료 처리 시각(ISO datetime), 미완료면 `null` |
| `items[].source_record_id` | `int\|null` | 미션 생성 원천 검진 기록. 엔진 생성분은 현재 `null`(미설정) |
| `items[].rationale` | `string` | **엔진 생성분만**: 이 미션을 추천한 이유. 레거시는 `""` |
| `items[].mission_type` | `string` | **엔진 생성분만**: `diet`\|`exercise`\|`hydration`\|`sleep`\|`stress`\|`checkup_followup`\|`habit`. 레거시는 `""` |
| `items[].difficulty` | `int` | **엔진 생성분만**: 난이도(1부터). 레거시는 `1` |
| `items[].execution.when` | `string` | **엔진 생성분만**: 수행 시점(예: "식후"). 레거시는 `""` |
| `items[].execution.duration_min` | `int\|null` | **엔진 생성분만**: 소요 시간(분) |
| `items[].execution.time` | `string` | **엔진 생성분만**: 예상 수행 시각 `"HH:MM"`(프론트 알람용). 규칙 기본값을 LLM이 미션 맥락에 맞게 조정, 형식 오류 시 규칙값 폴백. 레거시는 `""` |
| `items[].grounded_on` | `string[]` | **엔진 생성분만**: 근거로 인용한 PKG 관계. 레거시는 `[]` |
| `items[].source` | `string` | **엔진 생성분만**: `generated`\|`fallback`(LLM 실패 시 결정적 템플릿 사용) |
| `items[].description` | `string\|null` | **레거시만**: `mission_templates.description`. 엔진 생성분은 `null` |
| `items[].category` | `string\|null` | **레거시만**: `mission_templates.category`. 엔진 생성분은 `null`(대신 `mission_type` 사용) |
| `items[].verification_mode` | `string\|null` | **레거시만**: `mission_templates.verification_mode`. 엔진 생성분은 `null`(완료 방식 매핑은 미정) |

> ⚠️ 이전 계약(레거시 전용)에서는 `template_code`/`category`/`verification_mode`가 항상 non-null 문자열이었다. 엔진 생성 미션이 섞이면서 이 셋은 **nullable로 변경**됐다 — 프론트에서 non-null을 가정한 코드가 있으면 확인이 필요하다.

---

## POST /api/v1/missions/{mission_id}/complete

인증된 사용자가 본인 미션을 self-report로 완료 처리한다.

- 이미 `COMPLETED`인 미션을 다시 호출하면 **멱등**하게 처리한다(에러 없이 그대로 완료 유지, 재요청/더블탭 안전).
- 본인 미션이 아니거나 존재하지 않으면 `404`.
- 완료 상태는 `completed_at`에 기록되고, 최근 14일 완료율(`success_rate`)로 계산돼 다음 날 미션 생성 시 난이도 조정에 반영된다.
- 미션 완료 시 캐릭터 EXP 지급·자동 알림은 아직 연결되지 않았다(후속 Phase). 미션 리마인드 알림은 별도로 `POST /api/v1/missions/notifications/send`로 발송한다([api-notification.md](./api-notification.md)).

### Response

```json
{
  "success": true,
  "message": "미션을 완료했습니다.",
  "data": null,
  "error_code": null
}
```

---

## DELETE /api/v1/missions/{mission_id}/complete

본인 미션의 완료(인증) 처리를 취소한다(오탭 등으로 잘못 완료했을 때 되돌리는 용도).

- 이미 `ASSIGNED`(미완료) 상태에서 호출하면 **멱등**하게 처리한다(에러 없이 그대로 유지).
- 본인 미션이 아니거나 존재하지 않으면 `404`.
- 취소 시 `completed_at`을 `null`로 되돌린다. 날짜 제한은 없다(`complete`와 대칭).
- `complete`가 지급한 `xp_reward`만큼 캐릭터 EXP를 회수한다(0 미만으로는 내려가지 않음).

### Response

```json
{
  "success": true,
  "message": "미션 완료를 취소했습니다.",
  "data": null,
  "error_code": null
}
```

---

## 미션 조회 API (날짜별/주간/월간/총계)

순수 조회 엔드포인트. 모두 Bearer 인증, 본인 데이터만 반환한다. Body 없음(GET).

### GET /api/v1/missions/date/{date}

특정 날짜 배정 미션 목록·완료 집계. **응답 shape은 `/today`와 동일**(`date`, `total`, `completed`, `items[]`). 월간 캘린더에서 날짜 탭 → 상세에 사용.

| 위치 | 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| path | `date` | string `YYYY-MM-DD` | 필수 | 조회할 날짜 |

### GET /api/v1/missions/statistics/weekly

지정 날짜가 속한 주(월~일)의 일별·합계 집계. `days`는 항상 7개(미션 없는 날은 0).

| 위치 | 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| query | `date` | string `YYYY-MM-DD` | 선택 | 기준일. 생략 시 유저 로컬 오늘 |

```json
{ "week_start": "2026-07-06", "week_end": "2026-07-12", "total": 5, "completed": 3,
  "days": [ { "date": "2026-07-06", "total": 2, "completed": 1 }, "…7일" ] }
```

### GET /api/v1/missions/calendar

해당 월에서 **미션이 있는 날만** 일별 집계(캘린더 점 표시용).

| 위치 | 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| query | `year` | int (2000~2100) | 필수 | 조회 연도 |
| query | `month` | int (1~12) | 필수 | 조회 월 |

```json
{ "year": 2026, "month": 7, "days": [ { "date": "2026-07-06", "total": 3, "completed": 2 } ] }
```

### GET /api/v1/missions/statistics/summary

전체 기간 총 배정·완료 수 + 완성도. 요청 파라미터 없음.

| 위치 | 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| — | (없음) | — | — | 인증 사용자 전체 기간 집계 |

```json
{ "total_assigned": 120, "total_completed": 88, "completion_rate": 0.733 }
```

`completion_rate`는 0.0~1.0(미션 없으면 0.0).

---

## 구현 메모

- 캐릭터 프로필이 없는 기존 사용자는 `/home` 또는 `/characters/me` 호출 시 기본 프로필과 `frog` 보유 row가 lazy 생성된다.
- 온보딩 완료 시에도 캐릭터 기본 프로필을 미리 생성한다.
- Home은 `UserRepository`, `CharacterService`, `MissionService`, `NotificationService`를 조합한다.
- 알림 수는 Notification inbox의 미읽음 row를 조회한다. 설정 API는 `/my/notification-settings`(정본), 알림함은 `/notifications` — [api-notification.md](./api-notification.md).
- `POST /missions/{id}/complete`는 상태 전이만 하며 EXP·LEVEL_UP 알림과 연결되지 않는다(Phase 5 확장).
- **미션 생성은 API가 아니라 백그라운드 스케줄러**(매시 틱)가 PKG 기반으로 담당한다. 새 검진이 저장되면 당일 미완료 미션을 무효화하고 재생성한다(완료분은 보존). 프론트는 생성을 트리거할 필요가 없고 `/today`로 조회만 하면 된다.
