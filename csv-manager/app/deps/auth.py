"""
Authentication and authorization dependencies
"""
from typing import Literal
from fastapi import HTTPException, status, Depends
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Role type definition
Role = Literal["admin", "user"]


async def get_current_role() -> Role:
    """
    Get current user role.
    
    In development mode (AUTH_ENABLED=False):
    - Always returns "admin" for full access
    
    In production mode (AUTH_ENABLED=True):
    - Would use JWT authentication (not implemented)
    
    Returns:
        Role: "admin" in dev mode
    """
    
    if settings.AUTH_ENABLED:
        # Production mode: Would use proper authentication
        # For now, just return user
        return "user"
    else:
        # Development mode: Always admin for testing
        return "admin"


async def require_admin(role: Role = Depends(get_current_role)) -> Role:
    """
    Dependency to require admin role.
    
    Use this dependency on endpoints that require admin privileges.
    
    Args:
        role: Current user role from get_current_role
    
    Returns:
        Role: The admin role
    
    Raises:
        HTTPException: If user is not an admin (403 Forbidden)
    """
    if role != "admin":
        logger.warning(f"Access denied: User with role '{role}' attempted to access admin endpoint")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return role


async def require_user(role: Role = Depends(get_current_role)) -> Role:
    """
    Dependency to require at least user role.
    
    This allows both 'user' and 'admin' roles.
    Use this for endpoints accessible to all authenticated users.
    
    Args:
        role: Current user role from get_current_role
    
    Returns:
        Role: The current role
    """
    # Both admin and user roles are allowed
    return role


