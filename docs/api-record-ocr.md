# Record / OCR API

> 기준일: 2026-06-29  
> Base URL: `/api/v1/records`  
> 인증: 모든 엔드포인트에 `Authorization: Bearer <access_token>` 헤더 필요

---

## 검진 업로드 플로우

### OCR 업로드 (이미지)

```
1. POST /records/checkups/ocr-preview   ← 이미지 업로드 → OCR 결과 미리보기
         ↓
   사용자가 화면에서 지표 확인·수정
         ↓
2. POST /records/checkups               ← 확인된 결과 저장 (commit)
         ↓
3. POST /records/checkups/{id}/verify   ← 검수 완료 (온보딩 단계 전환 포함)
```

### 수동 입력

```
POST /records/checkups/manual           ← 이미지 없이 수치 직접 입력 후 저장
```

---

## API 목록

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/checkups/ocr-preview` | 이미지 업로드 → OCR preview |
| `POST` | `/checkups` | OCR 결과 확인 후 저장 |
| `POST` | `/checkups/manual` | 수동 입력으로 저장 |
| `GET` | `/checkups` | 검진 기록 목록 |
| `GET` | `/checkups/{id}` | 검진 기록 상세 |
| `GET` | `/checkups/{id}/metrics` | 지표 목록만 조회 |
| `GET` | `/checkups/{id}/trends` | 지표별 추세 데이터 |
| `PATCH` | `/checkups/{id}/metrics/{metric_id}` | 단일 지표 수정 |
| `PUT` | `/checkups/{id}/metrics` | 지표 일괄 수정 |
| `POST` | `/checkups/{id}/verify` | 검수 완료 |
| `DELETE` | `/checkups/{id}` | 검진 기록 삭제 |

---

## 엔드포인트 상세

### POST /checkups/ocr-preview

검진 결과지 이미지를 base64로 전송하면 OCR로 지표를 추출해 반환합니다.  
**이 단계에서는 저장이 일어나지 않습니다.**

**Request**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `images` | `string[]` | ✓ | PNG/JPEG base64 문자열 배열 (1~10장). `data:image/png;base64,...` 형식도 허용 |

제한사항:

| 항목 | 제한 |
|------|------|
| 이미지 장수 | 최소 1장, 최대 10장 |
| 단일 이미지 크기 | 최대 10 MB |
| 전체 합계 크기 | 최대 30 MB |

**Response**

| 필드 | 타입 | 설명 |
|------|------|------|
| `page_count` | `int` | 업로드된 전체 이미지 수 |
| `failed_pages` | `int[]` | OCR 실패한 페이지 인덱스 목록 (0-based) |
| `ocr_status` | `string` | `COMPLETED` / `PARTIAL` (일부 실패) / `FAILED` |
| `content_hash` | `string` | SHA-256 64자리 hex — commit 시 그대로 전달 |
| `metrics[].metric_code` | `string` | 지표 식별 코드 |
| `metrics[].metric_name` | `string` | 지표 한글명 |
| `metrics[].value` | `string\|null` | 추출된 수치 |
| `metrics[].unit` | `string\|null` | 단위 |
| `metrics[].confidence` | `float\|null` | OCR 신뢰도 (0~1) |
| `metrics[].low_confidence` | `bool` | `confidence < 0.8`이면 true — 사용자 확인 권장 |
| `metrics[].out_of_range` | `bool` | 정상 참고 범위 초과 여부 |
| `metrics[].raw_text` | `string\|null` | OCR 원문 |
| `metrics[].page_index` | `int\|null` | 추출된 페이지 인덱스 (0-based) |

---

### POST /checkups

OCR preview 결과를 사용자가 확인·수정한 뒤 저장합니다.  
동일한 `content_hash`로 재요청 시 중복 처리 — 기존 `record_id` 반환.

**Request**

preview 응답값을 그대로 전달하되, `metrics`는 사용자 수정값을 반영합니다.

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `ocr_status` | `string` | ✓ | preview 응답값 그대로 |
| `failed_pages` | `int[]` | ✓ | preview 응답값 그대로 |
| `content_hash` | `string` | ✓ | preview 응답값 그대로 |
| `metrics` | `object[]` | ✓ | 최소 1개 이상 |
| `metrics[].metric_code` | `string` | ✓ | |
| `metrics[].metric_name` | `string` | ✓ | |
| `metrics[].value` | `string\|null` | | |
| `metrics[].unit` | `string\|null` | | |
| `metrics[].confidence` | `float\|null` | | preview 응답값 그대로 |
| `metrics[].raw_text` | `string\|null` | | preview 응답값 그대로 |
| `metrics[].page_index` | `int\|null` | | preview 응답값 그대로 |
| `metrics[].is_edited` | `bool` | | 사용자가 값을 수정했으면 `true` |

**Response**

| 필드 | 타입 | 설명 |
|------|------|------|
| `record_id` | `int` | 저장된 검진 기록 ID |
| `verification_status` | `string` | `UNVERIFIED` / `VERIFIED` |
| `metrics[].metric_id` | `int` | 지표 ID — 개별 수정 시 사용 |
| `metrics[].status` | `string\|null` | `NORMAL` / `LOW` / `HIGH` / `CRITICAL` |
| `metrics[].reference_min` | `float\|null` | 정상 참고 하한 |
| `metrics[].reference_max` | `float\|null` | 정상 참고 상한 |
| `metrics[].source` | `string` | `OCR` / `MANUAL` (`is_edited=true`이면 `MANUAL`) |

중복 업로드 응답 메시지: `"이미 업로드된 검진 결과지입니다."`

---

### POST /checkups/manual

이미지 없이 사용자가 직접 수치를 입력해 저장합니다.

**Request**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `measured_at` | `datetime\|null` | | 검진일. null이면 현재 시각 |
| `metrics` | `object[]` | ✓ | 최소 1개 이상. 필드 구조는 commit과 동일 |

Response 구조는 `POST /checkups`와 동일합니다.

---

### POST /checkups/{record_id}/verify

사용자가 지표를 최종 확인 후 호출합니다. `UNVERIFIED → VERIFIED`로 전환합니다.  
온보딩 `INITIAL_CHECKUP` 단계 사용자는 이 호출로 온보딩 다음 단계로 전이됩니다.

**Request**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `metrics` | `object[]\|null` | | 마지막 수정이 있을 때만 포함 |
| `metrics[].metric_id` | `int` | ✓ | |
| `metrics[].value` | `string` | ✓ | |
| `metrics[].unit` | `string\|null` | | |

**Response**

| 필드 | 타입 | 설명 |
|------|------|------|
| `record_id` | `int` | |
| `verification_status` | `string` | `VERIFIED` |

---

### GET /checkups

| 파라미터 | 타입 | 기본값 | 범위 | 설명 |
|---------|------|--------|------|------|
| `page` | `int` | `1` | ≥ 1 | 페이지 번호 |
| `size` | `int` | `20` | 1~100 | 페이지 크기 |

**Response items 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `record_id` | `int` | |
| `source_type` | `string` | `UPLOAD` (OCR) / `MANUAL` |
| `verification_status` | `string` | `UNVERIFIED` / `VERIFIED` |
| `analysis_status` | `string\|null` | |
| `ocr_status` | `string\|null` | |
| `measured_at` | `datetime\|null` | |
| `created_at` | `datetime` | |
| `metric_count` | `int` | 저장된 지표 수 |

---

### GET /checkups/{record_id}

목록 항목 필드에 `verified_at`, `overall_status`, `metrics` 배열이 추가됩니다.

---

### GET /checkups/{record_id}/metrics

지표 배열만 반환합니다. 구조는 commit 응답의 `metrics`와 동일합니다.

---

### GET /checkups/{record_id}/trends

해당 기록 기준으로 지표별 시계열 데이터를 반환합니다.

**Response**

| 필드 | 타입 | 설명 |
|------|------|------|
| `record_id` | `int` | |
| `trends[].metric_code` | `string` | |
| `trends[].metric_name` | `string` | |
| `trends[].points[].record_id` | `int` | |
| `trends[].points[].date` | `string` | `YYYY-MM-DD` |
| `trends[].points[].value` | `string` | |
| `trends[].points[].unit` | `string\|null` | |

---

### PATCH /checkups/{record_id}/metrics/{metric_id}

**Request**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `value` | `string` | ✓ | 최대 50자 |
| `unit` | `string\|null` | | 최대 20자 |

---

### PUT /checkups/{record_id}/metrics

**Request**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `metrics[].metric_id` | `int` | ✓ | |
| `metrics[].value` | `string` | ✓ | 최대 50자 |
| `metrics[].unit` | `string\|null` | | 최대 20자 |

---

### DELETE /checkups/{record_id}

검진 기록과 연결된 지표를 모두 삭제합니다.

---

## 에러 코드

| HTTP | error_code | 상황 |
|------|-----------|------|
| 400 | `INVALID_IMAGE_FORMAT` | base64 디코딩 실패 또는 PNG/JPEG 외 포맷 |
| 400 | `INVALID_IMAGE_COUNT` | 이미지 0장 또는 10장 초과 |
| 413 | — | 단일 이미지 10MB 초과 또는 전체 30MB 초과 |
| 422 | `OCR_FAILED` | 전체 페이지 OCR 실패 |
| 503 | `OCR_BUSY` | OCR 동시 처리 한도 초과. `Retry-After` 헤더 확인 후 재시도 |
| 404 | — | 존재하지 않거나 본인 소유가 아닌 record_id |

---

## OCR 추출 지표 및 정확도

> OCR provider: Naver Clova General OCR  
> 파서 버전: 2026-06-28 기준 (x좌표 참고치 컬럼 필터링 적용)

### 추출 가능한 주요 metric_code

| metric_code | 한글명 | 단위 |
|-------------|--------|------|
| `height` | 키 | cm |
| `weight` | 체중 | kg |
| `bmi` | 체질량지수 | kg/m² |
| `waist` | 허리둘레 | cm |
| `systolic_bp` | 수축기혈압 | mmHg |
| `diastolic_bp` | 이완기혈압 | mmHg |
| `fasting_glucose` | 공복혈당 | mg/dL |
| `total_cholesterol` | 총콜레스테롤 | mg/dL |
| `triglyceride` | 중성지방 | mg/dL |
| `hdl` | HDL 콜레스테롤 | mg/dL |
| `ldl` | LDL 콜레스테롤 | mg/dL |
| `hemoglobin` | 헤모글로빈 | g/dL |
| `creatinine` | 크레아티닌 | mg/dL |
| `egfr` | 사구체여과율 | mL/min |
| `ast` | AST | U/L |
| `alt` | ALT | U/L |
| `gamma_gtp` | 감마GTP | U/L |
| `urine_protein` | 요단백 | — (음성/양성) |

### 파서 성능 요약 (2026-06-28)

| 이미지 | 추출 수 | 정확 수 | 오추출 | 주요 미추출 |
|--------|--------:|--------:|-------:|------------|
| ocr1.jpeg | 11 | 11 | 0 | systolic_bp, diastolic_bp |
| ocr2.png | 14 | 14 | 0 | hemoglobin, hdl, ldl |
| ocr3.png | 7 | 7 | 0 | height, weight, fasting_glucose, hdl, ldl, egfr, alt |
| ocr4.png | 15 | 15 | 0 | hdl, ldl, urine_protein |
| ocr5.png (빈 서식) | 0 | — | 0 | (정상 동작) |
| **합계** | **47** | **47** | **0** | |

전체 추출 정확도: **47/47 = 100%**

### 알려진 OCR 한계

| 이슈 | 영향 지표 | 원인 | 대응 |
|------|----------|------|------|
| HDL / LDL 미추출 | `hdl`, `ldl` | OCR 토큰이 "HDL-콜레스테롤"처럼 합성되면 exact match 실패 | alias 추가 예정 |
| 멀티컬럼 서식 height/weight 미추출 | `height`, `weight` | 라벨 다음 행에 추가 라벨이 있어 fallback guard 차단 | fallback 조건 개선 예정 |
| 혈압 일부 서식 미추출 | `systolic_bp`, `diastolic_bp` | "유질환자 고혈압" alias 매칭 후 다음 행 라벨 guard 차단 | live OCR 토큰 배치 차이로 픽스처와 동작 분기 가능 |
| 멀티컬럼 서식 bmi 미추출 | `bmi` | x좌표 필터(form 너비 65% 임계값)로 참고치 컬럼 제거 시 실제값도 제거됨 | 구조적 한계, 별도 개선 필요 |

### low_confidence 플래그

`confidence < 0.8`인 지표에 `low_confidence: true`가 설정됩니다.  
화면에서 사용자에게 확인을 유도하는 용도로 활용하세요.

낮은 신뢰도가 자주 발생하는 지표:

| metric_code | 발생 원인 |
|-------------|----------|
| `creatinine` | 소수점 수치, 서식별 폰트 차이 |
| `egfr` | 계산값 표기 방식 혼재 |
| `fasting_glucose` | 일부 서식에서 단위 컬럼 분리 |
| `triglyceride` | 컬럼 배치 혼입 가능성 |
