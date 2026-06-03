import re
from typing import Dict, Iterable, List
from urllib.parse import urlparse

from llm_client import LLMClient
from models import DigestItem, RawItem


def normalize_title(title: str) -> str:
    return re.sub(r"\W+", " ", title.lower()).strip()


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    if "news.google.com" in parsed.netloc:
        return url
    return parsed._replace(query="", fragment="").geturl().rstrip("/")


def deduplicate_raw(items: Iterable[RawItem]) -> List[RawItem]:
    seen = set()
    result: List[RawItem] = []
    for item in items:
        key = canonical_url(item.url) or normalize_title(item.title)
        title_key = normalize_title(item.title)
        dedupe_key = key or title_key
        if dedupe_key in seen or title_key in seen:
            continue
        seen.add(dedupe_key)
        seen.add(title_key)
        result.append(item)
    return result


def pre_rank(items: List[RawItem], track_config: Dict[str, object], max_candidates: int = 60) -> List[RawItem]:
    keywords = [str(keyword).lower() for keyword in track_config.get("keywords", [])]
    paper_terms = [str(term).lower() for term in track_config.get("paper_terms", [])]

    def score(item: RawItem) -> float:
        text = "{} {}".format(item.title, item.raw_text).lower()
        keyword_hits = sum(
            1
            for keyword in keywords + paper_terms
            if keyword in text
        )
        source_bonus = 4.0 if item.source_type == "arxiv" else 1.0
        date_bonus = item.published.timestamp() / 10_000_000_000 if item.published else 0
        return keyword_hits * 2 + source_bonus + date_bonus

    return sorted(items, key=score, reverse=True)[:max_candidates]


def balanced_candidates(items: List[RawItem], track_config: Dict[str, object], max_candidates: int = 60, min_papers: int = 20) -> List[RawItem]:
    deduped = deduplicate_raw(items)
    papers = pre_rank([item for item in deduped if item.source_type == "arxiv"], track_config, max_candidates=max_candidates)
    news = pre_rank([item for item in deduped if item.source_type != "arxiv"], track_config, max_candidates=max_candidates)

    selected = papers[:min_papers]
    selected.extend(news[: max_candidates - len(selected)])
    if len(selected) < max_candidates:
        selected.extend(papers[min_papers:max_candidates])
    return deduplicate_raw(selected)[:max_candidates]


def deduplicate_digest(items: Iterable[DigestItem]) -> List[DigestItem]:
    seen = set()
    result: List[DigestItem] = []
    for item in items:
        if not item.title or not item.url or not item.summary:
            continue
        key = canonical_url(item.url) or normalize_title(item.title)
        title_key = normalize_title(item.title)
        if key in seen or title_key in seen:
            continue
        seen.add(key)
        seen.add(title_key)
        result.append(item)
    return result


def analyze_items(raw_items: List[RawItem], track_config: Dict[str, object], track: str, limit: int = 10) -> List[DigestItem]:
    candidates = balanced_candidates(raw_items, track_config)
    prompt_items = [item.to_prompt_dict(index) for index, item in enumerate(candidates)]

    llm = LLMClient()
    data: Dict[str, object] = llm.analyze_batch(prompt_items, limit=limit, track_config=track_config, track=track)
    digest_items = [DigestItem.from_llm(item, default_track=track) for item in data.get("items", [])]
    digest_items = [item for item in digest_items if item.track == track]
    digest_items = deduplicate_digest(digest_items)
    digest_items.sort(key=lambda item: item.score, reverse=True)
    return digest_items[:limit]
