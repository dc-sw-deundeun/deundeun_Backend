from pydantic import BaseModel


class DiseaseResult(BaseModel):
    name: str = ""
    description: str = ""
    symptoms: list[str] = []


class DiseaseSearchResponse(BaseModel):
    results: list[DiseaseResult]
