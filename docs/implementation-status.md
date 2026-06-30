# 구현 현황

> 기준일: 2026-06-30
> 실행 중인 서버의 Swagger/OpenAPI가 API 계약의 최종 기준입니다. 이 문서는 팀 공유용 요약입니다.

범례: 구현, 부분, stub

## 요약

| 영역 | 상태 | 프론트 연동 |
|------|------|-------------|
| Auth / User | 구현 | 가능 |
| Onboarding | 구현 | 가능 |
| Record / OCR | 구현 | 가능 |
| HealthMetric | 구현 | 가능 |
| Analysis | legacy stub | 프론트 작업 제외 |
| Mission / Character | 부분 | Character 성장/동물 해금 API 구현 브랜치 진행 중 |
| Home | stub | 501 응답 |
| Notification | stub | 501 응답 |
| My / Support | stub | 501 응답 |
| Search | 미생성 | 라우터 없음 |

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

| Method | Path | 설명 |
|--------|------|------|
| POST | `/evaluate` | 건강 지표 평가(비저장 프리뷰) |
| POST | `/analyses` | 건강 지표 분석 저장, full UI 응답 반환 |
| GET | `/analyses/{analysis_id}` | 저장된 건강 지표 분석 조회 |

`POST /analyses`에 `record_id`를 전달하면 사용자 소유 VERIFIED 검진 기록만 허용하며, 성공 시 `CheckupRecord.analysis_status=COMPLETED`로 갱신합니다. 저장/조회 응답은 `analysis_id`, `record_id`, `results`, `explanation`, `ui.summary`, `ui.details`를 포함하고, record 연결 시 detail trend points를 포함합니다.

### Analysis `/api/v1/analysis` (Legacy Phase 4 Stub)

| Method | Path | 설명 |
|--------|------|------|
| POST | `/checkups/{record_id}` | legacy 분석 요청 (`ANALYSIS_CLIENT=stub`, 가짜 callback) |
| GET | `/jobs/{analysis_job_id}` | legacy 분석 상태 폴링 |
| GET | `/jobs/{analysis_job_id}/result` | legacy 분석 결과 조회 |
| POST | `/callback` | 외부 callback (서명 검증, 멱등) |

신규 프론트 화면은 `/api/v1/analysis/*`를 호출하지 않고 HealthMetric 분석 API를 사용합니다.

### Character `/api/v1/characters` (구현 브랜치 진행 중)

상세 계약은 [api-character-growth.md](./api-character-growth.md) 참조.

| Method | Path | 설명 |
|--------|------|------|
| GET | `/me` | 내 캐릭터 성장 상태와 보유 동물 목록 조회 |
| GET | `/animals` | 전체 동물 카탈로그와 내 locked/unlocked 상태 조회 |

`POST /me/experience`, `PATCH /me/stage`는 서버/내부 placeholder이며 프론트 공개 API가 아닙니다.

## Stub API

| Prefix | 상태 |
|--------|------|
| `/api/v1/missions` | 미션 API 미완성 (UserMission DB 레코드는 Phase 4에서 생성됨) |
| `/api/v1/home` | 홈 aggregation 미완성 |
| `/api/v1/notifications` | 알림 도메인 미완성 |
| `/api/v1/my` | 마이페이지·지원 기능 미완성 |

## 마이그레이션

| Revision | 내용 |
|----------|------|
| `001` ~ `008` | (기존) |
| `009_add_analysis_schema` | analysis_jobs, summaries, mission_candidates, mission_templates seed, user_missions |
| `010_add_health_metric_analysis_record_id` | health_metric_analyses.record_id 및 checkup_records 연결 |
| `011_add_character_growth_schema` | character_profiles, character_growth_logs, character_owned_animals |

## 다음 구현 우선순위

1. Phase 5 Mission/Growth: HealthMetric analysis 기반 미션 생성/수락, `GET /missions/today`, complete/XP, growth
2. Home aggregation
3. Legacy Analysis 도메인 제거 또는 migration 정리 정책 확정
4. Notification/My/Search

## 검증 기준

```bash
ruff check .
ruff format --check .
mypy app tests
pytest tests/
```
