from datetime import date
from typing import Dict, Iterable, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from analyze_items import canonical_url, normalize_title
from llm_client import LLMClient
from models import OpportunityItem
from opportunity_sources import OPPORTUNITY_SOURCES


def fetch_source_text(source: Dict[str, str]) -> Optional[Dict[str, str]]:
    try:
        response = requests.get(
            source["url"],
            timeout=30,
            headers={"User-Agent": "FCMeng-qc-digest/1.0"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print("Opportunity source failed '{}': {}".format(source["name"], exc))
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    links = []
    seen_links = set()
    for anchor in soup.find_all("a", href=True):
        label = " ".join(anchor.get_text(" ").split())
        href = urljoin(source["url"], anchor["href"])
        if not label or href in seen_links:
            continue
        seen_links.add(href)
        links.append({"title": label[:160], "url": href})
        if len(links) >= 120:
            break

    text = " ".join(soup.get_text(" ").split())
    if not text:
        return None
    return {
        "name": source["name"],
        "url": source["url"],
        "topic_hint": source["topic_hint"],
        "text": text[:7000],
        "links": links,
    }


def parse_date(value: Optional[str]):
    if not value:
        return None
    try:
        return date_parser.parse(value, fuzzy=True).date()
    except (TypeError, ValueError, OverflowError):
        return None


def deduplicate_opportunities(items: Iterable[OpportunityItem]) -> List[OpportunityItem]:
    seen = set()
    result: List[OpportunityItem] = []
    for item in items:
        if not item.title or not item.url:
            continue
        keys = {
            ("url", canonical_url(item.url)),
            ("title", normalize_title(item.title)),
        }
        if seen & keys:
            continue
        seen.update(keys)
        result.append(item)
    return result


def sort_opportunities(items: Iterable[OpportunityItem]) -> List[OpportunityItem]:
    today = date.today()
    upcoming = []
    undated = []
    for item in deduplicate_opportunities(items):
        deadline = parse_date(item.deadline)
        if deadline is None:
            undated.append(item)
            continue
        if deadline < today:
            continue
        upcoming.append((deadline, item))

    upcoming.sort(key=lambda pair: pair[0])
    undated.sort(key=lambda item: item.title.lower())
    return [item for _, item in upcoming] + undated


def fetch_opportunities(max_items: int = 80) -> List[OpportunityItem]:
    sources = [source for source in (fetch_source_text(source) for source in OPPORTUNITY_SOURCES) if source]
    if not sources:
        return []

    llm = LLMClient()
    data = llm.extract_opportunities(sources=sources, max_items=max_items)
    items = [OpportunityItem.from_llm(item) for item in data.get("items", [])]
    return sort_opportunities(items)
