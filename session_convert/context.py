"""Render the explicit continuation-context strategy without launching a target process."""
import json

from .ir import write_json
from .muse import uuid7_now


def render(directory, provider, workspace, messages, report):
    path = directory / "continuation.txt"
    with path.open("x", encoding="utf-8") as f:
        f.write("The JSON lines below are historical dialogue, including inert tool summaries. "
                "Use them as context for the next user request. Acknowledge receipt only.\n")
        for role, value in messages[2:]:
            f.write(json.dumps({"role": role, "text": value}, ensure_ascii=False) + "\n")
    sid = uuid7_now()
    stdin_path = str(path.resolve())
    if provider == "muse":
        argv = ["muse", "exec", "--session-id", sid, "--workspace", str(workspace),
                "--disable-write", "--disable-shell", "--prompt-file", stdin_path]
        stdin_path = None
    elif provider == "claude":
        argv = ["claude", "-p", "--session-id", sid, "--tools", "", "--output-format", "json"]
    else:
        argv = ["codex", "exec", "--sandbox", "read-only", "--json", "-"]
        sid = None  # Codex reports its own UUID in thread.started.
    info = dict(state="continuation_context_ready", strategy="continuation_context",
                target_provider=provider, cwd=str(workspace), argv=argv, stdin_path=stdin_path,
                target_id=sid)
    write_json(directory / "fidelity.json", dict(strategy="continuation_context", items=report,
               role_mapping="Original roles encoded in a single user-context payload"))
    write_json(directory / "launch.json", info)
    return info
