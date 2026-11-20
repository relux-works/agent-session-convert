# Self-configuring wake for new sessions (gap list, 2026-11-20)

Goal: a new session on any harness configures its own stable reading
(mailbox + wake + inbox discipline) without a hand-written prompt per lane.
The 2026-11-19 lane migrations needed hand-written WAKE-PROMPT files and
hand-made tmux sidecars; that is the gap. Layers, beyond a2a-swarm#526:

1. **CLI (a2a).** `identity ensure` must accept every supported runtime and
   finish with a working wake route, not only hooks where they exist:
   - claude/codex/muse: native hooks or the #526 carrier;
   - pi/antigravity (no hook runtime yet): generate a supervised sidecar
     (tmux wake window or service unit) with recorded PID/log, owned by the
     launcher, plus a bind record naming the route. `bind status` must show
     the route and its last qualification result.
   (#532 already extends ensure to `muse`; pi/antigravity remain.)
2. **Skill (a2a).** The skill's quickstart needs the per-runtime wake table
   and the readiness rule: not configured until an idle qualification event
   wakes the lane and it runs `a2a inbox` unaided. Today the table covers
   claude/codex and prose fallbacks.
3. **Converter.** `--apply` must emit the target lane's wake artifacts next
   to the converted session (sidecar script + wake prompt + bind checklist)
   and, with `--launch tmux`, start them. Today it prints only a resume
   command; the 2026-11-19 prompts were written by hand per lane.
4. **Curator.** The a2a capability in a profile declares the wake route per
   runtime; the launcher runs ensure/bind at launch and performs the
   qualification event before it reports a lane ready. A lane that fails
   qualification is reported degraded, never silently running deaf.

Order: CLI routes (in #532 for muse) -> converter artifacts -> skill table ->
Curator capability performing it at launch.
