"""Normalize native JSONL records. Unknown or non-portable facts retain raw evidence."""
import json


def text(kind, value):
    if not isinstance(value, str):
        raise ValueError("message text must be a string")
    return kind, {"content": [{"type": "text", "text": value}]}


def blocks(role, content, allowed):
    if isinstance(content, str):
        yield text(role, content)
        return
    for b in content or []:
        kind = b.get("type")
        if kind in allowed:
            yield text(role, b["text"])
        elif kind in ("thinking", "redacted_thinking", "reasoning"):
            yield "opaque_reasoning", {}
        elif kind == "tool_use":
            yield call(b.get("name"), b.get("id"), b.get("input"))
        elif kind == "tool_result":
            yield result(b.get("tool_use_id"), b.get("content"), b.get("is_error", False))
        else:
            yield "opaque_event", {}


def display(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def call(name, identifier, arguments):
    return "tool_call", {"name": name, "call_id": identifier, "arguments": display(arguments)}


def result(identifier, value, error=False):
    return "tool_result", {"call_id": identifier, "output": display(value), "is_error": error}


def claude(r):
    kind = r.get("type")
    if r.get("isSidechain") or r.get("isMeta"):
        return
    if kind in ("user", "assistant"):
        role = "compaction" if r.get("isCompactSummary") else kind + "_message"
        yield from blocks(role, r["message"]["content"], {"text"})


def codex(r):
    p = r.get("payload", {})
    kind = p.get("type") if isinstance(p, dict) else None
    if r.get("type") == "compacted" and isinstance(p.get("message"), str):
        yield text("compaction", p["message"])
    if r.get("type") != "response_item":
        return
    if kind == "message" and p.get("role") in ("user", "assistant"):
        yield from blocks(p["role"] + "_message", p["content"], {"input_text", "output_text"})
    elif kind in ("function_call", "custom_tool_call"):
        yield call(p.get("name"), p.get("call_id"), p.get("arguments", p.get("input")))
    elif kind in ("function_call_output", "custom_tool_call_output"):
        yield result(p.get("call_id"), p.get("output"))
    elif kind == "reasoning":
        yield "opaque_reasoning", {}


def muse(r):
    p = r.get("payload", {})
    if r.get("payload_type") == "runtime.user_intent.accepted":
        for b in p.get("refill_blocks", []):
            yield text("user_message", b["text"]) if b.get("kind") == "text" else ("opaque_event", {})
    elif r.get("payload_type") == "runtime.session":
        e = p.get("event", {})
        kind = e.get("kind")
        if kind == "assistant_message_committed":
            yield text("assistant_message", e["text"])
        elif kind in ("reasoning_committed", "reasoning_summary_committed"):
            yield "opaque_reasoning", {}
        elif kind == "assistant_tool_calls_committed":
            for c in e["tool_calls"]:
                yield call(c.get("name"), c.get("call_id"), c.get("args"))
        elif kind == "tool_result_batch_committed":
            for item in e["results"]:
                yield result(item.get("tool_call_id"), item.get("text"))
        elif kind == "model_completed":
            yield "usage", {}


READERS = {"muse": muse, "codex": codex, "claude": claude}


def identity(provider, r):
    if provider == "claude":
        return r.get("sessionId")
    if provider == "codex" and r.get("type") == "session_meta":
        return r["payload"].get("id")
    if provider == "muse" and r.get("stream", {}).get("kind") == "session":
        return r["stream"].get("id")
