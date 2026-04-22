"""過去ブリーフィングのアーカイブ管理と、地域別ナレッジベース参照。

- `data/archive/YYYY-MM-DD.json` に毎日のエントリを保存
- `load_recent_archives(days=7)` で過去7日分をプロンプト用の軽量形式で読み込み
- `load_knowledge(region_tags)` で `data/knowledge/*.md` を選択的にロード
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List

from .models import Analysis

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR = ROOT / "data" / "archive"
KNOWLEDGE_DIR = ROOT / "data" / "knowledge"

# region_tag から knowledge/*.md ファイル名へのマッピング
_REGION_TO_FILES = {
    "east_asia": ["taiwan_strait.md", "japan_us_alliance.md"],
    "southeast_asia": ["south_china_sea.md", "asean_framework.md"],
    "europe": [],  # 未整備
    "middle_east": ["middle_east.md", "iran_nuclear.md"],
    "cyber": ["cyber_security.md"],
    "gcap": ["gcap.md"],
    "global": [],
}


def save_daily_archive(analyses: List[Analysis], date_str: str) -> Path:
    """当日分のアーカイブ JSON を書き出す。

    保存内容は要約のみ(本文・全構造データは保存しない) — 後日プロンプトに
    含めるときの肥大化を避けるため。
    """
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    for a in analyses:
        entries.append(
            {
                "title": a.headline_ja,
                "summary": a.summary_ja,
                "actors": [act.name for act in a.actors],
                "region_tags": a.region_tags,
                "importance": a.importance,
                "source": a.article.source,
                "url": a.article.url,
            }
        )
    payload = {"date": date_str, "entries": entries}
    path = ARCHIVE_DIR / f"{date_str}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_recent_archives(*, days: int = 7, exclude_date: str | None = None) -> List[dict]:
    """過去 `days` 日分のアーカイブを新しい順で返す。

    各要素は `{"date": "YYYY-MM-DD", "entries": [...]}` の形式。
    `exclude_date` は除外したい日付(当日など)。
    """
    if not ARCHIVE_DIR.exists():
        return []
    today = datetime.now().date()
    results: List[dict] = []
    for i in range(1, days + 1):
        d = today - timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        if exclude_date and date_str == exclude_date:
            continue
        path = ARCHIVE_DIR / f"{date_str}.json"
        if not path.exists():
            continue
        try:
            results.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            log.warning("Invalid archive JSON: %s", path)
    return results


def load_knowledge(region_tags: Iterable[str]) -> str:
    """指定された地域タグに対応するナレッジベース Markdown を連結して返す。

    該当ファイルがなければ空文字を返す。全ファイルを読まないことでトークン節約。
    """
    if not KNOWLEDGE_DIR.exists():
        return ""
    seen: set[str] = set()
    chunks: List[str] = []
    for tag in region_tags:
        for fname in _REGION_TO_FILES.get(tag, []):
            if fname in seen:
                continue
            seen.add(fname)
            path = KNOWLEDGE_DIR / fname
            if path.exists():
                chunks.append(f"--- {fname} ---\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(chunks)


def related_archive_entries(
    archives: List[dict], region_tags: Iterable[str], limit: int = 5
) -> List[dict]:
    """過去アーカイブから、region_tag がひとつでも重なるエントリを返す。

    レポートの「関連する過去の動き」欄に使う。新しい順に並べて `limit` 件。
    """
    tag_set = set(region_tags)
    hits: List[dict] = []
    for arch in archives:
        for e in arch.get("entries", []):
            if tag_set.intersection(set(e.get("region_tags", []))):
                hits.append({**e, "date": arch.get("date", "")})
                if len(hits) >= limit:
                    return hits
    return hits


def summarize_for_prompt(archives: List[dict], max_entries: int = 20) -> str:
    """過去アーカイブを、プロンプトに埋め込むための短いテキストにまとめる。

    本文全体ではなく、日付・見出し・地域タグのみ。
    """
    lines: List[str] = []
    count = 0
    for arch in archives:
        date = arch.get("date", "")
        for e in arch.get("entries", []):
            if count >= max_entries:
                break
            tags = ",".join(e.get("region_tags", []))
            lines.append(
                f"- [{date}] {e.get('title', '')} ({tags}, 重要度:{e.get('importance', '中')})"
            )
            count += 1
        if count >= max_entries:
            break
    return "\n".join(lines)
