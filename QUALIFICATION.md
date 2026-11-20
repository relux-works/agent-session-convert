# Qualification evidence

On 2026-11-20, macOS arm64, native inspection passed for each of the nine source/target combinations on disposable transcripts containing a historical marker. Readers and writers used persisted IR between stages.

| Target | Observed version | Independent observation |
| --- | --- | --- |
| Claude Code | 2.1.326, Agent SDK 0.2.186 | get_session_messages resolves the target UUID in its workspace and returns the marker |
| Codex CLI | 0.171.0 | app-server thread/resume resolves the UUID and returns the marker in the turn items |
| Muse Code | 1.4.24-R9131.1 | trace inspect loads the minted permission frame and projected records in staging and the sandbox target store; the committed dialogue contains the marker |

An absent-marker control failed all nine cells at the marker assertion after provider inspection. An earlier Codex rollout prototype resolved the UUID with empty items; the marker assertion catches that failure. A Muse frame reserialized with sorted keys failed native inspection; its original bytes are now preserved.

The reference production Claude snapshot yielded 183,287 IR facts. The post-compaction replay contained 374 tool calls, 374 results and 137 dialogue/summary events. The raw source and all payloads are local to the private bundle. No production session was published or resumed in this run.

Authenticated bounded answers and two-account controls are pending for the new tuples. The existing Claude-to-Muse admission is based on the prior real-provider experiment. CLI upgrades require fresh evidence.
