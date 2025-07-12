import asyncio
from utils.jwt_util import create_access_token, verify_token, extract_user_id
from datetime import timedelta
import uuid

async def test_jwt_system():
    """Test our JWT system"""
    print("Testing JWT System...")
    
    # Test data
    user_id = str(uuid.uuid4())
    test_data = {
        "user_id": user_id,
        "username": "testuser"
    }
    
    # Test 1: Create token
    print("\n1. Creating JWT token...")
    token = create_access_token(test_data)
    print(f"Token created: {token[:50]}...")
    
    # Test 2: Verify token
    print("\n2. Verifying token...")
    payload = verify_token(token)
    if payload:
        print(f"Token verified: {payload}")
    else:
        print("Token verification failed")
    
    # Test 3: Extract user ID
    print("\n3. Extracting user ID...")
    extracted_id = extract_user_id(token)
    if extracted_id == user_id:
        print(f"User ID extracted correctly: {extracted_id}")
    else:
        print(f"User ID mismatch: {extracted_id} vs {user_id}")
    
    # Test 4: Invalid token
    print("\n4. Testing invalid token...")
    invalid_payload = verify_token("invalid.token.here")
    if invalid_payload is None:
        print("Invalid token correctly rejected")
    else:
        print("Invalid token was accepted")
    
    # Test 5: Short expiration
    print("\n5. Testing token expiration...")
    short_token = create_access_token(test_data, expires_delta=timedelta(seconds=-1))  # Already expired
    expired_payload = verify_token(short_token)
    if expired_payload is None:
        print("Expired token correctly rejected")
    else:
        print("Expired token was accepted")
    
    print("\nJWT testing completed!")

if __name__ == "__main__":
    asyncio.run(test_jwt_system())