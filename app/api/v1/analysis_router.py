import json

from fastapi import APIRouter, Depends, Header, Request
from pydantic import ValidationError

from app.core.dependencies import get_current_user
from app.core.exceptions import BadRequestException
from app.core.response import success_response
from app.domains.analysis.dependencies import get_analysis_service
from app.domains.analysis.schemas import AnalysisCallbackRequest
from app.domains.analysis.service import AnalysisService
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.post(
    "/checkups/{record_id}",
    summary="[프론트 사용] 검진 기록 AI 분석 요청",
    description=(
        "VERIFIED 상태의 검진 기록에 대해 Phase 4 분석 job을 생성합니다. "
        "`ANALYSIS_CLIENT=stub` 환경에서는 즉시 완료 callback을 처리하고 기본 미션 1건을 자동 배정합니다. "
        "Http/OpenAI 클라이언트와 polling worker는 후속 구현 대상입니다. "
        "Authorization 헤더 필요."
    ),
)
async def request_analysis(
    record_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: AnalysisService = Depends(get_analysis_service),
):
    result = await service.create_analysis_job(record_id, current_user.id)
    return success_response(message="분석 요청이 접수되었습니다.", data=result.model_dump())


@router.get(
    "/jobs/{analysis_job_id}",
    summary="[프론트 사용] AI 분석 job 상태 조회",
    description=(
        "분석 job의 현재 상태, external_job_id, 시도 횟수, 에러 코드, 모델 버전을 조회합니다. "
        "Stub MVP에서는 분석 요청 직후 보통 COMPLETED 상태가 됩니다. "
        "Authorization 헤더 필요."
    ),
)
async def get_analysis_job(
    analysis_job_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: AnalysisService = Depends(get_analysis_service),
):
    result = service.get_job_status(analysis_job_id, current_user.id)
    return success_response(data=result.model_dump())


@router.get(
    "/jobs/{analysis_job_id}/result",
    summary="[프론트 사용] AI 분석 결과 조회",
    description=(
        "분석 job의 완료 결과를 조회합니다. summary와 mission_candidates를 반환합니다. "
        "COMPLETED 상태가 아니면 ANALYSIS_NOT_COMPLETED(409)를 반환합니다. "
        "Authorization 헤더 필요."
    ),
)
async def get_analysis_result(
    analysis_job_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: AnalysisService = Depends(get_analysis_service),
):
    result = service.get_job_result(analysis_job_id, current_user.id)
    return success_response(data=result.model_dump())


@router.post(
    "/callback",
    summary="[서버/내부] AI 분석 callback 수신",
    description=(
        "외부 AI 분석 서버가 호출하는 callback endpoint입니다. "
        "`X-Analysis-Signature`로 HMAC 서명을 검증하며, 중복 callback은 멱등 처리합니다. "
        "프론트 화면에서 직접 호출하지 않습니다."
    ),
)
async def analysis_callback(
    request: Request,
    x_analysis_signature: str | None = Header(default=None, alias="X-Analysis-Signature"),
    service: AnalysisService = Depends(get_analysis_service),
):
    raw_body = await request.body()
    service.verify_callback_signature(raw_body, x_analysis_signature)
    try:
        payload_dict = json.loads(raw_body)
        request_body = AnalysisCallbackRequest.model_validate(payload_dict)
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
        raise BadRequestException(
            message="callback payload 형식이 올바르지 않습니다.",
            error_code="INVALID_CALLBACK_PAYLOAD",
        ) from exc
    callback = AnalysisService.callback_from_request(request_body)
    service.handle_callback(callback)
    return success_response(message="분석 callback이 처리되었습니다.")
