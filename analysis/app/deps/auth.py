"""
JWT Authentication dependency for analysis service
"""
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")

# Security scheme for Swagger UI
bearer_scheme = HTTPBearer()


class TokenPayload(BaseModel):
    """JWT Token payload structure"""
    iss: str
    sub: str  # user_id
    iat: int
    exp: int
    typ: str
    email: str


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
) -> str:
    """
    Extract and validate user_id from JWT token

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        user_id extracted from token's 'sub' claim

    Raises:
        HTTPException: If token is invalid or expired
    """
    token = credentials.credentials

    try:
        # Decode JWT token
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )

        # Extract user_id from 'sub' claim
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check token expiration
        exp = payload.get("exp")
        if exp and datetime.utcnow().timestamp() > exp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate token type
        typ = payload.get("typ")
        if typ != "ACCESS":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.info(f"Authenticated user_id: {user_id}, email: {payload.get('email')}")
        return str(user_id)

    except JWTError as e:
        logger.error(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_optional_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
) -> Optional[str]:
    """
    Extract user_id from JWT token if provided, otherwise return None

    Args:
        credentials: Optional Bearer token

    Returns:
        user_id if token is valid, None otherwise
    """
    if not credentials:
        return None

    try:
        return get_current_user_id(credentials)
    except HTTPException:
        return None