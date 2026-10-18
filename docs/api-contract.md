# API contract (frozen)

Base: /api/v1. Dates are ISO strings (YYYY-MM-DD). Money is always a string with two decimals; never parseFloat it, never sum it in JavaScript floats.

## Auth
POST /auth/login/ {username, password} -> 200 {access, refresh} | 401
Every other endpoint needs the header Authorization: Bearer <access>. Missing or expired token -> 401. The frontend keeps the access token in memory only (30 minute life); a page refresh logs out.

## Lists
Customers, products, invoices and payments are paginated, 20 per page: { count, next, previous, results: [...] }, ?page=N.

## Invoices
GET /invoices/        -> paginated list, newest issue_date first, ties by id descending
GET /invoices/{id}/   -> Invoice
DELETE /invoices/{id}/ -> 405 (invoices are never deleted)

Invoice: id, invoice_number, customer (id), status, issue_date, due_date,
  subtotal, tax_total, total, paid, outstanding,
  seller_name, seller_gstin, seller_state, seller_address,
  customer_name, customer_gstin, customer_state, customer_billing_address,
  items: [{ id, product, product_name, quantity, unit_price, tax_rate,
            discount, hsn_sac_code, line_total }],
  payments: [{ id, amount, payment_date, method }]  (payment_date ascending, then id)

irn and qr_code are NOT part of this contract. The server still returns both as null until the backend branch removes them. The frontend must not read or display them.

Show customer_name and the seller_* fields from the invoice itself, never from the customer record. State values are GST state codes such as "27".

PATCH /invoices/{id}/ {status} -> 200 Invoice | 400
Status transitions: draft->sent|cancelled; sent->paid|overdue|cancelled;
  overdue->paid|cancelled; paid and cancelled are final.
Rule (enforced by the server since e1307a4): status paid is only valid when outstanding is "0.00", otherwise 400 with body {"status": ["Cannot mark an invoice as paid while a balance is outstanding."]}. The UI must still offer Mark as paid only when outstanding === "0.00".
A paid request from draft is refused by the transition table before the balance check, so its body stays a list whose first entry is "Cannot transition invoice from draft to paid".

## Payments
POST /payments/ {invoice, amount, payment_date, method, idempotency_key} -> 201 | 400
201 body: { id, invoice, amount, payment_date, method, idempotency_key }
method is one of cash, upi, bank_transfer, cheque. idempotency_key is a UUID generated once per form and reused on retry.
Allowed only when the invoice status is sent or overdue, amount > 0 and amount <= outstanding.
PUT, PATCH and DELETE on payments -> 405.

## Error bodies (handle every shape)
400 can be a JSON list of strings, or an object keyed by field name whose values are a list of strings or a plain string, or an object with non_field_errors.
- Invalid or forbidden status change: a list, for example ["Cannot transition invoice from paid to sent"].
- Paid requested while a balance is outstanding: {"status": ["..."]}.
- Items edited after draft: a list.
- Customer changed after draft: {"customer": "..."}.
- Payment rejected by validation: {"non_field_errors": ["..."]} or a field-keyed object.
- Payment rejected by the locked re-check or a duplicate key: a bare list.
A client must normalise all of these to text. Never assume an object.

## Aging
GET /invoices/aging/ -> { not_due, days_0_30, days_31_60, days_61_90, days_90_plus }
Each is a list of { id, invoice_number, customer, due_date, total, outstanding, days_overdue }.
customer is the customer name string. days_overdue is 0 for not_due.

## Button rules for the invoice detail page
Mark as sent: status draft. Mark as overdue: status sent. Cancel: draft, sent or overdue.
Mark as paid: status sent or overdue and outstanding === "0.00".
Record payment: status sent or overdue and outstanding !== "0.00".

## Known caveats
- The key days_0_30 holds invoices 1-30 days overdue.
- A duplicate idempotency key that races past validation still returns 500. Parked until after the demo.
- Invoice status is changed manually; a sent invoice past its due date stays sent until someone marks it overdue.

## Verification log
- Status transitions match Invoice.ALLOWED_TRANSITIONS in models.py (checked at 68e5ced).
- Payment method values match Payment.METHOD_* in models.py (checked at 68e5ced).
- Aging keys and row fields match views.py aging(); the days_90_plus branch was outside the lines checked and is inferred from the bucket dict.
- Nested payments (4 keys) and invoice list ordering are covered by billing/test_invoice_api.py.
- NOT verified: the 201 body of POST /payments/. The PaymentForm owner reports the real body.
- Summing money in the browser: parse to integer paise (BigInt), never Number or parseFloat, then format with formatMoney.
