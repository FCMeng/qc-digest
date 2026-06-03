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
    track: str
    authors: List[str] = field(default_factory=list)

    def to_prompt_dict(self, index: int) -> Dict[str, Any]:
        return {
            "id": index,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "published_date": self.published.isoformat() if self.published else None,
            "source_type": self.source_type,
            "track": self.track,
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
    track: str = "quantum"
    category: Optional[str] = None

    @classmethod
    def from_llm(cls, data: Dict[str, Any], default_track: str = "quantum") -> "DigestItem":
        kind = str(data.get("kind", "")).strip().lower()
        if kind not in {"papers", "news"}:
            kind = "news"
        track = str(data.get("track") or default_track).strip().lower()
        if track not in {"quantum", "ai_ml"}:
            track = default_track
        return cls(
            title=str(data.get("title", "")).strip(),
            kind=kind,
            source=str(data.get("source", "")).strip(),
            published_date=data.get("published_date") or None,
            url=str(data.get("url", "")).strip(),
            score=float(data.get("score", 0) or 0),
            summary=str(data.get("summary", "")).strip(),
            why_selected=str(data.get("why_selected", "")).strip(),
            track=track,
            category=data.get("category") or None,
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
