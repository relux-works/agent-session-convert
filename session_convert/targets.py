"""Target-native transcript layouts. All writers take the same ordered projection."""
from importlib.resources import files
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from .ir import encode, file_digest
from .muse import build_records, frame_max_ts, uuid7_now


def claude(messages, sid, workspace, stamp):
    parent = None
    for role, value in messages:
        ident = uuid7_now()
        message = {"role": role, "content": value}
        if role == "assistant":
            message.update(id="msg_" + ident.replace("-", ""), type="message", model="converted",
                           content=[{"type": "text", "text": value}], stop_reason="end_turn",
                           stop_sequence=None, usage={"input_tokens": 0, "output_tokens": 0})
        yield dict(type=role, uuid=ident, parentUuid=parent, sessionId=sid, timestamp=stamp,
                   isSidechain=False, cwd=str(workspace), userType="external", message=message)
        parent = ident


def codex(messages, sid, workspace, stamp):
    meta = dict(id=sid, timestamp=stamp, cwd=str(workspace), originator="codex_cli_rs",
                cli_version="0.171.0", source="cli", model_provider="openai",
                base_instructions={"text": ""})
    yield dict(timestamp=stamp, type="session_meta", payload=meta)
    turn = None
    for role, value in messages:
        if role == "user":
            if turn:
                yield dict(timestamp=stamp, type="event_msg", payload=dict(type="task_complete", turn_id=turn))
            turn = uuid7_now()
            yield dict(timestamp=stamp, type="event_msg", payload=dict(type="task_started", turn_id=turn,
                       collaboration_mode_kind="default"))
        ident = uuid7_now()
        item = dict(type="message", role=role, id=ident, content=[
            {"type": "input_text" if role == "user" else "output_text", "text": value}])
        yield dict(timestamp=stamp, type="response_item", payload=item)
        if role == "user":
            visible = dict(type="user_message", message=value, images=[], local_images=[], text_elements=[])
        else:
            visible = dict(type="agent_message", message=value, phase="final_answer")
        yield dict(timestamp=stamp, type="event_msg", payload=visible)
    yield dict(timestamp=stamp, type="event_msg", payload=dict(type="task_complete", turn_id=turn))



def muse(messages, sid, workspace, stamp, frame=None):
    template = json.loads(files("session_convert").joinpath("muse-turn-template.json").read_bytes())
    turns = []
    for role, value in messages:
        if role == "user":
            turns.append([value, ""])
        else:
            turns[-1][1] += ("\n" if turns[-1][1] else "") + value
    yield from build_records(template, sid, str(workspace), turns, frame_max_ts(frame) if frame else 0)


WRITERS = {"claude": claude, "codex": codex, "muse": muse}


def stage(provider, path, messages, sid, workspace, stamp, frame=None):
    args = [messages, sid, workspace, stamp]
    if provider == "muse":
        args.append(frame)
    with path.open("xb") as out:
        if frame:
            out.write(frame)
        for ordinal, record in enumerate(WRITERS[provider](*args)):
            if provider == "codex":
                record["ordinal"] = ordinal
            out.write(encode(record) + b"\n")
        out.flush()
        os.fsync(out.fileno())


def store_path(provider, sid, workspace, now):
    if provider == "claude":
        root = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
        key = re.sub(r"[^a-zA-Z0-9]", "-", str(workspace))
        if len(key) > 200:
            raise ValueError("long Claude project keys require native discovery")
        return root / "projects" / key / (sid + ".jsonl")
    date = now.strftime("%Y/%m/%d")
    if provider == "codex":
        root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        return root / "sessions" / date / f"rollout-{now:%Y-%m-%dT%H-%M-%S}-{sid}.jsonl"
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return root / "muse/sessions" / date / sid / "session.jsonl"


def inspect_muse(path):
    proc = subprocess.run(["muse", "trace", "inspect", "--session-log", str(path), "--format", "json"],
                          capture_output=True, timeout=180)
    if proc.returncode or json.loads(proc.stdout).get("load_status") != "loaded":
        raise ValueError("Muse rejected the session during trace inspection")


def seed_frame(sid, workspace, scratch):
    # Mint the permission transaction in a private store. The live target never contains a seed.
    root = Path(tempfile.mkdtemp(dir=scratch))
    env = dict(os.environ, XDG_DATA_HOME=str(root))
    proc = subprocess.run(["muse", "exec", "--provider", "echo", "--session-id", sid,
                           "--workspace", str(workspace), "seed"], env=env, capture_output=True, timeout=180)
    candidates = list(root.glob(f"muse/sessions/*/*/*/{sid}/session.jsonl"))
    if proc.returncode or len(candidates) != 1:
        raise ValueError("Muse could not mint its native permission frame")
    with candidates[0].open("rb") as f:
        line = f.readline()
    if json.loads(line).get("retained_frame") != "session_permission_transaction":
        raise ValueError("unknown Muse permission frame")
    return line


def publish(staged, target):
    # Hard link a complete private temporary file on the target filesystem, atomically create-only.
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent) as temporary, staged.open("rb") as source:
        import shutil
        shutil.copyfileobj(source, temporary)
        temporary.flush()
        os.fsync(temporary.fileno())
        os.link(temporary.name, target)
    if file_digest(target) != file_digest(staged):
        raise ValueError("live transcript digest mismatch")
