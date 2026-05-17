from fastapi import APIRouter

from app.models.schemas import OptimizeRequest, OptimizeResponse
from app.services.route_simulation import find_optimal_route

router = APIRouter(prefix="/api/v1/route", tags=["route"])


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_route(request: OptimizeRequest) -> OptimizeResponse:
    return find_optimal_route(request)
