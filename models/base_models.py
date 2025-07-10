import uuid
from enum import Enum
from pydantic import BaseModel, Field, EmailStr, SecretStr
from datetime import datetime
from typing import Optional, List, Any, Dict

class access_scope_type(str, Enum):
    own = "own"
    project = "project"
    department = "department"
    organization = "organization"
    session = "session"

class classification_type(str, Enum):
    public = "public"
    internal = "internal"
    confidential = "confidential"
    secret = "secret"

class memory_tier_type(str, Enum):
    short_term = "short_term"
    long_term = "long_term"
    mid_term = "mid_term"

class project_status(str, Enum):
    planning = "planning"
    active = "active"
    completed = "completed"
    on_hold = "on_hold"
    cancelled = "cancelled"

class BaseModelWithTimestamps(BaseModel):
    """Base model with timestamp fields"""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True  # Allows creation from SQLAlchemy models
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=255)
    email: EmailStr = Field(..., unique=True)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    is_active: bool = Field(default=True)
    department_id: Optional[uuid.UUID] = None
    classification_level: classification_type = Field(default=classification_type.internal)

class UserCreate(UserBase):
    ''' Model for creating a new user'''
    password: str = Field(..., min_length=8)
    is_superuser: bool = Field(default=False)
    created_by: Optional[uuid.UUID] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
class UserUpdate(UserBase):
    ''' Model for updating user information'''
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    department_id: Optional[uuid.UUID] = None
    classification_level: Optional[classification_type] = None
    updated_at: Optional[datetime] = None
    
class UserResponse(UserBase, BaseModelWithTimestamps):
    """ Model for user response (no password)"""
    user_id: uuid.UUID 
    employee_id: Optional[str] = None
    department_name: Optional[str] = None
    roles: List[str] = []
    
class UserLogin(BaseModel):
    ''' Model for user login'''
    username: str
    password: str

class TokenResponse(BaseModel):
    """Model for token responses"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    username: str

class UserContext(BaseModel):
    """Complete user context with permissions"""
    user_id: uuid.UUID
    username: str
    email: str
    department_id: Optional[uuid.UUID] = None
    roles: List[str] = []
    permissions: List[str] = []
    hierarchy_level: int = 5
    project_ids: List[uuid.UUID] = []
    session_id: Optional[uuid.UUID] = None
    classification_level: classification_type = Field(default=classification_type.internal)
