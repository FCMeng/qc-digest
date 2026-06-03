import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

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


def digest_payload(generated_at: str, pages_url: str, archive_url: str, items: List[DigestItem]) -> Dict:
    return {
        "generated_at": generated_at,
        "pages_url": pages_url,
        "archive_url": archive_url,
        "items": [item.__dict__ for item in items],
    }


def write_digest_json(path: Path, payload: Dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_archive_items(slug: str) -> Optional[List[DigestItem]]:
    digest_path = ARCHIVE_DIR / slug / "digest.json"
    if not digest_path.exists():
        return None
    try:
        data = json.loads(digest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    items = data.get("items", [])
    if not isinstance(items, list):
        return None
    return [DigestItem.from_llm(item) for item in items]


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


def grouped_items(items: List[DigestItem]) -> Dict[str, List[DigestItem]]:
    return {
        "papers": [item for item in items if item.kind == "papers"],
        "news": [item for item in items if item.kind == "news"],
    }


def render_digest_page(template, path: Path, items: List[DigestItem], generated_label: str, archives: List[Dict[str, str]], active_slug: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    context = {
        "generated_at": generated_label,
        "pages_url": PAGES_URL,
        "items": items,
        "grouped": grouped_items(items),
        "archives": archives,
        "visible_archives": archives[:VISIBLE_ARCHIVE_LIMIT],
        "older_archives": archives[VISIBLE_ARCHIVE_LIMIT:],
        "active_archive_slug": active_slug,
    }
    path.write_text(template.render(**context), encoding="utf-8")


def render_all_archive_pages(template, archives: List[Dict[str, str]]) -> None:
    for archive in archives:
        slug = archive.get("slug")
        if not slug:
            continue
        items = load_archive_items(slug)
        if items is None:
            continue
        generated_label = archive.get("title") or archive.get("generated_at", "")
        render_digest_page(
            template,
            ARCHIVE_DIR / slug / "index.html",
            items,
            generated_label,
            archives,
            slug,
        )


def render_site(items: Iterable[DigestItem]) -> Path:
    digest_items: List[DigestItem] = list(items)
    generated_at = utc_now()
    slug = generated_at.strftime("%Y-%m-%d-%H%M")
    generated_label = generated_at.strftime("%Y-%m-%d %H:%M UTC")
    archive_fields = archive_display_fields(generated_at)

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

    html_path = SITE_DIR / "index.html"
    render_digest_page(template, html_path, digest_items, generated_label, archives, slug)

    archive_page_dir = ARCHIVE_DIR / slug
    archive_page_dir.mkdir(parents=True, exist_ok=True)
    payload = digest_payload(generated_at.isoformat(), PAGES_URL, current_archive["url"], digest_items)
    write_digest_json(SITE_DIR / "digest.json", payload)
    write_digest_json(archive_page_dir / "digest.json", payload)
    render_all_archive_pages(template, archives)
    return html_path
