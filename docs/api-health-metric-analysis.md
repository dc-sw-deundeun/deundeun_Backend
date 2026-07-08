# HealthMetric 분석 플로우

이 문서는 프론트가 OCR 결과를 확인한 뒤 건강 지표 분석을 저장하고 조회하는 흐름을 정리합니다.

## 전체 흐름

1. 프론트는 OCR preview 또는 검진 상세 API에서 metric 후보를 받습니다.
2. 사용자는 UI에서 항목명, 값, 단위를 확인하거나 수정합니다.
3. 저장 버튼을 누르면 프론트는 확정된 metric 배열만 `POST /api/v1/health-metrics/analyses`로 보냅니다.
4. 백엔드는 분석 가능한 항목만 canonical code로 매핑하고 기준표로 상태를 판정합니다.
5. 분석 결과, range bar, 설명, 추천, highlight를 정규화 테이블에 저장합니다.
6. 생성 API는 결과 본문을 반환하지 않고 `data: null`만 반환합니다.
7. 화면에 다시 보여줄 때는 `GET /api/v1/health-metrics/analyses/{analysis_id}`를 호출합니다.

## 생성 API

```http
POST /api/v1/health-metrics/analyses
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Request Body

프론트는 OCR 원본 전체가 아니라, 사용자가 확정한 metric 배열만 전달합니다.

```json
{
  "record_id": 22,
  "sex": "male",
  "measured_at": "2026-06-20",
  "metrics": [
    {
      "metric_code": "fasting_glucose",
      "metric_name": "공복혈당",
      "value": "126",
      "unit": "mg/dL",
      "raw_text": "126"
    },
    {
      "metric_code": "ldl",
      "metric_name": "LDL콜레스테롤",
      "value": "160",
      "unit": "mg/dL",
      "raw_text": "160"
    }
  ]
}
```

| 필드 | 필수 | 설명 |
|------|------|------|
| `record_id` | 아니오 | 저장된 검진 기록과 분석을 연결할 때 사용합니다. 제공하면 현재 사용자 소유 기록인지 확인합니다. |
| `sex` | 예 | 성별 기준이 필요한 지표 판정에 사용합니다. 예: `male`, `female`, `M`, `F` |
| `measured_at` | 아니오 | 검진일 또는 측정일입니다. ISO date/datetime 문자열을 받습니다. |
| `metrics` | 예 | 확정된 건강검진 지표 배열입니다. 최소 1개, 최대 100개입니다. |
| `metrics[].metric_code` | 예 | OCR/프론트가 가진 지표 코드입니다. 백엔드에서 canonical code로 매핑합니다. |
| `metrics[].metric_name` | 예 | 화면 표시명 또는 OCR 항목명입니다. |
| `metrics[].value` | 예 | 판정할 값입니다. 숫자로 파싱 가능한 문자열이어야 분석됩니다. |
| `metrics[].unit` | 아니오 | 단위입니다. |
| `metrics[].raw_text` | 아니오 | OCR 원문 값입니다. 저장 후 추적용으로 사용합니다. |

숫자로 판정할 수 없거나 현재 기준표에 없는 항목은 분석 저장 대상에서 제외됩니다. 모든 항목이 제외되면 `422 NO_ANALYZABLE_HEALTH_METRICS`가 반환됩니다.

### Response Body

생성 응답에는 분석 결과를 포함하지 않습니다.

```json
{
  "success": true,
  "message": "건강검진 분석이 생성되었습니다.",
  "data": null,
  "error_code": null
}
```

## 조회 API

```http
GET /api/v1/health-metrics/analyses/{analysis_id}
Authorization: Bearer <access_token>
```

조회 응답은 저장된 정규화 row를 조합해서 화면용 JSON으로 반환합니다.

```json
{
  "success": true,
  "message": "요청이 성공했습니다.",
  "data": {
    "analysis_id": 1,
    "record_id": null,
    "results": [
      {
        "input_label": "공복혈당",
        "canonical_test_code": "FPG",
        "name": "공복혈당",
        "value": 126.0,
        "unit": "mg/dL",
        "status": "risk",
        "status_label": "위험",
        "matched_rule": "FPG >= 126",
        "note": null
      }
    ],
    "explanation": {
      "status": "fallback",
      "summary": "위험으로 분류된 항목이 있어 결과를 확인하고 필요하면 전문가와 상담하는 것이 좋습니다.",
      "highlights": [
        "위험 항목이 1개 있습니다."
      ],
      "item_explanations": [
        {
          "canonical_test_code": "FPG",
          "input_label": "공복혈당",
          "title": "공복혈당",
          "explanation": "공복혈당은 당 대사 상태를 확인하는 지표입니다.",
          "status_label": "위험"
        }
      ],
      "disclaimer": "이 분석은 건강 관리를 돕기 위한 참고 정보이며, 진단이나 치료를 대신하지 않습니다."
    },
    "ui": {
      "summary": {
        "analysis_id": 1,
        "overall": {
          "title": "관리가 필요해요",
          "summary": "위험으로 분류된 항목이 있어 결과를 확인하고 필요하면 전문가와 상담하는 것이 좋습니다.",
          "counts": {
            "normal": 0,
            "caution": 0,
            "risk": 1,
            "unknown": 0
          }
        },
        "cards": []
      },
      "details": []
    }
  },
  "error_code": null
}
```

## Range Bar

각 지표의 range bar는 전체 표시 범위와 구간 배열, 현재 값이 속한 구간을 함께 반환합니다.

```json
{
  "min": 70.0,
  "max": 160.0,
  "marker": 126.0,
  "marker_percent": 62.22,
  "segments": [
    {
      "label": "안심 ~99",
      "from_value": 70.0,
      "to_value": 99.0,
      "color": "green"
    },
    {
      "label": "경계 100~125",
      "from_value": 100.0,
      "to_value": 125.0,
      "color": "yellow"
    },
    {
      "label": "위험 126~",
      "from_value": 126.0,
      "to_value": 160.0,
      "color": "red"
    }
  ],
  "active_segment": {
    "label": "위험 126~",
    "from_value": 126.0,
    "to_value": 160.0,
    "color": "red",
    "marker_percent": 0.0
  }
}
```

| 필드 | 설명 |
|------|------|
| `marker_percent` | 전체 range bar에서 현재 값의 위치입니다. |
| `active_segment` | 현재 값이 속한 구간입니다. |
| `active_segment.marker_percent` | 해당 구간 내부에서 현재 값의 위치입니다. 예를 들어 위험 구간의 시작값이면 `0.0`입니다. |

## 저장 구조

분석 생성 시 결과 JSON 전체를 한 컬럼에 저장하지 않습니다. 조회와 통계를 위해 아래처럼 정규화해서 저장합니다.

| 테이블 | 역할 |
|--------|------|
| `health_metric_analyses` | 분석 헤더, 사용자, 측정일, 전체 요약, 상태 count |
| `health_metric_analysis_items` | 지표별 판정 결과, canonical code, 값, 상태, 설명 |
| `health_metric_analysis_item_ranges` | 지표별 range bar의 전체 범위와 marker 위치 |
| `health_metric_analysis_range_segments` | range bar 구간 목록 |
| `health_metric_analysis_item_recommendations` | 지표별 추천 문구 |
| `health_metric_analysis_highlights` | 분석 상단 highlight 문구 |

기존 JSON payload 컬럼은 과거 데이터 호환을 위해 nullable로 남아 있습니다. 신규 생성 로직은 `request_payload`, `results_payload`, `explanation_payload`, `summary_payload`, `details_payload`를 채우지 않습니다.

## 예외와 제한

| 상황 | 응답 |
|------|------|
| 인증 토큰 없음 또는 잘못됨 | `401` |
| 요청 body validation 실패 | `422` |
| 분석 가능한 metric이 없음 | `422 NO_ANALYZABLE_HEALTH_METRICS` |
| `record_id`가 존재하지 않거나 다른 사용자의 기록 | `404` |
| 생성 rate limit 초과 | `429 RATE_LIMIT_EXCEEDED` |
| 다른 사용자의 분석 조회 또는 없는 분석 ID | `404 HEALTH_METRIC_ANALYSIS_NOT_FOUND` |

## 프론트 연동 기준

- 저장 버튼은 `POST /health-metrics/analyses`만 호출합니다.
- 생성 직후 결과 화면이 필요하면 생성 응답이 아니라 별도 조회 API를 호출해야 합니다.
- OCR/검진 기록에서 분석을 생성하는 경우 `record_id`를 함께 보내야 `GET /records/checkups/{record_id}/analysis`로 최신 분석을 조회할 수 있습니다.
- 프론트가 OCR confidence, page index, failed page 정보를 분석 API로 넘길 필요는 없습니다.
- 화면의 range bar는 `range_bar.segments`와 `range_bar.active_segment`를 기준으로 그립니다.
- 과거 추이는 `record_id`가 있으면 검진 기록 이력, 없으면 저장된 HealthMetric 분석 이력을 기준으로 `ui.details[].trend.points`에 포함됩니다.
