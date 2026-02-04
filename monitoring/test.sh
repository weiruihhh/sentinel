#!/bin/bash
# Test script to simulate various failure scenarios

# Get the first auth-service container
CONTAINER=$(docker compose -p monitoring ps -q auth-service | head -1)

if [ -z "$CONTAINER" ]; then
    echo "❌ No auth-service container found. Please start the monitoring stack first."
    exit 1
fi

echo "🧪 Sentinel Monitoring Stack - Test Script"
echo "📦 Using container: $CONTAINER"
echo ""

# Function to make API calls via docker exec
call_api() {
    local endpoint=$1
    local data=$2
    echo "📡 Calling $endpoint..."
    docker exec "$CONTAINER" python -c "
import urllib.request
import json

data = json.loads('$data')
req = urllib.request.Request(
    'http://localhost:8080$endpoint',
    data=json.dumps(data).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
try:
    with urllib.request.urlopen(req, timeout=5) as response:
        result = json.loads(response.read().decode('utf-8'))
        print(json.dumps(result, indent=2))
except Exception as e:
    print('Response received (or error:', str(e), ')')
"
    echo ""
}

# Check if argument provided (non-interactive mode)
if [ $# -gt 0 ]; then
    case "$1" in
        cpu_high|cpu_spike)
            choice=2
            ;;
        latency_spike|high_latency)
            choice=3
            ;;
        redis_timeout)
            choice=4
            ;;
        heavy_load)
            choice=5
            ;;
        all_failures)
            choice=6
            ;;
        reset)
            choice=7
            ;;
        continuous)
            choice=8
            ;;
        normal)
            choice=1
            ;;
        *)
            echo "❌ Unknown scenario: $1"
            echo "Available scenarios: cpu_high, latency_spike, redis_timeout, heavy_load, all_failures, reset, continuous, normal"
            exit 1
            ;;
    esac
else
    # Interactive menu
    echo "Select test scenario:"
    echo "1) Normal traffic (10 requests)"
    echo "2) Simulate CPU spike"
    echo "3) Simulate high latency"
    echo "4) Simulate Redis timeout"
    echo "5) Generate heavy load (100 requests)"
    echo "6) Trigger all failures (CPU + Latency + Redis)"
    echo "7) Reset all simulations"
    echo "8) Run continuous load test"
    echo ""
    read -p "Enter choice [1-8]: " choice
fi

case $choice in
    1)
        echo "🔄 Generating normal traffic..."
        for i in {1..10}; do
            call_api "/api/auth" '{}'
            sleep 0.5
        done
        ;;
    2)
        echo "🔥 Enabling CPU spike simulation..."
        call_api "/api/simulate/high-cpu" '{"enable": true}'
        echo "⏰ CPU will be high for the next few minutes"
        echo "💡 Check Prometheus: http://localhost:9090/graph?g0.expr=container_cpu_usage_seconds_total"
        ;;
    3)
        echo "🐌 Enabling high latency simulation..."
        call_api "/api/simulate/high-latency" '{"enable": true}'
        echo "⏰ Latency will be high for the next few minutes"
        echo "💡 Check Prometheus: http://localhost:9090/graph?g0.expr=http_request_duration_seconds"
        ;;
    4)
        echo "⏱️  Enabling Redis timeout simulation..."
        call_api "/api/simulate/redis-timeout" '{"enable": true}'
        echo "⏰ Redis timeouts will occur for the next few minutes"
        echo "💡 Check logs: docker-compose logs -f auth-service | grep ERROR"
        ;;
    5)
        echo "💥 Generating heavy load..."
        call_api "/api/load" '{"count": 100}'
        ;;
    6)
        echo "🚨 TRIGGERING ALL FAILURES..."
        call_api "/api/simulate/high-cpu" '{"enable": true}'
        call_api "/api/simulate/high-latency" '{"enable": true}'
        call_api "/api/simulate/redis-timeout" '{"enable": true}'
        echo ""
        echo "⚠️  All failure modes enabled!"
        echo "💡 This simulates the scenario in your mock data"
        echo "💡 Now run Sentinel to diagnose:"
        echo "   cd .."
        echo "   python main.py --use-real-tools --prometheus-url http://localhost:9090 --loki-url http://localhost:3100"
        ;;
    7)
        echo "🔄 Resetting all simulations..."
        call_api "/api/simulate/high-cpu" '{"enable": false}'
        call_api "/api/simulate/high-latency" '{"enable": false}'
        call_api "/api/simulate/redis-timeout" '{"enable": false}'
        echo "✅ All simulations disabled"
        ;;
    8)
        echo "🔁 Running continuous load test (Ctrl+C to stop)..."
        while true; do
            call_api "/api/auth" '{}'
            sleep 1
        done
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "✅ Test completed"
echo ""
echo "📊 View results:"
echo "  - Prometheus: http://localhost:9090"
echo "  - Grafana:    http://localhost:3000"
echo "  - Logs:       docker-compose logs -f auth-service"
echo ""
