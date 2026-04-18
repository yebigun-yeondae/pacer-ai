"""
경로 시뮬레이션 서비스 단위 테스트.
TDD: 이 테스트를 먼저 작성하고, 구현 전 실패를 확인한다.
"""
import pytest

from app.models.schemas import (
    CrosswalkInfo,
    OptimizeRequest,
    RouteCandidate,
    SignalInfo,
    UserProfile,
    Waypoint,
)
from app.services.route_simulation import (
    SIGNAL_FALLBACK_WAIT_SECONDS,
    calculate_wait,
    find_optimal_route,
    simulate_route,
)


# ── calculate_wait 단위 테스트 ──────────────────────────────────────────────

class TestCalculateWait:
    def test_green_eta_before_remaining_no_wait(self):
        """녹색 신호 중 도착: ETA < remaining → 대기 0"""
        signal = SignalInfo(phase="green", remaining_seconds=30, cycle_seconds=60)
        assert calculate_wait(eta=10.0, signal=signal) == 0.0

    def test_green_eta_equals_remaining_no_wait(self):
        """ETA == remaining_seconds 경계값 → 대기 0"""
        signal = SignalInfo(phase="green", remaining_seconds=20, cycle_seconds=60)
        assert calculate_wait(eta=20.0, signal=signal) == 0.0

    def test_green_eta_after_remaining_wait(self):
        """녹색 종료 후 도착 → 적색 대기 발생"""
        # cycle=60, remaining_green=10, so red_duration ≈ 50
        # eta=20 → time_after_green_ends=10, pos_in_cycle=10 → 적색 중 → wait=50-10=40
        signal = SignalInfo(phase="green", remaining_seconds=10, cycle_seconds=60)
        wait = calculate_wait(eta=20.0, signal=signal)
        assert wait == pytest.approx(40.0)

    def test_red_eta_before_remaining_wait(self):
        """적색 신호 중 도착: ETA < remaining → wait = remaining - ETA"""
        signal = SignalInfo(phase="red", remaining_seconds=30, cycle_seconds=60)
        wait = calculate_wait(eta=10.0, signal=signal)
        assert wait == pytest.approx(20.0)

    def test_red_eta_after_remaining_no_wait(self):
        """적색 종료 후 도착 (녹색 중) → 대기 0"""
        # cycle=60, remaining_red=15, green_duration≈45
        # eta=20 → time_after_red_ends=5, pos_in_cycle=5 < green_duration=45 → 녹색 통과
        signal = SignalInfo(phase="red", remaining_seconds=15, cycle_seconds=60)
        wait = calculate_wait(eta=20.0, signal=signal)
        assert wait == 0.0

    def test_red_eta_after_remaining_next_red(self):
        """적색 종료 후 녹색 통과 후 다시 적색 구간 도착"""
        # cycle=60, remaining_red=10, green_duration≈50
        # eta=70 → time_after_red_ends=60, pos_in_cycle=60%60=0 → pos<green(50)? 0<50 yes → 녹색
        # eta=65 → time_after_red_ends=55, pos_in_cycle=55%60=55 → 55>=50 → wait=60-55=5
        signal = SignalInfo(phase="red", remaining_seconds=10, cycle_seconds=60)
        wait = calculate_wait(eta=65.0, signal=signal)
        assert wait == pytest.approx(5.0)

    def test_multi_cycle_green(self):
        """다중 사이클: ETA > cycle_seconds — 올바른 사이클 내 위치 계산"""
        # cycle=60, remaining_green=30
        # eta=100 → time_after_green_ends=70, pos_in_cycle=70%60=10
        # red_duration≈30, 10 < 30 → wait = 30 - 10 = 20
        signal = SignalInfo(phase="green", remaining_seconds=30, cycle_seconds=60)
        wait = calculate_wait(eta=100.0, signal=signal)
        assert wait == pytest.approx(20.0)

    def test_multi_cycle_red(self):
        """다중 사이클: ETA > cycle_seconds — 적색 기준 사이클 내 위치 계산"""
        # cycle=60, remaining_red=15, green_duration≈45
        # eta=200 → time_after_red_ends=185, pos_in_cycle=185%60=5
        # 5 < 45 → 녹색 통과 → wait=0
        signal = SignalInfo(phase="red", remaining_seconds=15, cycle_seconds=60)
        wait = calculate_wait(eta=200.0, signal=signal)
        assert wait == 0.0


# ── simulate_route 단위 테스트 ────────────────────────────────────────────

def _make_route(route_id: str, crosswalks: list[CrosswalkInfo], total_distance: float) -> RouteCandidate:
    return RouteCandidate(
        route_id=route_id,
        waypoints=[Waypoint(lat=37.5, lng=126.9)],
        crosswalks=crosswalks,
        total_distance=total_distance,
    )


class TestSimulateRoute:
    def test_no_crosswalks(self):
        """횡단보도 없음: 순수 이동시간만 계산"""
        route = _make_route("r1", [], total_distance=140.0)
        detail, warnings = simulate_route(route, avg_speed=1.4)
        assert detail.wait_time_seconds == 0.0
        assert detail.travel_time_seconds == pytest.approx(100.0)
        assert detail.total_time_seconds == pytest.approx(100.0)
        assert detail.cits_coverage_rate == 0.0
        assert warnings == []

    def test_green_pass_no_wait(self):
        """녹색 통과: 대기 없이 이동시간 = 전체시간"""
        cw = CrosswalkInfo(
            crosswalk_id="cw-1",
            distance_from_start=140.0,  # ETA = 140/1.4 = 100s
            signal=SignalInfo(phase="green", remaining_seconds=120, cycle_seconds=180),
        )
        route = _make_route("r1", [cw], total_distance=280.0)
        detail, warnings = simulate_route(route, avg_speed=1.4)
        assert detail.wait_time_seconds == 0.0
        assert detail.cits_coverage_rate == pytest.approx(1.0)
        assert warnings == []

    def test_red_wait_accumulated(self):
        """적색 대기 → 두 번째 횡단보도 ETA에 누적"""
        # cw1: distance=140, ETA=100s, red remaining=50 → wait=50-100? NO
        # ETA=100 > remaining=50 → time_after_red_ends=50, pos=50%60=50, green≈10, 50>=10 → wait=60-50=10
        cw1 = CrosswalkInfo(
            crosswalk_id="cw-1",
            distance_from_start=140.0,
            signal=SignalInfo(phase="red", remaining_seconds=50, cycle_seconds=60),
        )
        # cw2: distance=280, ETA_base=280/1.4=200s, cumulative=10 → ETA=210s
        cw2 = CrosswalkInfo(
            crosswalk_id="cw-2",
            distance_from_start=280.0,
            signal=SignalInfo(phase="green", remaining_seconds=300, cycle_seconds=360),
        )
        route = _make_route("r1", [cw1, cw2], total_distance=420.0)
        detail, warnings = simulate_route(route, avg_speed=1.4)

        cw1_result = next(r for r in detail.crosswalk_results if r.crosswalk_id == "cw-1")
        cw2_result = next(r for r in detail.crosswalk_results if r.crosswalk_id == "cw-2")

        assert cw1_result.wait_seconds > 0
        # cw2 ETA는 cw1 대기시간이 누적되어야 함
        assert cw2_result.eta_seconds == pytest.approx(280.0 / 1.4 + cw1_result.wait_seconds)

    def test_signal_none_fallback(self):
        """신호 데이터 없음: 30초 fallback + warnings 기록"""
        cw = CrosswalkInfo(
            crosswalk_id="cw-null",
            distance_from_start=100.0,
            signal=None,
        )
        route = _make_route("r1", [cw], total_distance=200.0)
        detail, warnings = simulate_route(route, avg_speed=1.4)

        assert detail.wait_time_seconds == SIGNAL_FALLBACK_WAIT_SECONDS
        assert len(warnings) == 1
        assert warnings[0].crosswalk_id == "cw-null"
        assert warnings[0].fallback_wait_seconds == SIGNAL_FALLBACK_WAIT_SECONDS
        assert warnings[0].reason == "no_cits_data"

    def test_cits_coverage_rate(self):
        """cits_coverage_rate = 신호 있는 횡단보도 / 전체"""
        cw_with = CrosswalkInfo(
            crosswalk_id="cw-a",
            distance_from_start=100.0,
            signal=SignalInfo(phase="green", remaining_seconds=60, cycle_seconds=90),
        )
        cw_none = CrosswalkInfo(crosswalk_id="cw-b", distance_from_start=200.0, signal=None)
        route = _make_route("r1", [cw_with, cw_none], total_distance=300.0)
        detail, _ = simulate_route(route, avg_speed=1.4)
        assert detail.cits_coverage_rate == pytest.approx(0.5)

    def test_crosswalks_sorted_by_distance(self):
        """crosswalks가 순서 없이 전달돼도 distance 오름차순으로 처리"""
        cw1 = CrosswalkInfo(
            crosswalk_id="cw-far",
            distance_from_start=280.0,
            signal=SignalInfo(phase="red", remaining_seconds=40, cycle_seconds=60),
        )
        cw2 = CrosswalkInfo(
            crosswalk_id="cw-near",
            distance_from_start=140.0,
            signal=SignalInfo(phase="green", remaining_seconds=300, cycle_seconds=360),
        )
        route = _make_route("r1", [cw1, cw2], total_distance=420.0)
        detail, _ = simulate_route(route, avg_speed=1.4)
        results = {r.crosswalk_id: r for r in detail.crosswalk_results}
        # cw-near(140m) ETA = 100s → 녹색통과(remaining=300) wait=0
        assert results["cw-near"].wait_seconds == 0.0
        # cw-far(280m) ETA_base=200s, cumulative=0 → ETA=200s
        assert results["cw-far"].eta_seconds == pytest.approx(200.0)


# ── find_optimal_route 통합 테스트 ────────────────────────────────────────

class TestFindOptimalRoute:
    def _make_request(self, routes: list[RouteCandidate], profile: UserProfile | None = None) -> OptimizeRequest:
        return OptimizeRequest(
            user_id="user-test",
            user_profile=profile,
            route_candidates=routes,
        )

    def test_selects_min_total_time(self):
        """세 후보 중 총 소요시간 최소 경로를 반환"""
        # route-a: 1400m, 신호 없음 → 1000s 이동 + 30s fallback
        # route-b: 700m, 녹색통과 → 500s 이동 + 0s 대기 (최소)
        # route-c: 2100m, 신호 없음 → 1500s 이동 + 30s fallback
        route_a = _make_route("route-a", [
            CrosswalkInfo(crosswalk_id="cw-a1", distance_from_start=700.0, signal=None)
        ], total_distance=1400.0)
        route_b = _make_route("route-b", [
            CrosswalkInfo(
                crosswalk_id="cw-b1",
                distance_from_start=350.0,
                signal=SignalInfo(phase="green", remaining_seconds=600, cycle_seconds=900),
            )
        ], total_distance=700.0)
        route_c = _make_route("route-c", [
            CrosswalkInfo(crosswalk_id="cw-c1", distance_from_start=1050.0, signal=None)
        ], total_distance=2100.0)

        request = self._make_request([route_a, route_b, route_c])
        response = find_optimal_route(request)
        assert response.optimal_route_id == "route-b"

    def test_default_profile_used_when_none(self):
        """user_profile=None이면 기본값(avg_speed=1.4) 사용"""
        route = _make_route("r1", [], total_distance=140.0)
        request = self._make_request([route], profile=None)
        response = find_optimal_route(request)
        # 140 / 1.4 = 100s
        assert response.estimated_total_time_seconds == pytest.approx(100.0)

    def test_response_contains_all_simulation_details(self):
        """응답에 모든 후보의 시뮬레이션 상세가 포함되어야 함"""
        routes = [
            _make_route("r1", [], total_distance=100.0),
            _make_route("r2", [], total_distance=200.0),
        ]
        request = self._make_request(routes)
        response = find_optimal_route(request)
        assert len(response.simulation_details) == 2

    def test_optimal_route_estimated_wait_matches_detail(self):
        """estimated_wait_time_seconds가 최적 경로 시뮬레이션 결과와 일치"""
        cw = CrosswalkInfo(
            crosswalk_id="cw-x",
            distance_from_start=50.0,
            signal=SignalInfo(phase="red", remaining_seconds=20, cycle_seconds=60),
        )
        route = _make_route("r1", [cw], total_distance=100.0)
        request = self._make_request([route])
        response = find_optimal_route(request)

        optimal_detail = next(
            d for d in response.simulation_details if d.route_id == response.optimal_route_id
        )
        assert response.estimated_wait_time_seconds == pytest.approx(optimal_detail.wait_time_seconds)
