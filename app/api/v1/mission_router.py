from fastapi import APIRouter

from app.core.response import success_response

router = APIRouter()


@router.get("/today")
async def get_today_missions():
    return success_response(message="Not implemented"), 501


@router.post("/{mission_id}/complete")
async def complete_mission(mission_id: int):
    return success_response(message="Not implemented"), 501


@router.post("/{mission_id}/verify")
async def verify_mission(mission_id: int):
    return success_response(message="Not implemented"), 501


@router.get("/calendar")
async def get_mission_calendar():
    return success_response(message="Not implemented"), 501


@router.get("/statistics/weekly")
async def get_weekly_statistics():
    return success_response(message="Not implemented"), 501


@router.post("/notifications/send")
async def send_mission_notification():
    return success_response(message="Not implemented"), 501
