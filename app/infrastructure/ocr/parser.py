import re

from pydantic import BaseModel

from app.infrastructure.ocr.metric_dictionary import MetricSpec, find_spec_by_label
from app.infrastructure.ocr.ocr_dto import OcrFieldDTO, OcrResultDTO

_NUMBER_RE = re.compile(r"^\d+(\.\d+)?$")
_REFERENCE_MARKERS = ("정상", "미만", "이하", "이상", "~", "범위", "음성±")


class ParsedMetric(BaseModel):
    metric_code: str
    metric_name: str
    value: str
    unit: str
    confidence: float
    raw_text: str


def _is_number(text: str) -> bool:
    return bool(_NUMBER_RE.match(text.strip()))


def _is_reference(text: str) -> bool:
    return any(marker in text for marker in _REFERENCE_MARKERS)


class OcrParser:
    def parse(
        self, result: OcrResultDTO, row_tolerance: float = 20.0
    ) -> list[ParsedMetric]:
        rows = self._cluster_rows(result.fields, row_tolerance)
        metrics: list[ParsedMetric] = []
        seen: set[str] = set()
        for row in rows:
            for idx, fld in enumerate(row):
                spec = find_spec_by_label(fld.text)
                if spec is None:
                    continue
                right = [f for f in row[idx + 1 :] if not _is_reference(f.text)]
                parsed = self._extract(spec, right)
                for m in parsed:
                    if m.metric_code in seen:
                        continue
                    seen.add(m.metric_code)
                    metrics.append(m)
                break  # 한 행은 하나의 라벨만 처리
        return metrics

    def _cluster_rows(
        self, fields: list[OcrFieldDTO], tolerance: float
    ) -> list[list[OcrFieldDTO]]:
        ordered = sorted(fields, key=lambda f: f.y_center)
        rows: list[list[OcrFieldDTO]] = []
        for fld in ordered:
            if rows and abs(fld.y_center - rows[-1][0].y_center) <= tolerance:
                rows[-1].append(fld)
            else:
                rows.append([fld])
        for row in rows:
            row.sort(key=lambda f: f.x_min)
        return rows

    def _extract(
        self, spec: MetricSpec, right: list[OcrFieldDTO]
    ) -> list[ParsedMetric]:
        if spec.kind == "bp_pair":
            return self._extract_bp(right)
        if spec.kind == "categorical":
            return self._extract_categorical(spec, right)
        return self._extract_numeric(spec, right)

    def _extract_numeric(
        self, spec: MetricSpec, right: list[OcrFieldDTO]
    ) -> list[ParsedMetric]:
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
                    )
                ]
        return []

    def _extract_bp(self, right: list[OcrFieldDTO]) -> list[ParsedMetric]:
        numbers = [f for f in right if _is_number(f.text)]
        if len(numbers) < 2:
            return []
        sys_f, dia_f = numbers[0], numbers[1]
        return [
            ParsedMetric(
                metric_code="systolic_bp", metric_name="수축기혈압",
                value=sys_f.text.strip(), unit="mmHg",
                confidence=sys_f.confidence, raw_text=sys_f.text,
            ),
            ParsedMetric(
                metric_code="diastolic_bp", metric_name="이완기혈압",
                value=dia_f.text.strip(), unit="mmHg",
                confidence=dia_f.confidence, raw_text=dia_f.text,
            ),
        ]

    def _extract_categorical(
        self, spec: MetricSpec, right: list[OcrFieldDTO]
    ) -> list[ParsedMetric]:
        for fld in right:
            for cat in spec.categories:
                if cat in fld.text:
                    return [
                        ParsedMetric(
                            metric_code=spec.code, metric_name=spec.name,
                            value=cat, unit=spec.unit,
                            confidence=fld.confidence, raw_text=fld.text,
                        )
                    ]
        return []
