from typing import Protocol

from pydantic import BaseModel


class AnalysisRequestDTO(BaseModel):
    # record_id: int
    # user_id: int
    # file_url: str
    # source_type: str
    # requested_analysis: list[str]
    pass


class AnalysisJobResponseDTO(BaseModel):
    # external_job_id: str
    # status: str
    pass


class AnalysisStatusResponseDTO(BaseModel):
    # external_job_id: str
    # status: str
    pass


class AnalysisResultResponseDTO(BaseModel):
    # external_job_id: str
    # status: str
    # summary: dict | None
    # metrics: list | None
    pass


class AnalysisClient(Protocol):
    """외부 AI 분석 서버 호출 인터페이스입니다."""

    async def request_analysis(self, request: AnalysisRequestDTO) -> AnalysisJobResponseDTO: ...

    async def get_job_status(self, external_job_id: str) -> AnalysisStatusResponseDTO: ...

    async def get_job_result(self, external_job_id: str) -> AnalysisResultResponseDTO: ...


class StubAnalysisClient:
    """개발/테스트용 stub 구현입니다."""

    async def request_analysis(self, request: AnalysisRequestDTO) -> AnalysisJobResponseDTO:
        raise NotImplementedError

    async def get_job_status(self, external_job_id: str) -> AnalysisStatusResponseDTO:
        raise NotImplementedError

    async def get_job_result(self, external_job_id: str) -> AnalysisResultResponseDTO:
        raise NotImplementedError
