# Agent Session Conversion Specification v0.1.0 (draft)

Status: draft seed. Condensed from the cross-environment clone part of the Agent
Session Manager (`ax`) specification v0.7.0; see `TRACEABILITY.md` for the
source of every section. Where this document marks a rule **UNVERIFIED**, the
rule is the expected behavior and an implementation MUST keep the matching
writer path disabled until the verification named in Section 14 succeeds.

Working name of the tool in this document: *the converter*. Schema URNs use the
placeholder namespace `urn:sessconv:`; the final namespace is an open question.

## 1. Scope, conformance, and language

### 1.1 Normative language

MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, MAY, and OPTIONAL are used as in
BCP 14 (RFC 2119, RFC 8174) when, and only when, they appear in capitals.
Tables and closed schemas are normative. Examples are normative only where they
are labeled so.

### 1.2 Subject

This specification defines how one agent CLI session (Claude Code, Codex CLI,
Muse, and other providers as extensions) is converted into a new session of the
same or another provider, or of the same provider under another account,
through a provider-neutral intermediate representation (IR).

The conversion pipeline is:

```text
source native store
  -> capture (raw bytes, closed manifest)
  -> normalize (IR: Canonical Session + Canonical Events)
  -> plan (strategy, profile, per-item dispositions)
  -> project (staged target native objects)
  -> staged read-back
  -> publish (new target session, collision-absent)
  -> live read-back (+ optional bounded resume smoke)
  -> Fidelity Report, Validation Report, Lineage Receipt
```

or, for archive-only output, `capture -> normalize -> archive Fidelity Report`.

### 1.3 Non-scope

This specification does not define: session orchestration, terminals or PTYs,
process supervision, multi-host replication, leases or ownership epochs, task
boards, host channels, authentication or login flows, or release governance.
It defines workspace data only to the extent that a converted session must
reference a workspace (Section 5.3); copying repositories is out of scope.

### 1.4 Conformance targets

- **Converter core**: owns policy, validation, hashing, sealing, the bundle
  chain, the Fidelity Report, and the publish transaction.
- **Reader** (source adapter): owns native discovery, inspection, snapshot
  proof, capture, and normalization for one provider environment.
- **Writer** (target adapter): owns projection planning, projection into an
  isolated sink, read-back of staged and live targets, publication into the
  live native store, and the resume plan for one provider environment.

One adapter MAY implement both roles. A claim of conformance names the role and
the exact Environment Tuple (Section 5.1).

## 2. Terms

| Term | Meaning |
| --- | --- |
| Source session | The existing native session being converted. It is read, never modified. |
| Target session | The new native session produced by a conversion. It has a new native identity. |
| Environment | One semantic native agent environment (for example `codex`, `claude-code`, `muse`), identified by an Environment Tuple. |
| Realm | The provider-plus-account context that produced a payload. Represented only by an opaque `realm_fingerprint`; never by a credential, token, or account name. |
| Foreign | Produced under a realm other than the target's realm. A payload from the same provider but another account is foreign. |
| IR | The Canonical Session and its Canonical Events (Section 7). |
| Capture | Byte-exact copy of the closed set of durable source objects plus its manifests (Section 6). |
| Projection | Rendering IR items into target-native objects (Section 9). |
| Bundle | The immutable, content-addressed chain of manifests and objects produced by one conversion (Section 11). |
| Provider-bound artifact | A native field or record whose validity depends on the producing provider or account (Section 14). |

## 3. Global invariants

The following invariants hold for every conversion. A violation is a refusal,
never a degraded success.

1. **Derivation, not move.** A conversion MUST leave every source byte, native
   identity, and source credential unchanged. It creates exactly one new target
   native identity per successful run. (The in-place account rewrite of
   Section 10.6 is the only exception and is opt-in.)
2. **No fabrication.** The converter MUST NOT invent native events, signatures,
   encrypted payloads, server item references, tool results, or usage. Every
   inserted item is a `synthesized` IR event naming the conversion operation.
3. **Credentials never travel.** Credential, machine-auth, runtime-state, and
   transient-lock classes are always excluded from capture (Section 6.1).
   Detecting credential material inside an included object is the refusal
   `credential_material_detected`.
4. **Foreign reasoning is opaque.** Foreign encrypted or signed reasoning is
   preserved byte-exact in the bundle and MUST NOT be decrypted, re-encoded,
   summarized, truncated, promoted to visible text, or written into target
   native records (Section 9.4).
5. **Foreign instructions are low-authority history.** Source system prompts,
   developer instructions, and instruction snapshots never become target
   instructions. Visible migration text has authority `user_context` only.
6. **Historical tools are inert.** A projected tool definition never registers a
   callable tool. A tool call without its result becomes aborted history.
   Pending actions are never re-executed.
7. **Source usage is not target accounting.** Token and cost records are
   descriptive history and never seed target usage counters.
8. **Failed reads are not absence.** A failed, partial, malformed, or over-limit
   read of a store, manifest, or adapter result is `integrity_failure` (or the
   more specific code), never "nothing there" and never permission for a
   fallback path.
9. **No blank fallback.** If the target cannot open the projected identity, the
   conversion fails. Starting a fresh empty target session and calling it the
   converted session is forbidden.
10. **Absolute paths are routing data.** A source absolute path is never a
    cross-environment identity. Workspace identity is the logical Workspace
    Binding (Section 5.3).
11. **Item gates, not scores.** An aggregate fidelity score never replaces the
    per-item disposition gates.

## 4. Common data rules

These rules are condensed from the ax common data model and apply to every
schema in this document.

- Every complete schema object contains `schema` and `schema_version`. Closed
  objects contain exactly the listed members; unknown members are rejected.
  Extension data lives only in `extensions`, a map whose keys are reverse-DNS
  names and which cannot change any normative meaning.
- Text is valid UTF-8 (NFC SHOULD). Map keys are unique UTF-8 strings.
  Floating-point numbers, NaN, Infinity, and duplicate keys are forbidden.
  `uint53` is a JSON integer in `[0, 9007199254740991]`.
- Timestamps are UTC RFC 3339 with at least millisecond precision. Converter-
  created identifiers are lowercase UUIDv7. Digests are `sha256:` plus 64
  lowercase hex characters.
- Bytes are a content-addressed blob or unpadded base64url.
- Relative paths use `/`, do not start with `/` or a drive prefix, and contain
  no empty, `.`, or `..` segment, NUL, or encoded separator.
- `T[n..m]` is an array with inclusive bounds; `sorted unique` means bytewise
  order of each item's RFC 8785 (JCS) encoding with no duplicates.
- **Identity rule.** The identity of an immutable object is the SHA-256 of the
  JCS form of the object with only its self-identity member omitted. JSON and
  CBOR (RFC 8949 Section 4.2.1 deterministic) encodings of one object MUST yield
  the same identity.
- **Blobs.** A blob is an uninterpreted byte sequence identified by SHA-256.
  Metadata lives in a Blob Descriptor (`urn:sessconv:schema:blob` 1.0.0,
  closed: `schema`, `schema_version`, `descriptor_id`, `blob_id`, `size`,
  `media_type` lowercase `type/subtype`, `chunks`). Writers fsync and verify size
  and digest before referencing a blob. Logs and metrics record digest, size,
  and media type only, never blob contents.

## 5. Identities

### 5.1 Environment Tuple

`EnvironmentTuple` contains exactly:

| Member | Type |
| --- | --- |
| `environment_id` | `[a-z][a-z0-9.-]{0,63}` |
| `environment_version` | string[1..128], the observed provider CLI version |
| `platform` | `linux\|macos\|windows\|wsl2` |
| `architecture` | `amd64\|arm64` |
| `store_schema_fingerprint` | digest of the observed native store schema facts |
| `adapter_version` | SemVer of the reader or writer |

It never contains executable provenance, account names, or credentials. WSL2
and native Windows are distinct platforms; evidence for one never establishes
the other.

### 5.2 Native Identity

`NativeIdentity` contains exactly:

| Member | Type |
| --- | --- |
| `native_session_id` | string[1..512] |
| `identity_kind` | `provider_native\|official_import\|continuation_context` |
| `logical_workspace_id` | UUIDv7 |
| `realm_fingerprint` | digest or null |
| `opaque_identity` | string[1..512] or null |
| `extensions` | reverse-DNS map |

It contains no credential, absolute source path used as identity, PID, socket,
token, or secret environment value. `realm_fingerprint` is an adapter-derived
digest that distinguishes realms (Section 2) without revealing them; null means
the realm is unknown, and an unknown realm MUST be treated as foreign.

### 5.3 Workspace Binding

`WorkspaceBinding` contains exactly `logical_workspace_id:UUIDv7`,
`cwd_relative:string[1..4096]`,
`repository_remote_fingerprints:sorted unique digest[0..128]`,
`branch:string[1..1024]|null`, `head_digest:digest|null`,
`index_digest:digest|null`, `working_tree_digest:digest|null`, and
`extensions`.

`cwd_relative` is normalized beneath a workspace root chosen by the operator for
the target. The binding grants no filesystem authority. A writer maps it to a
target absolute path (and, for Claude Code, to a target project key) at
projection time; it MUST NOT copy the source absolute path or a source
path-derived key as identity. The converter does not copy workspace contents;
the target workspace MUST already exist, and a mismatch between the binding
digests and the target workspace is a finding the operator policy decides.

## 6. Capture

### 6.1 Capture classes

Every candidate native object has exactly one class:

| Class | Meaning | Capture |
| --- | --- | --- |
| `durable_payload` | Session log records, subagent logs, tool outputs | included |
| `durable_index_required` | Index entries the provider needs to discover the session | included |
| `durable_sidecar` | Durable companion data | included, or excluded with reason |
| `derived_cache_optional` | Rebuildable caches | included or excluded; never required |
| `credential` | Tokens, keys, OAuth material, API keys | always excluded |
| `machine_auth` | Login state, keyring entries, account profiles | always excluded |
| `runtime_state` | Sockets, PIDs, live process facts | always excluded |
| `transient_lock` | Lock files, live SQLite WAL/SHM | always excluded |
| `unknown` | Not classified by the reader | makes `raw_complete=false`; blocks `maximal_safe` |

### 6.2 Capture Item

`CaptureItem` contains exactly `native_item_key:string[1..512]`, `class`,
`disposition:included|excluded`, `blob_descriptor_id:digest|null`,
`byte_count:uint53|null`, `exclusion_reason:string[1..128]|null`, and
`extensions`. Included requires both content members non-null and a null reason.
Excluded requires null content members and a non-null reason.

`native_item_key` is a sanitized store-relative key, never an absolute path.

### 6.3 Raw Object Manifest

`urn:sessconv:schema:raw-object-manifest` 1.0.0 contains exactly:

| Field | Type and constraint |
| --- | --- |
| `schema` / `schema_version` | exact URN / `1.0.0` |
| `raw_object_manifest_id` | identity digest |
| `operation_id` | UUIDv7 conversion operation |
| `source_environment` | exact probed `EnvironmentTuple` |
| `source_native_session_id` | sanitized string[1..512] |
| `source_identity_digest` | digest of the canonical sanitized `NativeIdentity` |
| `capture_plan_digest` | digest of the validated capture plan |
| `entries` | `RawObjectEntry[0..65536]`, sorted unique by native item key |
| `total_bytes` | uint53, sum of entry byte counts |
| `extensions` | reverse-DNS map |

`RawObjectEntry` contains exactly `native_item_key`, `class` (one of
`durable_payload|durable_index_required|durable_sidecar|derived_cache_optional|unknown`),
`byte_count`, `blob_id`, and `blob_descriptor_id`. Excluded classes are
forbidden in entries.

### 6.4 Capture Manifest

`urn:sessconv:schema:capture-manifest` 1.0.0 contains exactly:

| Field | Type and constraint |
| --- | --- |
| `schema` / `schema_version` | exact URN / `1.0.0` |
| `capture_manifest_id` | identity digest |
| `operation_id` / `bundle_id` | UUIDv7 / UUIDv7 |
| `source_ref` | string[1..512], sanitized operator-facing reference to the source |
| `source_environment` / `source_identity` | exact tuple / sanitized `NativeIdentity` |
| `capture_plan_digest` | digest |
| `capture_boundary` | closed `CaptureBoundary` |
| `source_raw_object_manifest_id` | the raw manifest containing all and only included objects |
| `items` | `CaptureItem[0..65536]`, sorted by native item key, one per plan candidate |
| `excluded_classes` | sorted unique class[0..9], exactly the classes of excluded rows |
| `raw_complete` | core-derived boolean; true only after full plan/object reconciliation and no `unknown` item |
| `created_at` | timestamp |
| `extensions` | reverse-DNS map |

### 6.5 Capture Boundary and snapshot proof

A capture is valid only for a stable source. `CaptureBoundary` is a closed
union:

- `kind=stable` with `proof:StableSnapshotProof`;
- `kind=unstable_archive` with `source_generation`, `pre_capture_digest`,
  `post_capture_digest`, `reason_code=source_not_quiescent`,
  `operator_explicit=true`, and `target_projection_forbidden=true`. Only the
  core constructs it, only for archive-only output, and it MUST NOT enter a
  target branch.

`StableSnapshotProof` contains exactly
`proof_kind:closed_store|immutable_snapshot|verified_log_prefix|provider_quiescence`,
`source_generation:string[1..512]`, `snapshot_identity_digest:digest|null`,
`pre_capture_digest`, `post_capture_digest`, `input_blocked:boolean`,
`foreground_idle:boolean`, `background_idle:boolean`, and `extensions`.

- Pre- and post-capture digests MUST be equal.
- `closed_store` and `provider_quiescence` require all three booleans true and a
  null snapshot identity; `immutable_snapshot` and `verified_log_prefix`
  require a non-null snapshot identity.
- File-size equality is never proof.
- A source that is still running MAY be captured only as an immutable snapshot
  or a verified log prefix.
- The source generation is rechecked immediately before publication; a change
  is `source_changed_during_conversion` (Section 15).

## 7. Intermediate representation (IR)

### 7.1 Canonical Session

`urn:sessconv:schema:canonical-session` 1.0.0 contains exactly:

| Field | Type and constraint |
| --- | --- |
| `schema` / `schema_version` | exact URN / `1.0.0` |
| `canonical_session_id` | identity digest |
| `logical_session_id` | UUIDv7, stable across conversion hops of one lineage |
| `source_environment` / `source_native_session_id` | exact tuple / string[1..512] |
| `title` | string[1..4096] or null |
| `workspace` | closed `WorkspaceBinding` |
| `actors` | `Actor[1..1024]`, unique by actor ID |
| `event_ids` | ordered unique digest[1..1000000] |
| `head_event_ids` | sorted unique digest[1..1024], all in `event_ids` |
| `created_at` / `updated_at` | timestamp or null |
| `extensions` | reverse-DNS map |

`Actor` contains exactly `actor_id:UUIDv7`, `kind:main|subagent|external`,
`parent_actor_id:UUIDv7|null`, `name:string[1..512]|null`,
`source_native_id:string[1..512]|null`, `model:string[1..512]|null`, and
`extensions`. Exactly one actor is `main`; only it has a null parent.

### 7.2 Canonical Event

`urn:sessconv:schema:canonical-event` 1.0.0 contains exactly `schema`,
`schema_version`, `event_id` (identity digest), `logical_session_id`,
`ordinal:uint53` (contiguous from zero), `parents:sorted unique digest[0..64]`
(causal parents; this preserves branching and subagent graphs),
`actor_id:UUIDv7`, `turn_id:UUIDv7|null`, `kind`, `timestamp:timestamp|null`,
`visibility:public|projection|internal|opaque`, `payload` (closed, selected by
kind), `source_evidence`, and `extensions`.

The closed event-kind registry is:

`session_started`, `instruction_snapshot`, `user_message`,
`assistant_message`, `reasoning_summary`, `opaque_reasoning`,
`tool_definition_snapshot`, `tool_call`, `tool_result`, `approval_request`,
`approval_response`, `plan_update`, `progress`, `usage`, `rate_limit`,
`file_change`, `compaction`, `turn_started`, `turn_completed`, `turn_aborted`,
`subagent_started`, `subagent_completed`, `error`, `migration_checkpoint`,
`session_finished`, `opaque_event`.

Payloads contain only their registered typed facts. The per-kind payload
registries are not yet written (see `UNRESOLVED_QUESTIONS.md`); until then a
reader MUST NOT emit a payload member that a later registry could contradict,
and MUST route anything it cannot type into `opaque_event`.

### 7.3 Content blocks

Message-like payloads carry content blocks of exactly these types: `text`,
`json`, `image`, `audio`, `document`, `resource_link`, `redacted`, `opaque`.
Content is inline (at most 64 KiB) or a Blob Descriptor reference. Text over
64 KiB becomes a blob reference, never a truncation.

### 7.4 Source Evidence

`SourceEvidence` contains exactly `environment:EnvironmentTuple`,
`native_session_id`, `native_event_id:string[1..512]|null`,
`native_type:string[1..512]|null`,
`raw_refs:sorted unique RawReference[0..65536]`,
`capture_status:exact|partial|synthesized|unavailable`,
`reason_codes:sorted unique string[1..128][0..128]`,
`conversion_operation_id:UUIDv7|null`, and `extensions`.

`RawReference` contains exactly `manifest_id`, `blob_descriptor_id`,
`offset:uint53`, and `length:uint53`, addressing the exact source bytes.

`synthesized` requires a null native event ID and a non-null conversion
operation ID; every other status requires a null operation ID.

### 7.5 Normalization rules

A reader MUST apply these rules; each is independently testable.

1. **Unknown native records** become `opaque_event` with `visibility=opaque`,
   a whole-record raw reference, and reason `unknown_native_event`. Nothing
   attributable is dropped, guessed, or re-typed.
2. **Foreign encrypted or signed reasoning** becomes `opaque_reasoning` with
   `visibility=opaque` and a protection fact `encrypted|signed`, preserved
   byte-exact as a blob. Plain-text reasoning summaries that the provider
   stores separately and in the clear MAY become `reasoning_summary`; whether a
   given provider stores such text is per-provider and, unless Section 14 says
   verified, to be verified.
3. **Tools.** `tool_definition_snapshot` never registers a callable tool. A
   `tool_call` is resolved `completed` only together with its `tool_result`;
   otherwise both are marked `aborted`, and the projection treats them with
   reason `unsafe_pending_action`.
4. **Usage** goes to the descriptive `usage` kind only; target accounting is
   always zero.
5. **Instructions** become `instruction_snapshot` history with low authority;
   they never change the target's effective instructions.
6. **Framing errors** (unparseable JSON, duplicate members, lone surrogates,
   trailing data) refuse normalization with `source_corrupt`. They are not
   routed to `opaque_event`, because the record boundary itself is unknown.
7. Identical captured bytes MUST produce byte-identical IR.

## 8. Fidelity

### 8.1 Dispositions

The closed dispositions are:

| Disposition | Meaning |
| --- | --- |
| `exact` | The target carries the item with the same native meaning and bytes or a lossless re-encoding. |
| `semantic` | The target carries the same meaning in a different native form. |
| `summarized` | The target carries a shorter rendering; detail is lost but disclosed. |
| `opaque_preserved` | The bundle keeps the item byte-exact; the target does not interpret it (and, for foreign payloads, does not receive it). |
| `synthesized` | The item did not exist in the source; the conversion inserted it. |
| `omitted` | The item is deliberately not carried to the target. |
| `unrecoverable` | The item existed but cannot be recovered from the captured evidence. |

### 8.2 Reasons

Every non-`exact` disposition names one or more reasons from this closed core
set, or a reverse-DNS extension reason that cannot redefine a core code:

`target_no_equivalent`, `source_not_persisted`, `source_truncated`,
`source_corrupt`, `foreign_encrypted_payload`,
`foreign_signature_unverifiable`, `account_bound_reference`,
`target_schema_constraint`, `target_context_limit`, `target_size_limit`,
`target_version_gate`, `official_importer_loss`, `graph_flattened`,
`unsafe_pending_action`, `credential_excluded`, `secret_policy`,
`operator_policy`, `unsupported_media_type`, `unknown_native_event`,
`derived_index_rebuilt`.

`account_bound_reference` is new in this specification: a bare identifier that
points at a server-side object of the source realm (for example the Muse
`reasoning_replay.id` of Section 14.1). All others are carried from ax.

### 8.3 Disposition record

`FidelityDispositionRecord` contains exactly
`source_item_key:string[1..512]`, `source_class:string[1..128]`,
`source_evidence_ids:sorted unique digest[1..65536]`,
`canonical_object_id:digest|null`, `target_locator:string[1..1024]|null`,
`disposition`, `reason_codes:sorted unique string[1..128][0..128]`,
`explanation:string[1..4096]`,
`staged_evidence_object_ids:sorted unique digest[0..65536]`,
`live_evidence_object_ids:sorted unique digest[0..65536]`, and `extensions`.

- `exact` requires an empty reason set; every other disposition requires at
  least one reason.
- `synthesized` requires a null canonical source object; every other row traces
  to captured source evidence.
- `opaque_preserved` for a foreign payload requires a null `target_locator`.

`FidelityCounts` contains exactly the seven uint53 members named after the
dispositions.

### 8.4 Fidelity Report

`urn:sessconv:schema:fidelity-report` 1.0.0 contains exactly:

| Field | Type and constraint |
| --- | --- |
| `schema` / `schema_version` | exact URN / `1.0.0` |
| `fidelity_report_id` | identity digest |
| `scope` | `archive\|target` |
| `operation_id` / `bundle_id` | UUIDv7 / UUIDv7 |
| `source_snapshot_digest` | digest |
| `capture_manifest_id` / `canonical_session_id` | exact inputs |
| `projection_plan_id` | digest; null exactly for archive |
| `source_environment` | exact tuple |
| `target_environment` | exact tuple; null exactly for archive |
| `profile` | closed profile; `archive_only` exactly for archive |
| `required_dispositions` | closed map class -> sorted unique non-empty disposition set |
| `forbid_reasons` | sorted unique string[0..128] |
| `dispositions` | `FidelityDispositionRecord[1..1000000]`, sorted by source item key, synthesized rows after source rows |
| `counts` | `FidelityCounts` derived from the rows |
| `event_kind_counts` | map of every event kind to `FidelityCounts` |
| `content_block_counts` | map of every block type to `FidelityCounts` |
| `byte_counts` | map of every disposition to uint53 |
| `reason_counts` | sorted map reason -> uint53>0 |
| `raw_bundle_complete` / `canonical_complete` | core-derived booleans |
| `target_semantically_continuable` / `target_natively_resumable` | core-derived booleans; both false for archive |
| `staged_read_back_evidence_manifest_id` / `live_read_back_evidence_manifest_id` | both null for archive, both non-null for target |
| `extensions` | reverse-DNS map |

Reconciliation is total: every captured candidate reconciles once to raw
evidence or an exclusion; every raw item to an IR item or a normalization
disposition; every IR item to staged/live target evidence or a target
disposition. Every Capture Manifest item and Canonical Event occurs in exactly
one non-synthesized row. Aggregates are derived from rows and cannot replace
them. The report names no later object (validation report, receipt).

## 9. Projection

### 9.1 Strategies

| Strategy | Meaning |
| --- | --- |
| `same_environment_native_rewrite` | Same provider, possibly another account. Native records are copied and only provider-bound artifacts are rewritten (Section 14). |
| `target_native_writer` | Another provider. The writer emits target-native records for each IR item it can represent. |
| `target_official_import` | Another provider that offers a documented import surface; the writer prepares input for that importer. |
| `continuation_context` | A new target session whose history is delivered as low-authority user context (Section 9.6), not as native records. Explicitly non-native historical fidelity. |
| `archive_only` | No target. Produces the archive branch only. |

Selection order (from the reference implementation, normative here): an
explicit archive request wins; then an explicit continuation request; then, for
a same-environment pair, `same_environment_native_rewrite`; for a
cross-environment pair with an available official importer,
`target_official_import`; otherwise `target_native_writer`. If the selected
native strategy's writer is not admitted (Section 12.4), the converter MUST
refuse with `unsupported_environment_tuple` unless the operator explicitly
requested `continuation_context`; it MUST NOT silently downgrade.

### 9.2 Profiles

Profiles are `strict_exact`, `maximal_safe` (default), `compact`,
`messages_only`, and `archive_only`. A profile is applied after the strategy
decided the base disposition:

| Profile | Rule |
| --- | --- |
| `strict_exact` | Any non-`exact` item refuses the plan with `projection_loss_unacceptable`. |
| `maximal_safe` | Base dispositions pass through. Requires `raw_complete=true`. |
| `compact` | `semantic` becomes `summarized` with added reason `target_context_limit`. |
| `messages_only` | Only `user_message`, `assistant_message`, and `text`/`json`/`redacted` blocks survive; everything else becomes `omitted` with added `operator_policy` (plus `unsupported_media_type` for media blocks). |
| `archive_only` | Archive branch only; no Projection Plan exists. |

### 9.3 Base disposition rules

The planner decides each IR item's base disposition in this order:

1. `opaque_reasoning` -> `opaque_preserved`, reason
   `foreign_signature_unverifiable` if signed, otherwise
   `foreign_encrypted_payload`. This applies to every strategy when the payload
   is foreign, including same-provider account moves.
2. `opaque_event` or an `opaque` block -> `opaque_preserved`,
   `unknown_native_event`.
3. Aborted `tool_call`/`tool_result` -> `summarized`, `unsafe_pending_action`.
4. Strategy `continuation_context` -> `semantic`, `target_no_equivalent`.
5. Strategy `target_official_import`: complete tool history
   (`tool_call`, `tool_result`, `tool_definition_snapshot`) -> `semantic`,
   `official_importer_loss`; `subagent_started`/`subagent_completed` ->
   `semantic`, `graph_flattened`.
6. Otherwise `exact`, subject to writer-declared limits: a writer that cannot
   represent a kind natively MUST plan it `semantic` or `omitted` with
   `target_no_equivalent` (and `graph_flattened` when a DAG is linearized).

The planner never emits `synthesized` for a source item and never emits
`unrecoverable` for an item that exists in the IR. `usage` and `rate_limit`
items are planned `omitted` with `target_no_equivalent` unless the writer can
store them as inert, clearly-historical annotations, in which case `semantic`.

### 9.4 Provider-bound payload rule

For every strategy other than `archive_only`:

- A writer MUST NOT place a foreign encrypted payload, a foreign signature, or a
  foreign `account_bound_reference` into any target native record.
- The record that carried it MAY be kept with that member removed when the
  provider is known to accept the stripped form (Section 14). If the provider
  requires the member (for example a signature the target validates), the
  carrying item is `omitted` or `summarized` instead; re-signing is impossible
  and MUST NOT be attempted.
- The payload itself stays `opaque_preserved` in the bundle.

### 9.5 Projection Plan

`urn:sessconv:schema:projection-plan` 1.0.0 contains exactly:

| Field | Type and constraint |
| --- | --- |
| `schema` / `schema_version` | exact URN / `1.0.0` |
| `projection_plan_id` | identity digest |
| `operation_id` / `bundle_id` | UUIDv7 / UUIDv7 |
| `request_digest` / `source_snapshot_digest` | digests |
| `capture_manifest_id` / `canonical_session_id` | exact inputs |
| `canonical_event_ids` | ordered unique digest[0..65536], equal to IR order |
| `source_environment` / `target_environment` | exact tuples |
| `expected_target_native_session_id` | newly allocated string[1..512] |
| `target_workspace` | exact `WorkspaceBinding` |
| `strategy` | one of the four non-archive strategies |
| `strategy_rationale` | string[1..4096] |
| `fidelity_profile` | `strict_exact\|maximal_safe\|compact\|messages_only` |
| `required_dispositions` / `forbid_reasons` | exact request policy |
| `item_mappings` | `ProjectionItemMapping[1..1000000]`, one per captured/IR item |
| `target_operations` | `ProjectionTargetOperation[1..65536]`, ordered by sequence |
| `expected_resources` | `ExpectedTargetResource[0..65536]` |
| `synthesized_events` | `SynthesizedProjectionEvent[0..65536]` |
| `security_exclusions` | sorted unique capture class[0..9] |
| `resource_limits` | `ResourceLimits` |
| `read_back_plan` / `resume_plan` / `rollback_plan` | closed components below |
| `required_capabilities` | sorted unique string[1..64] |
| `fidelity_basis_digest` | digest of item mappings, policy, and predicted counts |
| `source_adapter_build_digest` / `target_adapter_build_digest` / `converter_build_digest` | observed digests |
| `extensions` | reverse-DNS map |

Components:

- `ProjectionItemMapping`: `source_item_key`, `canonical_object_id|null`,
  `target_resource_keys:sorted unique string[0..65536]`,
  `expected_disposition`, `reason_codes`, `extensions`.
- `ProjectionTargetOperation`: `sequence:uint53>0`,
  `action:create_directory|write_blob|write_native_record|rebuild_index`,
  `resource_keys[1..65536]`, `depends_on_sequences` (lower sequences only; a
  DAG), `extensions`.
- `ExpectedTargetResource`: `operation_sequence`, `resource_key`,
  `kind:blob|directory`, `mode:uint32[0..4095]|null`,
  `expected_blob_id:digest|null`, `extensions`.
- `SynthesizedProjectionEvent`: `canonical_event_id`,
  `insertion_after_event_id|null`,
  `purpose:migration_checkpoint|summary|delimiter`, `extensions`.
- `ReadBackPlan`: `modes=[staged,live]`, `require_identity_match=true`,
  `require_workspace_match=true`, `require_semantic_marker=true`.
- `ResumeProjectionPlan`: `opens_existing_identity=true`,
  `allow_blank_fallback=false`, `bounded_continuation_turn_required:boolean`.
- `RollbackPlan`: `required=true`, `retain_through=live_validated`,
  `forbidden_after_first_resume=true`.
- `ResourceLimits`: `max_objects>0`, `max_total_bytes>0`,
  `max_single_object_bytes>0`, `max_events`, `max_target_resources`.

`target_collision_policy` is fixed to `must_be_absent`: the expected target
native ID and every target resource key MUST be absent from the live store at
publication.

The plan never predicts a Fidelity Report ID; the report is derived from
read-back evidence. Projection never writes to a live store.

### 9.6 Migration Checkpoint and visible projection

Every target-branch conversion inserts one synthesized `migration_checkpoint`
event. `urn:sessconv:schema:migration-checkpoint` 1.0.0 contains exactly
`migration_checkpoint_id`, `checkpoint_id:UUIDv7`, `operation_id`,
`bundle_id`, `created_at`, `source_snapshot_digest`, `canonical_session_id`,
`projection_plan_id`, `source_environment`, `source_native_session_id`,
`source_logical_session_id`, `target_environment`, `target_native_session_id`,
`target_logical_session_id`, `previous_checkpoint_id|null`,
`previous_lineage_receipt_id|null`, `projection_policy_digest`,
`fidelity_basis_digest`, `report_locator` (bundle ID plus logical path
`reports/fidelity.json`, not a digest), `preserved_classes`,
`transformed_classes`, `archived_classes`, `unrecoverable_classes`,
`visible_projection`, and `extensions`.

`VisibleMigrationProjection` contains exactly `authority=user_context`,
`target_event_ids:sorted unique digest[1..64]`,
`escaped_text:string[1..65536]`, and `extensions`. Its text is built from typed
fields, each escaped as a JSON string literal so that it round-trips to the
input exactly; control characters, quotes, and markup delimiters never cross
raw. It is never an assistant reply, a system instruction, or an
authorization. For `continuation_context`, this visible projection (plus
referenced history blobs) is the only carrier of history into the target.

### 9.7 Projected Object Manifest

`urn:sessconv:schema:projected-object-manifest` 1.0.0 contains exactly
`projected_object_manifest_id`, `operation_id`, `projection_plan_id`,
`target_environment`, `expected_target_native_session_id`,
`entries:ProjectedObjectEntry[0..65536]` (sorted by sequence/key; blob entries
carry `mode`, `byte_count`, `blob_id`, `blob_descriptor_id`; directory entries
carry sequence, key, kind, mode), `total_bytes`, and `extensions`. Entries
partition the plan's expected resources exactly. The manifest grants no live
authority.

## 10. Write transaction and read-back

### 10.1 States

```text
resolving -> captured -> normalized -> planned -> projected
-> staged_validated -> publishing -> published -> live_validated -> completed
archive: normalized -> archived
rollback (before first resume): publishing|published -> rolling_back -> rolled_back
```

The converter persists each state and the identities it introduces before the
next external effect, so that a restart either completes the same target or
rolls it back. After any ambiguous result it reconciles by reading the target
store; it never allocates a second target identity for the same operation.

### 10.2 Stage and staged read-back

The writer projects into a fresh isolated sink. The writer's `read-back`
operation then parses the staged objects as the target provider would and
returns a Read-Back Evidence Manifest (Section 10.4) in mode `staged`.

### 10.3 Publish and live read-back

Before publishing, the core rechecks the source generation and the absence of
the target identity and resources. The writer publishes with
no-replace semantics (create-only; unrelated sessions and index entries are
merged, never replaced). The writer then reads the live target back
independently in mode `live`.

Where the provider maintains a derived index, the writer either merges a
single entry with a version-aware writer or lets the provider rebuild it; a
rebuilt index is reported with `derived_index_rebuilt`.

### 10.4 Read-Back Evidence Manifest

`urn:sessconv:schema:read-back-evidence-manifest` 1.0.0 contains exactly
`read_back_evidence_manifest_id`, `operation_id`, `mode:staged|live`,
`projection_plan_id`, `projected_object_manifest_id`,
`expected_target_native_session_id`, `observed_target_native_session_id`
(equal), `observed_environment`, `parsed_event_count`,
`parsed_head_ids:sorted unique string[0..1024]`, `workspace_binding`,
`structural_digest`, `evidence_objects:EvidenceObject[0..65536]`, and
`extensions`. `EvidenceObject` is
`evidence_kind:native_sample|parser_trace|marker_observation`, `media_type`,
`byte_count`, `blob_id`, `blob_descriptor_id`. Staged and live manifests are
distinct objects and MUST NOT be relabeled.

The semantic marker is the migration checkpoint (Section 9.6); read-back MUST
observe it in the target.

### 10.5 Validation Report and resume

`urn:sessconv:schema:validation-report` 1.0.0 contains exactly
`validation_report_id`, `operation_id`, `projection_plan_id`,
`projected_object_manifest_id`, both read-back manifest IDs,
`fidelity_report_id`, expected and observed target native IDs,
`target_environment`, booleans `staged_structural_valid`,
`live_structural_valid`, `semantic_marker_valid`, `identity_valid`,
`workspace_binding_valid`, `resume_surface_valid`,
`source_generation_revalidated`, `findings:AdapterFinding[0..4096]`, `valid`,
and `extensions`. `valid=true` requires every boolean true, equal native IDs
and tuple, and no `error` finding.

The writer's `resume-plan` returns argv, a relative cwd, and the names (never
values) of required environment variables; argv names the trusted CLI and
contains the explicit target identity exactly once. `resume_surface_valid`
means the provider's own discovery finds the target by explicit ID. A bounded
continuation turn (one short real turn) is OPTIONAL at run time, REQUIRED as
admission evidence for a writer (Section 12.4), and, when run, ends the
rollback window.

### 10.6 In-place account rewrite (opt-in)

For `same_environment_native_rewrite` when only the account changes, an
operator MAY request in-place rewrite instead of a new target identity. This is
the only mode that modifies a source store. It requires: the provider session
stopped (closed-store proof), a full backup copy of every touched object
written before the change, an atomic replace of each touched file, a refusal
for symlinked or non-regular files, and a verified rule set for the provider
(Section 14). Unverified providers MUST be refused. The Fidelity Report for
this mode uses the same dispositions; the backup location is recorded as an
extension, never its contents.

## 11. Bundle chain and lineage

### 11.1 Generations

A bundle is an immutable chain of manifests. Only these chains are legal:

```text
G0 capture -> G1 canonical -> A2 archive (terminal)
G0 capture -> G1 canonical -> G2 projection -> G3 published
```

| Generation / stage | Adds |
| --- | --- |
| G0 `capture` | `capture_manifest_id` |
| G1 `canonical` | `canonical_session_id`, `canonical_event_ids` |
| A2 `archive` | archive `fidelity_report_id`, `archive_validation_evidence_digest`, `raw_complete`, `canonical_complete` |
| G2 `projection` | `projection_plan_id`, `migration_checkpoint_id`, `projected_object_manifest_id`, `staged_read_back_evidence_manifest_id` |
| G3 `published` | `live_read_back_evidence_manifest_id`, target `fidelity_report_id`, `validation_report_id`, `lineage_receipt_id` |

The Bundle Manifest (`urn:sessconv:schema:bundle-manifest` 1.0.0) contains
`manifest_id`, `bundle_id`, `operation_id`, `generation:0..3`, `stage`,
`previous_manifest_id|null`, `content` (exactly the members of its row),
`created_at`, and `extensions`.

Stages cannot be skipped; operation and bundle IDs stay constant; one
predecessor cannot have two byte-different successors (an A2/G2 fork is an
integrity failure); a byte-identical replay returns the existing identity.
Digest edges point only to lower generations or prior hops; digest cycles are
forbidden. Rollback retains the highest verified generation and its reports.

### 11.2 Lineage Receipt

`urn:sessconv:schema:lineage-receipt` 1.0.0 contains exactly
`lineage_receipt_id`, `operation_id`, `bundle_id`, `source_native_session_id`,
`source_environment`, `target_native_session_id`, `target_environment`,
`migration_checkpoint_id`, `projection_plan_id`, `fidelity_report_id`,
`validation_report_id`, `previous_lineage_receipt_id|null`, `published_at`,
and `extensions`. Lineage is descriptive, never authorization. Multi-hop
conversions (A -> B -> C) chain receipts and SHOULD project from the richest
ancestor IR still available rather than from an already-lossy intermediate
target.

## 12. Reader and writer adapter protocol

### 12.1 Bindings

The operations below are the contract between the core and an adapter. An
adapter MAY be in-process (library) or out-of-process. The out-of-process
binding is newline-delimited JSON over stdio: request envelope exactly
`protocol=urn:sessconv:protocol:adapter`, `protocol_version`, `request_id`,
`operation`, `deadline`, `body`; success echoes the first four plus `ok=true`
and `body`; failure echoes them plus `ok=false` and a Structured Error
(Section 15). Frames are at most 8 MiB; large data is referenced by Blob
Descriptor or manifest ID. Invalid envelopes are
`adapter_protocol_error`. Stderr is diagnostic, redacted, and never parsed.

### 12.2 Operations

| Operation | Role | Authority / effect |
| --- | --- | --- |
| `manifest`, `probe` | both | none |
| `discover`, `inspect` | reader | read-only declared native roots |
| `snapshot-proof` | reader | read-only |
| `capture-plan` | reader | fresh plan sink |
| `capture`, `normalize` | reader | fresh raw / IR sink |
| `projection-plan`, `project` | writer | fresh plan / target-object sink; never a live store |
| `read-back` | writer | read-only staged or live target authority |
| `publish` | writer | create-only write into the live target store, limited to plan resources |
| `unpublish` | writer | removes exactly the resources it published, only before first resume |
| `validate`, `resume-plan` | writer | none |
| `doctor` | both | none |

Every adapter answers every name; an unavailable operation returns
`capability_unavailable` and an unknown name returns `operation_unknown`.
Every state-bearing call carries an `AdapterCallContext` (operation ID,
environment ID, Environment Tuple, adapter manifest digest, executable digest,
request digest) that the success echoes byte-for-byte.

Read authorities name roots the core opened, a purpose
(`source_native|target_staged|target_live`), and an expiry. Object authorities
name a purpose, `read|fresh_sink`, and hard object/byte limits. Partial,
malformed, over-limit, or escaped results are errors, never absence. The core
independently validates, rehashes, and seals every candidate object the adapter
returns; an adapter's self-reported digest is never trusted.

The request and success bodies follow ax Session Adapter 1.0.0 (see
`TRACEABILITY.md`) with ax-only members removed. Key constraints retained:
`inspect` requires zero ambiguities before capture; `capture-plan` and
`capture` reconcile plan keys exactly; `normalize` returns only IR candidates
whose raw references lie inside the Capture Manifest closure;
`projection-plan` forbids `archive_only` and assigns every IR item one
disposition; `project` returns actual counts that reconcile with the plan;
`read-back` mode is fixed by the authority and cannot be relabeled.

### 12.3 Manifest, probe, capabilities

The Adapter Manifest is closed: `environment_id`, `display_name`,
`adapter_version`, `environment_version_range`, `platforms`, `roles`
(`reader`, `writer`), `operations`, `capability_names`, `extensions`.

The Probe returns the observed Environment Tuple and one value per capability:
`status:available|conditional|unsupported|unknown`, `enabled:boolean`,
`evidence:documented|probed|accepted_test|provider_contract|inferred|acceptance_required|none`,
`detail`. Only `available` permits `enabled=true`. `unknown` MUST NOT be
rewritten as `unsupported`, and `conditional` MUST NOT be advertised as
`available`. Missing, extra, or contradictory facts invalidate the probe.

Capability names: `native_discovery`, `stable_snapshot`, `raw_capture`,
`canonical_read`, `canonical_write`, `native_read_back`, `native_resume_plan`,
`official_import`, `same_environment_lossless_clone`, `tool_history`,
`usage_history`, `compaction_history`, `subagent_graph`,
`opaque_reasoning_roundtrip`, `workspace_binding`, and (new)
`account_rewrite`.

### 12.4 Admission

- A **source read** requires available `native_discovery`, `stable_snapshot`,
  `raw_capture`, and `canonical_read` for the exact tuple. Unknown sources MAY
  be archived only after safe byte enumeration.
- A **target write** requires available `canonical_write` or
  `official_import`, `native_read_back`, `native_resume_plan`, and
  `workspace_binding` for the exact tuple, plus current passing fixture
  evidence and a passing bounded-resume smoke for that tuple and strategy.
  Unknown targets never write.
- `account_rewrite` requires a verified provider-bound artifact table
  (Section 14) and tests for the exact tuple.
- No `--force` flag, experimental profile, or environment-name-only match
  bypasses these gates.

Admission evidence is recorded in a Supported Pair Registry (one entry per
direction and exact tuple: strategies exercised, fixture suite digest, resume
smoke result, known fidelity limits, accepted/revoked status). Source-read
entries carry strategy `archive_only` only and no smoke; target-write entries
carry no `archive_only`. Whether the registry is signed is an open question.

## 13. Native-store contract matrix

Labels: **A** available from documented or accepted evidence (runtime probe
still required); **C** conditional, disabled until the named acceptance passes;
**U** unsupported; **?** unknown. Facts below come from ax v0.7.0 Section 8.2
and its Muse research note; anything not stated there is "to be verified".

| Provider | Durable identity and location | Resume / import surface | Materialization rule | Required exclusions |
| --- | --- | --- | --- | --- |
| Codex CLI | Session UUID; root `~/.codex/sessions`; rollout JSONL per session (a date-sharded `YYYY/MM/DD/rollout-<uuid>.jsonl` layout appears in an ax example; to be verified). Source absolute cwd is metadata. | `codex resume SESSION_ID`; `codex fork SESSION_ID`. Official import: to be verified. | Stage only the closed session objects identified; compute the destination cwd mapping; validate discovery by explicit ID; merge without replacing unrelated sessions. Portable store: C. | Auth files, config secrets, MCP tokens, logs not required by the session, live processes, locks, SQLite/WAL/SHM, sockets. |
| Claude Code | Session UUID; root `~/.claude/projects/<project-key>/` with a provider-computed project key. Exact file layout and record schema: to be verified. | `claude --resume SESSION_ID`, `--continue`, `--fork-session`. | Derive the destination project key from the target workspace mapping; never copy the source key as identity; stage the closed session plus documented companion data; validate explicit UUID resume. Portable store: C. | OAuth/API credentials, settings secrets, MCP auth, PTY state, PID/lock/socket files, caches, unproven companion databases. |
| Muse | Session UUID; `$XDG_DATA_HOME/muse/sessions/YYYY/MM/DD/<uuid>/` (default below `~/.local/share`) containing `session.jsonl`, `subagent/<uuid>/session.jsonl`, `tool-outputs/`; also `.session.lock` and `cron.db`. Resolver scans the store by UUID; no global index required (probed on 0.1.0). | `muse resume <uuid>`, `--last`, picker, `muse exec --session-id <uuid>`. `muse export` exists (offline, one-way); no native import. `muse trace inspect --session-log <file> --format json` reports `load_status`. | Stage the complete closed durable directory, omit transient files, validate, resume explicitly. Portable store: false. | `~/.config/muse/auth.json`, keys, login state, `.session.lock`, sockets/tokens, live WAL/SHM/locks, updater/plugin caches. `cron.db` is durable but not portable: a session with active or non-empty scheduled work MUST be refused for target write. |
| Other providers | Declared by adapter and exact probe. | Declared by adapter. | Every capability starts `?`/disabled until acceptance evidence exists. | Common exclusions plus provider-specific ones. |

Gemini CLI, Antigravity CLI, and Pi rows exist in ax v0.7.0 Section 8.2 and can
be imported as extension providers; they are not part of this seed.

## 14. Provider-bound artifacts

Dispositions in these tables: **keep** (copied unchanged), **strip** (member
removed, record kept), **re-sign impossible** (target validates a signature the
converter cannot produce; the carrying item cannot be written natively),
**synthesize** (converter creates a fresh target-realm value), **omit** (not
written to the target; preserved in the bundle unless it is a credential).

"Same provider" means `same_environment_native_rewrite` (account move).
"Cross provider" means any other target strategy. In every case the stripped or
omitted payload is `opaque_preserved` in the bundle, except credentials, which
are never captured.

### 14.1 Muse (verified 2026-11-10 on two real sessions, account move only)

| Field or record | Why it is bound | Same provider (account move) | Cross provider |
| --- | --- | --- | --- |
| `encrypted_content` of `reasoning_committed` records (`payload.event.kind == "reasoning_committed"`) | Encrypted reasoning issued to the producing account; another account cannot replay it | strip; keep the record | omit (`opaque_preserved`, `foreign_encrypted_payload`) |
| Nested `encrypted_content` inside context-compaction and projection checkpoints (`replay_model_messages[].content[]`, `model_messages[]`, `resume_state` copies) | Same blob, copied into checkpoints; without stripping, the resumed turn fails with HTTP 400 `encrypted_content was not issued to this caller` | strip every nested occurrence | omit |
| `id` of nested `reasoning_replay` items that no longer carry encrypted content | Bare reference to a server-side item of the old account; fails with HTTP 400 `Referenced reasoning item ... not found` | strip the `id`; keep the item (`account_bound_reference`) | omit |
| The `reasoning_replay` items and `reasoning_committed` records themselves | Muse's replay check needs them | keep. Deleting them makes Muse report that the log cannot be replayed; it then starts a new session that re-reads the old log and consumes quota | omit (no target equivalent) |
| Other records of `session.jsonl`, subagent logs, `tool-outputs/` | Not account-bound as far as verified | keep | normalize to IR; project per Section 9 |
| `workspace_root`, route-fact `cwd`, historical PID and terminal metadata | Machine-local history, not identity | keep as inert history | omit or `semantic` inert history; never authority; workspace remapped via Workspace Binding |
| Session UUID | Native identity | keep for in-place rewrite; a new UUID for a derived copy is to be verified | synthesize a new target-native ID |
| `.session.lock` (contains PID) | Machine-local, transient | exclude | exclude |
| `cron.db` (+ WAL/SHM) | Durable scheduled work; copying can duplicate jobs | keep in place (in-place rewrite); for a derived copy: refuse if non-empty | omit with `target_no_equivalent`; refuse if active scheduled work exists |
| `~/.config/muse/auth.json`, keys, login state | Credentials | never touched | never captured |

Verified procedure facts (account move): stop the session processes first; back
up the whole session directory; after the rewrite, `muse trace inspect ...
--format json` must report `"load_status": "loaded"`; the new account must be
the active login before resume; the backup is kept until the resumed session has
completed at least one turn. Verified only for the Muse versions in use at that
date; the exact version tuple is to be recorded by the first adapter.

### 14.2 Codex CLI (UNVERIFIED)

| Field or record | Why it is bound | Same provider (account move) | Cross provider |
| --- | --- | --- | --- |
| `encrypted_content` of rollout `reasoning` items | Expected: encrypted reasoning issued to the producing account (same mechanism as Muse) | expected: strip; keep the item. UNVERIFIED | omit (`opaque_preserved`, `foreign_encrypted_payload`) |
| Item or response IDs that may reference server-side objects | Expected: may be `account_bound_reference` like Muse `reasoning_replay.id`; which members exist is to be verified | expected: strip when the encrypted payload is stripped. UNVERIFIED | omit |
| Plain reasoning summary text, if stored | Not encrypted; existence and location to be verified | keep | `reasoning_summary` -> `semantic` at most |
| Session UUID, rollout file name | Native identity | to be verified (in-place vs new UUID) | synthesize |
| Absolute cwd in session metadata | Machine-local | keep as metadata | remap via Workspace Binding |
| Auth files, config secrets, MCP tokens, SQLite/WAL/SHM, locks, sockets | Credentials / runtime | exclude | exclude |

### 14.3 Claude Code (UNVERIFIED)

| Field or record | Why it is bound | Same provider (account move) | Cross provider |
| --- | --- | --- | --- |
| `signature` on `thinking` blocks | Provider-signed reasoning; the target validates the signature, and the converter cannot produce one | expected: the signature may stay valid across accounts of the same provider, or may not; to be verified. If not: re-sign impossible, so the whole `thinking` block is omitted, not kept unsigned | re-sign impossible: omit the block (`opaque_preserved`, `foreign_signature_unverifiable`) |
| Thinking text inside a `thinking` block | Bound to its signature | travels with the block; never promoted to visible text | omit; never promoted to visible text or an assistant message |
| Server item IDs (message and request IDs) | Expected: server-side references of the producing account | to be verified whether resume dereferences them; if yes, strip or synthesize | synthesize fresh IDs only if the target format requires them; never reuse source IDs as server references |
| Project directory key | Derived from the absolute workspace path | recompute for the destination workspace | compute for the destination workspace |
| Session UUID | Native identity | to be verified | synthesize |
| OAuth/API credentials, settings secrets, MCP auth, PID/lock/socket files, caches | Credentials / runtime | exclude | exclude |

Any other encrypted, redacted, or signed reasoning variant a provider stores is
handled by the rule of Section 9.4 and is to be verified per provider.

### 14.4 Verification required before enabling a writer

For each UNVERIFIED row, the acceptance evidence MUST show, on the exact tuple:
a real session from account A converted under account B (and, for cross
provider, into the target provider); the rewritten log loads under the
provider's own inspection command where one exists; one bounded resume turn
answers; and a negative control (the unstripped log) fails with the expected
provider error. Without this evidence the row stays disabled.

## 15. Errors and refusal codes

Errors are a closed Structured Error object: `schema`, `schema_version`,
`code` (stable lower snake case), `message` (human text; automation never
branches on it), `exit_code` (the value assigned to `code` below),
`retryable` (true only when the identical request may be retried safely),
optional `operation_id`, `details` (typed, redacted), and `extensions`.

| Exit | Codes |
| ---: | --- |
| 4 | `source_not_found`, `source_ambiguous` |
| 6 | `unsupported_environment_tuple`, `operation_unknown`, `capability_unavailable`, `target_resume_invalid` |
| 9 | `source_corrupt`, `bundle_integrity_failed`, `integrity_failure`, `credential_material_detected`, `unsafe_path` |
| 11 | `source_not_quiescent`, `source_changed_during_conversion` |
| 12 | `target_collision`, `target_prepare_failed`, `target_validation_failed`, `target_publish_failed`, `transaction_unknown` |
| 13 | `adapter_protocol_error`, `adapter_process_failed`, `adapter_timeout` |
| 16 | `projection_loss_unacceptable`, `unsafe_pending_action`, `scheduled_work_present` |

`transaction_unknown` is a parked ambiguous effect, never success or absence.
`target_collision` and `scheduled_work_present` are new in this specification
(ax expressed them as policy constants and Muse-row prose).

## 16. Security

- Session content is untrusted data. Nothing in a source session becomes an
  instruction to the converter, to an adapter, or to the target with more than
  `user_context` authority.
- Adapters read only the roots the core opened and write only to fresh sinks or,
  for `publish`, to plan resources. Paths are resolved beneath an allowed root
  (symlinks included) before any write; escapes are `unsafe_path`.
- Network is not required for conversion and SHOULD be denied to adapters
  unless declared.
- Logs, metrics, and reports carry digests, sizes, and media types, never
  content, credentials, or account identifiers.
- Bundles contain sensitive project history. Storage and sharing of bundles is
  the operator's responsibility; secure deletion is a separate operation.

## 17. Worked example: Muse to Claude Code

This example is normative for its rule references and illustrative for its
values. Claude Code writer facts are UNVERIFIED (Section 14.3), so in the
current state of evidence the admitted path is `continuation_context`; the
`target_native_writer` path is shown for what it would preserve once admitted.

**Step 1. Read the native store.** The Muse reader `inspect`s the source by
UUID under `$XDG_DATA_HOME/muse/sessions/YYYY/MM/DD/<uuid>/`. It finds
`session.jsonl`, two `subagent/<uuid>/session.jsonl`, `tool-outputs/*`,
`.session.lock`, and `cron.db`. Inspection reports zero ambiguities. The
operator has stopped the Muse session; `snapshot-proof` returns
`proof_kind=closed_store` with equal pre/post digests and all idle booleans
true. `cron.db` is empty; if it held active jobs the conversion would stop with
`scheduled_work_present`.

**Step 2. Capture.** `capture-plan` classifies: logs and tool outputs
`durable_payload`; `cron.db` `durable_sidecar` (excluded, reason
`target_no_equivalent`); `.session.lock` `transient_lock` (excluded);
`auth.json` is outside the session root and never enumerated. `capture` copies
included bytes into blobs and returns the Raw Object Manifest; the core seals
the Capture Manifest with `raw_complete=true` (no `unknown` items) and bundle
generation G0.

**Step 3. Canonicalize to IR.** `normalize` produces one main actor and two
subagent actors, and events in source order: `session_started`,
`user_message`, `assistant_message`, `tool_call`/`tool_result` pairs
(`completed`), each `reasoning_committed` encrypted blob as
`opaque_reasoning` (`protection=encrypted`), `compaction` for checkpoint
records (their nested encrypted copies referenced as raw ranges, not
duplicated), `usage`, `subagent_started`/`subagent_completed`, and any Muse
record the reader does not know as `opaque_event`. The last tool call, which
was interrupted, has no result and is `aborted`. G1 is sealed.

**Step 4. Choose strategy and profile.** Source `muse` and target
`claude-code` differ, Claude Code offers no admitted official importer, so the
selection rule yields `target_native_writer`. If the Claude Code writer is not
admitted for the exact tuple, the converter refuses with
`unsupported_environment_tuple`; the operator re-runs with an explicit
`continuation_context` request. Profile: `maximal_safe` (default; allowed
because `raw_complete=true`).

**Step 5. Plan and project to Claude Code's native JSONL.** The writer
allocates a new Claude Code session UUID, computes the destination project key
from the target Workspace Binding, and plans per Section 9.3:

| IR item | `target_native_writer` (once admitted) | `continuation_context` (admitted today) |
| --- | --- | --- |
| `user_message`, `assistant_message` text | `exact` or `semantic` as native user/assistant records | `semantic` (`target_no_equivalent`), inside the visible migration text |
| Completed `tool_call`/`tool_result` | `semantic` as inert historical tool records, if the target format can hold foreign tool names; otherwise `summarized` | `semantic`, rendered as text history |
| Aborted tool call | `summarized` (`unsafe_pending_action`); never re-executed | same |
| `opaque_reasoning` (Muse encrypted) | `opaque_preserved` (`foreign_encrypted_payload`); nothing written; no `thinking` block is created because no valid signature can exist | same |
| `compaction` | `summarized` or `semantic` (`target_no_equivalent`) | `semantic` |
| `usage` | `omitted` (`target_no_equivalent`); target accounting zero | same |
| Subagent events | `semantic` with `graph_flattened` if the writer linearizes | `semantic`, `graph_flattened` |
| `opaque_event` | `opaque_preserved` (`unknown_native_event`) | same |
| `instruction_snapshot` | `semantic` low-authority history; never a target system prompt | same |
| `migration_checkpoint` | `synthesized` | `synthesized`; carries the history |

Under `target_native_writer`, the writer emits one target-native record per
mapped item plus the synthesized migration checkpoint (the exact Claude Code
record schema is to be verified and is not defined here). Under
`continuation_context`, it emits a new session whose only history is the
synthesized migration checkpoint with its escaped `user_context` text. G2 is
sealed after staged read-back passes.

**Step 6. Read back.** Staged read-back parses the staged JSONL as Claude Code
would, confirms the expected session UUID, event count, heads, workspace
binding, and the migration-checkpoint marker. The core rechecks the Muse source
generation and the absence of the target UUID, then `publish` creates the files
create-only. Live read-back repeats the checks against the live store;
`resume-plan` returns `claude --resume <new-uuid>` with a relative cwd. An
optional bounded turn confirms the session answers. The source Muse session is
unchanged.

**Step 7. Fidelity report.** The target Fidelity Report lists every captured
item exactly once. Expected outcome: `target_semantically_continuable=true`;
`target_natively_resumable=true` (the new session opens by explicit ID);
counts dominated by `semantic`/`exact` messages, `opaque_preserved` reasoning,
`omitted` usage, one `synthesized` checkpoint, `summarized` aborted tool call,
and exclusions for `.session.lock` and `cron.db`. G3 adds the Validation Report
and Lineage Receipt.

**What survives natively, plainly:** with an admitted native writer, user and
assistant messages, and possibly completed tool history, become real Claude Code
records. Muse's reasoning never does: it is encrypted for the Muse account and
Claude Code would require its own signature, so it stays only in the bundle.
With `continuation_context`, nothing from Muse is a native Claude Code record:
the whole history is one block of user context, and the model continues from
it as from a briefing, not as from its own prior turns.

## Appendix A. Schema registry

| Contract | URN | Version |
| --- | --- | --- |
| Adapter protocol | `urn:sessconv:protocol:adapter` | 1.0.0 |
| Blob Descriptor | `urn:sessconv:schema:blob` | 1.0.0 |
| Raw Object Manifest | `urn:sessconv:schema:raw-object-manifest` | 1.0.0 |
| Capture Manifest | `urn:sessconv:schema:capture-manifest` | 1.0.0 |
| Canonical Session | `urn:sessconv:schema:canonical-session` | 1.0.0 |
| Canonical Event | `urn:sessconv:schema:canonical-event` | 1.0.0 |
| Fidelity Report | `urn:sessconv:schema:fidelity-report` | 1.0.0 |
| Projection Plan | `urn:sessconv:schema:projection-plan` | 1.0.0 |
| Projected Object Manifest | `urn:sessconv:schema:projected-object-manifest` | 1.0.0 |
| Migration Checkpoint | `urn:sessconv:schema:migration-checkpoint` | 1.0.0 |
| Read-Back Evidence Manifest | `urn:sessconv:schema:read-back-evidence-manifest` | 1.0.0 |
| Validation Report | `urn:sessconv:schema:validation-report` | 1.0.0 |
| Bundle Manifest | `urn:sessconv:schema:bundle-manifest` | 1.0.0 |
| Lineage Receipt | `urn:sessconv:schema:lineage-receipt` | 1.0.0 |
| Structured Error | `urn:sessconv:schema:error` | 1.0.0 |
