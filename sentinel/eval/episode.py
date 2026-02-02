"""
Episode definition for evaluation.

An episode captures a complete task execution for later replay and comparison.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from sentinel.types import Report, Task


class Outcome(BaseModel):
    """
    Outcome of an episode execution.
    """

    success: bool = Field(..., description="Whether episode succeeded")
    error: Optional[str] = Field(None, description="Error message if failed")

    # Metrics
    total_time_seconds: float = Field(..., description="Total execution time")
    tokens_used: int = Field(default=0, description="Total tokens used")
    tool_calls: int = Field(default=0, description="Total tool calls")

    # Quality metrics
    evidence_count: int = Field(default=0, description="Evidence collected")
    hypotheses_count: int = Field(default=0, description="Hypotheses generated")
    actions_planned: int = Field(default=0, description="Actions planned")
    actions_executed: int = Field(default=0, description="Actions executed")

    # Report quality
    report_status: str = Field(..., description="Report status: success|partial|failed")


class Episode(BaseModel):
    """
    Episode: complete record of a task execution.

    Can be used for:
    - Evaluation and benchmarking
    - Replay and debugging
    - A/B testing different strategies
    """

    episode_id: str = Field(..., description="Unique episode ID")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation time")

    # Input
    task: Task = Field(..., description="Input task")

    # Output
    report: Optional[Report] = Field(None, description="Generated report")
    outcome: Optional[Outcome] = Field(None, description="Execution outcome")

    # Trace
    trace_file: Optional[str] = Field(None, description="Path to trace file")

    # Metadata
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration used (LLM model, policies, etc.)",
    )
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump()

    @classmethod
    def from_execution(
        cls,
        task: Task,
        report: Report,
        trace_file: str,
        config: Optional[dict[str, Any]] = None,
    ) -> "Episode":
        """
        Create episode from execution results.

        Args:
            task: Input task
            report: Generated report
            trace_file: Path to trace file
            config: Configuration used

        Returns:
            Episode instance
        """
        # Build outcome from report metrics
        metrics = report.metrics
        outcome = Outcome(
            success=report.status == "success",
            error=report.errors[0] if report.errors else None,
            total_time_seconds=metrics.get("time_used", 0.0),
            tokens_used=metrics.get("tokens_used", 0),
            tool_calls=metrics.get("tool_calls_used", 0),
            evidence_count=metrics.get("evidence_count", 0),
            hypotheses_count=len(report.root_cause_hypotheses),
            actions_planned=metrics.get("actions_planned", 0),
            actions_executed=metrics.get("actions_executed", 0),
            report_status=report.status,
        )

        return cls(
            episode_id=task.task_id,
            task=task,
            report=report,
            outcome=outcome,
            trace_file=trace_file,
            config=config or {},
        )
