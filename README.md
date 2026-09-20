# Billing & Invoice Generator

Design decisions and accepted risks. Setup and usage documentation is not written yet.

## Invoice numbering

- Format: `INV-000001`, six-digit zero-padded, no year or prefix segment.
- Assigned server-side inside the invoice creation transaction, from a single-row counter (`InvoiceNumberCounter`, pk=1) locked with `select_for_update()`. Concurrent creates cannot receive the same number. A create that fails and rolls back does not consume a number.
- Clients cannot choose the number: `invoice_number` is read-only, and any posted value is discarded.
- Lifetime sequence: it never resets at the start of a financial year. This is a deliberate choice, not an oversight.
- Numbers are never reused. Any invoice removed after creation leaves a permanent gap in the sequence.

## Accepted risk: counter row deleted and recreated

The counter row is seeded by migration 0009 with pk=1.

- If the row is missing, invoice creation fails with a logged server error that names the missing counter. Repair: recreate the row with pk=1 and `last_number` set to the highest issued invoice sequence number.
- If the row is recreated with pk=1 and `last_number=0` while invoices already exist, every create collides with an existing `invoice_number` on the unique constraint, rolls back, and fails until the counter is repaired. It fails loudly and no duplicate number is ever saved, but invoice creation is blocked until someone fixes the counter. There is no code guard against this; it is accepted for a single-admin app.
- Recreating the row without an explicit pk gets a new pk, because the Postgres sequence has moved on. That hits the missing-row error above, not the collision.
