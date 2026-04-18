"""
경로 시뮬레이션 핵심 로직.
모든 함수는 순수 함수: 부작용 없음, 동일 입력 → 동일 출력.
"""
import math

from app.models.schemas import (
    CrosswalkResult,
    OptimizeRequest,
    OptimizeResponse,
    RouteCandidate,
    RouteWarning,
    SignalInfo,
    SimulationDetail,
    UserProfile,
)

SIGNAL_FALLBACK_WAIT_SECONDS = 30.0


def calculate_wait(eta: float, signal: SignalInfo) -> float:
    """
    횡단보도 도착 ETA(초)와 신호 정보로 대기시간(초)을 반환한다.
    다중 사이클(ETA > cycle_seconds)은 mod 연산으로 처리한다.

    [PENDING-1] C-ITS API의 green_duration/red_duration 별도 제공 여부 확인 후
    아래 red_duration/green_duration 근사 계산 라인을 실제 값으로 교체할 것.
    """
    if signal.phase == "green":
        if eta <= signal.remaining_seconds:
            return 0.0

        time_after_green_ends = eta - signal.remaining_seconds
        pos_in_cycle = time_after_green_ends % signal.cycle_seconds
        # [PENDING-1] 근사값: C-ITS가 red_duration을 별도 제공하면 해당 값으로 교체
        red_duration = signal.cycle_seconds - signal.remaining_seconds
        if pos_in_cycle < red_duration:
            return red_duration - pos_in_cycle
        return 0.0

    else:  # red
        if eta <= signal.remaining_seconds:
            return signal.remaining_seconds - eta

        time_after_red_ends = eta - signal.remaining_seconds
        pos_in_cycle = time_after_red_ends % signal.cycle_seconds
        # [PENDING-1] 근사값: C-ITS가 green_duration을 별도 제공하면 해당 값으로 교체
        green_duration = signal.cycle_seconds - signal.remaining_seconds
        if pos_in_cycle >= green_duration:
            return signal.cycle_seconds - pos_in_cycle
        return 0.0


def simulate_route(
    route: RouteCandidate,
    avg_speed: float,
) -> tuple[SimulationDetail, list[RouteWarning]]:
    """
    단일 경로를 시뮬레이션한다.
    crosswalks를 distance_from_start 오름차순으로 순회하며 누적 대기시간을 반영한다.
    signal=None이면 SIGNAL_FALLBACK_WAIT_SECONDS 적용 + warning 생성.
    """
    warnings: list[RouteWarning] = []
    crosswalk_results: list[CrosswalkResult] = []
    cumulative_wait = 0.0
    cits_count = 0

    sorted_crosswalks = sorted(route.crosswalks, key=lambda cw: cw.distance_from_start)

    for cw in sorted_crosswalks:
        eta = cw.distance_from_start / avg_speed + cumulative_wait

        if cw.signal is None:
            wait = SIGNAL_FALLBACK_WAIT_SECONDS
            warnings.append(RouteWarning(
                crosswalk_id=cw.crosswalk_id,
                reason="no_cits_data",
                fallback_wait_seconds=SIGNAL_FALLBACK_WAIT_SECONDS,
            ))
            signal_state: str = "unknown"
            has_cits_data = False
        else:
            wait = calculate_wait(eta, cw.signal)
            has_cits_data = True
            cits_count += 1
            signal_state = "green" if wait == 0.0 else "red"

        crosswalk_results.append(CrosswalkResult(
            crosswalk_id=cw.crosswalk_id,
            eta_seconds=round(eta, 6),
            signal_state_at_arrival=signal_state,
            wait_seconds=round(wait, 6),
            has_cits_data=has_cits_data,
        ))
        cumulative_wait += wait

    total_crosswalks = len(route.crosswalks)
    cits_coverage_rate = cits_count / total_crosswalks if total_crosswalks > 0 else 0.0

    travel_time = route.total_distance / avg_speed
    total_time = travel_time + cumulative_wait

    detail = SimulationDetail(
        route_id=route.route_id,
        total_time_seconds=round(total_time, 6),
        travel_time_seconds=round(travel_time, 6),
        wait_time_seconds=round(cumulative_wait, 6),
        cits_coverage_rate=round(cits_coverage_rate, 6),
        crosswalk_results=crosswalk_results,
    )
    return detail, warnings


def find_optimal_route(request: OptimizeRequest) -> OptimizeResponse:
    """
    모든 경로 후보를 시뮬레이션하고 total_time_seconds가 최소인 경로를 반환한다.
    user_profile이 None이면 UserProfile() 기본값(avg_speed=1.4)을 사용한다.
    """
    profile = request.user_profile if request.user_profile is not None else UserProfile()
    avg_speed = profile.avg_speed

    all_details: list[SimulationDetail] = []
    all_warnings: list[RouteWarning] = []

    for route in request.route_candidates:
        detail, warnings = simulate_route(route, avg_speed)
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
