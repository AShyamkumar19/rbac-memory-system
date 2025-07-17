#!/usr/bin/env python3
"""
Example Python client for RBAC Memory Management System
"""
import requests
import json

class MemoryClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.token = None
        self.headers = {"Content-Type": "application/json"}
    
    def login(self, username, password):
        """Authenticate and get access token"""
        response = requests.post(
            f"{self.base_url}/auth/login",
            json={"username": username, "password": password}
        )
        if response.status_code == 200:
            data = response.json()
            self.token = data["access_token"]
            self.headers["Authorization"] = f"Bearer {self.token}"
            print(f"Logged in as {data['username']}")
            return True
        else:
            print(f"Login failed: {response.status_code}")
            return False
    
    def store_conversation(self, messages, agent_name="AI Assistant"):
        """Store a conversation in memory"""
        data = {
            "messages": messages,
            "agent_name": agent_name
        }
        response = requests.post(
            f"{self.base_url}/memory/store",
            headers=self.headers,
            json=data
        )
        return response.json()
    
    def store_summary(self, summary_text, tags=None, entities=None):
        """Store a summary in memory"""
        data = {
            "summary_text": summary_text,
            "tags": tags or [],
            "entities": entities or {}
        }
        response = requests.post(
            f"{self.base_url}/memory/store",
            headers=self.headers,
            json=data
        )
        return response.json()
    
    def store_document(self, title, content, memory_type="documentation", metadata=None):
        """Store a document in memory"""
        data = {
            "title": title,
            "content": content,
            "memory_type": memory_type,
            "metadata": metadata or {}
        }
        response = requests.post(
            f"{self.base_url}/memory/store",
            headers=self.headers,
            json=data
        )
        return response.json()
    
    def search(self, query, limit=10):
        """Universal search across all memory tiers"""
        response = requests.get(
            f"{self.base_url}/memory/search",
            headers=self.headers,
            params={"query": query, "limit": limit}
        )
        return response.json()
    
    def get_overview(self):
        """Get memory overview and statistics"""
        response = requests.get(
            f"{self.base_url}/memory/overview",
            headers=self.headers
        )
        return response.json()
    
    def semantic_search(self, query, limit=5):
        """Semantic search in long-term documents"""
        response = requests.get(
            f"{self.base_url}/memory/long-term/search/semantic",
            headers=self.headers,
            params={"query": query, "limit": limit}
        )
        return response.json()

# Example usage
if __name__ == "__main__":
    # Initialize client
    client = MemoryClient()
    
    # Login
    if not client.login("authtest", "testpassword123"):
        exit(1)
    
    # Store different types of content
    print("\nStoring content...")
    
    # 1. Store a conversation
    conversation = client.store_conversation([
        {"role": "user", "content": "What's our Q4 revenue target?"},
        {"role": "assistant", "content": "Q4 revenue target is $2.5M based on current projections."}
    ])
    print(f" Conversation stored in: {conversation.get('memory_tier')}")
    
    # 2. Store a summary  
    summary = client.store_summary(
        "Q4 planning meeting completed. Key decisions: increase marketing budget, hire 2 developers, launch new product line.",
        tags=["planning", "Q4", "meeting"],
        entities={"quarter": "Q4", "decisions": 3}
    )
    print(f"Summary stored in: {summary.get('memory_tier')}")
    
    # 3. Store documentation
    document = client.store_document(
        "Development Guidelines",
        "This document outlines coding standards, review processes, and deployment procedures for the development team.",
        memory_type="documentation",
        metadata={"category": "development", "version": "1.0"}
    )
    print(f"📚 Document stored in: {document.get('memory_tier')}")
    
    # Get overview
    print("\nMemory Overview:")
    overview = client.get_overview()
    print(f"Total items: {overview['overview']['total_memory_items']}")
    print(f"Accessible tiers: {overview['overview']['accessible_tiers']}")
    
    # Search examples
    print("\nSearch Examples:")
    
    # Universal search
    search_results = client.search("revenue target")
    print(f"Universal search for 'revenue target': {search_results['total_results']} results")
    
    # Semantic search (if accessible)
    try:
        semantic_results = client.semantic_search("development guidelines")
        print(f"Semantic search for 'development guidelines': {semantic_results['count']} results")
    except:
        print("Semantic search not accessible (hierarchy level restriction)")
    
    print("\nDemo completed!") 