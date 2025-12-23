import os
import hashlib
from typing import Any, BinaryIO

import json
import uuid

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class StorageService:
    """
    文件存储服务，支持本地存储和MinIO对象存储
    """
    
    def __init__(self):
        self.storage_type = settings.STORAGE_TYPE
        self.storage_path = settings.STORAGE_PATH
        self._ensure_storage_dir()
        
        # MinIO配置
        self.minio_endpoint = settings.MINIO_ENDPOINT
        self.minio_access_key = settings.MINIO_ACCESS_KEY
        self.minio_secret_key = settings.MINIO_SECRET_KEY
        self.minio_secure = settings.MINIO_SECURE
        self.minio_bucket_name = settings.MINIO_BUCKET_NAME
        
        # 初始化MinIO客户端
        if self.storage_type == "minio" and self.minio_endpoint:
            self.minio_client = Minio(
                endpoint=self.minio_endpoint,
                access_key=self.minio_access_key,
                secret_key=self.minio_secret_key,
                secure=self.minio_secure
            )
            self._ensure_minio_bucket()
        else:
            self.minio_client = None
    
    def _ensure_storage_dir(self):
        """确保本地存储目录存在"""
        if self.storage_type == "local":
            os.makedirs(self.storage_path, exist_ok=True)
            os.makedirs(os.path.join(self.storage_path, "documents"), exist_ok=True)
    
    def _ensure_minio_bucket(self):
        """确保MinIO存储桶存在"""
        if self.minio_client:
            try:
                if not self.minio_client.bucket_exists(self.minio_bucket_name):
                    self.minio_client.make_bucket(self.minio_bucket_name)
                    logger.info(f"Created MinIO bucket: {self.minio_bucket_name}")
            except S3Error as e:
                logger.error(f"Error creating MinIO bucket: {e}")
                raise
    
    def _calculate_checksum(self, file: BinaryIO) -> str:
        """计算文件SHA256校验和"""
        sha256_hash = hashlib.sha256()
        
        # 记录当前位置
        current_position = file.tell()
        
        # 计算校验和
        file.seek(0)
        for chunk in iter(lambda: file.read(4096), b""):
            sha256_hash.update(chunk)
        
        # 恢复文件位置
        file.seek(current_position)
        
        return sha256_hash.hexdigest()
    
    def _generate_file_path(self, file_name: str, checksum: str) -> str:
        """生成文件存储路径"""
        # 使用校验和作为目录名，避免重复
        dir_name = checksum[:2]  # 使用校验和前两位作为目录名
        file_ext = os.path.splitext(file_name)[1]
        storage_file_name = f"{checksum}{file_ext}"
        
        return os.path.join("documents", dir_name, storage_file_name)
    
    def save_file(
        self,
        file: BinaryIO,
        file_name: str,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        保存文件
        
        Args:
            file: 文件对象
            file_name: 文件名
            content_type: MIME类型
            metadata: 额外的元数据
            
        Returns:
            包含文件存储信息的字典
        """
        # 计算文件大小和校验和
        current_position = file.tell()
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(current_position)
        
        checksum = self._calculate_checksum(file)
        
        # 构建文件引用信息
        file_ref = {
            "file_name": file_name,
            "file_size": file_size,
            "checksum": checksum,
            "content_type": content_type,
            "storage_type": self.storage_type,
            "metadata": metadata or {}
        }
        
        if self.storage_type == "local":
            return self._save_file_local(file, file_name, checksum, file_ref)
        elif self.storage_type == "minio" and self.minio_client:
            return self._save_file_minio(file, file_name, checksum, file_ref, content_type, metadata)
        else:
            raise ValueError(f"Unsupported storage type: {self.storage_type}")
    
    def _save_file_local(
        self,
        file: BinaryIO,
        file_name: str,
        checksum: str,
        file_ref: dict[str, Any]
    ) -> dict[str, Any]:
        """本地存储文件"""
        file_path = self._generate_file_path(file_name, checksum)
        full_path = os.path.join(self.storage_path, file_path)
        
        # 确保目录存在
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # 保存文件
        with open(full_path, "wb") as f:
            file.seek(0)
            f.write(file.read())
        
        # 更新文件引用信息
        file_ref["file_path"] = file_path
        file_ref["full_path"] = full_path
        
        logger.info(f"Saved file locally: {full_path}")
        return file_ref
    
    def _save_file_minio(
        self,
        file: BinaryIO,
        file_name: str,
        checksum: str,
        file_ref: dict[str, Any],
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """MinIO存储文件"""
        assert self.minio_client is not None, "MinIO client not initialized"
        object_name = self._generate_file_path(file_name, checksum).replace("\\", "/")
        
        # 准备元数据
        minio_metadata = {}
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    minio_metadata[f"x-amz-meta-{key}"] = str(value)
        
        # 上传文件
        try:
            file.seek(0)
            result = self.minio_client.put_object(
                bucket_name=self.minio_bucket_name,
                object_name=object_name,
                data=file,
                length=-1,
                part_size=10*1024*1024,
                content_type=content_type,
                metadata=minio_metadata
            )
            
            # 更新文件引用信息
            file_ref["object_name"] = object_name
            file_ref["bucket_name"] = self.minio_bucket_name
            file_ref["etag"] = result.etag
            
            logger.info(f"Saved file to MinIO: {object_name}")
            return file_ref
            
        except S3Error as e:
            logger.error(f"Error saving file to MinIO: {e}")
            raise
    
    def get_file(self, file_ref: dict[str, Any]) -> bytes:
        """
        获取文件内容
        
        Args:
            file_ref: 文件引用信息
            
        Returns:
            文件内容
        """
        storage_type = file_ref.get("storage_type", "local")
        
        if storage_type == "local":
            return self._get_file_local(file_ref)
        elif storage_type == "minio":
            return self._get_file_minio(file_ref)
        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")
    
    def _get_file_local(self, file_ref: dict[str, Any]) -> bytes:
        """从本地存储获取文件"""
        file_path = file_ref.get("full_path")
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, "rb") as f:
            return f.read()
    
    def _get_file_minio(self, file_ref: dict[str, Any]) -> bytes:
        """从MinIO获取文件"""
        assert self.minio_client is not None, "MinIO client not initialized"
        object_name = file_ref.get("object_name")
        bucket_name = file_ref.get("bucket_name", self.minio_bucket_name)
        
        if not object_name:
            raise ValueError("Missing object_name in file_ref")
        
        try:
            response = self.minio_client.get_object(bucket_name, object_name)
            return response.read()
        except S3Error as e:
            logger.error(f"Error getting file from MinIO: {e}")
            raise
    
    def delete_file(self, file_ref: dict[str, Any]) -> bool:
        """
        删除文件
        
        Args:
            file_ref: 文件引用信息
            
        Returns:
            是否成功删除
        """
        storage_type = file_ref.get("storage_type", "local")
        
        if storage_type == "local":
            return self._delete_file_local(file_ref)
        elif storage_type == "minio":
            return self._delete_file_minio(file_ref)
        else:
            logger.warning(f"Unsupported storage type for deletion: {storage_type}")
            return False
    
    def _delete_file_local(self, file_ref: dict[str, Any]) -> bool:
        """从本地存储删除文件"""
        file_path = file_ref.get("full_path")
        if not file_path:
            return False
        
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted local file: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting local file: {e}")
            return False
    
    def _delete_file_minio(self, file_ref: dict[str, Any]) -> bool:
        """从MinIO删除文件"""
        assert self.minio_client is not None, "MinIO client not initialized"
        object_name = file_ref.get("object_name")
        bucket_name = file_ref.get("bucket_name", self.minio_bucket_name)
        
        if not object_name:
            return False
        
        try:
            self.minio_client.remove_object(bucket_name, object_name)
            logger.info(f"Deleted MinIO object: {object_name}")
            return True
        except S3Error as e:
            logger.error(f"Error deleting MinIO object: {e}")
            return False


# 全局存储服务实例
storage_service = StorageService()