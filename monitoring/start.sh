#!/bin/bash
set -e

# 无论从哪个目录执行，都能正确找到 monitoring 目录
MONITORING_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$MONITORING_DIR"

echo "🚀 Starting Sentinel Monitoring Stack..."
echo ""

# 创建日志目录
mkdir -p logs

# 启动所有服务
echo "📦 Starting Docker containers..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# 检查 Prometheus
echo -n "🔍 Checking Prometheus... "
if curl -s http://localhost:9091/-/ready > /dev/null 2>&1; then
    echo "✅ Ready"
else
    echo "❌ Not ready (may need more time)"
fi

# 检查 Loki
echo -n "🔍 Checking Loki... "
if curl -s http://localhost:3100/ready > /dev/null 2>&1; then
    echo "✅ Ready"
else
    echo "❌ Not ready (may need more time)"
fi

# 检查 auth-service（未映射主机端口，在容器内检查）
echo -n "🔍 Checking auth-service... "
if docker compose exec -T auth-service curl -s http://localhost:8080/ > /dev/null 2>&1; then
    echo "✅ Ready"
else
    echo "❌ Not ready (may need more time)"
fi

echo ""
echo "✅ Monitoring stack is running!"
echo ""
echo "📊 Access points:"
echo "  - Prometheus:   http://localhost:9091"
echo "  - Loki:         http://localhost:3100"
echo "  - Grafana:      http://localhost:3000 (admin/admin)"
echo "  - Auth Service: 未映射主机端口（支持 scale），从宿主机调用请用下方 exec 命令"
echo ""
echo "🧪 Test commands (在 monitoring 目录下执行):"
echo "  # 进入任意 auth-service 容器内请求"
echo "  docker compose exec auth-service curl -s http://localhost:8080/"
echo "  docker compose exec auth-service curl -X POST http://localhost:8080/api/auth -H 'Content-Type: application/json' -d '{}'"
echo ""
echo "  # Simulate high CPU / high latency / redis-timeout / load（均在 exec 后加 curl 请求上述 API）"
echo "  docker compose exec auth-service curl -X POST http://localhost:8080/api/simulate/high-cpu -H 'Content-Type: application/json' -d '{\"enable\": true}'"
echo "  docker compose exec auth-service curl -X POST http://localhost:8080/api/load -H 'Content-Type: application/json' -d '{\"count\": 50}'"
echo ""
echo "📝 View logs:"
echo "  docker-compose logs -f auth-service"
echo ""
echo "🛑 Stop stack:"
echo "  ./stop.sh"
echo ""
