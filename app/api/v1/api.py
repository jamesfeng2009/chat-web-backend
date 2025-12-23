from fastapi import APIRouter

from app.api.v1.endpoints import (
    documents,
    parsing,
    structure,
    vector_collections,
    search,
    health,
    document_processing,
    vector_search,
    document_parsing,
    document_llm_processing,
    vector_ingestion,
    document_chunking,
    document_summary
)

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(parsing.router, prefix="/parsing", tags=["parsing"])
api_router.include_router(structure.router, prefix="/structure", tags=["structure"])
api_router.include_router(vector_collections.router, prefix="/vector-collections", tags=["vector-collections"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(document_processing.router, tags=["document-processing"])
api_router.include_router(vector_search.router, prefix="/vector-search", tags=["vector-search"])
api_router.include_router(document_parsing.router, prefix="/document-parsing", tags=["document-parsing"])
api_router.include_router(document_llm_processing.router, prefix="/llm-processing", tags=["llm-processing"])
api_router.include_router(vector_ingestion.router, prefix="/vector-collections", tags=["vector-ingestion"])
api_router.include_router(document_chunking.router, prefix="/chunking", tags=["document-chunking"])
api_router.include_router(document_summary.router, prefix="/summary", tags=["document-summary"])