from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.core.response import not_implemented_response
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.get("")
async def list_notifications(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.post("/test")
async def send_test_notification(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.get("/settings")
async def get_notification_settings(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.patch("/settings")
async def update_notification_settings(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()
