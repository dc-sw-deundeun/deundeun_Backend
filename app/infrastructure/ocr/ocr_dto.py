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
        xs = [v.get("x", 0) for v in vertices]
        ys = [v.get("y", 0) for v in vertices]
        return cls(
            text=text,
            confidence=confidence,
            x_min=min(xs),
            x_max=max(xs),
            y_center=(min(ys) + max(ys)) / 2,
        )


class OcrResultDTO(BaseModel):
    fields: list[OcrFieldDTO]
