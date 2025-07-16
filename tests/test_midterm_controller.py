import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from storage.database_client import db_client
from rbac.rbac_controller import RBACController
from memory.mid_term_controller import MidTermController
from models.base_models import UserContext, classification_type
import uuid
import hashlib
from datetime import datetime, timedelta

async def create_test_user(user_context: UserContext):
    """Create a test user in the database"""
    try:
        # Create a department first
        await db_client.fetchval(
            """
            INSERT INTO departments (department_id, department_name, department_code)
            VALUES ($1, $2, $3)
            ON CONFLICT (department_id) DO NOTHING
            RETURNING department_id
            """,
            user_context.department_id,
            f"Test Department {user_context.username}",
            f"DEPT-{user_context.username.upper()[:5]}"
        )
        
        # Create the user
        password_hash = hashlib.sha256("test_password".encode()).hexdigest()
        await db_client.fetchval(
            """
            INSERT INTO users (
                user_id, username, email, password_hash, 
                first_name, last_name, department_id, classification_level,
                is_active
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (user_id) DO NOTHING
            RETURNING user_id
            """,
            user_context.user_id,
            user_context.username,
            user_context.email,
            password_hash,
            user_context.username.split('_')[0].title(),
            "User",
            user_context.department_id,
            user_context.classification_level.value,
            True
        )
        
        # Create projects and assign user to them
        for project_id in user_context.project_ids:
            await db_client.fetchval(
                """
                INSERT INTO projects (project_id, project_name, project_code)
                VALUES ($1, $2, $3)
                ON CONFLICT (project_id) DO NOTHING
                RETURNING project_id
                """,
                project_id,
                f"Test Project {user_context.username}",
                f"PRJ-{user_context.username.upper()[:5]}"
            )
            
            await db_client.execute(
                """
                INSERT INTO project_members (project_id, user_id, role_in_project)
                VALUES ($1, $2, $3)
                ON CONFLICT (project_id, user_id) DO NOTHING
                """,
                project_id,
                user_context.user_id,
                "member"
            )
        
        print(f"Created test user: {user_context.username}")
        return True
        
    except Exception as e:
        print(f"Failed to create user {user_context.username}: {e}")
        return False

async def cleanup_test_users(user_contexts):
    """Clean up test users from the database"""
    try:
        for user_context in user_contexts:
            await db_client.execute("DELETE FROM users WHERE user_id = $1", user_context.user_id)
            await db_client.execute("DELETE FROM departments WHERE department_id = $1", user_context.department_id)
            for project_id in user_context.project_ids:
                await db_client.execute("DELETE FROM projects WHERE project_id = $1", project_id)
        print("Cleaned up test data")
    except Exception as e:
        print(f"Failed to cleanup test data: {e}")

async def test_mid_term_controller():
    """Test the mid-term memory controller"""
    print("Testing Mid-Term Memory Controller...")
    
    await db_client.initialize()
    
    # Create controllers
    rbac_controller = RBACController(db_client)
    mid_term_controller = MidTermController(db_client, rbac_controller)
    
    # Create test user contexts
    test_user = UserContext(
        user_id=uuid.uuid4(),
        username="mid_test_user",
        email="midtest@example.com",
        hierarchy_level=3,  # Project level access
        department_id=uuid.uuid4(),
        project_ids=[uuid.uuid4()],
        roles=["Employee"],
        permissions=[],
        classification_level=classification_type.internal
    )
    
    manager_user = UserContext(
        user_id=uuid.uuid4(),
        username="mid_manager",
        email="midmanager@example.com",
        hierarchy_level=2,  # Department level access
        department_id=test_user.department_id,  # Same department
        project_ids=[uuid.uuid4()],
        roles=["Manager"],
        permissions=[],
        classification_level=classification_type.internal
    )
    
    intern_user = UserContext(
        user_id=uuid.uuid4(),
        username="mid_intern",
        email="midintern@example.com",
        hierarchy_level=5,  # Limited access
        department_id=uuid.uuid4(),  # Different department
        project_ids=[],
        roles=["Intern"],
        permissions=[],
        classification_level=classification_type.internal
    )
    
    all_users = [test_user, manager_user, intern_user]
    
    try:
        # Step 1: Create test users in database
        print("\nCreating test users in database...")
        for user in all_users:
            await create_test_user(user)
        
        # Test 1: Store summary data
        print("\nTesting store_summary...")
        
        # Sample summary data with different topics and tags
        summary_samples = [
            {
                "summary_text": "Team discussed implementation of new authentication system. Key decisions: Use JWT tokens, implement role-based access control, target completion by end of sprint.",
                "tags": ["authentication", "security", "sprint-planning"],
                "conversation_ids": [str(uuid.uuid4()), str(uuid.uuid4())],
                "entities": {
                    "technologies": ["JWT", "RBAC"],
                    "timeline": "end of sprint",
                    "decision_type": "technical"
                },
                "access_scope": "project"
            },
            {
                "summary_text": "Marketing campaign review meeting concluded. Results show 15% increase in engagement. Next steps: expand to additional channels, increase budget allocation.",
                "tags": ["marketing", "campaign", "performance"],
                "conversation_ids": [str(uuid.uuid4())],
                "entities": {
                    "metrics": ["15% increase"],
                    "action_items": ["expand channels", "increase budget"],
                    "meeting_type": "review"
                },
                "access_scope": "department"
            },
            {
                "summary_text": "Budget planning session for Q4. Current spend at 78%. Identified cost-saving opportunities in infrastructure. Approved additional hiring for development team.",
                "tags": ["budget", "planning", "Q4", "hiring"],
                "conversation_ids": [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())],
                "entities": {
                    "financial": ["78% spend", "Q4"],
                    "departments": ["infrastructure", "development"],
                    "decisions": ["cost-saving", "hiring approval"]
                },
                "access_scope": "department"
            }
        ]
        
        stored_summaries = []
        
        for i, summary_data in enumerate(summary_samples):
            try:
                result = await mid_term_controller.store_summary(test_user, summary_data)
                stored_summaries.append(result)
                print(f"Summary {i+1} stored: {result['summary_id']}")
            except Exception as e:
                print(f"Failed to store summary {i+1}: {e}")
        
        # Test 2: Retrieve summaries
        print("\nTesting retrieve_summaries...")
        try:
            summaries = await mid_term_controller.retrieve_summaries(test_user, limit=10)
            print(f"Retrieved {len(summaries)} summaries")
            if summaries:
                print(f"First summary: {summaries[0]['summary_text'][:50]}...")
                print(f"Tags: {summaries[0]['tags']}")
        except Exception as e:
            print(f"Failed to retrieve summaries: {e}")
        
        # Test 3: Search by tags
        print("\nTesting search_by_tags...")
        try:
            auth_summaries = await mid_term_controller.search_by_tags(
                test_user, ["authentication", "security"], limit=5
            )
            print(f"Found {len(auth_summaries)} summaries with authentication/security tags")
            
            budget_summaries = await mid_term_controller.search_by_tags(
                test_user, ["budget", "planning"], limit=5
            )
            print(f"Found {len(budget_summaries)} summaries with budget/planning tags")
        except Exception as e:
            print(f"Failed to search by tags: {e}")
        
        # Test 4: Date range filtering
        print("\nTesting date range filtering...")
        try:
            date_filters = {
                "date_from": datetime.now() - timedelta(hours=1),
                "date_to": datetime.now() + timedelta(hours=1)
            }
            recent_summaries = await mid_term_controller.retrieve_summaries(
                test_user, filters=date_filters, limit=10
            )
            print(f"Found {len(recent_summaries)} summaries in date range")
        except Exception as e:
            print(f"Failed to filter by date range: {e}")
        
        # Test 5: Different user access levels
        print("\nTesting different user access levels...")
        
        # Manager should see department-level summaries
        try:
            manager_summaries = await mid_term_controller.retrieve_summaries(manager_user, limit=10)
            print(f"Manager retrieved {len(manager_summaries)} summaries")
        except Exception as e:
            print(f"Manager failed to retrieve summaries: {e}")
        
        # Intern should have limited access
        try:
            intern_summaries = await mid_term_controller.retrieve_summaries(intern_user, limit=10)
            print(f"Intern retrieved {len(intern_summaries)} summaries")
        except Exception as e:
            print(f"Intern failed to retrieve summaries: {e}")
        
        # Test 6: Advanced filtering
        print("\nTesting advanced filtering...")
        try:
            advanced_filters = {
                "tags": ["security", "planning"],  # Summaries with these tags
            }
            filtered_summaries = await mid_term_controller.retrieve_summaries(
                test_user, filters=advanced_filters, limit=10
            )
            print(f"Found {len(filtered_summaries)} summaries with advanced filters")
        except Exception as e:
            print(f"Failed advanced filtering: {e}")
        
        print("\nMid-term memory controller testing completed!")
        
    finally:
        # Clean up test data
        print("\nCleaning up test data...")
        await cleanup_test_users(all_users)

if __name__ == "__main__":
    asyncio.run(test_mid_term_controller())