from fastapi import APIRouter

from app.core.response import not_implemented_response

router = APIRouter()


@router.post("/checkups/{record_id}")
async def request_analysis(record_id: int):
    return not_implemented_response()


@router.get("/jobs/{analysis_job_id}")
async def get_analysis_job(analysis_job_id: int):
    return not_implemented_response()


@router.get("/jobs/{analysis_job_id}/result")
async def get_analysis_result(analysis_job_id: int):
    return not_implemented_response()


@router.post("/callback")
async def analysis_callback():
    return not_implemented_response()
