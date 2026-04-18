from __future__ import annotations

import pickle
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from sklearn.cluster import KMeans

from app.models.schemas import UserProfile


def _make_dummy_model(cluster_centers: list[list[float]], profiles: list[dict]) -> dict:
    """테스트용 더미 k-means 모델 데이터를 생성한다."""
    import numpy as np
    kmeans = KMeans(n_clusters=len(cluster_centers), n_init=1, random_state=42)
    # fit 없이 수동으로 cluster_centers_ 설정
    kmeans.cluster_centers_ = np.array(cluster_centers)
    kmeans.n_clusters = len(cluster_centers)
    return {
        "kmeans": kmeans,
        "cluster_profiles": profiles,
    }


class TestFallbackWhenNoModel:
    def test_returns_default_profile_when_model_file_missing(self):
        from app.services import user_clustering

        with patch.object(user_clustering, "MODEL_PATH", Path("/nonexistent/path/model.pkl")):
            user_clustering._load_model.cache_clear()
            result = user_clustering.get_initial_profile([1.2, 1.3])
        user_clustering._load_model.cache_clear()

        assert isinstance(result, UserProfile)
        assert result.avg_speed == pytest.approx(1.4)

    def test_returns_default_profile_when_observed_speeds_empty(self):
        from app.services import user_clustering

        with patch.object(user_clustering, "MODEL_PATH", Path("/nonexistent/path/model.pkl")):
            user_clustering._load_model.cache_clear()
            result = user_clustering.get_initial_profile([])
        user_clustering._load_model.cache_clear()

        assert isinstance(result, UserProfile)
        assert result.avg_speed == pytest.approx(1.4)


class TestModelLoad:
    def test_loads_model_and_returns_cluster_profile(self, tmp_path: Path):
        from app.services import user_clustering

        profiles = [
            {"avg_speed": 1.2, "speed_std": 0.15},
            {"avg_speed": 1.4, "speed_std": 0.20},
            {"avg_speed": 1.7, "speed_std": 0.25},
        ]
        model_data = _make_dummy_model([[1.2], [1.4], [1.7]], profiles)
        model_file = tmp_path / "user_clusters.pkl"
        with open(model_file, "wb") as f:
            pickle.dump(model_data, f)

        with patch.object(user_clustering, "MODEL_PATH", model_file):
            user_clustering._load_model.cache_clear()
            result = user_clustering.get_initial_profile([1.4])
        user_clustering._load_model.cache_clear()

        assert isinstance(result, UserProfile)
        assert result.avg_speed in {1.2, 1.4, 1.7}

    def test_assigns_closest_cluster_slow_user(self, tmp_path: Path):
        from app.services import user_clustering

        profiles = [
            {"avg_speed": 1.1, "speed_std": 0.10},
            {"avg_speed": 1.4, "speed_std": 0.20},
            {"avg_speed": 1.8, "speed_std": 0.25},
        ]
        model_data = _make_dummy_model([[1.1], [1.4], [1.8]], profiles)
        model_file = tmp_path / "user_clusters.pkl"
        with open(model_file, "wb") as f:
            pickle.dump(model_data, f)

        with patch.object(user_clustering, "MODEL_PATH", model_file):
            user_clustering._load_model.cache_clear()
            result = user_clustering.get_initial_profile([1.05, 1.1, 1.15])
        user_clustering._load_model.cache_clear()

        assert result.avg_speed == pytest.approx(1.1)
        assert result.speed_std == pytest.approx(0.10)

    def test_assigns_closest_cluster_fast_user(self, tmp_path: Path):
        from app.services import user_clustering

        profiles = [
            {"avg_speed": 1.1, "speed_std": 0.10},
            {"avg_speed": 1.4, "speed_std": 0.20},
            {"avg_speed": 1.8, "speed_std": 0.25},
        ]
        model_data = _make_dummy_model([[1.1], [1.4], [1.8]], profiles)
        model_file = tmp_path / "user_clusters.pkl"
        with open(model_file, "wb") as f:
            pickle.dump(model_data, f)

        with patch.object(user_clustering, "MODEL_PATH", model_file):
            user_clustering._load_model.cache_clear()
            result = user_clustering.get_initial_profile([1.75, 1.8, 1.85])
        user_clustering._load_model.cache_clear()

        assert result.avg_speed == pytest.approx(1.8)
        assert result.speed_std == pytest.approx(0.25)

    def test_cluster_profile_fields_returned_correctly(self, tmp_path: Path):
        from app.services import user_clustering

        profiles = [
            {"avg_speed": 1.35, "speed_std": 0.18},
        ]
        model_data = _make_dummy_model([[1.35]], profiles)
        model_file = tmp_path / "user_clusters.pkl"
        with open(model_file, "wb") as f:
            pickle.dump(model_data, f)

        with patch.object(user_clustering, "MODEL_PATH", model_file):
            user_clustering._load_model.cache_clear()
            result = user_clustering.get_initial_profile([1.35])
        user_clustering._load_model.cache_clear()

        assert result.avg_speed == pytest.approx(1.35)
        assert result.speed_std == pytest.approx(0.18)
        assert result.trip_count == 0


class TestModelCache:
    def test_model_loaded_only_once(self, tmp_path: Path):
        from app.services import user_clustering

        profiles = [{"avg_speed": 1.4, "speed_std": 0.20}]
        model_data = _make_dummy_model([[1.4]], profiles)
        model_file = tmp_path / "user_clusters.pkl"
        with open(model_file, "wb") as f:
            pickle.dump(model_data, f)

        with patch.object(user_clustering, "MODEL_PATH", model_file):
            user_clustering._load_model.cache_clear()
            with patch("builtins.open", wraps=open) as mock_open:
                user_clustering.get_initial_profile([1.4])
                user_clustering.get_initial_profile([1.4])
                # lru_cache로 인해 open은 한 번만 호출되어야 함
                pkl_opens = [
                    c for c in mock_open.call_args_list
                    if str(model_file) in str(c)
                ]
                assert len(pkl_opens) <= 1
        user_clustering._load_model.cache_clear()
