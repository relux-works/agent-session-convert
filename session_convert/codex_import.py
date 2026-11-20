"""Publish a staged rollout through the authenticated Codex app-server."""
import json
import os
from pathlib import Path
import platform
import subprocess
import threading
from uuid import UUID

from . import binding
from .ir import write_json
from .readers import codex


def require_version():
    version = subprocess.check_output(["codex", "--version"], text=True, timeout=10).strip()
    if (version, platform.system(), platform.machine()) != ("codex-cli 0.171.0", "Darwin", "arm64"):
        raise ValueError("unqualified Codex version or platform")


def user_visible(turns):
    messages = []
    for turn in turns:
        for item in turn["items"]:
            if item["type"] == "userMessage":
                messages.extend(("user", block["text"]) for block in item["content"] if block["type"] == "text")
            elif item["type"] == "agentMessage":
                messages.append(("assistant", item["text"]))
    return messages


def request(proc, seq, method, params):
    proc.stdin.write(json.dumps(dict(id=seq, method=method, params=params)) + "\n")
    proc.stdin.flush()
    for line in proc.stdout:
        reply = json.loads(line)
        if reply.get("id") == seq:
            if "error" in reply:
                raise ValueError(f"Codex rejected {method} (RPC {reply['error'].get('code')})")
            return reply["result"]
    raise ValueError(f"Codex closed the stream during {method}")


def publish_fork(staged, workspace, messages, result):
    staged_id = result.pop("target_id")
    receipt = staged.parent / "validation.json"
    result.update(state="publication_pending", staged_id=staged_id, strategy="target_official_import")
    with subprocess.Popen(["codex", "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, cwd=workspace, text=True, encoding="utf-8") as proc:
        timer = threading.Timer(90, proc.kill)
        timer.start()
        try:
            request(proc, 1, "initialize", dict(clientInfo=dict(name="session_convert", version="1"),
                                               capabilities=dict(experimentalApi=True)))
            proc.stdin.write('{"method":"initialized"}\n')
            account = request(proc, 2, "account/read", {"refreshToken": False}).get("account")
            if not account or account.get("type") != "chatgpt":
                raise ValueError("Codex publication requires the qualified ChatGPT login")
            write_json(receipt, result)
            thread = request(proc, 3, "thread/fork", dict(threadId=staged_id, path=str(staged.resolve()),
                                                         cwd=str(workspace)))["thread"]
            sid = str(UUID(thread["id"]))
            if sid == staged_id:
                raise ValueError("Codex did not allocate a fresh session")
            result.update(state="created_pending_readback", target_id=sid)
            write_json(receipt, result)
            if Path(thread["cwd"]).resolve() != workspace or user_visible(thread["turns"]) != messages:
                raise ValueError("Codex native turn history differs from the staged projection")
            path = Path(thread["path"]).resolve(strict=True)
            store = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve() / "sessions"
            if store not in path.parents or not path.name.endswith("-" + sid + ".jsonl"):
                raise ValueError("unexpected Codex rollout location")
        finally:
            timer.cancel()
            proc.stdin.close()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    # The UI turn stream and model-visible response items are distinct in a Codex rollout.
    persisted = []
    with path.open(encoding="utf-8") as log:
        first = json.loads(next(log))
        meta = first["payload"]
        if (first["type"] != "session_meta" or meta["id"] != sid or meta.get("account_scoped") is not True
                or Path(meta["cwd"]).resolve() != workspace):
            raise ValueError("Codex persisted an unexpected target identity or workspace")
        for line in log:
            for kind, payload in codex(json.loads(line)):
                if kind in ("user_message", "assistant_message"):
                    persisted.append((kind.split("_")[0], payload["content"][0]["text"]))
    if persisted != messages:
        raise ValueError("Codex persisted different model-visible history")
    result.update(state="published", target_log=str(path), resume_argv=binding.resume("codex", sid, result.get("destination")))
    write_json(receipt, result)
    return result
