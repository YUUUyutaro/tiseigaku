"""Generate Mermaid diagrams from Analysis objects.

We produce four complementary diagrams per article:
  - actor_map: 当事者と立場の関係図 (flowchart)
  - impact_tree: 影響ドメインとその重大度 (flowchart)
  - timeline: 出来事の経緯 (timeline)
  - key_points: 要点チェックリスト (mindmap)

Mermaid source is returned as text and rendered client-side in the HTML report.
"""
from __future__ import annotations

import re
from typing import List

from .models import Analysis

_STANCE_COLOR = {
    "推進": "#2e7d32",
    "反対": "#c62828",
    "中立": "#616161",
    "被害": "#ef6c00",
}
_SEVERITY_COLOR = {"高": "#c62828", "中": "#ef6c00", "低": "#2e7d32"}


def _safe(label: str) -> str:
    """Make a string safe to embed inside a Mermaid node label."""
    return re.sub(r'["\n\r]', " ", label).strip()


def _node_id(prefix: str, index: int) -> str:
    return f"{prefix}{index}"


def actor_map(analysis: Analysis) -> str:
    lines: List[str] = ["flowchart LR"]
    center = "T"
    lines.append(f'  {center}["{_safe(analysis.headline_ja)}"]')
    for i, actor in enumerate(analysis.actors):
        node = _node_id("A", i)
        lines.append(f'  {node}["{_safe(actor.name)}\\n({_safe(actor.role)})"]')
        lines.append(f"  {node} -- {_safe(actor.stance)} --> {center}")
        color = _STANCE_COLOR.get(actor.stance, "#1565c0")
        lines.append(f"  style {node} fill:{color},color:#fff,stroke:#333")
    lines.append(f"  style {center} fill:#263238,color:#fff,stroke:#000")
    return "\n".join(lines)


def impact_tree(analysis: Analysis) -> str:
    lines: List[str] = ["flowchart TB"]
    root = "R"
    lines.append(f'  {root}["影響の広がり"]')
    for i, impact in enumerate(analysis.impacts):
        dn = _node_id("D", i)
        inn = _node_id("I", i)
        lines.append(f'  {dn}["{_safe(impact.domain)}"]')
        lines.append(
            f'  {inn}["{_safe(impact.description)}\\n(重大度: {_safe(impact.severity)})"]'
        )
        lines.append(f"  {root} --> {dn} --> {inn}")
        color = _SEVERITY_COLOR.get(impact.severity, "#1565c0")
        lines.append(f"  style {inn} fill:{color},color:#fff,stroke:#333")
    lines.append(f"  style {root} fill:#263238,color:#fff,stroke:#000")
    return "\n".join(lines)


def timeline_diagram(analysis: Analysis) -> str:
    """Mermaid `timeline` 構文で経緯図を出す。

    Mermaid timeline の構文:
        timeline
            title <図のタイトル>
            <section/date> : <出来事ラベル>

    日付に ':' が入ると構文が壊れるので、コロンは中黒に置換する。
    """
    lines: List[str] = ["timeline"]
    lines.append(f"  title {_safe(analysis.headline_ja)} — 経緯")
    if not analysis.timeline:
        lines.append("  情報なし : タイムラインが取得できませんでした")
        return "\n".join(lines)
    for event in analysis.timeline:
        date = _safe(event.date).replace(":", "・")
        label = _safe(event.label).replace(":", "・")
        lines.append(f"  {date} : {label}")
    return "\n".join(lines)


def key_points_mindmap(analysis: Analysis) -> str:
    lines = ["mindmap", f"  root(({_safe(analysis.headline_ja)}))"]
    for point in analysis.key_points:
        lines.append(f"    {_safe(point)}")
    return "\n".join(lines)


def diagrams_for(analysis: Analysis) -> dict:
    return {
        "actor_map": actor_map(analysis),
        "impact_tree": impact_tree(analysis),
        "timeline": timeline_diagram(analysis),
        "key_points": key_points_mindmap(analysis),
    }
