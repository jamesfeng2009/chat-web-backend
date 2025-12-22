from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session


from app.core.database import get_db
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/")
async def health_check(db: Session = Depends(get_db)) -> Dict:
    """
    健康检查接口
    """
    # 检查数据库连接
    try:
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
    
    # 检查Milvus连接
    try:
        from pymilvus import connections, utility
        if not connections.has_connection("default"):
            connections.connect(alias="default", host="localhost", port="19530")
        
        # 列出集合来测试连接
        utility.list_collections()
        milvus_status = "healthy"
    except Exception as e:
        logger.error(f"Milvus health check failed: {e}")
        milvus_status = "unhealthy"
    
    # 检查Redis连接
    try:
        import redis
        r = redis.from_url("redis://localhost:6379/0")
        r.ping()
        redis_status = "healthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        redis_status = "unhealthy"
    
    overall_status = "healthy" if all(
        status == "healthy" for status in [db_status, milvus_status, redis_status]
    ) else "unhealthy"
    
    return {
        "status": overall_status,
        "version": "1.0.0",
        "services": {
            "database": db_status,
            "milvus": milvus_status,
            "redis": redis_status
        }
    }