from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from models.base_models import LoginRequest, LoginResponse, UserProfileResponse
from rbac.user_manager import UserManager, UserContext
from storage.database_client import DatabaseClient, get_db_client
from utils.jwt_util import create_access_token
from api.dependencies import authenticate_user
from config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db_client: DatabaseClient = Depends(get_db_client)) -> LoginResponse:
    """Endpoint for user login and return jwt token"""
    try:
        user_manager = UserManager(db_client)
        user_context = await user_manager.authenticate_user(request.username, request.password)
        if not user_context:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        
        new_token = create_access_token({"user_id": str(user_context['user_id'])})
        return LoginResponse(
            access_token=new_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_id=str(user_context['user_id']),
            username=user_context['username'],
        )
    except HTTPException as e:
        logger.error(f"Error logging in user: {e}")
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error logging in user",
        )

@router.get("/me", response_model=UserProfileResponse)
async def get_current_user(user_context: UserContext = Depends(authenticate_user), db_client: DatabaseClient = Depends(get_db_client)) -> UserProfileResponse:
    """Get current user profile"""
    try:
        user_manager = UserManager(db_client)
        user_data = await user_manager.get_user_by_id(user_context.user_id)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
            )
        
        return UserProfileResponse(
            user_id=user_data.user_id,
            username=user_data.username,
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            department_id=str(user_data.department_id) if user_data.department_id else None,
            department_name=user_data.department_name,
            roles=user_data.roles,
            classification_level=user_data.classification_level,
            is_active=user_data.is_active,
            last_login=None  # This field is not in the current query
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error getting user profile",
        )

