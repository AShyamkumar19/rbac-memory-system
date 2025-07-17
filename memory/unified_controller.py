from models.base_models import UserContext, memory_tier_type, classification_type
from storage.database_client import DatabaseClient
from rbac.rbac_controller import RBACController
from memory.short_term_controller import ShortTermController
from memory.mid_term_controller import MidTermController
from memory.long_term_controller import LongTermController
from fastapi import HTTPException
import logging
from typing import Dict, List, Optional, Union, Any
import uuid
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)

class UnifiedMemoryController:
    """
    Master controller that orchestrates all memory tiers
    Provides unified interface for memory operations across short, mid, and long-term memory
    """

    def __init__(self, db_client: DatabaseClient, rbac_controller: RBACController):
        self.db_client = db_client
        self.rbac_controller = rbac_controller
        
        # Initialize all memory tier controllers
        self.short_term = ShortTermController(db_client, rbac_controller)
        self.mid_term = MidTermController(db_client, rbac_controller)
        self.long_term = LongTermController(db_client, rbac_controller)

    def _determine_memory_tier(self, content: Dict) -> str:
        """
        Intelligently determine which memory tier content should go to
        
        Args:
            content: Memory content to analyze
            
        Returns:
            Recommended memory tier ('short_term', 'mid_term', 'long_term')
        """
        # Check explicit tier specification
        if 'memory_tier' in content:
            return content['memory_tier']
        
        # Analyze content characteristics
        content_text = content.get('content', content.get('summary_text', content.get('messages', '')))
        
        if isinstance(content_text, list):  # Messages array (short-term)
            return 'short_term'
        
        if isinstance(content_text, str):
            word_count = len(content_text.split())
            
            # Check for summary indicators (mid-term)
            summary_indicators = ['summary', 'decision', 'meeting', 'conclusion', 'key points']
            if any(indicator in content_text.lower() for indicator in summary_indicators):
                return 'mid_term'
            
            # Check for document indicators (long-term)
            document_indicators = ['policy', 'procedure', 'documentation', 'guide', 'manual']
            if any(indicator in content_text.lower() for indicator in document_indicators):
                return 'long_term'
            
            # Based on content length
            if word_count < 50:  # Short conversations
                return 'short_term'
            elif word_count < 500:  # Summaries and insights
                return 'mid_term'
            else:  # Long documents and knowledge
                return 'long_term'
        
        # Default to short-term for unknown content
        return 'short_term'

    def _rank_cross_tier_results(self, all_results: List[Dict]) -> List[Dict]:
        """
        Rank results from different memory tiers using unified scoring
        
        Args:
            all_results: Combined results from all tiers
            
        Returns:
            Ranked results with unified scoring
        """
        for result in all_results:
            score = 0.0
            
            # Base score from similarity if available
            if 'similarity_score' in result:
                score += result['similarity_score'] * 0.4
            
            # Recency bonus (newer content scores higher)
            if 'created_at' in result:
                try:
                    created_at = result['created_at']
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    
                    days_old = (datetime.now() - created_at.replace(tzinfo=None)).days
                    recency_score = max(0, 1 - (days_old / 365))  # Decay over a year
                    score += recency_score * 0.3
                except:
                    pass
            
            # Memory tier bonus (long-term is more authoritative)
            tier_bonus = {
                'long_term': 0.3,
                'mid_term': 0.2,
                'short_term': 0.1
            }
            score += tier_bonus.get(result.get('memory_tier', 'short_term'), 0.1)
            
            # Content quality bonus
            if result.get('word_count', 0) > 100:
                score += 0.1
            
            result['unified_score'] = score
        
        # Sort by unified score
        return sorted(all_results, key=lambda x: x.get('unified_score', 0), reverse=True)

    async def universal_search(self, user_context: UserContext, query: str, limit: int = 30) -> Dict:
        """
        Search across ALL memory tiers simultaneously
        
        Args:
            user_context: User's context
            query: Search query
            limit: Total number of results across all tiers
            
        Returns:
            Unified results from all tiers with metadata
        """
        try:
            logger.info(f"Universal search for user {user_context.username}: '{query}'")
            
            # Search all tiers concurrently
            search_tasks = []
            
            # Short-term search (sessions containing query)
            short_term_task = self._search_short_term(user_context, query, limit // 3)
            search_tasks.append(('short_term', short_term_task))
            
            # Mid-term search (summaries with tags/content)
            mid_term_task = self._search_mid_term(user_context, query, limit // 3)
            search_tasks.append(('mid_term', mid_term_task))
            
            # Long-term semantic search
            long_term_task = self.long_term.semantic_search(user_context, query, limit // 3)
            search_tasks.append(('long_term', long_term_task))
            
            # Execute all searches concurrently
            all_results = []
            search_errors = []
            
            for tier_name, task in search_tasks:
                try:
                    results = await task
                    for result in results:
                        result['memory_tier'] = tier_name
                        result['search_query'] = query
                    all_results.extend(results)
                except Exception as e:
                    logger.error(f"Search failed for {tier_name}: {e}")
                    search_errors.append(f"{tier_name}: {str(e)}")
            
            # Rank and limit results
            ranked_results = self._rank_cross_tier_results(all_results)
            final_results = ranked_results[:limit]
            
            return {
                "query": query,
                "total_results": len(final_results),
                "results": final_results,
                "tiers_searched": [tier for tier, _ in search_tasks],
                "search_errors": search_errors,
                "execution_time": datetime.now().isoformat(),
                "result_breakdown": {
                    tier: len([r for r in final_results if r.get('memory_tier') == tier])
                    for tier in ['short_term', 'mid_term', 'long_term']
                }
            }

        except Exception as e:
            logger.error(f"Universal search failed: {e}")
            raise HTTPException(status_code=500, detail="Universal search failed")

    async def _search_short_term(self, user_context: UserContext, query: str, limit: int) -> List[Dict]:
        """Search short-term memory sessions"""
        try:
            # Get recent sessions and filter by content
            sessions = await self.short_term.retrieve_sessions(user_context, limit=limit * 2)
            
            matching_sessions = []
            for session in sessions:
                # Search in messages content
                messages = session.get('messages', [])
                if isinstance(messages, str):
                    import json
                    try:
                        messages = json.loads(messages)
                    except:
                        messages = []
                
                # Check if query appears in any message
                content_text = ' '.join([
                    msg.get('content', '') for msg in messages 
                    if isinstance(msg, dict) and 'content' in msg
                ])
                
                if query.lower() in content_text.lower():
                    matching_sessions.append({
                        'id': str(session['session_id']),
                        'title': f"Session from {session['created_at']}",
                        'content': content_text[:200] + "..." if len(content_text) > 200 else content_text,
                        'created_at': session['created_at'],
                        'agent_name': session.get('agent_name', 'Unknown'),
                        'similarity_score': 0.7  # Simple text match score
                    })
            
            return matching_sessions[:limit]
        except Exception as e:
            logger.error(f"Short-term search failed: {e}")
            return []

    async def _search_mid_term(self, user_context: UserContext, query: str, limit: int) -> List[Dict]:
        """Search mid-term memory summaries"""
        try:
            # Search by content and tags
            content_results = await self.mid_term.retrieve_summaries(
                user_context, 
                filters={'content_search': query}, 
                limit=limit
            )
            
            # Also search by tags if query is a single word
            tag_results = []
            if len(query.split()) == 1:
                tag_results = await self.mid_term.search_by_tags(
                    user_context, [query.lower()], limit=limit
                )
            
            # Combine and deduplicate
            all_results = content_results + tag_results
            seen_ids = set()
            unique_results = []
            
            for result in all_results:
                result_id = str(result['summary_id'])
                if result_id not in seen_ids:
                    seen_ids.add(result_id)
                    unique_results.append({
                        'id': result_id,
                        'title': f"Summary: {result['summary_text'][:50]}...",
                        'content': result['summary_text'],
                        'tags': result.get('tags', []),
                        'created_at': result.get('timestamp', result.get('created_at')),
                        'similarity_score': 0.8  # Good match for summaries
                    })
            
            return unique_results[:limit]
        except Exception as e:
            logger.error(f"Mid-term search failed: {e}")
            return []

    async def store_memory_intelligent(self, user_context: UserContext, content: Dict) -> Dict:
        """
        Intelligently route memory to appropriate tier based on content type and size
        
        Args:
            user_context: User's context
            content: Memory content with type hints
            
        Returns:
            Storage result with tier information
        """
        try:
            # Determine appropriate memory tier
            recommended_tier = self._determine_memory_tier(content)
            
            logger.info(f"Routing content to {recommended_tier} for user {user_context.username}")
            
            # Route to appropriate controller
            if recommended_tier == 'short_term':
                result = await self.short_term.store_session_memory(user_context, content)
                result['memory_tier'] = 'short_term'
                result['tier_reason'] = 'Conversation/session data'
                
            elif recommended_tier == 'mid_term':
                result = await self.mid_term.store_summary(user_context, content)
                result['memory_tier'] = 'mid_term'
                result['tier_reason'] = 'Summary/insight data'
                
            elif recommended_tier == 'long_term':
                result = await self.long_term.store_document(user_context, content)
                result['memory_tier'] = 'long_term'
                result['tier_reason'] = 'Document/knowledge data'
                
            else:
                raise HTTPException(status_code=400, detail=f"Invalid memory tier: {recommended_tier}")
            
            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Intelligent storage failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to store memory intelligently")

    async def get_memory_overview(self, user_context: UserContext) -> Dict:
        """
        Get comprehensive overview of all accessible memory
        
        Args:
            user_context: User's context
            
        Returns:
            Complete memory statistics and overview
        """
        try:
            logger.info(f"Getting memory overview for user {user_context.username}")
            
            # Get stats from all tiers concurrently
            stats_tasks = [
                self._get_short_term_stats(user_context),
                self._get_mid_term_stats(user_context),
                self.long_term.get_memory_stats(user_context)
            ]
            
            short_stats, mid_stats, long_stats = await asyncio.gather(
                *stats_tasks, return_exceptions=True
            )
            
            # Handle any errors in stats gathering
            if isinstance(short_stats, Exception):
                short_stats = {"accessible": False, "error": str(short_stats)}
            if isinstance(mid_stats, Exception):
                mid_stats = {"accessible": False, "error": str(mid_stats)}
            if isinstance(long_stats, Exception):
                long_stats = {"accessible": False, "error": str(long_stats)}
            
            # Calculate totals
            total_items = (
                short_stats.get('total_sessions', 0) +
                mid_stats.get('total_summaries', 0) +
                long_stats.get('total_documents', 0)
            )
            
            # Recent activity (last 7 days)
            recent_activity = await self._get_recent_activity(user_context)
            
            return {
                "user_info": {
                    "username": user_context.username,
                    "hierarchy_level": user_context.hierarchy_level,
                    "roles": user_context.roles,
                    "access_scope": self._get_user_access_scope(user_context)
                },
                "overview": {
                    "total_memory_items": total_items,
                    "accessible_tiers": self._get_accessible_tiers(user_context),
                    "last_updated": datetime.now().isoformat()
                },
                "tier_breakdown": {
                    "short_term": short_stats,
                    "mid_term": mid_stats,
                    "long_term": long_stats
                },
                "recent_activity": recent_activity,
                "recommendations": self._generate_recommendations(user_context, short_stats, mid_stats, long_stats)
            }

        except Exception as e:
            logger.error(f"Memory overview failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to get memory overview")

    async def _get_short_term_stats(self, user_context: UserContext) -> Dict:
        """Get short-term memory statistics"""
        try:
            sessions = await self.short_term.retrieve_sessions(user_context, limit=1000)
            return {
                "total_sessions": len(sessions),
                "accessible": True,
                "most_recent": sessions[0]['created_at'] if sessions else None
            }
        except Exception as e:
            return {"accessible": False, "error": str(e)}

    async def _get_mid_term_stats(self, user_context: UserContext) -> Dict:
        """Get mid-term memory statistics"""
        try:
            summaries = await self.mid_term.retrieve_summaries(user_context, limit=1000)
            return {
                "total_summaries": len(summaries),
                "accessible": True,
                "most_recent": summaries[0]['created_at'] if summaries else None
            }
        except Exception as e:
            return {"accessible": False, "error": str(e)}

    async def _get_recent_activity(self, user_context: UserContext) -> Dict:
        """Get recent activity across all tiers"""
        try:
            recent_date = datetime.now() - timedelta(days=7)
            
            # Count recent items in each tier
            recent_short = await self.short_term.retrieve_sessions(user_context, limit=100)
            recent_mid = await self.mid_term.retrieve_summaries(
                user_context, 
                filters={"date_from": recent_date}, 
                limit=100
            )
            recent_long = await self.long_term.retrieve_documents(
                user_context, 
                filters={"date_from": recent_date}, 
                limit=100
            )
            
            return {
                "last_7_days": {
                    "short_term": len(recent_short),
                    "mid_term": len(recent_mid),
                    "long_term": len(recent_long)
                },
                "most_active_tier": max(
                    [
                        ("short_term", len(recent_short)),
                        ("mid_term", len(recent_mid)),
                        ("long_term", len(recent_long))
                    ],
                    key=lambda x: x[1]
                )[0]
            }
        except Exception as e:
            return {"error": str(e)}

    def _get_user_access_scope(self, user_context: UserContext) -> str:
        """Determine user's access scope based on hierarchy"""
        if user_context.hierarchy_level <= 1:
            return "organization"
        elif user_context.hierarchy_level <= 2:
            return "department"
        elif user_context.hierarchy_level <= 3:
            return "project"
        else:
            return "own"

    def _get_accessible_tiers(self, user_context: UserContext) -> List[str]:
        """Get list of memory tiers user can access"""
        tiers = ["short_term"]
        
        if user_context.hierarchy_level <= 4:  # Employee and above
            tiers.append("mid_term")
        
        if user_context.hierarchy_level <= 4:  # Employee and above  
            tiers.append("long_term")
        
        return tiers

    def _generate_recommendations(self, user_context: UserContext, short_stats: Dict, mid_stats: Dict, long_stats: Dict) -> List[str]:
        """Generate personalized recommendations"""
        recommendations = []
        
        # Check for data imbalances
        if short_stats.get('total_sessions', 0) > 50 and mid_stats.get('total_summaries', 0) < 5:
            recommendations.append("Consider creating summaries from your recent sessions to build mid-term memory")
        
        if long_stats.get('total_documents', 0) == 0 and user_context.hierarchy_level <= 3:
            recommendations.append("You have access to long-term memory - consider storing important documents and knowledge")
        
        # Role-based recommendations
        if "Manager" in user_context.roles:
            recommendations.append("As a manager, consider using mid-term memory to track team decisions and outcomes")
        
        if user_context.hierarchy_level <= 2:
            recommendations.append("You have organization-wide access - use long-term memory to store company policies and procedures")
        
        return recommendations

    async def migrate_memory(self, user_context: UserContext, source_tier: str, target_tier: str, memory_id: str) -> Dict:
        """
        Migrate memory from one tier to another
        
        Args:
            user_context: User's context
            source_tier: Source memory tier
            target_tier: Target memory tier
            memory_id: ID of memory to migrate
            
        Returns:
            Migration result
        """
        try:
            # Get source content
            if source_tier == 'short_term':
                # Get session and convert to summary
                sessions = await self.short_term.retrieve_sessions(user_context, limit=1000)
                source_item = next((s for s in sessions if str(s['session_id']) == memory_id), None)
                if not source_item:
                    raise HTTPException(status_code=404, detail="Source memory not found")
                
                # Convert session to summary format
                messages = source_item.get('messages', [])
                if isinstance(messages, str):
                    import json
                    messages = json.loads(messages)
                
                content_text = ' '.join([msg.get('content', '') for msg in messages if isinstance(msg, dict)])
                migrated_content = {
                    "summary_text": f"Session summary: {content_text[:500]}...",
                    "conversation_ids": [memory_id],
                    "tags": ["migrated", "session"],
                    "entities": {"source": "short_term_migration"}
                }
                
            elif source_tier == 'mid_term':
                # Get summary and convert to document
                summaries = await self.mid_term.retrieve_summaries(user_context, limit=1000)
                source_item = next((s for s in summaries if str(s['summary_id']) == memory_id), None)
                if not source_item:
                    raise HTTPException(status_code=404, detail="Source memory not found")
                
                migrated_content = {
                    "title": f"Summary Document: {source_item['summary_text'][:50]}...",
                    "content": source_item['summary_text'],
                    "memory_type": "migrated_summary",
                    "metadata": {
                        "original_tags": source_item.get('tags', []),
                        "source": "mid_term_migration"
                    }
                }
            else:
                raise HTTPException(status_code=400, detail="Migration from long-term not supported")
            
            # Store in target tier
            if target_tier == 'mid_term':
                result = await self.mid_term.store_summary(user_context, migrated_content)
            elif target_tier == 'long_term':
                result = await self.long_term.store_document(user_context, migrated_content)
            else:
                raise HTTPException(status_code=400, detail="Invalid target tier")
            
            return {
                "migration_id": str(uuid.uuid4()),
                "source_tier": source_tier,
                "target_tier": target_tier,
                "source_id": memory_id,
                "target_id": result.get('memory_id', result.get('summary_id')),
                "status": "success",
                "message": f"Successfully migrated from {source_tier} to {target_tier}"
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Memory migration failed: {e}")
            raise HTTPException(status_code=500, detail="Memory migration failed")
        