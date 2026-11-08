# Duplicate detection is too slow on the full catalogue

`find_duplicates` groups products that share the same key. On a catalogue of a
few thousand products it takes seconds, and the import job that calls it is now
missing its deadline. The result itself is correct; only the cost is wrong.

The verifier does **not** measure seconds. It passes a custom `key` callable
whose return value counts hashing, equality and ordering operations, then
checks the counts at three input sizes. The requirement is near-linear work:

- when the input grows by 4x, the operation count must grow by roughly 4x,
  not by roughly 16x;
- the `key` callable must be called about once per product, not once per pair;
- a larger input must not be silently truncated.

The output must stay exactly the same:

- each group is sorted by sku;
- groups appear in the order in which their first member appeared in the input;
- only groups of two or more are returned;
- a custom `key` callable is supported.

## Examples

```python
products = [
    Product("sku-3", "Blue Mug", 1200),
    Product("sku-1", "blue  mug", 1200),
    Product("sku-2", "Red Kettle", 3500),
]
find_duplicates(products) == [["sku-1", "sku-3"]]
```

## Constraints

- Keep the public signature, including the keyword-only `key` argument.
- Do not change `Product` or `dedupe_key`.
- Do not edit the visible tests.
- The input may be any iterable, including a one-shot generator.
