# Discounts are charged in the wrong order

A customer reports that a basket totals differently depending on the order in
which its discounts were added, even though the discounts themselves are the
same. The shop's rule is that **percentage discounts are applied before
fixed-amount discounts**. Within each kind, discounts keep the order they were
listed in. Each discount is rounded half up when it produces a fraction of a
cent, and tax is charged on what is left after every discount.

## Examples

```python
cart(LineItem("a", 1, 1000), discounts=(FixedOff(100), PercentOff(10)))
# expected: taxable_cents == 800, discount_cents == 200
```

```python
cart(LineItem("a", 1, 1005), discounts=(FixedOff(1), PercentOff(10)))
# expected: taxable_cents == 903, discount_cents == 102
```

```python
cart(LineItem("a", 1, 2500),
     discounts=(FixedOff(500), PercentOff(10), FixedOff(250), PercentOff(5)))
# expected: taxable_cents == 1387
```

## Constraints

- Money stays in integer cents. Do not introduce floats.
- Keep the public API in `minishop.pricing` unchanged.
- Do not edit the visible tests.
- Tax, shipping, validation and the quote fields behave exactly as before.
