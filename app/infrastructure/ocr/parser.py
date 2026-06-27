import re
import statistics

from pydantic import BaseModel

from app.infrastructure.ocr.metric_dictionary import (
    METRIC_SPEC_BY_CODE,
    METRIC_SPECS,
    MetricSpec,
    find_best_alias_match,
    is_plausible,
    normalize_label,
)
from app.infrastructure.ocr.ocr_dto import OcrFieldDTO, OcrResultDTO

_NUMBER_RE = re.compile(r"^\d+(\.\d+)?$")
_REFERENCE_MARKERS = ("정상", "미만", "이하", "이상", "~", "범위", "음성±")
# alias 중 가장 긴 것의 문자 수 = 글자별 토큰 분리 시 필요한 최대 윈도우 크기
_MAX_LABEL_WINDOW: int = max(
    len(normalize_label(alias)) for spec in METRIC_SPECS for alias in spec.aliases
)


class ParsedMetric(BaseModel):
    metric_code: str
    metric_name: str
    value: str
    unit: str
    confidence: float
    raw_text: str
    page_index: int = 0
    out_of_range: bool = False


def _is_number(text: str) -> bool:
    return bool(_NUMBER_RE.match(text.strip()))


def _is_reference(text: str) -> bool:
    return any(marker in text for marker in _REFERENCE_MARKERS)


class OcrParser:
    def parse(self, result: OcrResultDTO) -> list[ParsedMetric]:
        if not result.fields:
            return []
        heights = [f.y_height for f in result.fields if f.y_height > 0]
        row_tolerance = max(15.0, statistics.median(heights) * 1.0) if heights else 20.0
        rows = self._cluster_rows(result.fields, row_tolerance)
        metrics: list[ParsedMetric] = []
        seen: set[str] = set()
        for row_index, row in enumerate(rows):
            found = self._find_label_in_row(row)
            if found is None:
                continue
            spec, label_end = found
            right = [f for f in row[label_end:] if not _is_reference(f.text)]
            extracted = self._extract(spec, right)
            if not extracted and spec.kind in ("hw_pair", "bp_pair") and row_index + 1 < len(rows):
                next_row = rows[row_index + 1]
                if self._find_label_in_row(next_row) is None:
                    extracted = self._extract(
                        spec,
                        [f for f in next_row if not _is_reference(f.text)],
                    )
            if not extracted and spec.code == "alt" and row_index > 0:
                extracted = self._extract_alt_from_previous_ast_row(rows[row_index - 1])
            for m in extracted:
                if m.metric_code not in seen:
                    seen.add(m.metric_code)
                    metrics.append(m)
        return metrics

    def _cluster_rows(self, fields: list[OcrFieldDTO], tolerance: float) -> list[list[OcrFieldDTO]]:
        ordered = sorted(fields, key=lambda f: f.y_center)
        rows: list[list[OcrFieldDTO]] = []
        for fld in ordered:
            if rows:
                row_ys = [f.y_center for f in rows[-1]]
                row_y = statistics.median(row_ys)
                candidate_span = max([*row_ys, fld.y_center]) - min([*row_ys, fld.y_center])
            else:
                row_y = None
                candidate_span = 0.0
            if (
                row_y is not None
                and abs(fld.y_center - row_y) <= tolerance
                and candidate_span <= tolerance
            ):
                rows[-1].append(fld)
            else:
                rows.append([fld])
        for row in rows:
            row.sort(key=lambda f: f.x_min)
        return rows

    def _find_label_in_row(self, row: list[OcrFieldDTO]) -> tuple[MetricSpec, int] | None:
        """행에서 가장 긴 alias로 매칭되는 스펙을 반환한다.

        연속 토큰을 최대 _MAX_LABEL_WINDOW개씩 join해 alias 매칭 시도.
        반환: (spec, label_end_idx) — label_end_idx 이후가 값 후보 영역.
        """
        best_spec: MetricSpec | None = None
        best_alias_len: int = 0
        best_end: int = 0

        for start in range(len(row)):
            for window in range(1, _MAX_LABEL_WINDOW + 1):
                if start + window > len(row):
                    break
                combined = "".join(f.text for f in row[start : start + window])
                match = find_best_alias_match(combined)
                if match and len(match[1]) > best_alias_len:
                    best_spec = match[0]
                    best_alias_len = len(match[1])
                    best_end = start + window

        return (best_spec, best_end) if best_spec else None

    def _extract(self, spec: MetricSpec, right: list[OcrFieldDTO]) -> list[ParsedMetric]:
        if spec.kind == "bp_pair":
            return self._extract_bp(right)
        if spec.kind == "hw_pair":
            return self._extract_hw(right)
        if spec.kind == "categorical":
            return self._extract_categorical(spec, right)
        return self._extract_numeric(spec, right)

    def _extract_numeric(self, spec: MetricSpec, right: list[OcrFieldDTO]) -> list[ParsedMetric]:
        for fld in right:
            if _is_number(fld.text):
                return [
                    ParsedMetric(
                        metric_code=spec.code,
                        metric_name=spec.name,
                        value=fld.text.strip(),
                        unit=spec.unit,
                        confidence=fld.confidence,
                        raw_text=fld.text,
                        out_of_range=not is_plausible(spec, fld.text),
                    )
                ]
        return []

    def _extract_bp(self, right: list[OcrFieldDTO]) -> list[ParsedMetric]:
        numbers = [f for f in right if _is_number(f.text)]
        if len(numbers) < 2:
            return []
        sys_f, dia_f = numbers[0], numbers[1]
        sys_spec = METRIC_SPEC_BY_CODE["systolic_bp"]
        dia_spec = METRIC_SPEC_BY_CODE["diastolic_bp"]
        return [
            ParsedMetric(
                metric_code="systolic_bp",
                metric_name="수축기혈압",
                value=sys_f.text.strip(),
                unit="mmHg",
                confidence=sys_f.confidence,
                raw_text=sys_f.text,
                out_of_range=not is_plausible(sys_spec, sys_f.text),
            ),
            ParsedMetric(
                metric_code="diastolic_bp",
                metric_name="이완기혈압",
                value=dia_f.text.strip(),
                unit="mmHg",
                confidence=dia_f.confidence,
                raw_text=dia_f.text,
                out_of_range=not is_plausible(dia_spec, dia_f.text),
            ),
        ]

    def _extract_alt_from_previous_ast_row(
        self, previous_row: list[OcrFieldDTO]
    ) -> list[ParsedMetric]:
        found = self._find_label_in_row(previous_row)
        if found is None or found[0].code != "ast":
            return []
        numbers = [f for f in previous_row if _is_number(f.text) and not _is_reference(f.text)]
        if len(numbers) < 2:
            return []
        alt_f = numbers[1]
        alt_spec = METRIC_SPEC_BY_CODE["alt"]
        return [
            ParsedMetric(
                metric_code="alt",
                metric_name="ALT",
                value=alt_f.text.strip(),
                unit="U/L",
                confidence=alt_f.confidence,
                raw_text=alt_f.text,
                out_of_range=not is_plausible(alt_spec, alt_f.text),
            )
        ]

    def _extract_hw(self, right: list[OcrFieldDTO]) -> list[ParsedMetric]:
        numbers = [f for f in right if _is_number(f.text)]
        if not numbers:
            return []
        h_spec = METRIC_SPEC_BY_CODE["height"]
        w_spec = METRIC_SPEC_BY_CODE["weight"]
        result = [
            ParsedMetric(
                metric_code="height",
                metric_name="신장",
                value=numbers[0].text.strip(),
                unit="cm",
                confidence=numbers[0].confidence,
                raw_text=numbers[0].text,
                out_of_range=not is_plausible(h_spec, numbers[0].text),
            )
        ]
        if len(numbers) >= 2:
            result.append(
                ParsedMetric(
                    metric_code="weight",
                    metric_name="체중",
                    value=numbers[1].text.strip(),
                    unit="kg",
                    confidence=numbers[1].confidence,
                    raw_text=numbers[1].text,
                    out_of_range=not is_plausible(w_spec, numbers[1].text),
                )
            )
        return result

    def _extract_categorical(
        self, spec: MetricSpec, right: list[OcrFieldDTO]
    ) -> list[ParsedMetric]:
        for fld in right:
            for cat in spec.categories:
                if cat in fld.text:
                    return [
                        ParsedMetric(
                            metric_code=spec.code,
                            metric_name=spec.name,
                            value=cat,
                            unit=spec.unit,
                            confidence=fld.confidence,
                            raw_text=fld.text,
                        )
                    ]
        return []
