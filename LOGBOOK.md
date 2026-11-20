# Flight Logbook

> Institutional memory. Concise, factual, high-signal.
> Newest entries first. One block per insight.

## 2026-11-20

### 0520 — Name value byte emergency; review sent
- FINDING: Full head set (holders+devices+certs) over a NIP-05+relay landlord value exceeds the 520-byte Namecoin limit (~601). Optimizations B1-B6 in Downloads/REVIEW-new-specs-and-name-bytes.md free 140-220 bytes without touching grant bytes or invariants.
- FINDING: LIP-0032 draft conflicts: direct head not registered in LIP-0010 SH2; agent card signer must be owner device + subject countersignature, not the agent message key. Fix after keeper review.
- STATUS: Review posted to agents1-keeper 2026-11-20 (lobby topic session-convert-review).

### 0445 — Identity card belongs on Namecoin (idea, owner request)
- FINDING: The a2a agent card (`agents/<name>.md` in a2a-swarm + `card set`) is a
  projection of an entity's public identity: address, runtime, owner, role, rooms,
  scope, contact. The same shape fits agents, people and services.
- DECISION: Think through expressing the card through Swarma Link instead of a
  repo file: the card document content-addressed off-chain, its hash pinned in the
  entity's own Namecoin name value (beside device/holder lists), retrieval by
  hash (LIP-0019), updates as signed new versions, revocation with the name.
  Repo card stays a rendering/cache; protocol bytes are the source of truth.
- NOTE: Open: which key signs card versions (device key vs grant key), public
  subset vs sealed fields (chain is public), card schema/versioning, `seq`
  rollback rules like device lists, how keepers verify card<->name binding.
- STATUS: Idea recorded 2026-11-20 at owner's request; design not started.
