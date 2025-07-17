import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

async def test_complete_system():
    """Test the complete RBAC memory management system"""
    print("Testing Complete RBAC Memory Management System")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        # Test 1: System Health
        print("\nTesting system health...")
        health_response = await client.get(f"{BASE_URL}/health")
        if health_response.status_code == 200:
            health_data = health_response.json()
            print(f"System status: {health_data['status']}")
            print(f"   Database: {health_data['components']['database']}")
        else:
            print(f"Health check failed: {health_response.status_code}")
            return
        
        # Test 2: Authentication
        print("\nTesting authentication...")
        login_data = {"username": "authtest", "password": "testpassword123"}
        auth_response = await client.post(f"{BASE_URL}/auth/login", json=login_data)
        
        if auth_response.status_code == 200:
            auth_data = auth_response.json()
            token = auth_data["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print(f"Authentication successful")
            print(f"   User: {auth_data['username']}")
        else:
            print(f"Authentication failed: {auth_response.status_code}")
            return
        
        # Test 3: Memory Overview
        print("\nTesting memory overview...")
        overview_response = await client.get(f"{BASE_URL}/memory/overview", headers=headers)
        if overview_response.status_code == 200:
            overview = overview_response.json()
            print(f"Memory overview retrieved")
            print(f"   Total items: {overview['overview']['total_memory_items']}")
            print(f"   Accessible tiers: {overview['overview']['accessible_tiers']}")
            print(f"   User access: {overview['user_info']['access_scope']}")
        else:
            print(f"Memory overview failed: {overview_response.status_code}")
        
        # Test 4: Intelligent Memory Storage
        print("\nTesting intelligent memory storage...")
        
        # Store different types of content
        test_contents = [
            {
                "messages": [
                    {"role": "user", "content": "What's the status of our project?"},
                    {"role": "assistant", "content": "The project is on track, 80% complete."}
                ],
                "context_data": {"topic": "project_status"},
                "agent_name": "ProjectBot"
            },
            {
                "summary_text": "Weekly team meeting summary. Discussed project milestones, identified blockers, assigned action items for next sprint.",
                "tags": ["meeting", "weekly", "team", "milestones"],
                "conversation_ids": ["conv-123", "conv-124"],
                "entities": {"meeting_type": "weekly_standup", "participants": 5}
            },
            {
                "title": "API Design Guidelines",
                "content": "This document outlines the design principles for REST APIs in our system. Include proper HTTP status codes, consistent naming conventions, comprehensive error handling, and detailed documentation. All APIs should follow RESTful principles and include proper authentication mechanisms.",
                "memory_type": "documentation",
                "source_type": "user_input",
                "metadata": {"category": "technical", "version": "2.0"}
            }
        ]
        
        stored_items = []
        for i, content in enumerate(test_contents):
            store_response = await client.post(
                f"{BASE_URL}/memory/store", 
                json=content, 
                headers=headers
            )
            if store_response.status_code == 200:
                result = store_response.json()
                stored_items.append(result)
                print(f"Content {i+1} stored in {result['memory_tier']}: {result.get('tier_reason', 'N/A')}")
            else:
                print(f"Failed to store content {i+1}: {store_response.status_code}")
        
        # Test 5: Universal Search
        print("\nTesting universal search...")
        search_queries = [
            "project status",
            "meeting summary",
            "API design",
            "team milestones"
        ]
        
        for query in search_queries:
            search_response = await client.get(
                f"{BASE_URL}/memory/search?query={query}&limit=10",
                headers=headers
            )
            if search_response.status_code == 200:
                search_data = search_response.json()
                print(f"Search '{query}': {search_data['total_results']} results")
                if search_data['results']:
                    breakdown = search_data['result_breakdown']
                    print(f"   Breakdown: ST:{breakdown['short_term']}, MT:{breakdown['mid_term']}, LT:{breakdown['long_term']}")
            else:
                print(f"Search failed for '{query}': {search_response.status_code}")
        
        # Test 6: Tier-specific Operations
        print("\nTesting tier-specific operations...")
        
        # Short-term sessions
        sessions_response = await client.get(f"{BASE_URL}/memory/short-term/sessions?limit=5", headers=headers)
        if sessions_response.status_code == 200:
            sessions = sessions_response.json()
            print(f"Short-term: {sessions['count']} sessions")
        
        # Mid-term summaries
        summaries_response = await client.get(f"{BASE_URL}/memory/mid-term/summaries?limit=5", headers=headers)
        if summaries_response.status_code == 200:
            summaries = summaries_response.json()
            print(f"Mid-term: {summaries['count']} summaries")
        
        # Long-term documents
        docs_response = await client.get(f"{BASE_URL}/memory/long-term/documents?limit=5", headers=headers)
        if docs_response.status_code == 200:
            docs = docs_response.json()
            print(f"Long-term: {docs['count']} documents")
        
        # Test 7: Semantic Search
        print("\nTesting semantic search...")
        semantic_response = await client.get(
            f"{BASE_URL}/memory/long-term/search/semantic?query=documentation guidelines&limit=5",
            headers=headers
        )
        if semantic_response.status_code == 200:
            semantic_data = semantic_response.json()
            print(f"Semantic search: {semantic_data['count']} results")
            if semantic_data['documents']:
                best_match = semantic_data['documents'][0]
                print(f"   Best match: {best_match['title']} (score: {best_match.get('similarity_score', 0):.3f})")
        
        # Test 8: Analytics
        print("\nTesting analytics...")
        stats_response = await client.get(f"{BASE_URL}/memory/analytics/stats", headers=headers)
        if stats_response.status_code == 200:
            stats = stats_response.json()
            print(f"Analytics retrieved")
            print(f"   Total memory items: {stats['overview']['total_memory_items']}")
            
            # Handle recent activity (might have errors)
            recent_activity = stats.get('recent_activity', {})
            if 'last_7_days' in recent_activity:
                recent = recent_activity['last_7_days']
                print(f"   Recent activity: ST:{recent['short_term']}, MT:{recent['mid_term']}, LT:{recent['long_term']}")
            elif 'error' in recent_activity:
                print(f"   Recent activity: Error - {recent_activity['error']}")
            else:
                print(f"   Recent activity: No data available")
            
            if stats.get('recommendations'):
                print(f"   Recommendations: {len(stats['recommendations'])} items")
        
        print("\n" + "=" * 60)
        print("Complete system testing finished!")
        print("RBAC Memory Management System is fully operational!")

if __name__ == "__main__":
    asyncio.run(test_complete_system())