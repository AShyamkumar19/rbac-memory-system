from models.base_models import UserContext, memory_tier_type, access_scope_type, classification_type
from storage.database_client import DatabaseClient
from rbac.rbac_controller import RBACController
from fastapi import HTTPException
import logging
from typing import Dict, List, Optional
import uuid
import json

logger = logging.getLogger(__name__)

class MidTermController:
    """
    Handles mid-term memory operations (summaries, decisions, insights)
    """

    def __init__(self, db_client: DatabaseClient, rbac_controller: RBACController):
        self.db_client = db_client
        self.rbac_controller = rbac_controller
        self.memory_tier = memory_tier_type.mid_term  # Different from short-term!

    async def store_summary(self, user_context: UserContext, summary_data: Dict):
        """
        Store a mid-term memory summary

        Args:
            user_context: UserContext
            summary_data: Dict (summary_text, tags, conversation_ids, etc.)

        Returns:
            Dict with summary_id and status
        """
        try:
            # Step 1: Check RBAC permissions
            access_result = await self.rbac_controller.check_memory_access(
                user_context, self.memory_tier, "write"
            )
            if not access_result["granted"]:
                raise HTTPException(status_code=403, detail=access_result["reason"])
            
            # Step 2: Validate summary data
            summary_text = summary_data.get("summary_text", "")
            if not summary_text:
                raise HTTPException(status_code=400, detail="No summary text provided")
            
            # Step 3: Prepare data for database
            project_id = user_context.project_ids[0] if user_context.project_ids else None
            
            # Step 4: Store in database - This is where mid-term is different!
            summary_id = await self.db_client.fetchval(
                """
                INSERT INTO rbac_mid_term_memory 
                (user_id, summary_text, conversation_ids, tags, entities,
                 project_id, department_id, classification_level, access_scope)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING summary_id
                """,
                user_context.user_id,
                summary_data.get("summary_text"),
                summary_data.get("conversation_ids", []),  # Array of UUIDs
                summary_data.get("tags", []),               # Array of strings
                json.dumps(summary_data.get("entities", {})),  # JSONB field
                project_id,
                user_context.department_id,
                user_context.classification_level.value,
                summary_data.get("access_scope", "project")  # Default to project level
            )
            
            return {
                "summary_id": str(summary_id),
                "status": "success",
                "message": "Summary stored successfully"
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error storing summary: {e}")
            raise HTTPException(status_code=500, detail="Failed to store summary")

    async def retrieve_summaries(self, user_context: UserContext, filters: Dict = None, limit: int = 50):
        """
        Retrieve mid-term memory summaries

        Args:
            user_context: UserContext
            filters: Dict (optional filters like tags, date_range, etc.)
            limit: int (number of summaries to retrieve)

        Returns:
            List[Dict]: List of memory summaries
        """
        try:
            # Step 1: Check RBAC permissions
            access_result = await self.rbac_controller.check_memory_access(
                user_context, self.memory_tier, "read"
            )
            if not access_result["granted"]:
                raise HTTPException(status_code=403, detail=access_result["reason"])
            
            # Step 2: Build query with RBAC filters + user filters
            user_filters = filters or {}
            rbac_filters = access_result["filters"]
            
            # Build WHERE clause dynamically
            where_conditions = []
            params = []
            param_count = 0
            
            # RBAC filters
            if 'user_id' in rbac_filters:
                param_count += 1
                where_conditions.append(f"user_id = ${param_count}")
                params.append(rbac_filters['user_id'])
            
            if 'project_id__in' in rbac_filters:
                param_count += 1
                where_conditions.append(f"project_id = ANY(${param_count})")
                params.append(rbac_filters['project_id__in'])
            
            if 'department_id' in rbac_filters:
                param_count += 1
                where_conditions.append(f"department_id = ${param_count}")
                params.append(rbac_filters['department_id'])
            
            # User filters (this is what makes mid-term special!)
            if 'tags' in user_filters:
                param_count += 1
                where_conditions.append(f"tags && ${param_count}")  # Array overlap operator
                params.append(user_filters['tags'])
            
            if 'date_from' in user_filters:
                param_count += 1
                where_conditions.append(f"timestamp >= ${param_count}")
                params.append(user_filters['date_from'])
            
            if 'date_to' in user_filters:
                param_count += 1
                where_conditions.append(f"timestamp <= ${param_count}")
                params.append(user_filters['date_to'])
            
            # Add limit
            param_count += 1
            params.append(limit)
            
            # Build final query
            where_clause = " AND ".join(where_conditions) if where_conditions else "TRUE"
            query = f"""
                SELECT summary_id, user_id, summary_text, conversation_ids, tags,
                       entities, project_id, department_id, classification_level,
                       access_scope, timestamp, created_at
                FROM rbac_mid_term_memory 
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ${param_count}
            """
            
            # Step 3: Execute query
            summaries = await self.db_client.fetchall(query, *params)
            
            # Step 4: Convert to dict format and parse JSON fields
            result = []
            for summary in summaries:
                summary_dict = dict(summary)
                # Parse JSON fields back to Python objects
                if summary_dict.get('entities'):
                    summary_dict['entities'] = json.loads(summary_dict['entities'])
                result.append(summary_dict)
            
            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving summaries: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve summaries")

    async def search_by_tags(self, user_context: UserContext, tags: List[str], limit: int = 50):
        """
        Search summaries by tags (convenience method)
        
        Args:
            user_context: UserContext
            tags: List of tags to search for
            limit: Maximum number of results
            
        Returns:
            List[Dict]: Matching summaries
        """
        filters = {"tags": tags}
        return await self.retrieve_summaries(user_context, filters, limit)
    