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

## Customer snapshot on Invoice

- `Invoice.customer_name`, `customer_gstin`, `customer_state`, and `customer_billing_address` are snapshotted from the `Customer` row at invoice creation time, and re-snapshotted if the customer is changed while the invoice is still in draft status. Once an invoice leaves draft status, its customer cannot be reassigned, and its snapshot fields no longer change even if the underlying `Customer` row is edited.
- Invoices created before this snapshot existed were backfilled by a data migration (0013) from each invoice's *current* `Customer` row at the time the migration ran. This is accurate as of the migration's run date, not as of each invoice's actual creation date. If a customer's details were edited between an old invoice's creation and the migration running, that invoice's backfilled snapshot reflects the edited data, not the original. No historical record exists to backfill correctly, so this is accepted as a known limitation, not fixed further.

## Invoice deletion guard

Invoices cannot be deleted through the application. Deleting one would leave a permanent gap in the consecutive invoice-number sequence and would destroy a legal record. To cancel an invoice, use the status transition instead.

- `DELETE /api/v1/invoices/{id}/` returns 405 (`InvoiceViewSet` has no destroy route).
- A `pre_delete` receiver on `Invoice` raises `ValueError` for instance, queryset and cascade deletes, in every status including draft.
- Django checks `PROTECT` before `pre_delete`, so an invoice with payments raises `ProtectedError` first.
- The only bypass is the `allow_invoice_deletion()` context manager, used by `seed_aging_dev_data --clean` for dev data.
- A caller that catches this `ValueError` inside an enclosing transaction needs its own `transaction.atomic()` savepoint, because the exception is raised inside Django's deletion collector and marks the outer transaction as broken.
- Not covered: raw SQL and `_raw_delete`.

Known limitation: payment immutability is enforced at instance level only. `Payment.delete()` and `Payment.save()` raise, but `Payment.objects.filter(...).delete()` and the admin's bulk delete action bypass them. Accepted for a single-administrator system. `seed_aging_dev_data --clean` currently relies on this, so a future Payment guard needs a matching bypass there.
