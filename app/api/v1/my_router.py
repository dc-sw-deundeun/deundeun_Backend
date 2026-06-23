from fastapi import APIRouter

from app.core.response import not_implemented_response

router = APIRouter()


@router.get("/profile")
async def get_profile():
    return not_implemented_response()


@router.patch("/password")
async def change_password():
    return not_implemented_response()


@router.get("/app-lock")
async def get_app_lock():
    return not_implemented_response()


@router.patch("/app-lock")
async def update_app_lock():
    return not_implemented_response()


@router.post("/support")
async def submit_support():
    return not_implemented_response()


@router.delete("/account")
async def delete_account():
    return not_implemented_response()
