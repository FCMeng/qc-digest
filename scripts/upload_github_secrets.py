import base64
import json
import os
import subprocess
import sys

from nacl import encoding, public


OWNER = "FCMeng"
REPO = "qc-digest"
SECRET_NAMES = [
    "OPENAI_API_KEY",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "EMAIL_FROM",
    "EMAIL_TO",
]


def curl_json(args):
    return subprocess.check_output(args, text=True)


def main() -> int:
    token = os.environ["GITHUB_TOKEN"]
    headers = [
        "-H",
        "Authorization: Bearer {}".format(token),
        "-H",
        "Accept: application/vnd.github+json",
        "-H",
        "X-GitHub-Api-Version: 2022-11-28",
    ]

    key_raw = curl_json(
        [
            "curl",
            "-sS",
            *headers,
            "https://api.github.com/repos/{}/{}/actions/secrets/public-key".format(OWNER, REPO),
        ]
    )
    key = json.loads(key_raw)
    public_key = public.PublicKey(key["key"].encode("utf-8"), encoding.Base64Encoder)
    sealed_box = public.SealedBox(public_key)

    failures = []
    for name in SECRET_NAMES:
        value = os.environ.get(name)
        if not value:
            failures.append((name, "missing"))
            continue

        encrypted = base64.b64encode(sealed_box.encrypt(value.encode("utf-8"))).decode("utf-8")
        payload = json.dumps({"encrypted_value": encrypted, "key_id": key["key_id"]})
        status = subprocess.check_output(
            [
                "curl",
                "-sS",
                "-o",
                "/tmp/qc-secret-response.json",
                "-w",
                "%{http_code}",
                "-X",
                "PUT",
                *headers,
                "https://api.github.com/repos/{}/{}/actions/secrets/{}".format(OWNER, REPO, name),
                "-d",
                payload,
            ],
            text=True,
        )
        if status not in ("201", "204"):
            failures.append((name, status))

    if failures:
        print(
            "secret upload failures: {}".format(
                ", ".join("{}:{}".format(name, status) for name, status in failures)
            )
        )
        return 1

    print("uploaded secrets: {}".format(", ".join(SECRET_NAMES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
