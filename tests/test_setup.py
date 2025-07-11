import asyncio
import uuid
from storage.database_client import db_client
from rbac.user_manager import UserManager
from models.base_models import UserCreate, classification_type

async def test_basic_setup():
    """Test our basic setup"""
    print("Testing basic setup...")
    
    # Test database connection
    try:
        await db_client.initialize()
        health = await db_client.health_check()
        print(f"Database connection: {health['status']}")
    except Exception as e:
        print(f"Database connection failed: {e}")
        return
    
    # Test user manager
    try:
        user_manager = UserManager(db_client)
        
        # Create test user with unique username
        unique_id = str(uuid.uuid4())[:8]
        test_user = UserCreate(
            username=f"testuser_{unique_id}",
            email=f"test_{unique_id}@example.com",
            first_name="Test",
            last_name="User",
            password="testpassword123",
            classification_level=classification_type.internal
        )
        
        user_id = await user_manager.create_user(test_user)
        print(f"User created with ID: {user_id}")
        
        if user_id:
            # Test authentication
            auth_result = await user_manager.authenticate_user(f"testuser_{unique_id}", "testpassword123")
            if auth_result:
                print("Authentication successful")
                print(f"Authenticated user: {auth_result.get('username', 'Unknown')}")
            else:
                print("Authentication failed")
            
            # Test getting user context
            context = await user_manager.get_user_context(user_id)
            if context:
                print(f"User context loaded: {context.username}")
                print(f"User roles: {context.roles}")
                print(f"User permissions: {context.permissions}")
                print(f"Classification level: {context.classification_level}")
            else:
                print("Failed to load user context")
        else:
            print("Cannot continue tests - user creation failed")
            
    except Exception as e:
        print(f"User manager test failed: {e}")
    
    print("\nBasic setup test completed!")

if __name__ == "__main__":
    asyncio.run(test_basic_setup())