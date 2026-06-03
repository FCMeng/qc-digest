import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from models import DigestItem, utc_now
from track_config import TRACKS, TRACK_ORDER


VISIBLE_ARCHIVE_LIMIT = 30
DISPLAY_TZ = ZoneInfo("America/New_York")
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


def digest_payload(generated_at: str, pages_url: str, archive_url: str, tracks: Dict[str, List[DigestItem]]) -> Dict:
    return {
        "generated_at": generated_at,
        "pages_url": pages_url,
        "archive_url": archive_url,
        "tracks": {
            track: [item.__dict__ for item in items]
            for track, items in tracks.items()
        },
    }


def write_digest_json(path: Path, payload: Dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_archive_tracks(slug: str) -> Optional[Dict[str, List[DigestItem]]]:
    digest_path = ARCHIVE_DIR / slug / "digest.json"
    if not digest_path.exists():
        return None
    try:
        data = json.loads(digest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    tracks = data.get("tracks")
    if isinstance(tracks, dict):
        return {
            track: [DigestItem.from_llm(item, default_track=track) for item in items]
            for track, items in tracks.items()
            if isinstance(items, list)
        }

    legacy_items = data.get("items", [])
    if isinstance(legacy_items, list):
        restored = {track: [] for track in TRACK_ORDER}
        for item in legacy_items:
            digest_item = DigestItem.from_llm(item)
            restored.setdefault(digest_item.track, []).append(digest_item)
        return restored

    return None


def load_archive_items(slug: str, track: str = None) -> Optional[List[DigestItem]]:
    tracks = load_archive_tracks(slug)
    if tracks is None:
        return None
    if track:
        return tracks.get(track, [])
    items: List[DigestItem] = []
    for track_items in tracks.values():
        items.extend(track_items)
    return items


def as_display_time(value: datetime) -> datetime:
    return value.astimezone(DISPLAY_TZ)


def parse_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def archive_display_fields(generated_at: datetime) -> Dict[str, str]:
    display_time = as_display_time(generated_at)
    return {
        "title": display_time.strftime("%Y-%m-%d %H:%M %Z"),
        "display_time": display_time.strftime("%H:%M %Z"),
        "display_date": display_time.strftime("%Y-%m-%d"),
    }


def normalize_archive(entry: Dict[str, str]) -> Dict[str, str]:
    normalized = dict(entry)
    generated_at = parse_datetime(str(normalized.get("generated_at", "")))
    if generated_at:
        normalized.update(archive_display_fields(generated_at))
        return normalized

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


def build_track_sections(tracks: Dict[str, List[DigestItem]]) -> List[Dict[str, object]]:
    return [
        {
            "key": track,
            "label": TRACKS[track]["label"],
            "items": tracks.get(track, []),
            "grouped": grouped_items(tracks.get(track, [])),
        }
        for track in TRACK_ORDER
    ]


def render_digest_page(template, path: Path, tracks: Dict[str, List[DigestItem]], generated_label: str, archives: List[Dict[str, str]], active_slug: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    item_count = sum(len(items) for items in tracks.values())
    context = {
        "generated_at": generated_label,
        "pages_url": PAGES_URL,
        "item_count": item_count,
        "track_sections": build_track_sections(tracks),
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
        tracks = load_archive_tracks(slug)
        if tracks is None:
            continue
        generated_label = archive.get("title") or archive.get("generated_at", "")
        render_digest_page(
            template,
            ARCHIVE_DIR / slug / "index.html",
            tracks,
            generated_label,
            archives,
            slug,
        )


def render_site(tracks: Dict[str, Iterable[DigestItem]]) -> Path:
    digest_tracks: Dict[str, List[DigestItem]] = {
        track: list(tracks.get(track, []))
        for track in TRACK_ORDER
    }
    generated_at = utc_now()
    slug = generated_at.strftime("%Y-%m-%d-%H%M")
    archive_fields = archive_display_fields(generated_at)
    generated_label = archive_fields["title"]

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
    render_digest_page(template, html_path, digest_tracks, generated_label, archives, slug)

    archive_page_dir = ARCHIVE_DIR / slug
    archive_page_dir.mkdir(parents=True, exist_ok=True)
    payload = digest_payload(generated_at.isoformat(), PAGES_URL, current_archive["url"], digest_tracks)
    write_digest_json(SITE_DIR / "digest.json", payload)
    write_digest_json(archive_page_dir / "digest.json", payload)
    render_all_archive_pages(template, archives)
    return html_path
