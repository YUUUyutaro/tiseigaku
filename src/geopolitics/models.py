from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional


@dataclass
class Article:
    title: str
    url: str
    source: str
    published: Optional[datetime]
    summary: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["published"] = self.published.isoformat() if self.published else None
        return d


@dataclass
class Actor:
    name: str
    role: str  # e.g. "国家", "国際機関", "非国家主体"
    stance: str  # e.g. "推進", "反対", "中立"


@dataclass
class Issue:
    title: str
    description: str


@dataclass
class Impact:
    domain: str  # e.g. "経済", "安全保障", "エネルギー"
    description: str
    severity: str  # "低" / "中" / "高"


@dataclass
class TimelineEvent:
    date: str  # ISO date (YYYY-MM-DD) or free-form label
    label: str  # 1行で書ける出来事の要約


@dataclass
class Relationship:
    """当事者同士の関係。source → target に kind 種類の関係があるとみなす。"""

    source: str  # actor name
    target: str  # actor name
    kind: str  # "同盟" | "対立" | "緊張" | "支援" | "交渉" | "依存"


@dataclass
class Reference:
    title: str
    url: str
    note: str = ""  # 1行補足(任意)


@dataclass
class Analysis:
    article: Article
    headline_ja: str
    summary_ja: str
    background: str
    actors: List[Actor] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)
    impacts: List[Impact] = field(default_factory=list)
    timeline: List[TimelineEvent] = field(default_factory=list)
    relationships: List[Relationship] = field(default_factory=list)
    references: List[Reference] = field(default_factory=list)
    key_points: List[str] = field(default_factory=list)
