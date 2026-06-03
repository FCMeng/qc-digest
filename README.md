# Quantum Computing Digest

Automated GitHub Actions pipeline for user `FCMeng` that fetches recent quantum computing papers and news, analyzes them with an OpenAI LLM, publishes the top 10 items to GitHub Pages, and emails the Pages link.

Published site:

```text
https://fcmeng.github.io/qc-digest/
```

## What It Does

- Runs every 3 days via GitHub Actions.
- Fetches recent arXiv papers related to quantum computing.
- Fetches recent news from public Google News RSS search feeds.
- Uses an OpenAI LLM to classify candidates as `papers` or `news`.
- Uses the LLM to filter, rank, and summarize the best items.
- Publishes `site/index.html` to GitHub Pages.
- Deploys the site to GitHub Pages, then sends an SMTP email with the Pages link and selected titles.

## Repository Structure

```text
.github/workflows/digest.yml  GitHub Actions workflow
src/fetch_arxiv.py            arXiv Atom API fetcher
src/fetch_news.py             RSS news fetcher
src/llm_client.py             OpenAI Responses API wrapper
src/analyze_items.py          deduplication, LLM classification, ranking
src/render_site.py            static GitHub Pages renderer
src/email_digest.py           SMTP email sender
src/run_digest.py             end-to-end pipeline entry point
templates/index.html.j2       HTML template
site/.gitkeep                 Pages output directory placeholder
requirements.txt              Python dependencies
```

## Required GitHub Secrets

Repository secrets are encrypted by GitHub and are not committed to the repository.

Create these under:

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

Required secrets:

```text
OPENAI_API_KEY
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
EMAIL_FROM
EMAIL_TO
```

For Gmail SMTP, use a Gmail app password rather than your normal account password:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-address@gmail.com
SMTP_PASSWORD=your-gmail-app-password
EMAIL_FROM=your-address@gmail.com
EMAIL_TO=destination@example.com
```

## Optional GitHub Variable

Create this under:

```text
Settings -> Secrets and variables -> Actions -> Variables
```

```text
OPENAI_MODEL
```

Default:

```text
gpt-5-mini
```

For higher-quality analysis, set:

```text
gpt-5
```

## GitHub Pages Setup

1. Create a GitHub repository named `qc-digest` under user `FCMeng`.
2. Push this repository to GitHub.
3. Open the repository on GitHub.
4. Go to `Settings -> Pages`.
5. Set `Source` to `GitHub Actions`.
6. Save.

The workflow deploys the generated `site/` directory to:

```text
https://fcmeng.github.io/qc-digest/
```

## Running Locally

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set at least the OpenAI API key:

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-5-mini"
```

Run the pipeline:

```bash
python src/run_digest.py
```

If SMTP environment variables are missing locally, the script still generates `site/index.html` and skips email. In GitHub Actions, the workflow deploys Pages first and then sends email; missing SMTP secrets cause the email step to fail.

## Manual Workflow Run

1. Open the repository on GitHub.
2. Go to `Actions`.
3. Select `Quantum Computing Digest`.
4. Click `Run workflow`.
5. After it completes, open the Pages URL and check your email.

## Schedule

The workflow schedule is:

```yaml
0 14 */3 * *
```

This runs at 14:00 UTC every 3 days.

## Notes

- Do not print secrets or environment variables in workflow logs.
- `site/index.html` and `site/digest.json` are generated files and are ignored by Git.
- The workflow uses public RSS feeds for news, so no news API key is required.
