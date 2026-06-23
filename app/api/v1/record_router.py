from fastapi import APIRouter

from app.core.response import not_implemented_response

router = APIRouter()


@router.post("/checkups/upload")
async def upload_checkup():
    return not_implemented_response()


@router.get("/checkups")
async def list_checkups():
    return not_implemented_response()


@router.get("/checkups/{record_id}")
async def get_checkup(record_id: int):
    return not_implemented_response()


@router.get("/checkups/{record_id}/metrics")
async def get_checkup_metrics(record_id: int):
    return not_implemented_response()


@router.delete("/checkups/{record_id}")
async def delete_checkup(record_id: int):
    return not_implemented_response()


@router.post("/meals")
async def create_meal_record():
    return not_implemented_response()


@router.get("/meals")
async def list_meal_records():
    return not_implemented_response()
