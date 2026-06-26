import json
from pathlib import Path

import pytest

from app.infrastructure.ocr.ocr_dto import OcrFieldDTO, OcrResultDTO
from app.infrastructure.ocr.parser import OcrParser

_FIXTURE = Path(__file__).parent / "fixtures" / "clova_samsung2019_masked.json"

_EXPECTED = {
    "height": "163.3",
    "weight": "55.3",
    "bmi": "20.7",
    "waist": "68.0",
    "systolic_bp": "113",
    "diastolic_bp": "62",
    "hemoglobin": "12.3",
    "fasting_glucose": "85",
    "creatinine": "0.9",
    "egfr": "72",
    "ast": "18",
    "alt": "9",
    "gamma_gtp": "17",
}


def _load_fixture(path: Path) -> OcrResultDTO:
    body = json.loads(path.read_text(encoding="utf-8"))
    fields = []
    for image in body.get("images") or []:
        for raw in image.get("fields") or []:
            vertices = (raw.get("boundingPoly") or {}).get("vertices")
            if not vertices:
                continue
            fields.append(
                OcrFieldDTO.from_vertices(
                    text=raw.get("inferText", ""),
                    confidence=raw.get("inferConfidence", 0.0),
                    vertices=vertices,
                )
            )
    return OcrResultDTO(fields=fields)


def test_samsung2019_parser_regression():
    if not _FIXTURE.exists():
        pytest.fail(f"회귀 픽스처 없음: {_FIXTURE} — scripts/real_clova_test.py --save-json 로 생성하세요")

    result = _load_fixture(_FIXTURE)
    metrics = {m.metric_code: m for m in OcrParser().parse(result)}

    errors = []
    for code, expected_value in _EXPECTED.items():
        if code not in metrics:
            errors.append(f"MISSING  {code}")
        elif metrics[code].value != expected_value:
            errors.append(
                f"WRONG    {code}: got {metrics[code].value!r}, expected {expected_value!r}"
            )
    extra_codes = set(metrics.keys()) - set(_EXPECTED.keys())
    for code in sorted(extra_codes):
        errors.append(f"UNEXPECTED {code}: {metrics[code].value!r}")
    assert not errors, "파서 회귀 실패:\n" + "\n".join(errors)
