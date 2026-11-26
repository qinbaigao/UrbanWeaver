"""Bounded semantic reference selection; never replaces the user's CitySpec."""
from dataclasses import asdict
import hashlib
import json
import time

from cityg.agents.requirement import AgentAttempt, AgentGenerationError, _parse_json_object
from cityg.services.interfaces import ChatMessage


def select_reference(agent, requirement, library, *, max_attempts=2):
    catalog = [{"id": key, "intent": row["intent"], "spec": row["spec"],
                "review_status": row["review"]["status"]}
               for key, row in library.records.items() if row["review"]["status"] != "needs_revision"]
    ids = [row["id"] for row in catalog]
    schema = {"type": "object", "additionalProperties": False,
              "properties": {"prototype_id": {"type": "string", "enum": ["none", *ids]},
                             "reason": {"type": "string"}},
              "required": ["prototype_id", "reason"]}
    messages = [ChatMessage("system", "Select one urban layout reference for CityG, or none if incompatible. "
        "References are semantic priors, not fixed city sizes or approved templates. User requirements "
        "take precedence over their sample counts, heights and functions. Do not invent IDs. Return JSON."),
        ChatMessage("user", json.dumps({"requirement": requirement, "catalog": catalog}, ensure_ascii=False))]
    attempts = []
    for index in range(max_attempts):
        started = time.monotonic(); raw = ""; usage = {}; finish = None; error = None
        try:
            method = getattr(agent.service, "complete_with_metadata", None)
            if callable(method):
                completion = method(messages, schema)
                raw, usage, finish = completion.content, completion.usage, completion.finish_reason
            else:
                raw = agent.service.complete(messages, schema)
            if finish == "length":
                raise ValueError("Incomplete reference selection")
            choice = _parse_json_object(raw)
            if (set(choice) != {"prototype_id", "reason"} or choice["prototype_id"] not in ["none", *ids]
                    or not isinstance(choice["reason"], str) or not choice["reason"].strip()):
                raise ValueError("Invalid reference selection")
        except (ValueError, TypeError, RuntimeError) as exc:
            error = str(exc)
        serialized = tuple({"role": m.role, "content": m.content} for m in messages)
        attempts.append(AgentAttempt(index+1, hashlib.sha256(json.dumps(serialized).encode()).hexdigest(),
                                     serialized, raw, time.monotonic()-started, error, finish, usage))
        if error is None:
            return {**choice, "candidates": ids, "attempts": [asdict(a) for a in attempts],
                    "selection_mode": "llm_semantic_reference"}, tuple(attempts)
        messages.extend([ChatMessage("assistant", raw[:8000]), ChatMessage("user", "Rejected: "+error)])
    raise AgentGenerationError("Urban reference selection failed", attempts)
