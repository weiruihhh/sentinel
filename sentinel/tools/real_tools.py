"""
Real data source tools for production use.

These tools connect to actual monitoring systems, CMDB, and change tracking systems.
"""

import json
import logging
import subprocess
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import requests

from sentinel.config import DataSourcesConfig
from sentinel.tools.registry import ToolRegistry, ToolSpec
from sentinel.types import PermissionLevel, RiskLevel

logger = logging.getLogger(__name__)


# ===== Prometheus Integration =====


def query_metrics_prometheus(
    config: DataSourcesConfig,
    service: str,
    metric: str,
    start_time: str = "",
    end_time: str = "",
    aggregation: str = "avg",
) -> dict[str, Any]:
    """
    Query metrics from Prometheus.

    Args:
        config: Data sources configuration
        service: Service name
        metric: Metric name (e.g., cpu_percent, memory_percent, request_latency_p99)
        start_time: Start time (ISO format, optional)
        end_time: End time (ISO format, optional)
        aggregation: Aggregation method (avg, max, min)

    Returns:
        Metric data points
    """
    try:
        # Build PromQL query based on metric name
        # This is a simplified mapping - adjust based on your actual metric names
        metric_mapping = {
            "cpu_percent": f'avg(rate(container_cpu_usage_seconds_total{{service="{service}"}}[5m])) * 100',
            "memory_percent": f'avg(container_memory_usage_bytes{{service="{service}"}} / container_spec_memory_limit_bytes{{service="{service}"}}) * 100',
            "request_latency_p99": f'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{{service="{service}"}}[5m])) * 1000',
            "qps": f'sum(rate(http_requests_total{{service="{service}"}}[5m]))',
        }

        promql = metric_mapping.get(metric, f'{metric}{{service="{service}"}}')

        # Determine time range
        if not end_time:
            end_time = datetime.now().isoformat()
        if not start_time:
            start_time = (datetime.now() - timedelta(hours=1)).isoformat()

        # Convert ISO to Unix timestamp
        end_ts = datetime.fromisoformat(end_time.replace("Z", "+00:00")).timestamp()
        start_ts = datetime.fromisoformat(start_time.replace("Z", "+00:00")).timestamp()

        # Query Prometheus range API
        params = {
            "query": promql,
            "start": start_ts,
            "end": end_ts,
            "step": "60s",  # 1 minute resolution
        }

        url = f"{config.prometheus_url}/api/v1/query_range"
        response = requests.get(
            url, params=params, timeout=config.prometheus_timeout
        )
        response.raise_for_status()

        data = response.json()

        if data["status"] != "success":
            return {
                "service": service,
                "metric": metric,
                "data": [],
                "error": f"Prometheus query failed: {data.get('error', 'unknown')}",
            }

        # Parse results
        results = data.get("data", {}).get("result", [])
        if not results:
            return {
                "service": service,
                "metric": metric,
                "data": [],
                "message": f"No data found for {service}.{metric}",
            }

        # Extract time series data
        metric_data = []
        all_values = []
        for result in results:
            for timestamp, value in result.get("values", []):
                dt = datetime.fromtimestamp(timestamp).isoformat() + "Z"
                val = float(value)
                metric_data.append({"timestamp": dt, "value": val})
                all_values.append(val)

        # Calculate aggregation
        if all_values:
            if aggregation == "avg":
                agg_value = sum(all_values) / len(all_values)
            elif aggregation == "max":
                agg_value = max(all_values)
            elif aggregation == "min":
                agg_value = min(all_values)
            else:
                agg_value = sum(all_values) / len(all_values)
        else:
            agg_value = 0

        return {
            "service": service,
            "metric": metric,
            "data": metric_data,
            "aggregation": {aggregation: agg_value},
            "data_points": len(metric_data),
        }

    except requests.RequestException as e:
        logger.error(f"Prometheus query failed: {e}")
        return {
            "service": service,
            "metric": metric,
            "data": [],
            "error": f"Failed to query Prometheus: {str(e)}",
        }
    except Exception as e:
        logger.error(f"Unexpected error in query_metrics_prometheus: {e}")
        return {
            "service": service,
            "metric": metric,
            "data": [],
            "error": f"Unexpected error: {str(e)}",
        }


# ===== Loki Integration =====


def query_logs_loki(
    config: DataSourcesConfig,
    service: str,
    level: str = "ERROR",
    limit: int = 100,
    since: str = "",
) -> dict[str, Any]:
    """
    Query logs from Loki.

    Args:
        config: Data sources configuration
        service: Service name
        level: Log level filter (ERROR, WARN, INFO)
        limit: Maximum number of log entries
        since: Start time (ISO format, optional)

    Returns:
        Log entries
    """
    try:
        # Build LogQL query
        logql = f'{{service="{service}"}}'
        if level:
            logql += f' |= "{level}"'

        # Determine time range
        if not since:
            since = (datetime.now() - timedelta(hours=1)).isoformat()

        since_ts = datetime.fromisoformat(since.replace("Z", "+00:00")).timestamp()
        now_ts = datetime.now().timestamp()

        # Query Loki
        params = {
            "query": logql,
            "start": int(since_ts * 1e9),  # Loki uses nanoseconds
            "end": int(now_ts * 1e9),
            "limit": limit,
            "direction": "backward",  # Most recent first
        }

        url = f"{config.loki_url}/loki/api/v1/query_range"
        response = requests.get(url, params=params, timeout=config.loki_timeout)
        response.raise_for_status()

        data = response.json()

        if data["status"] != "success":
            return {
                "service": service,
                "level": level,
                "logs": [],
                "error": f"Loki query failed: {data.get('error', 'unknown')}",
            }

        # Parse results
        results = data.get("data", {}).get("result", [])
        logs = []

        for stream in results:
            for entry in stream.get("values", []):
                timestamp_ns, log_line = entry
                timestamp = datetime.fromtimestamp(
                    int(timestamp_ns) / 1e9
                ).isoformat() + "Z"

                # Try to parse structured logs (JSON)
                try:
                    log_obj = json.loads(log_line)
                    logs.append(
                        {
                            "timestamp": timestamp,
                            "level": log_obj.get("level", level),
                            "message": log_obj.get("message", log_line),
                            "count": 1,
                        }
                    )
                except json.JSONDecodeError:
                    # Plain text log
                    logs.append(
                        {
                            "timestamp": timestamp,
                            "level": level,
                            "message": log_line,
                            "count": 1,
                        }
                    )

        return {
            "service": service,
            "level": level,
            "logs": logs[:limit],
            "total_entries": len(logs),
        }

    except requests.RequestException as e:
        logger.error(f"Loki query failed: {e}")
        return {
            "service": service,
            "level": level,
            "logs": [],
            "error": f"Failed to query Loki: {str(e)}",
        }
    except Exception as e:
        logger.error(f"Unexpected error in query_logs_loki: {e}")
        return {
            "service": service,
            "level": level,
            "logs": [],
            "error": f"Unexpected error: {str(e)}",
        }


# ===== Elasticsearch Integration (Alternative for logs) =====


def query_logs_elasticsearch(
    config: DataSourcesConfig,
    service: str,
    level: str = "ERROR",
    limit: int = 100,
    since: str = "",
) -> dict[str, Any]:
    """
    Query logs from Elasticsearch.

    Args:
        config: Data sources configuration
        service: Service name
        level: Log level filter (ERROR, WARN, INFO)
        limit: Maximum number of log entries
        since: Start time (ISO format, optional)

    Returns:
        Log entries
    """
    try:
        if not config.elasticsearch_url:
            return {
                "service": service,
                "level": level,
                "logs": [],
                "error": "Elasticsearch URL not configured",
            }

        # Build Elasticsearch query
        if not since:
            since = (datetime.now() - timedelta(hours=1)).isoformat()

        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"service": service}},
                        {"match": {"level": level}},
                        {"range": {"@timestamp": {"gte": since}}},
                    ]
                }
            },
            "sort": [{"@timestamp": {"order": "desc"}}],
            "size": limit,
        }

        url = f"{config.elasticsearch_url}/{config.elasticsearch_index}/_search"
        response = requests.post(
            url,
            json=query,
            headers={"Content-Type": "application/json"},
            timeout=config.elasticsearch_timeout,
        )
        response.raise_for_status()

        data = response.json()
        hits = data.get("hits", {}).get("hits", [])

        logs = []
        for hit in hits:
            source = hit["_source"]
            logs.append(
                {
                    "timestamp": source.get("@timestamp", ""),
                    "level": source.get("level", level),
                    "message": source.get("message", ""),
                    "count": 1,
                }
            )

        return {
            "service": service,
            "level": level,
            "logs": logs,
            "total_entries": len(logs),
        }

    except requests.RequestException as e:
        logger.error(f"Elasticsearch query failed: {e}")
        return {
            "service": service,
            "level": level,
            "logs": [],
            "error": f"Failed to query Elasticsearch: {str(e)}",
        }
    except Exception as e:
        logger.error(f"Unexpected error in query_logs_elasticsearch: {e}")
        return {
            "service": service,
            "level": level,
            "logs": [],
            "error": f"Unexpected error: {str(e)}",
        }


# ===== CMDB / Topology Integration =====


def query_topology_cmdb(
    config: DataSourcesConfig, service: str = ""
) -> dict[str, Any]:
    """
    Query service topology from CMDB.

    Args:
        config: Data sources configuration
        service: Optional service name to filter by

    Returns:
        Topology information
    """
    try:
        if not config.cmdb_url:
            return {
                "error": "CMDB URL not configured",
                "message": "Please set data_sources.cmdb_url in config",
            }

        # Query CMDB API
        headers = {}
        if config.cmdb_api_key:
            headers["Authorization"] = f"Bearer {config.cmdb_api_key}"

        params = {}
        if service:
            params["service"] = service

        url = f"{config.cmdb_url}/api/v1/topology"
        response = requests.get(
            url, params=params, headers=headers, timeout=config.cmdb_timeout
        )
        response.raise_for_status()

        data = response.json()

        # Normalize response format to match mock_tools structure
        if service:
            # Filter for specific service
            services = data.get("services", [])
            service_info = next(
                (s for s in services if s["name"] == service), None
            )

            if not service_info:
                return {
                    "error": f"Service '{service}' not found",
                    "available_services": [s["name"] for s in services],
                }

            connections = [
                conn
                for conn in data.get("connections", [])
                if conn["from"] == service or conn["to"] == service
            ]

            return {"service": service_info, "connections": connections}
        else:
            return data

    except requests.RequestException as e:
        logger.error(f"CMDB query failed: {e}")
        return {
            "error": f"Failed to query CMDB: {str(e)}",
            "message": "Check CMDB URL and API key configuration",
        }
    except Exception as e:
        logger.error(f"Unexpected error in query_topology_cmdb: {e}")
        return {"error": f"Unexpected error: {str(e)}"}


# ===== Change History Integration =====


def get_change_history_real(
    config: DataSourcesConfig,
    service: str = "",
    change_type: str = "",
    since_hours: int = 24,
) -> dict[str, Any]:
    """
    Get change history from Git and CD systems.

    Args:
        config: Data sources configuration
        service: Optional service name to filter by
        change_type: Optional change type (deployment, config_change, etc.)
        since_hours: Look back window in hours

    Returns:
        Change history entries
    """
    changes = []

    # Query Git history if configured
    if config.git_repo_path:
        try:
            git_changes = _query_git_history(
                config.git_repo_path, service, since_hours
            )
            changes.extend(git_changes)
        except Exception as e:
            logger.error(f"Failed to query Git history: {e}")

    # Query CD system if configured
    if config.cd_api_url:
        try:
            cd_changes = _query_cd_system(
                config.cd_api_url, config.cd_api_key, service, since_hours
            )
            changes.extend(cd_changes)
        except Exception as e:
            logger.error(f"Failed to query CD system: {e}")

    # Filter by change type
    if change_type:
        changes = [c for c in changes if c.get("type") == change_type]

    # Sort by timestamp (most recent first)
    changes.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return {
        "changes": changes,
        "total_count": len(changes),
        "filter": {
            "service": service or "all",
            "type": change_type or "all",
            "since_hours": since_hours,
        },
    }


def _query_git_history(
    repo_path: str, service: str, since_hours: int
) -> list[dict[str, Any]]:
    """Query Git commit history."""
    since_time = datetime.now() - timedelta(hours=since_hours)
    since_str = since_time.strftime("%Y-%m-%d %H:%M:%S")

    # Git log command
    cmd = [
        "git",
        "-C",
        repo_path,
        "log",
        f"--since={since_str}",
        "--pretty=format:%H|%an|%ai|%s",
        "--",
    ]

    if service:
        # Filter by service directory/files
        cmd.append(f"*{service}*")

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    changes = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue

        parts = line.split("|", 3)
        if len(parts) == 4:
            commit_hash, author, timestamp, message = parts
            changes.append(
                {
                    "timestamp": timestamp,
                    "type": "code_change",
                    "service": service or "unknown",
                    "commit": commit_hash[:8],
                    "author": author,
                    "description": message,
                    "status": "completed",
                }
            )

    return changes


def _query_cd_system(
    cd_url: str, api_key: str, service: str, since_hours: int
) -> list[dict[str, Any]]:
    """Query CD system (e.g., ArgoCD, Jenkins) for deployments."""
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    since_time = datetime.now() - timedelta(hours=since_hours)

    params = {"since": since_time.isoformat()}
    if service:
        params["service"] = service

    # This is a generic endpoint - adjust based on your CD system
    url = f"{cd_url}/api/deployments"
    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()

    data = response.json()

    # Normalize to our format
    changes = []
    for deployment in data.get("deployments", []):
        changes.append(
            {
                "timestamp": deployment.get("timestamp", ""),
                "type": "deployment",
                "service": deployment.get("service", service),
                "from_version": deployment.get("from_version", ""),
                "to_version": deployment.get("to_version", ""),
                "author": deployment.get("author", ""),
                "description": deployment.get("description", ""),
                "status": deployment.get("status", "completed"),
            }
        )

    return changes


# ===== Docker Compose Write Operations =====


def _run_docker_compose_command(
    config: DataSourcesConfig,
    args: list[str],
    capture_output: bool = True,
) -> subprocess.CompletedProcess:
    """
    Run docker-compose command.

    Args:
        config: Data sources configuration
        args: Command arguments
        capture_output: Whether to capture output

    Returns:
        CompletedProcess result
    """
    cmd = ["docker-compose"]

    # Add project name if specified
    if config.docker_compose_project:
        cmd.extend(["-p", config.docker_compose_project])

    # Add compose file if specified
    if config.docker_compose_file:
        cmd.extend(["-f", config.docker_compose_file])

    # Add command arguments
    cmd.extend(args)

    logger.info(f"Running docker-compose command: {' '.join(cmd)}")

    return subprocess.run(
        cmd,
        capture_output=capture_output,
        text=True,
        check=False,
    )


def _get_service_scale(config: DataSourcesConfig, service: str) -> int:
    """
    Get current scale (replica count) of a docker-compose service.

    Args:
        config: Data sources configuration
        service: Service name

    Returns:
        Current replica count
    """
    result = _run_docker_compose_command(
        config,
        ["ps", "-q", service],
        capture_output=True,
    )

    if result.returncode != 0:
        return 0

    # Count running containers
    container_ids = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
    return len(container_ids)


def scale_service(
    config: DataSourcesConfig,
    service: str,
    replicas: int,
) -> dict[str, Any]:
    """
    Scale a docker-compose service (adjust replica count).

    Args:
        config: Data sources configuration
        service: Service name
        replicas: Target replica count

    Returns:
        Operation result
    """
    dry_run = not config.execute_write_operations

    try:
        # Validate replicas
        if replicas < 0:
            return {
                "success": False,
                "service": service,
                "error": f"Invalid replica count: {replicas} (must be >= 0)",
                "dry_run": dry_run,
            }

        # Get current scale
        try:
            current_replicas = _get_service_scale(config, service)
        except Exception as e:
            return {
                "success": False,
                "service": service,
                "error": f"Failed to get current scale: {str(e)}",
                "dry_run": dry_run,
            }

        # Check if service exists
        if current_replicas == 0 and not dry_run:
            # Try to check if service is defined in compose file
            result = _run_docker_compose_command(
                config,
                ["config", "--services"],
                capture_output=True,
            )
            services = result.stdout.strip().split("\n")
            if service not in services:
                return {
                    "success": False,
                    "service": service,
                    "error": f"Service '{service}' not found in docker-compose.yml",
                    "available_services": services,
                    "dry_run": dry_run,
                }

        # Check if already at target scale
        if replicas == current_replicas:
            return {
                "success": True,
                "service": service,
                "message": f"Service already has {replicas} replicas (no change needed)",
                "current_replicas": current_replicas,
                "target_replicas": replicas,
                "dry_run": dry_run,
            }

        # Dry run mode
        if dry_run:
            return {
                "success": True,
                "service": service,
                "message": f"DRY RUN: Would scale service from {current_replicas} to {replicas} replicas",
                "current_replicas": current_replicas,
                "target_replicas": replicas,
                "dry_run": True,
                "note": "Use --execute flag to perform actual scaling",
            }

        # Execute scaling
        result = _run_docker_compose_command(
            config,
            ["up", "-d", "--scale", f"{service}={replicas}", "--no-recreate"],
            capture_output=True,
        )

        if result.returncode != 0:
            return {
                "success": False,
                "service": service,
                "error": f"docker-compose scale failed: {result.stderr}",
                "current_replicas": current_replicas,
                "target_replicas": replicas,
                "dry_run": False,
            }

        logger.info(f"Scaled service {service} from {current_replicas} to {replicas} replicas")

        return {
            "success": True,
            "service": service,
            "message": f"Successfully scaled service from {current_replicas} to {replicas} replicas",
            "current_replicas": current_replicas,
            "target_replicas": replicas,
            "dry_run": False,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Unexpected error during scale: {e}")
        return {
            "success": False,
            "service": service,
            "error": f"Unexpected error: {str(e)}",
            "dry_run": dry_run,
        }


def restart_service(
    config: DataSourcesConfig,
    service: str,
) -> dict[str, Any]:
    """
    Restart a docker-compose service.

    Args:
        config: Data sources configuration
        service: Service name

    Returns:
        Operation result
    """
    dry_run = not config.execute_write_operations

    try:
        # Get current scale
        try:
            current_replicas = _get_service_scale(config, service)
        except Exception as e:
            return {
                "success": False,
                "service": service,
                "error": f"Failed to get current scale: {str(e)}",
                "dry_run": dry_run,
            }

        # Check if service exists
        if current_replicas == 0 and not dry_run:
            # Try to check if service is defined in compose file
            result = _run_docker_compose_command(
                config,
                ["config", "--services"],
                capture_output=True,
            )
            services = result.stdout.strip().split("\n")
            if service not in services:
                return {
                    "success": False,
                    "service": service,
                    "error": f"Service '{service}' not found in docker-compose.yml",
                    "available_services": services,
                    "dry_run": dry_run,
                }

        # Dry run mode
        if dry_run:
            return {
                "success": True,
                "service": service,
                "message": f"DRY RUN: Would restart service ({current_replicas} containers)",
                "replicas": current_replicas,
                "dry_run": True,
                "note": "Use --execute flag to perform actual restart",
            }

        # Execute restart
        result = _run_docker_compose_command(
            config,
            ["restart", service],
            capture_output=True,
        )

        if result.returncode != 0:
            return {
                "success": False,
                "service": service,
                "error": f"docker-compose restart failed: {result.stderr}",
                "dry_run": False,
            }

        logger.info(f"Restarted service {service}")

        return {
            "success": True,
            "service": service,
            "message": f"Successfully restarted service ({current_replicas} containers)",
            "replicas": current_replicas,
            "restart_timestamp": datetime.now().isoformat(),
            "dry_run": False,
        }

    except Exception as e:
        logger.error(f"Unexpected error during restart: {e}")
        return {
            "success": False,
            "service": service,
            "error": f"Unexpected error: {str(e)}",
            "dry_run": dry_run,
        }


# ===== Tool Registration =====


def register_real_tools(
    registry: ToolRegistry, config: DataSourcesConfig
) -> None:
    """
    Register all real data source tools to the registry.

    Args:
        registry: Tool registry instance
        config: Data sources configuration
    """

    # Determine which log backend to use
    if config.elasticsearch_url:
        log_handler = lambda **kwargs: query_logs_elasticsearch(config, **kwargs)
        log_backend = "Elasticsearch"
    else:
        log_handler = lambda **kwargs: query_logs_loki(config, **kwargs)
        log_backend = "Loki"

    # query_metrics tool (Prometheus)
    registry.register(
        ToolSpec(
            name="query_metrics",
            description=f"Query metrics from Prometheus for a service (URL: {config.prometheus_url})",
            input_schema={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service name"},
                    "metric": {
                        "type": "string",
                        "description": "Metric name (cpu_percent, memory_percent, request_latency_p99, qps)",
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
            handler=lambda **kwargs: query_metrics_prometheus(config, **kwargs),
            tags=["metrics", "monitoring", "read-only", "prometheus"],
        )
    )

    # query_logs tool (Loki or Elasticsearch)
    registry.register(
        ToolSpec(
            name="query_logs",
            description=f"Query logs from {log_backend} for a service",
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
            handler=log_handler,
            tags=["logs", "monitoring", "read-only", log_backend.lower()],
        )
    )

    # query_topology tool (CMDB)
    registry.register(
        ToolSpec(
            name="query_topology",
            description=f"Query service topology from CMDB (URL: {config.cmdb_url or 'not configured'})",
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
            handler=lambda **kwargs: query_topology_cmdb(config, **kwargs),
            tags=["topology", "architecture", "read-only", "cmdb"],
        )
    )

    # get_change_history tool (Git + CD)
    registry.register(
        ToolSpec(
            name="get_change_history",
            description="Get change history from Git and CD systems",
            input_schema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name (optional filter)",
                    },
                    "change_type": {
                        "type": "string",
                        "description": "Change type (deployment, config_change, code_change, etc.)",
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
            handler=lambda **kwargs: get_change_history_real(config, **kwargs),
            tags=["change", "history", "audit", "read-only", "git", "cd"],
        )
    )

    # scale_service tool (docker-compose write operation)
    registry.register(
        ToolSpec(
            name="scale_service",
            description=f"Scale a docker-compose service (adjust replica count). {'DRY RUN MODE - use --execute to perform actual scaling' if not config.execute_write_operations else 'EXECUTE MODE - will perform actual scaling'}",
            input_schema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name (from docker-compose.yml)",
                    },
                    "replicas": {
                        "type": "integer",
                        "description": "Target replica count (must be >= 0)",
                    },
                },
                "required": ["service", "replicas"],
            },
            risk_level=RiskLevel.RISKY_WRITE,
            permission_required=PermissionLevel.OPERATOR,
            handler=lambda **kwargs: scale_service(config, **kwargs),
            tags=["docker-compose", "scale", "write", "high-risk"],
        )
    )

    # restart_service tool (docker-compose write operation)
    registry.register(
        ToolSpec(
            name="restart_service",
            description=f"Restart a docker-compose service. {'DRY RUN MODE - use --execute to perform actual restart' if not config.execute_write_operations else 'EXECUTE MODE - will perform actual restart'}",
            input_schema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name (from docker-compose.yml)",
                    },
                },
                "required": ["service"],
            },
            risk_level=RiskLevel.RISKY_WRITE,
            permission_required=PermissionLevel.OPERATOR,
            handler=lambda **kwargs: restart_service(config, **kwargs),
            tags=["docker-compose", "restart", "write", "high-risk"],
        )
    )
