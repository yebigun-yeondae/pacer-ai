# 개발환경 세팅

## a-1. 개발 환경 요구사항

| 항목 | 내용 |
|------|------|
| Language | Python 3.11 |
| Framework | FastAPI |
| 스키마 검증 | Pydantic v2 |
| 클러스터링 | scikit-learn (k-means) |
| 서버 | uvicorn |
| 테스트 | pytest |

## b. 아키텍처 개요

```
Spring Boot ──→ POST /api/v1/route/optimize ──→ Pacer AI
               (경로 후보 목록 + 신호 데이터 +       │
                user_profile)                    │ 최적 경로 선택
                                                 ↓
Spring Boot ←── optimal_route_id + 시뮬레이션 결과 + warnings
```

- **Stateless**: DB 직접 접근 없음. 모든 영속성은 Spring Boot가 담당.
- Spring Boot가 요청에 `user_profile`을 포함해 전달하고, FastAPI는 최적 경로와 시뮬레이션 결과를 반환.
- 사용자 속도 프로필 갱신은 `POST /api/v1/user/profile/update`에서 별도로 처리하고, 응답에 `updated_profile`을 담아 반환.
- C-ITS 신호 데이터가 없는 횡단보도는 30초 fallback 처리.

## c. 시작하기

### c-1. 요구사항

- Python 3.11+

### c-2. 설치 및 실행

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

서버가 `http://localhost:8000` 에서 실행됨.

| URL | 설명 |
|-----|------|
| `http://localhost:8000/health` | 서버 상태 확인 |
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/redoc` | ReDoc |

### c-3. Docker

```bash
docker-compose up --build
```

## d. API 엔드포인트

### d-1. `POST /api/v1/route/optimize`

경로 후보들을 받아 신호 대기시간 시뮬레이션 후 최적 경로를 반환함.
`signal`은 `phase`, `remaining_seconds`, `cycle_seconds`가 모두 있을 때만 전달하고, 신호 데이터가 불완전하거나 없으면 `null`로 전달함.

**요청**

```json
{
  "user_id": "uuid",
  "user_profile": { "avg_speed": 1.4, "speed_std": 0.2, "trip_count": 12 },
  "route_candidates": [
    {
      "route_id": "route_001",
      "waypoints": [{ "lat": 37.5, "lng": 127.0, "elevation_m": 10.0 }],
      "crosswalks": [
        {
          "crosswalk_id": "9001",
          "intersection_id": 101,
          "distance_from_start": 150.0,
          "signal": { "phase": "green", "remaining_seconds": 23, "cycle_seconds": 60 }
        },
        {
          "crosswalk_id": "9002",
          "intersection_id": null,
          "distance_from_start": 240.0,
          "signal": null
        }
      ],
      "total_distance": 520.0
    }
  ]
}
```

**응답**

```json
{
  "optimal_route_id": "route_001",
  "estimated_total_time_seconds": 412,
  "estimated_wait_time_seconds": 0,
  "simulation_details": [...],
  "warnings": []
}
```

### d-2. `POST /api/v1/user/profile/update`

실제 이동 데이터로 사용자 속도 프로필을 갱신함.

**요청**

```json
{
  "current_profile": { "avg_speed": 1.4, "speed_std": 0.2, "trip_count": 12 },
  "actual_avg_speed": 1.55,
  "actual_duration_seconds": 380
}
```

**응답**

```json
{
  "updated": true,
  "updated_profile": { "avg_speed": 1.46, "speed_std": 0.19, "trip_count": 13 },
  "skip_reason": null
}
```

### d-3. `GET /health`

```json
{ "status": "ok" }
```

## e. 테스트

```bash
pytest                              # 전체 실행
pytest tests/ -v                    # verbose
pytest --cov=app tests/             # 커버리지 포함
```

## f. 환경변수

아래 값은 `.env.example`과 `app/core/config.py`에 정의되어 있음.
현재 `uvicorn app.main:app --reload` 실행 명령과 `Dockerfile`의 `uvicorn` 명령은 이 설정 객체를 직접 참조하지 않으므로, 실행 호스트나 포트를 바꾸려면 uvicorn 옵션 또는 Dockerfile 명령도 함께 조정해야 함.

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 서버 바인딩 주소 |
| `PORT` | `8000` | 서버 포트 |
| `LOG_LEVEL` | `info` | uvicorn 로그 레벨 |
