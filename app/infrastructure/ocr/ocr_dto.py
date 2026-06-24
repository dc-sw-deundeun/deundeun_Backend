from pydantic import BaseModel


class OcrFieldDTO(BaseModel):
    text: str
    confidence: float
    x_min: float
    x_max: float
    y_center: float

    @classmethod
    def from_vertices(
        cls, text: str, confidence: float, vertices: list[dict]
    ) -> "OcrFieldDTO":
        # Clova V2는 좌표가 0일 때 x/y 키를 생략할 수 있어 .get으로 방어한다.
        # vertices 자체가 비어 오는 경우(외부 응답 누락)에는 좌표를 0으로 둔다.
        xs = [v.get("x", 0) for v in vertices] or [0]
        ys = [v.get("y", 0) for v in vertices] or [0]
        return cls(
            text=text,
            confidence=confidence,
            x_min=min(xs),
            x_max=max(xs),
            y_center=(min(ys) + max(ys)) / 2,
        )


class OcrResultDTO(BaseModel):
    fields: list[OcrFieldDTO]
