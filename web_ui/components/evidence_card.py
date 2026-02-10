"""
Evidence card component for Sentinel Web UI.
Displays evidence collected during investigation phase.
"""

import streamlit as st
from typing import List, Dict
import json


def render_evidence_section(evidence_list: List[Dict]):
    """
    Render evidence cards section.

    Args:
        evidence_list: List of evidence items from report
    """
    st.markdown("## 🔬 调查证据")

    if not evidence_list:
        st.info("暂无证据数据")
        return

    # Group evidence by source type
    evidence_by_type = {}
    for evidence in evidence_list:
        source = evidence.get('source', 'unknown')
        if source not in evidence_by_type:
            evidence_by_type[source] = []
        evidence_by_type[source].append(evidence)

    # Render each evidence group
    for source, items in evidence_by_type.items():
        render_evidence_group(source, items)


def render_evidence_group(source: str, items: List[Dict]):
    """
    Render a group of evidence items from the same source.

    Args:
        source: Evidence source name
        items: List of evidence items
    """
    # Source icon mapping
    source_icons = {
        'query_metrics': '📊',
        'query_logs': '📝',
        'query_topology': '🌐',
        'get_change_history': '📜',
    }

    icon = source_icons.get(source, '📋')

    # Use header instead of expander to avoid nesting (Streamlit disallows expander inside expander)
    st.markdown(f"### {icon} {source} ({len(items)} 条证据)")
    for i, evidence in enumerate(items):
        render_evidence_card(evidence, i)


def render_evidence_card(evidence: Dict, index: int):
    """
    Render a single evidence card.

    Args:
        evidence: Evidence item
        index: Card index
    """
    data = evidence.get('data', {})
    confidence = evidence.get('confidence', 0)
    notes = evidence.get('notes', '')
    timestamp = evidence.get('timestamp', '')

    # Card container
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(255, 107, 107, 0.05), rgba(78, 205, 196, 0.05));
                border-radius: 10px; padding: 1rem; margin-bottom: 1rem;
                border-left: 4px solid #FF6B6B;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <div style="font-weight: 600;">证据 #{index + 1}</div>
            <div style="background: rgba(78, 205, 196, 0.2); padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem;">
                置信度: {confidence * 100:.0f}%
            </div>
        </div>
        <div style="color: #888; font-size: 0.85rem; margin-bottom: 0.5rem;">
            ⏰ {timestamp}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Notes
    if notes:
        st.markdown(f"**说明**: {notes}")

    # Data display
    if isinstance(data, dict):
        # Check for error
        if 'error' in data:
            st.error(f"❌ {data.get('error')}: {data.get('message', '')}")
        else:
            # Display key-value pairs
            if 'metric' in data:
                st.write(f"**指标**: {data.get('metric')}")

            if 'service' in data:
                st.write(f"**服务**: {data.get('service')}")

            if 'data_points' in data:
                st.write(f"**数据点数**: {data.get('data_points')}")

            if 'aggregation' in data:
                agg = data.get('aggregation', {})
                if 'max' in agg:
                    st.write(f"**最大值**: {agg['max']:.2f}")

            if 'total_count' in data:
                st.write(f"**总数**: {data.get('total_count')}")

            if 'total_entries' in data:
                st.write(f"**日志条目**: {data.get('total_entries')}")

            # Show raw data in expander
            with st.expander("🔍 查看原始数据", expanded=False):
                st.json(data)
    else:
        st.write(data)

    st.divider()
