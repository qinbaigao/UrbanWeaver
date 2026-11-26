"""Focused interpretation of route endpoints before the city design call."""
import hashlib
import json
import re
import time
from copy import deepcopy

from cityg.services.interfaces import ChatMessage
from cityg.walking_requirements import response_schema, validate


def extract_walks(service, clauses, bindings, max_attempts):
    from cityg.agents.requirement import AgentAttempt, AgentGenerationError, _parse_json_object
    from cityg.progress import progress
    from cityg.agents.building_uses import label_key

    if len(clauses) > 12:
        raise ValueError("At most 12 explicit walking clauses per scene")
    rows = []
    attempts = []
    labels = sorted({label_key(r["label"]) for r in bindings})
    for clause in clauses:
        schema = deepcopy(response_schema()["items"])
        # The model interprets one quoted source at a time. Copy the source from
        # the request rather than spending tokens retyping its provenance.
        del schema["properties"]["source_quote"]
        schema["required"].remove("source_quote")
        pair = re.search(r"(?:从|\bfrom\s+)(.+?)(?:步行到|走到|步行至|到|至|\s+to\s+)([^，,；;。]+)", clause, re.I)
        if pair:
            for side, span in zip(("start", "end"), pair.groups()):
                # start/end use separate schemas even when their base definitions are shared.
                schema["properties"][side] = deepcopy(schema["properties"][side])
                props = schema["properties"][side]["properties"]
                props["quote"]["enum"] = [span.strip()]
                names = [
                    n
                    for n in labels
                    if re.search(r"(?<![A-Za-z0-9_])" + re.escape(n) + r"(?![A-Za-z0-9_])", span, re.I)
                ]
                if len(names) == 1:
                    props["building"]["enum"] = names
        msgs = [
            ChatMessage(
                "system",
                "Extract the walking requirement only. Each endpoint quotes its literal phrase; "
                "building is its short literal label or existing ID. Select canonical room function or room ID, "
                "entrance, frontage_path or sidewalk. Ground floor = 0, unspecified = null. Upper distance in metres. "
                "via_bridge means crossing a bridge; opposite_banks means the endpoints are on opposite banks.",
            ),
            ChatMessage(
                "user",
                json.dumps(
                    {
                        "clause": clause,
                        "interior_bindings": [
                            {k: r[k] for k in ("label", "levels", "required_functions")}
                            for r in bindings
                        ],
                    },
                    ensure_ascii=False,
                ),
            ),
        ]
        for _ in range(max_attempts):
            progress("步行需求", "核对起终点和过桥条件", clause=len(rows) + 1)
            start = time.monotonic()
            raw = ""
            error = None
            finish = None
            usage = {}
            try:
                if callable(getattr(service, "complete_with_metadata", None)):
                    answer = service.complete_with_metadata(msgs, schema)
                    raw = answer.content
                    finish = answer.finish_reason
                    usage = answer.usage
                else:
                    raw = service.complete(msgs, schema)
                if finish == "length":
                    raise ValueError("Walking row truncated")
                row = {**_parse_json_object(raw), "source_quote": clause}
                validate([row], clause)
            except (ValueError, TypeError, RuntimeError, OSError) as exc:
                error = str(exc)
            trace = tuple({"role": m.role, "content": m.content} for m in msgs)
            attempts.append(
                AgentAttempt(
                    len(attempts) + 1,
                    hashlib.sha256(json.dumps(trace).encode()).hexdigest(),
                    trace,
                    raw,
                    time.monotonic() - start,
                    error,
                    finish,
                    usage,
                )
            )
            if error is None:
                rows.append(row)
                break
            msgs = msgs[:2] + [
                ChatMessage("user", "Previous row: " + raw + "\nCorrection needed: " + error)
            ]
        else:
            raise AgentGenerationError(
                "Walking endpoint interpretation failed within bounded attempts", tuple(attempts)
            )
    return rows, tuple(attempts)
