#!/usr/bin/env python3
"""
小例子：编排层数据结构用法演示。

演示 Node、Edge、ExecutionContext、Graph 的用法，
不依赖 LLM/Agent，纯编排层 API。
"""

import sys
from pathlib import Path

# 保证能 import sentinel
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentinel.orchestration.graph import (
    ExecutionContext,
    Graph,
    NodeStatus,
)


def main():
    # 1. 建图
    graph = Graph()

    # 2. 定义节点 handler：签名 (ExecutionContext) -> 任意结果
    def node_start(ctx: ExecutionContext):
        # 从共享 state 读输入
        task_id = ctx.task_id
        ctx.state["message"] = f"Started task {task_id}"
        return {"step": "start", "value": 1}

    def node_mid(ctx: ExecutionContext):
        # 读上一节点结果
        start_result = ctx.get_node_result("start")
        prev_value = start_result["value"] if start_result else 0
        ctx.state["accum"] = prev_value + 10
        return {"step": "mid", "value": prev_value + 10}

    def node_end(ctx: ExecutionContext):
        mid_result = ctx.get_node_result("mid")
        value = mid_result["value"] if mid_result else 0
        msg = ctx.state.get("message", "")
        return {"step": "end", "final": value, "message": msg}

    # 3. 添加节点（name, handler, description）
    graph.add_node("start", node_start, "第一步")
    graph.add_node("mid", node_mid, "第二步")
    graph.add_node("end", node_end, "第三步")

    # 4. 添加边：线性 start -> mid -> end
    graph.add_edge("start", "mid")
    graph.add_edge("mid", "end")

    # 5. 创建执行上下文（task_id + 初始 state）
    context = ExecutionContext(
        task_id="demo-task-001",
        state={"input": "hello"},
    )

    # 6. 按图执行
    current = "start"
    while current:
        success, result, error = graph.execute_node(current, context)
        if not success:
            print(f"Node '{current}' failed: {error}")
            break
        print(f"  [{current}] status={graph.get_node(current).status.value} result={result}")

        next_nodes = graph.get_next_nodes(current, context)
        current = next_nodes[0] if next_nodes else None

    # 7. 看最终结果和上下文
    print("\n--- ExecutionContext 最终状态 ---")
    print("  task_id:", context.task_id)
    print("  state:", context.state)
    print("  node_results:", context.node_results)
    print("  execution_path:", context.execution_path)

    # 8. 从 context 取某个节点的结果
    report = context.get_node_result("end")
    print("\n--- 最终输出 (end 节点结果) ---")
    print("  ", report)

    # 9. 进阶：带条件的边（可选演示）
    demo_conditional_edge()


def demo_conditional_edge():
    """演示 StateTransition.condition：根据 context 决定走哪条边。"""
    print("\n\n=== 进阶：带条件的边 ===\n")

    graph = Graph()

    def node_a(ctx: ExecutionContext):
        ctx.state["score"] = 5
        return "A"

    def node_b(ctx: ExecutionContext):
        return "B"

    def node_c(ctx: ExecutionContext):
        return "C"

    graph.add_node("a", node_a, "分支点")
    graph.add_node("b", node_b, "高分路径")
    graph.add_node("c", node_c, "低分路径")

    # 条件：score >= 5 走 b，否则走 c
    graph.add_edge("a", "b", condition=lambda ctx: ctx.state.get("score", 0) >= 5)
    graph.add_edge("a", "c", condition=lambda ctx: ctx.state.get("score", 0) < 5)

    ctx = ExecutionContext(task_id="cond-demo", state={})
    graph.execute_node("a", ctx)
    next_nodes = graph.get_next_nodes("a", ctx)
    chosen = next_nodes[0] if next_nodes else None
    print(f"  a 执行后 score={ctx.state['score']} -> 下一节点: {chosen}")

    if chosen:
        graph.execute_node(chosen, ctx)
        print(f"  执行 {chosen} 结果: {ctx.get_node_result(chosen)}")


if __name__ == "__main__":
    main()
