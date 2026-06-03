from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class RawItem:
    title: str
    url: str
    source: str
    published: Optional[datetime]
    raw_text: str
    source_type: str
    authors: List[str] = field(default_factory=list)

    def to_prompt_dict(self, index: int) -> Dict[str, Any]:
        return {
            "id": index,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "published_date": self.published.isoformat() if self.published else None,
            "source_type": self.source_type,
            "authors": self.authors,
            "text": self.raw_text[:3500],
        }


@dataclass
class DigestItem:
    title: str
    kind: str
    source: str
    published_date: Optional[str]
    url: str
    score: float
    summary: str
    why_selected: str

    @classmethod
    def from_llm(cls, data: Dict[str, Any]) -> "DigestItem":
        kind = str(data.get("kind", "")).strip().lower()
        if kind not in {"papers", "news"}:
            kind = "news"
        return cls(
            title=str(data.get("title", "")).strip(),
            kind=kind,
            source=str(data.get("source", "")).strip(),
            published_date=data.get("published_date") or None,
            url=str(data.get("url", "")).strip(),
            score=float(data.get("score", 0) or 0),
            summary=str(data.get("summary", "")).strip(),
            why_selected=str(data.get("why_selected", "")).strip(),
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
