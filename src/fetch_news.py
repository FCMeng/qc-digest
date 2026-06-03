from datetime import timedelta
from typing import Iterable, List
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from models import RawItem, as_utc, utc_now


DEFAULT_NEWS_QUERIES = [
    "quantum computing",
    "quantum computer",
    "quantum chip",
    "quantum processor",
    "quantum algorithm",
    "quantum cryptography",
]

QUANTUM_KEYWORDS = {
    "quantum",
    "qubit",
    "qpu",
    "superconducting",
    "trapped ion",
    "quantum computer",
    "quantum computing",
    "quantum algorithm",
    "quantum error correction",
}


def google_news_rss_url(query: str) -> str:
    encoded = quote_plus(query)
    return "https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en".format(encoded)


def bing_news_rss_url(query: str) -> str:
    encoded = quote_plus(query)
    return "https://www.bing.com/news/search?q={}&format=rss".format(encoded)


def clean_html(value: str) -> str:
    soup = BeautifulSoup(value or "", "html.parser")
    return " ".join(soup.get_text(" ").split())


def looks_quantum_related(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in QUANTUM_KEYWORDS)


def fetch_news(max_per_query: int = 12, days_back: int = 10, queries: Iterable[str] = None) -> List[RawItem]:
    cutoff = utc_now() - timedelta(days=days_back)
    items: List[RawItem] = []

    for query in queries or DEFAULT_NEWS_QUERIES:
        for feed_url in [bing_news_rss_url(query), google_news_rss_url(query)]:
            response = requests.get(feed_url, timeout=30)
            response.raise_for_status()
            feed = feedparser.parse(response.text)

            for entry in feed.entries[:max_per_query]:
                published = None
                if getattr(entry, "published", None):
                    published = as_utc(date_parser.parse(entry.published))
                if published and published < cutoff:
                    continue

                title = " ".join(getattr(entry, "title", "").split())
                summary = clean_html(getattr(entry, "summary", ""))
                link = getattr(entry, "link", "")
                source = "News RSS"
                if getattr(entry, "source", None) and getattr(entry.source, "title", None):
                    source = entry.source.title

                combined = "{} {}".format(title, summary)
                if not looks_quantum_related(combined):
                    continue

                items.append(
                    RawItem(
                        title=title,
                        url=link,
                        source=source,
                        published=published,
                        raw_text=summary,
                        source_type="news",
                    )
                )

    return items
