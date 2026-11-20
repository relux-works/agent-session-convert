# Traceability

Non-normative. Maps each section of `SPEC.md` to its source in the ax v0.7.0
specification (`bundle/ax-spec/SPEC.md`, 16 908 lines), its research note,
the reference Go implementation (`bundle/ax-impl/internal/...`), and the
account-transfer skill (`bundle/skill/`). Line ranges refer to the ax SPEC.md
file as delivered in the bundle.

Disposition codes:

- **copied**: wording or closed schema kept, with ax-specific identifiers
  replaced (for example `urn:ax:` to `urn:sessconv:`, AX Session to source/target
  session).
- **condensed**: same rules, shortened, ax-only members removed.
- **new**: not in ax; added for the standalone subject.

## Section mapping

| New SPEC section | Source (ax SPEC.md section, lines) | Other sources | Disposition |
| --- | --- | --- | --- |
| 1.1 Normative language | 1.1 (21-31) | | condensed |
| 1.2 Subject, pipeline | 13.14 intro (10322-10330); 13.14.4 state diagram (10989-10997) | STANDALONE_TO_AX_TRACEABILITY.md (pipeline overview row) | condensed; pipeline rewritten without leases/checkpoints |
| 1.3 Non-scope | 1.2 (32-74) as the inverse | | new |
| 1.4 Conformance targets | 7.8 ownership paragraph (3740-3747) | impl `cloneplanning/doc.go`, `cloneproject/doc.go` (core vs adapter split) | condensed; Provider 2 materializer role merged into the writer |
| 2 Terms | 2.1 (394-423) only for vocabulary | | new; "realm" and "foreign" are new definitions |
| 3 Global invariants | 13.14 intro (10322-10330); 13.14.1 normalization sentence (10390-10393); 13.14.2 visible-text rule (10582-10588); 13.14.4 "failed read is integrity failure" (11148-11152); 7.8 "never absence or fallback" (3779-3782, 3846-3849); 1.6 absolute-path rule (290-296) | STANDALONE_TO_AX_TRACEABILITY.md rows 1.5, 7.5 | condensed from scattered rules; invariant 9 from `ResumeProjectionPlan.allow_blank_fallback=false` (10712-10716) |
| 4 Common data rules | 1.6 (244-391); 10.2 Blob Descriptor (4851-4904) | | condensed |
| 5.1 Environment Tuple | 7.8 Probe paragraph (3870-3883); 8.4 WSL2 rule (4183-4184) | impl `sessadapter` (DecodeTuple) | copied |
| 5.2 Native Identity | 13.14.1 `NativeIdentity` (10398-10406) | | copied; `backend_realm_fingerprint` renamed `realm_fingerprint` and given the foreign-by-default rule (new) |
| 5.3 Workspace Binding | 13.14.1 `WorkspaceBinding` (10407-10416); 8.2 Claude project-key rule (4117) | research note "absolute source workspace is not the session identity" | copied; workspace replication (ax 12) dropped |
| 6.1 Capture classes | 13.14.1 capture classes (10348-10353); 16.2 exclusions (15394-15433) | impl `clonebundle/captureitem.go` | condensed; "meaning" column new |
| 6.2 Capture Item | 13.14.1 `CaptureItem` (10467-10477) | | copied |
| 6.3 Raw Object Manifest | 13.14.1 (10331-10339 summary; 10417-10436 table) | impl `clonebundle/rawmanifest.go` | copied |
| 6.4 Capture Manifest | 13.14.1 (10340-10352 summary; 10440-10466 table) | impl `clonebundle/capturebuild.go` | condensed; Capture Source Basis `ax_session` branch dropped, `external_source_ref` kept as `source_ref`; `created_by_host_id` dropped |
| 6.5 Capture Boundary | 13.14.1 (10361-10364, 10478-10500); 13.14.4 source recheck (11102-11105) | impl `clonebundle/boundary.go`, `clonesnap` | copied; "running source" sentence from STANDALONE_TO_AX_TRACEABILITY.md row 11.2; error renamed `source_changed_during_conversion` |
| 7.1 Canonical Session | 13.14.1 (10365-10372, 10499-10522) | impl `clonebundle/session.go` | copied |
| 7.2 Canonical Event, kinds | 13.14.1 (10373-10389, 10520-10533) | impl `clonebundle/event.go` | copied; note on missing per-kind payload registries is new (impl `clonebundle/doc.go` states the same bound) |
| 7.3 Content blocks | 13.14.1 (10384-10389) | impl `cloneproject/overflow.go` | copied |
| 7.4 Source Evidence | 13.14.1 (10534-10547) | | copied; `core_operation_id` renamed `conversion_operation_id` |
| 7.5 Normalization rules | 13.14.1 (10389-10393) | impl `cloneproject/doc.go` (projection rules list) | condensed from implementation doc into normative rules; rule 6 (framing errors refuse) from the same doc's stated bounds |
| 8.1 Dispositions | 13.14.2 (10550) | | copied list; meanings column new |
| 8.2 Reasons | 13.14.2 (10551-10553) | | copied; `account_bound_reference` new (from skill finding) |
| 8.3 Disposition record | 13.14.2 (10596-10615) | impl `clonefidelity/record.go` | copied; null `target_locator` rule for foreign `opaque_preserved` is new |
| 8.4 Fidelity Report | 13.14.2 (10554-10561 prose; 10616-10649 table) | impl `clonefidelity/report.go`, `clonereconcile` | copied; `adapter_attestations` dropped |
| 9.1 Strategies | 13.14.2 (10562-10566) | impl `cloneplanning/strategy.go` (SelectStrategy priority) | condensed; selection order made normative; no-silent-downgrade rule new |
| 9.2 Profiles | 13.14.2 (10562-10563) | impl `cloneplanning/plan.go` (applyProfile) | new as normative text, derived from implementation |
| 9.3 Base disposition rules | 13.14.1 (10390-10393) | impl `cloneplanning/plan.go` (baseMapping); `cloneplanning/effects.go` | new as normative text, derived from implementation; usage/rate-limit rule and writer-limit rule 6 new |
| 9.4 Provider-bound payload rule | 13.14.1 "foreign encrypted/signed reasoning is opaque-preserved" (10392) | `bundle/skill/SKILL.md` | new |
| 9.5 Projection Plan | 13.14.2 (10567-10574 prose; 10650-10721 tables) | impl `cloneplan/plan.go`, `operations.go`, `resources.go`, `mapping.go` | condensed; `TransactionPlan` folded into a fixed collision rule; `RollbackPlan.forbidden_after_provider_commit` replaced by `forbidden_after_first_resume`; `required_contracts` dropped |
| 9.6 Migration Checkpoint | 13.14.2 (10582-10588 prose; 10779-10813 schema) | impl `cloneplanning/visible.go` | condensed; `hop_id`, `source_checkpoint_id` (AX checkpoint) dropped |
| 9.7 Projected Object Manifest | 13.14.2 (10722-10736) | impl `cloneplan/manifest.go` | copied |
| 10.1 States | 13.14.4 state diagram (10989-10997) | | condensed; provider transaction, checkpoint sealing, and lineage-published states dropped |
| 10.2-10.3 Stage, publish, read-back | 13.14.4 (11102-11114); 8.2 Codex merge-without-replace rule (4116) | STANDALONE_TO_AX_TRACEABILITY.md rows 10.2-10.5, 8.10 | condensed; ax Provider `materialize` / `materialize-commit` replaced by writer `publish` |
| 10.4 Read-Back Evidence Manifest | 13.14.2 (10575-10581, 10737-10754) | impl `clonereadback` | copied |
| 10.5 Validation Report, resume | 13.14.2 (10755-10778); 7.8 `resume-plan` row (3845) | impl `clonereadback/report.go` | copied; `target_provider_manifest_id` dropped; run-time vs admission smoke split is new |
| 10.6 In-place account rewrite | none (ax forbids source mutation) | `bundle/skill/SKILL.md`, `strip-reasoning.py` (backup, atomic replace, symlink refusal) | new |
| 11.1 Bundle generations | 13.14.3 (10842-10903) | impl `clonebundle/generation.go` | condensed; G3 validation and G4 committed merged into one G3 `published`; provider facts, target Checkpoint, and AX events dropped |
| 11.2 Lineage Receipt | 13.14.2 (10589-10595, 10814-10841) | | condensed; AX record IDs, G3/G4 naming, operator signature dropped; multi-hop sentence from STANDALONE_TO_AX_TRACEABILITY.md row 11.3 |
| 12.1 Bindings | 7.8 envelope (3749-3755); 7.2 framing limits (2799-2889, by reference) | | condensed; in-process binding new; error codes renamed `adapter_*` |
| 12.2 Operations | 7.8 operation registry (3760-3772), body registry (3829-3846), shared types (3783-3828) | impl `sessadapter` | condensed; `publish` and `unpublish` new (ax gives these to Provider 2); full body tables not re-copied (open question) |
| 12.3 Manifest, probe, capabilities | 7.8 (3854-3903); 8.1 label rules (4097-4111) | | condensed; `provider_id` merged into `environment_id`; `roles` and capability `account_rewrite` new |
| 12.4 Admission | 7.8 target-write rule (3916-3924); 13.14.5 tuple registry (11183-11265) | | condensed; signed SSHSIG registry replaced by an unsigned Supported Pair Registry (signing is an open question) |
| 13 Native-store matrix | 8.2 (4112-4129); 8.3-8.4 labels (4130-4185) | `.research/260819_muse-antigravity-native-store-contracts.md` lines 49-70, 109, 204-214; ax provider capture example (3415-3440) for the Codex rollout path | condensed; Codex, Claude Code, Muse rows only; Gemini, Antigravity, Pi, Qwen rows dropped (named as extensions) |
| 14.1 Muse provider-bound artifacts | 8.2 Muse row (4119) | `bundle/skill/SKILL.md`, `strip-reasoning.py` (verified rules); research note lines 66-70 (route facts, lock, cron.db) | new; rows marked verified come from the skill only |
| 14.2 Codex provider-bound artifacts | 8.2 Codex row (4116) | `bundle/skill/SKILL.md` "Codex and Claude (not verified)" | new; UNVERIFIED |
| 14.3 Claude Code provider-bound artifacts | 8.2 Claude row (4117) | `bundle/skill/SKILL.md` "Codex and Claude (not verified)" | new; UNVERIFIED |
| 14.4 Verification required | 19.3 acceptance-suite principle (16023-16085); Appendix B (16539-16564) | skill check steps 4-6 | new |
| 15 Errors | 15.1 Structured Error (15095-15203, shape only); clone codes (15155-15172); exits (15204-15226) | | condensed; Structured Error trimmed (no session ID); `target_collision`, `target_publish_failed`, `scheduled_work_present` new; `session_adapter_*` renamed `adapter_*` |
| 16 Security | 16.1-16.4 (15373-15482); 10.2 log rule (4858-4859) | STANDALONE_TO_AX_TRACEABILITY.md rows 15.1-15.5 | condensed; trusted-mesh model dropped |
| 17 Worked example | none | all of the above | new |
| Appendix A Schema registry | 1.5 registry rows (131-133, 161-172) | | condensed; URN namespace replaced |

## Dropped from ax v0.7.0 and why

| ax content | Lines | Why dropped |
| --- | --- | --- |
| Terminal backends (4, 4.A-4.E, 7.A) | 896-1488, 3703-3737 | Terminals and PTYs are not part of converting a stored session. |
| Session Record, Session Event, leases, checkpoints, derived states (5) | 1489-2419 | ax ownership model; a converter has a source and a target, not a managed session lifecycle. |
| Configuration (6) | 2420-2764 | ax daemon configuration. |
| Provider Protocol 2 runtime operations, quiescence, profile mapping (7.1-7.7) | 2765-3702 | Process control of live agents. Only the trust idea (adapter executable digest) is kept. |
| Directory Node protocol (7.9), directory records (10.8), directory continuation (13.15) | 3925-4094, 6475-7288, 11266-11400 | Mesh-wide session catalog. |
| Task-board integration (9) | 4186-4829 | Out of scope. |
| Transfer Manifest, Materialization Plan 1/2, Journal 2/3, tombstones (10.3-10.7, 13.14.4 tables) | 4905-6474, 10904-11101 | Multi-host replication and rollback-token custody. Replaced by a single create-only publish with read-back. |
| Mesh RPC, host channels (11) | 7289-9017 | Out of scope. |
| Workspace replication (12) | 9018-9171 | The converter references a workspace; it does not copy one. |
| Lifecycle flows other than clone (13.1-13.13) | 9172-10321 | ax operations (launch, attach, takeover, fork, resume). |
| Clone Session Events and derived-state edge (13.14.5 first part) | 11154-11182 | ax event log. |
| Signed Supported Environment Tuple Registry, SSHSIG publication | 11183-11265 | Kept as an unsigned registry concept; signing and release authority are governance. |
| CLI surfaces and result versions (14) | 11401-15092 | ax CLI. The converter's CLI is not specified yet. |
| Observability, implementation release, publication governance (18-20) | 15718-16325 | ax project governance. |
| Appendices A, C, D | 16326-16538, 16565-16908 | ax review history, evidence references, fixture catalog. |

## Deliberate deviations from ax

1. **Source mutation.** ax forbids changing the source in a clone. This spec
   keeps that as the default and adds an opt-in in-place account rewrite
   (10.6), because that is the verified Muse procedure.
2. **Foreign reasoning in the target.** ax says foreign encrypted/signed
   reasoning is `opaque_preserved` but does not state whether the target
   receives it. This spec states that it does not (9.4, 8.3), following the
   verified Muse failure modes.
3. **New reason** `account_bound_reference` and **new codes**
   `target_collision`, `target_publish_failed`, `scheduled_work_present`.
4. **Bundle generations** reduced from five (G0-G4) to four (G0-G3) because
   there is no provider transaction or target Checkpoint.
5. **Writer owns publish.** In ax, live-store mutation belongs to Provider 2
   and the ax materializer; here the writer adapter publishes create-only.
