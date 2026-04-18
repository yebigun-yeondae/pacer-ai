import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

OPTIMIZE_PAYLOAD = {
    "user_id": "test-user",
    "user_profile": {"avg_speed": 1.4, "speed_std": 0.2, "trip_count": 10},
    "route_candidates": [
        {
            "route_id": "route-a",
            "waypoints": [
                {"lat": 37.5665, "lng": 126.9780},
                {"lat": 37.5670, "lng": 126.9785},
            ],
            "crosswalks": [
                {
                    "crosswalk_id": "cw-1",
                    "distance_from_start": 150.0,
                    "signal": {"phase": "green", "remaining_seconds": 20, "cycle_seconds": 60},
                }
            ],
            "total_distance": 300.0,
        }
    ],
}


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_optimize_route_ok():
    res = client.post("/api/v1/route/optimize", json=OPTIMIZE_PAYLOAD)
    assert res.status_code == 200
    data = res.json()
    assert "optimal_route_id" in data
    assert data["optimal_route_id"] == "route-a"


def test_optimize_route_empty_candidates():
    payload = {**OPTIMIZE_PAYLOAD, "route_candidates": []}
    res = client.post("/api/v1/route/optimize", json=payload)
    assert res.status_code == 422


def test_optimize_route_no_user_profile():
    payload = {k: v for k, v in OPTIMIZE_PAYLOAD.items() if k != "user_profile"}
    res = client.post("/api/v1/route/optimize", json=payload)
    assert res.status_code == 200
    assert "optimal_route_id" in res.json()


def test_profile_update_ok():
    payload = {
        "current_profile": {"avg_speed": 1.4, "speed_std": 0.2, "trip_count": 10},
        "actual_avg_speed": 1.5,
        "actual_duration_seconds": 400,
    }
    res = client.post("/api/v1/user/profile/update", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["updated"] is True


def test_profile_update_warmup():
    payload = {
        "current_profile": {"avg_speed": 1.4, "speed_std": 0.2, "trip_count": 3},
        "actual_avg_speed": 1.5,
        "actual_duration_seconds": 400,
    }
    res = client.post("/api/v1/user/profile/update", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["updated"] is False


def test_profile_update_outlier_speed():
    payload = {
        "current_profile": {"avg_speed": 1.4, "speed_std": 0.2, "trip_count": 10},
        "actual_avg_speed": 5.0,
        "actual_duration_seconds": 400,
    }
    res = client.post("/api/v1/user/profile/update", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["updated"] is False
    assert data["skip_reason"] is not None
