from jose import jwt, JWTError
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import uuid
import os
from dotenv import load_dotenv

from config import settings

load_dotenv()

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token

    Args:
        data: Dictionary containing the payload data (usually user_id)
        expires_delta: timedelta for token expiration

    Returns:
        str: JWT access token
    """

    copy_data = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    copy_data.update({"exp": expire, "iat": datetime.utcnow()})
    token = jwt.encode(copy_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a JWT access token

    Args:
        token: JWT access token

    Returns:
        Dict[str, Any]: Decoded token data if valid, None if invalid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
    
def extract_user_id(token: str) -> Optional[str]:
    """
    Extract the user ID from a JWT access token

    Args:
        token: JWT access token

    Returns:
        Optional[str]: User ID if valid, None if invalid
    """
    payload = verify_token(token)
    return payload.get('user_id') if payload else None
