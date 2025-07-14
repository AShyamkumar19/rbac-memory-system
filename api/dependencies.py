from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from utils.jwt_util import extract_user_id
from rbac.user_manager import UserManager
from models.base_models import UserContext
from storage.database_client import DatabaseClient, get_db_client
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer()

async def authenticate_user(credentials: HTTPAuthorizationCredentials = Depends(security), db_client: DatabaseClient = Depends(get_db_client)) -> UserContext:
    """
    Authenticate the user using the provided credentials which is the JWT token, 
    this must run before any other protected endpoint
    """
    try:
        token = credentials.credentials
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing token",
                headers={"WWW-Authenticate": "Bearer"},
            )   
        user_id = extract_user_id(token)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user_manager = UserManager(db_client)
        user_context = await user_manager.get_user_context(user_id)

        if not user_context:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user_context
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error authenticating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Error authenticating user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
