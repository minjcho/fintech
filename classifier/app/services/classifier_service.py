from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import json
import os
from openai import OpenAI
from pydantic import BaseModel

from app.models.schemas import (
    JobStatus,
    ExpenseCategory,
    ClassificationJob,
    ClassificationResult
)
from app.core.config import settings

logger = logging.getLogger(__name__)


# Internal CoT schema with reasoning (not exposed externally)
class TransactionClassificationWithCoT(BaseModel):
    """Internal schema that includes Chain of Thought reasoning"""
    reasoning: str  # Step-by-step reasoning process
    category: str
    subcategory: str
    confidence: float

# External schema (without reasoning)
class TransactionClassification(BaseModel):
    """External schema for API response"""
    category: str
    subcategory: str
    confidence: float


class ClassifierService:
    """
    Service for expense classification using GPT-5-nano with structured outputs
    """

    def __init__(self):
        # Initialize OpenAI client with GMS endpoint
        self.client = OpenAI(
            api_key=settings.GMS_API_KEY,
            base_url=settings.GMS_BASE_URL
        )
        self.model = settings.OPENAI_MODEL
        self.categories = self._load_categories()
        self.jobs = {}  # In-memory job storage (use Redis/DB in production)
        self.results_path = "./classification_results"
        os.makedirs(self.results_path, exist_ok=True)
        
    def _load_categories(self) -> Dict[str, List[str]]:
        """Load expense categories and subcategories with detailed definitions"""
        return {
            "식비": ["한식", "중식", "일식", "양식", "분식", "패스트푸드", "배달음식"],
            "카페": ["커피전문점", "디저트카페", "베이커리"],
            "마트/편의점": ["대형마트", "편의점", "온라인마트"],
            "문화생활": ["영화", "공연", "전시", "도서", "음악", "게임"],
            "교통/차량": ["대중교통", "택시", "주유", "주차", "통행료", "차량유지"],
            "패션/미용": ["의류", "신발", "가방", "화장품", "미용실", "네일"],
            "생활용품": ["가전제품", "가구", "생필품", "주방용품"],
            "주거/통신": ["월세", "관리비", "전기", "가스", "수도", "인터넷", "휴대폰"],
            "건강/병원": ["병원", "약국", "건강검진", "의료용품"],
            "교육": ["학원", "교재", "온라인강의", "학용품"],
            "경조사/회비": ["경조사", "모임회비", "기부"],
            "보험/세금": ["보험료", "세금", "연금"],
            "기타": ["기타"]
        }

    def _get_category_guidelines(self) -> str:
        """Get detailed category classification guidelines with edge cases"""
        return """
## 카테고리 분류 가이드라인

### 명확한 분류 규칙:
1. **식비 vs 카페**:
   - 카페 전문점(스타벅스, 투썸플레이스 등) → 카페
   - 식당에서의 식사, 패스트푸드 → 식비
   - 빵집/베이커리 → 카페 (음료 판매 시), 식비 (빵만 판매 시)

2. **마트/편의점 vs 생활용품**:
   - 마트/편의점 브랜드명 명시 → 마트/편의점
   - 특정 제품 구매(가전, 가구 등) → 생활용품
   - 일반 장보기 → 마트/편의점

3. **패션/미용 vs 건강/병원**:
   - 드럭스토어(올리브영, 왓슨스) → 패션/미용
   - 약국, 병원 → 건강/병원

4. **교통/차량**:
   - 대중교통 카드 충전 → 대중교통
   - 주유소 → 주유
   - 택시/카카오T/우버 → 택시

### 경계 케이스 처리:
- 애매한 경우 금액 참고: 고액(50만원+) → 생활용품/가전
- 브랜드가 명확하면 우선 반영
- 불확실하면 confidence 0.7 이하로 설정
"""

    def _get_few_shot_examples(self) -> List[Dict[str, str]]:
        """Get few-shot examples for better classification"""
        return [
            {
                "role": "user",
                "content": "가맹점: 스타벅스 강남점\n금액: 4,500원\n일시: 2025-01-15 09:30"
            },
            {
                "role": "assistant",
                "content": '{"reasoning": "스타벅스는 커피 전문점 체인이며, 4,500원은 일반적인 음료 가격대입니다. 카페 카테고리가 가장 적합합니다.", "category": "카페", "subcategory": "커피전문점", "confidence": 0.95}'
            },
            {
                "role": "user",
                "content": "가맹점: 올리브영\n금액: 28,000원\n일시: 2025-01-15 14:00"
            },
            {
                "role": "assistant",
                "content": '{"reasoning": "올리브영은 화장품과 생활용품을 판매하는 드럭스토어입니다. 주로 화장품 구매로 추정되므로 패션/미용 카테고리가 적합합니다.", "category": "패션/미용", "subcategory": "화장품", "confidence": 0.85}'
            },
            {
                "role": "user",
                "content": "가맹점: 이마트\n금액: 35,000원\n일시: 2025-01-15 18:00"
            },
            {
                "role": "assistant",
                "content": '{"reasoning": "이마트는 대형마트 체인이며, 35,000원은 일반적인 장보기 금액입니다. 마트/편의점 카테고리가 적합합니다.", "category": "마트/편의점", "subcategory": "대형마트", "confidence": 0.93}'
            }
        ]

    def _apply_rule_based_postprocessing(
        self,
        merchant_name: str,
        amount: float,
        category: str,
        subcategory: str,
        confidence: float
    ) -> Dict[str, Any]:
        """Apply rule-based post-processing for edge cases"""
        merchant_lower = merchant_name.lower()

        # Rule 1: Known cafe chains should always be "카페"
        cafe_keywords = ['스타벅스', 'starbucks', '투썸', 'twosome', '이디야', 'ediya',
                        '커피빈', 'coffee bean', '할리스', 'hollys', '파스쿠찌', 'pascucci',
                        '메가커피', 'mega', '컴포즈커피', 'compose']
        if any(kw in merchant_lower for kw in cafe_keywords):
            if category != "카페":
                logger.info(f"Rule correction: {merchant_name} → 카페 (was: {category})")
                return {"category": "카페", "subcategory": "커피전문점", "confidence": 0.95}

        # Rule 2: Convenience stores
        convenience_keywords = ['gs25', 'cu', '세븐일레븐', '7-eleven', '이마트24', 'emart24',
                               '미니스톱', 'ministop']
        if any(kw in merchant_lower for kw in convenience_keywords):
            if category != "마트/편의점":
                logger.info(f"Rule correction: {merchant_name} → 마트/편의점 (was: {category})")
                return {"category": "마트/편의점", "subcategory": "편의점", "confidence": 0.95}

        # Rule 3: Drugstores (cosmetics)
        drugstore_keywords = ['올리브영', 'olive young', '왓슨스', 'watsons', '롭스', 'lohbs']
        if any(kw in merchant_lower for kw in drugstore_keywords):
            if category != "패션/미용":
                logger.info(f"Rule correction: {merchant_name} → 패션/미용 (was: {category})")
                return {"category": "패션/미용", "subcategory": "화장품", "confidence": 0.90}

        # Rule 4: Fast food chains
        fastfood_keywords = ['맥도날드', 'mcdonald', '버거킹', 'burger king', '롯데리아', 'lotteria',
                            'kfc', '맘스터치', "mom's touch", '서브웨이', 'subway']
        if any(kw in merchant_lower for kw in fastfood_keywords):
            if category != "식비":
                logger.info(f"Rule correction: {merchant_name} → 식비 (was: {category})")
                return {"category": "식비", "subcategory": "패스트푸드", "confidence": 0.93}

        # Rule 5: Large supermarkets
        supermarket_keywords = ['이마트', 'emart', '홈플러스', 'homeplus', '롯데마트', 'lotte mart',
                               '코스트코', 'costco', '트레이더스', 'traders']
        if any(kw in merchant_lower for kw in supermarket_keywords):
            if category != "마트/편의점":
                logger.info(f"Rule correction: {merchant_name} → 마트/편의점 (was: {category})")
                return {"category": "마트/편의점", "subcategory": "대형마트", "confidence": 0.93}

        # Rule 6: Electronics stores (even if name contains "mart")
        electronics_keywords = ['하이마트', 'himart', '전자랜드', 'electroland', '일렉트로마트', 'electromart']
        if any(kw in merchant_lower for kw in electronics_keywords):
            if category != "생활용품":
                logger.info(f"Rule correction: {merchant_name} → 생활용품 (was: {category})")
                return {"category": "생활용품", "subcategory": "가전제품", "confidence": 0.90}

        # Rule 7: High amount adjustments (likely home appliances or furniture)
        if amount >= 500000 and category in ["마트/편의점", "기타"]:
            logger.info(f"Rule correction: High amount {amount} → 생활용품")
            return {"category": "생활용품", "subcategory": "가전제품", "confidence": 0.80}

        # No correction needed
        return {"category": category, "subcategory": subcategory, "confidence": confidence}
    
    async def classify_single(
        self,
        merchant_name: str,
        amount: float,
        timestamp: Optional[datetime] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Classify a single expense transaction using GPT-5-nano with CoT and structured outputs

        Process:
        1. Use Chain of Thought (CoT) for internal reasoning
        2. Apply structured output schema
        3. Apply rule-based post-processing for edge cases
        4. Return only final classification (without reasoning)
        """
        try:
            # Build category information for the prompt
            category_info = "\n".join([
                f"- {cat}: {', '.join(subcats)}"
                for cat, subcats in self.categories.items()
            ])

            # Enhanced system prompt with role definition and rubric
            system_prompt = f"""당신은 한국 소비자 금융 거래 카테고리 분류 전문가입니다.

## 역할 (Role)
- 가맹점 정보, 거래 금액, 거래 시간을 기반으로 13개 카테고리 중 가장 적합한 카테고리를 선택합니다.
- 단계별 추론(Chain of Thought)을 통해 신중하게 판단합니다.
- 경계가 애매한 케이스는 브랜드, 금액, 문맥을 종합적으로 고려합니다.

## 카테고리 정의
{category_info}

{self._get_category_guidelines()}

## 응답 형식
- reasoning: 단계별 추론 과정 (내부용, 외부 노출 안 됨)
- category: 선택한 주 카테고리
- subcategory: 선택한 세부 카테고리
- confidence: 분류 신뢰도 (0.0 ~ 1.0)

## 신뢰도 기준
- 0.9 이상: 명확한 브랜드/키워드 매칭
- 0.7~0.9: 강한 추론 근거 존재
- 0.5~0.7: 문맥적 추론
- 0.5 미만: 불확실"""

            # Prepare user message with transaction info
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M") if timestamp else "N/A"
            user_message = f"""가맹점: {merchant_name}
금액: {amount:,.0f}원
일시: {timestamp_str}"""
            if description:
                user_message += f"\n설명: {description}"

            # Build messages with few-shot examples
            messages = [
                {"role": "system", "content": system_prompt}
            ]

            # Add few-shot examples
            messages.extend(self._get_few_shot_examples())

            # Add current transaction
            messages.append({"role": "user", "content": user_message})

            # Call OpenAI API with CoT schema (includes reasoning)
            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=messages,
                response_format=TransactionClassificationWithCoT,
                max_completion_tokens=settings.OPENAI_MAX_TOKENS
            )

            # Extract structured output with reasoning
            result = completion.choices[0].message.parsed

            logger.debug(f"GPT reasoning for {merchant_name}: {result.reasoning}")

            # Apply rule-based post-processing
            corrected = self._apply_rule_based_postprocessing(
                merchant_name=merchant_name,
                amount=amount,
                category=result.category,
                subcategory=result.subcategory,
                confidence=result.confidence
            )

            # Return final classification (without reasoning)
            return {
                "category": corrected["category"],
                "subcategory": corrected["subcategory"],
                "confidence": corrected["confidence"]
            }

        except Exception as e:
            logger.error(f"Classification failed for {merchant_name}: {str(e)}")
            # Fallback to default category
            return {
                "category": "기타",
                "subcategory": "기타",
                "confidence": 0.0
            }
    
    async def process_batch(
        self,
        job_id: str,
        csv_key: str,
        options: Dict[str, Any]
    ):
        """
        Process batch classification job using GPT-5-nano with structured outputs

        This runs as a background task
        """
        import pandas as pd
        import asyncio
        from pathlib import Path

        try:
            # Initialize job
            self.jobs[job_id] = ClassificationJob(
                job_id=job_id,
                status=JobStatus.PROCESSING,
                progress=0.0,
                total_records=0,
                processed_records=0,
                failed_records=0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            # 1. Fetch CSV file from csv-manager service
            logger.info(f"Fetching CSV file for job {job_id}: {csv_key}")

            # For now, assume csv_key is a file_id that we can fetch from csv-manager
            # In production, call the csv-manager service API to get the file
            # Placeholder: Download from MinIO or local storage
            csv_file_path = f"./temp/{csv_key}.csv"

            if not Path(csv_file_path).exists():
                raise FileNotFoundError(f"CSV file not found: {csv_file_path}")

            # 2. Read and parse CSV
            df = pd.read_csv(csv_file_path)
            total_records = len(df)

            self.jobs[job_id].total_records = total_records
            self.jobs[job_id].updated_at = datetime.utcnow()

            # 3. Classify each row
            results = []
            for idx, row in df.iterrows():
                try:
                    merchant_name = row.get('merchant_name', row.get('가맹점', 'Unknown'))
                    amount = float(row.get('amount', row.get('금액', 0)))
                    timestamp_str = row.get('transaction_date_time', row.get('거래일시'))

                    # Parse timestamp if available
                    timestamp = None
                    if timestamp_str and pd.notna(timestamp_str):
                        try:
                            timestamp = pd.to_datetime(timestamp_str)
                        except:
                            pass

                    # Classify transaction
                    classification = await self.classify_single(
                        merchant_name=str(merchant_name),
                        amount=amount,
                        timestamp=timestamp
                    )

                    # Add classification to row
                    row['category'] = classification['category']
                    row['subcategory'] = classification.get('subcategory', '')
                    row['confidence'] = classification['confidence']

                    results.append(row)

                    # Update progress
                    self.jobs[job_id].processed_records = idx + 1
                    self.jobs[job_id].progress = ((idx + 1) / total_records) * 100
                    self.jobs[job_id].updated_at = datetime.utcnow()

                except Exception as e:
                    logger.error(f"Failed to classify row {idx}: {str(e)}")
                    self.jobs[job_id].failed_records += 1

                    # Add error info to row
                    row['category'] = 'Other'
                    row['subcategory'] = 'Error'
                    row['confidence'] = 0.0
                    results.append(row)

            # 4. Save results to CSV
            result_df = pd.DataFrame(results)
            result_file_path = f"{self.results_path}/{job_id}_results.csv"
            result_df.to_csv(result_file_path, index=False, encoding='utf-8-sig')

            # Mark as completed
            self.jobs[job_id].status = JobStatus.COMPLETED
            self.jobs[job_id].progress = 100.0
            self.jobs[job_id].completed_at = datetime.utcnow()
            self.jobs[job_id].result_file = result_file_path

            logger.info(f"Batch processing completed for job {job_id}: {self.jobs[job_id].processed_records}/{total_records} records")

        except Exception as e:
            logger.error(f"Batch processing failed for job {job_id}: {str(e)}")
            if job_id in self.jobs:
                self.jobs[job_id].status = JobStatus.FAILED
                self.jobs[job_id].error_message = str(e)
                self.jobs[job_id].updated_at = datetime.utcnow()
    
    async def get_job_status(self, job_id: str) -> Optional[ClassificationJob]:
        """Get status of classification job"""
        return self.jobs.get(job_id)
    
    async def get_result_file(self, job_id: str, format: str = "csv") -> Optional[str]:
        """Get path to result file"""
        job = self.jobs.get(job_id)
        if not job or job.status != JobStatus.COMPLETED:
            return None
        
        # TODO: Convert to requested format if needed
        return job.result_file
    
    async def get_categories(self) -> Dict[str, List[str]]:
        """Get available categories and subcategories"""
        return self.categories
    
    async def train_model(
        self,
        training_data_key: str,
        model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Train or retrain classification model
        
        Placeholder for model training
        """
        # TODO: Implement actual training logic
        # 1. Load training data
        # 2. Preprocess data
        # 3. Train model
        # 4. Evaluate model
        # 5. Save model
        
        model_id = f"model_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return {
            "model_id": model_id,
            "status": "training",
            "message": "Model training started"
        }