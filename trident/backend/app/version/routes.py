from fastapi import APIRouter

router = APIRouter(tags=["version"])

SKELETON_VERSION = "0.1.0-skeleton"


@router.get("/version")
def version() -> dict[str, str]:
    return {"version": SKELETON_VERSION, "service": "trident-api"}
