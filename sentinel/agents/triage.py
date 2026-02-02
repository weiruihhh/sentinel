"""
Triage agent: 任务分类和评估风险，并路由到适当的工作流。
"""

import json
from typing import Literal

from pydantic import BaseModel, Field

from sentinel.agents.base import BaseAgent
from sentinel.llm.base import LLMClient
from sentinel.tools.registry import ToolRegistry
from sentinel.types import LLMMessage, RiskLevel, Task


class TriageInput(BaseModel):
    """Input for triage agent."""

    task: Task = Field(..., description="Task to triage")


class TriageOutput(BaseModel):
    """Output from triage agent."""

    severity: Literal["low", "medium", "high", "critical"] = Field(
        ..., description="Severity level"
    )
    category: str = Field(..., description="Issue category (performance, availability, etc.)")
    risk_level: RiskLevel = Field(..., description="Risk level for operations")
    recommended_route: str = Field(
        ..., description="Recommended workflow route (e.g., investigate_and_plan)"
    )
    reasoning: str = Field(..., description="Reasoning for classification")
    estimated_investigation_time: int = Field(
        ..., description="Estimated investigation time in seconds"
    )
    priority_score: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Priority score (0.0-1.0)"
    )


class TriageAgent(BaseAgent[TriageInput, TriageOutput]):
    """
    Triage agent responsible for:
    - 分类：Classifying incoming tasks
    - 评估严重性和风险：Assessing severity and risk
    - 确定适当的工作流路由：Determining appropriate workflow route
    - 设置预算约束：Setting budget constraints
    """

    def __init__(self, llm_client: LLMClient, tool_registry: ToolRegistry):
        """Initialize triage agent."""
        super().__init__(name="triage-agent", llm_client=llm_client, tool_registry=tool_registry)

    def run(self, input_data: TriageInput) -> TriageOutput:
        """
        分类一个任务。

        Args:
            input_data: TriageInput with task

        Returns:
            TriageOutput with classification and routing
        """
        task = input_data.task

        # Build prompt for LLM
        system_prompt = self._build_system_prompt()
        user_message = self._build_user_message(task)

        # Call LLM
        messages = [LLMMessage(role="user", content=user_message)]
        response = self.llm_client.generate(messages, system_prompt=system_prompt)

        # Parse LLM response
        try:
            result_dict = json.loads(response.content)
            output = TriageOutput(**result_dict)

            # Update task with risk level
            task.risk_level = output.risk_level

            return output

        except Exception as e:
            # Fallback to conservative defaults
            return TriageOutput(
                severity="medium",
                category="unknown",
                risk_level=RiskLevel.READ_ONLY,
                recommended_route="investigate_and_plan",
                reasoning=f"Failed to parse LLM response: {str(e)}. Using conservative defaults.",
                estimated_investigation_time=180,
                priority_score=0.5,
            )

    def _build_system_prompt(self) -> str:
        """构建分类的系统的提示词。"""
        return """You are a datacenter operations triage agent.

Your responsibilities:
1. Analyze incoming tasks (alerts, tickets, questions)
2. Classify severity, category, and risk level
3. Determine the appropriate workflow route
4. Estimate investigation time

Classification guidelines:
- Severity: low (informational), medium (degraded service), high (outage), critical (multi-service outage)
- Category: performance, availability, resource, security, configuration, etc.
- Risk Level: READ_ONLY (investigation only), SAFE_WRITE (low-risk actions), RISKY_WRITE (high-risk actions)

Output valid JSON with fields: severity, category, risk_level, recommended_route, reasoning, estimated_investigation_time, priority_score (0.0-1.0).

Example output (for a latency spike alert):
{
  "severity": "high",
  "category": "performance",
  "risk_level": "READ_ONLY",
  "recommended_route": "investigate_and_plan",
  "reasoning": "Latency spike indicates potential service degradation; recommend investigation and planning before any write actions.",
  "estimated_investigation_time": 180,
  "priority_score": 0.8
}
"""

    def _build_user_message(self, task: Task) -> str:
        """Build user message for triage."""
        return f"""Triage the following task:

Task ID: {task.task_id}
Source: {task.source}
Goal: {task.goal}

Symptoms:
{json.dumps(task.symptoms, indent=2)}

Context:
{json.dumps(task.context, indent=2)}

Constraints:
{json.dumps(task.constraints, indent=2)}

Provide triage assessment in JSON format.
"""
