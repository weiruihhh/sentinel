"""
验证模块，用于验证修复是否成功。
使用真实数据源查询指标和日志，判断修复是否成功。
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from sentinel.config import SentinelConfig
from sentinel.tools.registry import ToolRegistry
from sentinel.types import Task

logger = logging.getLogger(__name__)


@dataclass
class VerificationRule:
    """单个验证规则。"""

    metric: str  # 指标名称
    threshold: float  # 阈值
    operator: str  # "lt", "gt", "eq", "le", "ge" 代表小于，大于，等于，小于等于，大于等于
    description: str  


@dataclass
class VerificationResult:
    """验证结果。"""

    verified: bool  # 是否验证通过
    status: str  # "improved", "degraded", "unchanged" 代表改进，恶化，不变
    checks: list[dict[str, Any]]  # 验证检查结果列表，每个元素是一个字典，包含验证检查结果
    notes: str  # 备注


class Verifier:
    """
    验证器，用于检查修复是否成功。

    使用真实指标和日志验证结果。
    """

    # 默认验证规则，用于常见指标
    DEFAULT_RULES = {
        "cpu_percent": VerificationRule(
            metric="cpu_percent",
            threshold=80.0,
            operator="lt",
            description="CPU usage should be below 80%",
        ),
        "memory_percent": VerificationRule(
            metric="memory_percent",
            threshold=85.0,
            operator="lt",
            description="Memory usage should be below 85%",
        ),
        "request_latency_p99": VerificationRule(
            metric="request_latency_p99",
            threshold=200.0,
            operator="lt",
            description="P99 latency should be below 200ms",
        ),
    }

    def __init__(
        self,
        tool_registry: ToolRegistry,
        config: SentinelConfig,
        use_real_verification: bool = True,
    ):
        """
        初始化验证器。

        Args:
            tool_registry: 工具注册表，用于查询指标和日志
            config: Sentinel 配置
            use_real_verification: 如果为 False，使用模拟验证（M1 行为）
        """
        self.tool_registry = tool_registry
        self.config = config
        self.use_real_verification = use_real_verification

    def verify(
        self,
        task: Task,
        context: dict[str, Any],
    ) -> VerificationResult:
        """
        验证问题是否已解决。

        Args:
            task: 原始任务
            context: 执行上下文，包含状态

        Returns:
            VerificationResult 验证结果，包含验证状态
        """
        if not self.use_real_verification:
            # 使用模拟验证
            return self._mock_verification()

        # 从任务症状中提取服务名称
        service = task.symptoms.get("service", "")
        if not service:
            logger.warning("No service specified in task, cannot verify")
            # 如果没有服务名称，则无法验证
            return VerificationResult(
                verified=False,
                status="unknown",
                checks=[],
                notes="No service specified for verification",
            )

        # 根据任务症状确定要检查的指标
        metrics_to_check = self._determine_metrics_to_check(task)

        # 执行验证检查
        checks = []
        all_passed = True

        for metric_name in metrics_to_check:
            check_result = self._check_metric(service, metric_name)
            checks.append(check_result)
            if not check_result["passed"]:
                all_passed = False

        # 检查错误日志
        log_check = self._check_error_logs(service)
        checks.append(log_check)
        if not log_check["passed"]:
            all_passed = False

        # 确定总体状态
        if all_passed:
            status = "improved"
            verified = True
            notes = "All verification checks passed. Issue appears to be resolved."
        else:
            failed_checks = [c for c in checks if not c["passed"]]
            status = "degraded" if len(failed_checks) > len(checks) / 2 else "unchanged"
            verified = False
            notes = f"{len(failed_checks)} of {len(checks)} checks failed. Issue may not be fully resolved."

        return VerificationResult(
            verified=verified,
            status=status,
            checks=checks,
            notes=notes,
        )

    def _determine_metrics_to_check(self, task: Task) -> list[str]:
        """根据任务症状确定要检查的指标。"""
        metrics = []

        symptoms = task.symptoms
        metric_name = symptoms.get("metric", "")

        # 检查主要指标
        if metric_name in self.DEFAULT_RULES:
            metrics.append(metric_name)

        # 根据报警类型检查相关指标
        alert_name = symptoms.get("alert_name", "").lower()

        if "cpu" in alert_name or "cpu" in metric_name:
            metrics.append("cpu_percent")
        if "latency" in alert_name or "latency" in metric_name:
            metrics.append("request_latency_p99")
        if "memory" in alert_name or "memory" in metric_name:
            metrics.append("memory_percent")

        # 移除重复
        return list(set(metrics))

    def _check_metric(self, service: str, metric_name: str) -> dict[str, Any]:
        """
        检查特定指标是否超过阈值。

        Args:
            service: 服务名称
            metric_name: 指标名称

        Returns:
            Check result dict检查结果字典
        """
        rule = self.DEFAULT_RULES.get(metric_name)
        if not rule:
            return {
                "type": "metric",
                "metric": metric_name,
                "passed": True,
                "message": f"No verification rule defined for {metric_name}",
            }

        try:
            # 查询最近指标（最近 5 分钟）
            end_time = datetime.now().isoformat() + "Z"
            start_time = (datetime.now() - timedelta(minutes=5)).isoformat() + "Z"

            result = self.tool_registry.call(
                "query_metrics",
                {
                    "service": service,
                    "metric": metric_name,
                    "start_time": start_time,
                    "end_time": end_time,
                    "aggregation": "avg",
                },
            )

            # 提取平均值
            if "error" in result:
                return {
                    "type": "metric",
                    "metric": metric_name,
                    "passed": False,
                    "message": f"Failed to query {metric_name}: {result['error']}",
                    "current_value": None,
                    "threshold": rule.threshold,
                }

            agg_data = result.get("aggregation", {})
            current_value = agg_data.get("avg", 0)

            # 检查是否超过阈值
            passed = self._evaluate_threshold(
                current_value, rule.threshold, rule.operator
            )

            return {
                "type": "metric",
                "metric": metric_name,
                "passed": passed,
                "message": rule.description,
                "current_value": current_value,
                "threshold": rule.threshold,
                "operator": rule.operator,
            }

        except Exception as e:
            logger.error(f"Error checking metric {metric_name}: {e}")
            return {
                "type": "metric",
                "metric": metric_name,
                "passed": False,
                "message": f"Error checking {metric_name}: {str(e)}",
                "current_value": None,
                "threshold": rule.threshold,
            }

    def _check_error_logs(self, service: str) -> dict[str, Any]:
        """
        检查最近错误日志。

        Args:
            service: 服务名称

        Returns:
            Check result dict检查结果字典
        """
        try:
            # 查询最近错误日志（最近 5 分钟）
            since = (datetime.now() - timedelta(minutes=5)).isoformat() + "Z"

            result = self.tool_registry.call(
                "query_logs",
                {
                    "service": service,
                    "level": "ERROR",
                    "limit": 10,
                    "since": since,
                },
            )

            if "error" in result:
                return {
                    "type": "logs",
                    "passed": False,
                    "message": f"Failed to query logs: {result['error']}",
                    "error_count": None,
                }

            error_count = result.get("total_entries", 0)

            # 如果最近 5 分钟内错误数少于 5 个，则认为通过
            # (大约每分钟少于 1 个错误)
            passed = error_count < 5

            return {
                "type": "logs",
                "passed": passed,
                "message": f"Error log count: {error_count} in last 5 minutes",
                "error_count": error_count,
                "threshold": 5,
            }

        except Exception as e:
            logger.error(f"Error checking logs: {e}")
            return {
                "type": "logs",
                "passed": False,
                "message": f"Error checking logs: {str(e)}",
                "error_count": None,
            }

    def _evaluate_threshold(
        self, value: float, threshold: float, operator: str
    ) -> bool:
        """评估值是否超过阈值。"""
        if operator == "lt":
            return value < threshold
        elif operator == "gt":
            return value > threshold
        elif operator == "eq":
            return abs(value - threshold) < 0.01  # Approximate equality
        elif operator == "le":
            return value <= threshold
        elif operator == "ge":
            return value >= threshold
        else:
            logger.warning(f"Unknown operator: {operator}")
            return False

    def _mock_verification(self) -> VerificationResult:
        """模拟验证，用于兼容 M1 行为。"""
        return VerificationResult(
            verified=True,
            status="improved",
            checks=[
                {
                    "type": "mock",
                    "passed": True,
                    "message": "Mock verification (M1 mode)",
                }
            ],
            notes="Mock verification: symptoms appear to be resolved (M1 simulation)",
        )
