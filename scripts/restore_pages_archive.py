import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


PAGES_URL = "https://fcmeng.github.io/qc-digest/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
ARCHIVE_DIR = SITE_DIR / "archive"
ARCHIVE_INDEX = ARCHIVE_DIR / "index.json"


def fetch_text(url: str) -> str:
    with urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8")


def restore_archive() -> None:
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
        restored += 1

    print("Restored {} archived run(s).".format(restored))


if __name__ == "__main__":
    restore_archive()
