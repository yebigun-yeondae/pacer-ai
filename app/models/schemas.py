from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


class UserProfile(BaseModel):
    avg_speed: float = 1.4
    speed_std: float = 0.2
    trip_count: int = 0


class SignalInfo(BaseModel):
    phase: Literal["green", "red"]
    remaining_seconds: float
    cycle_seconds: float


class Waypoint(BaseModel):
    lat: float
    lng: float
    elevation_m: float | None = None


class CrosswalkInfo(BaseModel):
    crosswalk_id: str
    distance_from_start: float  # 카카오맵 경로 geometry 기반 경로 상 누적 거리(m)
    signal: SignalInfo | None = None  # None이면 신호 데이터 없음 → 30초 fallback


class RouteCandidate(BaseModel):
    route_id: str
    waypoints: list[Waypoint]
    crosswalks: list[CrosswalkInfo]
    total_distance: float

    @field_validator("crosswalks")
    @classmethod
    def crosswalks_can_be_empty(cls, v: list[CrosswalkInfo]) -> list[CrosswalkInfo]:
        return v


class OptimizeRequest(BaseModel):
    user_id: str
    user_profile: UserProfile | None = None
    route_candidates: list[RouteCandidate]

    @field_validator("route_candidates")
    @classmethod
    def at_least_one_route(cls, v: list[RouteCandidate]) -> list[RouteCandidate]:
        if len(v) == 0:
            raise ValueError("route_candidates must not be empty")
        return v


class CrosswalkResult(BaseModel):
    crosswalk_id: str
    eta_seconds: float
    signal_state_at_arrival: Literal["green", "red", "unknown"]
    wait_seconds: float
    has_cits_data: bool


class SimulationDetail(BaseModel):
    route_id: str
    total_time_seconds: float
    travel_time_seconds: float
    wait_time_seconds: float
    cits_coverage_rate: float
    crosswalk_results: list[CrosswalkResult]


class RouteWarning(BaseModel):
    crosswalk_id: str
    reason: str
    fallback_wait_seconds: float


class OptimizeResponse(BaseModel):
    optimal_route_id: str
    estimated_total_time_seconds: float
    estimated_wait_time_seconds: float
    simulation_details: list[SimulationDetail]
    warnings: list[RouteWarning]


class ProfileUpdateRequest(BaseModel):
    current_profile: UserProfile
    actual_avg_speed: float
    actual_duration_seconds: float


class ProfileUpdateResponse(BaseModel):
    updated: bool
    updated_profile: UserProfile
    skip_reason: str | None = None
