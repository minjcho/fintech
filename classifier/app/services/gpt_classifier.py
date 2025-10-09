"""
Expense Classification using OpenAI GPT API
"""
import openai
from typing import Dict, Any, List, Optional
import json
import logging
from datetime import datetime
import asyncio
from app.models.schemas import JobStatus, ClassificationJob

logger = logging.getLogger(__name__)


class GPTClassifierService:
    """Service for expense classification using OpenAI GPT API"""
    
    def __init__(self, api_key: str = None, model: str = "gpt-4-turbo-preview"):
        self.api_key = api_key
        self.model = model
        self.categories = self._get_categories()
        self.jobs = {}  # In-memory job storage (use Redis in production)
        
        if api_key:
            openai.api_key = api_key
    
    def _get_categories(self) -> List[str]:
        """Get available expense categories"""
        return [
            "Food & Dining",
            "Transportation", 
            "Shopping",
            "Entertainment",
            "Bills & Utilities",
            "Healthcare",
            "Education",
            "Travel",
            "Personal Care",
            "Business",
            "Other"
        ]
    
    async def classify_single(
        self,
        merchant_name: str,
        amount: float,
        timestamp: Optional[datetime] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Classify a single expense using GPT
        """
        try:
            # Prepare prompt for GPT
            prompt = self._create_classification_prompt(
                merchant_name=merchant_name,
                amount=amount,
                timestamp=timestamp,
                description=description
            )
            
            # Call GPT API
            response = await self._call_gpt_api(prompt)
            
            # Parse GPT response
            result = self._parse_gpt_response(response)
            
            return result
            
        except Exception as e:
            logger.error(f"GPT classification failed: {str(e)}")
            # Fallback to rule-based classification
            return self._fallback_classification(merchant_name, amount)
    
    def _create_classification_prompt(
        self,
        merchant_name: str,
        amount: float,
        timestamp: Optional[datetime] = None,
        description: Optional[str] = None
    ) -> str:
        """Create prompt for GPT classification"""
        
        categories_str = ", ".join(self.categories)
        
        prompt = f"""
        Classify the following expense transaction into one of these categories:
        {categories_str}
        
        Transaction details:
        - Merchant: {merchant_name}
        - Amount: ${amount:.2f}
        - Date: {timestamp.strftime('%Y-%m-%d %H:%M:%S') if timestamp else 'N/A'}
        - Description: {description or 'N/A'}
        
        Please respond with a JSON object containing:
        {{
            "category": "selected category from the list",
            "subcategory": "more specific subcategory if applicable",
            "confidence": confidence score between 0 and 1,
            "reasoning": "brief explanation for the classification"
        }}
        
        Response:
        """
        
        return prompt
    
    async def _call_gpt_api(self, prompt: str) -> str:
        """Call OpenAI GPT API"""
        try:
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a financial expense categorization expert. Always respond with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent results
                max_tokens=200
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API call failed: {str(e)}")
            raise
    
    def _parse_gpt_response(self, response: str) -> Dict[str, Any]:
        """Parse GPT response JSON"""
        try:
            # Clean response and parse JSON
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            
            result = json.loads(response)
            
            # Validate response
            if "category" not in result:
                raise ValueError("Missing category in response")
            
            # Ensure category is valid
            if result["category"] not in self.categories:
                result["category"] = "Other"
            
            # Set default confidence if missing
            if "confidence" not in result:
                result["confidence"] = 0.8
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GPT response: {e}")
            raise ValueError(f"Invalid JSON response from GPT: {response}")
    
    def _fallback_classification(
        self,
        merchant_name: str,
        amount: float
    ) -> Dict[str, Any]:
        """Fallback classification when GPT is unavailable"""
        merchant_lower = merchant_name.lower()
        
        # Simple keyword-based rules
        rules = {
            "Food & Dining": ["restaurant", "cafe", "food", "coffee", "스타벅스", "맥도날드"],
            "Transportation": ["uber", "taxi", "bus", "subway", "gas", "교통"],
            "Shopping": ["amazon", "store", "mall", "shop", "쿠팡", "11번가"],
            "Entertainment": ["movie", "game", "netflix", "spotify", "cinema"],
            "Bills & Utilities": ["electric", "water", "internet", "phone", "전기"],
        }
        
        for category, keywords in rules.items():
            if any(keyword in merchant_lower for keyword in keywords):
                return {
                    "category": category,
                    "subcategory": None,
                    "confidence": 0.7,
                    "reasoning": "Classified using keyword matching (GPT unavailable)"
                }
        
        return {
            "category": "Other",
            "subcategory": None,
            "confidence": 0.5,
            "reasoning": "Default classification (no matching keywords)"
        }
    
    async def process_batch(
        self,
        job_id: str,
        csv_data: List[Dict[str, Any]],
        options: Dict[str, Any] = None
    ):
        """
        Process batch classification using GPT
        """
        try:
            # Initialize job
            self.jobs[job_id] = ClassificationJob(
                job_id=job_id,
                status=JobStatus.PROCESSING,
                progress=0.0,
                total_records=len(csv_data),
                processed_records=0,
                failed_records=0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            results = []
            batch_size = options.get("batch_size", 10) if options else 10
            
            # Process in batches to avoid rate limits
            for i in range(0, len(csv_data), batch_size):
                batch = csv_data[i:i + batch_size]
                
                # Process each item in batch
                batch_results = await asyncio.gather(*[
                    self.classify_single(
                        merchant_name=item.get("merchant_name", ""),
                        amount=float(item.get("amount", 0)),
                        timestamp=item.get("timestamp"),
                        description=item.get("description")
                    ) for item in batch
                ])
                
                results.extend(batch_results)
                
                # Update progress
                processed = min(i + batch_size, len(csv_data))
                self.jobs[job_id].processed_records = processed
                self.jobs[job_id].progress = (processed / len(csv_data)) * 100
                self.jobs[job_id].updated_at = datetime.utcnow()
                
                # Rate limiting delay
                await asyncio.sleep(1)
            
            # Mark as completed
            self.jobs[job_id].status = JobStatus.COMPLETED
            self.jobs[job_id].progress = 100.0
            self.jobs[job_id].completed_at = datetime.utcnow()
            
            return results
            
        except Exception as e:
            logger.error(f"Batch processing failed for job {job_id}: {str(e)}")
            self.jobs[job_id].status = JobStatus.FAILED
            self.jobs[job_id].error_message = str(e)
            raise
    
    async def get_job_status(self, job_id: str) -> Optional[ClassificationJob]:
        """Get status of classification job"""
        return self.jobs.get(job_id)
    
    async def create_batch_prompt(
        self,
        transactions: List[Dict[str, Any]]
    ) -> str:
        """Create prompt for batch classification"""
        
        categories_str = ", ".join(self.categories)
        
        transactions_str = "\n".join([
            f"{i+1}. Merchant: {t.get('merchant_name', 'N/A')}, Amount: ${t.get('amount', 0):.2f}"
            for i, t in enumerate(transactions)
        ])
        
        prompt = f"""
        Classify the following expense transactions into these categories:
        {categories_str}
        
        Transactions:
        {transactions_str}
        
        Please respond with a JSON array where each item contains:
        {{
            "index": transaction number,
            "category": "selected category",
            "confidence": confidence score between 0 and 1
        }}
        
        Response:
        """
        
        return prompt