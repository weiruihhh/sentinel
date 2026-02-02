"""
Tool registry with permission control and risk management.
"""

from datetime import datetime
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from sentinel.types import PermissionLevel, RiskLevel, ToolResult


class ToolSpec(BaseModel):
    """
    Tool specification including schema, risk level, and permission requirements.
    """

    name: str = Field(..., description="Tool name (unique identifier)")
    description: str = Field(..., description="Tool description")

    # Schema
    input_schema: dict[str, Any] = Field(
        default_factory=dict, description="JSON schema for input validation"
    )
    output_schema: dict[str, Any] = Field(
        default_factory=dict, description="JSON schema for output (optional)"
    )

    # Risk and permission
    risk_level: RiskLevel = Field(..., description="Risk level of this tool")
    permission_required: PermissionLevel = Field(
        ..., description="Minimum permission level required"
    )

    # Handler
    handler: Optional[Callable] = Field(
        None, description="Tool handler function (not serialized)", exclude=True
    )

    # Metadata
    tags: list[str] = Field(default_factory=list, description="Tool tags for categorization")
    version: str = Field(default="1.0.0", description="Tool version")

    class Config:
        arbitrary_types_allowed = True


class AuditRecord(BaseModel):
    """Audit record for tool invocation."""

    timestamp: datetime = Field(default_factory=datetime.now)
    tool_name: str
    caller_permission: PermissionLevel
    args: dict[str, Any]
    risk_level: RiskLevel
    dry_run: bool
    success: bool
    error: Optional[str] = None
    duration_ms: float = 0.0

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ToolRegistry:
    """
    Central registry for all tools with permission and risk management.
    """

    def __init__(self):
        """Initialize tool registry."""
        self._tools: dict[str, ToolSpec] = {}
        self._audit_log: list[AuditRecord] = []

    def register(self, spec: ToolSpec) -> None:
        """
        Register a tool.

        Args:
            spec: Tool specification

        Raises:
            ValueError: If tool name already registered
        """
        if spec.name in self._tools:
            raise ValueError(f"Tool '{spec.name}' already registered")

        if spec.handler is None:
            raise ValueError(f"Tool '{spec.name}' must have a handler function")

        self._tools[spec.name] = spec

    def get_tool(self, name: str) -> Optional[ToolSpec]:
        """
        Get tool specification by name.

        Args:
            name: Tool name

        Returns:
            ToolSpec if found, None otherwise
        """
        return self._tools.get(name)

    def list_tools(
        self,
        risk_level: Optional[RiskLevel] = None,
        permission_level: Optional[PermissionLevel] = None,
    ) -> list[ToolSpec]:
        """
        List tools, optionally filtered by risk/permission level.

        Args:
            risk_level: Filter by risk level
            permission_level: Filter by permission level

        Returns:
            List of matching tools
        """
        tools = list(self._tools.values())

        if risk_level:
            tools = [t for t in tools if t.risk_level == risk_level]

        if permission_level:
            tools = [
                t
                for t in tools
                if self._permission_level_value(t.permission_required)
                <= self._permission_level_value(permission_level)
            ]

        return tools

    def call(
        self,
        tool_name: str,
        args: dict[str, Any],
        caller_permission: PermissionLevel,
        dry_run: bool = False,
    ) -> ToolResult:
        """
        Call a tool with permission and schema validation.

        Args:
            tool_name: Tool name
            args: Tool arguments
            caller_permission: Caller's permission level
            dry_run: Whether to run in dry-run mode (no actual changes)

        Returns:
            ToolResult with execution result

        Raises:
            ValueError: If tool not found or validation fails
            PermissionError: If caller lacks permission
        """
        start_time = datetime.now()
        tool = self.get_tool(tool_name)

        # Check tool exists
        if tool is None:
            error_msg = f"Tool '{tool_name}' not found"
            self._record_audit(
                tool_name=tool_name,
                caller_permission=caller_permission,
                args=args,
                risk_level=RiskLevel.READ_ONLY,
                dry_run=dry_run,
                success=False,
                error=error_msg,
                duration_ms=0.0,
            )
            return ToolResult(success=False, error=error_msg)

        # Check permission
        if not self._check_permission(caller_permission, tool.permission_required):
            error_msg = (
                f"Permission denied: '{tool_name}' requires {tool.permission_required}, "
                f"caller has {caller_permission}"
            )
            self._record_audit(
                tool_name=tool_name,
                caller_permission=caller_permission,
                args=args,
                risk_level=tool.risk_level,
                dry_run=dry_run,
                success=False,
                error=error_msg,
                duration_ms=0.0,
            )
            return ToolResult(success=False, error=error_msg)

        # Validate input schema (basic validation)
        # In production, use jsonschema library for full validation
        required_fields = tool.input_schema.get("required", [])
        missing_fields = [f for f in required_fields if f not in args]
        if missing_fields:
            error_msg = f"Missing required fields: {missing_fields}"
            self._record_audit(
                tool_name=tool_name,
                caller_permission=caller_permission,
                args=args,
                risk_level=tool.risk_level,
                dry_run=dry_run,
                success=False,
                error=error_msg,
                duration_ms=0.0,
            )
            return ToolResult(success=False, error=error_msg)

        # Execute tool
        try:
            if dry_run and tool.risk_level != RiskLevel.READ_ONLY:
                # Dry-run mode: don't actually execute writes
                result_data = {
                    "dry_run": True,
                    "message": f"Would execute {tool_name} with args: {args}",
                }
                result = ToolResult(success=True, data=result_data)
            else:
                # Actually execute
                result_data = tool.handler(**args)
                result = ToolResult(success=True, data=result_data)

        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}"
            result = ToolResult(success=False, error=error_msg)

        # Calculate duration
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Record audit
        self._record_audit(
            tool_name=tool_name,
            caller_permission=caller_permission,
            args=args,
            risk_level=tool.risk_level,
            dry_run=dry_run,
            success=result.success,
            error=result.error,
            duration_ms=duration_ms,
        )

        # Add metadata to result
        result.metadata.update(
            {
                "tool_name": tool_name,
                "risk_level": tool.risk_level.value,
                "duration_ms": duration_ms,
                "dry_run": dry_run,
            }
        )

        return result

    def get_audit_log(self) -> list[AuditRecord]:
        """Get full audit log."""
        return self._audit_log.copy()

    def _check_permission(
        self, caller: PermissionLevel, required: PermissionLevel
    ) -> bool:
        """
        Check if caller has sufficient permission.

        Args:
            caller: Caller's permission level
            required: Required permission level

        Returns:
            True if caller has sufficient permission
        """
        return self._permission_level_value(caller) >= self._permission_level_value(
            required
        )

    @staticmethod
    def _permission_level_value(level: PermissionLevel) -> int:
        """Convert permission level to numeric value for comparison."""
        mapping = {
            PermissionLevel.GUEST: 1,
            PermissionLevel.OPERATOR: 2,
            PermissionLevel.ADMIN: 3,
        }
        return mapping[level]

    def _record_audit(
        self,
        tool_name: str,
        caller_permission: PermissionLevel,
        args: dict[str, Any],
        risk_level: RiskLevel,
        dry_run: bool,
        success: bool,
        error: Optional[str],
        duration_ms: float,
    ) -> None:
        """Record audit entry."""
        record = AuditRecord(
            tool_name=tool_name,
            caller_permission=caller_permission,
            args=args,
            risk_level=risk_level,
            dry_run=dry_run,
            success=success,
            error=error,
            duration_ms=duration_ms,
        )
        self._audit_log.append(record)
