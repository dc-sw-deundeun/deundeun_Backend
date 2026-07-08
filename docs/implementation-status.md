# 구현 현황

> 기준일: 2026-07-06
> 실행 중인 서버의 Swagger/OpenAPI가 API 계약의 최종 기준입니다. 이 문서는 팀 공유용 요약입니다.

범례: 구현, 부분, legacy stub, 서버/내부, stub

## 요약

| 영역 | 상태 | 프론트 연동 |
|------|------|-------------|
| Auth / User | 구현 | 가능 |
| Onboarding | 구현 | 가능 |
| Record / OCR | 구현 | 가능 |
| HealthMetric | 구현 | 가능 |
| Analysis | legacy stub | 프론트 작업 제외 |
| Mission | 부분 | `GET /today`, `POST /{id}/complete` 가능, 인증·캘린더·통계·complete→EXP는 후속 |
| Character | 구현 | 가능 |
| Home | 구현 | 가능 |
| My | 부분 | 연동 앱·알림 설정 가능, 프로필·앱잠금·문의·계정삭제는 stub |
| Search | 구현 | 가능 |
| PKG | 서버/내부 | 신규 프론트 화면 직접 호출 제외 |
| Notification | 구현 | 알림함 목록·읽음 처리 가능 |

## 구현된 API

### Auth `/api/v1/auth`

| Method | Path | 설명 |
|--------|------|------|
| POST | `/email/verify/request` | 이메일 인증 코드 요청 |
| POST | `/email/verify/confirm` | 이메일 인증 확인 |
| POST | `/signup` | 회원가입 |
| POST | `/login` | 로그인 |
| POST | `/refresh` | access token 재발급 |
| POST | `/logout` | 로그아웃 |
| POST | `/password/reset/request` | 비밀번호 재설정 요청 |
| POST | `/password/reset/confirm` | 비밀번호 재설정 확인 |
| GET | `/me` | 내 정보 |
| POST | `/policies/agree` | 약관 동의, 온보딩 단계 전환 |

### Onboarding `/api/v1/onboarding`

| Method | Path | 설명 |
|--------|------|------|
| GET | `/status` | 온보딩 진행 상태 |
| POST | `/wearable` | wearable CONNECT/SKIP |
| POST | `/complete` | 온보딩 완료 |

### Record `/api/v1/records`

OCR 업로드 플로우 상세는 [api-record-ocr.md](./api-record-ocr.md) 참조.

| Method | Path | 설명 |
|--------|------|------|
| POST | `/checkups/ocr-preview` | OCR preview |
| POST | `/checkups` | 검진 결과 커밋 |
| POST | `/checkups/manual` | 수동 검진 입력 |
| GET | `/checkups` | 검진 목록 |
| GET | `/checkups/{id}` | 검진 상세 |
| GET | `/checkups/{id}/trends` | 지표 추세 |
| GET | `/checkups/{id}/analysis` | 연결된 최신 HealthMetric 분석 조회 |
| GET | `/checkups/{id}/metrics` | 검진 지표 목록 |
| PATCH | `/checkups/{id}/metrics/{metric_id}` | 단일 지표 수정 |
| PUT | `/checkups/{id}/metrics` | 여러 지표 수정 |
| POST | `/checkups/{id}/verify` | 검진 검수 완료 |
| DELETE | `/checkups/{id}` | 검진 삭제 |

### HealthMetric `/api/v1/health-metrics`

분석 저장·조회 플로우 상세는 [api-health-metric-analysis.md](./api-health-metric-analysis.md) 참조.

| Method | Path | 설명 |
|--------|------|------|
| POST | `/analyses` | 건강 지표 분석 저장, `data: null` 응답 |
| GET | `/analyses/{analysis_id}` | 저장된 건강 지표 분석 조회 |

`POST /analyses`는 프론트가 확정한 `sex`, `measured_at`, `metrics[]`를 받아 분석을 저장합니다. 생성 응답은 결과 본문을 반환하지 않으며, 저장 분석 조회 응답은 `analysis_id`, `record_id`, `results`, `explanation`, `ui.summary`, `ui.details`를 포함합니다. detail trend points는 이전 HealthMetric 분석 이력을 기준으로 구성합니다.

### Analysis `/api/v1/analysis` (Legacy Phase 4 Stub)

| Method | Path | 설명 |
|--------|------|------|
| POST | `/checkups/{record_id}` | legacy 분석 요청 (`ANALYSIS_CLIENT=stub`, 가짜 callback) |
| GET | `/jobs/{analysis_job_id}` | legacy 분석 상태 폴링 |
| GET | `/jobs/{analysis_job_id}/result` | legacy 분석 결과 조회 |
| POST | `/callback` | 외부 callback (서명 검증, 멱등) |

신규 프론트 화면은 `/api/v1/analysis/*`를 호출하지 않고 HealthMetric 분석 API를 사용합니다.

### Character `/api/v1/characters`

상세 계약은 [api-character-growth.md](./api-character-growth.md) 참조.

| Method | Path | 설명 |
|--------|------|------|
| GET | `/me` | 내 캐릭터 성장 상태와 보유 동물 목록 조회 |
| GET | `/animals` | 전체 동물 카탈로그와 내 locked/unlocked 상태 조회 |

`POST /me/experience`, `PATCH /me/stage`는 서버/내부 placeholder이며 프론트 공개 API가 아닙니다.

### Home `/api/v1/home`

상세 계약은 [api-home.md](./api-home.md) 참조.

| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | 홈 화면 사용자·캐릭터·오늘 미션·알림 카운트 집계 |
| GET | `/summary` | 홈 상단/위젯용 축약 집계 |

`unread_notification_count`는 Notification inbox의 미읽음 알림 수를 반환합니다.

### Mission `/api/v1/missions`

상세 계약은 [api-home.md](./api-home.md) 참조.

| Method | Path | 설명 |
|--------|------|------|
| GET | `/today` | 사용자 timezone 기준 오늘 미션 목록과 완료 집계 |
| POST | `/{mission_id}/complete` | 본인 미션 self-report 완료(멱등) |

`POST /{mission_id}/complete`는 self-report 완료(멱등, 상태 전이만)입니다. **캐릭터 EXP 지급·LEVEL_UP 알림은 연결되지 않았으며** Phase 5 확장 대상입니다.

`POST /{mission_id}/verify`, `GET /calendar`, `GET /statistics/weekly`, `POST /notifications/send`는 후속 Phase placeholder입니다.

미션 생성은 REST API가 아니라 백그라운드 스케줄러(매시 틱, PKG 기반)가 담당합니다. `GET /today`는 조회만 하고, 새 검진 저장 시 당일 미완료 미션을 무효화·재생성합니다. 완료 이력(14일 완료율)은 다음 생성에 반영됩니다.

### My `/api/v1/my`

상세 계약은 [api-my-page.md](./api-my-page.md) 참조.

| Method | Path | 설명 |
|--------|------|------|
| GET | `/connected-apps` | 연동 앱 목록 및 상태 조회 |
| PATCH | `/connected-apps/{provider}` | 연동 앱 상태 토글 |
| GET | `/notification-settings` | 알림 설정 조회, 없으면 기본값 자동 생성 |
| PATCH | `/notification-settings` | 알림 설정 부분 업데이트 |
| GET | `/profile` | 마이페이지 프로필 조회 |
| PATCH | `/profile` | 닉네임 수정 |
| DELETE | `/account` | 회원탈퇴(소프트 탈퇴, 세션 무효화) |

`PATCH /password`, `GET/PATCH /app-lock`, `POST /support`는 후속 Phase placeholder입니다. 비밀번호 재설정은 Auth API를 사용합니다.

### Search `/api/v1/search`

상세 계약은 [api-search.md](./api-search.md) 참조.

| Method | Path | 설명 |
|--------|------|------|
| GET | `/diseases?q=검색어` | 의학 KG + AI 기반 질환 검색 |

Neo4j가 연결되어 있으면 의학 지식 그래프 참조 데이터를 사용하고, Neo4j 미연결 시에도 AI 단독 결과를 반환합니다.

### PKG `/api/v1/pkg`

| Method | Path | 설명 |
|--------|------|------|
| GET | `/{user_id}` | 개인 지식그래프(PKG) 조회 및 스냅샷 저장 |

PKG는 미션 생성 엔진이 소비하는 서버/내부 계약입니다. 로그인 사용자는 본인 PKG만 조회할 수 있고, 검증된 검진 기록이 없으면 404를 반환합니다. 신규 프론트 화면에서는 직접 호출하지 않습니다.

### Notification `/api/v1/notifications`

상세 계약은 [api-notification.md](./api-notification.md) 참조.

| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | 알림 목록 조회, 페이지네이션, 미읽음 필터 |
| PATCH | `/{notification_id}/read` | 알림 읽음 처리(멱등) |

**알림 설정 정본 (D-BE-004, 옵션 A)**: `GET/PATCH /my/notification-settings` — [api-my-page.md](./api-my-page.md)

`GET/PATCH /notifications/settings`, `POST /notifications/test`는 제공하지 않습니다. HealthMetric 분석 저장은 `ANALYSIS_COMPLETED`, `gain_exp` 레벨업은 `LEVEL_UP` 알림을 생성합니다. 미션 complete→EXP→LEVEL_UP 알림은 Phase 5 확장입니다.

## Stub API

| Prefix | 상태 |
|--------|------|
| `/api/v1/missions/*` | `/today`, `/{id}/complete` 외 미션 인증·캘린더·통계·알림 발송 미완성 |
| `/api/v1/my/app-lock`, `/api/v1/my/support` | 마이페이지 후속 기능 미완성 |

## 마이그레이션

| Revision | 내용 |
|----------|------|
| `001` ~ `008` | (기존) |
| `009_add_analysis_schema` | analysis_jobs, summaries, mission_candidates, mission_templates seed, user_missions |
| `010_add_health_metric_analysis_record_id` | health_metric_analyses.record_id 및 checkup_records 연결 |
| `011_add_character_growth_schema` | character_profiles, character_growth_logs, character_owned_animals |
| `012_normalize_health_metric_analysis` | HealthMetric 분석 결과 정규화 저장 테이블 |
| `013_add_pkg_snapshots` | PKG 스냅샷 영속 테이블 |
| `014_add_notification_preferences_columns` | My 알림 설정 저장 테이블 |
| `015_add_mission_generation_runs` | 미션 생성 멱등 로그(유저·날짜당 1회 생성 보장) |
| `016_extend_user_missions_for_generated` | user_missions에 엔진 생성분 저장 컬럼 추가(`template_code`, `payload`, `completed_at`), `template_id` nullable화 |
| `017_add_notifications_inbox` | 알림함 `notifications` 테이블, 사용자·이벤트 source 멱등 unique |

## 다음 구현 우선순위

1. Phase 5 Mission 확장: complete→`gain_exp`·LEVEL_UP 루프, 인증·캘린더·통계
2. My 후속: 앱잠금, 문의, 비밀번호 변경
3. Notification 7b: push, 리마인드 scheduler workers
5. Legacy Analysis 도메인 제거 또는 migration 정리 정책 확정

## 검증 기준

```bash
ruff check .
ruff format --check .
mypy app tests
pytest tests/
```
