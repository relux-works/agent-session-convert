# LIP-0032: Entity card — a signed public card for an agent, a person or a service

- **Status:** Draft, proposed 2026-11-20 by the session-convert keeper at the
  owner's request. Nothing in this file is in force. It revises nothing until
  the owners agree.
- **Affects:** how a verifier learns what an entity is (address, transports,
  owner/landlord, role, contact) without trusting a repository or a transport.
- **Builds on:** LIP-0010 section 11 (heads of statement sets, SH1 to SH8),
  LIP-0016 (certificate store), LIP-0019 (retrieval by hash), LIP-0029
  section 3 (device list), LIP-0026 section 9 (holders of a landlord),
  KEY-REGISTRY ("Keys bound to a name").

## Summary

Today an agent's card lives as a Markdown file in the a2a-swarm repository
(`agents/<name>.md`, installed by `a2a card set`). A repo file is a rendering,
not a protocol object: no signature, no version rule, no revocation, and no
meaning outside that repository. This LIP defines the card as a signed,
content-addressed statement set of the entity's own Namecoin name, so that
agents, people and services are described by one mechanism, and the repo card
becomes a cache that any reader can rebuild and check.

## The size question first (measured, LIP-0010 section 8 and 11)

A name value is at most **520 bytes**, every member counted. The budgets that
already compete for it (LIP-0010 section 8, `seq` below 10):

| Value | Bytes | Left |
| --- | ---: | ---: |
| Landlord, NIP-05 object and one relay | 294 | 226 |
| + `swarma-holders` head (103) | 397 | 121 |
| + `swarma-devices` head (103) | 500 | 20 |
| + a card head (~100) | ~600 | **does not fit** |
| Agent (key string in `nostr`) | 175 | 345 |
| + a card head (~100) | ~275 | ~245 |

**Conclusion: a fourth head member does not fit a working landlord value.**
The card therefore does NOT get its own name-value member in the general
case. Two placements are defined instead:

1. **Certificate-store statement (primary).** The card is one statement kind
   inside the LIP-0016 certificate store, whose head already lives in the
   name as `swarma-certs`. It costs zero additional name bytes, inherits the
   store's anchoring, journal and rollback rules, and follows the size plan
   of LIP-0010 section 8 ("every other key or binding is a signed statement
   in the certificate store").
2. **Direct head (optional, small values only).** Where the value's measured
   budget leaves at least 110 bytes after every other member the deployment
   uses, the owner MAY pin the card head directly as one more SH1 member,
   `{"seq":…,"sha256":…}` (about 100 bytes at `seq` below 10). A reader MUST
   measure the whole value; a value above 520 bytes is refused as today.
   The budget check, not preference, decides the placement, and the two
   placements MUST NOT both be live for one name: the direct head wins when
   present (rule C7).

## Proposal

### 1. The card document

`swarma-card/1` is a JSON document, UTF-8, at most 16384 bytes, with exactly
these members in this order:

| # | Member | Meaning |
| --- | --- | --- |
| 1 | `schema` | the exact string `swarma-card/1` |
| 2 | `network` | `main` or `regtest` (as the statement sets) |
| 3 | `name` | the entity's own `id/` name; the card names nobody else |
| 4 | `seq` | canonical positive integer, increases on every change |
| 5 | `kind` | `agent`, `person` or `service` |
| 6 | `display` | short human label; directs no authority |
| 7 | `owner` | the landlord/operator `id/` name, or the same name for a person |
| 8 | `transports` | array of `{transport, address}` the entity answers on (Matrix, XMPP, Mattermost, Nostr, ...) |
| 9 | `role` | short role text; directs no authority |
| 10 | `contact` | where work is offered (room alias or address) |
| 11 | `replaces` | `seq` of the previous card, or 0 for the first |

Free text (`display`, `role`) directs work only and gives no authority, as
free text in an envelope (LIP-0029 O1.2). A reader MUST refuse an unknown
member, a duplicate, another order, or a `seq` that does not increase over
the journaled head it took (rules SH4/SH5 applied to the card set).

### 2. Signature and binding

- The card octets are signed by a key the name already binds: for an agent,
  the working key in the name value; for a person or service, a device key
  from its device list. The name-owner (cold) key never signs cards.
- A reader verifies: the octets hash to the pinned head (store placement:
  through the store's head chain; direct placement: through the SH1 pin),
  the document names the name it was read under, and the signature verifies
  under a key that name binds at the same confirmed tip. Any failure gives
  no card, and leaves every grant and every other set as they read (SH6/SH7
  applied to the card set).

### 3. Updates and revocation

- A new card is a new statement (store) or a name update (direct head):
  add is slow and signed, as devices (LIP-0029 section 9). Readers journal
  the highest `seq` taken; a lower `seq` under a live head refuses with
  `CARD_ROLLBACK` (SH5).
- Revoking a card is removing its statement/head in the next set version.
  A card a taken version removed stays refused at every reader that took
  that version, as removed devices and holders (SH5). Killing the entity's
  name kills the card with it; no separate card seal exists in v1.

### 4. Projection rule

Consumers that need a flat card (the a2a-swarm repo file, a directory, a
UI) render it from the verified document and mark it as a projection. A
projection carries the head (`seq`, `sha256`, name) it was rendered from;
a projection without that mark is a claim, not a card.

## Refusals

`CARD_INVALID` (schema, members, order, bounds), `CARD_MISMATCH` (hash,
name, network or signature), `CARD_ROLLBACK` (lower `seq` under a live
head), `CARD_BUDGET` (direct placement without the measured 110 bytes).

## Cases

- Alisa (person, landlord value 294 bytes with holders and devices heads):
  card lives in her certificate store; a reader resolves it through
  `swarma-certs` at no name cost.
- Agent `id/cedar` (agent value 175 bytes): direct head fits (about 275 of
  520); a reader takes the card from the pin and checks the agent key.
- A value that carries both placements: the direct head wins (C7); the
  store statement of the same `seq` is ignored, a different `seq` there is
  `CARD_MISMATCH`.

## Open questions

1. Which key signs for a person: a device key of the device list, or the
   social key? This draft takes the device key; the social key signs nothing
   but Nostr, as the key map holds.
2. Public subset: the chain is public. Fields a deployment must not publish
   (exact room ids of private rooms) need a sealed companion statement, out
   of scope here; the card carries only what its owner publishes.
3. Does the umbrella-head form of LIP-0010 section 11 (one member pinning a
   heads document) supersede the direct placement when adopted? If so this
   LIP's direct placement folds into it unchanged.
4. Card for an entity without its own name (a one-off executor named by
   key): out of scope; such an executor is described by its landlord's
   holders entry, not by a card.

## Sources

LIP-0010 sections 8 and 11; LIP-0016; LIP-0019; LIP-0029 sections 3 and 9;
LIP-0026 section 9; KEY-REGISTRY "Keys bound to a name"; the a2a-swarm agent
cards (`agents/<name>.md`) as the existing projection this LIP replaces.
