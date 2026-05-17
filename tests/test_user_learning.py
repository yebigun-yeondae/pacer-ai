import math
import pytest

from app.models.schemas import ProfileUpdateRequest, UserProfile
from app.services.user_learning import calculate_updated_profile


def make_request(avg_speed=1.4, speed_std=0.2, trip_count=10, actual_avg_speed=1.4):
    return ProfileUpdateRequest(
        current_profile=UserProfile(avg_speed=avg_speed, speed_std=speed_std, trip_count=trip_count),
        actual_avg_speed=actual_avg_speed,
        actual_duration_seconds=300.0,
    )


# --- 웜업 기간 ---

def test_warmup_no_avg_speed_change():
    req = make_request(trip_count=4, actual_avg_speed=2.0)
    res = calculate_updated_profile(req)
    assert res.updated is False
    assert res.skip_reason == "warmup_period"
    assert res.updated_profile.avg_speed == pytest.approx(1.4, abs=1e-6)


def test_warmup_trip_count_incremented():
    req = make_request(trip_count=3)
    res = calculate_updated_profile(req)
    assert res.updated_profile.trip_count == 4


def test_warmup_speed_std_unchanged():
    req = make_request(trip_count=0)
    res = calculate_updated_profile(req)
    assert res.updated_profile.speed_std == pytest.approx(0.2, abs=1e-6)


def test_warmup_boundary_trip_count_4():
    req = make_request(trip_count=4)
    res = calculate_updated_profile(req)
    assert res.updated is False
    assert res.skip_reason == "warmup_period"


# --- EMA 적용 ---

def test_ema_applied_at_trip_count_5():
    req = make_request(avg_speed=1.4, trip_count=5, actual_avg_speed=1.6)
    res = calculate_updated_profile(req)
    expected_avg = 0.8 * 1.4 + 0.2 * 1.6
    assert res.updated is True
    assert res.updated_profile.avg_speed == pytest.approx(expected_avg, abs=1e-6)


def test_ema_formula_verification():
    old_avg = 1.4
    actual = 1.2
    req = make_request(avg_speed=old_avg, trip_count=10, actual_avg_speed=actual)
    res = calculate_updated_profile(req)
    expected = 0.8 * old_avg + 0.2 * actual
    assert res.updated_profile.avg_speed == pytest.approx(expected, abs=1e-6)


def test_ema_speed_std_updated():
    old_avg, old_std, actual = 1.4, 0.2, 1.6
    req = make_request(avg_speed=old_avg, speed_std=old_std, trip_count=5, actual_avg_speed=actual)
    res = calculate_updated_profile(req)
    expected_std = math.sqrt(0.8 * old_std**2 + 0.2 * (actual - old_avg)**2)
    assert res.updated_profile.speed_std == pytest.approx(expected_std, abs=1e-6)


def test_ema_skip_reason_none():
    req = make_request(trip_count=5, actual_avg_speed=1.4)
    res = calculate_updated_profile(req)
    assert res.skip_reason is None


# --- trip_count 증가 ---

def test_trip_count_incremented_on_ema():
    req = make_request(trip_count=10)
    res = calculate_updated_profile(req)
    assert res.updated_profile.trip_count == 11


# --- 이상값 필터 ---

def test_outlier_too_slow():
    req = make_request(trip_count=10, actual_avg_speed=0.29)
    res = calculate_updated_profile(req)
    assert res.updated is False
    assert res.skip_reason == "actual_speed_out_of_range"


def test_outlier_too_fast():
    req = make_request(trip_count=10, actual_avg_speed=3.01)
    res = calculate_updated_profile(req)
    assert res.updated is False
    assert res.skip_reason == "actual_speed_out_of_range"


def test_outlier_profile_unchanged():
    req = make_request(avg_speed=1.4, speed_std=0.2, trip_count=10, actual_avg_speed=0.1)
    res = calculate_updated_profile(req)
    assert res.updated_profile.avg_speed == pytest.approx(1.4, abs=1e-6)
    assert res.updated_profile.speed_std == pytest.approx(0.2, abs=1e-6)
    assert res.updated_profile.trip_count == 10


# --- 경계값 ---

def test_boundary_min_speed_accepted():
    req = make_request(trip_count=10, actual_avg_speed=0.3)
    res = calculate_updated_profile(req)
    assert res.updated is True


def test_boundary_max_speed_accepted():
    req = make_request(trip_count=10, actual_avg_speed=3.0)
    res = calculate_updated_profile(req)
    assert res.updated is True


# --- 순수 함수 검증 (입력 객체 불변) ---

def test_input_not_mutated():
    profile = UserProfile(avg_speed=1.4, speed_std=0.2, trip_count=10)
    req = ProfileUpdateRequest(
        current_profile=profile,
        actual_avg_speed=1.6,
        actual_duration_seconds=300.0,
    )
    calculate_updated_profile(req)
    assert profile.avg_speed == pytest.approx(1.4, abs=1e-6)
    assert profile.trip_count == 10
