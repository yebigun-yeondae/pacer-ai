"""
구간별 속도 예측 서비스.
데이터 없을 때는 규칙 기반 경사도 보정으로 동작하는 폴백 구현.

[향후 ML 교체 지점]
predict_segment_speed() 내부를 학습된 회귀 모델로 교체할 수 있다.
함수 시그니처는 변경하지 않는다.
"""
import math

from app.models.schemas import Waypoint

MIN_SPEED = 0.3  # m/s
MAX_SPEED = 3.0  # m/s

GRADE_MULTIPLIERS: dict[str, float] = {
    "flat":       1.00,
    "uphill":     0.85,
    "steep_up":   0.70,
    "downhill":   1.10,
    "steep_down": 1.05,
}


def _haversine_distance(wp1: Waypoint, wp2: Waypoint) -> float:
    """두 waypoint 간 수평 거리(m)를 반환한다."""
    R = 6_371_000.0
    lat1, lat2 = math.radians(wp1.lat), math.radians(wp2.lat)
    dlat = lat2 - lat1
    dlng = math.radians(wp2.lng - wp1.lng)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def classify_grade(elevation_diff_m: float, distance_m: float) -> str:
    """
    고도 차이와 수평 거리로 경사 유형을 분류한다.
    elevation_diff_m = 도착지 고도 - 출발지 고도
    distance_m = 0이면 flat 처리.
    """
    if distance_m <= 0:
        return "flat"

    grade_pct = (elevation_diff_m / distance_m) * 100.0

    if grade_pct > 8.0:
        return "steep_up"
    elif grade_pct >= 2.0:
        return "uphill"
    elif grade_pct <= -8.0:
        return "steep_down"
    elif grade_pct <= -2.0:
        return "downhill"
    else:
        return "flat"


def predict_segment_speed(
    base_speed: float,
    from_waypoint: Waypoint,
    to_waypoint: Waypoint,
    segment_distance_m: float,
) -> float:
    """
    두 waypoint 사이 구간의 예측 보행속도를 반환한다.
    elevation 데이터가 없으면 base_speed 그대로 반환 (평지 폴백).

    [향후 ML 교체 지점]
    데이터 누적 시 이 함수 내부를 학습된 회귀 모델 추론으로 교체 가능.
    인터페이스(시그니처)는 변경하지 않는다.
    """
    if from_waypoint.elevation_m is None or to_waypoint.elevation_m is None:
        return base_speed

    elevation_diff = to_waypoint.elevation_m - from_waypoint.elevation_m
    grade = classify_grade(elevation_diff, segment_distance_m)
    return base_speed * GRADE_MULTIPLIERS[grade]


def predict_route_speed(
    base_speed: float,
    waypoints: list[Waypoint],
) -> float:
    """
    경로 전체의 거리 가중 평균 보행속도를 반환한다.
    waypoints가 1개 이하이면 base_speed를 그대로 반환한다.
    반환값은 반드시 [MIN_SPEED, MAX_SPEED] 범위 내로 클리핑한다.
    """
    if len(waypoints) <= 1:
        return base_speed

    total_distance = 0.0
    weighted_speed_sum = 0.0

    for i in range(len(waypoints) - 1):
        wp_from = waypoints[i]
        wp_to = waypoints[i + 1]
        dist = _haversine_distance(wp_from, wp_to)
        seg_speed = predict_segment_speed(base_speed, wp_from, wp_to, dist)
        weighted_speed_sum += seg_speed * dist
        total_distance += dist

    if total_distance == 0.0:
        return base_speed

    avg_speed = weighted_speed_sum / total_distance
    return max(MIN_SPEED, min(MAX_SPEED, avg_speed))
