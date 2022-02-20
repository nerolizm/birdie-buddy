from fastapi import APIRouter

router = APIRouter()

@router.get("/now/", tags=["now"])
async def index():
    return [{"username": "Rick"}, {"username": "Morty"}]
