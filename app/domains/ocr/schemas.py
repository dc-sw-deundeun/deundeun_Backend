from pydantic import BaseModel


class OcrJobResponse(BaseModel):
    job_id: int
    record_id: int
    status: str
    parsed_field_count: int | None = None
    error_message: str | None = None
