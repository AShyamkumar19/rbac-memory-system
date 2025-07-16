import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from storage.database_client import db_client
from rbac.rbac_controller import RBACController
from memory.short_term_controller import ShortTermController
from models.base_models import UserContext, classification_type
import uuid
import hashlib

async def create_test_user(user_context: UserContext):
    """Create a test user in the database"""
    try:
        # Create a department first if it doesn't exist
        await db_client.fetchval(
            """
            INSERT INTO departments (department_id, department_name, department_code)
            VALUES ($1, $2, $3)
            ON CONFLICT (department_id) DO NOTHING
            RETURNING department_id
            """,
            user_context.department_id,
            f"Test Department {user_context.username}",
            f"DEPT-{user_context.username.upper()[:4]}"  # Limit to 10 chars total
        )
        
        # Create the user
        password_hash = hashlib.sha256("test_password".encode()).hexdigest()
        user_id = await db_client.fetchval(
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
            user_context.username.split('_')[0].title(),  # first_name
            "User",  # last_name
            user_context.department_id,
            user_context.classification_level.value,  # Use .value for enum
            True
        )
        
        # Create projects if they exist
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
                f"PRJ-{user_context.username.upper()[:5]}"  # Limit length
            )
            
            # Add user to project
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
            # Delete user (will cascade to session memory)
            await db_client.execute(
                "DELETE FROM users WHERE user_id = $1",
                user_context.user_id
            )
            
            # Delete department
            await db_client.execute(
                "DELETE FROM departments WHERE department_id = $1",
                user_context.department_id
            )
            
            # Delete projects
            for project_id in user_context.project_ids:
                await db_client.execute(
                    "DELETE FROM projects WHERE project_id = $1",
                    project_id
                )
        
        print("Cleaned up test data")
        
    except Exception as e:
        print(f"Failed to cleanup test data: {e}")

async def test_short_term_controller():
    """Test the short-term memory controller"""
    print("Testing Short-Term Memory Controller...")
    
    await db_client.initialize()
    
    # Create controllers
    rbac_controller = RBACController(db_client)
    short_term_controller = ShortTermController(db_client, rbac_controller)
    
    # Create test user contexts with unique emails
    test_suffix = str(uuid.uuid4())[:8]  # Use first 8 chars of UUID for uniqueness
    
    test_user = UserContext(
        user_id=uuid.uuid4(),
        username=f"test_user_{test_suffix}",
        email=f"test_{test_suffix}@example.com",
        hierarchy_level=3,  # Project level access
        department_id=uuid.uuid4(),
        project_ids=[uuid.uuid4()],
        roles=["Employee"],
        permissions=[],
        classification_level=classification_type.internal
    )
    
    ceo_user = UserContext(
        user_id=uuid.uuid4(),
        username=f"ceo_user_{test_suffix}",
        email=f"ceo_{test_suffix}@example.com",
        hierarchy_level=1,  # Organization level access
        department_id=uuid.uuid4(),
        project_ids=[uuid.uuid4()],
        roles=["CEO"],
        permissions=[],
        classification_level=classification_type.internal
    )
    
    intern_user = UserContext(
        user_id=uuid.uuid4(),
        username=f"intern_user_{test_suffix}",
        email=f"intern_{test_suffix}@example.com",
        hierarchy_level=5,  # Own access only
        department_id=uuid.uuid4(),
        project_ids=[],
        roles=["Intern"],
        permissions=[],
        classification_level=classification_type.internal
    )
    
    all_users = [test_user, ceo_user, intern_user]
    
    try:
        # Step 1: Create test users in database
        print("\nCreating test users in database...")
        for user in all_users:
            success = await create_test_user(user)
            if not success:
                print(f"Failed to create user {user.username}, continuing with test...")
        
        # Test 1: Store session memory
        print("\n1. Testing store_session_memory...")
        session_data = {
            "messages": [
                {"role": "user", "content": "Hello, how are you?"},
                {"role": "assistant", "content": "I'm doing well, thank you!"}
            ],
            "context_data": {"topic": "greeting", "sentiment": "positive"},
            "agent_name": "TestAgent"
        }
        
        try:
            result = await short_term_controller.store_session_memory(test_user, session_data)
            print(f"Session stored: {result}")
        except Exception as e:
            print(f"Failed to store session: {e}")
        
        # Test 2: Retrieve sessions
        print("\n2. Testing retrieve_sessions...")
        try:
            sessions = await short_term_controller.retrieve_sessions(test_user, limit=10)
            print(f"Retrieved {len(sessions)} sessions")
            if sessions:
                print(f"   First session: {sessions[0]['session_id']}")
        except Exception as e:
            print(f"Failed to retrieve sessions: {e}")
        
        # Test 3: Test with different user hierarchy levels
        print("\n3. Testing with different user levels...")
        
        # CEO user (should have broader access)
        try:
            ceo_sessions = await short_term_controller.retrieve_sessions(ceo_user, limit=10)
            print(f"CEO retrieved {len(ceo_sessions)} sessions")
        except Exception as e:
            print(f"CEO failed to retrieve sessions: {e}")
        
        # Intern user (should have limited access)
        try:
            intern_sessions = await short_term_controller.retrieve_sessions(intern_user, limit=10)
            print(f"Intern retrieved {len(intern_sessions)} sessions")
        except Exception as e:
            print(f"Intern failed to retrieve sessions: {e}")
        
        print("\nShort-term memory controller testing completed!")
        
    finally:
        # Clean up test data
        print("\nCleaning up test data...")
        await cleanup_test_users(all_users)

if __name__ == "__main__":
    asyncio.run(test_short_term_controller())