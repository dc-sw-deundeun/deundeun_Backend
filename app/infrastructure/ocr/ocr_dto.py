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
        xs = [v["x"] for v in vertices]
        ys = [v["y"] for v in vertices]
        return cls(
            text=text,
            confidence=confidence,
            x_min=min(xs),
            x_max=max(xs),
            y_center=(min(ys) + max(ys)) / 2,
        )


class OcrResultDTO(BaseModel):
    fields: list[OcrFieldDTO]
