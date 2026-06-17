from fastapi import APIRouter

from app.core.response import success_response

router = APIRouter()


@router.get("/status")
async def get_onboarding_status():
    return success_response(message="Not implemented"), 501


@router.post("/checkup")
async def submit_initial_checkup():
    return success_response(message="Not implemented"), 501


@router.post("/wearable")
async def connect_wearable():
    return success_response(message="Not implemented"), 501


@router.post("/complete")
async def complete_onboarding():
    return success_response(message="Not implemented"), 501
