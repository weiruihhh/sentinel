"""
Planner agent: generate execution plans based on evidence.
"""

import json
from typing import Any

from pydantic import BaseModel, Field

from sentinel.agents.base import BaseAgent
from sentinel.llm.base import LLMClient
from sentinel.tools.registry import ToolRegistry
from sentinel.types import Action, Evidence, LLMMessage, Plan, RiskLevel, Task


class PlannerInput(BaseModel):
    """Input for planner agent."""

    task: Task = Field(..., description="Task to plan for")
    evidence: list[Evidence] = Field(
        default_factory=list, description="Evidence from investigation"
    )


class PlannerOutput(BaseModel):
    """Output from planner agent."""

    plan: Plan = Field(..., description="Generated execution plan")
    reasoning: str = Field(..., description="Reasoning behind the plan")


class PlannerAgent(BaseAgent[PlannerInput, PlannerOutput]):
    """
    Planner agent responsible for:
    - 分析证据形成假设
    - 生成 remediation actions修复操作
    - 评估风险和创建回滚计划
    - 确定批准要求
    """

    def __init__(self, llm_client: LLMClient, tool_registry: ToolRegistry):
        """Initialize planner agent."""
        super().__init__(
            name="planner-agent",
            llm_client=llm_client,
            tool_registry=tool_registry,
        )

    def run(self, input_data: PlannerInput) -> PlannerOutput:
        """
        基于证据生成执行计划。

        Args:
            input_data: PlannerInput with task and evidence

        Returns:
            PlannerOutput with plan and reasoning
        """
        task = input_data.task
        evidence = input_data.evidence

        # Step 1: 调用LLM生成计划
        plan_dict = self._generate_plan_with_llm(task, evidence)

        # Step 2: 解析和结构化计划
        plan = self._parse_plan(plan_dict)

        # Step 3: 添加回滚计划 (M1: 占位符)
        plan.rollback_plan = self._generate_rollback_plan(plan)

        reasoning = plan_dict.get(
            "reasoning",
            "Plan generated based on evidence analysis and operational best practices.",
        )

        return PlannerOutput(plan=plan, reasoning=reasoning)

    def _generate_plan_with_llm(
        self, task: Task, evidence: list[Evidence]
    ) -> dict[str, Any]:
        """
        使用LLM生成计划。

        Args:
            task: Task to plan for
            evidence: Evidence from investigation

        Returns:
            Plan dict from LLM
        """
        # 构建系统提示词
        system_prompt = """You are an operations planning agent for datacenter infrastructure.

Based on investigation evidence, generate a remediation plan that includes:
1. Hypotheses about the root cause
2. Recommended actions (with risk levels)
3. Expected effect of the plan
4. Identified risks
5. Whether approval is required

For M1, focus on READ_ONLY or SAFE_WRITE actions. Avoid RISKY_WRITE unless critical.

Output valid JSON with fields:
- hypotheses: list[str]
- recommended_actions: list[{action_type, target, description, risk}]
- expected_effect: str
- risks: list[str]
- approval_required: bool

Example output (for a latency spike remediation):
{
  "hypotheses": [
    "Downstream auth-service overload or timeout causing P99 spike",
    "Recent config change may have reduced connection pool or timeouts"
  ],
  "recommended_actions": [
    {
      "action_type": "query_metrics",
      "target": "auth-service",
      "description": "Verify current latency and error rate before any change",
      "risk": "READ_ONLY"
    },
    {
      "action_type": "scale_replicas",
      "target": "auth-service",
      "description": "Increase replicas if capacity is the cause",
      "risk": "SAFE_WRITE"
    }
  ],
  "expected_effect": "P99 latency reduced to baseline; fewer timeout errors.",
  "risks": ["Scaling may not address root cause if it is downstream or config"],
  "approval_required": true
}
"""

        evidence_summary = "\n\n".join(
            [
                f"Evidence from {e.source} (confidence: {e.confidence}):\n{json.dumps(e.data, indent=2)}"
                for e in evidence
            ]
        )

        user_message = f"""Task: {task.goal}

Symptoms:
{json.dumps(task.symptoms, indent=2)}

Constraints:
{json.dumps(task.constraints, indent=2)}

Investigation Evidence:
{evidence_summary}

Generate a remediation plan.
"""

        # Call LLM
        messages = [LLMMessage(role="user", content=user_message)]
        response = self.llm_client.generate(messages, system_prompt=system_prompt)

        # Parse response
        try:
            plan_dict = json.loads(response.content)
            return plan_dict
        except Exception:
            # Fallback plan
            return {
                "hypotheses": ["Unable to determine root cause, needs manual investigation"],
                "recommended_actions": [
                    {
                        "action_type": "monitor",
                        "target": "all",
                        "description": "Continue monitoring for pattern changes",
                        "risk": "READ_ONLY",
                    }
                ],
                "expected_effect": "N/A",
                "risks": ["Insufficient evidence for automated action"],
                "approval_required": False,
            }

    def _parse_plan(self, plan_dict: dict[str, Any]) -> Plan:
        """
        Parse plan dict into Plan object.

        Args:
            plan_dict: Plan dictionary from LLM

        Returns:
            Plan object
        """
        # Parse hypotheses
        hypotheses = plan_dict.get("hypotheses", [])

        # Parse actions
        actions_data = plan_dict.get("recommended_actions", [])
        actions = []
        for action_data in actions_data:
            # Map risk string to RiskLevel enum
            risk_str = action_data.get("risk", "READ_ONLY").upper()
            if "RISKY" in risk_str:
                risk_level = RiskLevel.RISKY_WRITE
            elif "SAFE" in risk_str or "WRITE" in risk_str:
                risk_level = RiskLevel.SAFE_WRITE
            else:
                risk_level = RiskLevel.READ_ONLY

            action = Action(
                tool_name=action_data.get("action_type", "unknown"),
                args={
                    "target": action_data.get("target", ""),
                    "description": action_data.get("description", ""),
                },
                risk_level=risk_level,
                requires_approval=risk_level != RiskLevel.READ_ONLY,
                dry_run=True,  # M1: all actions are dry-run
            )
            actions.append(action)

        # Parse other fields
        expected_effect = plan_dict.get("expected_effect", "")
        risks = plan_dict.get("risks", [])
        approval_required = plan_dict.get("approval_required", False)

        # Determine confidence based on evidence quality
        confidence = 0.7 if len(hypotheses) > 0 else 0.3

        plan = Plan(
            hypotheses=hypotheses,
            actions=actions,
            expected_effect=expected_effect,
            risks=risks,
            rollback_plan=[],  # Will be filled separately
            approval_required=approval_required,
            confidence=confidence,
            estimated_duration_seconds=len(actions) * 30,  # Rough estimate
        )

        return plan

    def _generate_rollback_plan(self, plan: Plan) -> list[Action]:
        """
        Generate rollback plan (M1: placeholder).

        Args:
            plan: Forward plan

        Returns:
            List of rollback actions
        """
        # M1: Simple placeholder
        # M2: Implement proper rollback logic
        rollback_actions = []

        for action in plan.actions:
            if action.risk_level == RiskLevel.RISKY_WRITE:
                rollback_action = Action(
                    tool_name=f"rollback_{action.tool_name}",
                    args={"original_action": action.tool_name},
                    risk_level=RiskLevel.RISKY_WRITE,
                    requires_approval=True,
                    dry_run=True,
                )
                rollback_actions.append(rollback_action)

        return rollback_actions
