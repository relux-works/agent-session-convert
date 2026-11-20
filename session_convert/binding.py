"""Resolve Curator provenance and an explicit publication destination."""
import json
import os
from pathlib import Path
import re
import subprocess
from uuid import UUID

ENVIRONMENT = {"claude": "claude_code", "codex": "codex_cli", "muse": "muse"}
HOME_KEYS = {"codex": {"CODEX_HOME": ""}, "claude": {"CLAUDE_CONFIG_DIR": ""},
             "muse": {"XDG_CONFIG_HOME": "config", "XDG_DATA_HOME": "data",
                      "XDG_STATE_HOME": "state", "XDG_CACHE_HOME": "cache"}}
STORE = {"codex": "sessions", "claude": "projects", "muse": "data/muse/sessions"}


def curator(*args):
    return json.loads(subprocess.check_output(["curator", "env", *args], timeout=90))


def inventory():
    return curator("status", "--json")["homes"]


def match_home(rows, provider, profile):
    candidates = [Path(r["home"]) for r in rows if r["environment"] == ENVIRONMENT[provider]
                  and r["profile"] == profile and r["mode"] == "managed-home" and r["provisioned"]]
    if len(candidates) != 1 or not candidates[0].is_absolute():
        raise ValueError("managed home missing or ambiguous")
    return candidates[0].resolve(strict=True)


def provenance(path, provider):
    path = path.resolve(strict=True)
    for parent in path.parents:
        marker = parent / ".agent-environment.json"
        if not marker.exists():
            continue
        profile = json.loads(marker.read_bytes())["profile"]
        home = match_home(inventory(), provider, profile["name"])
        if home != parent or not path.is_relative_to(home / STORE[provider]):
            raise ValueError("source transcript outside registered provider store")
        return dict(profile=profile["name"], lock=profile["lock_sha256"], home=str(home))
    return None


def locate(provider, session_id, profile=None):
    sid = str(UUID(session_id))
    if session_id != sid:
        raise ValueError("canonical source UUID required")
    patterns = {"muse": f"*/*/*/{sid}/session.jsonl", "codex": f"*/*/*/rollout-*-{sid}.jsonl",
                "claude": f"*/{sid}.jsonl"}
    matches = []
    for r in inventory():
        if (r["environment"] != ENVIRONMENT[provider] or not r["provisioned"]
                or r["mode"] != "managed-home" or (profile and r["profile"] != profile)):
            continue
        store = Path(r["home"]) / STORE[provider]
        for path in store.glob(patterns[provider]):
            if path.is_file() and not path.is_symlink() and path.resolve() == path:
                matches.append((path, r["profile"]))
    if len(matches) != 1:
        raise ValueError("source UUID missing or ambiguous in managed stores")
    path, name = matches[0]
    binding = provenance(path, provider)
    if not binding or binding["profile"] != name:
        raise ValueError("source profile mismatch")
    return dict(schema=1, source_log=str(path), **binding)


def destination(source, provider, profile, personal, expected_home=None, expected_lock=None):
    if personal:
        if source:
            raise ValueError("managed source requires a Curator destination")
        for key in HOME_KEYS[provider]:
            os.environ.pop(key, None)
        return dict(kind="personal")
    profile = profile or (source and source["profile"])
    if not profile:
        raise ValueError("unknown source profile: select --target-profile or --personal before publication")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", profile):
        raise ValueError("invalid Curator profile")
    resolved = curator("resolve", ENVIRONMENT[provider], "--profile", profile, "--repair",
                       "--preserve-lock", "--format", "json")
    home = match_home(inventory(), provider, profile)
    lock = resolved["profile"]["lock_sha256"]
    if (resolved["environment"] != ENVIRONMENT[provider] or resolved["profile"]["name"] != profile
            or not re.fullmatch(r"[a-f0-9]{64}", lock)
            or (source and source["profile"] == profile and source["lock"] != lock)
            or (expected_lock and expected_lock != lock)
            or (expected_home and str(home) != expected_home)):
        raise ValueError("Curator destination binding mismatch")
    env = resolved["env"]
    for key, suffix in HOME_KEYS[provider].items():
        path = home / suffix
        if env[key] != str(path) or path.resolve(strict=True) != path:
            raise ValueError("Curator destination environment mismatch")
    allowed = set(HOME_KEYS[provider])
    if provider == "muse" and env.get("TBH_CREDENTIAL_BACKEND") == "file":
        allowed.add("TBH_CREDENTIAL_BACKEND")
    if set(env) != allowed:
        raise ValueError("unsupported Curator destination environment")
    os.environ.update(env)
    return dict(kind="curator", profile=profile, lock=lock, home=str(home))


def resume(provider, sid, binding):
    args = ["--resume", sid] if provider == "claude" else ["resume", sid]
    if binding and binding["kind"] == "curator":
        return ["curator", "run", ENVIRONMENT[provider], "--profile", binding["profile"],
                "--", *args]
    if binding and binding["kind"] == "personal":
        # A shell with an inherited managed home must also resume the personal copy correctly.
        return ["env", *(arg for key in HOME_KEYS[provider] for arg in ("-u", key)), provider, *args]
    return [provider, *args]


def previous_target(bundle, destination, provider, workspace, source, sid):
    """Retry only a fully published, still present, independently identifiable target."""
    from .ir import file_digest
    receipt = bundle / "projection" / "validation.json"
    if not receipt.is_file():
        raise ValueError(f"conversion already started; inspect {bundle}")
    result = json.loads(receipt.read_bytes())
    manifest = json.loads((bundle / "session.json").read_bytes())
    if (result.get("state") != "published" or result.get("destination") != destination
            or result["target_provider"] != provider or result["workspace"] != str(workspace.resolve())
            or manifest["source_native_session_id"] != sid
            or result["source_sha256"] != file_digest(source)):
        raise ValueError(f"existing conversion requires reconciliation: {bundle}")
    path = Path(result["target_log"])
    if (path.resolve(strict=True) != path or not path.is_relative_to(Path(destination["home"]) / STORE[provider])
            or not path.is_file()):
        raise ValueError(f"published target is no longer in its managed store: {bundle}")
    from .readers import identity
    with path.open("rb") as f:
        native = next((value for line in f if (value := identity(provider, json.loads(line)))), None)
    if not native or native != result["target_id"]:
        raise ValueError("published session identity changed")
    return result
