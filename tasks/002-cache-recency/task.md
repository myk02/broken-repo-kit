# The cache evicts the wrong entry and keeps entries too long

The product cache has two complaints from the team:

1. An entry that was just read is evicted before entries that nobody has
   touched. Reading with `get` is supposed to make an entry the most recently
   used one; `peek` is the read that deliberately does not.
2. An entry with `ttl=3` written at tick 0 is still readable at tick 3. It
   should be gone at tick 3: an entry is live while `now < written_at + ttl`.
   With `ttl=0` it should not be readable at all.

Both the `get`-based reads and the bulk operations (`len`, `in`, `keys`,
`purge_expired`) must agree on the expiry boundary.

## Examples

```python
clock = FakeClock()                       # now == 0
cache = TtlLruCache(capacity=2, ttl=3, clock=clock)
cache.set("a", "A")
cache.set("b", "B")
cache.get("a")                            # a is now the most recent
cache.set("c", "C")                       # b must be evicted, not a
```

```python
cache = TtlLruCache(capacity=2, ttl=3, clock=clock)
cache.set("a", "A")
clock.advance(3)                          # exactly one ttl later
cache.get("a", "gone") == "gone"          # must be gone
len(cache) == 0
```

## Constraints

- Keep the injected-clock design: never call `time` inside the cache.
- Keep the public API and the stats counters.
- Do not edit the visible tests.
