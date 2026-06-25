from app.infrastructure.ocr.ocr_dto import OcrFieldDTO, OcrResultDTO


def test_from_vertices_computes_bbox():
    field = OcrFieldDTO.from_vertices(
        text="공복혈당",
        confidence=0.97,
        vertices=[
            {"x": 10, "y": 100},
            {"x": 60, "y": 100},
            {"x": 60, "y": 130},
            {"x": 10, "y": 130},
        ],
    )
    assert field.text == "공복혈당"
    assert field.confidence == 0.97
    assert field.x_min == 10
    assert field.x_max == 60
    assert field.y_center == 115


def test_from_vertices_handles_empty_vertices():
    # vertices가 비어 와도 ValueError 없이 좌표 0으로 방어한다.
    field = OcrFieldDTO.from_vertices(text="x", confidence=0.5, vertices=[])
    assert field.x_min == 0
    assert field.x_max == 0
    assert field.y_center == 0


def test_result_holds_fields():
    result = OcrResultDTO(fields=[])
    assert result.fields == []
