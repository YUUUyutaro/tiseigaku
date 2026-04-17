"""Entry point for the geopolitical news illustrated-report generator (mock)."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List

import yaml

from .geopolitics.analyzer import analyze_batch
from .geopolitics.fetcher import fetch_from_mock, fetch_from_rss
from .geopolitics.models import Analysis, Article
from .geopolitics.reporter import render

ROOT = Path(__file__).resolve().parent.parent


def _load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="地政学ニュース図解ジェネレータ")
    p.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    p.add_argument("--mock", action="store_true", help="サンプルデータ + モック解析で動作")
    p.add_argument(
        "--mock-data", type=Path, default=ROOT / "data" / "mock_news.json"
    )
    p.add_argument("--output", type=Path, default=None, help="出力ディレクトリを上書き")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def run(argv: List[str]) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    log = logging.getLogger("main")

    config = _load_config(args.config) if args.config.exists() else {}
    analysis_cfg = config.get("analysis", {})
    output_cfg = config.get("output", {})
    formats = tuple(output_cfg.get("formats", ["html", "md"]))
    output_dir = args.output or ROOT / output_cfg.get("dir", "output")
    max_articles = int(analysis_cfg.get("max_articles", 5))

    # 1. Fetch
    articles: List[Article]
    if args.mock:
        articles = fetch_from_mock(args.mock_data)
    else:
        articles = fetch_from_rss(
            config.get("feeds", []),
            keywords=config.get("keywords", []),
            limit=max_articles * 3,
        )
    articles = articles[:max_articles]
    log.info("Fetched %d article(s)", len(articles))
    if not articles:
        log.warning("No articles fetched; aborting.")
        return 1

    # 2. Analyze
    analyses: List[Analysis] = analyze_batch(
        articles,
        use_mock=args.mock,
        model=analysis_cfg.get("model", "claude-sonnet-4-6"),
    )
    log.info("Produced %d analysis/analyses", len(analyses))
    if not analyses:
        log.warning("All analyses failed; aborting.")
        return 1

    # 3. Render report
    written = render(
        analyses,
        templates_dir=ROOT / "templates",
        output_dir=output_dir,
        formats=formats,
    )
    for path in written:
        log.info("Wrote %s", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
