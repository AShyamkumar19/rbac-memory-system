from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import sys
from datetime import datetime

from config import settings
from storage.database_client import db_client
from api.auth import router as auth_router
from api.memory import router as memory_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("rbac_memory_system.log")
    ]
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting RBAC Memory Management System...")
    try:
        await db_client.initialize()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    try:
        await db_client.close()
        logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# Create FastAPI app
app = FastAPI(
    title="RBAC Memory Management System",
    version="1.0.0",
    description="""
    **Role-Based Access Control Memory Management System**
    
    A sophisticated memory management system for Agentic AI with three-tier architecture:
    - **Short-term Memory**: Session conversations and temporary context
    - **Mid-term Memory**: Summaries, decisions, and insights  
    - **Long-term Memory**: Knowledge base, documents, and permanent storage
    
    Features:
    - Role-based access control (RBAC)
    - Universal search across all memory tiers
    - Semantic search with vector embeddings
    - Comprehensive analytics and insights
    - Intelligent memory routing
    - Memory migration between tiers
    """,
    debug=settings.DEBUG,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(memory_router, prefix="/memory", tags=["Memory Management"])

# Root endpoints
@app.get("/", summary="System Information")
async def root():
    """Get system information and available endpoints"""
    return {
        "service": "RBAC Memory Management System",
        "version": "1.0.0",
        "status": "active",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "authentication": "/auth",
            "memory_management": "/memory", 
            "api_docs": "/docs",
            "health_check": "/health"
        },
        "features": [
            "Role-based access control",
            "Three-tier memory architecture",
            "Universal search capabilities",
            "Semantic search with embeddings",
            "Intelligent memory routing",
            "Cross-tier analytics"
        ]
    }

@app.get("/health", summary="Health Check")
async def health_check():
    """Health check endpoint with system status"""
    try:
        # Check database health
        db_health = await db_client.health_check()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "components": {
                "database": db_health.get("status", "unknown"),
                "memory_controllers": "active",
                "rbac_system": "active"
            },
            "uptime": "running"
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for better error reporting"""
    logger.error(f"Unhandled exception on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url)
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )