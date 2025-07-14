import asyncio
import logging
import asyncpg
import uuid
import bcrypt
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from storage.database_client import DatabaseClient
from models.base_models import UserCreate, UserUpdate, UserResponse, UserContext, classification_type

logger = logging.getLogger(__name__)

class UserManager:
    """
    Manages user operations and authentication, creation, update, deletion, and retrieval.
    """

    def __init__(self, db_client: DatabaseClient):
        self.db_client = db_client

    def _hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify a password against a hashed password."""
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    
    async def create_user(self, user_create: UserCreate) -> uuid.UUID:
        """Create a new user in the database."""
        try:
            existing_user = await self.db_client.fetchone(
                """
                SELECT user_id FROM users WHERE username = $1
                """,
                user_create.username,
            )

            if existing_user:
                raise ValueError("User already exists")
            
            existing_email = await self.db_client.fetchone(
                """
                SELECT user_id FROM users WHERE email = $1
                """,
                user_create.email,
            )
            if existing_email:
                raise ValueError("Email already exists")
            
            password_hash = self._hash_password(user_create.password)
            employee_id = user_create.employee_id

            user_id = await self.db_client.fetchval(
                """
                INSERT INTO users (
                    username, email, password_hash, first_name, last_name, 
                    department_id, employee_id, classification_level, is_active
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING user_id
                """,
                user_create.username,
                user_create.email,
                password_hash,
                user_create.first_name,
                user_create.last_name,
                user_create.department_id,
                employee_id,
                user_create.classification_level.value,
                user_create.is_active
            )

            return user_id
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None

    async def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate a user and return a user context"""
        try:
            user = await self.db_client.fetchone(
                """
                SELECT user_id, username, email, password_hash, first_name, last_name,
                department_id, is_active, failed_login_attempts, account_locked_until
                FROM users WHERE username = $1
                """,    
                username,
            )
            if not user:
                logger.error(f"User not found: {username}")
                return None
            
            if not self.verify_password(password, user['password_hash']):
                return None
            
            return user
        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            return None
        
    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[UserResponse]:
        """Get a user by their ID"""
        try:
            user = await self.db_client.fetchone(
                """
                SELECT u.user_id, u.username, u.email, u.first_name, u.last_name,
                       u.department_id, u.employee_id, u.classification_level,
                       u.is_active, u.last_login, u.created_at, u.updated_at,
                       d.department_name
                FROM users u
                LEFT JOIN departments d ON u.department_id = d.department_id
                WHERE u.user_id = $1
                """,
                user_id,
            )

            if not user:
                logger.error(f"User not found: {user_id}")
                return None
            
            user_roles = await self.db_client.fetchall(
                """
                SELECT r.role_name
                FROM roles r
                JOIN user_roles ur ON r.role_id = ur.role_id
                WHERE ur.user_id = $1 AND ur.is_active = TRUE
                """,
                user_id
            )

            user_response = UserResponse(
                user_id=user['user_id'],
                username=user['username'],
                email=user['email'],
                first_name=user['first_name'],
                last_name=user['last_name'],
                is_active=user['is_active'],
                department_id=user['department_id'],
                employee_id=user['employee_id'],
                classification_level=user['classification_level'],
                department_name=user['department_name'],
                roles=[role['role_name'] for role in user_roles],
                created_at=user['created_at'],
                updated_at=user['updated_at']
            )

            return user_response
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None
        
    async def get_user_context(self, user_id: uuid.UUID) -> Optional[UserContext]:
        """Get a user context by their ID"""
        try:
            user = await self.db_client.fetchone(
                """
                SELECT user_id, username, email, department_id, classification_level
                FROM users 
                WHERE user_id = $1 AND is_active = TRUE
                """,
                user_id
            )
            
            if not user:
                return None
            
            # Get user roles and hierarchy level
            roles_data = await self.db_client.fetchall(
                """
                SELECT r.role_name, r.hierarchy_level
                FROM user_roles ur
                JOIN roles r ON ur.role_id = r.role_id
                WHERE ur.user_id = $1 AND ur.is_active = TRUE
                  AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
                """,
                user_id
            )
            
            # Get user permissions
            permissions = await self.db_client.fetchall(
                """
                SELECT DISTINCT p.permission_code
                FROM user_roles ur
                JOIN role_permissions rp ON ur.role_id = rp.role_id
                JOIN permissions p ON rp.permission_id = p.permission_id
                WHERE ur.user_id = $1 AND ur.is_active = TRUE
                """,
                user_id
            )
            
            # Get user projects
            projects = await self.db_client.fetchall(
                """
                SELECT DISTINCT p.project_id
                FROM project_members pm
                JOIN projects p ON pm.project_id = p.project_id
                WHERE pm.user_id = $1 AND pm.is_active = TRUE
                  AND p.status = 'active'
                """,
                user_id
            )
            
            # Build user context
            roles = [role['role_name'] for role in roles_data]
            hierarchy_level = min([role['hierarchy_level'] for role in roles_data], default=5)
            permission_codes = [perm['permission_code'] for perm in permissions]
            project_ids = [proj['project_id'] for proj in projects]
            
            return UserContext(
                user_id=user['user_id'],
                username=user['username'],
                email=user['email'],
                department_id=user['department_id'],
                roles=roles,
                permissions=permission_codes,
                hierarchy_level=hierarchy_level,
                project_ids=project_ids,
                classification_level=classification_type(user['classification_level']) 
            )
        except Exception as e:
            logger.error(f"Error getting user context: {e}")
            return None
        
    async def _increment_failed_login_attempts(self, user_id: uuid.UUID):
        """Increment failed login attempts and lock account if needed"""
        try:
            # Get current failed attempts
            failed_attempts = await self.db_client.fetchval(
                "SELECT failed_login_attempts FROM users WHERE user_id = $1",
                user_id
            )
            
            new_attempts = (failed_attempts or 0) + 1
            
            # Lock account if too many failed attempts
            if new_attempts >= 5:  # Maximum 5 attempts
                lock_until = datetime.utcnow() + timedelta(minutes=30)  # Lock for 30 minutes
                await self.db_client.execute(
                    """
                    UPDATE users 
                    SET failed_login_attempts = $1, account_locked_until = $2
                    WHERE user_id = $3
                    """,
                    new_attempts, lock_until, user_id
                )
                logger.warning(f"Account locked due to failed login attempts: {user_id}")
            else:
                await self.db_client.execute(
                    "UPDATE users SET failed_login_attempts = $1 WHERE user_id = $2",
                    new_attempts, user_id
                )
                
        except Exception as e:
            logger.error(f"Error incrementing failed login attempts: {e}")
    
    async def _reset_failed_login_attempts(self, user_id: uuid.UUID):
        """Reset failed login attempts after successful login"""
        try:
            await self.db_client.execute(
                """
                UPDATE users 
                SET failed_login_attempts = 0, account_locked_until = NULL
                WHERE user_id = $1
                """,
                user_id
            )
        except Exception as e:
            logger.error(f"Error resetting failed login attempts: {e}")
            