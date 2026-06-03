from datetime import date
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from analyze_items import canonical_url, can_publish_url, normalize_title, title_similarity, url_appears_live
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


def source_links(sources: Iterable[Dict[str, object]]) -> List[Dict[str, str]]:
    links: List[Dict[str, str]] = []
    for source in sources:
        for link in source.get("links", []):
            if isinstance(link, dict) and link.get("title") and link.get("url"):
                links.append({"title": str(link["title"]), "url": str(link["url"])})
    return links


def best_source_link(item: OpportunityItem, links: Iterable[Dict[str, str]]) -> str:
    best_link = ""
    best_score = 0.0
    for link in links:
        url = link.get("url", "")
        if not can_publish_url(url):
            continue
        score = max(
            title_similarity(item.title, link.get("title", "")),
            SequenceMatcher(None, normalize_title(item.url), normalize_title(url)).ratio(),
        )
        if score > best_score:
            best_link = url
            best_score = score
    if best_link and best_score >= 0.62 and url_appears_live(best_link):
        return best_link
    return ""


def repair_or_drop_bad_opportunity_urls(items: Iterable[OpportunityItem], links: Iterable[Dict[str, str]]) -> List[OpportunityItem]:
    repaired: List[OpportunityItem] = []
    link_list = list(links)
    for item in items:
        if can_publish_url(item.url) and url_appears_live(item.url):
            repaired.append(item)
            continue
        replacement = best_source_link(item, link_list)
        if replacement:
            item.url = replacement
            repaired.append(item)
        else:
            print("Dropped opportunity with unusable URL: {}".format(item.title))
    return repaired


def fetch_opportunities(max_items: int = 80) -> List[OpportunityItem]:
    sources = [source for source in (fetch_source_text(source) for source in OPPORTUNITY_SOURCES) if source]
    if not sources:
        return []

    llm = LLMClient()
    data = llm.extract_opportunities(sources=sources, max_items=max_items)
    items = [OpportunityItem.from_llm(item) for item in data.get("items", [])]
    items = repair_or_drop_bad_opportunity_urls(items, source_links(sources))
    return sort_opportunities(items)
