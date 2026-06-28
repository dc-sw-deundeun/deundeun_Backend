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
| Analysis | stub | 501 응답 |
| Mission / Character | stub | 501 응답 |
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

## Stub API

아래 라우터는 현재 사용자-facing 기능으로 쓰면 안 됩니다. 호출 시 `NOT_IMPLEMENTED` 또는 501 계열 응답을 기대해야 합니다.

| Prefix | 상태 |
|--------|------|
| `/api/v1/analysis` | 외부 분석 서버 연동 미완성 |
| `/api/v1/missions` | 미션 도메인 미완성 |
| `/api/v1/characters` | 성장/캐릭터 도메인 미완성 |
| `/api/v1/home` | 홈 aggregation 미완성 |
| `/api/v1/notifications` | 알림 도메인 미완성 |
| `/api/v1/my` | 마이페이지·지원 기능 미완성 |

## 마이그레이션

현재 Alembic head까지 적용하면 아래 영역의 스키마가 생성됩니다.

| Revision | 내용 |
|----------|------|
| `001_initial_auth_schema` | 인증·사용자 초기 스키마 |
| `002_add_auth_indexes_and_user_timestamp_trigger` | 인증 인덱스, updated_at trigger |
| `003_add_login_lock_and_access_token_blacklist` | 로그인 잠금, 토큰 블랙리스트 |
| `97a644712a37_init_ocr_checkup_schema` | OCR·검진 초기 스키마 |
| `76928652848e_add_page_index_drop_dedup` | OCR metric page index 추가 |
| `983204074d73_drop_ocr_jobs_raw_result_url` | OCR job raw result URL 제거 |
| `004_add_health_metric_analyses` | health metric 분석 테이블 |
| `005_add_health_metric_analysis_measured_at` | 분석 measured_at 추가 |
| `006_merge_health_metric_and_ocr_heads` | health metric/OCR head 병합 |
| `007_add_wearable_connections` | wearable 연결 테이블 |
| `008_add_health_metric_references` | 건강 지표 reference seed, file hash unique |

## 다음 구현 우선순위

1. Analysis API 실제 구현: 요청 생성, 상태 조회, callback, polling, 서명 검증
2. Mission/Character: 오늘의 미션, 완료/검증, XP/성장
3. Home aggregation: 홈 화면에 필요한 요약 응답
4. Notification/My/Search: 사용자 설정, 알림, 검색, 지원 기능

## 검증 기준

변경 후 최소 확인:

```bash
ruff check .
ruff format --check .
mypy app tests
pytest tests/
```
