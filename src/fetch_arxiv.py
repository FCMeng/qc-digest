import time
from datetime import timedelta
from typing import List
from urllib.parse import urlencode

import feedparser
import requests
from dateutil import parser as date_parser

from models import RawItem, as_utc, utc_now


ARXIV_API = "https://export.arxiv.org/api/query"
REQUEST_HEADERS = {
    "User-Agent": "FCMeng-qc-digest/1.0 (https://github.com/FCMeng/qc-digest)"
}
def build_query(terms: List[str]) -> str:
    return " OR ".join('all:"{}"'.format(term) for term in terms)


def fetch_arxiv_papers(terms: List[str], track: str, max_results: int = 40, days_back: int = 10) -> List[RawItem]:
    params = {
        "search_query": build_query(terms),
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = "{}?{}".format(ARXIV_API, urlencode(params))
    response = None
    for attempt in range(3):
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
        if response.status_code != 429:
            break
        if attempt < 2:
            time.sleep(10 * (attempt + 1))
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
