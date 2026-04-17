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
class Analysis:
    article: Article
    headline_ja: str
    summary_ja: str
    background: str
    actors: List[Actor] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)
    impacts: List[Impact] = field(default_factory=list)
    key_points: List[str] = field(default_factory=list)
