import os
import smtplib
import json
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, Iterable, List

from models import DigestItem, OpportunityItem
from render_site import PAGES_URL
from track_config import DIGEST_TRACK_ORDER, TRACKS


FIXED_RECIPIENTS = ["fanchem@g.clemson.edu", "zhenzhz@g.clemson.edu"]
REQUIRED_SMTP_ENV = [
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "EMAIL_FROM",
]


def missing_smtp_env() -> list:
    return [name for name in REQUIRED_SMTP_ENV if not os.environ.get(name)]


def opportunity_sort_key(item: OpportunityItem) -> str:
    return item.deadline or "9999-12-31"


def format_digest_section(label: str, items: Iterable[DigestItem]) -> str:
    items = list(items)
    papers = [item for item in items if item.kind == "papers"]
    news = [item for item in items if item.kind == "news"]
    paper_lines = ["- {}".format(item.title) for item in papers]
    news_lines = ["- {}".format(item.title) for item in news]
    return "{label}:\nPapers:\n{papers}\n\nNews:\n{news}".format(
        label=label,
        papers="\n".join(paper_lines) if paper_lines else "- No papers selected",
        news="\n".join(news_lines) if news_lines else "- No news selected",
    )


def format_opportunity_section(items: Iterable[OpportunityItem]) -> str:
    grouped = {"AI/ML": [], "Quantum": []}
    for item in items:
        grouped.setdefault(item.topic_tag, []).append(item)

    sections = ["Opportunities:"]
    for topic in ["AI/ML", "Quantum"]:
        sorted_items = sorted(grouped.get(topic, []), key=opportunity_sort_key)
        lines = [
            "- {title} ({event}; deadline {deadline})".format(
                title=item.title,
                event=item.event_tag,
                deadline=item.deadline or "unknown",
            )
            for item in sorted_items
        ]
        sections.append("{}:\n{}".format(topic, "\n".join(lines) if lines else "- No opportunities selected"))
    return "\n\n".join(sections)


def send_digest_email(tracks: Dict[str, List]) -> None:
    missing = missing_smtp_env()
    if missing:
        raise RuntimeError("Missing SMTP environment variables: {}".format(", ".join(missing)))

    sections = []
    for track in DIGEST_TRACK_ORDER:
        label = TRACKS[track]["label"]
        sections.append(format_digest_section(label, tracks.get(track, [])))
    sections.append(format_opportunity_section(tracks.get("opportunities", [])))

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
    message["To"] = ", ".join(FIXED_RECIPIENTS)
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
    tracks = load_tracks_from_site()
    items = []
    for track in DIGEST_TRACK_ORDER:
        items.extend(tracks.get(track, []))
    return items


def load_tracks_from_site() -> Dict[str, List]:
    digest_path = Path(__file__).resolve().parents[1] / "site" / "digest.json"
    data = json.loads(digest_path.read_text(encoding="utf-8"))
    tracks = data.get("tracks", {})
    result = {}
    for track, track_items in tracks.items():
        if track == "opportunities":
            result[track] = [OpportunityItem.from_llm(item) for item in track_items]
        else:
            result[track] = [DigestItem.from_llm(item, default_track=track) for item in track_items]
    return result


def main() -> None:
    send_digest_email(load_tracks_from_site())
    print("Email sent with Pages link: {}".format(PAGES_URL))


if __name__ == "__main__":
    main()
