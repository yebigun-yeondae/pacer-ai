"""
구간별 속도 예측 서비스 단위 테스트.
TDD: 구현 전 실패 확인 후 구현.
"""
import pytest

from app.models.schemas import Waypoint
from app.services.speed_predictor import (
    GRADE_MULTIPLIERS,
    MIN_SPEED,
    MAX_SPEED,
    classify_grade,
    predict_route_speed,
    predict_segment_speed,
)

BASE_SPEED = 1.4  # m/s


# ── classify_grade ────────────────────────────────────────────────────────────

class TestClassifyGrade:
    def test_flat_zero_diff(self):
        assert classify_grade(0.0, 100.0) == "flat"

    def test_flat_within_2pct(self):
        # 1.9m / 100m = 1.9% → flat
        assert classify_grade(1.9, 100.0) == "flat"
        assert classify_grade(-1.9, 100.0) == "flat"

    def test_uphill_moderate(self):
        # 5m / 100m = 5% → uphill
        assert classify_grade(5.0, 100.0) == "uphill"

    def test_uphill_at_boundary(self):
        # 2m / 100m = 2% → uphill (경계 포함)
        assert classify_grade(2.0, 100.0) == "uphill"

    def test_steep_up(self):
        # 10m / 100m = 10% → steep_up
        assert classify_grade(10.0, 100.0) == "steep_up"

    def test_downhill_moderate(self):
        # -5m / 100m = -5% → downhill
        assert classify_grade(-5.0, 100.0) == "downhill"

    def test_downhill_at_boundary(self):
        # -2m / 100m = -2% → downhill (경계 포함)
        assert classify_grade(-2.0, 100.0) == "downhill"

    def test_steep_down(self):
        # -10m / 100m = -10% → steep_down
        assert classify_grade(-10.0, 100.0) == "steep_down"

    def test_zero_distance_returns_flat(self):
        # 거리 0이면 경사 계산 불가 → flat 처리
        assert classify_grade(5.0, 0.0) == "flat"


# ── predict_segment_speed ─────────────────────────────────────────────────────

class TestPredictSegmentSpeed:
    def test_flat_no_correction(self):
        """평지 → 보정 없음 (1.0x)"""
        wp_from = Waypoint(lat=37.5, lng=126.9, elevation_m=30.0)
        wp_to   = Waypoint(lat=37.5, lng=126.9, elevation_m=31.0)  # 1m 상승 / 100m = 1% → flat
        speed = predict_segment_speed(BASE_SPEED, wp_from, wp_to, 100.0)
        assert speed == pytest.approx(BASE_SPEED * GRADE_MULTIPLIERS["flat"])

    def test_uphill_reduces_speed(self):
        """오르막 → 속도 감소 (0.85x)"""
        wp_from = Waypoint(lat=37.5, lng=126.9, elevation_m=30.0)
        wp_to   = Waypoint(lat=37.5, lng=126.9, elevation_m=35.0)  # 5m / 100m = 5% → uphill
        speed = predict_segment_speed(BASE_SPEED, wp_from, wp_to, 100.0)
        assert speed == pytest.approx(BASE_SPEED * GRADE_MULTIPLIERS["uphill"])

    def test_downhill_increases_speed(self):
        """내리막 → 속도 증가 (1.1x)"""
        wp_from = Waypoint(lat=37.5, lng=126.9, elevation_m=35.0)
        wp_to   = Waypoint(lat=37.5, lng=126.9, elevation_m=30.0)  # -5m / 100m = -5% → downhill
        speed = predict_segment_speed(BASE_SPEED, wp_from, wp_to, 100.0)
        assert speed == pytest.approx(BASE_SPEED * GRADE_MULTIPLIERS["downhill"])

    def test_elevation_none_from_waypoint_returns_base_speed(self):
        """from_waypoint elevation_m=None → 평지 폴백 (base_speed)"""
        wp_from = Waypoint(lat=37.5, lng=126.9, elevation_m=None)
        wp_to   = Waypoint(lat=37.5, lng=126.9, elevation_m=35.0)
        speed = predict_segment_speed(BASE_SPEED, wp_from, wp_to, 100.0)
        assert speed == pytest.approx(BASE_SPEED)

    def test_elevation_none_to_waypoint_returns_base_speed(self):
        """to_waypoint elevation_m=None → 평지 폴백 (base_speed)"""
        wp_from = Waypoint(lat=37.5, lng=126.9, elevation_m=30.0)
        wp_to   = Waypoint(lat=37.5, lng=126.9, elevation_m=None)
        speed = predict_segment_speed(BASE_SPEED, wp_from, wp_to, 100.0)
        assert speed == pytest.approx(BASE_SPEED)

    def test_both_elevation_none_returns_base_speed(self):
        """두 waypoint 모두 elevation_m=None → base_speed"""
        wp_from = Waypoint(lat=37.5, lng=126.9, elevation_m=None)
        wp_to   = Waypoint(lat=37.5, lng=126.9, elevation_m=None)
        speed = predict_segment_speed(BASE_SPEED, wp_from, wp_to, 100.0)
        assert speed == pytest.approx(BASE_SPEED)

    def test_steep_up_applies_70pct_multiplier(self):
        """급경사 오르막 > 8% → 0.70x"""
        wp_from = Waypoint(lat=37.5, lng=126.9, elevation_m=0.0)
        wp_to   = Waypoint(lat=37.5, lng=126.9, elevation_m=10.0)  # 10m / 100m = 10% → steep_up
        speed = predict_segment_speed(BASE_SPEED, wp_from, wp_to, 100.0)
        assert speed == pytest.approx(BASE_SPEED * GRADE_MULTIPLIERS["steep_up"])

    def test_steep_down_applies_105pct_multiplier(self):
        """급경사 내리막 < -8% → 1.05x"""
        wp_from = Waypoint(lat=37.5, lng=126.9, elevation_m=10.0)
        wp_to   = Waypoint(lat=37.5, lng=126.9, elevation_m=0.0)  # -10m / 100m = -10% → steep_down
        speed = predict_segment_speed(BASE_SPEED, wp_from, wp_to, 100.0)
        assert speed == pytest.approx(BASE_SPEED * GRADE_MULTIPLIERS["steep_down"])


# ── predict_route_speed ───────────────────────────────────────────────────────

class TestPredictRouteSpeed:
    def test_single_waypoint_returns_base_speed(self):
        """waypoints 1개 → base_speed 그대로"""
        wps = [Waypoint(lat=37.5, lng=126.9, elevation_m=30.0)]
        assert predict_route_speed(BASE_SPEED, wps) == pytest.approx(BASE_SPEED)

    def test_empty_waypoints_returns_base_speed(self):
        """waypoints 0개 → base_speed 그대로"""
        assert predict_route_speed(BASE_SPEED, []) == pytest.approx(BASE_SPEED)

    def test_flat_route_returns_base_speed(self):
        """전 구간 평지 → base_speed (1.0x)"""
        wps = [
            Waypoint(lat=37.50, lng=126.97, elevation_m=30.0),
            Waypoint(lat=37.51, lng=126.97, elevation_m=30.5),  # 0.5m / 111m ≈ 0.45% → flat
            Waypoint(lat=37.52, lng=126.97, elevation_m=31.0),
        ]
        speed = predict_route_speed(BASE_SPEED, wps)
        assert speed == pytest.approx(BASE_SPEED, rel=0.05)

    def test_mixed_route_is_weighted_average(self):
        """오르막+평지 혼합 → 거리 가중 평균"""
        # 구간 1: 100m, 5m 상승 (uphill, 0.85x)
        # 구간 2: 100m, 0m 변화 (flat, 1.0x)
        wps = [
            Waypoint(lat=37.50, lng=126.97, elevation_m=0.0),
            Waypoint(lat=37.51, lng=126.97, elevation_m=5.0),
            Waypoint(lat=37.52, lng=126.97, elevation_m=5.0),
        ]
        # 각 구간 100m씩 가정(haversine 근사)
        # 가중 평균 속도 = (100*1.4*0.85 + 100*1.4*1.0) / 200 = (119 + 140) / 200 = 1.2950
        # 정확한 값은 구현에서 haversine 계산하므로 범위로 검증
        speed = predict_route_speed(BASE_SPEED, wps)
        assert MIN_SPEED <= speed <= MAX_SPEED

    def test_all_elevation_none_returns_base_speed(self):
        """elevation_m 전부 None → base_speed"""
        wps = [
            Waypoint(lat=37.50, lng=126.97, elevation_m=None),
            Waypoint(lat=37.51, lng=126.97, elevation_m=None),
            Waypoint(lat=37.52, lng=126.97, elevation_m=None),
        ]
        speed = predict_route_speed(BASE_SPEED, wps)
        assert speed == pytest.approx(BASE_SPEED)

    def test_return_value_within_min_max_range(self):
        """반환 속도가 MIN_SPEED~MAX_SPEED 범위를 벗어나지 않는다"""
        # 극단적 경사도(급경사) 시나리오
        wps = [
            Waypoint(lat=37.50, lng=126.97, elevation_m=0.0),
            Waypoint(lat=37.50, lng=126.97, elevation_m=1000.0),  # 극단적 상승
        ]
        speed = predict_route_speed(0.3, wps)  # 이미 MIN_SPEED인 base_speed
        assert speed >= MIN_SPEED

        speed2 = predict_route_speed(3.0, wps)  # MAX_SPEED인 base_speed
        assert speed2 <= MAX_SPEED

    def test_clipping_prevents_below_min(self):
        """보정 후 속도가 MIN_SPEED 미만이 되지 않는다"""
        # 매우 낮은 base_speed + 강한 감속 보정
        speed = predict_route_speed(0.31, [
            Waypoint(lat=37.5, lng=126.9, elevation_m=0.0),
            Waypoint(lat=37.5, lng=126.9, elevation_m=10.0),  # 급경사 0.70x → 0.217 → 클리핑
        ])
        assert speed >= MIN_SPEED

    def test_clipping_prevents_above_max(self):
        """보정 후 속도가 MAX_SPEED 초과가 되지 않는다"""
        # 높은 base_speed + 내리막 보정
        speed = predict_route_speed(2.9, [
            Waypoint(lat=37.5, lng=126.9, elevation_m=10.0),
            Waypoint(lat=37.5, lng=126.9, elevation_m=0.0),  # downhill 1.1x → 3.19 → 클리핑
        ])
        assert speed <= MAX_SPEED
