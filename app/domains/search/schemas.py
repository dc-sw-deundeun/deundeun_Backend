from pydantic import BaseModel, Field


class DiseaseResult(BaseModel):
    name: str
    description: str
    symptoms: list[str] = Field(default_factory=list)


class DiseaseSearchResponse(BaseModel):
    results: list[DiseaseResult] = Field(default_factory=list)
