from datetime import datetime, timezone

from app.core.config import settings
from app.core.exceptions import (
    AuthException,
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.domains.analysis.models import (
    AnalysisJob,
    AnalysisMissionCandidate,
    CheckupAnalysisSummary,
)
from app.domains.analysis.repository import AnalysisRepository
from app.domains.analysis.schemas import (
    AnalysisJobCreateResponse,
    AnalysisJobStatusResponse,
    AnalysisResultResponse,
    AnalysisSummaryResponse,
    MissionCandidateResponse,
)
from app.domains.analysis.status import AnalysisStatus
from app.domains.mission.constants import DEFAULT_MISSION_TEMPLATE_CODE
from app.domains.mission.repository import MissionRepository, local_date_for_timezone
from app.domains.ocr.status import MetricSource, VerificationStatus
from app.domains.onboarding.repository import OnboardingRepository
from app.domains.record.models import CheckupMetricResult
from app.domains.record.repository import RecordRepository
from app.infrastructure.external_analysis.analysis_client import AnalysisClient
from app.infrastructure.external_analysis.analysis_dto import (
    AnalysisCallbackDTO,
    AnalysisMetricDTO,
    AnalysisRequestDTO,
    AnalysisSummaryDTO,
    MissionCandidateDTO,
)
from app.infrastructure.external_analysis.signature import verify_analysis_signature


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AnalysisService:
    def __init__(
        self,
        analysis_repo: AnalysisRepository,
        record_repo: RecordRepository,
        mission_repo: MissionRepository,
        onboarding_repo: OnboardingRepository,
        analysis_client: AnalysisClient,
    ) -> None:
        self._analysis_repo = analysis_repo
        self._record_repo = record_repo
        self._mission_repo = mission_repo
        self._onboarding_repo = onboarding_repo
        self._analysis_client = analysis_client

    def ensure_verified(self, record_id: int) -> None:
        record = self._record_repo.get_record(record_id)
        if record is None:
            raise NotFoundException(message="검진 기록을 찾을 수 없습니다.")
        if record.verification_status != VerificationStatus.VERIFIED.value:
            raise ConflictException(
                message="검수가 완료되지 않은 기록은 분석할 수 없습니다.",
                error_code="NOT_VERIFIED",
            )

    async def create_analysis_job(self, record_id: int, user_id: int) -> AnalysisJobCreateResponse:
        record = self._record_repo.get_record_for_user(user_id, record_id)
        if record is None:
            raise NotFoundException(message="검진 기록을 찾을 수 없습니다.")
        self.ensure_verified(record_id)

        if self._analysis_repo.find_summary_by_record_id(record_id) is not None:
            raise ConflictException(
                message="이미 분석이 완료된 검진 기록입니다.",
                error_code="ANALYSIS_ALREADY_COMPLETED",
            )

        active_job = self._analysis_repo.find_latest_job_by_record_id(record_id)
        if active_job is not None and active_job.status in {
            AnalysisStatus.PENDING.value,
            AnalysisStatus.PROCESSING.value,
        }:
            raise ConflictException(
                message="이미 진행 중인 분석 작업이 있습니다.",
                error_code="ANALYSIS_IN_PROGRESS",
            )

        metrics = self._build_metric_dtos(record_id)
        job = AnalysisJob(
            record_id=record_id,
            user_id=user_id,
            external_job_id="pending",
            status=AnalysisStatus.PENDING.value,
            started_at=_now(),
        )
        self._analysis_repo.save_job(job)

        client_response = await self._analysis_client.request_analysis(
            AnalysisRequestDTO(record_id=record_id, user_id=user_id, metrics=metrics)
        )
        job.external_job_id = client_response.external_job_id
        self._analysis_repo.update_job_status(job, AnalysisStatus.PROCESSING.value)
        self._record_repo.set_analysis_status(record, AnalysisStatus.PROCESSING.value)

        if settings.analysis_client == "stub":
            callback = self._analysis_client.build_callback_payload(
                external_job_id=job.external_job_id,
                record_id=record_id,
                metrics=metrics,
            )
            self.handle_callback(callback)

        self._analysis_repo.commit()
        return AnalysisJobCreateResponse(
            job_id=job.id,
            record_id=record_id,
            status=job.status,
            external_job_id=job.external_job_id,
        )

    def get_job_status(self, job_id: int, user_id: int) -> AnalysisJobStatusResponse:
        job = self._get_owned_job(job_id, user_id)
        return AnalysisJobStatusResponse(
            job_id=job.id,
            record_id=job.record_id,
            status=job.status,
            external_job_id=job.external_job_id,
            attempt_count=job.attempt_count,
            error_code=job.error_code,
            model_version=job.model_version,
        )

    def get_job_result(self, job_id: int, user_id: int) -> AnalysisResultResponse:
        job = self._get_owned_job(job_id, user_id)
        if job.status != AnalysisStatus.COMPLETED.value:
            raise ConflictException(
                message="분석이 아직 완료되지 않았습니다.",
                error_code="ANALYSIS_NOT_COMPLETED",
            )
        summary = self._analysis_repo.find_summary_by_record_id(job.record_id)
        if summary is None:
            raise NotFoundException(message="분석 결과를 찾을 수 없습니다.")
        return AnalysisResultResponse(
            job_id=job.id,
            record_id=job.record_id,
            status=job.status,
            summary=self._build_summary_response(summary),
        )

    def handle_callback(self, payload: AnalysisCallbackDTO) -> None:
        job = self._analysis_repo.find_job_by_external_id(payload.external_job_id)
        if job is None:
            raise NotFoundException(message="분석 작업을 찾을 수 없습니다.")

        if job.status == AnalysisStatus.COMPLETED.value:
            return

        record = self._record_repo.get_record(job.record_id)
        if record is None:
            raise NotFoundException(message="검진 기록을 찾을 수 없습니다.")

        if payload.status == AnalysisStatus.FAILED.value:
            self._analysis_repo.update_job_status(
                job,
                AnalysisStatus.FAILED.value,
                error_code="ANALYSIS_FAILED",
                raw_result=payload.model_dump(),
                finished=True,
            )
            self._record_repo.set_analysis_status(record, AnalysisStatus.FAILED.value)
            self._analysis_repo.commit()
            return

        if payload.status != AnalysisStatus.COMPLETED.value:
            raise BadRequestException(
                message="지원하지 않는 분석 상태입니다.",
                error_code="INVALID_ANALYSIS_STATUS",
            )

        if payload.summary is None:
            raise BadRequestException(
                message="분석 요약이 포함되어야 합니다.",
                error_code="SUMMARY_REQUIRED",
            )

        existing_summary = self._analysis_repo.find_summary_by_record_id(job.record_id)
        if existing_summary is not None:
            self._analysis_repo.update_job_status(
                job,
                AnalysisStatus.COMPLETED.value,
                model_version=payload.model_version,
                raw_result=payload.model_dump(),
                finished=True,
            )
            self._analysis_repo.commit()
            return

        summary = CheckupAnalysisSummary(
            record_id=job.record_id,
            job_id=job.id,
            summary_text=payload.summary.summary_text,
            risk_level=payload.summary.risk_level,
            positive_points=payload.summary.positive_points,
            caution_points=payload.summary.caution_points,
            recommendations=payload.summary.recommendations,
            avoidances=payload.summary.avoidances,
            model_version=payload.model_version,
        )
        self._analysis_repo.save_summary(summary)

        if payload.metrics:
            self._upsert_analysis_metrics(job.record_id, payload.metrics)

        for candidate in payload.mission_candidates:
            self._save_mission_candidate(summary.id, candidate)

        self._analysis_repo.update_job_status(
            job,
            AnalysisStatus.COMPLETED.value,
            model_version=payload.model_version,
            raw_result=payload.model_dump(),
            finished=True,
        )
        self._record_repo.set_analysis_status(record, AnalysisStatus.COMPLETED.value)
        self.assign_default_mission(user_id=job.user_id, source_record_id=job.record_id)
        self._analysis_repo.commit()

    def verify_callback_signature(self, raw_body: bytes, signature: str | None) -> None:
        secret = settings.analysis_callback_secret
        if not secret:
            raise AuthException(
                message="callback secret이 설정되지 않았습니다.",
                error_code="CALLBACK_SECRET_NOT_CONFIGURED",
            )
        if not verify_analysis_signature(raw_body.decode("utf-8"), secret, signature):
            raise ForbiddenException(
                message="callback 서명이 유효하지 않습니다.",
                error_code="INVALID_CALLBACK_SIGNATURE",
            )

    def assign_default_mission(self, *, user_id: int, source_record_id: int) -> None:
        template = self._mission_repo.find_default_template()
        if template is None:
            return

        user = self._onboarding_repo.get_user_by_id(user_id)
        timezone_name = user.timezone if user is not None else "Asia/Seoul"
        assigned_date = local_date_for_timezone(timezone_name)

        if self._mission_repo.find_user_mission_for_date(user_id, template.id, assigned_date):
            return

        self._mission_repo.create_user_mission(
            user_id=user_id,
            template=template,
            source_record_id=source_record_id,
            assigned_date=assigned_date,
        )

    def poll_pending_jobs(self) -> None:
        raise NotImplementedError

    def _get_owned_job(self, job_id: int, user_id: int) -> AnalysisJob:
        job = self._analysis_repo.find_job_by_id(job_id)
        if job is None:
            raise NotFoundException(message="분석 작업을 찾을 수 없습니다.")
        if job.user_id != user_id:
            raise ForbiddenException(message="분석 작업에 접근할 수 없습니다.")
        return job

    def _build_metric_dtos(self, record_id: int) -> list[AnalysisMetricDTO]:
        metrics = self._record_repo.list_metrics(record_id)
        return [
            AnalysisMetricDTO(
                metric_code=metric.metric_code,
                metric_name=metric.metric_name,
                value=metric.value or "",
                unit=metric.unit,
                status=metric.status,
                interpretation=metric.interpretation,
                confidence=metric.confidence,
            )
            for metric in metrics
        ]

    def _upsert_analysis_metrics(self, record_id: int, metrics: list[AnalysisMetricDTO]) -> None:
        rows = [
            CheckupMetricResult(
                record_id=record_id,
                metric_code=item.metric_code,
                metric_name=item.metric_name,
                value=item.value,
                unit=item.unit,
                status=item.status,
                interpretation=item.interpretation,
                source=MetricSource.ANALYSIS.value,
                confidence=item.confidence,
            )
            for item in metrics
        ]
        self._record_repo.upsert_analysis_metrics(record_id, rows)

    def _save_mission_candidate(self, summary_id: int, candidate: MissionCandidateDTO) -> None:
        template = None
        if candidate.template_code:
            template = self._mission_repo.find_template_by_code(candidate.template_code)
            if template is None:
                return

        self._analysis_repo.save_mission_candidate(
            AnalysisMissionCandidate(
                summary_id=summary_id,
                candidate_type="TEMPLATE" if template else "AI_GENERATED",
                template_code=candidate.template_code,
                priority=candidate.priority,
                reason_code=candidate.reason_code,
            )
        )

    def _build_summary_response(self, summary: CheckupAnalysisSummary) -> AnalysisSummaryResponse:
        candidates = self._analysis_repo.list_mission_candidates(summary.id)
        return AnalysisSummaryResponse(
            record_id=summary.record_id,
            summary_text=summary.summary_text,
            risk_level=summary.risk_level,
            positive_points=summary.positive_points or [],
            caution_points=summary.caution_points or [],
            recommendations=summary.recommendations or [],
            avoidances=summary.avoidances or [],
            model_version=summary.model_version,
            mission_candidates=[
                MissionCandidateResponse(
                    template_code=candidate.template_code,
                    priority=candidate.priority,
                    reason_code=candidate.reason_code,
                    title=candidate.title,
                    description=candidate.description,
                )
                for candidate in candidates
            ],
        )

    @classmethod
    def callback_from_request(cls, body: dict) -> AnalysisCallbackDTO:
        summary_data = body.get("summary")
        summary = None
        if summary_data is not None:
            summary = AnalysisSummaryDTO(
                risk_level=summary_data.get("overall_status")
                or summary_data.get("risk_level")
                or "UNKNOWN",
                summary_text=summary_data.get("description")
                or summary_data.get("summary_text")
                or summary_data.get("title")
                or "",
                positive_points=summary_data.get("positive_points") or [],
                caution_points=summary_data.get("caution_points") or [],
                recommendations=summary_data.get("recommendations") or [],
                avoidances=summary_data.get("avoidances") or [],
            )

        metrics = None
        if body.get("metrics"):
            metrics = [
                AnalysisMetricDTO(
                    metric_code=item.get("code") or item.get("metric_code") or "",
                    metric_name=item.get("display_name") or item.get("metric_name") or "",
                    value=str(item.get("value", "")),
                    unit=item.get("unit"),
                    status=item.get("status"),
                    confidence=item.get("confidence"),
                )
                for item in body["metrics"]
            ]

        mission_candidates = [
            MissionCandidateDTO(
                template_code=item.get("template_code") or DEFAULT_MISSION_TEMPLATE_CODE,
                priority=item.get("priority", 1),
                reason_code=item.get("reason_code"),
            )
            for item in body.get("mission_candidates") or []
        ]

        external_job_id = body.get("external_job_id") or body.get("job_id") or ""
        return AnalysisCallbackDTO(
            external_job_id=external_job_id,
            record_id=int(body["record_id"]),
            status=body["status"],
            model_version=body.get("model_version"),
            summary=summary,
            metrics=metrics,
            mission_candidates=mission_candidates,
        )
