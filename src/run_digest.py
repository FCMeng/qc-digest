import os
from typing import List

from analyze_items import analyze_items
from email_digest import missing_smtp_env, send_digest_email
from fetch_arxiv import fetch_arxiv_papers
from fetch_news import fetch_news
from models import RawItem
from render_site import PAGES_URL, render_site


def is_github_actions() -> bool:
    return os.environ.get("GITHUB_ACTIONS", "").lower() == "true"


def should_skip_email() -> bool:
    return os.environ.get("SKIP_EMAIL", "").lower() in {"1", "true", "yes"}


def main() -> None:
    print("Fetching recent arXiv papers...")
    papers: List[RawItem] = fetch_arxiv_papers()
    print("Fetched {} arXiv candidates.".format(len(papers)))

    print("Fetching recent news...")
    news: List[RawItem] = fetch_news()
    print("Fetched {} news candidates.".format(len(news)))

    print("Analyzing, classifying, ranking, and summarizing with LLM...")
    digest_items = analyze_items(papers + news, limit=10)
    print("Selected {} digest items.".format(len(digest_items)))

    html_path = render_site(digest_items)
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
    send_digest_email(digest_items)
    print("Email sent.")


if __name__ == "__main__":
    main()
