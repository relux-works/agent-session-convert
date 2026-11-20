# Implementation plan — owner decisions recorded 2026-11-19

Source of truth for the format remains `SPEC.md` (ax seed). This file records how we build it,
in which order, and the decisions the owner made in the 2026-11-19 session. Implementation lives
in this repository; the `skill-agent-session-transfer` skill becomes a thin Curator-distributed
skill that installs this CLI.

## Decisions (owner, 2026-11-19)

1. IR-first. Refactor the proven direct Claude->Muse pair onto the spec pipeline
   (Reader -> Capture -> Canonical IR -> Planner -> Writer -> staged/live read-back) before adding
   providers. No second direct pair converter.
2. Environments in scope: Codex, Muse, Claude Code, Antigravity (Pi as extension candidate; it is
   also the worker harness). First admitted pair: Claude Code -> Muse (done as the direct reference;
   becomes the regression pair after the IR refactor).
3. Qualification: a matrix harness must prove, per exact environment tuple (provider CLI version,
   store version), that conversion still works for every admitted pair — the admission experiment of
   SPEC 14.4 automated: fixture session per provider, convert, provider inspection, one bounded
   resume turn answering a question only the converted history can answer, negative control where
   applicable. A provider CLI upgrade that breaks a cell turns the matrix red before users hit it.
4. Tool history: lossy by budget, maximal value retention, configurable. v1 reference behavior is
   deterministic (no LLM): whitespace collapsed, first N chars (default 240) + truncation marker in
   replay; bundle IR keeps up to 20k chars per item; the retained source log is byte-exact.
   Measured on the reference conversion (post-compact suffix): 578k chars of tool input+result,
   <=180k kept in replay tool lines; code/diffs beyond the cap are lost from replay (not from the
   bundle/source). Planned value-preserving formats to evaluate in the planner (per tool kind,
   under a total replay token budget, all with bundle blob references the resumed agent can open):
   - shell: full command (capped separately), exit code, stdout head+tail, sha256, blob ref;
   - edit/write: path, line ranges, unified diff capped by hunks, blob ref to the full payload;
   - read: path + ranges read, blob ref (never inline file bodies by default);
   - errors: never truncated below the error line itself;
   - dedup repeated identical results; keep-full threshold for short payloads.
   Profiles: `strict_exact` (refuse on any loss), `maximal_safe`, `compact` (default until the
   budget allocator above lands), `messages_only`.
5. Distribution (later phase, designed for from the start): signed + notarized release binaries in
   GitHub release pipelines; Homebrew tap for macOS/Linux; versioned releases. The converter core
   stays dependency-light and offline (no network during conversion).
6. Execution: producer workers run on `pix` (Pi) with `gpt-6.2-sol`; the reviewer of record for
   spec/design is `gpt-6.2-astra` on pix. Orchestrator and stations are stable Matrix workbenches
   with their own a2a identities and one shared work room (see station plan; setup pending owner
   confirmation of names).
7. Swarma/Curator integration (seamless lane migration): converting a lane must also carry its
   relux wiring, not just the transcript. Target UX sketch (owner):
   `curator run muse from claude --resume <session-id>` — Curator resolves the environment profile
   (root contexts, skills, hooks, a2a identity, wake/bind), invokes the converter as a module
   (like curator-run is a separate module/process behind a Curator plugin), publishes the converted
   session into the target store, then launches the target runtime with the profile applied and
   the lane rebound (a2a bind/hooks, subscriptions intact). Open design points: which of this is
   the converter's job vs the profile's (converter: transcript + fidelity + resume-plan argv;
   profile: identities, hooks, wake sidecars, memory/MCP migration), and how preflight refuses a
   half-migrated lane (single-brain rule: source process stopped before target bind).

## Current state (2026-11-19)

- Direct reference converter Claude->Muse exists in `skill-agent-session-transfer`
  (`scripts/convert-claude-to-muse.py`, template capture, Swift black-box tests, proven end-to-end on
  a 373MB / 183k-record production session: trace `loaded` staged+live, verify turn answered from
  converted history). Its writer consumes in-memory turns, not the IR file — that is the refactor.
- Muse admission facts proven: permission frame is checksum-bound (must be minted by the muse CLI
  for the new UUID); a 14-record templated text turn replays; foreign reasoning/provider ids must
  be synthesized/stripped, records kept.

## Phases

- P0 IR v1 schema: typed payloads for the used subset (session, user/assistant messages, tool
  call/result, opaque_reasoning, compaction, attachment, usage, subagent, opaque_event; content
  blocks; source evidence). Golden fixtures. Resolves SPEC UNRESOLVED Q6 for the subset.
- P1 Refactor Claude->Muse onto IR v1 in this repo (reader, planner with budget profiles, writer
  consuming IR only, read-back). Keep the skill repo's behavior bit-compatible where practical;
  port/extend tests. CLI: `agent-session-convert convert --from claude --to Muse ...`.
- P2 Qualification matrix harness (fixtures per provider, admission probes, version tuples) in CI
  with a manual/secret lane for real resume turns.
- P3 Readers, then writers per environment, each admitted by the matrix: Codex, Antigravity, Pi;
  Muse as a reader (account move folds into the same CLI). Universal `continuation_context`
  writer available for every target from P1.
- P4 Curator integration design -> plugin (`curator run <to> from <from> --resume <id>`), lane
  migration preflight (single-brain, subscriptions, hooks per runtime), profile-carried contexts.
- P5 Release engineering: signed/notarized binaries, GitHub releases, Homebrew tap; skill repo
  becomes the Curator skill that installs the CLI.

## Companion state conversion (owner addition, 2026-11-19, from the live lane migration)

The reference lane migration showed the transcript is only part of a lane. The converter toolchain
must also convert, per harness and with fidelity dispositions like the transcript:

- **Memory.** Claude project memory (`~/.claude/projects/<key>/memory/*.md` + `MEMORY.md` index)
  maps to Muse `personal_project` scope (`~/.local/share/muse/memory/projects/<ws>-<hash>/`),
  which is workspace-bound, not session-bound and not global: every Muse session opened in that
  workspace sees it, other workspaces do not. Mapping must be scope-explicit (project vs personal),
  never silently promote project notes to personal scope; stale notes are marked, not dropped.
  Codex/Pi/Antigravity memory stores get adapters as their readers land.
- **Hooks.** Claude `settings.local.json` hooks (SessionStart/UserPromptSubmit/Stop commands plus
  `env`, permission denies) need a per-runtime equivalence table; for a2a doorbells the sanctioned
  path is `a2a hook install --runtime <target>`, never hand-copied JSON. Custom non-a2a hooks are
  ported only when a target equivalent event exists; otherwise `omitted` with a named gap.
- **Monitors, cron and scheduled work.** Inventory always; migrate only under explicit policy —
  two live copies of a schedule is a duplicate-effect incident. Until per-runtime migration is
  proven, a target write refuses active scheduled work (SPEC `scheduled_work_present`).
- **MCP servers, skills, permission mode, goals, attachments.** Inventory + target availability
  check in the fidelity report; migration where the target has a sanctioned importer/config,
  named gaps otherwise (e.g. Claude-only built-in skills).

## Curator / a2a seams as verified 2026-11-19

- Umbrella grammar: `curator run <env> --profile <p> -- <native args>`; envs `claude_code`
  (alias `claude`), `codex_cli` (alias `codex`), `pi`, `muse`; `opencode` refused.
- `--profile` resolves the Curator environment fragment (`curator env resolve --repair`):
  root contexts, skills, model/effort, permission mode. One profile per Werkstatt conversation.
- `--a2a <identity>` is a separate hosted-only doorbell request (heartbeat 1m, 6 wakes/hour);
  profile does not by itself supply the a2a identity — the launch/Werkstatt record binds them, and
  status keeps manager evidence and a2a evidence separate. For Claude the launcher itself runs
  `a2a hook install --runtime claude` against safely staged settings and verifies env+hooks before
  start; Codex binding/long-lived owners belong to the session manager.
- Gaps to close with a2a-source / curator-run owners: (a) `a2a identity ensure` accepts only
  `--runtime claude|codex|none` although `a2a hook`/`bind` know `muse`; (b) the Muse doorbell/Monitor
  route in curator-run is a proposed, capability-gated amendment (docs only), so Muse lanes cannot
  yet get the same automatic a2a binding Claude lanes get; (c) a conversion step has no place in
  the launch pipeline yet — candidate seam: between profile resolution and BuildLaunch, gated by a
  `--from <env>` request that runs the converter and feeds the resulting target session id to the
  resume selector; preflight enforces single-brain (source stopped) and subscription preservation.
- Lane migration candidates after the infra-manager proof, each converted and relaunched tmux-first
  (bind against the pane's real PID): Curator Core (`ivmbp_curator_orch`, curator-ivmbp),
  curator-run (`ivmbp_curator-run_orch`, curator-run-ivmbp), a2a-source (`ivmbp_a2a-source_orch`,
  a2a-source). Design input before P4: swarma-docs book + swarma-link-spec (local checkouts:
  `swarma-lead/book`, `swarma-link-spec`), plus agents1-keeper / swarma-lead (hibernating) review.

## Identity and transport abstraction (owner discussion, 2026-11-19)

- a2a must not be hard-bound to Matrix. The seam is a transport-profile config that maps an
  identity to one or more transports (Matrix, XMPP, Mattermost, Nostr, ...), each with its own
  account/address and device keys. `identity ensure` takes an explicit transport selection
  (e.g. `--transport matrix`) instead of assuming Matrix; Matrix is the first adapter, XMPP second
  (per signing-auth notes). L0 in conversion terms is therefore "transport account + local
  credentials", not "Matrix account".
- The chain identity abstracts the transports (Swarma Link, "Личность и имена" / "Ключи" +
  signing-auth `05-devices`): identity = permanent root key; the own Namecoin name's value
  publishes the working keys; each transport account/device is a *device* of that identity —
  the operator root attests the Matrix master (devices verify via Matrix self-signing),
  each XMPP OMEMO fingerprint is attested separately; a device key carries its own
  attestation scope and its own revocation entry in the owner's cumulative revocation snapshot.
  The recent direction the owner recalls is this device-key model; in link-spec the adopted LIPs
  run to LIP-0008 (grant v4; "channel descriptors and Matrix key support" still an open question),
  while book v3 name values are exact LIP-0004 bytes (`swarma.landlord.grant` + `nostr`) until the
  future parser (book calls it the LIP-0010 parser) is deployed at every verifier — extra members
  are not yet safe to write.
- Registrar service model (who creates identities): an agent never registers another agent's
  identity, but it may *request* one from an operator-run registration service (human or a
  high-rank trusted agent acting for the owner; see the `swarma-registrar` module). Flow: signed
  request with role/scope -> service verifies grant and quota -> service creates the root key in
  keyvault custody, sponsors the Namecoin name registration (cold name-owner key never leaves
  operator custody), writes the name value (working/message key), issues transport accounts and
  the device attestations, and hands the new agent only its working keys over a sealed channel.
  Key-only operation without a chain name remains the base case (one-off executors); long-lived
  workers/orchestrators get own `id/` names.
- Prepaid renewal: at registration, reserve N renewal outputs intended to fund `name_update`
  renewals for N nominal years; reserved outputs are fenced off from ordinary spends. Caveat that
  the draft must solve honestly: coins alone do not renew — a signature by the name-owner key is
  required, so the design needs either a constrained renewal-only key/script that can re-issue the
  same value but cannot transfer the name or change its value, watched by a renewal service, or
  pre-signed renewal transactions with their expiry limits studied. Base case: no reservations
  created -> loud registration-time warning + expiry alarms. Candidate next LIP draft (owner to
  confirm): "Prepaid name renewal reservations".
- `identity ensure` today (a2a): computes `<host>_<project>_<role>` (project from the git remote),
  reuses local credentials or registers the Matrix account (operator supplies the registration
  token via env), joins #lobby (+#broadcast), creates the project room when missing, adds baseline
  subscriptions, installs runtime hooks. It does not enforce keeper readiness, and `--runtime`
  lacks `muse`/`pi`. Both are a2a-side fix items for the a2a-source lane.

## Station plan (pending owner confirmation)

- Orchestrator: this Muse session's lane identity `ivmbp_session-convert_orch` (a2a), owner DM
  with Ivan only; no external room subscriptions beyond the work room.
- Work room: one Matrix room for orchestrator + stations (name TBD with owner).
- Stations: `ivmbp_session-convert_dev1` (pix, gpt-6.2-sol, producer), `ivmbp_session-convert_rev1`
  (pix, gpt-6.2-astra, reviewer of record). Stable tmux workbenches via the usual lane launcher;
  all coordination over Matrix so the owner can observe/replay.
