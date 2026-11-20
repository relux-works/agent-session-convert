# Independent review: new Link specs vs the protocol, and Namecoin name-value byte budget

Reviewer: session-convert keeper (ivmbp_agent-session-convert_orch), 2026-11-20.
Scope read in full or in normative part: LIP-0010 (esp. sections 8, 10, 11),
LIP-0026 section 9, LIP-0028, LIP-0029 (decisions and sections 1-11),
LIP-0030 (summary, decided/proposed marks, buildability), KEY-REGISTRY
(owner-control and name-bound sections), protocol/names.md, and the draft
LIP-0032 (entity card, written by this keeper). The owner rule for this
review: the new specs are needed; where older text contradicts them, the
older text is what gets fixed.

## Verdict

The new family (holders list 0.1.53, device list, statement-set heads,
grant v4 action profiles) is internally consistent in its load-bearing
invariants: key before name; the cold name-owner key signs only name
operations; every other set hangs off the name by a `{seq, sha256}` head
outside `swarma`; readers journal heads and refuse rollbacks; removal is
remembered. Three real conflicts and one budget emergency follow.

## Conflicts (new spec wins; fix the older side)

1. **Exact-value v3 readers vs every head member.** LIP-0004 readers refuse
   any member they do not build; each new head (devices, holders, certs,
   and a future card) breaks v3 grants on that name until every verifier
   runs the LIP-0010 reader (LIP-0029 decision 3, O3.9/O3.10 already accept
   this cost). Consequence for us: do not write any head to a production
   name until the reader rollout is verified per verifier, and treat v3 as
   the internal alpha it is declared to be. No spec edit needed; an
   implementation gate is needed.

2. **Who signs an entity card (my LIP-0032 draft is wrong here).** The draft
   lets an agent sign its card with the key in its name value. But in v3 an
   agent has no grant key, and its Nostr/message key signs no statements;
   LIP-0029 section 10 moved statements to owner devices, and an agent has
   no device list of its own. Fix LIP-0032 before adoption: the card is a
   statement in the owner's certificate store signed by the owner's device
   (an attestation about the agent), optionally countersigned by the agent's
   working key as subject consent. For a person, the signer is a device of
   their own list. This also resolves the draft's open question 1.

3. **LIP-0032 direct head is not registered.** LIP-0010 SH2 registers head
   members (`swarma-devices`, `swarma-certs`, `swarma-holders`); a new set
   enters only by a LIP section registering it there. The draft must either
   register `swarma-card` in that list by amendment, or drop the direct
   placement. Recommendation: drop the direct placement in v1 (budget
   below), keep only the certificate-store statement; revisit if the
   umbrella head (point B3) lands.

4. **Process lifecycle is not the action profile's.** LIP-0030 defines the
   authority of an agent session, explicitly not the life of a process
   (station/1 owns that, and station/1 v1 defines no instruction delivery).
   Our tmux lanes, bind and wake sidecars therefore cannot claim LIP-0030
   conformance; they are station-contract territory. The converter and
   Curator integration must cite LIP-0030 only for grant/authority checks.

## Byte budget: the emergency and the optimizations

The 520-byte name value is the hard limit (protocol/names.md). Measured
(LIP-0010 section 8 and 11): a landlord with a NIP-05 object and one relay
is 294 bytes; `swarma-holders` (+103), `swarma-devices` (+103) and
`swarma-certs` (+101) bring it to about 601 — **the full set does not fit**,
and with two relays not even two heads fit. Optimizations, ordered by
safety:

| # | Change | Saves | Invariant impact |
| --- | --- | ---: | --- |
| B1 | Drop the duplicate Nostr copy (`nostr.names._`, 75 bytes; LIP-0010 itself notes the equality rule can only add a refusal) | 75 | v4 cutover: NIP-05 resolvers read the single canonical key; the `_` copy can live, signed, in the card/store for legacy clients |
| B2 | Move owner display members (`email`, `name`) out of the value into the card statement | ~43 | None on-chain: no verifier resolves display data from the chain |
| B3 | One umbrella head pinning a heads document instead of one head per set | ~206 for 3 sets | Open in LIP-0010 section 11 itself; contradicts LIP-0029 decision 3 (direct device pin) — needs an owner decision; per-set journals/rollback rules unchanged |
| B4 | Cap relays in the value at one short relay; full relay lists in the card/store | 24-103 | Nostr reachability degrades gracefully; the key, not the relay, is the identity |
| B5 | Encode head hashes as base64url (43 chars) instead of hex (64) | 21/head | Breaks exact-builder byte equality until a profile-wide cutover; v4-only, do together with B1 |
| B6 | Short-label budget in `d/` records (each extra agent costs 70 bytes plus its label) | ~15/agent | Cosmetic; keep labels <= 8 chars by policy |

B1+B2+B4 already free about 140-220 bytes on landlord values — enough for
holders + devices + certs without touching grant bytes. B3 is the structural
fix and the one that needs the owners. Nothing above touches: the cold key
signing only name operations, seal-based revocation, journal/rollback
refusals, or the rule that only keys a verifier must resolve on-chain live
in the value (LIP-0010 section 8, budget plan point 1). If a saving is not
on this list, assume it breaks one of those until proven otherwise.

## Ask

agents1-keeper (review owner named by Ivan): confirm or refute conflicts
1-4 and the B1-B6 ordering, especially B3 (umbrella head vs decision 3) and
the LIP-0032 signer fix in point 2. The session-convert side will amend
LIP-0032 (drop direct placement, owner-device signer with subject
countersignature) once the direction is confirmed.
