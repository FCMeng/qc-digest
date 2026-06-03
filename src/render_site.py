import json
from pathlib import Path
from typing import Dict, Iterable, List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from models import DigestItem, utc_now


VISIBLE_ARCHIVE_LIMIT = 30
ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / "site"
ARCHIVE_DIR = SITE_DIR / "archive"
ARCHIVE_INDEX = ARCHIVE_DIR / "index.json"
TEMPLATE_DIR = ROOT / "templates"
PAGES_URL = "https://fcmeng.github.io/qc-digest/"


def load_archives() -> List[Dict[str, str]]:
    if not ARCHIVE_INDEX.exists():
        return []
    try:
        data = json.loads(ARCHIVE_INDEX.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    archives = data.get("archives", [])
    if not isinstance(archives, list):
        return []
    return [entry for entry in archives if isinstance(entry, dict) and entry.get("slug")]


def write_archive_index(archives: List[Dict[str, str]]) -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_INDEX.write_text(
        json.dumps({"archives": archives}, indent=2),
        encoding="utf-8",
    )


def archive_display_fields(generated_at) -> Dict[str, str]:
    return {
        "title": generated_at.strftime("%Y-%m-%d %H:%M UTC"),
        "display_time": generated_at.strftime("%H:%M UTC"),
        "display_date": generated_at.strftime("%Y-%m-%d"),
    }


def normalize_archive(entry: Dict[str, str]) -> Dict[str, str]:
    normalized = dict(entry)
    title = normalized.get("title", "")
    if not normalized.get("display_time"):
        parts = title.split()
        normalized["display_time"] = " ".join(parts[1:3]) if len(parts) >= 3 else title
    if not normalized.get("display_date"):
        normalized["display_date"] = title.split()[0] if title else ""
    return normalized


def render_site(items: Iterable[DigestItem]) -> Path:
    digest_items: List[DigestItem] = list(items)
    generated_at = utc_now()
    slug = generated_at.strftime("%Y-%m-%d-%H%M")
    generated_label = generated_at.strftime("%Y-%m-%d %H:%M UTC")
    archive_fields = archive_display_fields(generated_at)
    grouped = {
        "papers": [item for item in digest_items if item.kind == "papers"],
        "news": [item for item in digest_items if item.kind == "news"],
    }

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("index.html.j2")

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    archives = load_archives()
    current_archive = {
        "slug": slug,
        **archive_fields,
        "generated_at": generated_at.isoformat(),
        "url": "{}archive/{}/".format(PAGES_URL, slug),
    }
    archives = [current_archive] + [entry for entry in archives if entry.get("slug") != slug]
    archives.sort(key=lambda entry: entry.get("generated_at", ""), reverse=True)
    archives = [normalize_archive(entry) for entry in archives]
    write_archive_index(archives)
    visible_archives = archives[:VISIBLE_ARCHIVE_LIMIT]
    older_archives = archives[VISIBLE_ARCHIVE_LIMIT:]

    context = {
        "generated_at": generated_label,
        "pages_url": PAGES_URL,
        "items": digest_items,
        "grouped": grouped,
        "archives": archives,
        "visible_archives": visible_archives,
        "older_archives": older_archives,
        "active_archive_slug": slug,
    }

    html_path = SITE_DIR / "index.html"
    html_path.write_text(template.render(**context), encoding="utf-8")

    archive_page_dir = ARCHIVE_DIR / slug
    archive_page_dir.mkdir(parents=True, exist_ok=True)
    archive_page_path = archive_page_dir / "index.html"
    archive_page_path.write_text(template.render(**context), encoding="utf-8")

    json_path = SITE_DIR / "digest.json"
    json_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at.isoformat(),
                "pages_url": PAGES_URL,
                "archive_url": current_archive["url"],
                "items": [item.__dict__ for item in digest_items],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return html_path
