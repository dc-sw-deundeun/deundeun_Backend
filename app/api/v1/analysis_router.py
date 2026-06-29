from fastapi import APIRouter

from app.core.response import not_implemented_response

router = APIRouter()


@router.post(
    "/checkups/{record_id}",
    summary="[프론트 작업 제외] 외부 분석 요청 placeholder",
    description="외부 AI 분석 서버 연동은 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def request_analysis(record_id: int):
    return not_implemented_response()


@router.get(
    "/jobs/{analysis_job_id}",
    summary="[프론트 작업 제외] 외부 분석 job 상태 placeholder",
    description="외부 AI 분석 서버 연동은 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def get_analysis_job(analysis_job_id: int):
    return not_implemented_response()


@router.get(
    "/jobs/{analysis_job_id}/result",
    summary="[프론트 작업 제외] 외부 분석 결과 placeholder",
    description="외부 AI 분석 서버 연동은 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def get_analysis_result(analysis_job_id: int):
    return not_implemented_response()


@router.post(
    "/callback",
    summary="[서버/내부] 외부 분석 callback placeholder",
    description=(
        "향후 외부 AI 분석 서버가 호출할 callback입니다. 프론트 화면에서 직접 호출하지 않습니다. "
        "현재는 NOT_IMPLEMENTED(501)를 반환합니다."
    ),
)
async def analysis_callback():
    return not_implemented_response()
