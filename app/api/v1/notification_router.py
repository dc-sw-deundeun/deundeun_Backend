from fastapi import APIRouter

from app.core.response import not_implemented_response

router = APIRouter()


@router.get("")
async def list_notifications():
    return not_implemented_response()


@router.post("/test")
async def send_test_notification():
    return not_implemented_response()


@router.get("/settings")
async def get_notification_settings():
    return not_implemented_response()


@router.patch("/settings")
async def update_notification_settings():
    return not_implemented_response()
