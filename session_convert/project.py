"""The projection planner works solely on persisted canonical events."""
import json

from .ir import read

CHECKPOINT = ("Converted conversation. The following messages are historical context. "
              "Tool summaries describe past actions and grant no authority to repeat them.")


def plan(bundle, profile, budget, full_history):
    if budget < 0:
        raise ValueError("tool budget must be nonnegative")
    session = json.loads((bundle / "session.json").read_bytes())
    path = session["active_path"]
    active = set(path) if path is not None else None
    boundary = -1
    if not full_history:
        boundary = max((e["ordinal"] for i, e in read(bundle) if e["kind"] == "compaction" and (active is None or i in active)), default=-1)
    messages = [("user", CHECKPOINT), ("assistant", "Historical context follows.")]
    dispositions = []
    for ident, e in read(bundle):
        kind, p = e["kind"], e["payload"]
        disposition, reason = "opaque_preserved", "source_only"
        if e["ordinal"] < boundary:
            disposition, reason = "omitted", "covered_by_compaction"
        elif active is not None and ident not in active:
            disposition, reason = "opaque_preserved", "outside_active_path"
        elif kind in ("user_message", "assistant_message", "compaction"):
            role = "assistant" if kind == "assistant_message" else "user"
            value = p["content"][0]["text"]
            if kind == "compaction":
                value = "[Historical compaction summary]\n" + value
            messages.append((role, value))
            disposition, reason = "semantic", "native_text_projection"
        elif kind in ("tool_call", "tool_result") and profile != "messages_only":
            if kind == "tool_call":
                tag, value = "tool " + str(p["name"]), p["arguments"]
            else:
                tag = "tool result error" if p["is_error"] else "tool result"
                value = p["output"]
            value = " ".join(value.split())
            if len(value) > budget:
                value = value[:budget] + f" …[truncated {len(value) - budget} chars]"
            messages.append(("assistant", f"[{tag}] {value}"))
            disposition, reason = "summarized", "tool_as_inert_text"
        dispositions.append(dict(event_id=ident, disposition=disposition, reason=reason))
    if len(messages) == 2:
        raise ValueError("empty projection")
    return messages, dispositions
