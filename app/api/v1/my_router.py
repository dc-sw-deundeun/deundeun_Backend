from fastapi import APIRouter

from app.core.response import success_response

router = APIRouter()


@router.get("/profile")
async def get_profile():
    return success_response(message="Not implemented"), 501


@router.patch("/password")
async def change_password():
    return success_response(message="Not implemented"), 501


@router.get("/notification-settings")
async def get_notification_settings():
    return success_response(message="Not implemented"), 501


@router.patch("/notification-settings")
async def update_notification_settings():
    return success_response(message="Not implemented"), 501


@router.get("/app-lock")
async def get_app_lock():
    return success_response(message="Not implemented"), 501


@router.patch("/app-lock")
async def update_app_lock():
    return success_response(message="Not implemented"), 501


@router.post("/support")
async def submit_support():
    return success_response(message="Not implemented"), 501


@router.delete("/account")
async def delete_account():
    return success_response(message="Not implemented"), 501
