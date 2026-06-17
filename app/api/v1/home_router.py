from fastapi import APIRouter

from app.core.response import success_response

router = APIRouter()


@router.get("")
async def get_home():
    return success_response(message="Not implemented"), 501


@router.get("/summary")
async def get_home_summary():
    return success_response(message="Not implemented"), 501
