from fastapi import APIRouter

from app.core.response import success_response

router = APIRouter()


@router.get("")
async def list_notifications():
    return success_response(message="Not implemented"), 501


@router.post("/test")
async def send_test_notification():
    return success_response(message="Not implemented"), 501


@router.get("/settings")
async def get_notification_settings():
    return success_response(message="Not implemented"), 501


@router.patch("/settings")
async def update_notification_settings():
    return success_response(message="Not implemented"), 501
