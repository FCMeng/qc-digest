import json
import os
from typing import Any, Dict, List

from openai import OpenAI


DEFAULT_MODEL = "gpt-5-mini"


class LLMClient:
    def __init__(self, model: str = None) -> None:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required for LLM analysis.")
        self.client = OpenAI()
        self.model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)

    def analyze_batch(self, candidates: List[Dict[str, Any]], limit: int, track_config: Dict[str, Any], track: str) -> Dict[str, Any]:
        system_prompt = (
            "You are an expert {}. ".format(track_config["expert_role"]) +
            "Classify candidate items as papers or news, reject irrelevant or duplicate items, "
            "rank by importance to a research-oriented reader, categorize papers, and summarize accurately. "
            "Return only JSON that matches the requested schema."
        )
        user_prompt = {
            "task": track_config["task"],
            "instructions": [
                "Only include items genuinely related to this track.",
                "Classify arXiv/manuscript items as papers and journalism/company/government/reporting items as news.",
                "For every paper, choose exactly one category from the allowed paper categories.",
                "For news, use category null.",
                "Prefer recent, technically meaningful, or high-impact items.",
                "Write each summary in 2-3 concise sentences.",
                "Use the original URL from the candidate item.",
                "Return at most {} selected items.".format(limit),
            ],
            "track": track,
            "allowed_paper_categories": track_config["categories"],
            "candidates": candidates,
        }

        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt)},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "quantum_digest",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "title": {"type": "string"},
                                        "track": {"type": "string", "enum": ["quantum", "ai_ml"]},
                                        "kind": {"type": "string", "enum": ["papers", "news"]},
                                        "category": {"type": ["string", "null"]},
                                        "source": {"type": "string"},
                                        "published_date": {"type": ["string", "null"]},
                                        "url": {"type": "string"},
                                        "score": {"type": "number"},
                                        "summary": {"type": "string"},
                                        "why_selected": {"type": "string"},
                                    },
                                    "required": [
                                        "title",
                                        "track",
                                        "kind",
                                        "category",
                                        "source",
                                        "published_date",
                                        "url",
                                        "score",
                                        "summary",
                                        "why_selected",
                                    ],
                                },
                            }
                        },
                        "required": ["items"],
                    },
                }
            },
        )
        return json.loads(response.output_text)
