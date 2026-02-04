#!/bin/bash
set -e

# 无论从哪个目录执行，都能正确找到 monitoring 目录
cd "$(cd "$(dirname "$0")" && pwd)"

echo "🛑 Stopping Sentinel Monitoring Stack..."
docker-compose down

echo ""
echo "✅ All services stopped"
echo ""
echo "💡 To remove all data volumes, run:"
echo "   docker-compose down -v"
echo ""
