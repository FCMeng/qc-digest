import os
from typing import List, Set, Tuple

from analyze_items import analyze_items, canonical_url, normalize_title
from email_digest import missing_smtp_env, send_digest_email
from fetch_arxiv import fetch_arxiv_papers
from fetch_news import fetch_news
from models import RawItem
from render_site import PAGES_URL, load_archive_items, load_archives, render_site
from track_config import TRACKS, TRACK_ORDER


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


def seen_archive_keys(track: str) -> Set[Tuple[str, str]]:
    keys: Set[Tuple[str, str]] = set()
    for archive in load_archives():
        slug = archive.get("slug")
        if not slug:
            continue
        items = load_archive_items(slug, track=track) or []
        for item in items:
            if item.url:
                keys.add(("url", canonical_url(item.url)))
            if item.title:
                keys.add(("title", normalize_title(item.title)))
    return keys


def filter_previous_results(items: List[RawItem], track: str) -> List[RawItem]:
    seen = seen_archive_keys(track)
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


def build_track_digest(track: str, days_back: int) -> List:
    config = TRACKS[track]
    label = config["label"]

    print("Fetching recent {} arXiv papers...".format(label))
    papers: List[RawItem] = fetch_arxiv_papers(
        terms=config["paper_terms"],
        track=track,
        days_back=days_back,
    )
    print("Fetched {} {} arXiv candidates.".format(len(papers), label))

    print("Fetching recent {} news...".format(label))
    news: List[RawItem] = fetch_news(
        queries=config["news_queries"],
        keywords=config["keywords"],
        track=track,
        days_back=days_back,
    )
    print("Fetched {} {} news candidates.".format(len(news), label))

    candidates = filter_previous_results(papers + news, track=track)
    print("Analyzing, classifying, ranking, and summarizing {} with LLM...".format(label))
    digest_items = analyze_items(candidates, track_config=config, track=track, limit=10) if candidates else []
    print("Selected {} {} digest items.".format(len(digest_items), label))
    return digest_items


def main() -> None:
    days_back = fetch_window_days()
    if has_previous_runs():
        print("Previous archive found. Fetching items from the last {} day(s).".format(days_back))
    else:
        print("No previous archive found. Fetching items from the last {} day(s).".format(days_back))

    digest_tracks = {
        track: build_track_digest(track, days_back)
        for track in TRACK_ORDER
    }

    html_path = render_site(digest_tracks)
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
    send_digest_email([item for items in digest_tracks.values() for item in items])
    print("Email sent.")


if __name__ == "__main__":
    main()
