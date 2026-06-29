# 구현 현황

> 기준일: 2026-06-29  
> 실행 중인 서버의 Swagger/OpenAPI가 API 계약의 최종 기준입니다. 이 문서는 팀 공유용 요약입니다.

범례: 구현, 부분, stub

## 요약

| 영역 | 상태 | 프론트 연동 |
|------|------|-------------|
| Auth / User | 구현 | 가능 |
| Onboarding | 구현 | 가능 |
| Record / OCR | 구현 | 가능 |
| HealthMetric | 구현 | 가능 |
| Analysis | 구현 (Stub MVP) | 가능 |
| Mission / Character | stub | 501 응답 (UserMission 자동 배정만 Phase 4) |
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

| Method | Path | 설명 |
|--------|------|------|
| POST | `/checkups/upload` | 검진 이미지 업로드, OCR preview |
| POST | `/checkups/ocr-preview` | OCR preview |
| POST | `/checkups` | 검진 결과 커밋 |
| POST | `/checkups/manual` | 수동 검진 입력 |
| GET | `/checkups` | 검진 목록 |
| GET | `/checkups/{id}` | 검진 상세 |
| GET | `/checkups/{id}/trends` | 지표 추세 |
| GET | `/checkups/{id}/metrics` | 검진 지표 목록 |
| PATCH | `/checkups/{id}/metrics/{metric_id}` | 단일 지표 수정 |
| PUT | `/checkups/{id}/metrics` | 여러 지표 수정 |
| POST | `/checkups/{id}/verify` | 검진 검수 완료 |
| DELETE | `/checkups/{id}` | 검진 삭제 |

아직 구현하지 않은 Record API:

| Method | Path | 상태 |
|--------|------|------|
| POST/GET | `/meals` | stub/미구현 |

### OCR `/api/v1/ocr`

| Method | Path | 설명 |
|--------|------|------|
| GET | `/jobs/{job_id}` | OCR job 상태 조회 |

### HealthMetric `/api/v1/health-metrics`

| Method | Path | 설명 |
|--------|------|------|
| POST | `/evaluate` | 건강 지표 평가 |
| POST | `/analyses` | 건강 지표 분석 저장/조회 흐름 |

### Analysis `/api/v1/analysis` (Phase 4 Stub MVP)

| Method | Path | 설명 |
|--------|------|------|
| POST | `/checkups/{record_id}` | 분석 요청 (`ANALYSIS_CLIENT=stub`, 가짜 callback) |
| GET | `/jobs/{analysis_job_id}` | 분석 상태 폴링 |
| GET | `/jobs/{analysis_job_id}/result` | 분석 결과 조회 |
| POST | `/callback` | 외부 callback (서명 검증, 멱등) |

분석 COMPLETED 시 `MissionTemplate` seed(`DEFAULT_SELF_CHECK`) 기준 **UserMission 1건 자동 배정**.

## Stub API

| Prefix | 상태 |
|--------|------|
| `/api/v1/missions` | 미션 API 미완성 (UserMission DB 레코드는 Phase 4에서 생성됨) |
| `/api/v1/characters` | 성장/캐릭터 도메인 미완성 |
| `/api/v1/home` | 홈 aggregation 미완성 |
| `/api/v1/notifications` | 알림 도메인 미완성 |
| `/api/v1/my` | 마이페이지·지원 기능 미완성 |

## 마이그레이션

| Revision | 내용 |
|----------|------|
| `001` ~ `008` | (기존) |
| `009_add_analysis_schema` | analysis_jobs, summaries, mission_candidates, mission_templates seed, user_missions |

## 다음 구현 우선순위

1. Phase 5 Mission/Growth: `GET /missions/today`, complete/XP, growth
2. Home aggregation
3. Http/OpenAI AnalysisClient (현재 stub만)
4. Notification/My/Search

## 검증 기준

```bash
ruff check .
ruff format --check .
mypy app tests
pytest tests/
```
