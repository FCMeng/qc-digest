import re
from difflib import SequenceMatcher
from typing import Dict, Iterable, List
from urllib.parse import urlparse

import requests

from llm_client import LLMClient
from models import DigestItem, RawItem


def normalize_title(title: str) -> str:
    return re.sub(r"\W+", " ", title.lower()).strip()


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    if "news.google.com" in parsed.netloc:
        return url
    return parsed._replace(query="", fragment="").geturl().rstrip("/")


def is_http_url(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_google_news_wrapper(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    return parsed.netloc.endswith("news.google.com") and "/rss/articles/" in parsed.path


def can_publish_url(url: str, allow_google_news_wrapper: bool = False) -> bool:
    if not is_http_url(url):
        return False
    if not allow_google_news_wrapper and is_google_news_wrapper(url):
        return False
    return True


def url_appears_live(url: str, allow_google_news_wrapper: bool = False, timeout: int = 12) -> bool:
    if not can_publish_url(url, allow_google_news_wrapper=allow_google_news_wrapper):
        return False
    headers = {"User-Agent": "Mozilla/5.0 (compatible; FCMeng-qc-digest/1.0)"}
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True, headers=headers)
        if response.status_code in {405, 403, 429}:
            response = requests.get(url, timeout=timeout, allow_redirects=True, headers=headers, stream=True)
        if is_google_news_wrapper(response.url) and not allow_google_news_wrapper:
            return False
        return response.status_code not in {400, 404, 410} and response.status_code < 500
    except requests.RequestException:
        return False


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


def title_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_title(left), normalize_title(right)).ratio()


def best_candidate_url(item: DigestItem, candidates: Iterable[RawItem]) -> str:
    best = None
    best_score = 0.0
    for candidate in candidates:
        if item.kind == "news" and candidate.source_type != "news":
            continue
        if not can_publish_url(candidate.url):
            continue
        score = title_similarity(item.title, candidate.title)
        if score > best_score:
            best = candidate
            best_score = score
    if best and best_score >= 0.72 and url_appears_live(best.url):
        return best.url
    return ""


def repair_or_drop_bad_news_urls(items: Iterable[DigestItem], candidates: Iterable[RawItem]) -> List[DigestItem]:
    repaired: List[DigestItem] = []
    candidate_list = list(candidates)
    for item in items:
        if item.kind != "news":
            repaired.append(item)
            continue
        if can_publish_url(item.url) and url_appears_live(item.url):
            repaired.append(item)
            continue
        replacement = best_candidate_url(item, candidate_list)
        if replacement:
            item.url = replacement
            repaired.append(item)
        else:
            print("Dropped news item with unusable URL: {}".format(item.title))
    return repaired


def analyze_items(raw_items: List[RawItem], track_config: Dict[str, object], track: str, limit: int = 10) -> List[DigestItem]:
    candidates = balanced_candidates(raw_items, track_config)
    prompt_items = [item.to_prompt_dict(index) for index, item in enumerate(candidates)]

    llm = LLMClient()
    data: Dict[str, object] = llm.analyze_batch(prompt_items, limit=limit, track_config=track_config, track=track)
    digest_items = [DigestItem.from_llm(item, default_track=track) for item in data.get("items", [])]
    digest_items = [item for item in digest_items if item.track == track]
    digest_items = repair_or_drop_bad_news_urls(digest_items, candidates)
    digest_items = deduplicate_digest(digest_items)
    digest_items.sort(key=lambda item: item.score, reverse=True)
    return digest_items[:limit]
