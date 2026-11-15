# Unresolved questions

Decisions the owner must make before or during the first implementation. Each
item states the options and a recommendation.

## Product scope

1. **Cross-provider native resume, or continuation context only?**
   Options: (a) support `target_native_writer` for cross-provider pairs, where
   messages become real target records; (b) support only
   `continuation_context` across providers, and native rewrite only within one
   provider (account moves). Native writing depends on undocumented target
   formats that can change with any CLI release, and reasoning never transfers
   anyway. Recommendation: (b) first, keep (a) in the spec as a gated strategy.

2. **Which providers and directions first?** Candidates: Muse account move
   (verified rules exist), Codex account move, Claude Code account move, then
   any provider to Claude Code or Codex through continuation context.
   Recommendation: Muse account move as the first reader/writer pair, then
   continuation context into Claude Code and Codex.

3. **In-place account rewrite as a first-class mode?** The verified Muse
   procedure rewrites the source log in place with a backup. The spec allows it
   as opt-in (SPEC 10.6). Alternative: always produce a new session ID. That
   needs proof that Muse accepts a copied session under a new UUID (not
   verified). Decide whether in-place stays or is replaced once new-UUID copies
   are verified.

4. **Muse `cron.db` and scheduled work.** The spec refuses target writes when
   scheduled work exists. Decide whether a later version should migrate jobs or
   always refuse.

## IR and serialization

5. **IR serialization.** ax uses one JSON object per immutable record,
   identified by the SHA-256 of its RFC 8785 form, with optional deterministic
   CBOR. Options: keep that; or a simpler on-disk bundle (one directory, a
   `session.json` plus `events.jsonl` plus `blobs/`) with digests still
   computed per record. Recommendation: keep per-object identity, use the
   directory layout as the bundle storage form.

6. **Per-kind payload registries.** SPEC 7.2 names 26 event kinds, but the
   typed payload members of each kind are not defined (ax did not define them
   either). They must be written before two independent readers can produce
   compatible IR.

7. **Schema namespace and repository name.** `urn:sessconv:` and "the
   converter" are placeholders.

8. **How much of the closed ax adapter body registry to copy.** SPEC 12.2
   keeps the operations and their key constraints but not every request and
   response body. Decide whether to copy the full bodies now or define them
   with the first implementation.

9. **Adapter binding.** In-process library, out-of-process JSONL over stdio,
   or both. Out-of-process allows adapters in other languages and process
   isolation; in-process is simpler. The spec allows both.

## Verification

10. **How to verify the Codex and Claude Code rules.** SPEC 14.4 requires, per
    exact tuple: a real session moved from account A to account B, provider
    inspection (where one exists) passing, one bounded resume turn answering,
    and a negative control (unstripped log) failing with the expected error.
    Open points: which test accounts are available for this, whether the
    negative control is acceptable given quota use, and who runs it.

11. **Claude Code `thinking` signatures across accounts.** Unknown whether a
    signature stays valid when the same session moves to another account of
    the same provider. If it does not, the whole block must be omitted (a block
    without its signature is expected to be rejected; also unverified).

12. **Codex server item references.** Unknown which rollout members besides
    `encrypted_content` reference server-side state of the old account.

13. **Claude Code native file format.** The bundle does not state the session
    file layout or record schema. A Claude Code writer cannot be specified until
    this is documented from observed files and fixtures.

14. **Supported Pair Registry trust.** ax signs its registry. Decide whether a
    standalone tool needs a signed registry or a reviewed file in the repository
    is enough.

## Policy

15. **Default profile.** The spec keeps `maximal_safe` as default, which
    requires `raw_complete=true`. Decide whether an incomplete capture should
    fall back to `compact` automatically or refuse (the spec currently refuses).

16. **Bundle retention.** Bundles contain the full source history, including
    foreign encrypted reasoning. Decide default retention, location, and whether
    bundles may leave the machine.
