# 🚪 API Gateway Service

통합 API Gateway로 모든 마이크로서비스에 대한 단일 진입점을 제공합니다.

## 🎯 주요 기능

- **단일 진입점**: 모든 API 요청을 포트 8000으로 통합
- **통합 문서**: Swagger UI에서 모든 서비스 API 문서 확인
- **서비스 프록시**: 요청을 적절한 마이크로서비스로 자동 라우팅
- **헬스 체크**: 모든 서비스 상태 실시간 모니터링
- **인증 통합**: 토큰 기반 인증 중앙 관리

## 📋 API 엔드포인트

### Gateway 관리
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ai` | GET | Gateway 정보 및 서비스 목록 |
| `/api/ai/health` | GET | 모든 서비스 헬스 체크 |
| `/api/ai/services` | GET | 활성 서비스 상태 조회 |

### 서비스 라우팅
Gateway는 다음 패턴에 따라 요청을 라우팅합니다:

| Path Pattern | Target Service | Description |
|--------------|----------------|-------------|
| `/api/ai/csv/*` | CSV Manager (8003) | CSV 파일 관리 |
| `/api/ai/classify/*` | Classifier (8001) | 거래 분류 |
| `/api/ai/data/*` | Analysis (8002) | 데이터 분석 |

## 🏗 아키텍처

```
         ┌─────────────────────────────────┐
         │         Clients                 │
         └──────────────┬──────────────────┘
                       │
                       ▼ :8000
         ┌─────────────────────────────────┐
         │      API Gateway Service        │
         │                                 │
         │  - Request Routing              │
         │  - Auth Validation              │
         │  - OpenAPI Aggregation          │
         │  - Health Monitoring            │
         └─────┬──────┬──────┬─────────────┘
               │      │      │
        :8003  │:8001 │:8002 │
               ▼      ▼      ▼
         ┌─────┐ ┌─────┐ ┌─────┐
         │ CSV │ │Class│ │Anal │
         └─────┘ └─────┘ └─────┘
```

## 📚 통합 API 문서

Gateway는 모든 서비스의 OpenAPI 스키마를 자동으로 병합하여 통합 문서를 제공합니다.

### 접속 URL
- **Swagger UI**: http://localhost:8000/api/ai/docs
- **ReDoc**: http://localhost:8000/api/ai/redoc
- **OpenAPI JSON**: http://localhost:8000/api/ai/openapi.json

### 문서 구조
```
Swagger UI
├── Gateway           # Gateway 관리 API
├── CSV Management    # 파일 업로드/관리
├── Expense Classifier # 거래 분류
└── Data Analysis     # 예측 분석
```

## 🔒 인증 시스템

Gateway는 중앙 집중식 인증을 제공합니다:

### 토큰 타입
- **Admin Token** (`X-Admin-Token`): 관리 기능 (업로드, 삭제, 분류)
- **User Token** (`X-User-Token`): 조회 기능

### 인증 예시
```bash
# Admin 권한 요청
curl -X POST "http://localhost:8000/api/ai/csv/upload" \
  -H "X-Admin-Token: admin-token" \
  -F "file=@data.csv"

# User 권한 요청
curl "http://localhost:8000/api/ai/csv/status?file_id=123" \
  -H "X-User-Token: user-token"
```

## 💡 사용 예시

### 1. 헬스 체크
```bash
curl http://localhost:8000/api/ai/health

# Response
{
  "gateway": "healthy",
  "services": {
    "csv-manager": {"status": "healthy"},
    "classifier": {"status": "healthy"},
    "analysis": {"status": "healthy"}
  }
}
```

### 2. CSV 파일 업로드 (Gateway 경유)
```bash
curl -X POST "http://localhost:8000/api/ai/csv/upload" \
  -H "X-Admin-Token: admin-token" \
  -F "file=@transactions.csv"
```

### 3. 거래 분류 (Gateway 경유)
```bash
# 단일 거래
curl "http://localhost:8000/api/ai/classify?merchant_name=스타벅스&amount=4800"

# 배치 분류
curl -X POST "http://localhost:8000/api/ai/classify/process?file_id=abc-123" \
  -H "X-Admin-Token: admin-token"
```

### 4. 데이터 분석 (Gateway 경유)
```bash
# 분석 시작
curl -X POST "http://localhost:8000/api/ai/data?file_id=abc-123"

# 결과 조회
curl "http://localhost:8000/api/ai/data/leak?file_id=abc-123"
```

## ⚙️ 환경 설정

### 필수 환경 변수 (.env)
```bash
# Service URLs (Docker 내부 네트워크)
CLASSIFIER_SERVICE_URL=http://classifier:8001
ANALYSIS_SERVICE_URL=http://analysis:8002
CSV_MANAGER_SERVICE_URL=http://csv-manager:8003

# Authentication
ADMIN_TOKEN=admin-token
USER_TOKEN=user-token

# Logging
LOG_LEVEL=INFO
```

## 🔧 개발 가이드

### OpenAPI 스키마 병합
Gateway는 시작 시 각 서비스의 OpenAPI 스키마를 가져와 병합합니다:

1. 각 서비스에서 `/openapi.json` 엔드포인트 호출
2. 경로 프리픽스 조정 (`/ai/data` → `/api/ai/data`)
3. 태그별 그룹화
4. 통합 스키마 생성

### 프록시 구현
```python
# 요청 프록시 패턴
/api/ai/classify/* → http://classifier:8001/ai/classify/*
/api/ai/data/*     → http://analysis:8002/ai/data/*
/api/ai/csv/*      → http://csv-manager:8003/api/ai/csv/*
```

### 에러 처리
- `503 Service Unavailable`: 대상 서비스 접근 불가
- `504 Gateway Timeout`: 서비스 응답 시간 초과
- `404 Not Found`: 잘못된 경로

## 📊 모니터링

### 서비스 상태 확인
```python
import requests

response = requests.get("http://localhost:8000/api/ai/services")
services = response.json()

for service_name, info in services.items():
    print(f"{service_name}: {info['endpoints']} endpoints")
```

### 로그 확인
```bash
# Gateway 로그
docker-compose logs gateway -f

# 특정 시간대 로그
docker-compose logs gateway --since="2024-01-01" --until="2024-01-02"
```

## 🚀 성능 최적화

- **Connection Pooling**: httpx AsyncClient 재사용
- **Timeout 설정**: 서비스별 적절한 타임아웃
- **Retry 로직**: 실패 시 자동 재시도
- **스키마 캐싱**: OpenAPI 스키마 캐싱으로 시작 시간 단축

## 🔍 트러블슈팅

### 문제: Swagger UI에 서비스가 안 보임
```bash
# 서비스 상태 확인
curl http://localhost:8000/api/ai/health

# Gateway 재시작
docker-compose restart gateway
```

### 문제: 504 Gateway Timeout
```bash
# 타임아웃 증가 (docker-compose.yml)
environment:
  - REQUEST_TIMEOUT=60
```

### 문제: 인증 실패
```bash
# 토큰 확인
echo $ADMIN_TOKEN
echo $USER_TOKEN

# 환경 변수 재로드
docker-compose up -d gateway
```

## 📝 API 응답 예시

### 성공 응답
```json
{
  "status": "success",
  "data": {...},
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### 에러 응답
```json
{
  "status": "error",
  "message": "Service unavailable",
  "service": "classifier",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## 📝 주요 변경사항

### v2.0.0 (현재)
- ✅ GPT-5-nano 기반 Classifier 서비스 통합
- ✅ Analysis doojo 엔드포인트 라우팅 추가
- ✅ Structured Outputs 지원
- ✅ 통합 API 문서 개선
- ✅ 서비스별 헬스체크 강화

### v1.0.0
- 초기 릴리스
- 기본 라우팅 기능
- OpenAPI 스키마 병합

## 🔗 관련 문서

- [Main README](../README.md)
- [CSV Manager Service](../csv-manager/README.md)
- [Classifier Service](../classifier/README.md)
- [Analysis Service](../analysis/README.md)

---

**Version**: 2.0.0
**Last Updated**: 2025-10-01