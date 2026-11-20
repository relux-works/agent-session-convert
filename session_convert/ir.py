"""An immutable transcript snapshot and a versioned, content-addressed event stream."""
import hashlib
import json
import re
import shutil

from uuid import UUID
from .readers import READERS, identity


def encode(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def file_digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def write_json(path, obj):
    path.write_bytes(encode(obj) + b"\n")


def invalid_number(_):
    raise ValueError("nonfinite JSON number")


def unique_keys(pairs):
    out = dict(pairs)
    if len(out) != len(pairs):
        raise ValueError("duplicate JSON object key")
    return out


def store_payload(bundle, payload):
    # Large message text and tool bodies are content-addressed without truncating UTF-8.
    fields = [(b, "text") for b in payload.get("content", [])]
    fields += [(payload, key) for key in ("arguments", "output") if key in payload]
    for obj, key in fields:
        data = obj[key].encode()
        if len(data) <= 65536:
            continue
        ident = digest(data)
        path = bundle / "blobs" / ident[7:]
        if not path.exists():
            path.write_bytes(data)
        del obj[key]
        obj[key + "_blob"] = ident


def unpack(bundle, payload):
    fields = [(b, "text") for b in payload.get("content", [])]
    fields += [(payload, key) for key in ("arguments", "output") if key + "_blob" in payload]
    for obj, key in fields:
        ref = obj.pop(key + "_blob", None)
        if ref is None:
            continue
        if not isinstance(ref, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", ref):
            raise ValueError("invalid payload reference")
        path = bundle / "blobs" / ref[7:]
        if path.is_symlink():
            raise ValueError("invalid payload path")
        data = path.read_bytes()
        if digest(data) != ref:
            raise ValueError("payload digest mismatch")
        obj[key] = data.decode()


def stable_id(provider, raw_digest, label):
    # Use timestamp zero for an unknown source time. All remaining identity bits are hash-derived.
    seed = hashlib.sha256(encode([provider, raw_digest, label])).digest()
    value = bytearray(b"\x00" * 6 + seed[:10])
    value[6] = 0x70 | (value[6] & 0x0f)
    value[8] = 0x80 | (value[8] & 0x3f)
    return str(UUID(bytes=bytes(value)))


def capture(source, provider, bundle):
    if source.is_symlink() or not source.is_file():
        raise ValueError("source must be a regular transcript")
    bundle.mkdir(mode=0o700)
    raw = bundle / "source.jsonl"
    first = file_digest(source)
    shutil.copyfile(source, raw)
    if file_digest(raw) != first or file_digest(source) != first:
        raise ValueError("source_changed_during_conversion")
    (bundle / "blobs").mkdir()
    logical, actor = (stable_id(provider, first, label) for label in ("session", "main"))
    ids, native, parent_by_uuid, heads = [], None, {}, set()
    offset = 0
    children, ancestry = {}, {}
    epoch_heads, calls, results = [], {}, {}
    forked, last_visible = False, None
    transcript = False
    with raw.open("rb") as f, (bundle / "events.jsonl").open("xb") as out:
        for line_number, line in enumerate(f, 1):
            try:
                r = json.loads(line, object_pairs_hook=unique_keys, parse_constant=invalid_number)
                candidate = identity(provider, r)
                if native and candidate and native != candidate:
                    raise ValueError("mixed session identities")
                native = native or candidate
                facts = list(READERS[provider](r)) or [("opaque_event", {})]
                parents = ids[-1:]
                if provider == "claude" and "parentUuid" in r:
                    key = r["parentUuid"]
                    parents = [parent_by_uuid[key]] if key in parent_by_uuid else []
                for kind, payload in facts:
                    store_payload(bundle, payload)
                    transcript |= kind in ("user_message", "assistant_message", "compaction")
                    event = dict(schema_version=1, ordinal=len(ids), logical_session_id=logical,
                                 actor_id=actor, parents=parents, kind=kind, payload=payload,
                                 source_evidence=dict(blob_id=first, offset=offset, length=len(line)))
                    ident = digest(encode(event))
                    ids.append(ident)
                    heads.difference_update(parents)
                    heads.add(ident)
                    if provider == "claude":
                        ancestry[ident] = parents[0] if parents else None
                        if parents and r.get("uuid") and not r.get("isSidechain"):
                            forked |= parents[0] in children
                            children[parents[0]] = ident
                        if kind == "compaction" and last_visible:
                            epoch_heads.append(last_visible)
                        if kind == "tool_call":
                            calls[ident] = payload["call_id"]
                        if kind == "tool_result":
                            results[ident] = payload["call_id"]
                        if kind in ("user_message", "assistant_message", "compaction", "tool_call", "tool_result"):
                            last_visible = ident
                    parents = [ident]
                    out.write(encode(dict(event, event_id=ident)) + b"\n")
                if r.get("uuid"):
                    parent_by_uuid[r["uuid"]] = ids[-1]
            except (KeyError, TypeError, AttributeError, ValueError) as e:
                raise ValueError(f"invalid {provider} transcript at line {line_number} ({type(e).__name__})") from None
            offset += len(line)
    if not transcript or not native:
        raise ValueError("no identifiable session with conversation history")
    active_path = None
    if forked:
        active = set()
        for leaf in epoch_heads + [last_visible]:
            while leaf is not None and leaf not in active:
                active.add(leaf)
                leaf = ancestry[leaf]
        # Parallel tool results can be sibling records rather than successive ancestors.
        selected_calls = {calls[i] for i in active if i in calls and calls[i]}
        active.update(i for i, call_id in results.items() if call_id in selected_calls)
        active_path = [i for i in ids if i in active]
    session = dict(active_path=active_path, schema="relux.transcript-ir", schema_version=1, logical_session_id=logical,
                   source_provider=provider, source_native_session_id=native, actor_id=actor,
                   event_ids=ids, head_event_ids=sorted(heads), raw_sha256=first,
                   capture_scope="single_transcript", raw_complete=False)
    write_json(bundle / "session.json", dict(session, canonical_session_id=digest(encode(session))))


def read(bundle):
    session = json.loads((bundle / "session.json").read_bytes())
    ident = session.pop("canonical_session_id")
    if (session["schema"] != "relux.transcript-ir" or session["schema_version"] != 1
            or ident != digest(encode(session))):
        raise ValueError("invalid IR session")
    seen = set()
    with (bundle / "events.jsonl").open("rb") as f:
        for i, expected in enumerate(session["event_ids"]):
            event = json.loads(f.readline())
            if (event.pop("event_id") != expected or digest(encode(event)) != expected
                    or event["ordinal"] != i or expected in seen
                    or event["logical_session_id"] != session["logical_session_id"]
                    or not seen.issuperset(event["parents"])):
                raise ValueError("invalid IR event chain")
            seen.add(expected)
            unpack(bundle, event["payload"])
            yield expected, event
        if f.read(1):
            raise ValueError("unmanifested IR event")
