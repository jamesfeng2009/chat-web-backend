import os
import json
import uuid
import hashlib
import openai
import numpy as np
from text2vec import SentenceModel
from typing import Any

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """向量化服务"""
    
    def __init__(self):
        # 初始化OpenAI客户端
        if settings.OPENAI_API_KEY:
            openai.api_key = settings.OPENAI_API_KEY
        
        # 初始化本地模型
        self.local_model = None
        
        # 模型配置
        self.model_configs = {
            "text-embedding-3-large": {
                "provider": "openai",
                "dimension": 3072,
                "max_tokens": 8191
            },
            "text-embedding-3-small": {
                "provider": "openai",
                "dimension": 1536,
                "max_tokens": 8191
            },
            "text-embedding-ada-002": {
                "provider": "openai",
                "dimension": 1536,
                "max_tokens": 8191
            },
            "text2vec-large-chinese": {
                "provider": "local",
                "dimension": 1024,
                "model_path": "shibing624/text2vec-base-chinese"
            }
        }
    
    def _get_local_model(self, model_name: str):
        """获取本地模型"""
        if not self.local_model:
            config = self.model_configs.get(model_name, {})
            model_path = config.get("model_path", "shibing624/text2vec-base-chinese")
            try:
                self.local_model = SentenceModel(model_path)
                logger.info(f"Loaded local model: {model_path}")
            except Exception as e:
                logger.error(f"Failed to load local model {model_path}: {e}")
                raise
        return self.local_model
    
    def _get_text_hash(self, text: str) -> str:
        """获取文本哈希"""
        return hashlib.md5(text.encode("utf-8")).hexdigest()
    
    def embed_text(self, text: str, model_name: str | None = None) -> list[float]:
        """
        对单个文本进行向量化
        
        Args:
            text: 输入文本
            model_name: 模型名称
            
        Returns:
            向量
        """
        if not model_name:
            model_name = settings.EMBEDDING_MODEL
        
        # 获取模型配置
        config = self.model_configs.get(model_name, {})
        if not config:
            raise ValueError(f"Unsupported embedding model: {model_name}")
        
        provider = config.get("provider")
        
        if provider == "openai":
            return self._embed_with_openai(text, model_name, config)
        elif provider == "local":
            return self._embed_with_local(text, model_name, config)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def embed_texts(self, texts: list[str], model_name: str | None = None) -> list[list[float]]:
        """
        对多个文本进行批量向量化
        
        Args:
            texts: 输入文本列表
            model_name: 模型名称
            
        Returns:
            向量列表
        """
        if not model_name:
            model_name = settings.EMBEDDING_MODEL
        
        # 获取模型配置
        config = self.model_configs.get(model_name, {})
        if not config:
            raise ValueError(f"Unsupported embedding model: {model_name}")
        
        provider = config.get("provider")
        
        if provider == "openai":
            return self._embed_batch_with_openai(texts, model_name, config)
        elif provider == "local":
            return self._embed_batch_with_local(texts, model_name, config)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def _embed_with_openai(self, text: str, model_name: str, config: dict[str, Any]) -> list[float]:
        """使用OpenAI进行向量化"""
        try:
            response = openai.Embedding.create(
                model=model_name,
                input=text
            )
            return response["data"][0]["embedding"]
        except Exception as e:
            logger.error(f"Error embedding text with OpenAI: {e}")
            raise
    
    def _embed_batch_with_openai(self, texts: list[str], model_name: str, config: dict[str, Any]) -> list[list[float]]:
        """使用OpenAI进行批量向量化"""
        try:
            response = openai.Embedding.create(
                model=model_name,
                input=texts
            )
            return [item["embedding"] for item in response["data"]]
        except Exception as e:
            logger.error(f"Error embedding texts with OpenAI: {e}")
            raise
    
    def _embed_with_local(self, text: str, model_name: str, config: dict[str, Any]) -> list[float]:
        """使用本地模型进行向量化"""
        try:
            model = self._get_local_model(model_name)
            embedding = model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error embedding text with local model: {e}")
            raise
    
    def _embed_batch_with_local(self, texts: list[str], model_name: str, config: dict[str, Any]) -> list[list[float]]:
        """使用本地模型进行批量向量化"""
        try:
            model = self._get_local_model(model_name)
            embeddings = model.encode(texts)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Error embedding texts with local model: {e}")
            raise
    
    def get_model_dimension(self, model_name: str | None = None) -> int:
        """
        获取模型向量维度
        
        Args:
            model_name: 模型名称
            
        Returns:
            向量维度
        """
        if not model_name:
            model_name = settings.EMBEDDING_MODEL
        
        config = self.model_configs.get(model_name, {})
        dimension = config.get("dimension", 1536)
        return int(dimension) if isinstance(dimension, int) else 1536
    
    def get_model_info(self, model_name: str | None = None) -> dict[str, Any]:
        """
        获取模型信息
        
        Args:
            model_name: 模型名称
            
        Returns:
            模型信息
        """
        if not model_name:
            model_name = settings.EMBEDDING_MODEL
        
        config = self.model_configs.get(model_name, {})
        if not config:
            raise ValueError(f"Unsupported embedding model: {model_name}")
        
        return {
            "model_name": model_name,
            "provider": config.get("provider"),
            "dimension": config.get("dimension"),
            "max_tokens": config.get("max_tokens"),
            "model_path": config.get("model_path")
        }


# 全局向量化服务实例
embedding_service = EmbeddingService()