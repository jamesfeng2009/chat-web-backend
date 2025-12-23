import secrets


from pydantic import field_validator
from pydantic_settings import BaseSettings as PydanticBaseSettings


class Settings(PydanticBaseSettings):
    # 基础配置
    PROJECT_NAME: str = "Legal Document Structuring System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 数据库配置
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/legal_db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False  # 生产环境设为False，开发时可设为True用于调试
    
    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Milvus配置
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION_NAME: str = "legal_clause_vectors"
    
    # 文件存储配置
    STORAGE_TYPE: str = "local"  # local, s3, minio
    STORAGE_PATH: str = "./storage"
    
    # MinIO配置
    MINIO_ENDPOINT: str | None = None
    MINIO_ACCESS_KEY: str | None = None
    MINIO_SECRET_KEY: str | None = None
    MINIO_SECURE: bool = False
    MINIO_BUCKET_NAME: str = "legal-docs"

    # AI服务配置
    OPENAI_API_KEY: str | None = None
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIMENSION: int = 1536
    
    # 条款切分配置
    CLAUSE_CHUNKING_MODEL: str = "BAAI/bge-m3"
    CLAUSE_CHUNKING_CROSS_ENCODER: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"
    CLAUSE_CHUNKING_CACHE_DIR: str = "./models/clause_chunking"
    
    # 文档处理配置
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_FILE_TYPES: list[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
        "text/html"
    ]
    
    # 安全配置
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # CORS配置
    # 默认允许本地开发环境，生产环境应通过环境变量配置具体域名
    BACKEND_CORS_ORIGINS: list[str] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: list[str] | str) -> list[str]:
        """
        将CORS来源配置转换为URL列表

        支持两种格式：
        1. 逗号分隔的字符串: "http://localhost:3000,http://localhost:8080"
        2. 列表: ["http://localhost:3000", "http://localhost:8080"]
        """
        # 如果环境变量是字符串，解析为列表
        if isinstance(v, str):
            if not v.strip() or v.strip() == "[]":
                return []  # 空字符串返回空列表
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        # 如果已经是列表，直接返回
        elif isinstance(v, list):
            return v
        raise ValueError(f"BACKEND_CORS_ORIGINS must be a comma-separated string or list of URLs, got: {type(v)}")

    # JWT配置
    ALGORITHM: str = "HS256"

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 任务队列配置
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    # 分页配置
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # 向量搜索配置
    DEFAULT_SEARCH_LIMIT: int = 10
    MAX_SEARCH_LIMIT: int = 100
    
    class Config:
        env_file: str = ".env"
        case_sensitive: bool = True


settings = Settings()