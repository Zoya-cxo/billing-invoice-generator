import re
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Company, Customer, Invoice, InvoiceItem, Payment, Product
from .serializers import InvoiceSerializer

LIST_URL = "/api/v1/invoices/"

SELLER_FIELDS = ["seller_name", "seller_gstin", "seller_state", "seller_address"]
CUSTOMER_FIELDS = [
    "customer_name", "customer_gstin", "customer_state", "customer_billing_address",
]
SNAPSHOT_FIELDS = SELLER_FIELDS + CUSTOMER_FIELDS

FORGED = {
    "seller_name": "Forged Seller",
    "seller_gstin": "29FORGED0000Z1Z",
    "seller_state": "35",
    "seller_address": "Forged Seller Address",
    "customer_name": "Forged Customer",
    "customer_gstin": "37FORGED0000Z1Z",
    "customer_state": "37",
    "customer_billing_address": "Forged Customer Address",
}

PAYMENT_KEYS = {"id", "amount", "payment_date", "method"}
ITEM_KEYS = {
    "id", "product", "product_name", "quantity", "unit_price",
    "tax_rate", "discount", "hsn_sac_code", "line_total",
}


def shape(sql):
    return re.sub(r"\d+", "N", re.sub(r"'[^']*'", "S", sql))


def grown_queries(few, many):
    before = Counter(shape(s) for s in few)
    after = Counter(shape(s) for s in many)
    return {s: (before[s], after[s]) for s in after if after[s] > before[s]}


class InvoiceApiFixture(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="invoiceapiadmin", password="testpass123"
        )
        self.client.force_authenticate(user=user)
        self.company = Company.objects.create(
            name="Live Seller Pvt Ltd",
            gstin="27AAAPL1234C1Z5",
            state="27",
            registered_address="Live Seller Address, Pune",
        )
        self.customer = Customer.objects.create(
            name="Live Customer",
            email="live@example.com",
            phone="9999999990",
            gstin="07BBBPL5678D1Z6",
            state="07",
            billing_address="Live Customer Address, Delhi",
        )
        self.product_a = Product.objects.create(
            name="Product A",
            unit_price=Decimal("10.05"),
            default_tax_rate=Decimal("9.00"),
            hsn_sac_code="998314",
        )
        self.product_b = Product.objects.create(
            name="Product B",
            unit_price=Decimal("10.02"),
            default_tax_rate=Decimal("18.00"),
            hsn_sac_code="998315",
        )
        self.counter = 0

    def make_invoice(self, items=(), send=True, total="1000.00",
                     issue_date=None, due_date=None, **overrides):
        self.counter += 1
        today = date.today()
        fields = {
            "invoice_number": f"API-{self.counter:04d}",
            "customer": self.customer,
            "seller_name": self.company.name,
            "seller_gstin": self.company.gstin,
            "seller_state": self.company.state,
            "seller_address": self.company.registered_address,
            "customer_name": self.customer.name,
            "customer_gstin": self.customer.gstin,
            "customer_state": self.customer.state,
            "customer_billing_address": self.customer.billing_address,
            "issue_date": issue_date or today,
            "due_date": due_date or today + timedelta(days=30),
            "subtotal": Decimal(total),
            "tax_total": Decimal("0.00"),
            "total": Decimal(total),
        }
        fields.update(overrides)
        invoice = Invoice.objects.create(**fields)
        for product, quantity in items:
            InvoiceItem.objects.create(
                invoice=invoice,
                product=product,
                quantity=quantity,
                unit_price=product.unit_price,
                tax_rate=product.default_tax_rate,
                hsn_sac_code=product.hsn_sac_code,
            )
        if send:
            invoice.transition_to(Invoice.STATUS_SENT)
        return invoice

    def add_payment(self, invoice, amount, payment_date="2026-02-01"):
        return Payment.objects.create(
            invoice=invoice,
            amount=Decimal(amount),
            payment_date=payment_date,
            method=Payment.METHOD_CASH,
        )

    def get_detail(self, invoice):
        response = self.client.get(f"{LIST_URL}{invoice.id}/")
        self.assertEqual(response.status_code, 200)
        return response.data

    def get_list_rows(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        return {row["id"]: row for row in response.data["results"]}


class InvoiceSnapshotFieldTests(InvoiceApiFixture):
    def test_snapshot_fields_come_from_invoice_not_live_records(self):
        expected = {
            "seller_name": "Snapshot Seller",
            "seller_gstin": "29AAAPL9999C1Z1",
            "seller_state": "29",
            "seller_address": "Snapshot Seller Address, Bengaluru",
            "customer_name": "Snapshot Customer",
            "customer_gstin": "09CCCPL1111D1Z2",
            "customer_state": "09",
            "customer_billing_address": "Snapshot Customer Address, Lucknow",
        }
        invoice = self.make_invoice(**expected)
        sources = (
            ("detail", self.get_detail(invoice)),
            ("list", self.get_list_rows()[invoice.id]),
        )
        for label, payload in sources:
            with self.subTest(source=label):
                self.assertEqual({k: payload.get(k) for k in expected}, expected)

    def test_snapshot_values_sent_on_create_are_ignored(self):
        payload = {
            "customer": self.customer.id,
            "issue_date": "2026-01-01",
            "due_date": "2026-01-31",
            "items": [
                {"product": self.product_a.id, "quantity": "1.00", "discount": "0"}
            ],
            **FORGED,
        }
        response = self.client.post(LIST_URL, payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        expected = {
            "seller_name": self.company.name,
            "seller_gstin": self.company.gstin,
            "seller_state": self.company.state,
            "seller_address": self.company.registered_address,
            "customer_name": self.customer.name,
            "customer_gstin": self.customer.gstin,
            "customer_state": self.customer.state,
            "customer_billing_address": self.customer.billing_address,
        }
        self.assertEqual({k: response.data.get(k) for k in expected}, expected)
        stored = Invoice.objects.get(pk=response.data["id"])
        self.assertEqual({k: getattr(stored, k) for k in expected}, expected)

    def test_snapshot_fields_are_read_only_on_patch(self):
        for send in (False, True):
            with self.subTest(sent=send):
                invoice = self.make_invoice(
                    items=[(self.product_a, Decimal("1.00"))],
                    send=send,
                    issue_date=date(2026, 1, 1),
                    due_date=date(2026, 1, 31),
                )
                before = {f: getattr(invoice, f) for f in SNAPSHOT_FIELDS}
                response = self.client.patch(
                    f"{LIST_URL}{invoice.id}/",
                    {"due_date": "2026-02-15", **FORGED},
                    format="json",
                )
                self.assertEqual(response.status_code, 200, response.data)
                invoice.refresh_from_db()
                self.assertEqual(str(invoice.due_date), "2026-02-15")
                self.assertEqual(
                    {f: getattr(invoice, f) for f in SNAPSHOT_FIELDS}, before
                )


class InvoicePaymentTotalsTests(InvoiceApiFixture):
    def test_paid_and_outstanding_are_strings_for_none_partial_split_and_full(self):
        cases = [
            ("none", [], "0.00", "1000.00"),
            ("partial", ["300.00"], "300.00", "700.00"),
            ("split", ["300.00", "200.50"], "500.50", "499.50"),
            ("full", ["1000.00"], "1000.00", "0.00"),
        ]
        for name, amounts, paid, outstanding in cases:
            with self.subTest(case=name):
                invoice = self.make_invoice(total="1000.00")
                for amount in amounts:
                    self.add_payment(invoice, amount)
                sources = (
                    ("detail", self.get_detail(invoice)),
                    ("list", self.get_list_rows()[invoice.id]),
                )
                for label, payload in sources:
                    with self.subTest(source=label):
                        self.assertEqual(payload.get("paid"), paid)
                        self.assertEqual(payload.get("outstanding"), outstanding)
                        self.assertEqual(len(payload.get("payments", [None])), len(amounts))

    def test_money_fields_quantize_to_two_places_half_up(self):
        fields = InvoiceSerializer().fields
        for name in ("total", "paid", "outstanding"):
            for raw, expected in (
                ("10.9500", "10.95"),
                ("10.9650", "10.97"),
                ("0", "0.00"),
            ):
                with self.subTest(field=name, raw=raw):
                    self.assertEqual(
                        fields[name].to_representation(Decimal(raw)), expected
                    )

    def test_list_outstanding_equals_aging_outstanding(self):
        today = date.today()
        unpaid = self.make_invoice(
            issue_date=today - timedelta(days=40), due_date=today - timedelta(days=10)
        )
        partial = self.make_invoice(
            issue_date=today - timedelta(days=80), due_date=today - timedelta(days=40)
        )
        self.add_payment(partial, "300.00")

        rows = self.get_list_rows()
        aging = self.client.get(reverse("invoice-aging"))
        self.assertEqual(aging.status_code, 200)
        aging_rows = {
            row["invoice_number"]: row
            for bucket in aging.data.values()
            for row in bucket
        }
        for invoice in (unpaid, partial):
            with self.subTest(invoice=invoice.invoice_number):
                self.assertEqual(
                    rows[invoice.id].get("outstanding"),
                    aging_rows[invoice.invoice_number]["outstanding"],
                )

    def test_payments_are_nested_with_exact_shape_ordered_by_date_then_id(self):
        invoice = self.make_invoice()
        late = self.add_payment(invoice, "100.00", "2026-02-10")
        early = self.add_payment(invoice, "50.00", "2026-02-01")
        tie = self.add_payment(invoice, "25.00", "2026-02-10")

        sources = (
            ("detail", self.get_detail(invoice)),
            ("list", self.get_list_rows()[invoice.id]),
        )
        for label, payload in sources:
            with self.subTest(source=label):
                payments = payload.get("payments", [])
                self.assertEqual(
                    [p["id"] for p in payments], [early.id, late.id, tie.id]
                )
                for p in payments:
                    self.assertEqual(set(p.keys()), PAYMENT_KEYS)
                self.assertEqual(
                    payments[0],
                    {
                        "id": early.id,
                        "amount": "50.00",
                        "payment_date": "2026-02-01",
                        "method": "cash",
                    },
                )


class InvoiceItemsShapeTests(InvoiceApiFixture):
    def test_items_expose_product_name_and_string_decimals(self):
        invoice = self.make_invoice(items=[(self.product_a, Decimal("2.00"))])
        sources = (
            ("detail", self.get_detail(invoice)),
            ("list", self.get_list_rows()[invoice.id]),
        )
        for label, payload in sources:
            with self.subTest(source=label):
                items = payload["items"]
                self.assertEqual(len(items), 1)
                self.assertEqual(set(items[0].keys()), ITEM_KEYS)
                self.assertEqual(
                    {
                        k: items[0][k]
                        for k in (
                            "product_name", "quantity", "unit_price",
                            "tax_rate", "discount", "hsn_sac_code", "line_total",
                        )
                    },
                    {
                        "product_name": "Product A",
                        "quantity": "2.00",
                        "unit_price": "10.05",
                        "tax_rate": "9.00",
                        "discount": "0.00",
                        "hsn_sac_code": "998314",
                        "line_total": "20.10",
                    },
                )


class InvoiceListOrderingTests(InvoiceApiFixture):
    def test_list_is_newest_issue_date_first_with_id_descending_on_ties(self):
        oldest = self.make_invoice(issue_date=date(2026, 3, 1))
        ties = [self.make_invoice(issue_date=date(2026, 3, 5)) for _ in range(6)]
        newest = self.make_invoice(issue_date=date(2026, 3, 9))

        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        expected = (
            [newest.id]
            + sorted((i.id for i in ties), reverse=True)
            + [oldest.id]
        )
        self.assertEqual([r["id"] for r in response.data["results"]], expected)


class InvoiceQueryCountTests(InvoiceApiFixture):
    def build(self, count):
        for _ in range(count):
            invoice = self.make_invoice(
                items=[
                    (self.product_a, Decimal("1.00")),
                    (self.product_b, Decimal("2.00")),
                ]
            )
            self.add_payment(invoice, "100.00")

    def capture(self, expected_rows):
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), expected_rows)
        return [q["sql"] for q in context.captured_queries]

    def test_list_query_count_is_constant_for_2_and_5_invoices(self):
        self.build(2)
        few = self.capture(2)
        self.build(3)
        many = self.capture(5)
        self.assertEqual(
            len(few),
            len(many),
            f"{len(few)} queries for 2 invoices, {len(many)} for 5. "
            f"Growing: {grown_queries(few, many)}",
        )

    def test_list_uses_five_queries_count_invoices_items_products_payments(self):
        self.build(3)
        queries = self.capture(3)
        self.assertEqual(
            len(queries), 5,
            f"expected 5 queries, got {len(queries)}:\n"
            + "\n".join(shape(q) for q in queries),
        )


class InvoiceAnonymousAccessTests(InvoiceApiFixture):
    def test_anonymous_list_and_detail_return_401(self):
        invoice = self.make_invoice()
        urls = [LIST_URL, f"{LIST_URL}{invoice.id}/"]
        for url in urls:
            with self.subTest(url=url, authenticated=True):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_authenticate(user=None)
        for url in urls:
            with self.subTest(url=url, authenticated=False):
                self.assertEqual(self.client.get(url).status_code, 401)


class InvoiceCreateResponseTests(InvoiceApiFixture):
    def test_post_response_money_values(self):
        product = Product.objects.create(
            name="Plain Product",
            unit_price=Decimal("10.95"),
            default_tax_rate=Decimal("0.00"),
            hsn_sac_code="998316",
        )
        payload = {
            "customer": self.customer.id,
            "issue_date": "2026-01-01",
            "due_date": "2026-01-31",
            "items": [{"product": product.id, "quantity": "1.00", "discount": "0"}],
        }
        response = self.client.post(LIST_URL, payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["total"], "10.95")
        self.assertEqual(response.data["paid"], "0.00")
        self.assertEqual(response.data["outstanding"], "10.95")
        self.assertEqual(list(response.data["payments"]), [])


class InvoiceEinvoiceFieldsTests(InvoiceApiFixture):
    def test_irn_and_qr_code_are_null_when_not_generated(self):
        invoice = self.make_invoice()
        payload = {
            "customer": self.customer.id,
            "issue_date": "2026-01-01",
            "due_date": "2026-01-31",
            "items": [
                {"product": self.product_a.id, "quantity": "1.00", "discount": "0"}
            ],
        }
        created = self.client.post(LIST_URL, payload, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        bodies = (
            ("detail", self.get_detail(invoice)),
            ("list", self.get_list_rows()[invoice.id]),
            ("post", created.data),
        )
        for label, body in bodies:
            for key in ("irn", "qr_code"):
                with self.subTest(source=label, key=key):
                    self.assertIn(key, body)
                    self.assertIsNone(body[key])
