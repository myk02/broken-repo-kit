# 002-cache-recency - reasoning

## Root cause

Two edits landed in the same review:

1. `get` stopped calling `move_to_end`, so a read no longer made an entry the
   most recently used one. The LRU order silently became insertion order.
2. Expiry used `now > expires_at` instead of `now >= expires_at` (in
   `_is_expired` and in `purge_expired`), so an entry survived one tick too
   long. `ttl=0` entries were readable at the tick they were written.

They are one report because both make the cache keep the wrong entry: one
governs *which* entry goes, the other *when*.

## Why this verifier is fair

Every check uses the public constructor and methods with an injected counter
clock. Nothing sleeps or reads the wall clock. The checks assert observable
behaviour: which key can be read after an eviction, and whether a key is live
at an exact tick.

## What valid variation it allows

The golden fix restores `move_to_end` and `>=`. A solution may instead
reinsert the key to refresh it, or compute age as `now - written_at` rather
than comparing absolute timestamps. Both alternatives are shipped and pass.

## Cheats it blocks

- Fixing only the boundary still evicts the just-read entry.
- Fixing only recency still serves expired data.
- Making `peek` refresh recency fails the pass-to-pass peek check.
- Evicting the newest entry fails the visible capacity tests.
- Editing the visible tests is a violation before pytest starts.
