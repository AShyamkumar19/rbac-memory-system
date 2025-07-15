import asyncio
import sys
import os

# Add parent directory to Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.database_client import db_client
from rbac.rbac_controller import RBACController
from models.base_models import UserContext, memory_tier_type, access_scope_type, classification_type
import uuid

async def test_rbac_controller():
    """Test our RBAC controller with different user levels"""
    print("Testing RBAC Controller...")
    
    await db_client.initialize()
    rbac_controller = RBACController(db_client)
    
    # Create test users with different hierarchy levels
    test_users = [
        {
            "name": "CEO",
            "user_context": UserContext(
                user_id=uuid.uuid4(),
                username="ceo_user",
                email="ceo@company.com",
                hierarchy_level=1,
                department_id=uuid.uuid4(),
                project_ids=[uuid.uuid4(), uuid.uuid4()],
                roles=["CEO"],
                permissions=[],
                classification_clearance=classification_type.internal
            )
        },
        {
            "name": "Manager",
            "user_context": UserContext(
                user_id=uuid.uuid4(),
                username="manager_user",
                email="manager@company.com",
                hierarchy_level=2,
                department_id=uuid.uuid4(),
                project_ids=[uuid.uuid4()],
                roles=["Manager"],
                permissions=[],
                classification_clearance=classification_type.internal
            )
        },
        {
            "name": "Employee",
            "user_context": UserContext(
                user_id=uuid.uuid4(),
                username="employee_user",
                email="employee@company.com",
                hierarchy_level=4,
                department_id=uuid.uuid4(),
                project_ids=[uuid.uuid4()],
                roles=["Employee"],
                permissions=[],
                classification_clearance=classification_type.internal
            )
        },
        {
            "name": "Intern",
            "user_context": UserContext(
                user_id=uuid.uuid4(),
                username="intern_user",
                email="intern@company.com",
                hierarchy_level=5,
                department_id=uuid.uuid4(),
                project_ids=[],
                roles=["Intern"],
                permissions=[],
                classification_clearance=classification_type.internal
            )
        }
    ]
    
    memory_tiers = [
        memory_tier_type.short_term,
        memory_tier_type.mid_term,
        memory_tier_type.long_term
    ]
    
    # Test each user against each memory tier
    for user_info in test_users:
        print(f"\nTesting {user_info['name']} (Level {user_info['user_context'].hierarchy_level}):")
        
        for memory_tier in memory_tiers:
            access_result = await rbac_controller.check_memory_access(
                user_info['user_context'],
                memory_tier,
                "read"
            )
            
            if access_result["granted"]:
                scope = access_result.get("scope", "unknown")
                filters = access_result.get("filters", {})
                print(f"  {memory_tier.value}: {scope.value} access")
                if filters:
                    print(f"     Filters: {filters}")
            else:
                print(f"  {memory_tier.value}: {access_result['reason']}")
    
    print("\nRBAC Controller testing completed!")

if __name__ == "__main__":
    asyncio.run(test_rbac_controller())