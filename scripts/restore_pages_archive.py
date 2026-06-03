import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from bs4 import BeautifulSoup


PAGES_URL = "https://fcmeng.github.io/qc-digest/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
ARCHIVE_DIR = SITE_DIR / "archive"
ARCHIVE_INDEX = ARCHIVE_DIR / "index.json"


def fetch_text(url: str) -> str:
    with urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8")


def parse_archived_html(page_text: str, entry: dict) -> dict:
    soup = BeautifulSoup(page_text, "html.parser")
    items = []
    for article in soup.find_all("article"):
        tag = article.find(class_="tag")
        title = article.find("h3")
        link = article.find("a", href=True)
        paragraphs = article.find_all("p")
        meta_spans = article.find_all("span")

        kind = "news"
        if tag and "paper" in tag.get_text(" ", strip=True).lower():
            kind = "papers"

        source = ""
        published_date = None
        score = 0.0
        if len(meta_spans) >= 2:
            source = meta_spans[1].get_text(" ", strip=True)
        for span in meta_spans[2:]:
            value = span.get_text(" ", strip=True)
            if value.lower().startswith("score"):
                try:
                    score = float(value.split()[-1])
                except ValueError:
                    score = 0.0
            elif not published_date:
                published_date = value

        summary = paragraphs[0].get_text(" ", strip=True) if paragraphs else ""
        why_selected = ""
        if len(paragraphs) > 1:
            why_selected = paragraphs[1].get_text(" ", strip=True)
            if why_selected.lower().startswith("why selected:"):
                why_selected = why_selected.split(":", 1)[1].strip()

        if not title or not link:
            continue

        items.append(
            {
                "title": title.get_text(" ", strip=True),
                "kind": kind,
                "source": source,
                "published_date": published_date,
                "url": link["href"],
                "score": score,
                "summary": summary,
                "why_selected": why_selected,
            }
        )

    item_tracks = {"quantum": items, "ai_ml": []}
    return {
        "generated_at": entry.get("generated_at"),
        "pages_url": PAGES_URL,
        "archive_url": entry.get("url"),
        "tracks": item_tracks,
    }


def restore_archive() -> None:
    if os.environ.get("RESET_PUBLISHED_ARCHIVE", "").lower() in {"1", "true", "yes"}:
        print("Archive reset requested; skipping published archive restore.")
        return

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        index_text = fetch_text(PAGES_URL + "archive/index.json")
    except (HTTPError, URLError, TimeoutError):
        print("No published archive found to restore.")
        return

    ARCHIVE_INDEX.write_text(index_text, encoding="utf-8")
    data = json.loads(index_text)
    restored = 0
    for entry in data.get("archives", []):
        slug = entry.get("slug")
        if not slug:
            continue
        try:
            page_text = fetch_text(PAGES_URL + "archive/{}/".format(slug))
        except (HTTPError, URLError, TimeoutError):
            continue
        page_dir = ARCHIVE_DIR / slug
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "index.html").write_text(page_text, encoding="utf-8")
        try:
            digest_text = fetch_text(PAGES_URL + "archive/{}/digest.json".format(slug))
        except (HTTPError, URLError, TimeoutError):
            digest_text = json.dumps(parse_archived_html(page_text, entry), indent=2)
        (page_dir / "digest.json").write_text(digest_text, encoding="utf-8")
        restored += 1

    print("Restored {} archived run(s).".format(restored))


if __name__ == "__main__":
    restore_archive()
