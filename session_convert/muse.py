"""Muse native record synthesis, derived from skill-agent-session-transfer (Apache-2.0)."""
import json
import os
import time
import uuid

def dump(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def uuid7_at(ms, n=0):
    rand_b = int.from_bytes(os.urandom(8), "big")
    val = (ms << 80) | (0x7 << 76) | ((n & 0x0FFF) << 64) | (0b10 << 62) | (rand_b & ((1 << 62) - 1))
    return str(uuid.UUID(int=val))


def uuid7_now():
    return uuid7_at(int(time.time() * 1000), int.from_bytes(os.urandom(2), "big"))


def build_records(template, new_id, workspace_root, rendered_turns, frame_children_max_ts=0):
    """Records after the permission frame: patched header + synthesized turns + session.end."""
    donor_id = template["donor_session_id"]
    donor_ws = template.get("donor_workspace_root") or ""
    header = []
    for r in template["header_records"]:
        s = dump(r).replace(donor_id, new_id)
        if donor_ws:
            s = s.replace(dump(donor_ws)[1:-1], dump(workspace_root)[1:-1])
        header.append(json.loads(s))
    for r in header:
        pl = r.get("payload") or {}
        rec = pl.get("record")
        if isinstance(rec, dict):
            if "workspace_root" in rec:
                rec["workspace_root"] = workspace_root
            if "cwd" in rec:
                rec["cwd"] = workspace_root
            if "terminal_title_identity" in rec:
                rec["terminal_title_identity"] = new_id.replace("-", "")[-12:]
    out = list(header)
    seq = max(r.get("sequence") or 0 for r in out)
    clock = max([r.get("recorded_at") or 0 for r in out] + [frame_children_max_ts]) + 1_000_000
    ctr = 0

    def fresh_id():
        nonlocal ctr
        ctr += 1
        return uuid7_at(clock // 1000, ctr)

    templates = template["turn_records"]
    for ti, (utext, atext) in enumerate(rendered_turns):
        run_id, task_id = fresh_id(), fresh_id()
        resp_id = f"resp_synth{ti:06d}"
        idmap = {donor_id: new_id, template["donor_run_id"]: run_id}
        if template.get("donor_task_id"):
            idmap[template["donor_task_id"]] = task_id
        if template.get("donor_response_id"):
            idmap[template["donor_response_id"]] = resp_id
        for r in templates:
            idmap[r["id"]] = fresh_id()
            srr = (r.get("payload") or {}).get("source_run_record_id")
            if srr and srr not in idmap:
                idmap[srr] = str(uuid.uuid4())
        accepted_seq = None
        for tmpl in templates:
            s = dump(tmpl)
            for old, new in idmap.items():
                s = s.replace(old, new)
            r = json.loads(s)
            seq += 1
            clock += 50_000
            r["sequence"] = seq
            r["recorded_at"] = clock
            pl = r.get("payload") or {}
            ev = pl.get("event") or {}
            if r.get("payload_type") == "runtime.user_intent.accepted":
                pl["refill_blocks"] = [{"kind": "text", "text": utext}]
                pl["model_messages"] = [{"content": [{"kind": "text", "text": utext}]}]
                accepted_seq = seq
            if isinstance(ev, dict) and ev.get("kind") == "started" and "prompt" in ev:
                ev["prompt"] = utext
            if r.get("payload_type") == "runtime.user_intent.materialized":
                pl["envelope_sequence"] = accepted_seq
                if isinstance(pl.get("outcome"), dict):
                    pl["outcome"]["cut_before"] = f"session:{new_id}:turn:{ti}"
            if isinstance(ev, dict) and ev.get("kind") == "reasoning_committed":
                ev.pop("encrypted_content", None)
                ev.pop("provider_item_id", None)
                ev["text"] = ""
                ev["message_id"] = str(uuid.uuid4())
            if isinstance(ev, dict) and ev.get("kind") == "assistant_message_committed":
                ev["text"] = atext if atext else "[source turn had no assistant text]"
                ev.pop("provider_item_id", None)
                ev["message_id"] = str(uuid.uuid4())
            if isinstance(ev, dict) and ev.get("kind") == "model_completed":
                if isinstance(ev.get("usage"), dict):
                    ev["usage"] = {k: 0 for k in ev["usage"]}
                ev["estimated_prompt_tokens"] = 0
            out.append(r)
        clock += 5_000_000
    if template.get("end_record"):
        r = json.loads(dump(template["end_record"]).replace(donor_id, new_id))
        seq += 1
        clock += 50_000
        r["sequence"] = seq
        r["recorded_at"] = clock
        r["id"] = fresh_id()
        out.append(r)
    return out


def frame_max_ts(frame_line):
    try:
        fr = json.loads(frame_line)
        return max(json.loads(ch["record_json"]).get("recorded_at") or 0 for ch in fr.get("children", []))
    except Exception:
        return 0
