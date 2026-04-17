from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import Analysis
from .visualizer import diagrams_for


def _env(templates_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "htm", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render(
    analyses: List[Analysis],
    *,
    templates_dir: Path,
    output_dir: Path,
    formats: Iterable[str] = ("html", "md"),
    title: str = "地政学ニュース図解レポート",
) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    env = _env(templates_dir)
    diagrams = [diagrams_for(a) for a in analyses]
    context = {
        "title": title,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "analyses": analyses,
        "diagrams": diagrams,
    }
    written: List[Path] = []
    if "html" in formats:
        html = env.get_template("report.html.j2").render(**context)
        path = output_dir / "report.html"
        path.write_text(html, encoding="utf-8")
        written.append(path)
    if "md" in formats:
        md = env.get_template("report.md.j2").render(**context)
        path = output_dir / "report.md"
        path.write_text(md, encoding="utf-8")
        written.append(path)
    return written
