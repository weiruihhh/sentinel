"""
Lightweight graph/state machine engine for orchestration.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field


class NodeStatus(str, Enum):
    """Node execution status."""

    PENDING = "pending" #等候执行
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class Node(BaseModel):
    """
    Node in execution graph.
    """

    name: str = Field(..., description="Node name (unique identifier)")
    handler: Optional[Callable] = Field(
        None, description="Handler function to execute", exclude=True
    )
    description: str = Field(default="", description="Node description")

    # Execution state
    status: NodeStatus = Field(default=NodeStatus.PENDING, description="Execution status")
    start_time: Optional[datetime] = Field(None, description="Start time")
    end_time: Optional[datetime] = Field(None, description="End time")
    error: Optional[str] = Field(None, description="Error message if failed")

    # Result storage
    result: Optional[Any] = Field(None, description="Node execution result")

    class Config:
        arbitrary_types_allowed = True


class StateTransition(BaseModel):
    """
    Transition condition between nodes.
    """

    from_node: str = Field(..., description="Source node name")
    to_node: str = Field(..., description="Target node name")
    condition: Optional[Callable] = Field(
        None, description="Condition function (returns bool)", exclude=True
    )
    description: str = Field(default="", description="Transition description")

    class Config:
        arbitrary_types_allowed = True


class Edge(BaseModel):
    """
    Edge in execution graph (alias for StateTransition).
    """

    from_node: str = Field(..., description="Source node name")
    to_node: str = Field(..., description="Target node name")
    weight: float = Field(default=1.0, description="Edge weight (for priority)")


class ExecutionContext(BaseModel):
    """
    Execution context shared across all nodes.
    """

    # Input
    task_id: str = Field(..., description="Task ID being executed")

    # Shared state
    state: dict[str, Any] = Field(
        default_factory=dict, description="Shared state across nodes"
    )

    # Execution metadata
    start_time: datetime = Field(default_factory=datetime.now, description="Execution start time")
    current_node: Optional[str] = Field(None, description="Currently executing node")

    # Results from each node
    node_results: dict[str, Any] = Field(
        default_factory=dict, description="Results from each node"
    )

    # Execution history
    execution_path: list[str] = Field(
        default_factory=list, description="Path of executed nodes"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    def get_node_result(self, node_name: str) -> Optional[Any]:
        """Get result from a specific node."""
        return self.node_results.get(node_name)

    def set_node_result(self, node_name: str, result: Any) -> None:
        """Set result for a node."""
        self.node_results[node_name] = result

    def add_to_path(self, node_name: str) -> None:
        """Add node to execution path."""
        self.execution_path.append(node_name)


class Graph:
    """
    Lightweight graph engine for orchestration.
    """

    def __init__(self):
        """Initialize graph."""
        self._nodes: dict[str, Node] = {}
        self._transitions: list[StateTransition] = []
        self._edges: dict[str, list[str]] = {}  # from_node -> [to_nodes]

    def add_node(
        self,
        name: str,
        handler: Callable,
        description: str = "",
    ) -> None:
        """
        给图增加函数节点

        Args:
            name: Node name (unique)
            handler: Handler function to execute
            description: Node description

        Raises:
            ValueError: If node already exists
        """
        if name in self._nodes:
            raise ValueError(f"Node '{name}' already exists")

        node = Node(name=name, handler=handler, description=description)
        self._nodes[name] = node

    def add_edge(
        self,
        from_node: str,
        to_node: str,
        condition: Optional[Callable[[ExecutionContext], bool]] = None,
    ) -> None:
        """
        Add an edge (transition) between nodes.

        Args:
            from_node: Source node name
            to_node: Target node name
            condition: Optional condition function (returns bool)

        Raises:
            ValueError: If nodes don't exist
        """
        if from_node not in self._nodes:
            raise ValueError(f"Node '{from_node}' does not exist")
        if to_node not in self._nodes:
            raise ValueError(f"Node '{to_node}' does not exist")

        # Add to edge list
        if from_node not in self._edges:
            self._edges[from_node] = []
        self._edges[from_node].append(to_node)

        # Add transition
        transition = StateTransition(
            from_node=from_node,
            to_node=to_node,
            condition=condition,
        )
        self._transitions.append(transition)

    def get_node(self, name: str) -> Optional[Node]:
        """Get node by name."""
        return self._nodes.get(name)

    def get_next_nodes(
        self, current_node: str, context: ExecutionContext
    ) -> list[str]:
        """
        Get next nodes to execute based on current node and context.

        Args:
            current_node: Current node name
            context: Execution context

        Returns:
            List of next node names to execute
        """
        next_nodes = []

        for transition in self._transitions:
            if transition.from_node == current_node:
                # Check condition if present
                if transition.condition is None or transition.condition(context):
                    next_nodes.append(transition.to_node)

        return next_nodes

    def execute_node(
        self, node_name: str, context: ExecutionContext
    ) -> tuple[bool, Any, Optional[str]]:
        """
        Execute a single node.

        Args:
            node_name: Node to execute
            context: Execution context

        Returns:
            Tuple of (success, result, error)
        """
        node = self._nodes.get(node_name)
        if node is None:
            return False, None, f"Node '{node_name}' not found"

        # Update node status
        node.status = NodeStatus.RUNNING
        node.start_time = datetime.now()
        context.current_node = node_name

        try:
            # Execute handler
            if node.handler is None:
                raise ValueError(f"Node '{node_name}' has no handler")

            result = node.handler(context)

            # Update node status
            node.status = NodeStatus.SUCCESS
            node.end_time = datetime.now()
            node.result = result

            # Store result in context
            context.set_node_result(node_name, result)
            context.add_to_path(node_name)

            return True, result, None

        except Exception as e:
            # Update node status
            node.status = NodeStatus.FAILED
            node.end_time = datetime.now()
            node.error = str(e)

            return False, None, str(e)

    def get_all_nodes(self) -> list[Node]:
        """Get all nodes."""
        return list(self._nodes.values())

    def get_edges(self) -> dict[str, list[str]]:
        """Get all edges."""
        return self._edges.copy()
