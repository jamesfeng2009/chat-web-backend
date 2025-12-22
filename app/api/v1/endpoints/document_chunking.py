"""
文档条款切分API接口
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from app.services.clause_chunking import clause_chunking_service
from app.services.parser import parser_service
from app.services.document_processing import DocumentProcessingService
from app.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class ChunkingRequest(BaseModel):
    """切分请求模型"""
    mode: str = Field(default="contract", description="切分模式: contract/summary/single")
    use_cross_encoder: bool = Field(default=False, description="是否使用交叉编码器")
    embedding_model: str = Field(default="text-embedding-3-large", description="嵌入模型")
    collection_name: str = Field(default="mirrors_clause_vectors", description="向量集合名称")
    lang: str = Field(default="zh", description="语言代码")
    auto_label: bool = Field(default=False, description="是否自动执行LLM标注和向量化")


class ChunkingResponse(BaseModel):
    """切分响应模型"""
    success: bool
    message: str
    doc_id: str
    steps: dict
    data: dict


@router.post("/chunk_document", response_model=ChunkingResponse)
async def chunk_document(
    file: UploadFile = File(...),
    mode: str = Form(default="contract"),
    use_cross_encoder: bool = Form(default=False),
    embedding_model: str = Form(default="text-embedding-3-large"),
    collection_name: str = Form(default="mirrors_clause_vectors"),
    lang: str = Form(default="zh"),
    auto_label: bool = Form(default=False),
    doc_id: str = Form(default=None)
):
    """
    上传文档并执行条款切分
    
    Args:
        file: 上传的文档文件
        mode: 切分模式 (contract/summary/single)
        use_cross_encoder: 是否使用交叉编码器
        embedding_model: 嵌入模型
        collection_name: 向量集合名称
        lang: 语言代码
        auto_label: 是否自动执行LLM标注和向量化
        doc_id: 自定义文档ID（可选）
        
    Returns:
        切分结果
    """
    try:
        # 生成文档ID
        if not doc_id:
            import uuid
            doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        
        # 读取文件内容
        content = await file.read()
        file_type = file.content_type or "application/pdf"
        doc_name = file.filename or f"document_{doc_id}"
        
        logger.info(f"开始处理文档: {doc_name} (ID: {doc_id})")
        
        if auto_label:
            # 完整处理流程：切分 + 标注 + 向量化
            doc_processing_service = DocumentProcessingService()
            result = doc_processing_service.process_with_clause_chunking(
                content=content,
                file_type=file_type,
                doc_id=doc_id,
                doc_name=doc_name,
                mode=mode,
                use_cross_encoder=use_cross_encoder,
                embedding_model=embedding_model,
                collection_name=collection_name,
                lang=lang
            )
            return ChunkingResponse(**result)
        else:
            # 仅执行切分
            # 解析文档
            text_blocks = parser_service.parse(content, file_type)
            
            # 转换为Block结构
            from app.services.clause_chunking import Block
            blocks = [Block.from_text_block(block) for block in text_blocks if block.text.strip()]
            
            if not blocks:
                raise HTTPException(status_code=400, detail="文档中没有有效的文本内容")
            
            # 执行切分
            result = clause_chunking_service.chunk_blocks(
                blocks, mode=mode, use_cross_encoder=use_cross_encoder
            )
            
            # 构建响应
            return ChunkingResponse(
                success=True,
                message="文档切分完成",
                doc_id=doc_id,
                steps={
                    "chunking": {
                        "success": True,
                        "chunks_count": len(result["spans"]),
                        "mode": mode,
                        "use_cross_encoder": use_cross_encoder
                    }
                },
                data={
                    "chunks": [{"span": span, "indices": span} for span in result["spans"]],
                    "texts": result["texts"],
                    "total": len(result["spans"]),
                    "doc_name": doc_name,
                    "file_type": file_type
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in document chunking: {e}")
        raise HTTPException(status_code=500, detail=f"文档切分失败: {str(e)}")


@router.post("/chunk_text", response_model=ChunkingResponse)
async def chunk_text(
    request: ChunkingRequest,
    doc_id: str = None
):
    """
    对纯文本执行条款切分
    
    Args:
        request: 切分请求参数
        doc_id: 自定义文档ID（可选）
        
    Returns:
        切分结果
    """
    try:
        # 生成文档ID
        if not doc_id:
            import uuid
            doc_id = f"text_{uuid.uuid4().hex[:12]}"
        
        # 这里需要从请求体获取文本内容
        # 但当前模型设计不包含文本，所以暂时返回错误
        raise HTTPException(status_code=400, detail="此端点需要包含文本内容的请求体")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in text chunking: {e}")
        raise HTTPException(status_code=500, detail=f"文本切分失败: {str(e)}")


class ChunkingTextRequest(BaseModel):
    """文本切分请求模型"""
    text: str = Field(..., description="待切分的文本内容")
    doc_name: str = Field(default="text_document", description="文档名称")
    doc_id: str = Field(None, description="自定义文档ID")
    mode: str = Field(default="contract", description="切分模式")
    use_cross_encoder: bool = Field(default=False, description="是否使用交叉编码器")


@router.post("/chunk_text_content", response_model=ChunkingResponse)
async def chunk_text_content(request: ChunkingTextRequest):
    """
    对文本内容执行条款切分
    
    Args:
        request: 包含文本内容和切分参数的请求
        
    Returns:
        切分结果
    """
    try:
        # 生成文档ID
        if not request.doc_id:
            import uuid
            doc_id = f"text_{uuid.uuid4().hex[:12]}"
        else:
            doc_id = request.doc_id
        
        # 将文本转换为Block结构
        # 按行分割，每行作为一个Block
        lines = request.text.split('\n')
        from app.services.clause_chunking import Block
        blocks = [Block(text=line.strip(), indent=len(line) - len(line.lstrip())) 
                  for line in lines if line.strip()]
        
        if not blocks:
            raise HTTPException(status_code=400, detail="文本中没有有效的内容")
        
        # 执行切分
        result = clause_chunking_service.chunk_blocks(
            blocks, mode=request.mode, use_cross_encoder=request.use_cross_encoder
        )
        
        # 构建响应
        return ChunkingResponse(
            success=True,
            message="文本切分完成",
            doc_id=doc_id,
            steps={
                "chunking": {
                    "success": True,
                    "chunks_count": len(result["spans"]),
                    "mode": request.mode,
                    "use_cross_encoder": request.use_cross_encoder
                }
            },
            data={
                "chunks": [{"span": span, "indices": span} for span in result["spans"]],
                "texts": result["texts"],
                "total": len(result["spans"]),
                "doc_name": request.doc_name
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in text content chunking: {e}")
        raise HTTPException(status_code=500, detail=f"文本切分失败: {str(e)}")


@router.get("/chunking_modes")
async def get_chunking_modes():
    """
    获取支持的切分模式说明
    
    Returns:
        切分模式列表和说明
    """
    try:
        return {
            "success": True,
            "data": {
                "modes": [
                    {
                        "id": "contract",
                        "name": "合同模式",
                        "description": "适用于完整合同文档，强调结构优先，适合章/节/款层级明显的文档",
                        "parameters": {
                            "w_heading": 1.2, "w_indent_back": 1.8, "w_enum": 1.5,
                            "w_sem_start": 1.0, "w_sem_cont": 0.8, "sem_margin_neg": -0.06, 
                            "sem_margin_pos": 0.10, "pen_SS": -0.6, "pen_CC": 0.15
                        }
                    },
                    {
                        "id": "summary",
                        "name": "汇总模式",
                        "description": "适用于条款汇总文档，防止过合并，适合很多相似条款并列的文档",
                        "parameters": {
                            "w_heading": 1.0, "w_indent_back": 1.2, "w_enum": 1.6,
                            "w_sem_start": 1.2, "w_sem_cont": 0.6, "sem_margin_neg": -0.04,
                            "sem_margin_pos": 0.12, "pen_SS": -0.8, "pen_CC": 0.1
                        }
                    },
                    {
                        "id": "single",
                        "name": "单条款模式",
                        "description": "适用于单个条款或极短片段，偏向续写与抑制起新段",
                        "parameters": {
                            "w_heading": 0.6, "w_indent_back": 1.0, "w_enum": 1.2,
                            "w_sem_start": 0.6, "w_sem_cont": 1.0, "sem_margin_neg": -0.08,
                            "sem_margin_pos": 0.06, "pen_SS": -1.2, "pen_CC": 0.2,
                            "short_len_cont_bonus": 0.8, "ema_alpha": 0.35
                        }
                    }
                ],
                "cross_encoder_info": {
                    "description": "交叉编码器用于低置信边界复核，提高切分精度",
                    "models": [
                        {
                            "id": "cross-encoder/ms-marco-MiniLM-L-12-v2",
                            "name": "MS MARCO MiniLM-L-12-v2",
                            "description": "默认模型，速度快、准确度高，适合大多数场景"
                        },
                        {
                            "id": "cross-encoder/ms-marco-MiniLM-L-6-v2",
                            "name": "MS MARCO MiniLM-L-6-v2",
                            "description": "更小更快的模型，准确度略低"
                        },
                        {
                            "id": "BAAI/bge-reranker-v2-m3",
                            "name": "BAAI BGE Reranker v2-m3",
                            "description": "多语种支持，准确度更高，速度较慢"
                        }
                    ]
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting chunking modes: {e}")
        raise HTTPException(status_code=500, detail=f"获取切分模式失败: {str(e)}")