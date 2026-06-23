from fastapi import APIRouter

from app.core.response import not_implemented_response

router = APIRouter()


@router.get("/today")
async def get_today_missions():
    return not_implemented_response()


@router.post("/{mission_id}/complete")
async def complete_mission(mission_id: int):
    return not_implemented_response()


@router.post("/{mission_id}/verify")
async def verify_mission(mission_id: int):
    return not_implemented_response()


@router.get("/calendar")
async def get_mission_calendar():
    return not_implemented_response()


@router.get("/statistics/weekly")
async def get_weekly_statistics():
    return not_implemented_response()


@router.post("/notifications/send")
async def send_mission_notification():
    return not_implemented_response()
