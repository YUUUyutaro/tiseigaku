import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from dateutil import parser as date_parser

from .models import Article

logger = logging.getLogger(__name__)


def _matches_keywords(text: str, keywords: Iterable[str]) -> bool:
    if not keywords:
        return True
    text = text.lower()
    return any(kw.lower() in text for kw in keywords)


def fetch_from_rss(
    feeds: List[dict], keywords: Optional[List[str]] = None, limit: int = 20
) -> List[Article]:
    """Fetch articles from RSS feeds. Requires `feedparser`.

    `feeds` is a list of {"name": ..., "url": ...}.
    """
    import feedparser  # imported lazily so mock mode doesn't require it at import time

    articles: List[Article] = []
    for feed in feeds:
        logger.info("Fetching RSS: %s", feed["url"])
        parsed = feedparser.parse(feed["url"])
        for entry in parsed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            if not _matches_keywords(f"{title} {summary}", keywords or []):
                continue
            published = None
            if entry.get("published"):
                try:
                    published = date_parser.parse(entry.published)
                except (ValueError, TypeError):
                    published = None
            articles.append(
                Article(
                    title=title,
                    url=entry.get("link", ""),
                    source=feed.get("name", parsed.feed.get("title", "unknown")),
                    published=published,
                    summary=summary,
                )
            )
    articles.sort(key=lambda a: a.published or datetime.min, reverse=True)
    return articles[:limit]


def fetch_from_mock(path: Path) -> List[Article]:
    """Load sample articles from a JSON file for offline/demo runs."""
    logger.info("Loading mock articles from %s", path)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    articles = []
    for item in data:
        published = None
        if item.get("published"):
            try:
                published = date_parser.parse(item["published"])
            except (ValueError, TypeError):
                published = None
        articles.append(
            Article(
                title=item["title"],
                url=item.get("url", ""),
                source=item.get("source", "mock"),
                published=published,
                summary=item.get("summary", ""),
            )
        )
    return articles
