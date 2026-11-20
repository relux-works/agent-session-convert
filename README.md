# Agent session conversion

Convert a Claude Code, Codex CLI or Muse Code transcript through an on-disk intermediate representation (IR). Every reader feeds the same planner. Each native writer consumes the ordered projection. Adding a fourth provider requires one reader and one writer.

## CLI

Python 3.9 or later. Run from a checkout or use the executable distributed by the transfer skill.

```sh
./agent-session-convert capture --from muse --source-log /path/to/session.jsonl --out-dir bundle
./agent-session-convert project --bundle bundle --to codex --workspace "$PWD" --out-dir codex-preview
./agent-session-convert project --bundle bundle --to claude --workspace "$PWD" --out-dir claude-preview
```

Bundle paths must be fresh. The private bundle contains a byte-exact snapshot of the supplied transcript, ordered and hashed events, content-addressed oversized payloads and a session manifest. It can hold private workspace data. Keep it with the source. Capture covers a single transcript. Workspace files, hooks, provider credentials, permissions and schedules belong to separate stores.

`convert --from SOURCE --to TARGET --source-log PATH --out-dir DIR --workspace DIR` combines the steps. The native projection contains a fresh identity, staged JSONL, per-event fidelity and a read-back report. Compact projection starts at the last recognized compaction summary. Use `--full-history` for the whole timeline, `--max-tool-chars N` for inert tool summaries or `--profile messages_only` for messages. Foreign reasoning and unknown records stay in the snapshot. See [the transcript IR contract](TRANSCRIPT-IR.md).

### Native publication and continuation

Native staging supports the nine combinations of the three providers, including same-provider copies. Native publication currently admits Claude → Muse Code 1.4.24 build R9131.1. Add `--apply` to `convert` to mint a fresh permission transaction, inspect staged and published history, and receive the workspace and resume arguments in `projection/validation.json`. Production admission for other combinations requires the provider and account qualification described below.

Use `--strategy continuation_context` on any combination to produce `continuation.txt` and `launch.json`. The plan gives the target CLI arguments, working directory and optional input file. Launching that command sends the projected text to the chosen target as one historical message. Codex returns its new UUID in the `thread.started` event. This strategy starts a new context and does not retain native message boundaries.

## Qualification and tools

- `swift test` exercises the CLI in separate processes for all nine projections, raw-input removal, private-reasoning omission, collision refusal and tamper detection.
- `tools/qualify --scratch DIR --muse MUSE_LOG --claude CLAUDE_LOG --codex CODEX_LOG --word WORD` runs the provider read-back matrix in a dedicated environment. Supply disposable transcripts with a unique verification word in historical dialogue. Put HOME, XDG_CONFIG_HOME, XDG_CACHE_HOME, XDG_DATA_HOME, CODEX_HOME, TMPDIR and the working directory beneath DIR. Install the Claude Agent SDK in the qualification interpreter (`python -m pip install claude-agent-sdk`). Codex uses its app-server, Muse uses trace inspection. Results, projections and version tuples are written under `DIR/matrix-*/`.
- Add `--check-turn` with authenticated qualification accounts to require the historical word from a bounded resumed turn. Account-transfer admission additionally requires a real A→B experiment with an unstripped negative control per the draft specification §14.4. Synthetic fixture results qualify only what their report measures.
- `tools/package /path/to/agent-session-convert.pyz` builds a reproducible executable for the Curator skill using only the Python standard library. The output path must be fresh.
