import json
import os
from datetime import date
from typing import Any, Dict, List

from openai import OpenAI


DEFAULT_MODEL = "gpt-5.4-mini"


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
                "If paper candidates are available, include several strong papers in the final selection rather than selecting only news.",
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

    def extract_opportunities(self, sources: List[Dict[str, Any]], max_items: int) -> Dict[str, Any]:
        system_prompt = (
            "You extract upcoming AI/ML and quantum computing workshops, conferences, tutorials, "
            "schools, and application-based opportunities from source text. Return only valid JSON."
        )
        user_prompt = {
            "task": "Extract upcoming opportunities and normalize their metadata.",
            "current_date": date.today().isoformat(),
            "instructions": [
                "Include only opportunities related to AI/ML or quantum computing/information.",
                "Include workshops, conferences, tutorials, schools, summer schools, or application-based events.",
                "Use deadline for submission, application, registration, or abstract deadline when available.",
                "Represent deadline and event_date as ISO YYYY-MM-DD strings when known; otherwise null.",
                "Exclude expired opportunities if the source text makes it clear they are expired.",
                "Use the most specific original URL available; if unavailable, use the source URL.",
                "Deduplicate obvious repeated entries.",
                "Return at most {} items.".format(max_items),
            ],
            "sources": sources,
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
                    "name": "research_opportunities",
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
                                        "url": {"type": "string"},
                                        "deadline": {"type": ["string", "null"]},
                                        "event_date": {"type": ["string", "null"]},
                                        "topic_tag": {"type": "string", "enum": ["AI/ML", "Quantum"]},
                                        "event_tag": {
                                            "type": "string",
                                            "enum": ["Workshop", "Conference", "Tutorial", "School"],
                                        },
                                        "summary": {"type": "string"},
                                    },
                                    "required": [
                                        "title",
                                        "url",
                                        "deadline",
                                        "event_date",
                                        "topic_tag",
                                        "event_tag",
                                        "summary",
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
