from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.core.response import not_implemented_response
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.post("/checkups/upload")
async def upload_checkup(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.get("/checkups")
async def list_checkups(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.get("/checkups/{record_id}")
async def get_checkup(record_id: int, current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.get("/checkups/{record_id}/metrics")
async def get_checkup_metrics(
    record_id: int, current_user: CurrentUser = Depends(get_current_user)
):
    return not_implemented_response()


@router.delete("/checkups/{record_id}")
async def delete_checkup(record_id: int, current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.post("/meals")
async def create_meal_record(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.get("/meals")
async def list_meal_records(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()
