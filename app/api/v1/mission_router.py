from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.core.response import not_implemented_response
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.get("/today")
async def get_today_missions(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.post("/{mission_id}/complete")
async def complete_mission(mission_id: int, current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.post("/{mission_id}/verify")
async def verify_mission(mission_id: int, current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.get("/calendar")
async def get_mission_calendar(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.get("/statistics/weekly")
async def get_weekly_statistics(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.post("/notifications/send")
async def send_mission_notification(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()
