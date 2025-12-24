#!/bin/bash
# Web2Lean 启动脚本

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查命令
COMMAND=${1:-"help"}

case $COMMAND in
    init)
        echo "Initializing database..."
        python main.py --init-db
        ;;

    start)
        echo "Starting Web2Lean backend..."
        python main.py
        ;;

    vllm)
        echo "Starting VLLM server for Kimina-Autoformalizer-7B..."
        vllm serve /root/Kimina-Autoformalizer-7B --tensor-parallel-size 1 --port 8000 --host 0.0.0.0
        ;;

    frontend)
        echo "Starting frontend..."
        cd frontend
        npm run dev
        ;;

    install-frontend)
        echo "Installing frontend dependencies..."
        cd frontend
        npm install
        ;;

    crawl)
        echo "Starting crawler for ${2:-math_stackexchange}..."
        curl -X POST http://localhost:5000/api/crawlers/start \
            -H "Content-Type: application/json" \
            -d "{\"site_name\": \"${2:-math_stackexchange}\", \"mode\": \"incremental\"}"
        ;;

    test)
        echo "Testing API..."
        curl http://localhost:5000/api/statistics/overview
        ;;

    help|*)
        echo "Web2Lean 控制脚本"
        echo ""
        echo "用法: ./start.sh [命令]"
        echo ""
        echo "命令:"
        echo "  init              - 初始化数据库"
        echo "  start             - 启动后端 API 服务器"
        echo "  vllm              - 启动 VLLM 服务器 (Lean 转换)"
        echo "  frontend          - 启动前端开发服务器"
        echo "  install-frontend  - 安装前端依赖"
        echo "  crawl [site]      - 启动爬虫 (默认: math_stackexchange)"
        echo "  test              - 测试 API 连接"
        echo ""
        echo "示例:"
        echo "  ./start.sh init"
        echo "  ./start.sh start"
        echo "  ./start.sh frontend"
        echo "  ./start.sh crawl math_stackexchange"
        ;;
esac
