from fastapi import APIRouter

router = APIRouter(prefix="/preview", tags=["preview"])


@router.get("/ping")
def preview_ping() -> dict:
    return {"status": "ok"}
