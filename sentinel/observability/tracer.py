"""
记录Trace，用于全局观测系统运行情况。

以JSONL格式记录所有事件，用于分析和调试。
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


class TraceSpan(BaseModel):
    """
    Trace span 表示一个工作单元。
    """

    span_id: str = Field(..., description="Unique span ID")
    parent_span_id: Optional[str] = Field(None, description="Parent span ID")

    component: str = Field(..., description="Component: orchestrator|agent|tool|policy")
    name: str = Field(..., description="Span name")

    start_time: datetime = Field(..., description="Start time")
    end_time: Optional[datetime] = Field(None, description="End time")

    status: str = Field(default="running", description="Status: running|success|failed|skipped")
    error: Optional[str] = Field(None, description="Error message if failed")

    # Input/output (truncated if too large)
    input_summary: Optional[str] = Field(None, description="Input summary")
    output_summary: Optional[str] = Field(None, description="Output summary")

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class TraceEvent(BaseModel):
    """
    Trace event (point-in-time observation).
    """

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Event ID")
    span_id: Optional[str] = Field(None, description="Associated span ID")

    timestamp: datetime = Field(default_factory=datetime.now, description="Event timestamp")
    component: str = Field(..., description="Component name")
    event_type: str = Field(..., description="Event type")

    message: str = Field(..., description="Event message")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Event metadata")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class TraceRecorder:
    """
    记录Trace和事件到JSONL文件。
    """

    def __init__(self, output_dir: Path):
        """
        Initialize trace recorder.

        Args:
            output_dir: Directory to write trace files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.trace_file = self.output_dir / "trace.jsonl"

        # 内存中存储当前运行的Trace和事件
        self._spans: dict[str, TraceSpan] = {}
        self._events: list[TraceEvent] = []

        # Metrics
        self._metrics: dict[str, Any] = {
            "total_spans": 0,
            "total_events": 0,
            "spans_by_component": {},
            "spans_by_status": {},
        }

    def start_span(
        self,
        component: str,
        name: str,
        parent_span_id: Optional[str] = None,
        input_summary: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        开始一个新的Trace span。

        Args:
            component: Component name
            name: Span name
            parent_span_id: Parent span ID (optional)
            input_summary: Input summary (optional)
            metadata: Additional metadata (optional)

        Returns:
            Span ID
        """
        span_id = str(uuid.uuid4())

        span = TraceSpan(
            span_id=span_id,
            parent_span_id=parent_span_id,
            component=component,
            name=name,
            start_time=datetime.now(),
            input_summary=self._truncate(input_summary, max_length=500),
            metadata=metadata or {},
        )

        self._spans[span_id] = span
        self._metrics["total_spans"] += 1

        # 更新组件指标
        self._metrics["spans_by_component"][component] = (
            self._metrics["spans_by_component"].get(component, 0) + 1
        )

        # 写入文件
        self._write_record({"type": "span_start", "span": span.model_dump()})

        return span_id

    def end_span(
        self,
        span_id: str,
        status: str = "success",
        error: Optional[str] = None,
        output_summary: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        结束一个Trace span。

        Args:
            span_id: Span ID
            status: Status (success|failed|skipped)
            error: Error message if failed
            output_summary: Output summary (optional)
            metadata: Additional metadata (optional)
        """
        span = self._spans.get(span_id)
        if span is None:
            # Span not found, 记录警告但不要失败
            self.record_event(
                component="tracer",
                event_type="warning",
                message=f"Attempted to end unknown span: {span_id}",
            )
            return

        # Update span
        span.end_time = datetime.now()
        span.status = status
        span.error = error
        span.output_summary = self._truncate(output_summary, max_length=500)

        if metadata:
            span.metadata.update(metadata)

        # 更新状态指标
        self._metrics["spans_by_status"][status] = (
            self._metrics["spans_by_status"].get(status, 0) + 1
        )

        # 写入文件
        self._write_record({"type": "span_end", "span": span.model_dump()})

    def record_event(
        self,
        component: str,
        event_type: str,
        message: str,
        span_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        记录一个Trace事件。

        Args:
            component: Component name
            event_type: Event type
            message: Event message
            span_id: Associated span ID (optional)
            metadata: Additional metadata (optional)

        Returns:
            Event ID
        """
        event = TraceEvent(
            span_id=span_id,
            component=component,
            event_type=event_type,
            message=message,
            metadata=metadata or {},
        )

        self._events.append(event)
        self._metrics["total_events"] += 1

        # Write to file
        self._write_record({"type": "event", "event": event.model_dump()})

        return event.event_id

    def get_metrics(self) -> dict[str, Any]:
        """Get aggregated metrics."""
        return self._metrics.copy()

    def get_spans(self) -> list[TraceSpan]:
        """Get all spans."""
        return list(self._spans.values())

    def get_events(self) -> list[TraceEvent]:
        """Get all events."""
        return self._events.copy()

    def _write_record(self, record: dict[str, Any]) -> None:
        """
        写入一条记录到JSONL文件。

        Args:
            record: Record to write
        """
        try:
            with open(self.trace_file, "a") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception as e:
            # 不要在Trace写入错误时失败
            print(f"Warning: Failed to write trace: {e}")

    def _truncate(self, text: Optional[str], max_length: int = 500) -> Optional[str]:
        """
        截断文本到最大长度。

        Args:
            text: Text to truncate
            max_length: Maximum length

        Returns:
            Truncated text
        """
        if text is None:
            return None

        if len(text) <= max_length:
            return text

        return text[:max_length] + "... (truncated)"

    def flush(self) -> None:
        """刷新任何挂起的写入（目前没有操作，立即写入）。"""
        pass
