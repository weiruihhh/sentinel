"""
Mock tools for demonstration and testing.

These tools return simulated data for various datacenter operations scenarios.
"""

from datetime import datetime, timedelta
from typing import Any

from sentinel.tools.registry import ToolRegistry, ToolSpec
from sentinel.types import PermissionLevel, RiskLevel


# ===== Mock Data Sources =====

MOCK_METRICS_DB = {
    "auth-service": {
        "cpu_percent": [
            {"timestamp": "2024-01-20T14:15:00Z", "value": 35.2},
            {"timestamp": "2024-01-20T14:20:00Z", "value": 38.1},
            {"timestamp": "2024-01-20T14:23:00Z", "value": 95.7},  # Spike!
            {"timestamp": "2024-01-20T14:25:00Z", "value": 94.3},
            {"timestamp": "2024-01-20T14:30:00Z", "value": 92.8},
        ],
        "memory_percent": [
            {"timestamp": "2024-01-20T14:15:00Z", "value": 62.1},
            {"timestamp": "2024-01-20T14:30:00Z", "value": 68.5},
        ],
        "request_latency_p99": [
            {"timestamp": "2024-01-20T14:15:00Z", "value": 120},  # ms
            {"timestamp": "2024-01-20T14:20:00Z", "value": 135},
            {"timestamp": "2024-01-20T14:23:00Z", "value": 850},  # Spike!
            {"timestamp": "2024-01-20T14:30:00Z", "value": 780},
        ],
        "qps": [
            {"timestamp": "2024-01-20T14:15:00Z", "value": 1250},
            {"timestamp": "2024-01-20T14:30:00Z", "value": 1200},
        ],
    },
    "redis-cache": {
        "cpu_percent": [
            {"timestamp": "2024-01-20T14:15:00Z", "value": 15.2},
            {"timestamp": "2024-01-20T14:30:00Z", "value": 18.3},
        ],
        "memory_percent": [
            {"timestamp": "2024-01-20T14:15:00Z", "value": 45.1},
            {"timestamp": "2024-01-20T14:30:00Z", "value": 47.2},
        ],
    },
}

MOCK_LOGS_DB = {
    "auth-service": [
        {
            "timestamp": "2024-01-20T14:23:15Z",
            "level": "ERROR",
            "message": "Connection timeout to redis-cache:6379",
            "count": 45,
        },
        {
            "timestamp": "2024-01-20T14:24:30Z",
            "level": "WARN",
            "message": "High CPU usage detected: 95.7%",
            "count": 1,
        },
        {
            "timestamp": "2024-01-20T14:25:00Z",
            "level": "ERROR",
            "message": "Failed to acquire lock: timeout",
            "count": 23,
        },
    ],
    "redis-cache": [
        {
            "timestamp": "2024-01-20T14:22:00Z",
            "level": "INFO",
            "message": "Connected clients: 125",
            "count": 1,
        },
    ],
}

MOCK_TOPOLOGY = {
    "services": [
        {
            "name": "auth-service",
            "type": "application",
            "replicas": 3,
            "version": "v2.3.1",
            "dependencies": ["redis-cache", "postgres-db"],
            "health_status": "degraded",
        },
        {
            "name": "redis-cache",
            "type": "cache",
            "replicas": 2,
            "version": "7.0.5",
            "dependencies": [],
            "health_status": "healthy",
        },
        {
            "name": "postgres-db",
            "type": "database",
            "replicas": 1,
            "version": "14.5",
            "dependencies": [],
            "health_status": "healthy",
        },
    ],
    "connections": [
        {"from": "auth-service", "to": "redis-cache", "protocol": "redis", "port": 6379},
        {
            "from": "auth-service",
            "to": "postgres-db",
            "protocol": "postgresql",
            "port": 5432,
        },
    ],
}

MOCK_CHANGE_HISTORY = [
    {
        "timestamp": "2024-01-20T14:20:00Z",
        "type": "deployment",
        "service": "auth-service",
        "from_version": "v2.3.0",
        "to_version": "v2.3.1",
        "author": "deploy-bot",
        "description": "Release v2.3.1: Added connection pooling optimization",
        "status": "completed",
    },
    {
        "timestamp": "2024-01-20T10:15:00Z",
        "type": "config_change",
        "service": "redis-cache",
        "parameter": "maxmemory",
        "from_value": "2GB",
        "to_value": "4GB",
        "author": "ops-team",
        "status": "completed",
    },
    {
        "timestamp": "2024-01-19T16:30:00Z",
        "type": "deployment",
        "service": "postgres-db",
        "from_version": "14.4",
        "to_version": "14.5",
        "author": "dba-team",
        "description": "Security patch update",
        "status": "completed",
    },
]


# ===== Tool Implementations =====


def query_metrics(
    service: str,
    metric: str,
    start_time: str = "",
    end_time: str = "",
    aggregation: str = "avg",
) -> dict[str, Any]:
    """
    Query metrics for a service.

    Args:
        service: Service name
        metric: Metric name (e.g., cpu_percent, memory_percent, request_latency_p99)
        start_time: Start time (ISO format, optional)
        end_time: End time (ISO format, optional)
        aggregation: Aggregation method (avg, max, min)

    Returns:
        Metric data points
    """
    service_metrics = MOCK_METRICS_DB.get(service, {})
    metric_data = service_metrics.get(metric, [])

    if not metric_data:
        return {
            "service": service,
            "metric": metric,
            "data": [],
            "message": f"No data found for {service}.{metric}",
        }

    # Simple aggregation
    values = [point["value"] for point in metric_data]
    if aggregation == "avg":
        agg_value = sum(values) / len(values) if values else 0
    elif aggregation == "max":
        agg_value = max(values) if values else 0
    elif aggregation == "min":
        agg_value = min(values) if values else 0
    else:
        agg_value = sum(values) / len(values) if values else 0

    return {
        "service": service,
        "metric": metric,
        "data": metric_data,
        "aggregation": {aggregation: agg_value},
        "data_points": len(metric_data),
    }


def query_logs(
    service: str,
    level: str = "ERROR",
    limit: int = 100,
    since: str = "",
) -> dict[str, Any]:
    """
    Query logs for a service.

    Args:
        service: Service name
        level: Log level filter (ERROR, WARN, INFO)
        limit: Maximum number of log entries
        since: Start time (ISO format, optional)

    Returns:
        Log entries
    """
    service_logs = MOCK_LOGS_DB.get(service, [])

    # Filter by level
    if level:
        service_logs = [log for log in service_logs if log["level"] == level]

    # Apply limit
    service_logs = service_logs[:limit]

    return {
        "service": service,
        "level": level,
        "logs": service_logs,
        "total_entries": len(service_logs),
    }


def query_topology(service: str = "") -> dict[str, Any]:
    """
    Query service topology.

    Args:
        service: Optional service name to filter by

    Returns:
        Topology information
    """
    if service:
        # Filter topology for specific service
        service_info = next(
            (s for s in MOCK_TOPOLOGY["services"] if s["name"] == service), None
        )
        if not service_info:
            return {
                "error": f"Service '{service}' not found",
                "available_services": [s["name"] for s in MOCK_TOPOLOGY["services"]],
            }

        # Get connections involving this service
        related_connections = [
            conn
            for conn in MOCK_TOPOLOGY["connections"]
            if conn["from"] == service or conn["to"] == service
        ]

        return {
            "service": service_info,
            "connections": related_connections,
        }
    else:
        # Return full topology
        return MOCK_TOPOLOGY.copy()


def get_change_history(
    service: str = "",
    change_type: str = "",
    since_hours: int = 24,
) -> dict[str, Any]:
    """
    Get change history (deployments, config changes, etc.).

    Args:
        service: Optional service name to filter by
        change_type: Optional change type (deployment, config_change, scale, etc.)
        since_hours: Look back window in hours

    Returns:
        Change history entries
    """
    changes = MOCK_CHANGE_HISTORY.copy()

    # Filter by service
    if service:
        changes = [c for c in changes if c.get("service") == service]

    # Filter by type
    if change_type:
        changes = [c for c in changes if c.get("type") == change_type]

    # Filter by time (simplified - in production would parse timestamps)
    # For mock, we assume all changes are within the window

    return {
        "changes": changes,
        "total_count": len(changes),
        "filter": {
            "service": service or "all",
            "type": change_type or "all",
            "since_hours": since_hours,
        },
    }


# ===== Tool Registration =====


def register_mock_tools(registry: ToolRegistry) -> None:
    """
    Register all mock tools to the registry.

    Args:
        registry: Tool registry instance
    """
    # query_metrics tool
    registry.register(
        ToolSpec(
            name="query_metrics",
            description="Query metrics (CPU, memory, latency, etc.) for a service",
            input_schema={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service name"},
                    "metric": {
                        "type": "string",
                        "description": "Metric name (cpu_percent, memory_percent, etc.)",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time (ISO format, optional)",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time (ISO format, optional)",
                    },
                    "aggregation": {
                        "type": "string",
                        "description": "Aggregation method (avg, max, min)",
                        "default": "avg",
                    },
                },
                "required": ["service", "metric"],
            },
            risk_level=RiskLevel.READ_ONLY,
            permission_required=PermissionLevel.GUEST,
            handler=query_metrics,
            tags=["metrics", "monitoring", "read-only"],
        )
    )

    # query_logs tool
    registry.register(
        ToolSpec(
            name="query_logs",
            description="Query logs for a service with filtering",
            input_schema={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service name"},
                    "level": {
                        "type": "string",
                        "description": "Log level (ERROR, WARN, INFO)",
                        "default": "ERROR",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum entries to return",
                        "default": 100,
                    },
                    "since": {
                        "type": "string",
                        "description": "Start time (ISO format, optional)",
                    },
                },
                "required": ["service"],
            },
            risk_level=RiskLevel.READ_ONLY,
            permission_required=PermissionLevel.GUEST,
            handler=query_logs,
            tags=["logs", "monitoring", "read-only"],
        )
    )

    # query_topology tool
    registry.register(
        ToolSpec(
            name="query_topology",
            description="Query service topology and dependencies",
            input_schema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name (optional, returns full topology if empty)",
                    },
                },
                "required": [],
            },
            risk_level=RiskLevel.READ_ONLY,
            permission_required=PermissionLevel.GUEST,
            handler=query_topology,
            tags=["topology", "architecture", "read-only"],
        )
    )

    # get_change_history tool
    registry.register(
        ToolSpec(
            name="get_change_history",
            description="Get change history (deployments, config changes, etc.)",
            input_schema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name (optional filter)",
                    },
                    "change_type": {
                        "type": "string",
                        "description": "Change type (deployment, config_change, etc.)",
                    },
                    "since_hours": {
                        "type": "integer",
                        "description": "Look back window in hours",
                        "default": 24,
                    },
                },
                "required": [],
            },
            risk_level=RiskLevel.READ_ONLY,
            permission_required=PermissionLevel.GUEST,
            handler=get_change_history,
            tags=["change", "history", "audit", "read-only"],
        )
    )
