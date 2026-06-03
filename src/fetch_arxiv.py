import time
from datetime import timedelta
from typing import List
from urllib.parse import urlencode

import feedparser
import requests
from requests import RequestException
from dateutil import parser as date_parser

from models import RawItem, as_utc, utc_now


ARXIV_API = "https://export.arxiv.org/api/query"
REQUEST_HEADERS = {
    "User-Agent": "FCMeng-qc-digest/1.0 (https://github.com/FCMeng/qc-digest)"
}
def build_query(term: str) -> str:
    return 'all:"{}"'.format(term)


def fetch_arxiv_term(term: str, track: str, max_results: int, days_back: int) -> List[RawItem]:
    params = {
        "search_query": build_query(term),
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = "{}?{}".format(ARXIV_API, urlencode(params))
    response = None
    for attempt in range(3):
        try:
            response = requests.get(url, headers=REQUEST_HEADERS, timeout=45)
            if response.status_code != 429:
                break
        except RequestException as exc:
            print("arXiv request failed for '{}': {}".format(term, exc))
            response = None
        if attempt < 2:
            time.sleep(10 * (attempt + 1))
    if response is None:
        return []
    if response.status_code == 429:
        print("arXiv rate-limited term '{}'; skipping.".format(term))
        return []
    response.raise_for_status()

    cutoff = utc_now() - timedelta(days=days_back)
    feed = feedparser.parse(response.text)
    items: List[RawItem] = []

    for entry in feed.entries:
        published = None
        if getattr(entry, "published", None):
            published = as_utc(date_parser.parse(entry.published))
        if published and published < cutoff:
            continue

        authors = [author.name for author in getattr(entry, "authors", []) if getattr(author, "name", None)]
        title = " ".join(getattr(entry, "title", "").split())
        summary = " ".join(getattr(entry, "summary", "").split())
        link = getattr(entry, "link", "")
        source = "arXiv"

        items.append(
            RawItem(
                title=title,
                url=link,
                source=source,
                published=published,
                raw_text=summary,
                source_type="arxiv",
                track=track,
                authors=authors,
            )
        )

    return items


def fetch_arxiv_papers(terms: List[str], track: str, max_results: int = 40, days_back: int = 10) -> List[RawItem]:
    per_term = max(6, min(12, max_results // max(1, len(terms)) + 3))
    items: List[RawItem] = []
    seen = set()

    for index, term in enumerate(terms):
        if index:
            time.sleep(3)
        for item in fetch_arxiv_term(term, track=track, max_results=per_term, days_back=days_back):
            key = item.url or item.title.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
            if len(items) >= max_results:
                return items

    return items
