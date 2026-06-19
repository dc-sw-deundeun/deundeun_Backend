from pydantic import BaseModel


class AnalysisJobResponse(BaseModel):
    # id: int
    # record_id: int
    # status: str
    # external_job_id: str | None
    pass


class AnalysisResultResponse(BaseModel):
    # job_id: int
    # status: str
    # summary: dict | None
    # metrics: list | None
    pass


class AnalysisCallbackRequest(BaseModel):
    # external_job_id: str
    # status: str
    # summary: dict | None
    # metrics: list | None
    pass
