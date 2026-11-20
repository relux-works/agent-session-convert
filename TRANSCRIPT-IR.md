# Transcript IR v1

The format identifier is `relux.transcript-ir`, version 1. This is the single-transcript implementation subset of the proposed conversion specification. It has a separate schema identifier while whole-store capture, cross-generation lineage and companion-state migration are under development.

`source.jsonl` contains exact input bytes. `session.json` binds the source provider and native session ID, snapshot SHA-256, logical identity, main actor, event order and graph heads. `events.jsonl` stores one or more facts per physical record, in native order. Each contains its zero-based ordinal, causal parents, actor, kind, typed payload and raw byte offset/length in that snapshot. Claude parent UUIDs link known ancestors. The compact projection follows the latest visible Claude branch, visits earlier compaction epochs and includes sibling tool results linked by call ID. Other readers use transcript order. Unrecognized records and ancillary state remain opaque.

| Kind | Payload |
| --- | --- |
| user_message, assistant_message, compaction | content array with text blocks |
| tool_call | native call ID, tool name and serialized arguments |
| tool_result | native call ID, serialized output and error flag |
| opaque_reasoning, opaque_event, usage | raw evidence reference on the event |

Inline text fields above 64 KiB by UTF-8 length become a SHA-256 reference in the corresponding field with suffix `_blob`. The bytes live in `blobs/<hex>`. Session and event digest calculation omits the self-identity member and hashes compact UTF-8 JSON with lexically sorted keys. All object keys produced for hashing belong to the ASCII schema. Capture assigns stable logical and actor IDs for one captured generation. Projection verifies the manifest, raw snapshot, event identities and referenced blobs before rendering.

Visible history uses one main dialogue. Sidechain and runtime metadata can be recovered from the snapshot. Fidelity records distinguish replayable text, summarized inert tools and source-only records. The converter allocates new native target IDs and never reuses foreign signatures, encrypted reasoning or tool permissions.
