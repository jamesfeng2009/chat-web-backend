#!/bin/bash

# 法务数据结构化系统启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Docker是否安装
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_info "Docker and Docker Compose are installed."
}

# 检查环境配置文件
check_env() {
    if [ ! -f .env ]; then
        print_warn ".env file not found. Creating from .env.example..."
        cp .env.example .env
        print_warn "Please edit .env file with your configuration before running the system."
        exit 1
    fi
    
    print_info ".env file found."
}

# 创建必要的目录
create_dirs() {
    print_info "Creating necessary directories..."
    mkdir -p storage/documents
    mkdir -p logs
    mkdir -p backup
    print_info "Directories created."
}

# 构建Docker镜像
build_images() {
    print_info "Building Docker images..."
    docker-compose build
    print_info "Docker images built successfully."
}

# 启动服务
start_services() {
    print_info "Starting services..."
    docker-compose up -d
    print_info "Services started."
}

# 等待服务启动
wait_for_services() {
    print_info "Waiting for services to start..."
    
    # 等待MySQL启动
    print_info "Waiting for MySQL to be ready..."
    until docker-compose exec mysql mysqladmin ping -h localhost --silent; do
        echo -n "."
        sleep 2
    done
    echo ""
    print_info "MySQL is ready."
    
    # 等待Redis启动
    print_info "Waiting for Redis to be ready..."
    until docker-compose exec redis redis-cli ping; do
        echo -n "."
        sleep 2
    done
    echo ""
    print_info "Redis is ready."
    
    # 等待Milvus启动
    print_info "Waiting for Milvus to be ready..."
    until curl -s http://localhost:19530/health > /dev/null; do
        echo -n "."
        sleep 5
    done
    echo ""
    print_info "Milvus is ready."
    
    # 等待应用启动
    print_info "Waiting for the application to be ready..."
    until curl -s http://localhost:8000/api/v1/health/ > /dev/null; do
        echo -n "."
        sleep 3
    done
    echo ""
    print_info "Application is ready."
}

# 初始化数据库
init_database() {
    print_info "Initializing database..."
    docker-compose exec app alembic upgrade head
    print_info "Database initialized."
}

# 显示服务状态
show_status() {
    print_info "Service status:"
    docker-compose ps
    
    echo ""
    print_info "API documentation: http://localhost:8000/docs"
    print_info "Health check: http://localhost:8000/api/v1/health/"
}

# 主函数
main() {
    print_info "Starting Legal Document Structuring System..."
    
    # 检查依赖
    check_docker
    
    # 检查配置
    check_env
    
    # 创建目录
    create_dirs
    
    # 构建镜像
    build_images
    
    # 启动服务
    start_services
    
    # 等待服务启动
    wait_for_services
    
    # 初始化数据库
    init_database
    
    # 显示状态
    show_status
    
    print_info "Legal Document Structuring System started successfully!"
}

# 如果直接运行此脚本
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi