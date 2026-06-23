from fastapi import APIRouter

from app.core.response import not_implemented_response

router = APIRouter()


@router.get("/status")
async def get_onboarding_status():
    return not_implemented_response()


@router.post("/checkup")
async def submit_initial_checkup():
    return not_implemented_response()


@router.post("/wearable")
async def connect_wearable():
    return not_implemented_response()


@router.post("/complete")
async def complete_onboarding():
    return not_implemented_response()
