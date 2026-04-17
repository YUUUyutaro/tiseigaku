import json
import logging
import os
import re
from typing import List, Optional

from .models import Actor, Analysis, Article, Impact, Issue

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """あなたは地政学・安全保障の専門アナリストです。
与えられたニュース記事を読み、日本語で「図解付き解説」向けの構造化データを JSON で返してください。

必ず以下のスキーマに従い、JSON オブジェクトのみを出力してください:
{
  "headline_ja": "日本語の見出し (30文字以内)",
  "summary_ja": "3〜5文の日本語要約",
  "background": "背景・経緯の説明 (2〜3文)",
  "actors": [
    {"name": "当事者名", "role": "国家|国際機関|非国家主体|企業など", "stance": "推進|反対|中立|被害|その他"}
  ],
  "issues": [
    {"title": "争点", "description": "1〜2文の説明"}
  ],
  "impacts": [
    {"domain": "経済|安全保障|エネルギー|外交|技術 など", "description": "影響の説明", "severity": "低|中|高"}
  ],
  "key_points": ["読者が押さえるべき要点1", "要点2", "要点3"]
}
"""


def _strip_json(text: str) -> str:
    """Extract a JSON object from a model response, stripping code fences if present."""
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fence:
        return fence.group(1).strip()
    # Fallback: take from first { to last }
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _to_analysis(article: Article, payload: dict) -> Analysis:
    return Analysis(
        article=article,
        headline_ja=payload.get("headline_ja", article.title),
        summary_ja=payload.get("summary_ja", ""),
        background=payload.get("background", ""),
        actors=[Actor(**a) for a in payload.get("actors", [])],
        issues=[Issue(**i) for i in payload.get("issues", [])],
        impacts=[Impact(**i) for i in payload.get("impacts", [])],
        key_points=list(payload.get("key_points", [])),
    )


def analyze_with_claude(
    article: Article,
    model: str = "claude-sonnet-4-6",
    api_key: Optional[str] = None,
) -> Analysis:
    """Call the Claude API to produce a structured analysis for a single article."""
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    user_prompt = (
        f"タイトル: {article.title}\n"
        f"ソース: {article.source}\n"
        f"公開日時: {article.published.isoformat() if article.published else '不明'}\n"
        f"本文(要約): {article.summary}\n"
    )

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )
    payload = json.loads(_strip_json(raw))
    return _to_analysis(article, payload)


def analyze_mock(article: Article) -> Analysis:
    """Deterministic stub analysis for offline demo / tests.

    The shape mirrors what the Claude-powered analyzer returns.
    """
    title = article.title
    # A very light-weight heuristic: generate plausible structure based on the article.
    actors = [
        Actor(name="当事国A", role="国家", stance="推進"),
        Actor(name="当事国B", role="国家", stance="反対"),
        Actor(name="国際機関", role="国際機関", stance="中立"),
    ]
    issues = [
        Issue(title="主権・領土", description="領域の管轄権と国際法上の位置づけが争点。"),
        Issue(title="同盟関係", description="周辺国・同盟国を巻き込む連鎖反応が懸念されている。"),
    ]
    impacts = [
        Impact(domain="安全保障", description="周辺地域の軍事的緊張が高まる。", severity="高"),
        Impact(domain="経済", description="資源価格と貿易ルートに影響が波及する。", severity="中"),
        Impact(domain="外交", description="国際会議における合意形成が難しくなる。", severity="中"),
    ]
    return Analysis(
        article=article,
        headline_ja=title[:30],
        summary_ja=(article.summary or title)[:240],
        background="近年の地域情勢と過去の合意を踏まえた文脈で捉える必要がある。",
        actors=actors,
        issues=issues,
        impacts=impacts,
        key_points=[
            "当事者と立場を押さえる",
            "直近のトリガーとなった出来事を確認する",
            "安全保障・経済・外交への波及を分けて理解する",
        ],
    )


def analyze_batch(
    articles: List[Article],
    *,
    use_mock: bool,
    model: str = "claude-sonnet-4-6",
    api_key: Optional[str] = None,
) -> List[Analysis]:
    results: List[Analysis] = []
    for article in articles:
        try:
            if use_mock:
                results.append(analyze_mock(article))
            else:
                results.append(
                    analyze_with_claude(article, model=model, api_key=api_key)
                )
        except Exception as exc:  # keep going on per-article failures
            logger.warning("Analysis failed for %s: %s", article.title, exc)
    return results
