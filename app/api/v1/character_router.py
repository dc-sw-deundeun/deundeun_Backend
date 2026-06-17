from fastapi import APIRouter

from app.core.response import success_response

router = APIRouter()


@router.get("/me")
async def get_my_character():
    return success_response(message="Not implemented"), 501


@router.post("/me/experience")
async def add_experience():
    return success_response(message="Not implemented"), 501


@router.patch("/me/stage")
async def update_stage():
    return success_response(message="Not implemented"), 501
