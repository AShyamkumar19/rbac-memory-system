import asyncpg
import asyncio
import logging
from typing import Optional, List, Dict, Any, Union
from config import settings
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class DatabaseClient:
    """
    Asynchronous database client for interacting with PostgreSQL.
    """

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = Optional[asyncpg.Pool] = None
        self._initialized = False
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        """Initialize the database connection pool"""
        if self._initialized:
            self.logger.info("Database connection pool already initialized")
            return
        try:
            self.logger.info("Initializing database connection pool...")
            self.pool = await asyncpg.create_pool(
                dsn=self.database_url,
                min_size=5,
                max_size=20,
                timeout=30,
                server_settings={
                    'jit': 'off',
                    'application_name': 'rbac_system'
                }
            )

            async with self.pool.acquire() as connection:
                await connection.execute("SELECT 1")

            self.initialize = True
            logger.info("Database connection pool initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database connection pool: {e}")
            raise 

    async def close(self):
        """Close the database connection pool"""
        if self.pool:
            await self.pool.close()
            self.initialize = False
            logger.info("Database connection pool closed successfully")

    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool"""
        if not self.pool:
            raise RuntimeError("Database connection pool not initialized")
        
        try:
            connection = await self.pool.acquire()
            yield connection
            logger.info("Connection released back to pool")
        except Exception as e:
            logger.error(f"Error getting connection from pool: {e}")
            raise

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return the result (It doens't return data like INSERT, UPDATE, DELETE)"""
        async with self.get_connection() as connection:
            return await connection.execute(query, *args)
        
    async def fetchone(self, query: str, *args: Any) -> Optional[Dict]:
        """Execute a query and return the result (It returns data like SELECT)"""
        async with self.get_connection() as connection:
            row = await connection.fetchrow(query, *args)
            return row.to_dict() if row else None
        
    async def fetchall(self, query: str, *args: Any) -> List[Dict]:
        """Fetch all rows from the db"""
        async with self.get_connection() as connection:
            rows = await connection.fetch(query, *args)
            return [row.to_dict() for row in rows]
        
    async def fetchval(self, query: str, *args: Any) -> Any:
        """Fetch a single value from the db"""
        async with self.get_connection() as connection:
            result = await connection.fetchval(query, *args)
            return result
        
    async def transaction(self):
        """Get db transaction context"""
        if not self.initialized:
            await self.initialize()
        return self.pool.acquire()
        
    async def health_check(self) -> Dict[str, Any]:
        """Check database health"""
        try:
            async with self.get_connection() as conn:
                # Test basic query
                result = await conn.fetchval("SELECT 1")
                
                # Get database stats
                stats = await conn.fetchrow("""
                    SELECT 
                        pg_database_size(current_database()) as db_size,
                        (SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()) as active_connections,
                        current_timestamp as server_time
                """)
                
                return {
                    "status": "healthy",
                    "database_size": stats["db_size"],
                    "active_connections": stats["active_connections"],
                    "server_time": stats["server_time"]
                }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

# Create global database client instance
db_client = DatabaseClient(settings.DATABASE_URL)

# Dependency for FastAPI
async def get_db_client() -> DatabaseClient:
    """FastAPI dependency to get database client"""
    return db_client