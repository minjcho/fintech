# 📚 AI Fintech System 사용 가이드

AI 기반 금융 데이터 분석 시스템의 전체 워크플로우를 단계별로 안내합니다.

## 📋 목차

1. [시스템 시작](#1-시스템-시작)
2. [CSV 파일 준비](#2-csv-파일-준비)
3. [CSV 파일 업로드](#3-csv-파일-업로드)
4. [AI 카테고리 분류](#4-ai-카테고리-분류)
5. [AI 소비 패턴 분석](#5-ai-소비-패턴-분석)
6. [AI 절약 방법 추천](#6-ai-절약-방법-추천)
7. [전체 워크플로우 예시](#7-전체-워크플로우-예시)

---

## 1. 시스템 시작

### Docker Compose로 전체 시스템 실행

```bash
# 프로젝트 디렉토리로 이동
cd /path/to/ai

# 환경 변수 설정 (.env 파일 생성)
cp .env.example .env
# .env 파일에서 GMS_API_KEY 설정 필수!

# 전체 서비스 시작
docker-compose up -d

# 서비스 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f
```

### 시스템 헬스체크

```bash
curl http://localhost:8000/api/ai/health
```

**Expected Output:**
```json
{
  "gateway": "healthy",
  "services": {
    "csv-manager": {"status": "healthy"},
    "classifier": {"status": "healthy"},
    "analysis": {"status": "healthy"}
  }
}
```

---

## 2. CSV 파일 준비

### CSV 파일 형식

거래 데이터 CSV 파일은 다음 4개 컬럼을 포함해야 합니다:

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `merchant_name` | string | 가맹점명 | 스타벅스, 맥도날드, GS25 |
| `category` | string | 카테고리 (선택) | 카페, 식비, 마트/편의점 |
| `amount` | float | 거래 금액 (원) | 4800, 15000, 35000 |
| `transaction_date_time` | datetime | 거래 일시 | 2024-11-01T10:30:00 |

### CSV 파일 예시 (`transactions.csv`)

```csv
merchant_name,category,amount,transaction_date_time
스타벅스,카페,4800,2024-11-01T10:30:00
맥도날드,식비,7500,2024-11-01T12:15:00
이마트,마트/편의점,35000,2024-11-01T14:20:00
CGV,문화생활,15000,2024-11-02T19:00:00
GS25,마트/편의점,8500,2024-11-02T08:30:00
투썸플레이스,카페,5200,2024-11-03T15:00:00
버거킹,식비,9800,2024-11-03T12:30:00
올리브영,패션/미용,23000,2024-11-04T16:00:00
카카오T,교통/차량,12000,2024-11-04T08:00:00
교보문고,문화생활,18000,2024-11-05T14:30:00
```

### 데이터 요구사항

✅ **최소 요구사항:**
- **행 수**: 최소 30개 이상 (Prophet 분석용)
- **기간**: 최소 30일 이상 권장
- **카테고리**: 비어있어도 됨 (AI가 자동 분류)

✅ **권장 사항:**
- **행 수**: 100개 이상
- **기간**: 3개월 이상 (90일)
- **다양성**: 여러 카테고리의 거래 포함

### Python으로 CSV 생성 예시

```python
import pandas as pd
from datetime import datetime, timedelta
import random

# 샘플 데이터 생성
merchants = {
    '카페': ['스타벅스', '투썸플레이스', '이디야', '커피빈'],
    '식비': ['맥도날드', '버거킹', '김밥천국', '롯데리아'],
    '마트/편의점': ['이마트', 'GS25', 'CU', '세븐일레븐'],
    '문화생활': ['CGV', '메가박스', '교보문고', '예스24'],
    '패션/미용': ['올리브영', '왓슨스', '다이소']
}

data = []
start_date = datetime(2024, 11, 1)

for day in range(90):  # 90일치 데이터
    date = start_date + timedelta(days=day)
    # 하루에 2-5개 거래
    for _ in range(random.randint(2, 5)):
        category = random.choice(list(merchants.keys()))
        merchant = random.choice(merchants[category])
        amount = random.randint(3000, 50000)
        time = date + timedelta(hours=random.randint(8, 22))

        data.append({
            'merchant_name': merchant,
            'category': category,
            'amount': amount,
            'transaction_date_time': time.strftime('%Y-%m-%dT%H:%M:%S')
        })

# CSV 저장
df = pd.DataFrame(data)
df.to_csv('transactions.csv', index=False)
print(f"✅ {len(df)} 거래 데이터 생성 완료!")
```

---

## 3. CSV 파일 업로드

### API 엔드포인트

```
POST /api/ai/csv/upload
```

### 요청 형식

**Headers:**
- `X-Admin-Token`: admin-token (관리자 권한 필요)

**Body:**
- `Content-Type`: multipart/form-data
- `file`: CSV 파일

### cURL 예시

```bash
curl -X POST "http://localhost:8000/api/ai/csv/upload" \
  -H "X-Admin-Token: admin-token" \
  -F "file=@transactions.csv"
```

### Python 예시

```python
import requests

# CSV 파일 업로드
url = "http://localhost:8000/api/ai/csv/upload"
headers = {"X-Admin-Token": "admin-token"}

with open('transactions.csv', 'rb') as f:
    files = {'file': ('transactions.csv', f, 'text/csv')}
    response = requests.post(url, headers=headers, files=files)

result = response.json()
file_id = result['file_id']

print(f"✅ 파일 업로드 성공!")
print(f"📁 File ID: {file_id}")
print(f"📊 유효한 행: {result['validation']['valid_rows']}개")
print(f"📅 데이터 기간: {result['validation']['date_range']['start']} ~ {result['validation']['date_range']['end']}")
```

### Expected Output (성공)

```json
{
  "csv_file": "transactions.csv",
  "file_id": "73941f06-9e89-4103-9c71-fded15beccb7",
  "checksum": "pending",
  "size_bytes": 0,
  "uploaded_at": "2025-10-01T00:00:00Z",
  "replaced_at": null,
  "s3_key": "73941f06-9e89-4103-9c71-fded15beccb7_transactions.csv",
  "s3_url": "pending",
  "validation": {
    "status": "valid",
    "total_rows": 276,
    "valid_rows": 276,
    "date_range_days": 90,
    "unique_categories": 5,
    "categories": ["카페", "식비", "마트/편의점", "문화생활", "패션/미용"],
    "date_range": {
      "start": "2024-11-01T08:00:00",
      "end": "2025-01-29T22:00:00"
    },
    "total_amount": 6194142.0,
    "validation_errors": [],
    "prophet_warnings": [],
    "prophet_errors": [],
    "prophet_ready": true,
    "baseline_ready": true
  }
}
```

### 업로드 상태 확인

```bash
# file_id로 상태 확인
curl "http://localhost:8000/api/ai/csv/status?file_id={file_id}" \
  -H "X-User-Token: user-token"
```

**Expected Output:**
```json
{
  "csv_file": "transactions.csv",
  "status": "none",  // uploading → ingesting → none
  "progress": null,
  "last_updated": "2025-10-01T00:01:00Z",
  "details": null
}
```

---

## 4. AI 카테고리 분류

### 개요

GPT-5-nano를 사용하여 거래를 13개 한국 카테고리로 자동 분류합니다.

**지원 카테고리:**
1. 식비
2. 카페
3. 마트/편의점
4. 문화생활
5. 교통/차량
6. 패션/미용
7. 생활용품
8. 주거/통신
9. 건강/병원
10. 교육
11. 경조사/회비
12. 보험/세금
13. 기타

### 방법 1: 단일 거래 분류

#### API 엔드포인트

```
GET /api/ai/classify?merchant_name={가맹점명}&amount={금액}
```

#### cURL 예시

```bash
# 스타벅스 분류
curl "http://localhost:8000/api/ai/classify?merchant_name=스타벅스&amount=4800"

# 맥도날드 분류
curl "http://localhost:8000/api/ai/classify?merchant_name=맥도날드&amount=7500"

# CGV 분류
curl "http://localhost:8000/api/ai/classify?merchant_name=CGV&amount=15000"
```

#### Python 예시

```python
import requests

def classify_transaction(merchant_name, amount):
    url = "http://localhost:8000/api/ai/classify"
    params = {
        "merchant_name": merchant_name,
        "amount": amount
    }

    response = requests.get(url, params=params)
    result = response.json()

    print(f"🏪 가맹점: {merchant_name} ({amount:,}원)")
    print(f"📂 카테고리: {result['category']}")
    print(f"📌 하위분류: {result['subcategory']}")
    print(f"🎯 신뢰도: {result['confidence']:.2%}")
    print()

    return result

# 테스트
classify_transaction("스타벅스", 4800)
classify_transaction("맥도날드", 7500)
classify_transaction("이마트", 35000)
classify_transaction("CGV", 15000)
classify_transaction("GS25", 8500)
```

#### Expected Output

```json
// 스타벅스
{
  "category": "카페",
  "subcategory": "커피전문점",
  "confidence": 0.95
}

// 맥도날드
{
  "category": "식비",
  "subcategory": "패스트푸드",
  "confidence": 0.92
}

// 이마트
{
  "category": "마트/편의점",
  "subcategory": "대형마트",
  "confidence": 0.93
}

// CGV
{
  "category": "문화생활",
  "subcategory": "영화",
  "confidence": 0.94
}

// GS25
{
  "category": "마트/편의점",
  "subcategory": "편의점",
  "confidence": 0.95
}
```

### 방법 2: 배치 분류 (전체 CSV)

#### 1단계: 배치 분류 시작

```bash
curl -X POST "http://localhost:8000/api/ai/classify/process?file_id={file_id}" \
  -H "X-Admin-Token: admin-token"
```

**Expected Output:**
```json
{
  "file_id": "73941f06-9e89-4103-9c71-fded15beccb7",
  "status": "started",
  "message": "Classification started in background"
}
```

#### 2단계: 분류 진행 상태 확인

```python
import requests
import time

def wait_for_classification(file_id, timeout=300):
    url = f"http://localhost:8000/api/ai/csv/status"
    params = {"file_id": file_id}
    headers = {"X-User-Token": "user-token"}

    start_time = time.time()

    while time.time() - start_time < timeout:
        response = requests.get(url, params=params, headers=headers)
        status = response.json()

        print(f"⏳ 상태: {status['status']}")

        if status['status'] == 'none':
            print("✅ 분류 완료!")
            return True
        elif status['status'] == 'failed':
            print("❌ 분류 실패!")
            return False

        time.sleep(5)  # 5초마다 확인

    print("⏱️ 타임아웃!")
    return False

# 사용 예시
file_id = "73941f06-9e89-4103-9c71-fded15beccb7"
wait_for_classification(file_id)
```

#### 3단계: 분류 결과 조회

```bash
curl "http://localhost:8000/api/ai/classify/result?file_id={file_id}"
```

**Expected Output:**
```json
{
  "file_id": "73941f06-9e89-4103-9c71-fded15beccb7",
  "total_rows": 276,
  "classified_rows": 276,
  "status": "completed",
  "results": [
    {
      "merchant_name": "스타벅스",
      "amount": 4800,
      "category": "카페",
      "subcategory": "커피전문점",
      "confidence": 0.95,
      "transaction_date_time": "2024-11-01T10:30:00"
    },
    {
      "merchant_name": "맥도날드",
      "amount": 7500,
      "category": "식비",
      "subcategory": "패스트푸드",
      "confidence": 0.92,
      "transaction_date_time": "2024-11-01T12:15:00"
    }
    // ... 나머지 276개 거래
  ],
  "category_summary": {
    "카페": 52,
    "식비": 58,
    "마트/편의점": 65,
    "문화생활": 48,
    "패션/미용": 53
  }
}
```

---

## 5. AI 소비 패턴 분석

### 개요

Facebook Prophet을 사용하여 카테고리별 지출 패턴을 분석하고 미래 지출을 예측합니다.

### 1단계: Prophet 분석 시작

#### API 엔드포인트

```
POST /api/ai/data?file_id={file_id}
```

#### cURL 예시

```bash
curl -X POST "http://localhost:8000/api/ai/data?file_id={file_id}"
```

#### Python 예시

```python
import requests

def start_prophet_analysis(file_id):
    url = f"http://localhost:8000/api/ai/data"
    params = {"file_id": file_id}

    response = requests.post(url, params=params)
    result = response.json()

    print(f"✅ Prophet 분석 시작!")
    print(f"📁 File ID: {result['file_id']}")
    print(f"📅 분석 월: {result['year']}-{result['month']}")
    print(f"💼 Job ID: {result['message'].split(': ')[1]}")

    return result

# 사용 예시
file_id = "73941f06-9e89-4103-9c71-fded15beccb7"
start_prophet_analysis(file_id)
```

**Expected Output:**
```json
{
  "file_id": "73941f06-9e89-4103-9c71-fded15beccb7",
  "year": 2025,
  "month": 1,
  "total_leak": 0,
  "message": "Prophet analysis started. Job ID: job-abc-123"
}
```

### 2단계: 분석 진행 상태 확인

```python
import requests
import time

def wait_for_analysis(file_id, timeout=60):
    url = f"http://localhost:8000/api/ai/csv/status"
    params = {"file_id": file_id}
    headers = {"X-User-Token": "user-token"}

    start_time = time.time()

    while time.time() - start_time < timeout:
        response = requests.get(url, params=params, headers=headers)
        status = response.json()

        current_status = status['status']
        print(f"⏳ 상태: {current_status}")

        if current_status == 'none':
            print("✅ 분석 완료!")
            return True
        elif current_status == 'analyzing':
            print("🔬 Prophet 분석 중...")

        time.sleep(3)

    print("⏱️ 타임아웃!")
    return False

# 사용 예시
wait_for_analysis(file_id)
```

### 3단계: 현재월 예측 결과 조회

#### API 엔드포인트

```
GET /api/ai/data/leak?file_id={file_id}&year={year}&month={month}
```

#### cURL 예시

```bash
curl "http://localhost:8000/api/ai/data/leak?file_id={file_id}&year=2025&month=1"
```

#### Python 예시

```python
import requests

def get_current_month_prediction(file_id, year=2025, month=1):
    url = f"http://localhost:8000/api/ai/data/leak"
    params = {
        "file_id": file_id,
        "year": year,
        "month": month
    }

    response = requests.get(url, params=params)
    result = response.json()

    print(f"📊 {year}년 {month}월 지출 예측")
    print(f"="*60)

    details = result['details']
    print(f"💰 총 예측 지출: {details['total_predicted']:,.0f}원")
    print(f"📂 분석 카테고리: {details['categories_count']}개")
    print()

    print("📌 카테고리별 예측:")
    for category, pred in details['category_predictions'].items():
        print(f"\n  {category}:")
        print(f"    예측: {pred['predicted_amount']:,.0f}원")
        print(f"    범위: {pred['lower_bound']:,.0f}원 ~ {pred['upper_bound']:,.0f}원")

    return result

# 사용 예시
file_id = "73941f06-9e89-4103-9c71-fded15beccb7"
get_current_month_prediction(file_id, year=2025, month=1)
```

#### Expected Output

```json
{
  "file_id": "73941f06-9e89-4103-9c71-fded15beccb7",
  "year": 2025,
  "month": 1,
  "leak_amount": 0,
  "transactions_count": 5,
  "details": {
    "total_predicted": 2010569.42,
    "categories_count": 5,
    "category_predictions": {
      "카페": {
        "predicted_amount": 82049.0,
        "lower_bound": 53393.0,
        "upper_bound": 119750.0
      },
      "식비": {
        "predicted_amount": 249920.0,
        "lower_bound": 212352.0,
        "upper_bound": 295239.0
      },
      "마트/편의점": {
        "predicted_amount": 849297.67,
        "lower_bound": 733245.0,
        "upper_bound": 932606.0
      },
      "문화생활": {
        "predicted_amount": 251199.0,
        "lower_bound": 175299.0,
        "upper_bound": 312325.0
      },
      "패션/미용": {
        "predicted_amount": 632248.33,
        "lower_bound": 520640.0,
        "upper_bound": 776015.0
      }
    }
  }
}
```

**출력 예시:**
```
📊 2025년 1월 지출 예측
============================================================
💰 총 예측 지출: 2,010,569원
📂 분석 카테고리: 5개

📌 카테고리별 예측:

  카페:
    예측: 82,049원
    범위: 53,393원 ~ 119,750원

  식비:
    예측: 249,920원
    범위: 212,352원 ~ 295,239원

  마트/편의점:
    예측: 849,298원
    범위: 733,245원 ~ 932,606원

  문화생활:
    예측: 251,199원
    범위: 175,299원 ~ 312,325원

  패션/미용:
    예측: 632,248원
    범위: 520,640원 ~ 776,015원
```

### 4단계: 과거 11개월 베이스라인 조회

#### API 엔드포인트

```
GET /api/ai/data/baseline?file_id={file_id}
```

#### cURL 예시

```bash
curl "http://localhost:8000/api/ai/data/baseline?file_id={file_id}"
```

#### Python 예시

```python
import requests

def get_baseline_predictions(file_id):
    url = f"http://localhost:8000/api/ai/data/baseline"
    params = {"file_id": file_id}

    response = requests.get(url, params=params)
    result = response.json()

    print(f"📊 과거 11개월 소비 기준 금액 (베이스라인)")
    print(f"="*60)

    for month_data in result['baseline_months']:
        year = month_data['year']
        month = month_data['month']
        total = month_data['total_predicted']

        print(f"\n📅 {year}년 {month}월")
        print(f"   총 예측: {total:,.0f}원")
        print(f"   학습 데이터: ~{month_data['training_data_until']}")

        # 상위 3개 카테고리만 표시
        predictions = month_data['category_predictions']
        sorted_cats = sorted(
            predictions.items(),
            key=lambda x: x[1]['predicted_amount'],
            reverse=True
        )[:3]

        for cat, pred in sorted_cats:
            print(f"   - {cat}: {pred['predicted_amount']:,.0f}원")

    return result

# 사용 예시
file_id = "73941f06-9e89-4103-9c71-fded15beccb7"
get_baseline_predictions(file_id)
```

#### Expected Output (일부)

```json
{
  "file_id": "73941f06-9e89-4103-9c71-fded15beccb7",
  "baseline_months": [
    {
      "year": 2024,
      "month": 3,
      "total_predicted": 1850432.18,
      "categories_count": 5,
      "category_predictions": {
        "카페": {
          "predicted_amount": 75000.0,
          "lower_bound": 48000.0,
          "upper_bound": 105000.0
        },
        "식비": {
          "predicted_amount": 235000.0,
          "lower_bound": 198000.0,
          "upper_bound": 278000.0
        }
        // ... 나머지 카테고리
      },
      "training_data_until": "2024-02-29"
    }
    // ... 나머지 10개월
  ],
  "months_count": 11,
  "category_filter": null
}
```

**출력 예시:**
```
📊 과거 11개월 소비 기준 금액 (베이스라인)
============================================================

📅 2024년 3월
   총 예측: 1,850,432원
   학습 데이터: ~2024-02-29
   - 마트/편의점: 780,000원
   - 패션/미용: 590,000원
   - 식비: 235,000원

📅 2024년 4월
   총 예측: 1,920,156원
   학습 데이터: ~2024-03-31
   - 마트/편의점: 810,000원
   - 패션/미용: 615,000원
   - 식비: 245,000원

...
```

---

## 6. AI 절약 방법 추천

### 개요

**두꺼비 조언 (doojo)** 엔드포인트를 통해 GPT-5-nano 기반 개인화 절약 조언을 받을 수 있습니다.

- S3 CSV 기반 실시간 분석
- 카테고리별 최다 지출/방문 가맹점 추출
- GPT-5-nano 기반 한국어 금융 조언 자동 생성

### API 엔드포인트

```
GET /api/ai/data/doojo?file_id={file_id}&year={year}&month={month}
```

### cURL 예시

```bash
curl "http://localhost:8000/api/ai/data/doojo?file_id={file_id}&year=2025&month=1"
```

### Python 예시

```python
import requests

def get_saving_recommendations(file_id, year=2025, month=1):
    url = f"http://localhost:8000/api/ai/data/doojo"
    params = {
        "file_id": file_id,
        "year": year,
        "month": month
    }

    response = requests.get(url, params=params)
    result = response.json()

    doojo_data = result['doojo'][0]

    print(f"💡 {year}년 {month}월 AI 절약 조언")
    print(f"="*70)

    # 전체 지출 현황
    current = result.get('current_spending', {})
    if current:
        print(f"\n💰 이번 달 총 지출: {current.get('total', 0):,.0f}원")
        print(f"📊 평균 대비: {current.get('status', 'N/A')}")
        print(f"   (최소: {current.get('min', 0):,.0f}원, 평균: {current.get('avg', 0):,.0f}원, 최대: {current.get('max', 0):,.0f}원)")

    # 카테고리별 조언
    categories_detail = doojo_data.get('categories_detail', {})

    for idx, (category, details) in enumerate(categories_detail.items(), 1):
        print(f"\n{'='*70}")
        print(f"📂 {idx}. {category}")
        print(f"{'='*70}")

        # 카테고리 지출 정보
        cat_prediction = doojo_data['categories_prediction'].get(category, {})
        print(f"💵 이번 달 지출: {cat_prediction.get('real', 0):,.0f}원")
        print(f"📈 평균: {cat_prediction.get('avg', 0):,.0f}원")
        print(f"📊 범위: {cat_prediction.get('min', 0):,.0f}원 ~ {cat_prediction.get('max', 0):,.0f}원")

        # 예산 초과 여부
        if cat_prediction.get('result'):
            print(f"⚠️  예산 초과!")
        else:
            print(f"✅ 예산 내 지출")

        # 최다 지출 가맹점
        most_spent = details.get('most_spent', {})
        if most_spent:
            print(f"\n🏪 최다 지출 가맹점: {most_spent.get('merchant')}")
            print(f"   금액: {most_spent.get('amount', 0):,.0f}원")
            msg = most_spent.get('msg', '')
            if msg:
                print(f"   💬 AI 조언: \"{msg}\"")

        # 최다 방문 가맹점
        most_frequent = details.get('most_frequent', {})
        if most_frequent:
            print(f"\n🔁 최다 방문 가맹점: {most_frequent.get('merchant')}")
            print(f"   방문: {most_frequent.get('count')}회")
            print(f"   총액: {most_frequent.get('total_amount', 0):,.0f}원")
            msg = most_frequent.get('msg', '')
            if msg:
                print(f"   💬 AI 조언: \"{msg}\"")

    print(f"\n{'='*70}")
    print(f"✨ 총 {len(categories_detail)}개 카테고리에 대한 절약 조언을 받았습니다!")

    return result

# 사용 예시
file_id = "73941f06-9e89-4103-9c71-fded15beccb7"
get_saving_recommendations(file_id, year=2025, month=1)
```

### Expected Output

```json
{
  "file_id": "73941f06-9e89-4103-9c71-fded15beccb7",
  "doojo": [{
    "year": 2025,
    "month": 1,
    "categories_count": 5,
    "categories_prediction": {
      "카페": {
        "min": 53393.0,
        "max": 119750.0,
        "current": 82049.0,
        "real": 53393.0,
        "result": false,
        "avg": 82049.0
      },
      "식비": {
        "min": 212352.0,
        "max": 295239.0,
        "current": 249920.0,
        "real": 242169.0,
        "result": false,
        "avg": 249920.0
      },
      "마트/편의점": {
        "min": 733245.0,
        "max": 932606.0,
        "current": 849297.67,
        "real": 882042.0,
        "result": true,
        "avg": 849297.67
      }
    },
    "categories_detail": {
      "카페": {
        "most_spent": {
          "merchant": "투썸플레이스",
          "amount": 5939.0,
          "date": "2025-01-16T10:41:00",
          "msg": "투썸플레이스 지출은 카페로 바로 기록하고, 이번 달 예산과 지출 패턴 점검해."
        },
        "most_frequent": {
          "merchant": "스타벅스",
          "count": 5,
          "total_amount": 22740.0,
          "msg": "다음 달 스타벅스 지출을 월 2만 원 이하로 제한하고, 필요하면 집에서 만든 커피나 대체 음료로 대체해봐."
        }
      },
      "식비": {
        "most_spent": {
          "merchant": "버거킹",
          "amount": 14903.0,
          "date": "2025-01-21T09:08:00",
          "msg": "다음엔 버거킹은 세트 말고 단품으로 주문하고 음료는 물로 바꿔서 지출을 줄여."
        },
        "most_frequent": {
          "merchant": "김밥천국",
          "count": 8,
          "total_amount": 83405.0,
          "msg": "김밥천국 방문을 주 1-2회로 줄이고 집에서 도시락을 준비해보는 건 어때?"
        }
      },
      "마트/편의점": {
        "most_spent": {
          "merchant": "CU",
          "amount": 58167.0,
          "date": "2025-01-07T16:04:00",
          "msg": "다음 달 CU 지출은 필요한 물건만 사고 예산을 미리 잡아 영수증으로 관리해."
        },
        "most_frequent": {
          "merchant": "CU",
          "count": 8,
          "total_amount": 346225.0,
          "msg": "편의점 대신 대형마트에서 한꺼번에 장보면 단가가 낮아져 절약할 수 있어."
        }
      },
      "문화생활": {
        "most_spent": {
          "merchant": "CGV",
          "amount": 19149.0,
          "date": "2025-01-02T09:36:00",
          "msg": "다음엔 예산 한도를 먼저 정하고 CGV 할인이나 쿠폰을 적극 활용하자."
        },
        "most_frequent": {
          "merchant": "교보문고",
          "count": 10,
          "total_amount": 153104.0,
          "msg": "다음 달엔 필요 물건만 목록에 적고 예산을 한도 내로 정해 충동구매를 피하자."
        }
      },
      "패션/미용": {
        "most_spent": {
          "merchant": "다이소",
          "amount": 47008.0,
          "date": "2025-01-09T18:58:00",
          "msg": "필요한 물건만 사고 다음엔 목록을 만들고 예산 한도를 확인해 중복 지출을 막자."
        },
        "most_frequent": {
          "merchant": "올리브영",
          "count": 8,
          "total_amount": 312997.0,
          "msg": "다음 달엔 필요 물건만 리스트로 적고 예산 한도 내에서만 쓰며 즉흥구매를 줄여."
        }
      }
    }
  }]
}
```

### 출력 예시

```
💡 2025년 1월 AI 절약 조언
======================================================================

💰 이번 달 총 지출: 2,010,569원
📊 평균 대비: 초과
   (최소: 1,750,000원, 평균: 1,900,000원, 최대: 2,200,000원)

======================================================================
📂 1. 카페
======================================================================
💵 이번 달 지출: 53,393원
📈 평균: 82,049원
📊 범위: 53,393원 ~ 119,750원
✅ 예산 내 지출

🏪 최다 지출 가맹점: 투썸플레이스
   금액: 5,939원
   💬 AI 조언: "투썸플레이스 지출은 카페로 바로 기록하고, 이번 달 예산과 지출 패턴 점검해."

🔁 최다 방문 가맹점: 스타벅스
   방문: 5회
   총액: 22,740원
   💬 AI 조언: "다음 달 스타벅스 지출을 월 2만 원 이하로 제한하고, 필요하면 집에서 만든 커피나 대체 음료로 대체해봐."

======================================================================
📂 2. 식비
======================================================================
💵 이번 달 지출: 242,169원
📈 평균: 249,920원
📊 범위: 212,352원 ~ 295,239원
✅ 예산 내 지출

🏪 최다 지출 가맹점: 버거킹
   금액: 14,903원
   💬 AI 조언: "다음엔 버거킹은 세트 말고 단품으로 주문하고 음료는 물로 바꿔서 지출을 줄여."

🔁 최다 방문 가맹점: 김밥천국
   방문: 8회
   총액: 83,405원
   💬 AI 조언: "김밥천국 방문을 주 1-2회로 줄이고 집에서 도시락을 준비해보는 건 어때?"

======================================================================
📂 3. 마트/편의점
======================================================================
💵 이번 달 지출: 882,042원
📈 평균: 849,298원
📊 범위: 733,245원 ~ 932,606원
⚠️  예산 초과!

🏪 최다 지출 가맹점: CU
   금액: 58,167원
   💬 AI 조언: "다음 달 CU 지출은 필요한 물건만 사고 예산을 미리 잡아 영수증으로 관리해."

🔁 최다 방문 가맹점: CU
   방문: 8회
   총액: 346,225원
   💬 AI 조언: "편의점 대신 대형마트에서 한꺼번에 장보면 단가가 낮아져 절약할 수 있어."

======================================================================
✨ 총 5개 카테고리에 대한 절약 조언을 받았습니다!
```

---

## 7. 전체 워크플로우 예시

### 완전한 Python 스크립트

```python
import requests
import time
import json

BASE_URL = "http://localhost:8000/api/ai"
ADMIN_TOKEN = "admin-token"
USER_TOKEN = "user-token"

def main():
    print("🚀 AI Fintech System - 전체 워크플로우")
    print("="*70)

    # 1. CSV 파일 업로드
    print("\n📤 1단계: CSV 파일 업로드")
    print("-"*70)

    with open('transactions.csv', 'rb') as f:
        files = {'file': ('transactions.csv', f, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/csv/upload",
            headers={"X-Admin-Token": ADMIN_TOKEN},
            files=files
        )

    result = response.json()
    file_id = result['file_id']

    print(f"✅ 파일 업로드 성공!")
    print(f"📁 File ID: {file_id}")
    print(f"📊 유효한 행: {result['validation']['valid_rows']}개")
    print(f"📅 데이터 기간: {result['validation']['date_range_days']}일")

    # 2. AI 카테고리 분류
    print("\n🤖 2단계: AI 카테고리 분류")
    print("-"*70)

    # 단일 거래 테스트
    test_merchants = [
        ("스타벅스", 4800),
        ("맥도날드", 7500),
        ("이마트", 35000)
    ]

    for merchant, amount in test_merchants:
        response = requests.get(
            f"{BASE_URL}/classify",
            params={"merchant_name": merchant, "amount": amount}
        )
        result = response.json()
        print(f"  {merchant} → {result['category']}/{result['subcategory']} ({result['confidence']:.2%})")

    # 배치 분류 시작
    print("\n⏳ 배치 분류 시작...")
    response = requests.post(
        f"{BASE_URL}/classify/process?file_id={file_id}",
        headers={"X-Admin-Token": ADMIN_TOKEN}
    )

    # 분류 완료 대기
    while True:
        response = requests.get(
            f"{BASE_URL}/csv/status",
            params={"file_id": file_id},
            headers={"X-User-Token": USER_TOKEN}
        )
        status = response.json()['status']

        if status == 'none':
            print("✅ 분류 완료!")
            break

        print(f"  상태: {status}")
        time.sleep(5)

    # 3. AI 소비 패턴 분석
    print("\n📊 3단계: AI 소비 패턴 분석 (Prophet)")
    print("-"*70)

    # Prophet 분석 시작
    response = requests.post(
        f"{BASE_URL}/data",
        params={"file_id": file_id}
    )
    print("✅ Prophet 분석 시작!")

    # 분석 완료 대기
    print("\n⏳ 분석 진행 중...")
    while True:
        response = requests.get(
            f"{BASE_URL}/csv/status",
            params={"file_id": file_id},
            headers={"X-User-Token": USER_TOKEN}
        )
        status = response.json()['status']

        if status == 'none':
            print("✅ 분석 완료!")
            break

        print(f"  상태: {status}")
        time.sleep(3)

    # 현재월 예측 조회
    response = requests.get(
        f"{BASE_URL}/data/leak",
        params={"file_id": file_id, "year": 2025, "month": 1}
    )
    result = response.json()

    print(f"\n💰 2025년 1월 예측:")
    details = result['details']
    print(f"  총 예측 지출: {details['total_predicted']:,.0f}원")
    print(f"  분석 카테고리: {details['categories_count']}개")

    # 상위 3개 카테고리
    predictions = details['category_predictions']
    sorted_cats = sorted(
        predictions.items(),
        key=lambda x: x[1]['predicted_amount'],
        reverse=True
    )[:3]

    print("\n  상위 3개 카테고리:")
    for cat, pred in sorted_cats:
        print(f"    {cat}: {pred['predicted_amount']:,.0f}원")

    # 4. AI 절약 방법 추천
    print("\n💡 4단계: AI 절약 방법 추천 (doojo)")
    print("-"*70)

    response = requests.get(
        f"{BASE_URL}/data/doojo",
        params={"file_id": file_id, "year": 2025, "month": 1}
    )
    result = response.json()

    doojo_data = result['doojo'][0]
    categories_detail = doojo_data['categories_detail']

    print(f"✅ {len(categories_detail)}개 카테고리 절약 조언 생성 완료!\n")

    # 각 카테고리별 조언 출력
    for idx, (category, details) in enumerate(categories_detail.items(), 1):
        print(f"📂 {category}")

        # 최다 지출 가맹점
        most_spent = details['most_spent']
        print(f"  🏪 최다 지출: {most_spent['merchant']} ({most_spent['amount']:,.0f}원)")
        if most_spent.get('msg'):
            print(f"     💬 \"{most_spent['msg']}\"")

        # 최다 방문 가맹점
        most_frequent = details['most_frequent']
        print(f"  🔁 최다 방문: {most_frequent['merchant']} ({most_frequent['count']}회)")
        if most_frequent.get('msg'):
            print(f"     💬 \"{most_frequent['msg']}\"")

        print()

    print("="*70)
    print("🎉 전체 워크플로우 완료!")
    print(f"📁 File ID: {file_id}")
    print("="*70)

if __name__ == "__main__":
    main()
```

### 실행 결과

```bash
python complete_workflow.py
```

```
🚀 AI Fintech System - 전체 워크플로우
======================================================================

📤 1단계: CSV 파일 업로드
----------------------------------------------------------------------
✅ 파일 업로드 성공!
📁 File ID: 73941f06-9e89-4103-9c71-fded15beccb7
📊 유효한 행: 276개
📅 데이터 기간: 90일

🤖 2단계: AI 카테고리 분류
----------------------------------------------------------------------
  스타벅스 → 카페/커피전문점 (95.00%)
  맥도날드 → 식비/패스트푸드 (92.00%)
  이마트 → 마트/편의점/대형마트 (93.00%)

⏳ 배치 분류 시작...
  상태: uploading
  상태: ingesting
✅ 분류 완료!

📊 3단계: AI 소비 패턴 분석 (Prophet)
----------------------------------------------------------------------
✅ Prophet 분석 시작!

⏳ 분석 진행 중...
  상태: analyzing
  상태: analyzing
✅ 분석 완료!

💰 2025년 1월 예측:
  총 예측 지출: 2,010,569원
  분석 카테고리: 5개

  상위 3개 카테고리:
    마트/편의점: 849,298원
    패션/미용: 632,248원
    식비: 249,920원

💡 4단계: AI 절약 방법 추천 (doojo)
----------------------------------------------------------------------
✅ 5개 카테고리 절약 조언 생성 완료!

📂 카페
  🏪 최다 지출: 투썸플레이스 (5,939원)
     💬 "투썸플레이스 지출은 카페로 바로 기록하고, 이번 달 예산과 지출 패턴 점검해."
  🔁 최다 방문: 스타벅스 (5회)
     💬 "다음 달 스타벅스 지출을 월 2만 원 이하로 제한하고, 필요하면 집에서 만든 커피나 대체 음료로 대체해봐."

📂 식비
  🏪 최다 지출: 버거킹 (14,903원)
     💬 "다음엔 버거킹은 세트 말고 단품으로 주문하고 음료는 물로 바꿔서 지출을 줄여."
  🔁 최다 방문: 김밥천국 (8회)
     💬 "김밥천국 방문을 주 1-2회로 줄이고 집에서 도시락을 준비해보는 건 어때?"

📂 마트/편의점
  🏪 최다 지출: CU (58,167원)
     💬 "다음 달 CU 지출은 필요한 물건만 사고 예산을 미리 잡아 영수증으로 관리해."
  🔁 최다 방문: CU (8회)
     💬 "편의점 대신 대형마트에서 한꺼번에 장보면 단가가 낮아져 절약할 수 있어."

📂 문화생활
  🏪 최다 지출: CGV (19,149원)
     💬 "다음엔 예산 한도를 먼저 정하고 CGV 할인이나 쿠폰을 적극 활용하자."
  🔁 최다 방문: 교보문고 (10회)
     💬 "다음 달엔 필요 물건만 목록에 적고 예산을 한도 내로 정해 충동구매를 피하자."

📂 패션/미용
  🏪 최다 지출: 다이소 (47,008원)
     💬 "필요한 물건만 사고 다음엔 목록을 만들고 예산 한도를 확인해 중복 지출을 막자."
  🔁 최다 방문: 올리브영 (8회)
     💬 "다음 달엔 필요 물건만 리스트로 적고 예산 한도 내에서만 쓰며 즉흥구매를 줄여."

======================================================================
🎉 전체 워크플로우 완료!
📁 File ID: 73941f06-9e89-4103-9c71-fded15beccb7
======================================================================
```

---

## 🔧 트러블슈팅

### 1. CSV 업로드 실패

**문제:** 400 Bad Request
```json
{
  "detail": "Invalid CSV format"
}
```

**해결:**
- CSV 파일 형식 확인 (4개 컬럼 필수)
- 인코딩 UTF-8 확인
- 파일 확장자 .csv 확인

### 2. 분류 정확도 낮음

**문제:** 신뢰도 점수 < 0.7

**해결:**
- 가맹점명 명확하게 작성
- 거래 금액 정확하게 입력
- 알려진 브랜드명 사용

### 3. Prophet 분석 실패

**문제:** 데이터 부족 에러
```json
{
  "detail": "Insufficient data for analysis"
}
```

**해결:**
- 최소 30개 거래 필요
- 최소 30일 기간 필요
- 데이터 추가 후 재업로드

### 4. GPT 조언 생성 안 됨

**문제:** msg 필드 비어있음

**해결:**
- GMS_API_KEY 환경 변수 확인
- Analysis 서비스 재시작
- max_completion_tokens 확인 (1000 이상)

---

## 📞 지원

### API 문서
- **Swagger UI**: http://localhost:8000/api/ai/docs
- **ReDoc**: http://localhost:8000/api/ai/redoc

### 로그 확인
```bash
# 전체 로그
docker-compose logs

# 특정 서비스 로그
docker-compose logs classifier -f
docker-compose logs analysis -f
```

### 이슈 리포트
- GitHub: https://github.com/anthropics/claude-code/issues

---

**Version**: 2.0.0
**Last Updated**: 2025-10-01
**Team**: SSAFY 13기 A409팀
