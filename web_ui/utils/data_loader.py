"""
Data loader utilities for Sentinel Web UI.
Load episode, report, and trace data from runs directory.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


def list_episodes(runs_dir: str = "./runs") -> List[Dict[str, str]]:
    """
    List all available episodes from runs directory.

    Returns:
        List of dicts with episode_id, timestamp, and path
    """
    runs_path = Path(runs_dir)
    if not runs_path.exists():
        return []

    episodes = []
    for episode_dir in sorted(runs_path.iterdir(), reverse=True):
        if not episode_dir.is_dir():
            continue

        episode_file = episode_dir / "episode.json"
        if episode_file.exists():
            try:
                with open(episode_file, 'r') as f:
                    data = json.load(f)
                    episodes.append({
                        "episode_id": data.get("episode_id", episode_dir.name),
                        "timestamp": data.get("created_at", "Unknown"),
                        "path": str(episode_dir),
                        "scenario": data.get("config", {}).get("scenario", "unknown"),
                        "service": data.get("task", {}).get("symptoms", {}).get("service", "unknown"),
                    })
            except Exception as e:
                print(f"Error loading {episode_file}: {e}")
                continue

    return episodes


def load_episode(episode_path: str) -> Optional[Dict]:
    """
    Load a complete episode including report and trace.

    Args:
        episode_path: Path to episode directory

    Returns:
        Dict with episode, report, and trace data
    """
    episode_dir = Path(episode_path)
    if not episode_dir.exists():
        return None

    result = {}

    # Load episode.json
    episode_file = episode_dir / "episode.json"
    if episode_file.exists():
        with open(episode_file, 'r') as f:
            result['episode'] = json.load(f)

    # Load report.json
    report_file = episode_dir / "report.json"
    if report_file.exists():
        with open(report_file, 'r') as f:
            result['report'] = json.load(f)

    # Load trace.jsonl
    trace_file = episode_dir / "trace.jsonl"
    if trace_file.exists():
        result['trace'] = parse_trace(str(trace_file))

    return result


def parse_trace(trace_file: str) -> List[Dict]:
    """
    Parse trace.jsonl file into list of span events.

    Args:
        trace_file: Path to trace.jsonl file

    Returns:
        List of span events with computed durations
    """
    spans = []
    span_map = {}  # span_id -> span data

    with open(trace_file, 'r') as f:
        for line in f:
            if not line.strip():
                continue

            event = json.loads(line)
            event_type = event.get('type')
            span_data = event.get('span', {})

            if event_type == 'span_start':
                span_id = span_data.get('span_id')
                span_map[span_id] = {
                    'span_id': span_id,
                    'name': span_data.get('name'),
                    'component': span_data.get('component'),
                    'start_time': span_data.get('start_time'),
                    'status': 'running',
                    'metadata': span_data.get('metadata', {}),
                }

            elif event_type == 'span_end':
                span_id = span_data.get('span_id')
                if span_id in span_map:
                    span = span_map[span_id]
                    span['end_time'] = span_data.get('end_time')
                    span['status'] = span_data.get('status', 'success')
                    span['error'] = span_data.get('error')

                    # Compute duration
                    if span['start_time'] and span['end_time']:
                        try:
                            start = datetime.fromisoformat(span['start_time'].replace('Z', '+00:00'))
                            end = datetime.fromisoformat(span['end_time'].replace('Z', '+00:00'))
                            span['duration'] = (end - start).total_seconds()
                        except:
                            span['duration'] = 0

                    # Update metadata from end event
                    span['metadata'].update(span_data.get('metadata', {}))

                    spans.append(span)

    return spans


def get_latest_episode(runs_dir: str = "./runs") -> Optional[Dict]:
    """
    Get the most recent episode.

    Returns:
        Episode data or None
    """
    episodes = list_episodes(runs_dir)
    if not episodes:
        return None

    return load_episode(episodes[0]['path'])


def format_timestamp(timestamp: str) -> str:
    """
    Format timestamp for display.

    Args:
        timestamp: ISO format timestamp

    Returns:
        Formatted string
    """
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return timestamp
