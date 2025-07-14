import asyncio
import httpx
import json
import uuid
from storage.database_client import db_client
from rbac.user_manager import UserManager
from models.base_models import UserCreate, classification_type

BASE_URL = "http://localhost:8000"

async def setup_test_user():
    """Create a test user for authentication testing"""
    print("Setting up test user...")
    
    try:
        await db_client.initialize()
        user_manager = UserManager(db_client)
        
        # Generate unique username to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        username = f"authtest_{unique_id}"
        
        # Create test user with unique username
        test_user = UserCreate(
            username=username,
            email=f"authtest_{unique_id}@example.com",
            first_name="Auth",
            last_name="Test",
            password="testpassword123",
            classification_level=classification_type.internal
        )
        
        user_id = await user_manager.create_user(test_user)
        print(f"Test user created: {user_id}")
        print(f"  Username: {username}")
        return test_user
        
    except Exception as e:
        print(f"Error setting up test user: {e}")
        return None

async def test_auth_endpoints():
    """Test our authentication endpoints"""
    print("Testing Authentication Endpoints...")
    
    # Step 1: Setup test user
    test_user = await setup_test_user()
    if not test_user:
        print("Failed to create test user")
        return
    
    async with httpx.AsyncClient() as client:
        # Step 2: Test login endpoint
        print("\n1. Testing login endpoint...")
        
        login_data = {
            "username": test_user.username,
            "password": test_user.password
        }
        
        response = await client.post(f"{BASE_URL}/auth/login", json=login_data)
        
        if response.status_code == 200:
            login_result = response.json()
            print(f"Login successful!")
            print(f"   Token: {login_result['access_token'][:50]}...")
            print(f"   User ID: {login_result['user_id']}")
            print(f"   Username: {login_result['username']}")
            
            # Store token for next test
            access_token = login_result['access_token']
            
        else:
            print(f"Login failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return
        
        # Step 3: Test profile endpoint
        print("\n2. Testing profile endpoint...")
        
        headers = {"Authorization": f"Bearer {access_token}"}
        profile_response = await client.get(f"{BASE_URL}/auth/me", headers=headers)
        
        if profile_response.status_code == 200:
            profile_data = profile_response.json()
            print(f"Profile retrieved successfully!")
            print(f"   Name: {profile_data['first_name']} {profile_data['last_name']}")
            print(f"   Email: {profile_data['email']}")
            print(f"   Roles: {profile_data['roles']}")
            print(f"   Classification: {profile_data['classification_level']}")
            
        else:
            print(f"Profile retrieval failed: {profile_response.status_code}")
            print(f"   Error: {profile_response.text}")
        
        # Step 4: Test invalid token
        print("\n3. Testing invalid token...")
        
        invalid_headers = {"Authorization": "Bearer invalid.token.here"}
        invalid_response = await client.get(f"{BASE_URL}/auth/me", headers=invalid_headers)
        
        if invalid_response.status_code == 401:
            print("Invalid token correctly rejected")
        else:
            print(f"Invalid token was accepted: {invalid_response.status_code}")
        
        # Step 5: Test missing token
        print("\n4. Testing missing token...")
        
        no_auth_response = await client.get(f"{BASE_URL}/auth/me")
        
        if no_auth_response.status_code == 401:
            print("Missing token correctly rejected")
        else:
            print(f"Missing token was accepted: {no_auth_response.status_code}")
        
        # Step 6: Test invalid login
        print("\n5. Testing invalid login...")
        
        invalid_login = {
            "username": "nonexistent",
            "password": "wrongpassword"
        }
        
        invalid_login_response = await client.post(f"{BASE_URL}/auth/login", json=invalid_login)
        
        if invalid_login_response.status_code == 401:
            print("Invalid login correctly rejected")
        else:
            print(f"Invalid login was accepted: {invalid_login_response.status_code}")
    
    print("\nAuthentication endpoint testing completed!")

if __name__ == "__main__":
    asyncio.run(test_auth_endpoints())