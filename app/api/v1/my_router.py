from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.core.response import not_implemented_response
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.get("/profile")
async def get_profile(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.patch("/password")
async def change_password(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.get("/app-lock")
async def get_app_lock(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.patch("/app-lock")
async def update_app_lock(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.post("/support")
async def submit_support(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.delete("/account")
async def delete_account(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()
