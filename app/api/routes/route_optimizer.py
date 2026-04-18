from fastapi import APIRouter

from app.models.schemas import (
    OptimizeRequest,
    OptimizeResponse,
    RouteWarning,
    SimulationDetail,
    UserProfile,
)
from app.services.route_simulation import simulate_route
from app.services.speed_predictor import predict_route_speed

router = APIRouter(prefix="/api/v1/route", tags=["route"])


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_route(request: OptimizeRequest) -> OptimizeResponse:
    profile = request.user_profile if request.user_profile is not None else UserProfile()

    all_details: list[SimulationDetail] = []
    all_warnings: list[RouteWarning] = []

    for route in request.route_candidates:
        corrected_speed = predict_route_speed(profile.avg_speed, route.waypoints)
        detail, warnings = simulate_route(route, corrected_speed)
        all_details.append(detail)
        all_warnings.extend(warnings)

    optimal = min(all_details, key=lambda d: d.total_time_seconds)

    return OptimizeResponse(
        optimal_route_id=optimal.route_id,
        estimated_total_time_seconds=optimal.total_time_seconds,
        estimated_wait_time_seconds=optimal.wait_time_seconds,
        simulation_details=all_details,
        warnings=all_warnings,
    )
