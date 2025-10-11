"""
Application constants for analysis service
Centralized location for all magic numbers to improve code maintainability
"""

# ===== Prophet Configuration =====
PROPHET_MIN_DATA_DAYS = 30  # Minimum days of data required for Prophet training
PROPHET_MIN_TRANSACTIONS = 30  # Minimum number of transactions required
PROPHET_FORECAST_PERIODS = 30  # Number of days to forecast into the future
PROPHET_INTERVAL_WIDTH = 0.95  # Confidence interval width (95%)

# ===== ThreadPool Configuration =====
PROPHET_MAIN_WORKERS = 4  # Main Prophet ThreadPool workers for real-time requests
PROPHET_BASELINE_WORKERS = 2  # Baseline Prophet ThreadPool workers for background tasks
# Recommended for 8-core system: 4 (main) + 2 (baseline) + 2 (reserved for other tasks)

# ===== Baseline Analysis =====
BASELINE_MONTHS_COUNT = 11  # Number of historical months to calculate for baseline predictions

# ===== Timeout Configuration =====
ANALYSIS_LOCK_TIMEOUT = 120  # Redis lock timeout in seconds
S3_DOWNLOAD_TIMEOUT = 60  # S3 file download timeout in seconds
DB_QUERY_TIMEOUT = 30  # Database query timeout in seconds

# ===== Cache Configuration =====
REDIS_CACHE_TTL = 86400  # Redis cache TTL: 24 hours in seconds
FILE_METADATA_TTL = 604800  # File metadata TTL: 7 days in seconds

# ===== Category Configuration =====
CATEGORIES = [
    "식비",
    "카페",
    "마트/편의점",
    "문화생활",
    "교통/차량",
    "패션/미용",
    "생활용품",
    "주거/통신",
    "건강/병원",
    "교육",
    "경조사/회비",
    "보험/세금",
    "기타"
]
TOTAL_CATEGORIES = len(CATEGORIES)  # 13 categories
