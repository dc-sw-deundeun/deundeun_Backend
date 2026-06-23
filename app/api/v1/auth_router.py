from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.core.response import not_implemented_response, success_response
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.post("/signup")
async def signup():
    return not_implemented_response()


@router.post("/login")
async def login():
    return not_implemented_response()


@router.post("/logout")
async def logout():
    return not_implemented_response()


@router.post("/refresh")
async def refresh_token():
    return not_implemented_response()


@router.post("/email/verify/request")
async def request_email_verification():
    return not_implemented_response()


@router.post("/email/verify/confirm")
async def confirm_email_verification():
    return not_implemented_response()


@router.post("/password/reset/request")
async def request_password_reset():
    return not_implemented_response()


@router.post("/password/reset/confirm")
async def confirm_password_reset():
    return not_implemented_response()


@router.post("/policies/agree")
async def agree_policies():
    return not_implemented_response()


@router.get("/me")
async def get_me(current_user: CurrentUser = Depends(get_current_user)):
    return success_response(data={"user_id": current_user.id})
