# 📂 CSV Manager Service

CSV 파일 관리를 위한 독립적인 마이크로서비스 - MinIO/S3 스토리지와 Redis 캐시를 활용한 안정적인 파일 관리

## 🎯 Overview

CSV Manager는 금융 데이터 CSV 파일의 업로드, 저장, 상태 관리를 담당하는 전용 서비스입니다.
고유 file_id를 통해 중복 파일명도 허용하며, Redis를 통한 메타데이터 관리로 빠른 응답을 제공합니다.

## ✨ Key Features

### 파일 관리
- **중복 파일명 허용**: 동일한 파일명도 고유 file_id로 구분
- **비동기 업로드**: 백그라운드 처리로 빠른 응답
- **파일 교체**: 기존 file_id 유지하며 새 버전으로 교체
- **안전한 삭제**: 처리 중 상태 확인 후 삭제

### 스토리지
- **MinIO/S3 통합**: S3 호환 객체 스토리지
- **Redis 캐싱**: 메타데이터 및 상태 정보 고속 처리
- **자동 버킷 관리**: 시작 시 버킷 자동 생성
- **SHA-256 체크섬**: 파일 무결성 검증

### 보안
- **토큰 기반 인증**: Admin/User 역할 분리
- **Presigned URL**: 안전한 다운로드 링크 생성
- **파일 검증**: CSV 형식 및 Content-Type 확인

## 🚀 API Endpoints

### 1. 파일 업로드 (비동기)
```bash
POST /api/ai/csv/upload
X-Admin-Token: admin-token
Content-Type: multipart/form-data

# Request
file: transactions.csv

# Response (202 Accepted)
{
  "csv_file": "transactions.csv",
  "file_id": "abc-123-def-456",  # 고유 ID
  "status": "uploading",
  "checksum": "pending",
  "size_bytes": 0,
  "uploaded_at": "2024-12-01T00:00:00Z",
  "s3_key": "abc-123-def-456_transactions.csv"
}
```

### 2. 상태 확인
```bash
GET /api/ai/csv/status?file_id=abc-123-def-456
X-User-Token: user-token

# Response
{
  "csv_file": "transactions.csv",
  "status": "none",  # uploading/analyzing/none
  "progress": null,
  "last_updated": "2024-12-01T00:01:00Z",
  "details": null
}
```

### 3. 파일 정보 조회
```bash
GET /api/ai/csv/file?file_id=abc-123-def-456
X-User-Token: user-token

# Response
{
  "csv_file": "transactions.csv",
  "file_id": "abc-123-def-456",
  "checksum": "a1b2c3d4...",
  "size_bytes": 102400,
  "uploaded_at": "2024-12-01T00:00:00Z",
  "replaced_at": null,
  "s3_key": "abc-123-def-456_transactions.csv",
  "s3_url": "https://..."  # Presigned URL
}
```

### 4. 파일 삭제
```bash
DELETE /api/ai/csv/delete?file_id=abc-123-def-456
X-Admin-Token: admin-token

# Response: 204 No Content
```

### 5. 파일 교체 (비동기)
```bash
PUT /api/ai/csv/change?file_id=abc-123-def-456
X-Admin-Token: admin-token
Content-Type: multipart/form-data

# Request
file: new_transactions.csv

# Response (202 Accepted)
{
  "csv_file": "transactions.csv",
  "file_id": "abc-123-def-456",  # 동일한 ID 유지
  "status": "uploading",
  "replaced_at": "2024-12-02T00:00:00Z"
}
```

## 📁 Project Structure

```
csv-manager/
├── app/
│   ├── api/
│   │   └── endpoints/
│   │       └── csv.py         # API 엔드포인트
│   ├── core/
│   │   └── config.py         # 환경 설정
│   ├── deps/
│   │   └── auth.py          # 인증 미들웨어
│   ├── models/
│   │   └── schemas.py       # Pydantic 모델
│   ├── repos/
│   │   ├── csv_repo.py      # S3/MinIO 저장소
│   │   └── redis_client.py  # Redis 클라이언트
│   └── main.py              # FastAPI 앱
├── Dockerfile
└── requirements.txt
```

## 🔧 Configuration

### 환경 변수 (.env)
```bash
# MinIO/S3 설정
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=csv-uploads
MINIO_SECURE=false
MINIO_REGION=us-east-1
VERIFY_SSL=false

# Redis 설정
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# 인증 토큰
ADMIN_TOKEN=admin-token
USER_TOKEN=user-token

# Presigned URL 만료 시간 (초)
PRESIGNED_URL_EXPIRY=3600  # 1시간

# 로깅
LOG_LEVEL=INFO
```

## 🏗️ Architecture

### 시스템 구조
```
┌─────────────────┐
│   API Gateway   │
└────────┬────────┘
         │ /api/ai/csv/*
         ▼
┌─────────────────┐
│  CSV Manager    │◄──── 비동기 처리
│    Service      │       (BackgroundTasks)
└────┬───────┬────┘
     │       │
     ▼       ▼
┌────────┐ ┌────────┐
│ MinIO  │ │ Redis  │
│  /S3   │ │ Cache  │
└────────┘ └────────┘
```

### 데이터 흐름
1. **업로드 요청** → 즉시 file_id 반환 (202)
2. **백그라운드 처리** → S3 업로드 + 체크섬 계산
3. **메타데이터 저장** → Redis에 파일 정보 저장
4. **상태 업데이트** → uploading → ingesting → none

## 🔄 상태 관리

### 파일 상태
| Status | Description | 다음 가능 동작 |
|--------|-------------|--------------|
| `uploading` | S3에 파일 업로드 중 | 삭제/교체 불가 |
| `ingesting` | 데이터 처리 및 검증 중 | 삭제/교체 불가 |
| `analyzing` | Prophet AI 분석 진행 중 | 삭제/교체 불가 |
| `none` | 유휴 상태 | 모든 작업 가능 |

### Redis 키 구조
```
csv:metadata:id:{file_id}     # 파일 메타데이터
csv:status:{file_id}          # 처리 상태
csv:all_file_ids              # 모든 file_id Set
```

## 🔒 Security

### 인증 체계
- **Admin Token** (`X-Admin-Token`)
  - 파일 업로드/삭제/교체
  - 모든 파일 조회

- **User Token** (`X-User-Token`)
  - 파일 상태 확인
  - 파일 정보 조회

### 파일 검증
```python
# 허용 Content-Type
- text/csv
- application/csv
- application/vnd.ms-excel
- text/plain

# 파일 확장자
- .csv (대소문자 구분 없음)
```

## 🚀 Development

### 로컬 개발
```bash
# 독립 실행
cd csv-manager
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8003

# Docker 실행
docker build -t csv-manager .
docker run -p 8003:8003 --env-file ../.env csv-manager
```

### 테스트
```bash
# 단위 테스트
pytest tests/

# 통합 테스트
pytest tests/integration/

# 커버리지
pytest --cov=app tests/
```

## 📊 성능 최적화

### 비동기 처리
- FastAPI BackgroundTasks 활용
- 파일 업로드 즉시 응답 (202 Accepted)
- 백그라운드에서 S3 업로드 처리

### 캐싱 전략
- Redis를 통한 메타데이터 캐싱
- file_id 기반 빠른 조회
- Set 구조로 모든 파일 ID 관리

### 스토리지 최적화
- StreamingHashWrapper로 업로드 중 체크섬 계산
- Presigned URL로 직접 다운로드 제공
- 타임스탬프 기반 파일 버저닝

## 🔍 Monitoring

### Health Check
```bash
GET /health

# Response
{
  "status": "healthy",
  "service": "csv-manager",
  "dependencies": {
    "minio": "connected",
    "redis": "connected"
  }
}
```

### 메트릭스
- 업로드된 파일 수
- 평균 파일 크기
- 처리 시간
- 에러율

## 📝 주요 변경사항

### v2.0.0 (현재)
- ✅ 중복 파일명 허용 (file_id 기반 관리)
- ✅ Redis를 primary storage로 변경
- ✅ 비동기 업로드/교체 구현
- ✅ 백그라운드 태스크 처리
- ✅ 4-state 시스템 (uploading, ingesting, analyzing, none)

### v1.0.0
- 초기 릴리스
- MinIO 통합
- 기본 CRUD 작업

## 🐛 트러블슈팅

### MinIO 연결 실패
```bash
# MinIO 상태 확인
docker-compose ps minio

# 로그 확인
docker-compose logs minio

# 버킷 수동 생성
docker exec -it minio mc mb local/csv-uploads
```

### Redis 연결 문제
```bash
# Redis 재시작
docker-compose restart redis

# 연결 테스트
docker exec redis redis-cli ping
```

### 파일 업로드 실패
- 파일 크기 제한 확인 (기본 100MB)
- CSV 형식 검증
- 디스크 공간 확인

## 🤝 Integration

이 서비스는 다음 서비스들과 통합됩니다:

- **API Gateway**: 요청 라우팅 및 인증
- **Classifier Service**: 업로드된 CSV 분류
- **Analysis Service**: CSV 데이터 분석

## 📝 주요 변경사항

### v2.0.0 (현재)
- ✅ 중복 파일명 허용 (file_id 기반 관리)
- ✅ Redis를 primary storage로 변경
- ✅ 비동기 업로드/교체 구현
- ✅ 백그라운드 태스크 처리
- ✅ 4-state 시스템 (uploading, ingesting, analyzing, none)
- ✅ Prophet 분석 준비 상태 검증

### v1.0.0
- 초기 릴리스
- MinIO 통합
- 기본 CRUD 작업

## 🔗 관련 문서

- [Main README](../README.md)
- [API Gateway](../gateway/README.md)
- [Classifier Service](../classifier/README.md)
- [Analysis Service](../analysis/README.md)

---

**Version**: 2.0.0
**Last Updated**: 2025-10-01