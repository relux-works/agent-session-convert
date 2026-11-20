"""Public entry point for capture, detached projection and single-command conversion."""
import argparse
import datetime
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

from .context import render
from .ir import capture, file_digest, write_json
from .muse import uuid7_now
from .project import plan
from .readers import READERS, identity
from .targets import inspect_muse, publish, seed_frame, stage, store_path


def schedules(source, provider):
    if provider != "muse":
        return
    db = source.parent / "cron.db"
    if db.is_symlink():
        raise ValueError("unsafe cron sidecar")
    if db.exists():
        conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            if conn.execute("SELECT 1 FROM cron_jobs WHERE status='active' LIMIT 1").fetchone():
                raise ValueError("scheduled_work_present")
        finally:
            conn.close()


def project(bundle, directory, provider, workspace, profile, budget, full_history, apply, source=None,
            qualification=False, strategy="native"):
    if not workspace.is_dir():
        raise ValueError("target workspace must exist")
    workspace = workspace.resolve()
    session = json.loads((bundle / "session.json").read_bytes())
    if file_digest(bundle / "source.jsonl") != session["raw_sha256"]:
        raise ValueError("source snapshot digest mismatch")
    messages, report = plan(bundle, profile, budget, full_history)
    directory.mkdir(mode=0o700)
    if strategy == "continuation_context":
        if apply:
            raise ValueError("continuation context is consumed by the target CLI using launch.json")
        return render(directory, provider, workspace, messages, report)
    now = datetime.datetime.now().astimezone()
    stamp = now.astimezone(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    sid = uuid7_now()
    target = store_path(provider, sid, workspace, now)
    staged = directory / "session.jsonl"
    if apply:
        if not qualification:
            if (session["source_provider"], provider) != ("claude", "muse"):
                raise ValueError("native writer awaiting provider qualification; projection available offline")
            version = subprocess.check_output(["muse", "--version"], text=True, timeout=15).strip()
            if version != "Muse Code 1.4.24 (1.4.24-R9131.1)":
                raise ValueError("unqualified Muse version")
        schedules(source, session["source_provider"])
    frame = None
    if apply and provider == "muse":
        with tempfile.TemporaryDirectory(dir=directory) as seed:
            frame = seed_frame(sid, workspace, seed)
    stage(provider, staged, messages, sid, workspace, stamp, frame)
    # Reopen staged records to validate the actual native identity and replay, including ordering.
    expected = []
    for role, value in messages:
        if provider == "muse" and role == "assistant" and expected and expected[-1][0] == role:
            expected[-1] = (role, expected[-1][1] + "\n" + value)
        else:
            expected.append((role, value))
    observed, identities = [], set()
    with staged.open() as f:
        for line in f:
            record = json.loads(line)
            native = identity(provider, record)
            if native:
                identities.add(native)
            for kind, payload in READERS[provider](record):
                if kind in ("user_message", "assistant_message"):
                    value = payload["content"][0]["text"]
                    observed.append((kind.split("_")[0], value))
    if provider == "muse":
        expanded = []
        for item in expected:
            if item[0] == "user" and expanded and expanded[-1][0] == "user":
                expanded.append(("assistant", "[source turn had no assistant text]"))
            expanded.append(item)
        if expanded[-1][0] == "user":
            expanded.append(("assistant", "[source turn had no assistant text]"))
        expected = expanded
    if identities != {sid} or observed != expected:
        raise ValueError("native readback mismatch")
    write_json(directory / "fidelity.json", dict(profile=profile, strategy="target_native_writer",
               items=report, synthesized=["migration checkpoint", "target envelopes"],
               canonical_session_id=session["canonical_session_id"]))
    result = dict(state="staged", target_provider=provider, target_id=sid, workspace=str(workspace),
                  source_sha256=session["raw_sha256"], staged_sha256=file_digest(staged))
    write_json(directory / "validation.json", result)
    if apply:
        if provider == "muse":
            inspect_muse(staged)
        if file_digest(source) != session["raw_sha256"]:
            raise ValueError("source_changed_during_conversion")
        schedules(source, session["source_provider"])
        publish(staged, target)
        try:
            if provider == "muse":
                inspect_muse(target)
        except Exception:
            if file_digest(target) == result["staged_sha256"]:
                target.unlink()
            raise
        result.update(state="published", target_log=str(target),
                      resume_argv=[provider, "--resume", sid] if provider == "claude"
                      else [provider, "resume", sid])
        write_json(directory / "validation.json", result)
    return result


def parser():
    p = argparse.ArgumentParser(prog="agent-session-convert")
    subs = p.add_subparsers(dest="command", required=True)
    for name in ("capture", "project", "convert"):
        sub = subs.add_parser(name)
        sub.add_argument("--out-dir", type=Path, required=True)
        if name != "project":
            sub.add_argument("--from", dest="reader", choices=READERS, required=True)
            sub.add_argument("--source-log", type=Path, required=True)
        else:
            sub.add_argument("--bundle", type=Path, required=True)
        if name != "capture":
            sub.add_argument("--strategy", choices=("native", "continuation_context"), default="native")
            sub.add_argument("--to", dest="writer", choices=READERS, required=True)
            sub.add_argument("--workspace", type=Path, required=True)
            sub.add_argument("--profile", choices=("compact", "messages_only"), default="compact")
            sub.add_argument("--max-tool-chars", type=int, default=240)
            sub.add_argument("--full-history", action="store_true")
        if name == "convert":
            sub.add_argument("--apply", action="store_true")
    return p


def main(argv=None):
    os.umask(0o077)
    a = parser().parse_args(argv)
    try:
        if a.command != "project":
            capture(a.source_log, a.reader, a.out_dir)
            if a.command == "capture":
                print(a.out_dir / "session.json")
                return 0
        bundle = a.bundle if a.command == "project" else a.out_dir
        out = a.out_dir if a.command == "project" else bundle / "projection"
        print(json.dumps(project(bundle, out, a.writer, a.workspace, a.profile, a.max_tool_chars,
                                 a.full_history, getattr(a, "apply", False), getattr(a, "source_log", None),
                                 strategy=a.strategy)))
        return 0
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.SubprocessError) as e:
        print(f"conversion failed: {e}", file=sys.stderr)
        return 2
