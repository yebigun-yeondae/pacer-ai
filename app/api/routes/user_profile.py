from fastapi import APIRouter

from app.models.schemas import ProfileUpdateRequest, ProfileUpdateResponse
from app.services.user_learning import calculate_updated_profile

router = APIRouter(prefix="/api/v1/user", tags=["user"])


@router.post("/profile/update", response_model=ProfileUpdateResponse)
async def update_profile(request: ProfileUpdateRequest) -> ProfileUpdateResponse:
    return calculate_updated_profile(request)
