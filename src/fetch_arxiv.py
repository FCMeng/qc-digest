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
ARXIV_RSS = "https://rss.arxiv.org/rss/{}"
REQUEST_HEADERS = {
    "User-Agent": "FCMeng-qc-digest/1.0 (https://github.com/FCMeng/qc-digest)"
}
def build_query(term: str) -> str:
    return 'all:"{}"'.format(term)


def fetch_arxiv_query(search_query: str, track: str, max_results: int, days_back: int) -> List[RawItem]:
    params = {
        "search_query": search_query,
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
            print("arXiv request failed for '{}': {}".format(search_query, exc))
            response = None
        if attempt < 2:
            time.sleep(10 * (attempt + 1))
    if response is None:
        return []
    if response.status_code == 429:
        print("arXiv rate-limited query '{}'; skipping.".format(search_query))
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


def entry_datetime(entry):
    value = getattr(entry, "published", None) or getattr(entry, "updated", None)
    return as_utc(date_parser.parse(value)) if value else None


def fetch_arxiv_rss(categories: List[str], terms: List[str], track: str, max_results: int, days_back: int, filter_terms: bool = False) -> List[RawItem]:
    cutoff = utc_now() - timedelta(days=days_back)
    terms_lower = [term.lower() for term in terms]
    items: List[RawItem] = []
    seen = set()

    for category in categories:
        feed = feedparser.parse(ARXIV_RSS.format(category))
        for entry in feed.entries:
            published = entry_datetime(entry)
            if published and published < cutoff:
                continue

            title = " ".join(getattr(entry, "title", "").split())
            summary = " ".join(getattr(entry, "summary", "").split())
            combined = "{} {}".format(title, summary).lower()
            if filter_terms and terms_lower and not any(term in combined for term in terms_lower):
                continue

            link = getattr(entry, "link", "")
            key = link or title.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(
                RawItem(
                    title=title,
                    url=link,
                    source="arXiv",
                    published=published,
                    raw_text=summary,
                    source_type="arxiv",
                    track=track,
                )
            )
            if len(items) >= max_results:
                return items

    return items


def fetch_arxiv_papers(terms: List[str], track: str, max_results: int = 50, days_back: int = 10, arxiv_query: str = None, rss_categories: List[str] = None) -> List[RawItem]:
    search_query = arxiv_query or " OR ".join(build_query(term) for term in terms)
    items = fetch_arxiv_query(search_query, track=track, max_results=max_results, days_back=days_back)
    if items or not rss_categories:
        return items
    print("Falling back to arXiv RSS for {}.".format(track))
    return fetch_arxiv_rss(rss_categories, terms=terms, track=track, max_results=max_results, days_back=days_back)
