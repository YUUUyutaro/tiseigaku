"""Entry point for the geopolitical news illustrated-report generator (mock)."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import yaml

from .geopolitics.analyzer import analyze_batch, keyword_filter
from .geopolitics.archive import (
    load_recent_archives,
    related_archive_entries,
    save_daily_archive,
)
from .geopolitics.fetcher import fetch_from_mock, fetch_from_rss
from .geopolitics.models import Analysis, Article
from .geopolitics.reporter import render, render_index

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
    p.add_argument(
        "--site",
        action="store_true",
        help="docs/ 配下に静的サイト形式で出力し index.html を更新",
    )
    p.add_argument(
        "--site-dir",
        type=Path,
        default=ROOT / "docs",
        help="--site 時の公開ディレクトリ(既定 docs/)",
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
    max_articles = int(analysis_cfg.get("max_articles", 5))

    # 1. Fetch (多めに取得しておき、段階的に絞り込む)
    articles: List[Article]
    if args.mock:
        articles = fetch_from_mock(args.mock_data)
    else:
        articles = fetch_from_rss(
            config.get("feeds", []),
            keywords=config.get("keywords", []),
            limit=max_articles * 10,  # Step 1 の事前選別に回すため多めに
        )
    log.info("Fetched %d article(s)", len(articles))
    if not articles:
        log.warning("No articles fetched; aborting.")
        return 1

    # Step 1: APIを使わないキーワード事前選別
    articles = keyword_filter(articles, max_articles=max_articles)
    log.info("After pre-filter: %d article(s)", len(articles))
    if not articles:
        log.warning("No articles passed the pre-filter; aborting.")
        return 1

    # Step 2: Claude API で構造化分析
    analyses: List[Analysis] = analyze_batch(
        articles,
        use_mock=args.mock,
        model=analysis_cfg.get("model", "claude-opus-4-7"),
    )

    # Step 2-b: 重要度でソート(高→中→低)
    importance_order = {"高": 0, "中": 1, "低": 2}
    analyses.sort(key=lambda a: importance_order.get(a.importance, 99))
    log.info("Produced %d analysis/analyses", len(analyses))
    if not analyses:
        log.warning("All analyses failed; aborting.")
        return 1

    today = datetime.now().strftime("%Y-%m-%d")

    # Step 3: 当日分をアーカイブ保存(モック/本番問わず)
    archive_path = save_daily_archive(analyses, today)
    log.info("Saved archive: %s", archive_path)

    # Step 3-b: 過去1週間のアーカイブと、各記事の関連エントリを収集
    recent_archives = load_recent_archives(days=7, exclude_date=today)
    related_by_index: List[List[dict]] = [
        related_archive_entries(recent_archives, a.region_tags, limit=5) for a in analyses
    ]

    # 地域別グルーピング
    region_groups: dict = {}
    for a in analyses:
        for tag in a.region_tags or ["global"]:
            region_groups.setdefault(tag, []).append(a)

    extra_ctx = {
        "recent_archives": recent_archives,
        "related_entries": related_by_index,
        "region_groups": region_groups,
    }

    # 4. Render
    if args.site:
        reports_dir = args.site_dir / "reports"
        written = render(
            analyses,
            templates_dir=ROOT / "templates",
            output_dir=reports_dir,
            formats=formats,
            title=f"地政学ニュース図解レポート {today} 号",
            report_name=today,
            write_manifest=True,
            extra=extra_ctx,
        )
        index_path = render_index(
            args.site_dir, templates_dir=ROOT / "templates"
        )
        written.append(index_path)
    else:
        output_dir = args.output or ROOT / output_cfg.get("dir", "output")
        written = render(
            analyses,
            templates_dir=ROOT / "templates",
            output_dir=output_dir,
            formats=formats,
            extra=extra_ctx,
        )

    for path in written:
        log.info("Wrote %s", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
