"""
Investigation agent: gather evidence using tools.
证据收集代理：使用工具收集证据。
"""

import json
from typing import Any

from pydantic import BaseModel, Field

from sentinel.agents.base import BaseAgent
from sentinel.llm.base import LLMClient
from sentinel.tools.registry import ToolRegistry
from sentinel.types import Evidence, LLMMessage, PermissionLevel, Task


class InvestigationInput(BaseModel):
    """Input for investigation agent."""

    task: Task = Field(..., description="Task to investigate")
    caller_permission: PermissionLevel = Field(
        default=PermissionLevel.OPERATOR, description="Permission level for tool calls"
    )


class InvestigationOutput(BaseModel):
    """Output from investigation agent."""

    evidence: list[Evidence] = Field(default_factory=list, description="Collected evidence")
    key_findings: list[str] = Field(default_factory=list, description="Key findings summary")
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Overall confidence in findings"
    )
    next_steps: list[str] = Field(
        default_factory=list, description="Recommended next steps"
    )
    tool_calls_made: int = Field(default=0, description="Number of tool calls executed")


class InvestigationAgent(BaseAgent[InvestigationInput, InvestigationOutput]):
    """
    Investigation agent responsible for:
    - 调用只读工具收集证据
    - 分析指标、日志、拓扑、变化
    - 建立全面的证据基础
    - 形成假设
    """

    def __init__(self, llm_client: LLMClient, tool_registry: ToolRegistry):
        """Initialize investigation agent."""
        super().__init__(
            name="investigation-agent",
            llm_client=llm_client,
            tool_registry=tool_registry,
        )

    def run(self, input_data: InvestigationInput) -> InvestigationOutput:
        """
        调查一个任务，通过收集证据。

        Args:
            input_data: InvestigationInput with task and permission

        Returns:
            InvestigationOutput with evidence and findings
        """
        task = input_data.task
        caller_permission = input_data.caller_permission

        # Step 1: 确定要调用哪些工具基于任务
        tools_to_call = self._plan_investigation(task)

        # Step 2: 执行工具调用
        evidence_list: list[Evidence] = []
        tool_calls_made = 0

        for tool_call in tools_to_call:
            try:
                result = self.tool_registry.call(
                    tool_name=tool_call["tool_name"],
                    args=tool_call["args"],
                    caller_permission=caller_permission,
                    dry_run=False,
                )

                if result.success:
                    evidence = Evidence(
                        source=tool_call["tool_name"],
                        data=result.data,
                        confidence=0.9,
                        notes=tool_call.get("notes", ""),
                    )
                    evidence_list.append(evidence)
                    tool_calls_made += 1

            except Exception as e:
                # Log error but continue investigation
                evidence = Evidence(
                    source=tool_call["tool_name"],
                    data={"error": str(e)},
                    confidence=0.0,
                    notes=f"Tool call failed: {str(e)}",
                )
                evidence_list.append(evidence)

        # Step 3: Analyze evidence with LLM
        analysis = self._analyze_evidence(task, evidence_list)

        return InvestigationOutput(
            evidence=evidence_list,
            key_findings=analysis.get("key_findings", []),
            confidence=analysis.get("confidence", 0.5),
            next_steps=analysis.get("next_steps", []),
            tool_calls_made=tool_calls_made,
        )

    def _plan_investigation(self, task: Task) -> list[dict[str, Any]]:
        """
        计划要调用哪些工具基于任务。

        Args:
            task: Task to investigate

        Returns:
            List of tool calls to make
        """
        tools_to_call = []
        symptoms = task.symptoms
        context = task.context

        # 确定受影响的服务
        service = symptoms.get("service", "auth-service")  # Default for demo

        # 总是收集基本信息
        tools_to_call.append(
            {
                "tool_name": "query_topology",
                "args": {"service": service},
                "notes": "Get service topology and dependencies",
            }
        )

        tools_to_call.append(
            {
                "tool_name": "get_change_history",
                "args": {"service": service, "since_hours": 24},
                "notes": "Check recent changes (deployments, config)",
            }
        )

        # 如果症状提到特定的指标，查询它们
        if "cpu" in str(symptoms).lower() or "latency" in str(symptoms).lower():
            tools_to_call.append(
                {
                    "tool_name": "query_metrics",
                    "args": {"service": service, "metric": "cpu_percent", "aggregation": "max"},
                    "notes": "Check CPU metrics",
                }
            )
            tools_to_call.append(
                {
                    "tool_name": "query_metrics",
                    "args": {
                        "service": service,
                        "metric": "request_latency_p99",
                        "aggregation": "max",
                    },
                    "notes": "Check latency metrics",
                }
            )

        # Always check error logs
        tools_to_call.append(
            {
                "tool_name": "query_logs",
                "args": {"service": service, "level": "ERROR", "limit": 50},
                "notes": "Check error logs",
            }
        )

        return tools_to_call

    def _analyze_evidence(
        self, task: Task, evidence_list: list[Evidence]
    ) -> dict[str, Any]:
        """
        用LLM分析收集的证据。

        Args:
            task: Original task
            evidence_list: Collected evidence

        Returns:
            Analysis dict with key_findings, confidence, next_steps
        """
        # 构建系统提示词
        system_prompt = """You are an investigation analyst for datacenter operations.

Analyze the collected evidence and provide:
1. Key findings (list of important observations)
2. Confidence level (0.0-1.0)
3. Recommended next steps

Output valid JSON with fields: key_findings, confidence, next_steps.

Example output (for a latency spike investigation):
{
  "key_findings": [
    "request_latency_p99 spiked to 850ms in the last 15 minutes",
    "No recent deployments in the past 24 hours; config change 6 hours ago",
    "Error logs show increased timeout errors from downstream auth-service"
  ],
  "confidence": 0.75,
  "next_steps": [
    "Generate remediation plan (scale or tune timeouts)",
    "Verify downstream health and capacity"
  ]
}
"""

        evidence_summary = "\n\n".join(
            [
                f"Evidence from {e.source}:\n{json.dumps(e.data, indent=2)}\nNotes: {e.notes}"
                for e in evidence_list
            ]
        )

        user_message = f"""Task: {task.goal}

Symptoms:
{json.dumps(task.symptoms, indent=2)}

Evidence collected:
{evidence_summary}

Analyze this evidence and provide structured findings.
"""

        # 调用LLM
        messages = [LLMMessage(role="user", content=user_message)]
        response = self.llm_client.generate(messages, system_prompt=system_prompt)

        # 解析响应
        try:
            analysis = json.loads(response.content)
            return analysis
        except Exception:
            # Fallback: extract key findings from evidence
            key_findings = []
            for e in evidence_list:
                if e.confidence > 0.5 and e.notes:
                    key_findings.append(e.notes)

            return {
                "key_findings": key_findings[:5],
                "confidence": 0.6,
                "next_steps": ["Generate remediation plan based on findings"],
            }
