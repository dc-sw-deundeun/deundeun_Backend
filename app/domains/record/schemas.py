from pydantic import BaseModel


class UploadCheckupRequest(BaseModel):
    # source_type: str
    # measured_at: str | None
    pass


class CheckupResponse(BaseModel):
    # id: int
    # user_id: int
    # source_type: str
    # file_url: str
    # analysis_status: str
    pass


class CheckupMetricResponse(BaseModel):
    # metric_code: str
    # metric_name: str
    # value: float
    # unit: str
    # status: str
    pass


class CreateMealRecordRequest(BaseModel):
    pass
