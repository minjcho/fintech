# 📊 Analysis Service

Facebook Prophet 기반 시계열 예측 서비스 - 카테고리별 지출 예측 및 베이스라인 분석

## 🎯 Overview

Analysis Service는 Facebook Prophet을 활용하여 사용자의 금융 거래 데이터를 분석하고 미래 지출을 예측하는 서비스입니다.
13개 카테고리별로 독립적인 예측 모델을 구축하여 정확한 지출 예측과 소비 기준 금액(베이스라인)을 제공합니다.

## ✨ Key Features

### 예측 분석
- **현재월 예측**: 카테고리별 당월 지출 예측
- **11개월 베이스라인**: 과거 11개월 소비 기준 금액
- **누수 분석**: 예측 대비 실제 지출 초과분 계산
- **신뢰구간**: 95% 상한/하한 예측 범위
- **두꺼비 조언 (doojo)**: S3 CSV 기반 실시간 지출 패턴 분석

### GPT 기반 개인화 조언
- **가맹점 분석**: 카테고리별 최다 지출/방문 가맹점 추출
- **맞춤형 조언**: GPT-5-nano 기반 한국어 금융 조언 자동 생성
- **실시간 생성**: 사용자 소비 패턴에 맞춘 실시간 메시지

### 모델 최적화
- **카테고리별 커스터마이징**: 지출 패턴별 최적 파라미터
- **계절성 분석**: 주간/월간 패턴 자동 감지
- **병렬 처리**: ThreadPoolExecutor 4 workers
- **순차 실행**: 현재월 우선 처리 후 베이스라인 계산

### 데이터 관리
- **Azure MySQL 저장**: 예측 결과 영구 보관 (SSL 보안 연결)
- **Redis 캐싱**: 상태 관리 (analyzing → none) 및 메타데이터 저장
- **S3 연동**: CSV 파일 직접 다운로드
- **비동기 처리**: BackgroundTasks 활용

## 🚀 API Endpoints

### 1. 분석 시작
```bash
POST /api/ai/data?file_id=abc-123

# Response (202 Accepted)
{
  "file_id": "abc-123",
  "year": 2024,
  "month": 12,
  "total_leak": 0,
  "message": "Prophet analysis started. Job ID: xyz-789"
}
```

### 2. 현재월 예측 및 누수 조회
```bash
GET /api/ai/data/leak?file_id=abc-123

# Response
{
  "file_id": "abc-123",
  "year": 2024,
  "month": 12,
  "leak_amount": 0,
  "transactions_count": 13,
  "details": {
    "total_predicted": 1058850.54,
    "categories_count": 13,
    "category_predictions": {
      "식비": {
        "predicted_amount": 228906.00,
        "lower_bound": 210543.00,
        "upper_bound": 247269.00
      },
      "교통/차량": {
        "predicted_amount": 106261.00,
        "lower_bound": 95635.00,
        "upper_bound": 116887.00
      }
      // ... 11개 카테고리 더
    }
  }
}
```

### 3. 과거 11개월 베이스라인 조회
```bash
GET /api/ai/data/baseline?file_id=abc-123

# Response
{
  "file_id": "abc-123",
  "baseline_months": [
    {
      "year": 2024,
      "month": 11,
      "total_predicted": 1100431.42,
      "categories_count": 13,
      "category_predictions": {
        "식비": {
          "predicted_amount": 450000,
          "lower_bound": 420000,
          "upper_bound": 480000
        }
      },
      "training_data_until": "2024-10-31"
    }
    // ... 10개월 더
  ],
  "months_count": 11,
  "category_filter": null
}
```

### 4. 특정 카테고리 베이스라인
```bash
GET /api/ai/data/baseline?file_id=abc-123&category=식비

# Response: 식비 카테고리만 필터링된 11개월 베이스라인
```

### 5. 두꺼비 조언 (doojo) - GPT 기반 개인화 조언
```bash
GET /api/ai/data/doojo?file_id=abc-123&year=2025&month=1

# Response
{
  "file_id": "abc-123",
  "doojo": [{
    "year": 2025,
    "month": 1,
    "categories_count": 5,
    "categories_prediction": {
      "카페": {
        "min": 50000,
        "max": 120000,
        "current": 82000,    # 평균값 기준
        "real": 75000,
        "result": false,     # 예산 초과 여부
        "avg": 82000
      }
    },
    "categories_detail": {
      "카페": {
        "most_spent": {
          "merchant": "스타벅스",
          "amount": 12000,
          "date": "2025-01-15",
          "msg": "다음 달 스타벅스 지출을 월 2만 원 이하로 제한하고..."  # GPT 생성
        },
        "most_frequent": {
          "merchant": "이디야",
          "count": 8,
          "total_amount": 32000,
          "msg": "이디야 방문을 주 2회로 줄이고 집에서 만든 커피로..."  # GPT 생성
        }
      }
    }
  }]
}
```

**doojo 특징:**
- ✅ S3 CSV 기반: MySQL 없이 순수 CSV 데이터만 사용
- ✅ GPT-5-nano 조언: 가맹점별 개인화된 한국어 조언 자동 생성
- ✅ 실시간 분석: 카테고리별 min/max/avg 계산
- ✅ 월별 쿼리: year/month 파라미터로 특정 월 분석

## 📁 Project Structure

```
analysis/
├── app/
│   ├── api/
│   │   └── endpoints/
│   │       └── data.py          # API 엔드포인트
│   ├── db/
│   │   ├── database.py         # Azure MySQL 연결 (SSL)
│   │   └── models.py           # SQLAlchemy 모델
│   ├── services/
│   │   ├── prophet_service.py  # Prophet 예측 엔진
│   │   ├── redis_client.py     # Redis 클라이언트
│   │   └── s3_client.py        # S3 파일 처리
│   ├── models/
│   │   └── schemas.py          # Pydantic 모델
│   └── main.py                 # FastAPI 앱
├── Dockerfile
└── requirements.txt
```

## 🏗️ Architecture

### 시스템 구조
```
┌─────────────────┐
│   API Gateway   │
└────────┬────────┘
         │ /api/ai/data/*
         ▼
┌─────────────────┐
│   Analysis      │◄──── Prophet Engine
│    Service      │       (13 Models)
└────┬───────┬────┘
     │       │
     ▼       ▼
┌────────────┐ ┌────────┐
│Azure MySQL │ │ Redis  │
│     DB     │ │ Cache  │
└────────────┘ └────────┘
```

### 처리 프로세스

#### 분석 워크플로우
1. **CSV 다운로드** → S3에서 파일 가져오기
2. **데이터 전처리** → 카테고리별 일일 집계
3. **현재월 예측** → 전체 데이터로 당월 예측
4. **DB 저장** → 현재월 결과 즉시 커밋
5. **베이스라인 계산** → 과거 11개월 순차 계산
6. **최종 저장** → 베이스라인 결과 저장

## 🧠 Prophet 예측 엔진

### 카테고리별 최적화
```python
# 식비/카페 - 주간 패턴 강함
if category in ['식비', '카페/간식']:
    model = Prophet(
        weekly_seasonality=True,
        changepoint_prior_scale=0.1,
        interval_width=0.95
    )

# 교통비 - 월간 정기 패턴
elif category in ['교통/차량']:
    model = Prophet(
        weekly_seasonality=False,
        changepoint_prior_scale=0.05
    )
    model.add_seasonality(
        name='monthly',
        period=30.5,
        fourier_order=5
    )

# 기타 - 균형 설정
else:
    model = Prophet(
        weekly_seasonality=True,
        seasonality_mode='multiplicative',
        changepoint_prior_scale=0.05
    )
```

### 베이스라인 계산 로직
```python
# 현재 12월인 경우 - 과거 11개월 계산
months_to_calculate = []
for i in range(11, 0, -1):  # 11개월 전부터 1개월 전까지
    calc_date = current_date - timedelta(days=30 * i)
    months_to_calculate.append((calc_date.year, calc_date.month))

# 예: 1월~11월 각각 계산
for target_year, target_month in months_to_calculate:
    # 해당 월 이전 데이터만 사용
    cutoff_date = datetime(target_year, target_month, 1) - timedelta(days=1)
    train_data = csv_data[csv_data['date'] <= cutoff_date]

    # Prophet 모델 학습 및 예측
    for category in categories:
        model = train_prophet_model(train_data, category)
        prediction = model.predict(target_month)
```

### GPT Message Generator - 개인화 조언
```python
from openai import OpenAI

# GMS (SSAFY GPT Model Service) 클라이언트
gms_client = OpenAI(
    api_key=os.getenv('GMS_API_KEY'),
    base_url=os.getenv('GMS_BASE_URL')
)

def generate_merchant_message(
    category: str,
    merchant: str,
    message_type: str,
    amount: float = None,
    count: int = None
) -> str:
    """GPT-5-nano 기반 개인화 조언 생성"""

    if message_type == 'most_spent':
        prompt = f"{category} 카테고리 '{merchant}'에서 {amount:,.0f}원 지출했어. 한 줄로 조언해줘 (반말, 이모지 없이)"
    else:  # most_frequent
        prompt = f"{category} 카테고리 '{merchant}'에 {count}회 방문해서 총 {amount:,.0f}원 썼어. 한 줄로 조언해줘 (반말, 이모지 없이)"

    response = gms_client.chat.completions.create(
        model="gpt-5-nano",
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=1000  # 충분한 토큰으로 응답 보장
    )

    return response.choices[0].message.content.strip()

# 조언 생성 예시
most_spent_msg = generate_merchant_message(
    category="카페",
    merchant="스타벅스",
    message_type="most_spent",
    amount=5939.0
)
# → "다음 달 스타벅스 지출을 월 2만 원 이하로 제한하고, 필요하면 집에서 만든 커피나 대체 음료로 대체해봐."

most_freq_msg = generate_merchant_message(
    category="카페",
    merchant="스타벅스",
    message_type="most_frequent",
    amount=22740.0,
    count=5
)
# → "다음 달 스타벅스 방문을 주 1회로 줄이고, 집에서 만든 커피나 텀블러 사용으로 지출을 줄여봐."
```

## 💾 Database Schema

### predictions 테이블
```sql
CREATE TABLE predictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_id VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    prediction_date DATE NOT NULL,
    predicted_amount DECIMAL(15,2),
    lower_bound DECIMAL(15,2),
    upper_bound DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_file_category (file_id, category),
    INDEX idx_date (prediction_date)
);
```

### baseline_predictions 테이블
```sql
CREATE TABLE baseline_predictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_id VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    predicted_amount DECIMAL(15,2),
    lower_bound DECIMAL(15,2),
    upper_bound DECIMAL(15,2),
    training_cutoff_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_file_year_month (file_id, year, month),
    UNIQUE KEY uk_file_category_date (file_id, category, year, month)
);
```

### leak_analysis 테이블
```sql
CREATE TABLE leak_analysis (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_id VARCHAR(255) NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    actual_amount DECIMAL(15,2),
    predicted_amount DECIMAL(15,2),
    leak_amount DECIMAL(15,2),
    analysis_data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_file_date (file_id, year, month)
);
```

## 🔧 Configuration

### 환경 변수 (.env)
```bash
# Azure MySQL (SSL 연결 필수)
MYSQL_HOST=ssafy-mysql-db.mysql.database.azure.com
MYSQL_PORT=3306
MYSQL_DATABASE=S13P21A409
MYSQL_USER=S13P21A409
MYSQL_PASSWORD=your-password
DATABASE_URL=mysql+pymysql://user:password@host:3306/database?charset=utf8mb4

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# S3/MinIO
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=csv-uploads

# GMS (SSAFY GPT Model Service) for doojo
GMS_API_KEY=S13P22A409-xxxx-xxxx-xxxx-xxxxxxxxxxxx
GMS_BASE_URL=https://gms.ssafy.io/gmsapi/api.openai.com/v1

# Service
SERVICE_PORT=8002
LOG_LEVEL=INFO

# Prophet
MAX_WORKERS=4
PREDICTION_DAYS=60
CONFIDENCE_INTERVAL=0.95
```

## 📊 지원 카테고리

| 카테고리 | 계절성 | 평균 월지출 | 특징 |
|----------|--------|------------|------|
| 식비 | 주간 | 22만원 | 주말 증가 |
| 교통/차량 | 월간 | 10만원 | 정기 지출 |
| 마트/편의점 | 주간 | 14만원 | 주말 장보기 |
| 온라인쇼핑 | 이벤트 | 7만원 | 불규칙 |
| 카페/간식 | 주간 | 8만원 | 평일 집중 |
| 의료/건강 | 비정기 | 6만원 | 돌발 지출 |
| 문화/여가 | 주말 | 5만원 | 주말 집중 |
| 생활 | 월간 | 8만원 | 고정 지출 |
| 뷰티/미용 | 월간 | 4만원 | 주기적 |
| 여행/숙박 | 계절 | 3만원 | 휴가철 |
| 교육 | 분기 | 9만원 | 학기별 |
| 술/유흥 | 주말 | 2만원 | 금토 집중 |
| 기타 | 랜덤 | 2만원 | 패턴 없음 |

## 🚀 Development

### 로컬 개발
```bash
# 독립 실행
cd analysis
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8002

# Docker 실행
docker build -t analysis .
docker run -p 8002:8002 --env-file ../.env analysis
```

### 테스트
```bash
# 단위 테스트
pytest tests/

# 예측 정확도 테스트
python tests/prophet_accuracy.py

# 통합 테스트
pytest tests/integration/
```

## 📈 성능 최적화

### 병렬 처리
- ThreadPoolExecutor (4 workers)
- 카테고리별 독립 모델
- 평균 처리: 3-5초 (13개 카테고리)

### 순차 실행 전략
```python
# 1. 현재월 먼저 처리
current_month_result = await prophet_service.predict_by_category(csv_data)
db.commit()  # 즉시 저장

# 2. 베이스라인 계산
baseline_predictions = await prophet_service.calculate_baseline_predictions_async(csv_data)
```

### 데이터베이스 최적화
- 적절한 인덱싱
- 배치 INSERT
- 커넥션 풀링 (max=10)

## 🔍 Monitoring

### Health Check
```bash
GET /health

# Response
{
  "status": "healthy",
  "service": "analysis",
  "dependencies": {
    "database": "connected",
    "redis": "connected",
    "s3": "connected"
  }
}
```

### 메트릭스
- 평균 응답: < 100ms (조회)
- 분석 시간: 3-5초 (전체)
- 동시 처리: 10개 파일
- 메모리: < 512MB

## 📝 주요 변경사항

### v2.0.0 (현재)
- ✅ 11개월 베이스라인으로 확장
- ✅ 현재월 우선 처리 구현
- ✅ 다음월 예측 제거
- ✅ Azure MySQL 마이그레이션 (로컬 → 클라우드)
- ✅ 순차 실행 최적화
- ✅ **doojo 엔드포인트 추가** (S3 CSV 기반)
- ✅ **GPT-5-nano 조언 생성** (개인화 금융 조언)
- ✅ **merchant_name 컬럼 지원** (CSV 표준화)
- ✅ **openai 1.55.3** 라이브러리 추가

### v1.0.0
- 초기 릴리스
- 9개월 베이스라인
- PostgreSQL 사용

## 🐛 트러블슈팅

### 분석 시작 안 됨
```bash
# 상태 확인 (analyzing이면 대기, none이면 분석 가능)
GET /api/ai/csv/status?file_id=abc-123

# 상태가 none일 때 분석 시작
POST /api/ai/data?file_id=abc-123
```

### 특정 카테고리 누락
- 원인: 데이터 부족 (< 2일)
- 해결: 해당 카테고리 0원으로 처리

### Azure MySQL 연결 실패
```bash
# Analysis 서비스 재시작
docker-compose restart analysis

# SSL 연결 로그 확인
docker-compose logs analysis --tail 50

# SSL 설정 확인 필수
# database.py에 SSL context 설정이 있어야 함
```

### GPT 조언 생성 실패
```bash
# GMS API Key 확인
echo $GMS_API_KEY

# 토큰 문제 (빈 응답)
# gpt-5-nano는 reasoning token을 많이 사용
# max_completion_tokens을 1000 이상으로 설정 권장

# 연결 테스트
curl -H "Authorization: Bearer $GMS_API_KEY" \
  https://gms.ssafy.io/gmsapi/api.openai.com/v1/models
```

### doojo 엔드포인트 에러
- **원인**: merchant_name 컬럼 누락
- **해결**: CSV에 merchant_name 컬럼 포함 확인
- **원인**: 데이터 부족 (< 30 거래)
- **해결**: 최소 30개 거래 데이터 필요

## 🤝 Integration

이 서비스는 다음 서비스들과 통합됩니다:

- **API Gateway**: 요청 라우팅
- **CSV Manager**: 파일 다운로드
- **Classifier**: 분류된 데이터 수신
- **Redis**: 상태 공유 (analyzing/none)
- **Azure MySQL**: 클라우드 기반 결과 저장 (SSL 보안 연결)

## 🔗 관련 문서

- [Main README](../README.md)
- [API Gateway](../gateway/README.md)
- [CSV Manager Service](../csv-manager/README.md)
- [Classifier Service](../classifier/README.md)

---

**Version**: 2.0.0
**Last Updated**: 2025-10-01
**GPT Model**: GPT-5-nano (doojo advice generation)