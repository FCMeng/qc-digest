import os
import smtplib
import json
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable

from models import DigestItem
from render_site import PAGES_URL


REQUIRED_SMTP_ENV = [
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "EMAIL_FROM",
    "EMAIL_TO",
]


def missing_smtp_env() -> list:
    return [name for name in REQUIRED_SMTP_ENV if not os.environ.get(name)]


def send_digest_email(items: Iterable[DigestItem]) -> None:
    missing = missing_smtp_env()
    if missing:
        raise RuntimeError("Missing SMTP environment variables: {}".format(", ".join(missing)))

    item_lines = ["- {}".format(item.title) for item in items]
    body = """A new quantum computing digest is available:

{pages_url}

Selected items:
{items}
""".format(
        pages_url=PAGES_URL,
        items="\n".join(item_lines) if item_lines else "- No items selected",
    )

    message = EmailMessage()
    message["Subject"] = "Quantum Computing Digest"
    message["From"] = os.environ["EMAIL_FROM"]
    message["To"] = os.environ["EMAIL_TO"]
    message.set_content(body)

    host = os.environ["SMTP_HOST"]
    port = int(os.environ["SMTP_PORT"])
    username = os.environ["SMTP_USERNAME"]
    password = os.environ["SMTP_PASSWORD"]

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(message)


def load_items_from_site() -> list:
    digest_path = Path(__file__).resolve().parents[1] / "site" / "digest.json"
    data = json.loads(digest_path.read_text(encoding="utf-8"))
    if isinstance(data.get("tracks"), dict):
        items = []
        for track, track_items in data["tracks"].items():
            items.extend(DigestItem.from_llm(item, default_track=track) for item in track_items)
        return items
    return [DigestItem.from_llm(item) for item in data.get("items", [])]


def main() -> None:
    send_digest_email(load_items_from_site())
    print("Email sent with Pages link: {}".format(PAGES_URL))


if __name__ == "__main__":
    main()
