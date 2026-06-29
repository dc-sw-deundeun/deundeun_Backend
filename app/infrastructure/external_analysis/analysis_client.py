import uuid
from typing import Protocol

from app.domains.mission.constants import DEFAULT_MISSION_TEMPLATE_CODE
from app.infrastructure.external_analysis.analysis_dto import (
    AnalysisCallbackDTO,
    AnalysisJobResponseDTO,
    AnalysisMetricDTO,
    AnalysisRequestDTO,
    AnalysisResultResponseDTO,
    AnalysisStatusResponseDTO,
    AnalysisSummaryDTO,
    MissionCandidateDTO,
)


class AnalysisClient(Protocol):
    async def request_analysis(self, request: AnalysisRequestDTO) -> AnalysisJobResponseDTO: ...

    async def get_job_status(self, external_job_id: str) -> AnalysisStatusResponseDTO: ...

    async def get_job_result(self, external_job_id: str) -> AnalysisResultResponseDTO: ...

    def build_callback_payload(
        self,
        *,
        external_job_id: str,
        record_id: int,
        metrics: list[AnalysisMetricDTO],
    ) -> AnalysisCallbackDTO: ...


class StubAnalysisClient:
    """개발/테스트용 stub — deterministic fake 분석 결과를 반환합니다."""

    async def request_analysis(self, request: AnalysisRequestDTO) -> AnalysisJobResponseDTO:
        external_job_id = f"stub-{request.record_id}-{uuid.uuid4().hex[:8]}"
        return AnalysisJobResponseDTO(external_job_id=external_job_id, status="PROCESSING")

    async def get_job_status(self, external_job_id: str) -> AnalysisStatusResponseDTO:
        return AnalysisStatusResponseDTO(external_job_id=external_job_id, status="COMPLETED")

    async def get_job_result(self, external_job_id: str) -> AnalysisResultResponseDTO:
        callback = self.build_callback_payload(
            external_job_id=external_job_id,
            record_id=0,
            metrics=[],
        )
        return AnalysisResultResponseDTO(
            external_job_id=external_job_id,
            status="COMPLETED",
            summary=callback.summary,
            metrics=callback.metrics,
            mission_candidates=callback.mission_candidates,
        )

    def build_callback_payload(
        self,
        *,
        external_job_id: str,
        record_id: int,
        metrics: list[AnalysisMetricDTO],
    ) -> AnalysisCallbackDTO:
        caution_points = [
            metric.metric_name for metric in metrics if metric.status in {"CAUTION", "RISK"}
        ]
        risk_level = "NEEDS_MANAGEMENT" if caution_points else "GOOD"
        summary_text = (
            "검진 결과를 바탕으로 건강 관리가 필요해 보입니다."
            if caution_points
            else "전반적으로 양호한 검진 결과입니다."
        )
        return AnalysisCallbackDTO(
            external_job_id=external_job_id,
            record_id=record_id,
            status="COMPLETED",
            model_version="health-check-stub-v1",
            summary=AnalysisSummaryDTO(
                risk_level=risk_level,
                summary_text=summary_text,
                positive_points=["규칙적인 생활을 유지하고 있습니다."]
                if not caution_points
                else [],
                caution_points=caution_points,
                recommendations=["가벼운 유산소 운동을 권장합니다."],
                avoidances=["과도한 당분 섭취를 피해 주세요."],
            ),
            metrics=metrics,
            mission_candidates=[
                MissionCandidateDTO(
                    template_code=DEFAULT_MISSION_TEMPLATE_CODE,
                    priority=1,
                    reason_code="ANALYSIS_STUB",
                )
            ],
        )
