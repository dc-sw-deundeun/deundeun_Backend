from fastapi import APIRouter

from app.core.response import success_response

router = APIRouter()


@router.post("/checkups/upload")
async def upload_checkup():
    return success_response(message="Not implemented"), 501


@router.get("/checkups")
async def list_checkups():
    return success_response(message="Not implemented"), 501


@router.get("/checkups/{record_id}")
async def get_checkup(record_id: int):
    return success_response(message="Not implemented"), 501


@router.get("/checkups/{record_id}/metrics")
async def get_checkup_metrics(record_id: int):
    return success_response(message="Not implemented"), 501


@router.delete("/checkups/{record_id}")
async def delete_checkup(record_id: int):
    return success_response(message="Not implemented"), 501


@router.post("/meals")
async def create_meal_record():
    return success_response(message="Not implemented"), 501


@router.get("/meals")
async def list_meal_records():
    return success_response(message="Not implemented"), 501
