# Pacer AI Server

보행자 네비게이션 앱 **Pacer**의 AI 연산 서버입니다.
서울시 C-ITS 신호 잔여시간 데이터와 사용자 걷기속도 프로필을 결합해 신호 대기시간이 최소인 최적 경로를 선택하고, 사용할수록 개인화되는 속도 프로필을 관리합니다.

## 기술 스택

| 항목 | 내용 |
|------|------|
| Language | Python 3.11 |
| Framework | FastAPI |
| 스키마 검증 | Pydantic v2 |
| 클러스터링 | scikit-learn (k-means) |
| 서버 | uvicorn |
| 테스트 | pytest |

## 아키텍처 개요

```
Spring Boot ──→ POST /api/v1/route/optimize ──→ Pacer AI
               (경로 후보 3개 + 신호 데이터 +        │
                user_profile)                    │ 최적 경로 선택
                                                 ↓
Spring Boot ←── optimal_route_id + 시뮬레이션 결과 + updated_profile
```

- **Stateless**: DB 직접 접근 없음. 모든 영속성은 Spring Boot가 담당.
- Spring Boot가 요청에 `user_profile`을 포함해 전달하고, FastAPI는 계산 후 `updated_profile`을 응답에 담아 반환.
- C-ITS 신호 데이터가 없는 횡단보도는 30초 fallback 처리.

## 시작하기

### 요구사항

- Python 3.11+

### 설치 및 실행

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

서버가 `http://localhost:8000` 에서 실행됩니다.

| URL | 설명 |
|-----|------|
| `http://localhost:8000/health` | 서버 상태 확인 |
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/redoc` | ReDoc |

### Docker

```bash
docker-compose up --build
```

## API 엔드포인트

### `POST /api/v1/route/optimize`

경로 후보들을 받아 신호 대기시간 시뮬레이션 후 최적 경로를 반환합니다.

**요청**
```json
{
  "user_id": "uuid",
  "user_profile": { "avg_speed": 1.4, "speed_std": 0.2, "trip_count": 12 },
  "route_candidates": [
    {
      "route_id": "route-a",
      "waypoints": [{ "lat": 37.5, "lng": 127.0, "elevation_m": 10.0 }],
      "crosswalks": [
        {
          "crosswalk_id": "cw-001",
          "distance_from_start": 150.0,
          "signal": { "phase": "green", "remaining_seconds": 23, "cycle_seconds": 60 }
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
  "optimal_route_id": "route-a",
  "estimated_total_time_seconds": 412,
  "estimated_wait_time_seconds": 0,
  "simulation_details": [...],
  "warnings": []
}
```

---

### `POST /api/v1/profile/update`

실제 이동 데이터로 사용자 속도 프로필을 갱신합니다.

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

---

### `GET /health`

```json
{ "status": "ok" }
```

## 테스트

```bash
pytest                              # 전체 실행
pytest tests/ -v                    # verbose
pytest --cov=app tests/             # 커버리지 포함
```

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 서버 바인딩 주소 |
| `PORT` | `8000` | 서버 포트 |
| `LOG_LEVEL` | `info` | uvicorn 로그 레벨 |
| `ALLOWED_ORIGINS` | `*` | CORS (내부 서비스 간 통신) |

## 디렉토리 구조

```
pacer_ai/
├── app/
│   ├── api/routes/       # 엔드포인트 (route_optimizer, user_profile)
│   ├── models/schemas.py # Pydantic 요청/응답 스키마
│   ├── services/         # 비즈니스 로직 (route_simulation, speed_predictor)
│   └── main.py
├── tests/
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```
