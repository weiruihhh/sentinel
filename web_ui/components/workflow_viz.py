"""
Workflow visualization component for Sentinel Web UI.
Displays the multi-agent workflow as an interactive state machine.
"""

import streamlit as st
from typing import List, Dict


def render_workflow(trace_data: List[Dict]):
    """
    Render workflow visualization from trace data.

    Args:
        trace_data: List of span events from trace.jsonl
    """
    st.markdown("## 🔄 诊断工作流")

    # Define workflow stages
    stages = [
        {"name": "DETECT", "icon": "🔍", "label": "检测"},
        {"name": "TRIAGE", "icon": "🏷️", "label": "分类"},
        {"name": "INVESTIGATE", "icon": "🔬", "label": "调查"},
        {"name": "PLAN", "icon": "📋", "label": "规划"},
        {"name": "APPROVE", "icon": "✅", "label": "审批"},
        {"name": "EXECUTE", "icon": "⚡", "label": "执行"},
        {"name": "VERIFY", "icon": "🔎", "label": "验证"},
        {"name": "REPORT", "icon": "📄", "label": "报告"},
    ]

    # Find spans for each stage
    stage_spans = {}
    for stage in stages:
        stage_name = stage["name"].lower()
        matching_spans = [s for s in trace_data if s.get('name', '').lower() == stage_name]
        if matching_spans:
            stage_spans[stage["name"]] = matching_spans[0]

    # Render workflow as columns
    cols = st.columns(len(stages))

    for i, stage in enumerate(stages):
        with cols[i]:
            span = stage_spans.get(stage["name"])

            if span:
                status = span.get('status', 'unknown')
                duration = span.get('duration', 0)

                # Status styling
                if status == 'success':
                    st.markdown(f"""
                    <div style="text-align: center; padding: 1rem; background: linear-gradient(135deg, rgba(149, 225, 211, 0.2), rgba(149, 225, 211, 0.1)); border-radius: 10px; border: 2px solid #95E1D3;">
                        <div style="font-size: 2rem;">{stage['icon']}</div>
                        <div style="font-weight: 600; margin-top: 0.5rem;">{stage['label']}</div>
                        <div style="color: #95E1D3; font-size: 0.85rem; margin-top: 0.25rem;">✓ {duration:.1f}s</div>
                    </div>
                    """, unsafe_allow_html=True)
                elif status == 'running':
                    st.markdown(f"""
                    <div style="text-align: center; padding: 1rem; background: linear-gradient(135deg, rgba(78, 205, 196, 0.2), rgba(78, 205, 196, 0.1)); border-radius: 10px; border: 2px solid #4ECDC4;">
                        <div style="font-size: 2rem;">{stage['icon']}</div>
                        <div style="font-weight: 600; margin-top: 0.5rem;">{stage['label']}</div>
                        <div style="color: #4ECDC4; font-size: 0.85rem; margin-top: 0.25rem;">⏳ 进行中</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="text-align: center; padding: 1rem; background: linear-gradient(135deg, rgba(243, 129, 129, 0.2), rgba(243, 129, 129, 0.1)); border-radius: 10px; border: 2px solid #F38181;">
                        <div style="font-size: 2rem;">{stage['icon']}</div>
                        <div style="font-weight: 600; margin-top: 0.5rem;">{stage['label']}</div>
                        <div style="color: #F38181; font-size: 0.85rem; margin-top: 0.25rem;">✗ 失败</div>
                    </div>
                    """, unsafe_allow_html=True)

                # Expandable details
                with st.expander(f"📊 {stage['label']}详情", expanded=False):
                    st.write(f"**状态**: {status}")
                    st.write(f"**耗时**: {duration:.2f}秒")
                    st.write(f"**组件**: {span.get('component', 'N/A')}")

                    metadata = span.get('metadata', {})
                    if metadata:
                        st.write("**元数据**:")
                        st.json(metadata)

            else:
                # Stage not found in trace
                st.markdown(f"""
                <div style="text-align: center; padding: 1rem; background: rgba(255, 255, 255, 0.05); border-radius: 10px; border: 1px dashed rgba(255, 255, 255, 0.2);">
                    <div style="font-size: 2rem; opacity: 0.3;">{stage['icon']}</div>
                    <div style="font-weight: 600; margin-top: 0.5rem; opacity: 0.5;">{stage['label']}</div>
                    <div style="color: #888; font-size: 0.85rem; margin-top: 0.25rem;">-</div>
                </div>
                """, unsafe_allow_html=True)

    # Add arrows between stages
    st.markdown("""
    <div style="text-align: center; margin-top: 1rem; color: #888;">
        🔍 → 🏷️ → 🔬 → 📋 → ✅ → ⚡ → 🔎 → 📄
    </div>
    """, unsafe_allow_html=True)

    # Summary metrics
    st.markdown("### 📊 执行统计")

    total_duration = sum(s.get('duration', 0) for s in trace_data)
    success_count = sum(1 for s in trace_data if s.get('status') == 'success')
    total_count = len(trace_data)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("总耗时", f"{total_duration:.2f}s")

    with col2:
        st.metric("成功步骤", f"{success_count}/{total_count}")

    with col3:
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        st.metric("成功率", f"{success_rate:.1f}%")
