"""
Policies for orchestration (budget, retry, approval).
"""

from typing import Optional

from pydantic import BaseModel, Field

from sentinel.types import Budget, Plan, RiskLevel


class BudgetPolicy(BaseModel):
    """
    预算策略用于限制资源消耗。
    """

    max_tokens: int = Field(default=100000, description="Maximum LLM tokens")
    max_time_seconds: int = Field(default=300, description="Maximum execution time")
    max_tool_calls: int = Field(default=50, description="Maximum tool calls")

    def create_budget(self) -> Budget:
        """Create a budget instance from this policy."""
        return Budget(
            max_tokens=self.max_tokens,
            max_time_seconds=self.max_time_seconds,
            max_tool_calls=self.max_tool_calls,
        )

    def is_budget_exceeded(self, budget: Budget) -> bool:
        """Check if budget is exceeded."""
        return budget.is_exceeded()

    def get_remaining_budget(self, budget: Budget) -> dict[str, int]:
        """Get remaining budget."""
        return {
            "tokens": max(0, budget.max_tokens - budget.tokens_used),
            "time_seconds": max(0, int(budget.max_time_seconds - budget.time_used)),
            "tool_calls": max(0, budget.max_tool_calls - budget.tool_calls_used),
        }


class RetryPolicy(BaseModel):
    """
    重试策略用于失败的操作。
    """

    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay_seconds: float = Field(default=1.0, description="Delay between retries")
    backoff_multiplier: float = Field(
        default=2.0, description="Backoff multiplier for exponential backoff"
    )

    def should_retry(self, attempt: int) -> bool:
        """Check if should retry based on attempt count."""
        return attempt < self.max_retries

    def get_retry_delay(self, attempt: int) -> float:
        """Get retry delay for given attempt (exponential backoff)."""
        return self.retry_delay_seconds * (self.backoff_multiplier ** attempt)


class ApprovalPolicy(BaseModel):
    """
    Approval policy for action execution.
    """

    auto_approve_read_only: bool = Field(
        default=True, description="Auto-approve read-only actions"
    )
    auto_approve_safe_write: bool = Field(
        default=False, description="Auto-approve safe write actions"
    )
    require_approval_for_risky: bool = Field(
        default=True, description="Require approval for risky actions"
    )

    def requires_approval(self, plan: Plan) -> bool:
        """
        检查计划是否需要批准。

        Args:
            plan: Execution plan

        Returns:
            True if approval is required
        """
        if plan.approval_required:
            return True

        # Check actions
        for action in plan.actions:
            if action.risk_level == RiskLevel.RISKY_WRITE:
                if self.require_approval_for_risky:
                    return True
            elif action.risk_level == RiskLevel.SAFE_WRITE:
                if not self.auto_approve_safe_write:
                    return True
            elif action.risk_level == RiskLevel.READ_ONLY:
                if not self.auto_approve_read_only:
                    return True

        return False

    def approve_plan(self, plan: Plan) -> tuple[bool, Optional[str]]:
        """
        赞成或者拒绝计划 (M1: 根据策略自动批准计划)
        M2: 计划集成人类批准工作流

        Args:
            plan: Execution plan

        Returns:
            Tuple of (approved, reason)
        """
        if not self.requires_approval(plan):
            return True, "Auto-approved by policy"

        # M1: Auto-approve all plans (in M2, integrate with human approval workflow)
        # 对于高风险操作，通常需要人工批准
        risky_actions = [
            a for a in plan.actions if a.risk_level == RiskLevel.RISKY_WRITE
        ]

        if risky_actions and self.require_approval_for_risky:
            # M1: 自动批准并发出警告
            return (
                True,
                f"Auto-approved (M1 mode) - {len(risky_actions)} risky actions require review in M2",
            )

        return True, "Approved by policy"
