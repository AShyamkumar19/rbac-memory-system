from models.base_models import UserContext, memory_tier_type, access_scope_type, classification_type
from storage.database_client import DatabaseClient
from rbac.rbac_controller import RBACController
from fastapi import HTTPException
import logging
from typing import Dict, List, Optional
import uuid
import json

logger = logging.getLogger(__name__)

class ShortTermController:
    """
    Handles short-term memory operations (session, conversation, etc.)
    """

    def __init__(self, db_client: DatabaseClient, rbac_controller: RBACController):
        self.db_client = db_client
        self.rbac_controller = rbac_controller
        self.memory_tier = memory_tier_type.short_term

    async def store_session_memory(self, user_context: UserContext, session_data: Dict):
        """
        Store a short-term memory session

        Args:
            user_context: UserContext
            session_data: Dict (messages, context, etc.)

        Returns:
            Dict with session_id and status
        """
        try:
            # Step 1: Check RBAC permissions
            access_result = await self.rbac_controller.check_memory_access(
                user_context, self.memory_tier, "write"
            )
            if not access_result["granted"]:
                raise HTTPException(status_code=403, detail=access_result["reason"])
            
            # Step 2: Validate session data
            messages = session_data.get("messages", [])
            if not messages:
                raise HTTPException(status_code=400, detail="No messages provided")
            
            # Step 3: Prepare data for database
            project_id = user_context.project_ids[0] if user_context.project_ids else None
            
            # Step 4: Store in database
            session_id = await self.db_client.fetchval(
                """
                INSERT INTO rbac_session_memory 
                (user_id, messages, context_data, agent_name, project_id, department_id, security_level)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING session_id
                """,
                user_context.user_id,
                json.dumps(messages),  # Convert to JSON string for JSONB field
                json.dumps(session_data.get("context_data", {})),  # Convert to JSON string for JSONB field
                session_data.get("agent_name", "AI Assistant"),
                project_id,
                user_context.department_id,
                user_context.classification_level.value
            )
            
            return {
                "session_id": str(session_id),
                "status": "success",
                "message": "Session stored successfully"
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error storing session memory: {e}")
            raise HTTPException(status_code=500, detail="Failed to store memory session")
            
    async def retrieve_sessions(self, user_context: UserContext, limit: int = 50):
        """
        Retrieve short-term memory sessions 

        Args:
            user_context: UserContext
            limit: int (number of sessions to retrieve)

        Returns:
            List[Dict]: List of memory sessions
        """
        try:
            # Step 1: Check RBAC permissions
            access_result = await self.rbac_controller.check_memory_access(
                user_context, self.memory_tier, "read"
            )
            if not access_result["granted"]:
                raise HTTPException(status_code=403, detail=access_result["reason"])
            
            # Step 2: Build query with RBAC filters
            filters = access_result["filters"]
            
            # Build WHERE clause dynamically based on filters
            where_conditions = []
            params = []
            param_count = 0
            
            if 'user_id' in filters:
                param_count += 1
                where_conditions.append(f"user_id = ${param_count}")
                params.append(filters['user_id'])
            
            if 'project_id__in' in filters:
                param_count += 1
                where_conditions.append(f"project_id = ANY(${param_count})")
                params.append(filters['project_id__in'])
            
            if 'department_id' in filters:
                param_count += 1
                where_conditions.append(f"department_id = ${param_count}")
                params.append(filters['department_id'])
            
            # Add limit
            param_count += 1
            params.append(limit)
            
            # Build final query
            where_clause = " AND ".join(where_conditions) if where_conditions else "TRUE"
            query = f"""
                SELECT session_id, user_id, messages, context_data, agent_name, 
                    project_id, department_id, security_level, created_at
                FROM rbac_session_memory 
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_count}
            """
            
            # Step 3: Execute query
            sessions = await self.db_client.fetchall(query, *params)
            
            # Step 4: Convert to dict format
            return [dict(session) for session in sessions]

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving sessions: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve memory sessions")
