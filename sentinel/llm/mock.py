"""
Mock LLM implementation using rule-based / template-based generation.
"""

import json
import random
from typing import Optional

from sentinel.llm.base import LLMClient
from sentinel.types import LLMMessage, LLMResponse


class MockLLM(LLMClient):
    """
    Mock LLM for testing and demonstration.

    Uses simple pattern matching and templates to generate responses.
    Useful for M1 where we don't need real LLM integration.
    """

    def __init__(
        self,
        model: str = "mock-llm-v1",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        deterministic: bool = False,
    ):
        """
        Initialize Mock LLM.

        Args:
            model: Model identifier
            temperature: Temperature (affects randomness in mock)
            max_tokens: Max tokens (affects response length)
            deterministic: If True, always generate same output for same input
        """
        super().__init__(model, temperature, max_tokens)
        self.deterministic = deterministic

    def generate(
        self,
        messages: list[LLMMessage],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate mock response based on simple rules.

        Args:
            messages: Conversation messages
            system_prompt: System prompt
            **kwargs: Additional arguments (ignored in mock)

        Returns:
            LLMResponse with generated content
        """
        # Combine all message content for pattern matching
        full_context = "\n".join([msg.content for msg in messages])
        if system_prompt:
            full_context = f"{system_prompt}\n{full_context}"

        # Pattern-based response generation
        response_content = self._generate_based_on_context(full_context)

        # Simulate token usage (rough estimate)
        tokens_used = len(response_content.split()) * 2  # Rough approximation

        return LLMResponse(
            content=response_content,
            tokens_used=tokens_used,
            metadata={
                "model": self.model,
                "temperature": self.temperature,
                "mock": True,
            },
        )

    def _generate_based_on_context(self, context: str) -> str:
        """
        Generate response based on context patterns.

        Args:
            context: Full context string

        Returns:
            Generated response
        """
        context_lower = context.lower()

        # Triage Agent responses
        if "triage" in context_lower or "classify" in context_lower:
            return self._generate_triage_response(context)

        # Investigation Agent responses
        if "investigate" in context_lower or "evidence" in context_lower:
            return self._generate_investigation_response(context)

        # Planner Agent responses
        if "plan" in context_lower or "action" in context_lower:
            return self._generate_planner_response(context)

        # Default response
        return self._generate_default_response(context)

    def _generate_triage_response(self, context: str) -> str:
        """Generate triage agent response."""
        # Extract symptoms from context
        if "latency" in context.lower():
            severity = "high"
            category = "performance"
            risk = "READ_ONLY"
        elif "cpu" in context.lower():
            severity = "medium"
            category = "resource"
            risk = "READ_ONLY"
        elif "error" in context.lower():
            severity = "high"
            category = "availability"
            risk = "READ_ONLY"
        else:
            severity = "medium"
            category = "unknown"
            risk = "READ_ONLY"

        response = {
            "severity": severity,
            "category": category,
            "risk_level": risk,
            "recommended_route": "investigate_and_plan",
            "reasoning": f"Based on symptoms analysis, this appears to be a {category} issue with {severity} severity. "
            f"Recommend thorough investigation before any actions.",
            "estimated_investigation_time": 120,
        }

        return json.dumps(response, indent=2)

    def _generate_investigation_response(self, context: str) -> str:
        """Generate investigation agent response."""
        # Analyze what tools might have been called
        findings = []

        if "metrics" in context.lower() or "cpu" in context.lower():
            findings.append(
                "CPU utilization shows abnormal pattern: spike to 95% at 14:23, "
                "correlates with deployment at 14:20"
            )

        if "logs" in context.lower() or "error" in context.lower():
            findings.append(
                "Logs show repeated 'Connection timeout' errors starting at 14:23, "
                "rate ~50 errors/min"
            )

        if "topology" in context.lower():
            findings.append(
                "Service topology shows auth-service depends on redis-cache and postgres-db, "
                "both appear healthy"
            )

        if "change" in context.lower():
            findings.append(
                "Recent deployment detected: auth-service v2.3.1 deployed at 14:20, "
                "timeline matches symptom onset"
            )

        if not findings:
            findings.append("Investigation completed, awaiting further tool outputs for analysis")

        response = {
            "key_findings": findings,
            "confidence": 0.8 if len(findings) >= 3 else 0.5,
            "next_steps": [
                "Correlate deployment timing with symptom onset",
                "Check for code changes in v2.3.1",
                "Verify resource limits and scaling config",
            ],
        }

        return json.dumps(response, indent=2)

    def _generate_planner_response(self, context: str) -> str:
        """Generate planner agent response."""
        # Based on evidence, generate plan
        if "cpu" in context.lower() and "deployment" in context.lower():
            hypotheses = [
                "Recent deployment (v2.3.1) introduced CPU-intensive code path",
                "Possible inefficient database query in new code",
                "Resource limits may need adjustment",
            ]
            actions = [
                {
                    "action_type": "rollback",
                    "target": "auth-service",
                    "description": "Rollback to v2.3.0 (last known good version)",
                    "risk": "SAFE_WRITE",
                },
                {
                    "action_type": "scale",
                    "target": "auth-service",
                    "description": "Temporarily scale up replicas from 3 to 5",
                    "risk": "SAFE_WRITE",
                },
            ]
        elif "latency" in context.lower():
            hypotheses = [
                "Network latency between services",
                "Database query performance degradation",
                "Cache miss rate increased",
            ]
            actions = [
                {
                    "action_type": "investigate_query",
                    "target": "database",
                    "description": "Check slow query logs",
                    "risk": "READ_ONLY",
                },
                {
                    "action_type": "restart",
                    "target": "redis-cache",
                    "description": "Restart redis-cache to clear potential corruption",
                    "risk": "RISKY_WRITE",
                },
            ]
        else:
            hypotheses = ["Root cause unclear, needs more investigation"]
            actions = [
                {
                    "action_type": "monitor",
                    "target": "all",
                    "description": "Continue monitoring for pattern changes",
                    "risk": "READ_ONLY",
                }
            ]

        response = {
            "hypotheses": hypotheses,
            "recommended_actions": actions,
            "expected_effect": "Resolve symptom within 5-10 minutes" if actions else "N/A",
            "risks": [
                "Rollback may cause brief service disruption (~30s)",
                "Need to coordinate with on-call team",
            ]
            if any(a.get("risk") != "READ_ONLY" for a in actions)
            else ["Minimal risk - read-only operations"],
            "approval_required": any(
                a.get("risk") in ["RISKY_WRITE", "SAFE_WRITE"] for a in actions
            ),
        }

        return json.dumps(response, indent=2)

    def _generate_default_response(self, context: str) -> str:
        """Generate default response for unrecognized patterns."""
        return json.dumps(
            {
                "response": "Acknowledged. Processing context and generating appropriate response.",
                "context_length": len(context),
                "status": "ready",
            },
            indent=2,
        )
