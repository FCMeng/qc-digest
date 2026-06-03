import json
from pathlib import Path
from typing import Iterable, List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from models import DigestItem, utc_now


ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / "site"
TEMPLATE_DIR = ROOT / "templates"
PAGES_URL = "https://fcmeng.github.io/qc-digest/"


def render_site(items: Iterable[DigestItem]) -> Path:
    digest_items: List[DigestItem] = list(items)
    generated_at = utc_now()
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
    html_path = SITE_DIR / "index.html"
    html_path.write_text(
        template.render(
            generated_at=generated_at.strftime("%Y-%m-%d %H:%M UTC"),
            pages_url=PAGES_URL,
            items=digest_items,
            grouped=grouped,
        ),
        encoding="utf-8",
    )

    json_path = SITE_DIR / "digest.json"
    json_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at.isoformat(),
                "pages_url": PAGES_URL,
                "items": [item.__dict__ for item in digest_items],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return html_path
