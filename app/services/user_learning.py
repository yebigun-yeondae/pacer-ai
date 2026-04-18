import math

from app.models.schemas import ProfileUpdateRequest, ProfileUpdateResponse, UserProfile

ALPHA = 0.2
WARMUP_TRIPS = 5
MIN_SPEED = 0.3
MAX_SPEED = 3.0


def calculate_updated_profile(request: ProfileUpdateRequest) -> ProfileUpdateResponse:
    profile = request.current_profile
    actual_speed = request.actual_avg_speed

    if actual_speed < MIN_SPEED or actual_speed > MAX_SPEED:
        return ProfileUpdateResponse(
            updated=False,
            updated_profile=UserProfile(
                avg_speed=profile.avg_speed,
                speed_std=profile.speed_std,
                trip_count=profile.trip_count,
            ),
            skip_reason="actual_speed_out_of_range",
        )

    if profile.trip_count < WARMUP_TRIPS:
        return ProfileUpdateResponse(
            updated=False,
            updated_profile=UserProfile(
                avg_speed=profile.avg_speed,
                speed_std=profile.speed_std,
                trip_count=profile.trip_count + 1,
            ),
            skip_reason="warmup_period",
        )

    new_avg = (1 - ALPHA) * profile.avg_speed + ALPHA * actual_speed
    new_std = math.sqrt((1 - ALPHA) * profile.speed_std**2 + ALPHA * (actual_speed - new_avg)**2)

    return ProfileUpdateResponse(
        updated=True,
        updated_profile=UserProfile(
            avg_speed=new_avg,
            speed_std=new_std,
            trip_count=profile.trip_count + 1,
        ),
        skip_reason=None,
    )
