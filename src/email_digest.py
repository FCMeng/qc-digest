import os
import smtplib
import json
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable

from models import DigestItem
from render_site import PAGES_URL
from track_config import TRACKS, TRACK_ORDER


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

    grouped = {track: [] for track in TRACK_ORDER}
    for item in items:
        grouped.setdefault(item.track, []).append(item)

    sections = []
    for track in TRACK_ORDER:
        label = TRACKS[track]["label"]
        papers = [item for item in grouped.get(track, []) if item.kind == "papers"]
        news = [item for item in grouped.get(track, []) if item.kind == "news"]
        paper_lines = ["- {}".format(item.title) for item in papers]
        news_lines = ["- {}".format(item.title) for item in news]
        sections.append(
            "{label}:\nPapers:\n{papers}\n\nNews:\n{news}".format(
                label=label,
                papers="\n".join(paper_lines) if paper_lines else "- No papers selected",
                news="\n".join(news_lines) if news_lines else "- No news selected",
            )
        )

    body = """A new research digest is available:

{pages_url}

Selected items:
{items}
""".format(
        pages_url=PAGES_URL,
        items="\n\n".join(sections),
    )

    message = EmailMessage()
    message["Subject"] = "Research Digest"
    message["From"] = os.environ["EMAIL_FROM"]
    recipients = [
        address.strip()
        for address in "{},zhenzhz@clemson.edu,fanchem@clemson.edu".format(os.environ["EMAIL_TO"]).split(",")
        if address.strip()
    ]
    message["To"] = ", ".join(dict.fromkeys(recipients))
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
