from __future__ import annotations

import json
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
    report_name: str = "report",
    write_manifest: bool = False,
) -> List[Path]:
    """1件ぶんのレポートを書き出す。

    `write_manifest=True` の場合、index.html 再生成用のメタ情報 JSON も
    同じディレクトリに `<report_name>.json` として書き出す。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    env = _env(templates_dir)
    diagrams = [diagrams_for(a) for a in analyses]
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    context = {
        "title": title,
        "generated_at": generated_at,
        "analyses": analyses,
        "diagrams": diagrams,
    }
    written: List[Path] = []
    if "html" in formats:
        html = env.get_template("report.html.j2").render(**context)
        path = output_dir / f"{report_name}.html"
        path.write_text(html, encoding="utf-8")
        written.append(path)
    if "md" in formats:
        md = env.get_template("report.md.j2").render(**context)
        path = output_dir / f"{report_name}.md"
        path.write_text(md, encoding="utf-8")
        written.append(path)

    if write_manifest:
        manifest = {
            "slug": report_name,
            "title": title,
            "generated_at": generated_at,
            "count": len(analyses),
            "headlines": [a.headline_ja for a in analyses],
            "formats": [fmt for fmt in formats],
        }
        manifest_path = output_dir / f"{report_name}.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        written.append(manifest_path)

    return written


def render_index(
    site_dir: Path,
    *,
    templates_dir: Path,
    reports_subdir: str = "reports",
    site_title: str = "地政学ニュース図解アーカイブ",
) -> Path:
    """`site_dir/<reports_subdir>/*.json` を読み、`site_dir/index.html` を生成する。"""
    reports_dir = site_dir / reports_subdir
    manifests: List[dict] = []
    if reports_dir.exists():
        for p in sorted(reports_dir.glob("*.json"), reverse=True):
            try:
                manifests.append(json.loads(p.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue

    env = _env(templates_dir)
    html = env.get_template("index.html.j2").render(
        site_title=site_title,
        reports=manifests,
        reports_subdir=reports_subdir,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    out = site_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    return out
