# Character Growth API

> 기준일: 2026-07-02  
> Base URL: `/api/v1/characters`  
> 인증: 모든 프론트 사용 엔드포인트에 `Authorization: Bearer <access_token>` 헤더 필요

---

## 목적

캐릭터 도메인은 사용자의 미션/성장 EXP를 기반으로 동물 캐릭터를 해금하고, 프론트 홈 화면에서 사용자가 보유한 동물들이 점점 늘어나는 경험을 제공한다.

중요한 해석:

- 레벨업은 “대표 동물 자동 변경”이 아니다.
- 레벨업은 “사용자별 동물 보유 컬렉션에 새 동물이 추가됨”이다.
- 홈 화면은 사용자가 실제 보유한 동물 목록을 렌더링한다.
- 별도 카탈로그 API는 아직 잠긴 동물까지 포함해 `locked/unlocked` 상태와 mock unlock value를 내려준다.
- 홈 aggregation 응답의 `character` 블록은 이 문서의 `/me` 응답 shape를 재사용한다. 홈 계약은 [api-home.md](./api-home.md)를 참조한다.

---

## API 목록

| Method | Path | 프론트 사용 | 설명 |
|--------|------|-------------|------|
| `GET` | `/me` | ✓ | 내 캐릭터 성장 상태와 보유 동물 목록 조회 |
| `GET` | `/animals` | ✓ | 전체 동물 카탈로그와 내 잠금/해금 상태 조회 |
| `POST` | `/me/experience` | ✗ | 직접 EXP 추가 placeholder. 프론트 공개 API 아님 |
| `PATCH` | `/me/stage` | ✗ | 직접 stage 변경 placeholder. 프론트 공개 API 아님 |

---

## Mock unlock value

제품 밸런싱 확정 전까지 사용하는 mock 값이다. 실제 수치가 바뀌어도 API shape는 유지하고 정책 값만 교체한다.

| animal_code | 이름 | unlock_level | required_total_exp | 상태 설명 |
|-------------|------|--------------|--------------------|-----------|
| `frog` | 개구리 | 1 | 0 | 기본 지급 |
| `chick` | 병아리 | 3 | 235 | 누적 EXP 235 이상 |
| `penguin` | 펭귄 | 5 | 663 | 누적 EXP 663 이상 |
| `dog` | 강아지 | 7 | 1,443 | 누적 EXP 1,443 이상 |
| `cat` | 고양이 | 10 | 3,968 | 누적 EXP 3,968 이상 |
| `tiger` | 호랑이 | 13 | 10,181 | 누적 EXP 10,181 이상 |
| `panda` | 판다 | 16 | 25,469 | 누적 EXP 25,469 이상 |
| `monkey` | 원숭이 | 20 | 85,268 | 누적 EXP 85,268 이상 |

계산 기준:

```text
level N -> N+1 필요 EXP = floor(100 * 1.35^(N - 1))
required_total_exp = 해당 unlock_level 도달 전까지 필요한 누적 EXP
```

---

## 엔드포인트 상세

### GET /me

내 캐릭터 성장 상태와 사용자가 실제로 보유한 동물 목록을 반환한다. 프로필이 없으면 기본 프로필과 초기 보유 동물(`frog`)을 생성한다.

**Request**

| 항목 | 값 |
|------|-----|
| Header | `Authorization: Bearer <access_token>` |
| Body | 없음 |

예시:

```http
GET /api/v1/characters/me HTTP/1.1
Authorization: Bearer eyJ...
```

**Response**

| 필드 | 타입 | 설명 |
|------|------|------|
| `user_id` | `int` | 사용자 ID |
| `level` | `int` | 현재 레벨 |
| `total_exp` | `int` | 누적 EXP |
| `current_level_exp` | `int` | 현재 레벨 구간에서 쌓은 EXP |
| `exp_to_next_level` | `int` | 다음 레벨까지 필요한 현재 구간 EXP |
| `progress_ratio` | `float` | 현재 레벨 진행도, 0~1 |
| `owned_animals[]` | `object[]` | 사용자가 실제 보유한 동물 목록 |
| `owned_animals[].animal_code` | `string` | 동물 코드 |
| `owned_animals[].name` | `string` | 동물 한글명 |
| `owned_animals[].unlocked_level` | `int` | 해금된 레벨 |
| `owned_animals[].unlocked_at` | `datetime` | 보유 row 생성 시각 |
| `updated_at` | `datetime\|null` | 캐릭터 프로필 수정 시각 |

예시 응답:

```json
{
  "success": true,
  "message": "요청이 성공했습니다.",
  "data": {
    "user_id": 1,
    "level": 5,
    "total_exp": 700,
    "current_level_exp": 37,
    "exp_to_next_level": 332,
    "progress_ratio": 0.1114,
    "owned_animals": [
      {
        "animal_code": "frog",
        "name": "개구리",
        "unlocked_level": 1,
        "unlocked_at": "2026-06-30T12:00:00Z"
      },
      {
        "animal_code": "chick",
        "name": "병아리",
        "unlocked_level": 3,
        "unlocked_at": "2026-06-30T12:10:00Z"
      },
      {
        "animal_code": "penguin",
        "name": "펭귄",
        "unlocked_level": 5,
        "unlocked_at": "2026-06-30T12:20:00Z"
      }
    ],
    "updated_at": "2026-06-30T12:20:00Z"
  },
  "error_code": null
}
```

> `current_animal`은 대표 동물 자동 변경으로 오해될 수 있으므로 홈 API 계약의 중심에서 제외한다.

---

### GET /animals

전체 동물 카탈로그를 반환하고, 현재 사용자의 보유 여부를 `is_unlocked`로 표시한다. 프론트에서 잠긴 동물까지 보여주는 진행도/도감 UI에 사용한다.

> `/me`와 `/animals`는 조회 API지만, 프로필/보유 row가 아직 없거나 누락된 경우 현재 레벨 기준으로 `character_owned_animals`를 보정(materialize)할 수 있다. 이는 홈 화면의 보유 동물 source-of-truth를 DB row로 유지하기 위한 의도된 동작이다.

**Request**

| 항목 | 값 |
|------|-----|
| Header | `Authorization: Bearer <access_token>` |
| Body | 없음 |

예시:

```http
GET /api/v1/characters/animals HTTP/1.1
Authorization: Bearer eyJ...
```

**Response**

| 필드 | 타입 | 설명 |
|------|------|------|
| `animals[]` | `object[]` | 전체 동물 카탈로그 |
| `animals[].animal_code` | `string` | 동물 코드 |
| `animals[].name` | `string` | 동물 한글명 |
| `animals[].unlock_level` | `int` | 해금 레벨 |
| `animals[].required_total_exp` | `int` | 해금까지 필요한 mock 누적 EXP |
| `animals[].is_unlocked` | `bool` | 현재 사용자가 보유/해금했는지 여부 |
| `animals[].unlocked_at` | `datetime\|null` | 보유 중이면 해금 시각, 잠김이면 null |

예시 응답:

```json
{
  "success": true,
  "message": "요청이 성공했습니다.",
  "data": {
    "animals": [
      {
        "animal_code": "frog",
        "name": "개구리",
        "unlock_level": 1,
        "required_total_exp": 0,
        "is_unlocked": true,
        "unlocked_at": "2026-06-30T12:00:00Z"
      },
      {
        "animal_code": "chick",
        "name": "병아리",
        "unlock_level": 3,
        "required_total_exp": 235,
        "is_unlocked": true,
        "unlocked_at": "2026-06-30T12:10:00Z"
      },
      {
        "animal_code": "penguin",
        "name": "펭귄",
        "unlock_level": 5,
        "required_total_exp": 663,
        "is_unlocked": false,
        "unlocked_at": null
      }
    ]
  },
  "error_code": null
}
```

---

## DB 설계

### character_profiles

사용자별 성장 상태를 저장한다.

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | integer | PK | 캐릭터 프로필 ID |
| `user_id` | integer | FK `users.id`, unique, index | 사용자 ID |
| `level` | integer | not null, default 1 | 현재 레벨 |
| `total_exp` | integer | not null, default 0 | 누적 EXP |
| `created_at` | datetime | not null | 생성 시각 |
| `updated_at` | datetime | not null | 수정 시각 |

> `current_animal`은 이번 구현의 활성 ORM/API/service/DTO 계약에서 제거한다. 대표 동물 자동 변경 상태를 DB source-of-truth로 두지 않는다.

### character_owned_animals

사용자가 실제로 보유한 동물 컬렉션이다.

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | integer | PK | 보유 row ID |
| `user_id` | integer | FK `users.id`, index | 사용자 ID |
| `character_profile_id` | integer | FK `character_profiles.id`, index | 캐릭터 프로필 ID |
| `animal_code` | varchar(50) | not null | `frog`, `chick` 등 |
| `unlocked_level` | integer | not null | 해금된 당시 레벨 |
| `unlocked_total_exp` | integer | not null | 해금된 당시 누적 EXP |
| `unlocked_at` | datetime | not null | 해금 시각 |

권장 제약:

| 제약 | 설명 |
|------|------|
| unique(`user_id`, `animal_code`) | 같은 사용자가 같은 동물을 중복 보유하지 않도록 방지 |
| index(`user_id`) | 내 보유 동물 목록 조회 최적화 |
| index(`character_profile_id`) | 프로필 기준 join 최적화 |

### character_growth_logs

EXP 획득/레벨업 이력을 저장한다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | integer | PK |
| `character_profile_id` | integer | 캐릭터 프로필 ID |
| `user_id` | integer | 사용자 ID |
| `exp_gained` | integer | 획득 EXP |
| `before_level` / `after_level` | integer | 지급 전/후 레벨 |
| `before_total_exp` / `after_total_exp` | integer | 지급 전/후 누적 EXP |
| `reason` | string | 예: `MISSION_COMPLETED` |
| `source` | string | 예: `mock_mission` |
| `source_id` | string\|null | 미션 ID 등 |
| `created_at` | datetime | 생성 시각 |

---

## 해금 처리 흐름

```text
CharacterService.gain_exp(user_id, amount, reason, source)
  -> total_exp 증가
  -> level 재계산
  -> growth log 저장
  -> policy에서 현재 level 이하 동물 계산
  -> character_owned_animals에 없는 동물만 insert
  -> 응답에서는 owned_animals 반환
```

중복 방지:

```text
unique(user_id, animal_code)
```

동시 요청에서 같은 동물이 동시에 해금될 수 있으므로 repository는 unique 제약 위반을 안전하게 처리하거나 upsert 패턴을 사용한다.

---

## 테스트 기준

| 테스트 | 검증 내용 |
|--------|----------|
| 기본 프로필 생성 | 신규 사용자 조회 시 프로필 + `frog` 보유 생성 |
| EXP 지급/레벨업 | 누적 EXP로 레벨 상승 |
| 동물 해금 | 레벨 도달 시 신규 동물 보유 row 생성 |
| 중복 방지 | 재조회/추가 EXP 지급 시 기존 동물 중복 저장 없음 |
| `GET /me` | 보유 동물 목록만 홈 렌더링용으로 반환 |
| `GET /animals` | 전체 동물 + locked/unlocked + mock unlock value 반환 |
| mock mission seam | mock mission EXP 지급 후 동물 해금까지 연결 |

---

## Swagger 반영 기준

- `GET /api/v1/characters/me`
  - summary: `[프론트 사용] 내 캐릭터 조회`
  - description에 “보유 동물 목록 반환, 대표 동물 자동 변경 아님” 명시
- `GET /api/v1/characters/animals`
  - summary: `[프론트 사용] 전체 동물 잠금/해금 상태 조회`
  - description에 “mock unlock value 포함” 명시
- `POST /me/experience`, `PATCH /me/stage`
  - `[서버/내부]` 또는 placeholder로 유지
  - 프론트 공개 API로 표시하지 않음
