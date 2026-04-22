import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import List, Optional

from .models import (
    Actor,
    Analysis,
    Article,
    Impact,
    Issue,
    Reference,
    Relationship,
    TimelineEvent,
)

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """あなたは地政学・安全保障の専門アナリストです。
与えられたニュース記事を読み、日本語で「図解付き解説」向けの構造化データを JSON で返してください。

必ず以下のスキーマに従い、JSON オブジェクトのみを出力してください:
{
  "headline_ja": "日本語の見出し (30文字以内)",
  "summary_ja": "3〜5文の日本語要約",
  "background": "背景・経緯の説明 (2〜3文)",
  "importance": "高|中|低",
  "region_tags": ["east_asia" | "southeast_asia" | "europe" | "middle_east" | "americas" | "africa" | "cyber" | "global"],
  "actors": [
    {"name": "当事者名", "role": "国家|国際機関|非国家主体|企業など", "stance": "推進|反対|中立|被害|その他"}
  ],
  "issues": [
    {"title": "争点", "description": "1〜2文の説明"}
  ],
  "impacts": [
    {"domain": "経済|安全保障|エネルギー|外交|技術 など", "description": "影響の説明", "severity": "低|中|高"}
  ],
  "timeline": [
    {"date": "YYYY-MM-DD または '2週間前' 等の相対表現", "label": "1行でわかる出来事の要約"}
  ],
  "relationships": [
    {"source": "当事者A", "target": "当事者B", "kind": "同盟|対立|緊張|支援|交渉|依存"}
  ],
  "references": [
    {"title": "参考資料のタイトル", "url": "https://...", "note": "補足(任意)"}
  ],
  "key_points": ["読者が押さえるべき要点1", "要点2", "要点3"]
}

importance 判定基準:
- 「高」: 日本の安全保障に直接的影響、関係国が3カ国以上、軍事的緊張を伴う
- 「中」: 間接的影響または関係国2カ国程度、軍事的要素はあるが緊張は限定的
- 「低」: 日本への影響が小さい、または純粋な地域内問題

region_tags はこの記事が該当する地域・テーマを配列で示すこと。
- east_asia: 中国・台湾・朝鮮半島・日米同盟など
- southeast_asia: ASEAN・南シナ海・フィリピンなど
- europe: NATO・ウクライナ・ロシアなど
- middle_east: イラン・イスラエル・ガザ・紅海など
- cyber: サイバー攻撃・情報戦
- global: 複数地域にまたがる案件

timeline は時系列が古い→新しい順で 3〜6 件。記事中の固有の出来事・会談・声明などを
具体的に拾ってください。不明な場合のみ相対表現で構いません。

relationships は actors の name 同士を参照すること。記事中で明示されている
アライアンス・対立・緊張関係のみを拾い、推測で関係を追加しないでください。

references は記事本文で実際に言及・引用された URL のみを使うこと。URL を
創作してはいけません。該当がなければ空配列で構いません。
"""


# Step 1 (APIを使わない事前選別) で記事を通すためのキーワード群。
# タイトル or 要約のどれかに1つ以上マッチすれば通過。
FILTER_KEYWORDS = [
    "防衛", "安全保障", "ASEAN", "南シナ海", "台湾", "サイバー", "ミサイル",
    "同盟", "演習", "領海", "NATO", "インド太平洋", "中国", "北朝鮮",
    "ロシア", "ウクライナ", "イラン", "中東", "イスラエル", "ガザ",
    "紅海", "フーシ", "核合意", "ホルムズ海峡",
    # 英語メディア向け
    "defense", "defence", "security", "military", "nuclear", "missile",
    "NATO", "Ukraine", "Taiwan", "South China Sea", "Iran", "Israel",
    "Gaza", "Houthi", "Red Sea", "sanctions", "alliance",
]


def keyword_filter(articles: list, max_articles: int = 5) -> list:
    """Step 1: APIを使わず、タイトル+要約のキーワードマッチで事前選別する。

    通過条件: FILTER_KEYWORDS のどれか1つ以上が本文に含まれる。
    max_articles 件に絞って返す(公開日時の新しい順)。
    """
    from .models import Article  # 遅延 import (循環回避)

    def matches(article: "Article") -> bool:
        text = f"{article.title} {article.summary}".lower()
        return any(kw.lower() in text for kw in FILTER_KEYWORDS)

    kept = [a for a in articles if matches(a)]
    kept.sort(key=lambda a: a.published or datetime.min, reverse=True)
    return kept[:max_articles]


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
    importance = payload.get("importance", "中")
    if importance not in ("高", "中", "低"):
        importance = "中"
    return Analysis(
        article=article,
        headline_ja=payload.get("headline_ja", article.title),
        summary_ja=payload.get("summary_ja", ""),
        background=payload.get("background", ""),
        importance=importance,
        region_tags=list(payload.get("region_tags", [])),
        actors=[Actor(**a) for a in payload.get("actors", [])],
        issues=[Issue(**i) for i in payload.get("issues", [])],
        impacts=[Impact(**i) for i in payload.get("impacts", [])],
        timeline=[TimelineEvent(**t) for t in payload.get("timeline", [])],
        relationships=[Relationship(**r) for r in payload.get("relationships", [])],
        references=[Reference(**r) for r in payload.get("references", [])],
        key_points=list(payload.get("key_points", [])),
    )


def analyze_with_claude(
    article: Article,
    model: str = "claude-opus-4-7",
    api_key: Optional[str] = None,
    *,
    knowledge_text: str = "",
    recent_context: str = "",
) -> Analysis:
    """Call the Claude API to produce a structured analysis for a single article.

    `knowledge_text` — 該当地域のベースライン知識(data/knowledge/*.md)を連結した文字列。
    `recent_context` — 過去1週間分のアーカイブ要約。どちらも空文字可。
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    parts = [
        f"タイトル: {article.title}",
        f"ソース: {article.source}",
        f"公開日時: {article.published.isoformat() if article.published else '不明'}",
        f"本文(要約): {article.summary}",
    ]
    if knowledge_text:
        parts.append("\n# 参考: 地域ベースライン知識\n" + knowledge_text)
    if recent_context:
        parts.append(
            "\n# 参考: 過去1週間の動き\n"
            + recent_context
            + "\n\n上記の過去1週間の動きを踏まえて、今日のニュースの位置づけを background に含めてください。"
        )
    user_prompt = "\n".join(parts)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.RateLimitError as exc:
        raise RuntimeError(f"レートリミット: {exc}") from exc
    except anthropic.AuthenticationError as exc:
        raise RuntimeError("API キーが無効です。ANTHROPIC_API_KEY を確認してください。") from exc
    except anthropic.APIStatusError as exc:
        raise RuntimeError(f"API エラー ({exc.status_code}): {exc.message}") from exc

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
    base = article.published or datetime.now()
    timeline = [
        TimelineEvent(
            date=(base - timedelta(days=90)).strftime("%Y-%m-%d"),
            label="伏線となる出来事の発生",
        ),
        TimelineEvent(
            date=(base - timedelta(days=30)).strftime("%Y-%m-%d"),
            label="主要当事者による声明・方針転換",
        ),
        TimelineEvent(
            date=(base - timedelta(days=7)).strftime("%Y-%m-%d"),
            label="直接のトリガーとなる動き",
        ),
        TimelineEvent(
            date=base.strftime("%Y-%m-%d"),
            label="本記事で報じられた現時点の動き",
        ),
    ]
    relationships = [
        Relationship(source=actors[0].name, target=actors[1].name, kind="対立"),
        Relationship(source=actors[0].name, target=actors[2].name, kind="交渉"),
        Relationship(source=actors[1].name, target=actors[2].name, kind="緊張"),
    ]
    references = []
    if article.url:
        references.append(
            Reference(title=f"原記事: {article.title}", url=article.url, note=article.source)
        )
    references.extend(
        [
            Reference(
                title="関係国の公式声明(例)",
                url="https://example.gov/statement",
                note="当事国政府が発表した関連声明(モック)",
            ),
            Reference(
                title="国際機関の関連レポート(例)",
                url="https://example.int/report",
                note="国際機関が公表した背景資料(モック)",
            ),
        ]
    )
    # 簡易ヒューリスティック: タイトルに主要キーワードが含まれるかで重要度を決める
    text = f"{title} {article.summary}".lower()
    high_keywords = ["台湾", "ミサイル", "軍事", "攻撃", "侵攻", "taiwan", "missile", "military"]
    if any(kw in text for kw in high_keywords):
        importance = "高"
    else:
        importance = "中"

    region_tags = []
    if any(kw in text for kw in ["中国", "台湾", "朝鮮", "china", "taiwan", "korea"]):
        region_tags.append("east_asia")
    if any(kw in text for kw in ["asean", "南シナ海", "south china sea"]):
        region_tags.append("southeast_asia")
    if any(kw in text for kw in ["nato", "ウクライナ", "ukraine", "russia"]):
        region_tags.append("europe")
    if any(kw in text for kw in ["イラン", "中東", "ガザ", "iran", "middle east", "gaza"]):
        region_tags.append("middle_east")
    if not region_tags:
        region_tags = ["global"]

    return Analysis(
        article=article,
        headline_ja=title[:30],
        summary_ja=(article.summary or title)[:240],
        background="近年の地域情勢と過去の合意を踏まえた文脈で捉える必要がある。",
        importance=importance,
        region_tags=region_tags,
        actors=actors,
        issues=issues,
        impacts=impacts,
        timeline=timeline,
        relationships=relationships,
        references=references,
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
    model: str = "claude-opus-4-7",
    api_key: Optional[str] = None,
) -> List[Analysis]:
    """記事を順次分析する。

    本番モードでは、各記事に対して(地域ベースライン知識 + 過去1週間アーカイブ)を
    プロンプトに追加して呼び出す。モックモードでは付加情報は使わない。
    """
    from .archive import load_knowledge, load_recent_archives, summarize_for_prompt

    results: List[Analysis] = []
    recent_archives = [] if use_mock else load_recent_archives(days=7)
    recent_context = summarize_for_prompt(recent_archives) if recent_archives else ""

    for article in articles:
        try:
            if use_mock:
                results.append(analyze_mock(article))
            else:
                pre_tags = _guess_region_tags(article)
                knowledge = load_knowledge(pre_tags)
                results.append(
                    analyze_with_claude(
                        article,
                        model=model,
                        api_key=api_key,
                        knowledge_text=knowledge,
                        recent_context=recent_context,
                    )
                )
        except Exception as exc:  # keep going on per-article failures
            logger.warning("Analysis failed for %s: %s", article.title, exc)
    return results


def _guess_region_tags(article: Article) -> List[str]:
    """タイトル+要約から地域タグをざっくり推定(ナレッジ選択用)。"""
    text = f"{article.title} {article.summary}".lower()
    tags: List[str] = []
    if any(kw in text for kw in ["中国", "台湾", "朝鮮", "china", "taiwan", "korea"]):
        tags.append("east_asia")
    if any(kw in text for kw in ["asean", "南シナ海", "south china sea", "philippines", "vietnam"]):
        tags.append("southeast_asia")
    if any(kw in text for kw in ["nato", "ウクライナ", "ukraine", "russia"]):
        tags.append("europe")
    if any(kw in text for kw in ["イラン", "中東", "ガザ", "iran", "middle east", "gaza", "israel", "houthi", "紅海"]):
        tags.append("middle_east")
    if any(kw in text for kw in ["cyber", "サイバー", "hack", "ransomware"]):
        tags.append("cyber")
    if any(kw in text for kw in ["gcap", "次期戦闘機", "テンペスト", "tempest"]):
        tags.append("gcap")
    return tags or ["global"]
