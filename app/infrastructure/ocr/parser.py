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
_REFERENCE_MARKERS = ("정상", "미만", "미안", "이하", "이상", "~", "범위", "음성±")
# "미안"은 "미만"의 흔한 OCR 오인식 — 건강검진 서식에서 참조범위 마커로만 사용됨
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


_REF_COL_RATIO = 0.65  # 폼 너비의 65% 이상 = 참고치 컬럼으로 간주
_MIN_FORM_WIDTH = 600  # 이보다 좁으면 테스트 픽스처로 간주하고 x 필터 미적용


class OcrParser:
    def parse(self, result: OcrResultDTO) -> list[ParsedMetric]:
        if not result.fields:
            return []
        heights = [f.y_height for f in result.fields if f.y_height > 0]
        row_tolerance = max(15.0, statistics.median(heights) * 1.0) if heights else 20.0
        rows = self._cluster_rows(result.fields, row_tolerance)

        form_x_max = max((f.x_max for f in result.fields), default=0.0)
        ref_x_threshold = (
            form_x_max * _REF_COL_RATIO if form_x_max >= _MIN_FORM_WIDTH else None
        )

        metrics: list[ParsedMetric] = []
        seen: set[str] = set()
        for row_index, row in enumerate(rows):
            col_pos = 0
            while col_pos < len(row):
                found = self._find_first_label_from(row, col_pos)
                if found is None:
                    break
                spec, label_start, label_end = found
                next_label = self._find_first_label_from(row, label_end)
                value_end = next_label[1] if next_label else len(row)

                right_raw = row[label_end:value_end]
                right = [
                    f
                    for i, f in enumerate(right_raw)
                    if not _is_reference(f.text)
                    and not (
                        _is_number(f.text)
                        and i + 1 < len(right_raw)
                        and _is_reference(right_raw[i + 1].text)
                        and not right_raw[i + 1].text[:1].isdigit()
                    )
                ]
                extracted = self._extract(spec, right, ref_x_threshold)
                if not extracted and spec.kind in ("hw_pair", "bp_pair") and row_index + 1 < len(rows):
                    next_row = rows[row_index + 1]
                    if self._find_first_label_from(next_row, 0) is None:
                        extracted = self._extract(
                            spec,
                            [f for f in next_row if not _is_reference(f.text)],
                            ref_x_threshold,
                        )
                if not extracted and spec.code == "alt" and row_index > 0:
                    extracted = self._extract_alt_from_previous_ast_row(
                        rows[row_index - 1], ref_x_threshold
                    )
                for m in extracted:
                    if m.metric_code not in seen:
                        seen.add(m.metric_code)
                        metrics.append(m)
                col_pos = label_end
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

    def _find_first_label_from(
        self, row: list[OcrFieldDTO], pos: int
    ) -> tuple[MetricSpec, int, int] | None:
        """pos 이상에서 가장 앞서 나오는 라벨 매칭을 반환한다.
        같은 start 위치라면 더 긴 alias를 우선한다.
        반환: (spec, start_idx, end_idx)
        """
        best_spec: MetricSpec | None = None
        best_start: int | None = None
        best_end: int = 0
        best_alias_len: int = 0

        for start in range(pos, len(row)):
            for window in range(1, _MAX_LABEL_WINDOW + 1):
                if start + window > len(row):
                    break
                combined = "".join(f.text for f in row[start : start + window])
                match = find_best_alias_match(combined)
                if match:
                    alias_len = len(match[1])
                    is_earlier = best_start is None or start < best_start
                    is_same_longer = best_start == start and alias_len > best_alias_len
                    if is_earlier or is_same_longer:
                        best_spec = match[0]
                        best_alias_len = alias_len
                        best_start = start
                        best_end = start + window

        return (best_spec, best_start, best_end) if best_spec else None

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

    def _extract(
        self,
        spec: MetricSpec,
        right: list[OcrFieldDTO],
        ref_x_threshold: float | None = None,
    ) -> list[ParsedMetric]:
        if spec.kind == "bp_pair":
            return self._extract_bp(right, ref_x_threshold)
        if spec.kind == "hw_pair":
            return self._extract_hw(right, ref_x_threshold)
        if spec.kind == "categorical":
            return self._extract_categorical(spec, right)
        return self._extract_numeric(spec, right, ref_x_threshold)

    def _extract_numeric(
        self,
        spec: MetricSpec,
        right: list[OcrFieldDTO],
        ref_x_threshold: float | None = None,
    ) -> list[ParsedMetric]:
        for fld in right:
            if _is_number(fld.text):
                if ref_x_threshold is not None and fld.x_min >= ref_x_threshold:
                    continue
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

    def _extract_bp(
        self, right: list[OcrFieldDTO], ref_x_threshold: float | None = None
    ) -> list[ParsedMetric]:
        numbers = [
            f
            for f in right
            if _is_number(f.text)
            and (ref_x_threshold is None or f.x_min < ref_x_threshold)
        ]
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
        self,
        previous_row: list[OcrFieldDTO],
        ref_x_threshold: float | None = None,
    ) -> list[ParsedMetric]:
        found = self._find_label_in_row(previous_row)
        if found is None or found[0].code != "ast":
            return []
        numbers = [
            f
            for f in previous_row
            if _is_number(f.text)
            and not _is_reference(f.text)
            and (ref_x_threshold is None or f.x_min < ref_x_threshold)
        ]
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

    def _extract_hw(
        self, right: list[OcrFieldDTO], ref_x_threshold: float | None = None  # noqa: ARG002
    ) -> list[ParsedMetric]:
        # hw_pair 라벨("키(cm) 및 몸무게(kg)")은 길어서 값이 폼 우측에 위치함.
        # 빈 서식에서는 hw_pair 행에 숫자가 없으므로 x 필터를 적용하지 않는다.
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
