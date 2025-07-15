from storage.database_client import DatabaseClient
from models.base_models import UserContext, memory_tier_type, access_scope_type, memory_tier_type, classification_type
from typing import Dict, Any, List, Optional
import logging
from typing import Type

logger = logging.getLogger(__name__)

class RBACController:
    def __init__(self, db_client: DatabaseClient):
        self.db_client = db_client
        
        self.access_matrix = {
            1: {
                # Top level access
                memory_tier_type.short_term: access_scope_type.organization,
                memory_tier_type.long_term: access_scope_type.organization,
                memory_tier_type.mid_term: access_scope_type.organization,
            },
            2: {
                # Department level access
                memory_tier_type.short_term: access_scope_type.department,
                memory_tier_type.long_term: access_scope_type.department,
                memory_tier_type.mid_term: access_scope_type.department,
            },
            3: {
                # User level access
                memory_tier_type.short_term: access_scope_type.project,
                memory_tier_type.long_term: access_scope_type.project,
                memory_tier_type.mid_term: access_scope_type.project,
            },
            4: {
                # User level access
                memory_tier_type.short_term: access_scope_type.project,
                memory_tier_type.long_term: access_scope_type.own,
                memory_tier_type.mid_term: access_scope_type.project,
            },
            5: {
                # Session level access
                memory_tier_type.short_term: access_scope_type.own,
                memory_tier_type.long_term: None,
                memory_tier_type.mid_term: None,
            },


        }

    async def check_memory_access(self, user_context: UserContext, memory_tier: memory_tier_type, action: str = "read"):
        """
        Check if the user has access to the specific memory level

        Args:
            user_context: UserContext
            memory_tier: memory_tier_type (memory tier to check)
            action: str (action to check) (read, write, delete, etc.)
        """
        try:
            user_level = user_context.hierarchy_level

            if user_level not in self.access_matrix:
                return {
                    "granted": False,
                    "reason": f"User level {user_level} not found in access matrix",
                    "filter": {}
                }
            
            allowed_scope = self.access_matrix[user_level].get(memory_tier)

            if allowed_scope is None:
                return {
                    "granted": False,
                    "reason": f"No access to {memory_tier.value} for hierarchy level {user_level}",
                    "filters": {}
                }
        
            filters = self._build_access_filters(user_context, allowed_scope)
        
            return {
            "granted": True,
            "reason": f"Access granted with scope: {allowed_scope.value}",
            "scope": allowed_scope,
            "filters": filters
        }
        
        except Exception as e:
            logger.error(f"Error checking memory access: {e}")
            return {
                "granted": False,
                "reason": "Access check failed",
                "filters": {}
            }


    def _build_access_filters(self, user_context: UserContext, access_scope: access_scope_type) -> Dict[str, Any]:
        """
        Build database filters based on access scope
        
        Args:
            user_context: User's context
            access_scope: The access scope (own, project, department, organization)
            
        Returns:
            Dictionary of filters for database queries
        """
        filters = {}
        
        if access_scope == access_scope_type.own:
            # User can only see their own data
            filters['user_id'] = user_context.user_id
            
        elif access_scope == access_scope_type.project:
            # User can see data from their projects
            filters['project_id__in'] = user_context.project_ids
            
        elif access_scope == access_scope_type.department:
            # User can see data from their department
            filters['department_id'] = user_context.department_id
            
        elif access_scope == access_scope_type.organization:
            # User can see all data (no filters)
            pass
        
        return filters

