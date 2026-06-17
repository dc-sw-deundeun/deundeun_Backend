from fastapi import APIRouter

from app.core.response import success_response

router = APIRouter()


@router.post("/signup")
async def signup():
    return success_response(message="Not implemented"), 501


@router.post("/login")
async def login():
    return success_response(message="Not implemented"), 501


@router.post("/logout")
async def logout():
    return success_response(message="Not implemented"), 501


@router.post("/refresh")
async def refresh_token():
    return success_response(message="Not implemented"), 501


@router.post("/email/verify/request")
async def request_email_verification():
    return success_response(message="Not implemented"), 501


@router.post("/email/verify/confirm")
async def confirm_email_verification():
    return success_response(message="Not implemented"), 501


@router.post("/password/reset/request")
async def request_password_reset():
    return success_response(message="Not implemented"), 501


@router.post("/password/reset/confirm")
async def confirm_password_reset():
    return success_response(message="Not implemented"), 501


@router.post("/policies/agree")
async def agree_policies():
    return success_response(message="Not implemented"), 501


@router.get("/me")
async def get_me():
    return success_response(message="Not implemented"), 501
