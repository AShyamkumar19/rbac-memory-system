from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import List, Optional, Dict, Any
import uuid

from models.base_models import UserContext
from memory.unified_controller import UnifiedMemoryController
from memory.short_term_controller import ShortTermController
from memory.mid_term_controller import MidTermController
from memory.long_term_controller import LongTermController
from rbac.rbac_controller import RBACController
from storage.database_client import DatabaseClient, get_db_client
from api.dependencies import authenticate_user

router = APIRouter()

# Dependency to get unified controller
async def get_unified_controller(
    db_client: DatabaseClient = Depends(get_db_client)
) -> UnifiedMemoryController:
    rbac_controller = RBACController(db_client)
    return UnifiedMemoryController(db_client, rbac_controller)

# ==========================================
# UNIFIED MEMORY ENDPOINTS
# ==========================================

@router.get("/search", summary="Universal Memory Search")
async def universal_search(
    query: str = Query(..., description="Search query"),
    limit: int = Query(default=30, le=100, description="Maximum results"),
    user_context: UserContext = Depends(authenticate_user),
    controller: UnifiedMemoryController = Depends(get_unified_controller)
):
    """
    Search across ALL memory tiers simultaneously
    Returns unified results ranked by relevance and recency
    """
    try:
        results = await controller.universal_search(user_context, query, limit)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/store", summary="Intelligent Memory Storage")
async def store_memory_intelligent(
    content: Dict[str, Any] = Body(..., description="Memory content to store"),
    user_context: UserContext = Depends(authenticate_user),
    controller: UnifiedMemoryController = Depends(get_unified_controller)
):
    """
    Intelligently store memory in appropriate tier based on content analysis
    """
    try:
        result = await controller.store_memory_intelligent(user_context, content)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/overview", summary="Complete Memory Overview")
async def get_memory_overview(
    user_context: UserContext = Depends(authenticate_user),
    controller: UnifiedMemoryController = Depends(get_unified_controller)
):
    """
    Get comprehensive overview of all accessible memory across tiers
    """
    try:
        overview = await controller.get_memory_overview(user_context)
        return overview
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/migrate", summary="Migrate Memory Between Tiers")
async def migrate_memory(
    source_tier: str = Body(..., description="Source memory tier"),
    target_tier: str = Body(..., description="Target memory tier"),
    memory_id: str = Body(..., description="Memory ID to migrate"),
    user_context: UserContext = Depends(authenticate_user),
    controller: UnifiedMemoryController = Depends(get_unified_controller)
):
    """
    Migrate memory from one tier to another
    """
    try:
        result = await controller.migrate_memory(user_context, source_tier, target_tier, memory_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# SHORT-TERM MEMORY ENDPOINTS
# ==========================================

@router.post("/short-term/sessions", summary="Store Session")
async def store_session(
    session_data: Dict[str, Any] = Body(...),
    user_context: UserContext = Depends(authenticate_user),
    controller: UnifiedMemoryController = Depends(get_unified_controller)
):
    """Store a new short-term memory session"""
    try:
        result = await controller.short_term.store_session_memory(user_context, session_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/short-term/sessions", summary="Get Sessions")
async def get_sessions(
    limit: int = Query(default=50, le=100),
    user_context: UserContext = Depends(authenticate_user),
    controller: UnifiedMemoryController = Depends(get_unified_controller)
):
    """Retrieve short-term memory sessions"""
    try:
        sessions = await controller.short_term.retrieve_sessions(user_context, limit)
        return {"sessions": sessions, "count": len(sessions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# MID-TERM MEMORY ENDPOINTS
# ==========================================

@router.post("/mid-term/summaries", summary="Store Summary")
async def store_summary(
    summary_data: Dict[str, Any] = Body(...),
    user_context: UserContext = Depends(authenticate_user),
    controller: UnifiedMemoryController = Depends(get_unified_controller)
):
    """Store a new mid-term memory summary"""
    try:
        result = await controller.mid_term.store_summary(user_context, summary_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mid-term/summaries", summary="Get Summaries")
async def get_summaries(
    limit: int = Query(default=50, le=100),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),
    user_context: UserContext = Depends(authenticate_user),
    controller: UnifiedMemoryController = Depends(get_unified_controller)
):
    """Retrieve mid-term memory summaries"""
    try:
        filters = {}
        if tags:
            filters["tags"] = [tag.strip() for tag in tags.split(",")]
        
        summaries = await controller.mid_term.retrieve_summaries(user_context, filters, limit)
        return {"summaries": summaries, "count": len(summaries)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mid-term/search/tags", summary="Search by Tags")
async def search_summaries_by_tags(
    tags: str = Query(..., description="Comma-separated tags"),
    limit: int = Query(default=20, le=100),
    user_context: UserContext = Depends(authenticate_user),
    controller: UnifiedMemoryController = Depends(get_unified_controller)
):
    """Search summaries by tags"""
    try:
        tag_list = [tag.strip() for tag in tags.split(",")]
        results = await controller.mid_term.search_by_tags(user_context, tag_list, limit)
        return {"summaries": results, "count": len(results), "tags": tag_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# LONG-TERM MEMORY ENDPOINTS
# ==========================================

@router.post("/long-term/documents", summary="Store Document")
async def store_document(
    document_data: Dict[str, Any] = Body(...),
    user_context: UserContext = Depends(authenticate_user),
    controller: UnifiedMemoryController = Depends(get_unified_controller)
):
    """Store a new long-term memory document"""
    try:
        result = await controller.long_term.store_document(user_context, document_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/long-term/documents", summary="Get Documents")
async def get_documents(
    limit: int = Query(default=50, le=100),
    memory_type: Optional[str] = Query(None, description="Filter by memory type"),
    keywords: Optional[str] = Query(None, description="Comma-separated keywords"),
    content_search: Optional[str] = Query(None, description="Text search in content"),
    user_context: UserContext = Depends(authenticate_user),
    controller: UnifiedMemoryController = Depends(get_unified_controller)
):
    """Retrieve long-term memory documents"""
    try:
        filters = {}
        if memory_type:
            filters["memory_type"] = memory_type
        if keywords:
            filters["keywords"] = [kw.strip() for kw in keywords.split(",")]
        if content_search:
            filters["content_search"] = content_search
        
        documents = await controller.long_term.retrieve_documents(user_context, filters, limit)
        return {"documents": documents, "count": len(documents)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/long-term/search/semantic", summary="Semantic Search")
async def semantic_search(
    query: str = Query(..., description="Semantic search query"),
    limit: int = Query(default=20, le=100),
    user_context: UserContext = Depends(authenticate_user),
    controller: UnifiedMemoryController = Depends(get_unified_controller)
):
    """Perform semantic search on long-term documents"""
    try:
        results = await controller.long_term.semantic_search(user_context, query, limit)
        return {"documents": results, "count": len(results), "query": query}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/long-term/documents/{memory_id}", summary="Get Document by ID")
async def get_document(
    memory_id: str,
    user_context: UserContext = Depends(authenticate_user),
    controller: UnifiedMemoryController = Depends(get_unified_controller)
):
    """Get a specific document by ID"""
    try:
        document = await controller.long_term.get_document_by_id(user_context, memory_id)
        return document
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/long-term/documents/{memory_id}", summary="Update Document")
async def update_document(
    memory_id: str,
    updates: Dict[str, Any] = Body(...),
    user_context: UserContext = Depends(authenticate_user),
    controller: UnifiedMemoryController = Depends(get_unified_controller)
):
    """Update an existing document"""
    try:
        result = await controller.long_term.update_document(user_context, memory_id, updates)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/long-term/documents/{memory_id}", summary="Delete Document")
async def delete_document(
    memory_id: str,
    user_context: UserContext = Depends(authenticate_user),
    controller: UnifiedMemoryController = Depends(get_unified_controller)
):
    """Delete (archive) a document"""
    try:
        result = await controller.long_term.delete_document(user_context, memory_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# ANALYTICS ENDPOINTS
# ==========================================

@router.get("/analytics/stats", summary="Memory Statistics")
async def get_memory_statistics(
    user_context: UserContext = Depends(authenticate_user),
    controller: UnifiedMemoryController = Depends(get_unified_controller)
):
    """Get comprehensive memory statistics"""
    try:
        stats = await controller.get_memory_overview(user_context)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/long-term/stats", summary="Long-term Memory Statistics")
async def get_long_term_stats(
    user_context: UserContext = Depends(authenticate_user),
    controller: UnifiedMemoryController = Depends(get_unified_controller)
):
    """Get detailed long-term memory statistics"""
    try:
        stats = await controller.long_term.get_memory_stats(user_context)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    