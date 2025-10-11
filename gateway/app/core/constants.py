"""
Application constants for gateway service
Centralized location for all magic numbers to improve code maintainability
"""

# ===== HTTP Client Timeout Configuration =====
GATEWAY_SHORT_TIMEOUT = 30.0  # Short timeout for quick operations (seconds)
# Used for: Health checks, simple queries

GATEWAY_LONG_TIMEOUT = 120.0  # Long timeout for heavy operations (seconds)
# Used for: Prophet analysis, CSV processing, batch operations

# ===== Retry Configuration =====
MAX_RETRY_ATTEMPTS = 3  # Maximum number of retry attempts for failed requests
RETRY_BACKOFF_FACTOR = 1.0  # Exponential backoff factor (1.0 = linear, 2.0 = exponential)
