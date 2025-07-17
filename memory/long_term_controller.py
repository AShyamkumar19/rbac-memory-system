from models.base_models import UserContext, memory_tier_type, access_scope_type, classification_type
from storage.database_client import DatabaseClient
from rbac.rbac_controller import RBACController
from fastapi import HTTPException
import logging
from typing import Dict, List, Optional, Union
import uuid
import json
import hashlib
import re
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

class LongTermController:
    """
    Handles long-term memory operations (knowledge base, documents, permanent storage)
    Supports vector embeddings for semantic search and advanced document management.
    """

    def __init__(self, db_client: DatabaseClient, rbac_controller: RBACController):
        self.db_client = db_client
        self.rbac_controller = rbac_controller
        self.memory_tier = memory_tier_type.long_term

    def _generate_content_hash(self, content: str) -> str:
        """Generate hash for content deduplication"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _extract_keywords(self, content: str, max_keywords: int = 10) -> List[str]:
        """
        Extract keywords from content using simple text processing
        In production, you'd use NLP libraries like spaCy or NLTK
        """
        # Simple keyword extraction - remove common words and extract meaningful terms
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those'
        }
        
        # Extract words, convert to lowercase, remove punctuation
        words = re.findall(r'\b[a-zA-Z]{3,}\b', content.lower())
        
        # Filter out stop words and count frequency
        word_freq = {}
        for word in words:
            if word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Return top keywords by frequency
        keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in keywords[:max_keywords]]

    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate vector embedding for text
        
        This is a simple placeholder implementation. In production, you would use:
        - OpenAI Embeddings API
        - Sentence-BERT models
        - Other transformer-based embedding models
        
        For now, we'll create a simple hash-based embedding for demonstration
        """
        # Simple hash-based embedding (1536 dimensions like OpenAI)
        # This is NOT suitable for production - use real embeddings!
        
        # Normalize text
        text = text.lower().strip()
        
        # Create multiple hashes and combine them
        embedding = []
        
        # Use different hash seeds to create variety
        for i in range(96):  # 96 * 16 = 1536 dimensions
            hash_obj = hashlib.md5(f"{text}_{i}".encode())
            hex_hash = hash_obj.hexdigest()
            
            # Convert hex to 16 float values between -1 and 1
            for j in range(0, 32, 2):
                hex_pair = hex_hash[j:j+2]
                # Convert to float between -1 and 1
                float_val = (int(hex_pair, 16) / 255.0) * 2 - 1
                embedding.append(float_val)
        
        return embedding[:1536]  # Ensure exactly 1536 dimensions

    def _calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings"""
        if len(embedding1) != len(embedding2):
            return 0.0
        
        # Convert to numpy arrays for easier calculation
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        return float(similarity)

    async def store_document(self, user_context: UserContext, document_data: Dict) -> Dict:
        """
        Store a long-term memory document with vector embedding
        
        Args:
            user_context: User's context
            document_data: Dict containing:
                - content: Main text content (required)
                - title: Document title (optional)
                - memory_type: Type of document (document, procedure, policy, etc.)
                - source_type: How document was created (user_input, document_upload, etc.)
                - source_url: Original URL if applicable
                - file_path: File path if uploaded
                - metadata: Additional metadata
                
        Returns:
            Dict with memory_id and status
        """
        try:
            # Step 1: Check RBAC permissions
            access_result = await self.rbac_controller.check_memory_access(
                user_context, self.memory_tier, "write"
            )
            if not access_result["granted"]:
                raise HTTPException(status_code=403, detail=access_result["reason"])
            
            # Step 2: Validate document data
            content = document_data.get("content", "").strip()
            if not content:
                raise HTTPException(status_code=400, detail="Document content is required")
            
            if len(content) < 10:
                raise HTTPException(status_code=400, detail="Document content too short (minimum 10 characters)")
            
            # Step 3: Generate content hash for deduplication
            content_hash = self._generate_content_hash(content)
            
            # Check if document with same content already exists
            existing_doc = await self.db_client.fetchone(
                "SELECT memory_id FROM rbac_long_term_memory WHERE content_hash = $1",
                content_hash
            )
            
            if existing_doc:
                logger.info(f"Document with same content already exists: {existing_doc['memory_id']}")
                return {
                    "memory_id": str(existing_doc['memory_id']),
                    "status": "duplicate",
                    "message": "Document with identical content already exists"
                }
            
            # Step 4: Process document content
            title = document_data.get("title", content[:100] + "..." if len(content) > 100 else content)
            keywords = self._extract_keywords(content)
            embedding = self._generate_embedding(content)
            word_count = len(content.split())
            
            # Step 5: Prepare data for database
            project_id = user_context.project_ids[0] if user_context.project_ids else None
            
            # Step 6: Store in database
            memory_id = await self.db_client.fetchval(
                """
                INSERT INTO rbac_long_term_memory 
                (title, content, content_hash, embedding, metadata, memory_type, source_type,
                 source_url, file_path, project_id, department_id, created_by, 
                 classification_level, access_scope, keywords, word_count, version)
                VALUES ($1, $2, $3, $4::vector, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                RETURNING memory_id
                """,
                title,
                content,
                content_hash,
                str(embedding),  # Convert to string for VECTOR type
                json.dumps(document_data.get("metadata", {})),
                document_data.get("memory_type", "document"),
                document_data.get("source_type", "user_input"),
                document_data.get("source_url"),
                document_data.get("file_path"),
                project_id,
                user_context.department_id,
                user_context.user_id,
                user_context.classification_level.value,
                document_data.get("access_scope", "project"),
                keywords,  # PostgreSQL array
                word_count,
                1  # Initial version
            )
            
            logger.info(f"Stored long-term document: {memory_id} for user: {user_context.username}")
            
            return {
                "memory_id": str(memory_id),
                "status": "success",
                "message": "Document stored successfully",
                "keywords": keywords,
                "word_count": word_count
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error storing document: {e}")
            raise HTTPException(status_code=500, detail="Failed to store document")

    async def retrieve_documents(self, user_context: UserContext, filters: Dict = None, limit: int = 50) -> List[Dict]:
        """
        Retrieve long-term documents with advanced filtering
        
        Args:
            user_context: User's context
            filters: Dict with optional filters:
                - memory_type: Filter by document type
                - keywords: Filter by keywords (array overlap)
                - content_search: Text search in content
                - date_from/date_to: Date range
                - min_word_count/max_word_count: Word count range
                - classification_level: Filter by classification
                
        Returns:
            List of documents user can access
        """
        try:
            # Step 1: Check RBAC permissions
            access_result = await self.rbac_controller.check_memory_access(
                user_context, self.memory_tier, "read"
            )
            if not access_result["granted"]:
                raise HTTPException(status_code=403, detail=access_result["reason"])
            
            # Step 2: Build query with RBAC filters + user filters
            user_filters = filters or {}
            rbac_filters = access_result["filters"]
            
            # Build WHERE clause dynamically
            where_conditions = []
            params = []
            param_count = 0
            
            # RBAC filters
            if 'user_id' in rbac_filters:
                param_count += 1
                where_conditions.append(f"created_by = ${param_count}")
                params.append(rbac_filters['user_id'])
            
            if 'project_id__in' in rbac_filters:
                param_count += 1
                where_conditions.append(f"project_id = ANY(${param_count})")
                params.append(rbac_filters['project_id__in'])
            
            if 'department_id' in rbac_filters:
                param_count += 1
                where_conditions.append(f"department_id = ${param_count}")
                params.append(rbac_filters['department_id'])
            
            # User filters
            if 'memory_type' in user_filters:
                param_count += 1
                where_conditions.append(f"memory_type = ${param_count}")
                params.append(user_filters['memory_type'])
            
            if 'keywords' in user_filters:
                param_count += 1
                where_conditions.append(f"keywords && ${param_count}")  # Array overlap
                params.append(user_filters['keywords'])
            
            if 'content_search' in user_filters:
                param_count += 1
                where_conditions.append(f"(content ILIKE ${param_count} OR title ILIKE ${param_count})")
                search_term = f"%{user_filters['content_search']}%"
                params.append(search_term)
            
            if 'date_from' in user_filters:
                param_count += 1
                where_conditions.append(f"created_at >= ${param_count}")
                params.append(user_filters['date_from'])
            
            if 'date_to' in user_filters:
                param_count += 1
                where_conditions.append(f"created_at <= ${param_count}")
                params.append(user_filters['date_to'])
            
            if 'min_word_count' in user_filters:
                param_count += 1
                where_conditions.append(f"word_count >= ${param_count}")
                params.append(user_filters['min_word_count'])
            
            if 'max_word_count' in user_filters:
                param_count += 1
                where_conditions.append(f"word_count <= ${param_count}")
                params.append(user_filters['max_word_count'])
            
            if 'classification_level' in user_filters:
                param_count += 1
                where_conditions.append(f"classification_level = ${param_count}")
                params.append(user_filters['classification_level'])
            
            # Add limit
            param_count += 1
            params.append(limit)
            
            # Build final query
            where_clause = " AND ".join(where_conditions) if where_conditions else "TRUE"
            where_clause += " AND is_archived = FALSE"  # Don't show archived documents
            
            query = f"""
                SELECT memory_id, title, content, metadata, memory_type, source_type,
                       source_url, file_path, project_id, department_id, created_by,
                       classification_level, access_scope, keywords, word_count,
                       version, created_at, updated_at
                FROM rbac_long_term_memory 
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_count}
            """
            
            # Step 3: Execute query
            documents = await self.db_client.fetchall(query, *params)
            
            # Step 4: Process results
            result = []
            for doc in documents:
                doc_dict = dict(doc)
                # Parse JSON metadata
                if doc_dict.get('metadata'):
                    doc_dict['metadata'] = json.loads(doc_dict['metadata'])
                
                # Convert UUIDs to strings for JSON serialization
                doc_dict['memory_id'] = str(doc_dict['memory_id'])
                if doc_dict.get('project_id'):
                    doc_dict['project_id'] = str(doc_dict['project_id'])
                if doc_dict.get('department_id'):
                    doc_dict['department_id'] = str(doc_dict['department_id'])
                if doc_dict.get('created_by'):
                    doc_dict['created_by'] = str(doc_dict['created_by'])
                
                result.append(doc_dict)
            
            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving documents: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve documents")

    async def semantic_search(self, user_context: UserContext, query: str, limit: int = 20) -> List[Dict]:
        """
        Perform semantic search using vector embeddings
        
        Args:
            user_context: User's context
            query: Search query text
            limit: Maximum number of results
            
        Returns:
            List of documents ranked by semantic similarity
        """
        try:
            # Step 1: Check RBAC permissions
            access_result = await self.rbac_controller.check_memory_access(
                user_context, self.memory_tier, "read"
            )
            if not access_result["granted"]:
                raise HTTPException(status_code=403, detail=access_result["reason"])
            
            # Step 2: Generate embedding for search query
            query_embedding = self._generate_embedding(query)
            
            # Step 3: Get candidate documents (apply RBAC filtering first)
            rbac_filters = access_result["filters"]
            where_conditions = []
            params = []
            param_count = 0
            
            # Apply RBAC filters
            if 'user_id' in rbac_filters:
                param_count += 1
                where_conditions.append(f"created_by = ${param_count}")
                params.append(rbac_filters['user_id'])
            
            if 'project_id__in' in rbac_filters:
                param_count += 1
                where_conditions.append(f"project_id = ANY(${param_count})")
                params.append(rbac_filters['project_id__in'])
            
            if 'department_id' in rbac_filters:
                param_count += 1
                where_conditions.append(f"department_id = ${param_count}")
                params.append(rbac_filters['department_id'])
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "TRUE"
            where_clause += " AND is_archived = FALSE"
            
            # Get documents with embeddings
            query_sql = f"""
                SELECT memory_id, title, content, embedding, keywords, 
                       classification_level, created_at, word_count
                FROM rbac_long_term_memory 
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT 200
            """
            
            # Step 4: Execute query to get candidate documents
            documents = await self.db_client.fetchall(query_sql, *params)
            
            # Step 5: Calculate similarities and rank results
            ranked_results = []
            
            for doc in documents:
                doc_embedding = doc['embedding']
                
                # Calculate similarity
                similarity = self._calculate_similarity(query_embedding, doc_embedding)
                
                # Create result object
                result = {
                    'memory_id': str(doc['memory_id']),
                    'title': doc['title'],
                    'content': doc['content'][:500] + "..." if len(doc['content']) > 500 else doc['content'],
                    'keywords': doc['keywords'],
                    'classification_level': doc['classification_level'],
                    'created_at': doc['created_at'],
                    'word_count': doc['word_count'],
                    'similarity_score': similarity,
                    'relevance': 'high' if similarity > 0.8 else 'medium' if similarity > 0.6 else 'low'
                }
                
                ranked_results.append(result)
            
            # Step 6: Sort by similarity and return top results
            ranked_results.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            return ranked_results[:limit]

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            raise HTTPException(status_code=500, detail="Failed to perform semantic search")

    async def get_document_by_id(self, user_context: UserContext, memory_id: str) -> Dict:
        """
        Get a specific document by ID with RBAC checking
        
        Args:
            user_context: User's context
            memory_id: Document ID to retrieve
            
        Returns:
            Document details if user has access
        """
        try:
            # Step 1: Check RBAC permissions
            access_result = await self.rbac_controller.check_memory_access(
                user_context, self.memory_tier, "read"
            )
            if not access_result["granted"]:
                raise HTTPException(status_code=403, detail=access_result["reason"])
            
            # Step 2: Get document with RBAC filtering
            rbac_filters = access_result["filters"]
            where_conditions = [f"memory_id = $1"]
            params = [uuid.UUID(memory_id)]
            param_count = 1
            
            # Apply RBAC filters
            if 'user_id' in rbac_filters:
                param_count += 1
                where_conditions.append(f"created_by = ${param_count}")
                params.append(rbac_filters['user_id'])
            
            if 'project_id__in' in rbac_filters:
                param_count += 1
                where_conditions.append(f"project_id = ANY(${param_count})")
                params.append(rbac_filters['project_id__in'])
            
            if 'department_id' in rbac_filters:
                param_count += 1
                where_conditions.append(f"department_id = ${param_count}")
                params.append(rbac_filters['department_id'])
            
            where_clause = " AND ".join(where_conditions)
            
            query = f"""
                SELECT memory_id, title, content, metadata, memory_type, source_type,
                       source_url, file_path, project_id, department_id, created_by,
                       classification_level, access_scope, keywords, entities,
                       word_count, version, created_at, updated_at
                FROM rbac_long_term_memory 
                WHERE {where_clause} AND is_archived = FALSE
            """
            
            document = await self.db_client.fetchone(query, *params)
            
            if not document:
                raise HTTPException(status_code=404, detail="Document not found or access denied")
            
            # Step 3: Process result
            doc_dict = dict(document)
            
            # Parse JSON fields
            if doc_dict.get('metadata'):
                doc_dict['metadata'] = json.loads(doc_dict['metadata'])
            if doc_dict.get('entities'):
                doc_dict['entities'] = json.loads(doc_dict['entities'])
            
            # Convert UUIDs to strings
            doc_dict['memory_id'] = str(doc_dict['memory_id'])
            if doc_dict.get('project_id'):
                doc_dict['project_id'] = str(doc_dict['project_id'])
            if doc_dict.get('department_id'):
                doc_dict['department_id'] = str(doc_dict['department_id'])
            if doc_dict.get('created_by'):
                doc_dict['created_by'] = str(doc_dict['created_by'])
            
            return doc_dict

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting document by ID: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve document")

    async def update_document(self, user_context: UserContext, memory_id: str, updates: Dict) -> Dict:
        """
        Update an existing document (creates new version)
        
        Args:
            user_context: User's context
            memory_id: Document ID to update
            updates: Dictionary of fields to update
            
        Returns:
            Updated document info
        """
        try:
            # Step 1: Check if user can write to long-term memory
            access_result = await self.rbac_controller.check_memory_access(
                user_context, self.memory_tier, "write"
            )
            if not access_result["granted"]:
                raise HTTPException(status_code=403, detail=access_result["reason"])
            
            # Step 2: Get existing document
            existing_doc = await self.get_document_by_id(user_context, memory_id)
            
            # Step 3: Check if user can modify this document
            if str(existing_doc['created_by']) != str(user_context.user_id):
                # Only allow if user has higher hierarchy level or same department
                if user_context.hierarchy_level > 2:  # Only managers and above can edit others' docs
                    raise HTTPException(status_code=403, detail="Cannot modify documents created by others")
            
            # Step 4: Prepare updated content
            new_content = updates.get('content', existing_doc['content'])
            new_title = updates.get('title', existing_doc['title'])
            new_metadata = updates.get('metadata', existing_doc.get('metadata', {}))
            
            # Step 5: Generate new hash and embedding if content changed
            if new_content != existing_doc['content']:
                content_hash = self._generate_content_hash(new_content)
                embedding = self._generate_embedding(new_content)
                keywords = self._extract_keywords(new_content)
                word_count = len(new_content.split())
            else:
                content_hash = existing_doc.get('content_hash')
                embedding = None  # Keep existing embedding
                keywords = existing_doc['keywords']
                word_count = existing_doc['word_count']
            
            # Step 6: Update document (increment version)
            if embedding:
                update_query = """
                    UPDATE rbac_long_term_memory 
                    SET title = $2, content = $3, content_hash = $4, embedding = $5::vector,
                        metadata = $6, keywords = $7, word_count = $8, version = version + 1,
                        last_modified_by = $9, updated_at = CURRENT_TIMESTAMP
                    WHERE memory_id = $1
                    RETURNING memory_id, version
                """
                result = await self.db_client.fetchone(
                    update_query,
                    uuid.UUID(memory_id), new_title, new_content, content_hash, str(embedding),
                    json.dumps(new_metadata), keywords, word_count, user_context.user_id
                )
            else:
                update_query = """
                    UPDATE rbac_long_term_memory 
                    SET title = $2, metadata = $3, last_modified_by = $4, updated_at = CURRENT_TIMESTAMP
                    WHERE memory_id = $1
                    RETURNING memory_id, version
                """
                result = await self.db_client.fetchone(
                    update_query,
                    uuid.UUID(memory_id), new_title, json.dumps(new_metadata), user_context.user_id
                )
            
            if not result:
                raise HTTPException(status_code=404, detail="Document not found or update failed")
            
            return {
                "memory_id": str(result['memory_id']),
                "version": result['version'],
                "status": "success",
                "message": "Document updated successfully"
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating document: {e}")
            raise HTTPException(status_code=500, detail="Failed to update document")

    async def delete_document(self, user_context: UserContext, memory_id: str) -> Dict:
        """
        Delete (archive) a document
        
        Args:
            user_context: User's context
            memory_id: Document ID to delete
            
        Returns:
            Deletion status
        """
        try:
            # Step 1: Check if user can delete from long-term memory
            access_result = await self.rbac_controller.check_memory_access(
                user_context, self.memory_tier, "delete"
            )
            if not access_result["granted"]:
                raise HTTPException(status_code=403, detail=access_result["reason"])
            
            # Step 2: Get existing document to check ownership
            existing_doc = await self.get_document_by_id(user_context, memory_id)
            
            # Step 3: Check if user can delete this document
            if str(existing_doc['created_by']) != str(user_context.user_id):
                # Only allow if user has manager level or above
                if user_context.hierarchy_level > 2:
                    raise HTTPException(status_code=403, detail="Cannot delete documents created by others")
            
            # Step 4: Archive document (soft delete)
            result = await self.db_client.fetchone(
                """
                UPDATE rbac_long_term_memory 
                SET is_archived = TRUE, archived_at = CURRENT_TIMESTAMP
                WHERE memory_id = $1
                RETURNING memory_id
                """,
                uuid.UUID(memory_id)
            )
            
            if not result:
                raise HTTPException(status_code=404, detail="Document not found or deletion failed")
            
            return {
                "memory_id": str(result['memory_id']),
                "status": "success",
                "message": "Document archived successfully"
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete document")

    async def get_memory_stats(self, user_context: UserContext) -> Dict:
        """
        Get statistics about long-term memory accessible to user
        
        Args:
            user_context: User's context
            
        Returns:
            Statistics about accessible documents
        """
        try:
            # Check RBAC permissions
            access_result = await self.rbac_controller.check_memory_access(
                user_context, self.memory_tier, "read"
            )
            if not access_result["granted"]:
                return {"total_documents": 0, "accessible": False}
            
            # Build RBAC filter conditions
            rbac_filters = access_result["filters"]
            where_conditions = ["is_archived = FALSE"]
            params = []
            param_count = 0
            
            if 'user_id' in rbac_filters:
                param_count += 1
                where_conditions.append(f"created_by = ${param_count}")
                params.append(rbac_filters['user_id'])
            
            if 'project_id__in' in rbac_filters:
                param_count += 1
                where_conditions.append(f"project_id = ANY(${param_count})")
                params.append(rbac_filters['project_id__in'])
            
            if 'department_id' in rbac_filters:
                param_count += 1
                where_conditions.append(f"department_id = ${param_count}")
                params.append(rbac_filters['department_id'])
            
            where_clause = " AND ".join(where_conditions)
            
            # Get comprehensive statistics
            stats_query = f"""
                SELECT 
                    COUNT(*) as total_documents,
                    COUNT(DISTINCT memory_type) as document_types,
                    AVG(word_count) as avg_word_count,
                    SUM(word_count) as total_words,
                    COUNT(DISTINCT created_by) as contributors,
                    MAX(created_at) as latest_document,
                    MIN(created_at) as earliest_document
                FROM rbac_long_term_memory 
                WHERE {where_clause}
            """
            
            stats = await self.db_client.fetchone(stats_query, *params)
            
            # Get memory type breakdown
            type_query = f"""
                SELECT memory_type, COUNT(*) as count
                FROM rbac_long_term_memory 
                WHERE {where_clause}
                GROUP BY memory_type
                ORDER BY count DESC
            """
            
            types = await self.db_client.fetchall(type_query, *params)
            
            return {
                "total_documents": int(stats['total_documents'] or 0),
                "document_types": int(stats['document_types'] or 0),
                "avg_word_count": float(stats['avg_word_count'] or 0),
                "total_words": int(stats['total_words'] or 0),
                "contributors": int(stats['contributors'] or 0),
                "latest_document": stats['latest_document'],
                "earliest_document": stats['earliest_document'],
                "memory_type_breakdown": [
                    {"type": row['memory_type'], "count": row['count']} 
                    for row in types
                ],
                "user_access_level": getattr(access_result.get("scope"), "value", str(access_result.get("scope", "unknown"))),
                "accessible": True
            }

        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return {"error": "Failed to retrieve statistics", "accessible": False}
        