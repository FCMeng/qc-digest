import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OWNER = "FCMeng"
REPO = "qc-digest"


def github_request(url: str, method: str = "GET"):
    token = os.environ["GITHUB_TOKEN"]
    request = Request(
        url,
        method=method,
        headers={
            "Authorization": "Bearer {}".format(token),
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def main() -> None:
    current_run_id = str(os.environ.get("GITHUB_RUN_ID", ""))
    url = "https://api.github.com/repos/{}/{}/actions/runs?per_page=100".format(OWNER, REPO)
    data = github_request(url)
    deleted = 0
    blocked = 0
    for run in data.get("workflow_runs", []):
        run_id = str(run.get("id"))
        if not run_id or run_id == current_run_id:
            continue
        try:
            github_request(
                "https://api.github.com/repos/{}/{}/actions/runs/{}".format(OWNER, REPO, run_id),
                method="DELETE",
            )
            deleted += 1
        except (HTTPError, URLError, TimeoutError) as exc:
            print("Could not delete workflow run {}: {}".format(run_id, exc))
            blocked += 1

    print("Deleted {} workflow run(s); {} deletion(s) blocked.".format(deleted, blocked))


if __name__ == "__main__":
    main()
