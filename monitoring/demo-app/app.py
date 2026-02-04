"""
Demo application for Sentinel monitoring stack.

This app simulates a microservice that:
- Exposes Prometheus metrics
- Generates structured JSON logs
- Connects to Redis
- Can simulate various failure scenarios
"""

import json
import logging
import os
import random
import time
from datetime import datetime
from threading import Thread

import redis
from flask import Flask, jsonify, request
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# Configuration
SERVICE_NAME = os.getenv("SERVICE_NAME", "auth-service")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Flask app
app = Flask(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
)
CPU_USAGE = Gauge("container_cpu_usage_seconds_total", "CPU usage")
MEMORY_USAGE = Gauge("container_memory_usage_bytes", "Memory usage")
MEMORY_LIMIT = Gauge("container_spec_memory_limit_bytes", "Memory limit")

# Set memory limit (simulated)
MEMORY_LIMIT.set(1024 * 1024 * 1024)  # 1GB

# Redis client
redis_client = None

# Failure simulation flags
simulate_high_cpu = False
simulate_high_latency = False
simulate_redis_timeout = False


# ===== Logging Setup =====


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": SERVICE_NAME,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


# Setup logging
log_dir = "/app/logs"
os.makedirs(log_dir, exist_ok=True)
log_file = f"{log_dir}/{SERVICE_NAME}.log"

file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(JSONFormatter())

console_handler = logging.StreamHandler()
console_handler.setFormatter(JSONFormatter())

logger = logging.getLogger(SERVICE_NAME)
logger.setLevel(getattr(logging, LOG_LEVEL))
logger.addHandler(file_handler)
logger.addHandler(console_handler)


# ===== Redis Connection =====


def init_redis():
    """Initialize Redis connection."""
    global redis_client
    max_retries = 5
    for i in range(max_retries):
        try:
            redis_client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, socket_timeout=5
            )
            redis_client.ping()
            logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            return
        except Exception as e:
            logger.warning(f"Failed to connect to Redis (attempt {i+1}/{max_retries}): {e}")
            time.sleep(2)
    logger.error("Could not connect to Redis after multiple attempts")


# ===== Background Tasks =====


def background_metrics_updater():
    """Update system metrics in background."""
    while True:
        try:
            # Simulate CPU usage
            if simulate_high_cpu:
                cpu_value = random.uniform(0.90, 0.98)  # 90-98%
            else:
                cpu_value = random.uniform(0.20, 0.40)  # 20-40%
            CPU_USAGE.set(cpu_value)

            # Simulate memory usage
            if simulate_high_cpu:  # High CPU often correlates with high memory
                mem_value = random.uniform(700, 900) * 1024 * 1024  # 700-900MB
            else:
                mem_value = random.uniform(400, 600) * 1024 * 1024  # 400-600MB
            MEMORY_USAGE.set(mem_value)

            time.sleep(5)
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
            time.sleep(5)


# ===== API Endpoints =====


@app.before_request
def before_request():
    """Record request start time."""
    request.start_time = time.time()


@app.after_request
def after_request(response):
    """Record metrics after request."""
    if hasattr(request, "start_time"):
        latency = time.time() - request.start_time
        REQUEST_LATENCY.labels(
            method=request.method, endpoint=request.path
        ).observe(latency)
        REQUEST_COUNT.labels(
            method=request.method, endpoint=request.path, status=response.status_code
        ).inc()
    return response


@app.route("/")
def index():
    """Health check endpoint."""
    return jsonify({"service": SERVICE_NAME, "status": "healthy"})


@app.route("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


@app.route("/api/auth", methods=["POST"])
def authenticate():
    """Simulate authentication endpoint."""
    start = time.time()

    # Simulate high latency if flag is set
    if simulate_high_latency:
        delay = random.uniform(0.5, 1.5)  # 500-1500ms
        time.sleep(delay)
        logger.warning(f"High latency detected: {delay*1000:.0f}ms")

    # Try to use Redis
    try:
        if redis_client:
            if simulate_redis_timeout:
                # Simulate Redis timeout
                time.sleep(6)  # Longer than socket_timeout
            else:
                # Normal Redis operation
                token = f"token_{random.randint(1000, 9999)}"
                redis_client.setex(f"session:{token}", 3600, "user_data")
                logger.info(f"Authentication successful, token: {token}")
                return jsonify({"status": "success", "token": token})
    except redis.exceptions.TimeoutError:
        logger.error("Connection timeout to redis-cache:6379", extra={"count": 1})
        return jsonify({"status": "error", "message": "Redis timeout"}), 500
    except Exception as e:
        logger.error(f"Redis error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    # Fallback if Redis is not available
    logger.warning("Redis not available, using fallback")
    return jsonify({"status": "success", "token": "fallback_token"})


@app.route("/api/simulate/high-cpu", methods=["POST"])
def simulate_cpu():
    """Enable/disable high CPU simulation."""
    global simulate_high_cpu
    enable = request.json.get("enable", True)
    simulate_high_cpu = enable
    logger.warning(f"High CPU simulation: {'enabled' if enable else 'disabled'}")
    return jsonify({"simulate_high_cpu": simulate_high_cpu})


@app.route("/api/simulate/high-latency", methods=["POST"])
def simulate_latency():
    """Enable/disable high latency simulation."""
    global simulate_high_latency
    enable = request.json.get("enable", True)
    simulate_high_latency = enable
    logger.warning(f"High latency simulation: {'enabled' if enable else 'disabled'}")
    return jsonify({"simulate_high_latency": simulate_high_latency})


@app.route("/api/simulate/redis-timeout", methods=["POST"])
def simulate_redis_fail():
    """Enable/disable Redis timeout simulation."""
    global simulate_redis_timeout
    enable = request.json.get("enable", True)
    simulate_redis_timeout = enable
    logger.warning(f"Redis timeout simulation: {'enabled' if enable else 'disabled'}")
    return jsonify({"simulate_redis_timeout": simulate_redis_timeout})


@app.route("/api/load", methods=["POST"])
def generate_load():
    """Generate load for testing."""
    count = request.json.get("count", 10)
    results = {"success": 0, "error": 0}

    for i in range(count):
        try:
            # Simulate some work
            time.sleep(random.uniform(0.01, 0.05))
            if random.random() < 0.9:  # 90% success rate
                results["success"] += 1
            else:
                results["error"] += 1
                logger.error(f"Failed to acquire lock: timeout")
        except Exception as e:
            results["error"] += 1
            logger.error(f"Load generation error: {e}")

    logger.info(f"Load test completed: {results}")
    return jsonify(results)


# ===== Main =====


if __name__ == "__main__":
    logger.info(f"Starting {SERVICE_NAME}")

    # Initialize Redis
    init_redis()

    # Start background metrics updater
    metrics_thread = Thread(target=background_metrics_updater, daemon=True)
    metrics_thread.start()

    # Start Flask app
    app.run(host="0.0.0.0", port=8080, debug=False)
