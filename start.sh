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

    start|backend)
        echo "Starting Web2Lean backend on port 5000..."
        python main.py --host 0.0.0.0 --port 5000
        ;;

    start-bg|backend-bg)
        echo "Starting Web2Lean backend in background..."
        nohup python main.py --host 0.0.0.0 --port 5000 > logs/backend.log 2>&1 &
        echo "Backend started in background. Logs: logs/backend.log"
        echo "Check logs: tail -f logs/backend.log"
        ;;

    frontend)
        echo "Starting frontend on port 3000..."
        cd frontend
        # Clear Vite cache if it exists to prevent startup issues
        rm -rf node_modules/.vite node_modules/.cache 2>/dev/null
        npm run dev
        ;;

    start-all|all)
        echo "Starting both backend and frontend..."
        echo "1. Starting backend in background..."
        nohup python main.py --host 0.0.0.0 --port 5000 > logs/backend.log 2>&1 &
        sleep 2
        echo "2. Starting frontend..."
        cd frontend
        npm run dev
        ;;

    stop)
        echo "Stopping all services..."
        echo "Stopping backend (port 5000)..."
        lsof -ti:5000 | xargs -r kill -9 2>/dev/null && echo "  Backend stopped" || echo "  Backend not running"
        echo "Stopping frontend (port 3000)..."
        lsof -ti:3000 | xargs -r kill -9 2>/dev/null && echo "  Frontend stopped" || echo "  Frontend not running"
        ;;

    status)
        echo "Checking service status..."
        echo ""
        echo "Backend (port 5000):"
        if lsof -i:5000 >/dev/null 2>&1; then
            echo "  ✓ Running"
            lsof -i:5000 -t | head -1 | xargs ps -p | tail -1
        else
            echo "  ✗ Not running"
        fi
        echo ""
        echo "Frontend (port 3000):"
        if lsof -i:3000 >/dev/null 2>&1; then
            echo "  ✓ Running"
            lsof -i:3000 -t | head -1 | xargs ps -p | tail -1
        else
            echo "  ✗ Not running"
        fi
        ;;

    vllm)
        echo "Starting VLLM server for Kimina-Autoformalizer-7B..."
        vllm serve /root/Kimina-Autoformalizer-7B --tensor-parallel-size 1 --port 8000 --host 0.0.0.0
        ;;

    install-frontend)
        echo "Installing frontend dependencies..."
        cd frontend
        npm install
        ;;

    clean|clean-cache)
        echo "Cleaning caches..."
        echo "  - Frontend Vite cache..."
        rm -rf frontend/node_modules/.vite frontend/node_modules/.cache 2>/dev/null
        echo "  - Backend __pycache__..."
        find backend -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
        find backend -type f -name "*.pyc" -delete 2>/dev/null
        echo "  Done! Cache cleared."
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

    logs)
        echo "Showing backend logs (Ctrl+C to exit)..."
        tail -f logs/backend.log
        ;;

    help|*)
        echo "Web2Lean 控制脚本"
        echo ""
        echo "用法: ./start.sh [命令]"
        echo ""
        echo "命令:"
        echo "  start             - 启动后端 API 服务器 (前台)"
        echo "  start-bg          - 启动后端 API 服务器 (后台)"
        echo "  backend           - 同 'start'"
        echo "  backend-bg        - 同 'start-bg'"
        echo "  frontend          - 启动前端开发服务器 (端口 3000)"
        echo "  start-all         - 同时启动后端和前端"
        echo "  all               - 同 'start-all'"
        echo "  stop              - 停止所有服务"
        echo "  status            - 查看服务运行状态"
        echo "  logs              - 查看后端日志"
        echo "  clean             - 清理缓存 (解决启动问题)"
        echo "  clean-cache       - 同 'clean'"
        echo "  init              - 初始化数据库"
        echo "  vllm              - 启动 VLLM 服务器 (Lean 转换)"
        echo "  install-frontend  - 安装前端依赖"
        echo "  crawl [site]      - 启动爬虫 (默认: math_stackexchange)"
        echo "  test              - 测试 API 连接"
        echo ""
        echo "示例:"
        echo "  ./start.sh start-bg      # 后台启动后端"
        echo "  ./start.sh frontend      # 启动前端"
        echo "  ./start.sh start-all     # 同时启动前后端"
        echo "  ./start.sh stop          # 停止所有服务"
        echo "  ./start.sh status        # 查看状态"
        echo "  ./start.sh clean         # 清理缓存"
        echo ""
        echo "手动启动方式:"
        echo "  后端: python main.py --host 0.0.0.0 --port 5000"
        echo "  前端: cd frontend && npm run dev"
        echo ""
        echo "故障排除:"
        echo "  如果前端启动失败，运行: ./start.sh clean"
        echo "  如果问题仍存在，运行: cd frontend && rm -rf node_modules package-lock.json && npm install"
        ;;
esac
