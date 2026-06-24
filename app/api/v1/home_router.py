from fastapi import APIRouter

from app.core.response import not_implemented_response

router = APIRouter()


@router.get("")
async def get_home():
    return not_implemented_response()


@router.get("/summary")
async def get_home_summary():
    return not_implemented_response()
