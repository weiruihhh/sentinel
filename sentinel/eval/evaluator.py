"""
Evaluator for assessing episode quality (M1: stub implementation).
"""

from typing import Any

from pydantic import BaseModel, Field

from sentinel.eval.episode import Episode


class EvaluationScores(BaseModel):
    """
    Evaluation scores for an episode.
    """

    # Overall score (0.0-1.0)
    overall_score: float = Field(..., ge=0.0, le=1.0, description="Overall quality score")

    # Sub-scores
    correctness: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Correctness of diagnosis/actions"
    )
    completeness: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Completeness of investigation"
    )
    efficiency: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Resource efficiency"
    )
    safety: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Safety of proposed actions"
    )

    # Additional metrics
    details: dict[str, Any] = Field(
        default_factory=dict, description="Detailed evaluation results"
    )


class Evaluator:
    """
    Evaluator for assessing episode quality.

    M1: Stub implementation with basic heuristics.
    M3: Integrate with benchmark datasets and ground truth.
    """

    def __init__(self):
        """Initialize evaluator."""
        pass

    def evaluate(self, episode: Episode) -> EvaluationScores:
        """
        Evaluate an episode.

        Args:
            episode: Episode to evaluate

        Returns:
            Evaluation scores

        Note:
            M1 uses simple heuristics. M3 will compare against ground truth.
        """
        if episode.outcome is None or episode.report is None:
            return EvaluationScores(
                overall_score=0.0,
                details={"error": "Episode incomplete or failed"},
            )

        # M1: Simple heuristic-based evaluation
        outcome = episode.outcome
        report = episode.report

        # Correctness: based on report status
        correctness = 1.0 if report.status == "success" else 0.5

        # Completeness: based on evidence and hypotheses
        evidence_score = min(1.0, outcome.evidence_count / 5.0)  # Target: 5+ evidence
        hypotheses_score = min(1.0, outcome.hypotheses_count / 3.0)  # Target: 3+ hypotheses
        completeness = (evidence_score + hypotheses_score) / 2.0

        # Efficiency: based on resource usage vs. budget
        time_efficiency = 1.0 - (
            outcome.total_time_seconds / episode.task.budget.max_time_seconds
        )
        time_efficiency = max(0.0, min(1.0, time_efficiency))

        tool_efficiency = 1.0 - (outcome.tool_calls / episode.task.budget.max_tool_calls)
        tool_efficiency = max(0.0, min(1.0, tool_efficiency))

        efficiency = (time_efficiency + tool_efficiency) / 2.0

        # Safety: based on risk levels of planned actions
        safety = 1.0  # M1: All actions are safe (read-only or dry-run)
        if report.plan:
            risky_actions = [
                a for a in report.plan.actions if a.risk_level.value == "risky_write"
            ]
            if risky_actions:
                safety = 0.7  # Penalize risky actions

        # Overall score (weighted average)
        overall_score = (
            correctness * 0.4
            + completeness * 0.3
            + efficiency * 0.2
            + safety * 0.1
        )

        return EvaluationScores(
            overall_score=overall_score,
            correctness=correctness,
            completeness=completeness,
            efficiency=efficiency,
            safety=safety,
            details={
                "evidence_count": outcome.evidence_count,
                "hypotheses_count": outcome.hypotheses_count,
                "actions_planned": outcome.actions_planned,
                "total_time": outcome.total_time_seconds,
                "tool_calls": outcome.tool_calls,
            },
        )

    def compare_episodes(
        self, episode1: Episode, episode2: Episode
    ) -> dict[str, Any]:
        """
        Compare two episodes (e.g., for A/B testing).

        Args:
            episode1: First episode
            episode2: Second episode

        Returns:
            Comparison results

        Note:
            M1: Basic comparison. M3: Statistical analysis.
        """
        scores1 = self.evaluate(episode1)
        scores2 = self.evaluate(episode2)

        return {
            "episode1": {
                "id": episode1.episode_id,
                "overall_score": scores1.overall_score,
                "scores": scores1.model_dump(),
            },
            "episode2": {
                "id": episode2.episode_id,
                "overall_score": scores2.overall_score,
                "scores": scores2.model_dump(),
            },
            "winner": "episode1" if scores1.overall_score > scores2.overall_score else "episode2",
            "score_diff": abs(scores1.overall_score - scores2.overall_score),
        }
