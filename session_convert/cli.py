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

from . import binding, codex_import
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
            qualification=False, strategy="native", destination=None):
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
    if destination and destination["kind"] == "curator":
        root = Path(destination["home"]) / binding.STORE[provider]
        if target.resolve() != target or not target.is_relative_to(root):
            raise ValueError("target outside resolved Curator store")
    staged = directory / "session.jsonl"
    official_fork = apply and provider == "codex" and not qualification
    if apply:
        if official_fork:
            codex_import.require_version()
        elif not qualification:
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
        expected = [(role, value or "[source turn had no assistant text]") if role == "assistant"
                    else (role, value) for role, value in expanded]
    if identities != {sid} or observed != expected:
        raise ValueError("native readback mismatch")
    write_json(directory / "fidelity.json", dict(profile=profile,
               strategy="target_official_import" if official_fork else "target_native_writer",
               items=report, synthesized=["migration checkpoint", "target envelopes"],
               canonical_session_id=session["canonical_session_id"]))
    result = dict(state="staged", target_provider=provider, target_id=sid, workspace=str(workspace),
                  source_sha256=session["raw_sha256"], staged_sha256=file_digest(staged))
    if destination:
        result["destination"] = destination
    write_json(directory / "validation.json", result)
    if apply:
        if provider == "muse":
            inspect_muse(staged)
        if file_digest(source) != session["raw_sha256"]:
            raise ValueError("source_changed_during_conversion")
        schedules(source, session["source_provider"])
        if official_fork:
            return codex_import.publish_fork(staged, workspace, messages, result)
        publish(staged, target)
        try:
            if provider == "muse":
                inspect_muse(target)
        except Exception:
            if file_digest(target) == result["staged_sha256"]:
                target.unlink()
            raise
        result.update(state="published", target_log=str(target),
                      resume_argv=binding.resume(provider, sid, destination))
        write_json(directory / "validation.json", result)
    return result


def parser():
    p = argparse.ArgumentParser(prog="agent-session-convert")
    subs = p.add_subparsers(dest="command", required=True)
    locate = subs.add_parser("locate", help="locate a native UUID in registered Curator homes")
    locate.add_argument("--from", dest="reader", required=True, choices=READERS)
    locate.add_argument("--session-id", required=True)
    locate.add_argument("--source-profile")
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
            group = sub.add_mutually_exclusive_group()
            group.add_argument("--target-profile")
            group.add_argument("--personal", action="store_true")
            sub.add_argument("--expect-home")
            sub.add_argument("--expect-lock")
            sub.add_argument("--expect-source-id")
            sub.add_argument("--reuse-published", action="store_true")
    return p


def main(argv=None):
    os.umask(0o077)
    a = parser().parse_args(argv)
    try:
        target = None
        if a.command == "locate":
            print(json.dumps(binding.locate(a.reader, a.session_id, a.source_profile)))
            return 0
        if a.command != "project":
            origin = binding.provenance(a.source_log, a.reader)
            if getattr(a, "expect_source_id", None) and (not origin or origin["profile"] != a.target_profile
                    or origin["lock"] != a.expect_lock):
                raise ValueError("source no longer matches the pinned Curator profile")
            if getattr(a, "apply", False):
                target = binding.destination(origin, a.writer, a.target_profile, a.personal,
                                             a.expect_home, a.expect_lock)
            if getattr(a, "reuse_published", False):
                if not (a.apply and a.expect_source_id and a.expect_home and a.expect_lock and
                        origin and target and target["kind"] == "curator"):
                    raise ValueError("reuse requires a pinned managed transfer")
                if a.out_dir.exists():
                    print(json.dumps(binding.previous_target(a.out_dir, target, a.writer, a.workspace,
                                                             a.source_log, a.expect_source_id)))
                    return 0
            capture(a.source_log, a.reader, a.out_dir)
            if origin:
                write_json(a.out_dir / "source-binding.json", origin)
            if getattr(a, "expect_source_id", None):
                manifest = json.loads((a.out_dir / "session.json").read_bytes())
                if not origin or manifest["source_native_session_id"] != a.expect_source_id:
                    raise ValueError("source native identity mismatch")
            if a.command == "capture":
                print(a.out_dir / "session.json")
                return 0
        bundle = a.bundle if a.command == "project" else a.out_dir
        out = a.out_dir if a.command == "project" else bundle / "projection"
        print(json.dumps(project(bundle, out, a.writer, a.workspace, a.profile, a.max_tool_chars,
                                 a.full_history, getattr(a, "apply", False), getattr(a, "source_log", None),
                                 strategy=a.strategy, destination=target)))
        return 0
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.SubprocessError) as e:
        print(f"conversion failed: {e}", file=sys.stderr)
        return 2
