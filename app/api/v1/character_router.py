from fastapi import APIRouter

from app.core.response import not_implemented_response

router = APIRouter()


@router.get("/me")
async def get_my_character():
    return not_implemented_response()


@router.post("/me/experience")
async def add_experience():
    return not_implemented_response()


@router.patch("/me/stage")
async def update_stage():
    return not_implemented_response()
