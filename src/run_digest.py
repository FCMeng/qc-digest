import os
from typing import List, Set, Tuple

from analyze_items import analyze_items, canonical_url, normalize_title
from email_digest import missing_smtp_env, send_digest_email
from fetch_arxiv import fetch_arxiv_papers
from fetch_news import fetch_news
from models import RawItem
from render_site import PAGES_URL, load_archive_items, load_archives, render_site


def is_github_actions() -> bool:
    return os.environ.get("GITHUB_ACTIONS", "").lower() == "true"


def should_skip_email() -> bool:
    return os.environ.get("SKIP_EMAIL", "").lower() in {"1", "true", "yes"}


def digest_interval_days() -> int:
    raw_value = os.environ.get("DIGEST_INTERVAL_DAYS", "3")
    try:
        value = int(raw_value)
    except ValueError:
        raise RuntimeError("DIGEST_INTERVAL_DAYS must be an integer.")
    if value < 1:
        raise RuntimeError("DIGEST_INTERVAL_DAYS must be at least 1.")
    return value


def has_previous_runs() -> bool:
    return os.path.exists(os.path.join("site", "archive", "index.json"))


def fetch_window_days() -> int:
    if has_previous_runs():
        return digest_interval_days()
    return int(os.environ.get("FIRST_RUN_DAYS_BACK", "10"))


def seen_archive_keys() -> Set[Tuple[str, str]]:
    keys: Set[Tuple[str, str]] = set()
    for archive in load_archives():
        slug = archive.get("slug")
        if not slug:
            continue
        items = load_archive_items(slug) or []
        for item in items:
            if item.url:
                keys.add(("url", canonical_url(item.url)))
            if item.title:
                keys.add(("title", normalize_title(item.title)))
    return keys


def filter_previous_results(items: List[RawItem]) -> List[RawItem]:
    seen = seen_archive_keys()
    if not seen:
        return items

    filtered: List[RawItem] = []
    skipped = 0
    for item in items:
        item_keys = {
            ("url", canonical_url(item.url)),
            ("title", normalize_title(item.title)),
        }
        if item_keys & seen:
            skipped += 1
            continue
        filtered.append(item)

    print("Skipped {} candidate(s) already shown in previous runs.".format(skipped))
    return filtered


def main() -> None:
    days_back = fetch_window_days()
    if has_previous_runs():
        print("Previous archive found. Fetching items from the last {} day(s).".format(days_back))
    else:
        print("No previous archive found. Fetching items from the last {} day(s).".format(days_back))

    print("Fetching recent arXiv papers...")
    papers: List[RawItem] = fetch_arxiv_papers(days_back=days_back)
    print("Fetched {} arXiv candidates.".format(len(papers)))

    print("Fetching recent news...")
    news: List[RawItem] = fetch_news(days_back=days_back)
    print("Fetched {} news candidates.".format(len(news)))

    candidates = filter_previous_results(papers + news)
    print("Analyzing, classifying, ranking, and summarizing with LLM...")
    digest_items = analyze_items(candidates, limit=10) if candidates else []
    print("Selected {} digest items.".format(len(digest_items)))

    html_path = render_site(digest_items)
    print("Rendered {}".format(html_path))
    print("Pages URL: {}".format(PAGES_URL))

    if should_skip_email():
        print("Skipping email because SKIP_EMAIL is set.")
        return

    missing_email = missing_smtp_env()
    if missing_email and not is_github_actions():
        print("Skipping email locally because SMTP env vars are missing: {}".format(", ".join(missing_email)))
        return

    print("Sending digest email...")
    send_digest_email(digest_items)
    print("Email sent.")


if __name__ == "__main__":
    main()
