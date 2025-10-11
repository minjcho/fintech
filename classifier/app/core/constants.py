"""
Application constants for classifier service
Centralized location for all magic numbers to improve code maintainability
"""

# ===== Amount Thresholds =====
HIGH_AMOUNT_THRESHOLD = 500_000  # 50만원 - High-value transaction threshold
# Transactions above this amount in "마트/편의점" or "기타" categories
# are automatically reclassified as "생활용품/가전제품"

# ===== Confidence Score Thresholds =====
# Confidence scores represent the certainty of category classification
CONFIDENCE_VERY_HIGH = 0.95  # Clear brand/keyword match (e.g., Starbucks → 카페)
CONFIDENCE_HIGH = 0.93  # Strong inference basis (e.g., E-Mart → 마트/편의점)
CONFIDENCE_MEDIUM_HIGH = 0.90  # Good contextual match
CONFIDENCE_MEDIUM = 0.85  # Moderate inference (e.g., Olive Young → 패션/미용)
CONFIDENCE_LOW = 0.70  # Weak contextual inference
CONFIDENCE_MINIMUM = 0.50  # Absolute minimum acceptable confidence

# Confidence level guidelines:
# - 0.90+: Clear brand/keyword matching
# - 0.70-0.90: Strong inference with good reasoning
# - 0.50-0.70: Contextual inference
# - Below 0.50: Should be flagged for manual review
