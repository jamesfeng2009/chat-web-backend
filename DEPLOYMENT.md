# 部署指南

## 系统要求

### 硬件要求

- **CPU**: 8核以上
- **内存**: 16GB以上
- **存储**: 100GB以上可用空间
- **网络**: 带宽100Mbps以上

### 软件要求

- **操作系统**: Linux (推荐Ubuntu 20.04+) / macOS / Windows
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Python**: 3.11+
- **MySQL**: 8.0+
- **Redis**: 6.0+
- **Milvus**: 2.3+

## 部署方式

### 一、Docker Compose部署（推荐用于开发和小规模生产）

#### 1. 准备环境

```bash
# 克隆项目
git clone <repository-url>
cd chat-web-backend

# 复制环境配置
cp .env.example .env

# 编辑环境配置
vim .env
```

#### 2. 配置环境变量

在 `.env` 文件中配置以下关键参数：

```bash
# 数据库配置
DATABASE_URL=mysql+pymysql://legal_user:legal_password@mysql:3306/legal_db

# Redis配置
REDIS_URL=redis://redis:6379/0

# Milvus配置
MILVUS_HOST=milvus-standalone
MILVUS_PORT=19530
MILVUS_COLLECTION_NAME=legal_clause_vectors

# AI服务配置
OPENAI_API_KEY=your-openai-api-key-here
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSION=1536

# 文件存储配置
STORAGE_TYPE=minio  # 或 local
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=legal-docs
```

#### 3. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f app
```

#### 4. 初始化数据库

```bash
# 进入应用容器
docker-compose exec app bash

# 运行数据库迁移
alembic upgrade head

# 退出容器
exit
```

#### 5. 验证部署

```bash
# 检查健康状态
curl http://localhost:8000/api/v1/health/

# 查看API文档
open http://localhost:8000/docs
```

### 二、Kubernetes部署（推荐用于大规模生产）

#### 1. 准备Kubernetes配置文件

创建 `k8s/` 目录并添加以下文件：

##### namespace.yaml
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: legal-system
```

##### configmap.yaml
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: legal-config
  namespace: legal-system
data:
  DATABASE_URL: "mysql+pymysql://legal_user:legal_password@mysql:3306/legal_db"
  REDIS_URL: "redis://redis:6379/0"
  MILVUS_HOST: "milvus"
  MILVUS_PORT: "19530"
  STORAGE_TYPE: "minio"
  MINIO_ENDPOINT: "minio:9000"
  LOG_LEVEL: "INFO"
```

##### secret.yaml
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: legal-secrets
  namespace: legal-system
type: Opaque
data:
  OPENAI_API_KEY: <base64-encoded-key>
  MINIO_ACCESS_KEY: <base64-encoded-key>
  MINIO_SECRET_KEY: <base64-encoded-key>
```

##### deployment.yaml
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: legal-app
  namespace: legal-system
spec:
  replicas: 3
  selector:
    matchLabels:
      app: legal-app
  template:
    metadata:
      labels:
        app: legal-app
    spec:
      containers:
      - name: legal-app
        image: legal-system:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: legal-config
        - secretRef:
            name: legal-secrets
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /api/v1/health/
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/health/
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

##### service.yaml
```yaml
apiVersion: v1
kind: Service
metadata:
  name: legal-service
  namespace: legal-system
spec:
  selector:
    app: legal-app
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

##### ingress.yaml
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: legal-ingress
  namespace: legal-system
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - legal.example.com
    secretName: legal-tls
  rules:
  - host: legal.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: legal-service
            port:
              number: 80
```

#### 2. 部署到Kubernetes

```bash
# 应用配置
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# 检查部署状态
kubectl get pods -n legal-system
kubectl get services -n legal-system
kubectl get ingress -n legal-system

# 查看日志
kubectl logs -f deployment/legal-app -n legal-system
```

#### 3. 扩容和更新

```bash
# 扩容应用
kubectl scale deployment legal-app --replicas=5 -n legal-system

# 更新应用
kubectl set image deployment/legal-app legal-app=legal-system:v2 -n legal-system

# 回滚应用
kubectl rollout undo deployment/legal-app -n legal-system
```

### 三、云服务商部署

#### 1. AWS部署

##### 使用ECS部署

```bash
# 创建ECS任务定义
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# 创建ECS服务
aws ecs create-service --cluster legal-cluster --service-name legal-service --task-definition legal-task:1 --desired-count 3

# 更新服务
aws ecs update-service --cluster legal-cluster --service-name legal-service --task-definition legal-task:2
```

##### 使用Elastic Beanstalk部署

```bash
# 初始化EB应用
eb init legal-system

# 创建环境
eb create production

# 部署应用
eb deploy

# 查看状态
eb status
```

#### 2. 阿里云部署

##### 使用容器服务部署

```bash
# 创建命名空间
kubectl create namespace legal-system

# 部署应用
kubectl apply -f k8s/
```

#### 3. 腾讯云部署

##### 使用TKE部署

```bash
# 创建集群
tke create-cluster --name legal-cluster

# 部署应用
kubectl apply -f k8s/
```

## 监控和日志

### 1. Prometheus监控

```yaml
# prometheus.yaml
apiVersion: v1
kind: ServiceMonitor
metadata:
  name: legal-app-metrics
  namespace: legal-system
spec:
  selector:
    matchLabels:
      app: legal-app
  endpoints:
  - port: metrics
    interval: 30s
```

### 2. Grafana仪表板

配置Grafana仪表盘，监控以下指标：
- 请求QPS
- 响应时间
- 错误率
- 资源使用率
- 向量搜索延迟

### 3. 日志收集

```yaml
# fluentd.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluentd-config
  namespace: legal-system
data:
  fluent.conf: |
    <source>
      @type tail
      path /var/log/containers/*legal*.log
      pos_file /var/log/fluentd-containers.log.pos
      tag kubernetes.*
      format json
    </source>
    
    <match kubernetes.**>
      @type elasticsearch
      host elasticsearch.logging.svc.cluster.local
      port 9200
      index_name legal-logs
    </match>
```

## 备份和恢复

### 1. 数据库备份

```bash
# 创建备份
mysqldump -h localhost -u legal_user -p legal_db > legal_db_backup.sql

# 恢复备份
mysql -h localhost -u legal_user -p legal_db < legal_db_backup.sql
```

### 2. Milvus备份

```bash
# 创建备份
python milvus_backup.py --create --collection legal_clause_vectors --backup_path /backup/milvus

# 恢复备份
python milvus_backup.py --restore --collection legal_clause_vectors --backup_path /backup/milvus
```

### 3. 文件备份

```bash
# 创建文件备份
tar -czf /backup/storage_$(date +%Y%m%d).tar.gz ./storage

# 恢复文件备份
tar -xzf /backup/storage_20231201.tar.gz
```

## 性能优化

### 1. 数据库优化

```sql
-- 添加索引
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_clauses_doc_id ON clauses(doc_id);
CREATE INDEX idx_clause_items_clause_id ON clause_items(clause_id);

-- 优化查询
EXPLAIN SELECT * FROM clauses WHERE doc_id = 'doc123';
```

### 2. 向量搜索优化

```python
# 创建HNSW索引
collection.create_index(
    field_name="embedding",
    index_params={
        "index_type": "HNSW",
        "params": {"M": 16, "efConstruction": 200}
    }
)

# 优化搜索参数
search_params = {
    "metric_type": "IP",
    "params": {"ef": 200}
}
```

### 3. 缓存策略

```python
# Redis缓存装饰器
from functools import wraps
import redis

redis_client = redis.Redis(host='redis', port=6379, db=0)

def cache_result(expire_time=3600):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            cached_result = redis_client.get(cache_key)
            
            if cached_result:
                return json.loads(cached_result)
            
            result = func(*args, **kwargs)
            redis_client.setex(cache_key, expire_time, json.dumps(result))
            return result
        return wrapper
    return decorator
```

## 安全配置

### 1. 网络安全

```yaml
# network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: legal-netpol
  namespace: legal-system
spec:
  podSelector:
    matchLabels:
      app: legal-app
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: mysql
  - to:
    - podSelector:
        matchLabels:
          app: redis
  - to:
    - podSelector:
        matchLabels:
          app: milvus
```

### 2. RBAC配置

```yaml
# rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: legal-sa
  namespace: legal-system
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: legal-role
  namespace: legal-system
rules:
- apiGroups: [""]
  resources: ["pods", "services"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: legal-rb
  namespace: legal-system
subjects:
- kind: ServiceAccount
  name: legal-sa
  namespace: legal-system
roleRef:
  kind: Role
  name: legal-role
  apiGroup: rbac.authorization.k8s.io
```

## 故障排除

### 1. 常见问题

#### 数据库连接失败
```bash
# 检查数据库连接
docker-compose exec mysql mysql -u legal_user -p

# 检查网络连通性
docker-compose exec app ping mysql
```

#### Milvus连接失败
```bash
# 检查Milvus状态
curl http://localhost:19530/health

# 查看Milvus日志
docker-compose logs milvus-standalone
```

#### 向量搜索慢
```bash
# 检查索引状态
python -c "from pymilvus import Collection; c = Collection('legal_clause_vectors'); print(c.indexes)"

# 重建索引
python -c "from pymilvus import Collection; c = Collection('legal_clause_vectors'); c.drop_index(); c.create_index('embedding', {'index_type': 'HNSW', 'M': 16, 'efConstruction': 200})"
```

### 2. 日志分析

```bash
# 查看应用日志
docker-compose logs -f app

# 查看错误日志
docker-compose logs app | grep ERROR

# 分析访问日志
docker-compose logs nginx | awk '{print $7}' | sort | uniq -c | sort -nr
```

### 3. 性能分析

```bash
# 使用py-spy进行性能分析
pip install py-spy
py-spy top --pid $(pgrep -f uvicorn)

# 生成火焰图
py-spy record -o profile.svg --pid $(pgrep -f uvicorn)
```

## 升级指南

### 1. 应用升级

```bash
# 构建新镜像
docker build -t legal-system:v2 .

# 更新Docker Compose配置
vim docker-compose.yml

# 滚动更新
docker-compose up -d --no-deps app

# 验证更新
curl http://localhost:8000/api/v1/health/
```

### 2. 数据库迁移

```bash
# 生成迁移文件
alembic revision --autogenerate -m "Add new table"

# 执行迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

### 3. Milvus升级

```bash
# 备份数据
python milvus_backup.py --create --backup_path /backup/milvus

# 停止旧版本
docker-compose stop milvus-standalone

# 更新配置
vim docker-compose.yml

# 启动新版本
docker-compose up -d milvus-standalone

# 恢复数据
python milvus_backup.py --restore --backup_path /backup/milvus
```

## 运维脚本

### 1. 健康检查脚本

```bash
#!/bin/bash
# health_check.sh

# 检查服务状态
services=("app" "mysql" "redis" "milvus-standalone")
for service in "${services[@]}"; do
  if docker-compose ps $service | grep -q "Up"; then
    echo "✓ $service is running"
  else
    echo "✗ $service is not running"
  fi
done

# 检查API健康状态
if curl -s http://localhost:8000/api/v1/health/ | grep -q "healthy"; then
  echo "✓ API is healthy"
else
  echo "✗ API is not healthy"
fi
```

### 2. 备份脚本

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup"

# 数据库备份
docker-compose exec -T mysql mysqldump -u legal_user -plegal_password legal_db > $BACKUP_DIR/legal_db_$DATE.sql

# 文件备份
tar -czf $BACKUP_DIR/storage_$DATE.tar.gz ./storage

# Milvus备份
python milvus_backup.py --create --backup_path $BACKUP_DIR/milvus_$DATE

# 清理旧备份（保留7天）
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
find $BACKUP_DIR -name "milvus_*" -mtime +7 -exec rm -rf {} \;
```

### 3. 监控脚本

```bash
#!/bin/bash
# monitor.sh

# 检查容器资源使用
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# 检查磁盘使用
df -h

# 检查内存使用
free -h

# 检查网络连接
netstat -an | grep :8000
```

这些脚本可以添加到 `scripts/` 目录中，并设置可执行权限：

```bash
chmod +x scripts/*.sh
```