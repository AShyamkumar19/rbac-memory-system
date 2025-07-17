import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from storage.database_client import db_client
from rbac.rbac_controller import RBACController
from memory.long_term_controller import LongTermController
from models.base_models import UserContext, classification_type
import uuid
import hashlib

async def create_test_user(user_context: UserContext):
    """Create a test user in the database"""
    try:
        # Create department
        await db_client.fetchval(
            """
            INSERT INTO departments (department_id, department_name, department_code)
            VALUES ($1, $2, $3)
            ON CONFLICT (department_id) DO NOTHING
            RETURNING department_id
            """,
            user_context.department_id,
            f"Test Department {user_context.username}",
            f"DEPT-{str(user_context.department_id)[:4]}"
        )
        
        # Create user
        password_hash = hashlib.sha256("test_password".encode()).hexdigest()
        await db_client.fetchval(
            """
            INSERT INTO users (
                user_id, username, email, password_hash, 
                first_name, last_name, department_id, classification_level, is_active
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (user_id) DO NOTHING
            RETURNING user_id
            """,
            user_context.user_id, user_context.username, user_context.email,
            password_hash, user_context.username.split('_')[0].title(), "User",
            user_context.department_id, user_context.classification_level.value, True
        )
        
        # Create projects and assign user
        for project_id in user_context.project_ids:
            await db_client.fetchval(
                """
                INSERT INTO projects (project_id, project_name, project_code)
                VALUES ($1, $2, $3)
                ON CONFLICT (project_id) DO NOTHING
                RETURNING project_id
                """,
                project_id, f"Test Project {user_context.username}",
                f"PRJ-{str(project_id)[:5]}"
            )
            
            await db_client.execute(
                """
                INSERT INTO project_members (project_id, user_id, role_in_project)
                VALUES ($1, $2, $3)
                ON CONFLICT (project_id, user_id) DO NOTHING
                """,
                project_id, user_context.user_id, "member"
            )
        
        print(f"Created test user: {user_context.username}")
        return True
    except Exception as e:
        print(f"Failed to create user {user_context.username}: {e}")
        return False

async def test_long_term_controller():
    """Test the long-term memory controller"""
    print("Testing Long-Term Memory Controller...")
    
    await db_client.initialize()
    
    # Create controllers
    rbac_controller = RBACController(db_client)
    long_term_controller = LongTermController(db_client, rbac_controller)
    
    # Create test user with unique identifiers
    unique_suffix = str(uuid.uuid4())[:8]
    test_user = UserContext(
        user_id=uuid.uuid4(),
        username=f"long_test_user_{unique_suffix}",
        email=f"longtest_{unique_suffix}@example.com",
        hierarchy_level=3,
        department_id=uuid.uuid4(),
        project_ids=[uuid.uuid4()],
        roles=["Employee"],
        permissions=[],
        classification_level=classification_type.internal
    )
    
    try:
        # Setup test user
        await create_test_user(test_user)
        
        # Test 1: Store documents
        print("\nTesting store_document...")
        
        documents = [
            {
                "title": "API Documentation",
                "content": "This document describes the REST API endpoints for our memory management system. It includes authentication methods, RBAC integration, and example requests and responses.",
                "memory_type": "documentation",
                "source_type": "user_input",
                "metadata": {"category": "technical", "version": "1.0"}
            },
            {
                "title": "Security Policy",
                "content": "Company security policy outlines data classification levels, access control procedures, and incident response protocols. All employees must follow these guidelines.",
                "memory_type": "policy", 
                "source_type": "document_upload",
                "metadata": {"category": "security", "mandatory": True}
            },
            {
                "title": "Project Planning Guide",
                "content": "Step-by-step guide for project planning including timeline creation, resource allocation, risk assessment, and stakeholder communication strategies.",
                "memory_type": "procedure",
                "source_type": "user_input", 
                "metadata": {"category": "management", "difficulty": "intermediate"}
            }
        ]
        
        stored_docs = []
        for i, doc in enumerate(documents):
            try:
                result = await long_term_controller.store_document(test_user, doc)
                stored_docs.append(result)
                print(f"Document {i+1} stored: {result['memory_id']}")
                print(f"   Keywords: {result.get('keywords', [])}")
            except Exception as e:
                print(f"Failed to store document {i+1}: {e}")
        
        # Test 2: Retrieve documents
        print("\nTesting retrieve_documents...")
        try:
            docs = await long_term_controller.retrieve_documents(test_user, limit=10)
            print(f"Retrieved {len(docs)} documents")
            if docs:
                print(f"    First doc: {docs[0]['title']}")
        except Exception as e:
            print(f"Failed to retrieve documents: {e}")
        
        # Test 3: Semantic search
        print("\nTesting semantic_search...")
        search_queries = [
            "API authentication security",
            "project planning timeline",
            "data classification policy"
        ]
        
        for query in search_queries:
            try:
                results = await long_term_controller.semantic_search(test_user, query, limit=5)
                print(f"Query '{query}': Found {len(results)} results")
                if results:
                    best_match = results[0]
                    print(f"    Best match: {best_match['title']} (similarity: {best_match['similarity_score']:.3f})")
            except Exception as e:
                print(f"Search failed for '{query}': {e}")
        
        # Test 4: Advanced filtering
        print("\nTesting advanced filtering...")
        filters = [
            {"memory_type": "documentation"},
            {"keywords": ["security", "policy"]},
            {"content_search": "project"},
            {"min_word_count": 20}
        ]
        
        for filter_set in filters:
            try:
                results = await long_term_controller.retrieve_documents(test_user, filters=filter_set, limit=5)
                print(f"Filter {filter_set}: Found {len(results)} documents")
            except Exception as e:
                print(f"Filter failed {filter_set}: {e}")
        
        # Test 5: Get document by ID
        print("\nTesting get_document_by_id...")
        if stored_docs:
            try:
                doc = await long_term_controller.get_document_by_id(test_user, stored_docs[0]['memory_id'])
                print(f"Retrieved document: {doc['title']}")
                print(f"   Word count: {doc['word_count']}")
            except Exception as e:
                print(f"Failed to get document by ID: {e}")
        
        # Test 6: Memory statistics
        print("\nTesting get_memory_stats...")
        try:
            stats = await long_term_controller.get_memory_stats(test_user)
            print(f"Memory stats:")
            print(f"   Total documents: {stats['total_documents']}")
            print(f"   Document types: {stats['document_types']}")
            print(f"   Average words: {stats['avg_word_count']:.1f}")
            print(f"   Access level: {stats['user_access_level']}")
        except Exception as e:
            print(f"Failed to get memory stats: {e}")
        
        print("\nLong-term memory controller testing completed!")
        
    finally:
        # Cleanup - delete in correct order due to foreign key constraints
        # First delete documents that reference the user
        await db_client.execute("DELETE FROM rbac_long_term_memory WHERE created_by = $1", test_user.user_id)
        # Then delete user and related data
        await db_client.execute("DELETE FROM users WHERE user_id = $1", test_user.user_id)
        await db_client.execute("DELETE FROM departments WHERE department_id = $1", test_user.department_id)
        for project_id in test_user.project_ids:
            await db_client.execute("DELETE FROM projects WHERE project_id = $1", project_id)
        print("Cleaned up test data")

if __name__ == "__main__":
    asyncio.run(test_long_term_controller())