# Agent session conversion (seed)

This repository is about one thing: converting a stored agent CLI session into
a new session for another provider, or for the same provider under another
account, without losing track of what was lost on the way.

Initial providers: Claude Code, Codex CLI, and Muse. Others are added as
extension adapters.

Status: specification seed only. No reader, writer, or CLI exists yet. Provider
rules for Muse account moves are verified. Codex and Claude Code rules are
written as the expected behavior and marked UNVERIFIED.

## Files

| File | Content |
| --- | --- |
| `SPEC.md` | Normative specification v0.1.0 (draft) |
| `TRACEABILITY.md` | Where each SPEC section comes from, and what was dropped |
| `UNRESOLVED_QUESTIONS.md` | Decisions the owner still has to make |
| `SUMMARY-RU.md` | Short owner summary in Russian |

## Scope

- Reading a provider's native session store (discovery, stable snapshot,
  byte-exact capture with a closed manifest).
- Normalizing to a provider-neutral IR.
- Planning a projection: strategy, fidelity profile, and a disposition for
  every item.
- Writing a new target session (native records, official import, or
  continuation context), with read-back of the staged and the live target.
- Handling provider-bound artifacts: encrypted reasoning, signatures, and
  server references that are valid only for the account or provider that
  produced them.
- Fidelity Report, Validation Report, and a lineage chain across conversions.
- An opt-in in-place rewrite for same-provider account moves.

## Non-scope

- Running, supervising, attaching to, or resuming agent processes beyond
  producing a resume command and an optional one-turn smoke test.
- Terminals, multi-host replication, leases, task boards, and orchestration.
- Authentication: the converter never reads, copies, or moves credentials. The
  operator logs in to the target account.
- Copying workspaces or repositories. A converted session references an
  existing workspace through a logical Workspace Binding.
- Cross-provider "native resume" of reasoning: foreign encrypted or signed
  reasoning is never written into a target.

## IR overview

The IR is a **Canonical Session** (logical session ID, source environment,
title, Workspace Binding, a set of actors with exactly one `main` and optional
subagents, and the ordered list of event IDs with their heads) plus one
**Canonical Event** per source fact. An event has a contiguous ordinal, causal
parents (so branches and subagent graphs survive), an actor, a kind from a
closed registry of 26 (`user_message`, `assistant_message`, `tool_call`,
`tool_result`, `opaque_reasoning`, `compaction`, `usage`, `opaque_event`, and
so on), a visibility, a typed payload whose message content uses eight block
types, and Source Evidence that points back to the exact captured byte ranges.
Every object is content-addressed (SHA-256 over RFC 8785 canonical JSON).
Anything a reader cannot type becomes an `opaque_event` instead of being
dropped; foreign encrypted or signed reasoning becomes `opaque_reasoning`,
kept byte-exact in the bundle and never written into a target. The writer then
assigns each item one of seven dispositions (`exact`, `semantic`,
`summarized`, `opaque_preserved`, `synthesized`, `omitted`, `unrecoverable`)
with closed reason codes, and the Fidelity Report accounts for every item.

## Tools

None yet. When the first reader or writer lands, list each tool here with its
purpose, exact commands, and output locations (scratch output goes to `.temp/`).

## Origin

The specification is condensed from the cross-environment clone part of a
larger session-manager specification (v0.7.0) and from a small, verified
account-transfer procedure for Muse. `TRACEABILITY.md` records the mapping.
