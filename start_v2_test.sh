#!/bin/bash

# 启动v2测试脚本

echo "=== 法务数据结构化系统 v2 测试启动脚本 ==="
echo ""

# 检查虚拟环境
if [ -z "$VIRTUAL_ENV" ]; then
    echo "警告: 没有检测到虚拟环境，建议使用虚拟环境"
fi

# 检查依赖项
echo "检查依赖项..."
pip install -r requirements.txt > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "错误: 依赖项安装失败"
    exit 1
fi
echo "依赖项检查完成"

# 检查数据库连接
echo "检查数据库连接..."
python -c "
from app.core.database import engine
from sqlalchemy import text
try:
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
    print('数据库连接成功')
except Exception as e:
    print(f'数据库连接失败: {e}')
    exit(1)
"

# 检查Milvus连接
echo "检查Milvus连接..."
python -c "
try:
    from app.core.milvus_client import MilvusClient
    from app.core.config import settings
    client = MilvusClient(host=settings.milvus_host, port=settings.milvus_port)
    print('Milvus连接成功')
except Exception as e:
    print(f'Milvus连接失败: {e}')
    print('注意: 如果Milvus服务未运行，向量化功能将无法使用')
"

# 启动API服务
echo ""
echo "启动API服务..."
echo "服务将在 http://localhost:8000 启动"
echo "API文档地址: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload