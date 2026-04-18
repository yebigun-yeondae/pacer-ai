from __future__ import annotations

import pickle
from functools import lru_cache
from pathlib import Path

from app.models.schemas import UserProfile

MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "user_clusters.pkl"

# pkl 파일에 저장되는 구조:
# {
#   "kmeans": KMeans 인스턴스 (cluster_centers_ 보유),
#   "cluster_profiles": [
#       {"avg_speed": 1.2, "speed_std": 0.15},
#       {"avg_speed": 1.4, "speed_std": 0.20},
#       {"avg_speed": 1.7, "speed_std": 0.25},
#   ]
# }


@lru_cache(maxsize=1)
def _load_model() -> dict | None:
    """모델 파일을 로드해 캐시한다. 파일이 없거나 로드 실패 시 None 반환."""
    if not MODEL_PATH.exists():
        return None
    try:
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def get_initial_profile(observed_speeds: list[float]) -> UserProfile:
    """
    신규 사용자의 초기 관측 속도 목록을 받아 가장 유사한 클러스터의 프로필을 반환한다.
    - 모델이 없거나 observed_speeds가 비어 있으면 기본값(avg_speed=1.4) 반환
    - 모델 있으면: 평균 관측 속도로 가장 가까운 클러스터 중심 탐색 → 해당 클러스터 프로필 반환
    """
    if not observed_speeds:
        return UserProfile()

    model = _load_model()
    if model is None:
        return UserProfile()

    avg_observed = sum(observed_speeds) / len(observed_speeds)

    kmeans = model["kmeans"]
    centers = kmeans.cluster_centers_

    # 가장 가까운 클러스터 중심 탐색 (1-D 피처: 평균 속도)
    closest_idx = min(range(len(centers)), key=lambda i: abs(centers[i][0] - avg_observed))

    cluster_profiles: list[dict] = model["cluster_profiles"]
    profile_data = cluster_profiles[closest_idx]

    return UserProfile(
        avg_speed=profile_data["avg_speed"],
        speed_std=profile_data["speed_std"],
        trip_count=0,
    )
