import threading
import time
from decimal import Decimal
from unittest import mock
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connections, transaction
from django.test import TransactionTestCase
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.test import APITestCase

from .models import (
    Customer, Product, Invoice, InvoiceItem, Payment, Company,
    InvoiceNumberCounter,
)
from .serializers import InvoiceSerializer, PaymentSerializer


class PaymentViewSetTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="testadmin", password="testpass123")
        self.client.force_authenticate(user=self.user)

        self.customer = Customer.objects.create(
            name="Test Customer",
            email="customer@example.com",
            phone="9999999999",
            billing_address="123 Test Street",
        )

        self.product = Product.objects.create(
            name="Test Product",
            unit_price=Decimal("1000.00"),
            default_tax_rate=Decimal("18.00"),
            hsn_sac_code="998314",
        )

    def _build_invoice(self, invoice_number, status_value, quantity=Decimal("1")):
        invoice = Invoice.objects.create(
            invoice_number=invoice_number,
            customer=self.customer,
            issue_date="2026-01-01",
            due_date="2026-01-31",
            seller_name="Test Seller Pvt Ltd",
            seller_gstin="27AAAPL1234C1Z5",
            seller_state="27",
            seller_address="Test Seller Address, Pune",
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            product=self.product,
            quantity=quantity,
            unit_price=self.product.unit_price,
            tax_rate=self.product.default_tax_rate,
            hsn_sac_code=self.product.hsn_sac_code,
        )
        items = invoice.items.all()
        subtotal = sum(item.line_total for item in items)
        tax_total = sum((item.line_total * item.tax_rate / 100) for item in items)
        invoice.subtotal = subtotal
        invoice.tax_total = tax_total
        invoice.total = subtotal + tax_total
        invoice.save(update_fields=["subtotal", "tax_total", "total"])
        invoice.refresh_from_db()

        if status_value != Invoice.STATUS_DRAFT:
            invoice.transition_to(Invoice.STATUS_SENT)
        if status_value == Invoice.STATUS_OVERDUE:
            invoice.transition_to(Invoice.STATUS_OVERDUE)

        return invoice

    def _payment_payload(self, invoice, amount, method=Payment.METHOD_CASH, key=None):
        return {
            "invoice": invoice.id,
            "amount": str(amount),
            "payment_date": "2026-01-15",
            "method": method,
            "idempotency_key": str(key or uuid4()),
        }

    def test_create_payment_against_sent_invoice_succeeds(self):
        invoice = self._build_invoice("INV-001", Invoice.STATUS_SENT)
        payload = self._payment_payload(invoice, Decimal("500.00"))
        response = self.client.post("/api/v1/payments/", payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Payment.objects.count(), 1)

    def test_create_payment_against_draft_invoice_rejected(self):
        invoice = self._build_invoice("INV-002", Invoice.STATUS_DRAFT)
        payload = self._payment_payload(invoice, Decimal("500.00"))
        response = self.client.post("/api/v1/payments/", payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Payment.objects.count(), 0)

    def test_create_payment_against_overdue_invoice_succeeds(self):
        invoice = self._build_invoice("INV-003", Invoice.STATUS_OVERDUE)
        payload = self._payment_payload(invoice, Decimal("500.00"))
        response = self.client.post("/api/v1/payments/", payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_payment_update_returns_405(self):
        invoice = self._build_invoice("INV-004", Invoice.STATUS_SENT)
        payment = Payment.objects.create(
            invoice=invoice, amount=Decimal("100.00"), payment_date="2026-01-15",
            method=Payment.METHOD_CASH, idempotency_key=uuid4(),
        )
        response = self.client.patch(f"/api/v1/payments/{payment.id}/", {"amount": "200.00"})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_payment_delete_returns_405(self):
        invoice = self._build_invoice("INV-005", Invoice.STATUS_SENT)
        payment = Payment.objects.create(
            invoice=invoice, amount=Decimal("100.00"), payment_date="2026-01-15",
            method=Payment.METHOD_CASH, idempotency_key=uuid4(),
        )
        response = self.client.delete(f"/api/v1/payments/{payment.id}/")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_payment_exceeding_outstanding_balance_rejected(self):
        invoice = self._build_invoice("INV-006", Invoice.STATUS_SENT)
        overpay = invoice.total + Decimal("1.00")
        payload = self._payment_payload(invoice, overpay)
        response = self.client.post("/api/v1/payments/", payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Payment.objects.count(), 0)

    def test_payment_exactly_matching_outstanding_balance_succeeds(self):
        invoice = self._build_invoice("INV-007", Invoice.STATUS_SENT)
        payload = self._payment_payload(invoice, invoice.total)
        response = self.client.post("/api/v1/payments/", payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_duplicate_idempotency_key_rejected(self):
        invoice = self._build_invoice("INV-008", Invoice.STATUS_SENT)
        key = uuid4()
        first = self._payment_payload(invoice, Decimal("100.00"), key=key)
        response1 = self.client.post("/api/v1/payments/", first)
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        second = self._payment_payload(invoice, Decimal("50.00"), key=key)
        response2 = self.client.post("/api/v1/payments/", second)
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Payment.objects.count(), 1)

    def test_same_amount_different_idempotency_key_succeeds(self):
        invoice = self._build_invoice("INV-009", Invoice.STATUS_SENT, quantity=Decimal("10"))
        first = self._payment_payload(invoice, Decimal("100.00"))
        response1 = self.client.post("/api/v1/payments/", first)
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        second = self._payment_payload(invoice, Decimal("100.00"))
        response2 = self.client.post("/api/v1/payments/", second)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Payment.objects.count(), 2)

    def test_payment_missing_idempotency_key_rejected(self):
        invoice = self._build_invoice("INV-010", Invoice.STATUS_SENT)
        payload = self._payment_payload(invoice, Decimal("100.00"))
        del payload["idempotency_key"]
        response = self.client.post("/api/v1/payments/", payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Payment.objects.count(), 0)

    def test_payment_invalid_method_rejected(self):
        invoice = self._build_invoice("INV-011", Invoice.STATUS_SENT)
        payload = self._payment_payload(invoice, Decimal("100.00"), method="bitcoin")
        response = self.client.post("/api/v1/payments/", payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Payment.objects.count(), 0)

    def test_payment_zero_or_negative_amount_rejected(self):
        invoice = self._build_invoice("INV-012", Invoice.STATUS_SENT)
        for bad_amount in (Decimal("0.00"), Decimal("-50.00")):
            with self.subTest(amount=bad_amount):
                payload = self._payment_payload(invoice, bad_amount)
                response = self.client.post("/api/v1/payments/", payload)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Payment.objects.count(), 0)

    def test_payment_list_returns_created_payments(self):
        invoice = self._build_invoice("INV-013", Invoice.STATUS_SENT)
        payload = self._payment_payload(invoice, Decimal("100.00"))
        self.client.post("/api/v1/payments/", payload)

        response = self.client.get("/api/v1/payments/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"] if "results" in response.data else response.data), 1)


class CustomerViewSetDeleteTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="testadmin2", password="testpass123")
        self.client.force_authenticate(user=self.user)

        self.customer = Customer.objects.create(
            name="Delete Test Customer",
            email="deletetest@example.com",
            phone="8888888888",
            billing_address="456 Delete Street",
        )

    def test_delete_customer_without_invoices_succeeds(self):
        response = self.client.delete(f"/api/v1/customers/{self.customer.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Customer.objects.filter(id=self.customer.id).exists())

    def test_delete_customer_with_invoice_returns_409(self):
        Invoice.objects.create(
            invoice_number="INV-DELETE-TEST-001",
            customer=self.customer,
            issue_date="2026-01-01",
            due_date="2026-01-31",
            seller_name="Test Seller Pvt Ltd",
            seller_gstin="27AAAPL1234C1Z5",
            seller_state="27",
            seller_address="Test Seller Address, Pune",
        )

        response = self.client.delete(f"/api/v1/customers/{self.customer.id}/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("detail", response.data)
        self.assertTrue(Customer.objects.filter(id=self.customer.id).exists())


class ProductViewSetDeleteTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="testadmin3", password="testpass123")
        self.client.force_authenticate(user=self.user)

        self.customer = Customer.objects.create(
            name="Product Delete Test Customer",
            email="productdeletetest@example.com",
            phone="7777777777",
            billing_address="789 Delete Street",
        )

        self.product = Product.objects.create(
            name="Product Delete Test Product",
            unit_price=Decimal("500.00"),
            default_tax_rate=Decimal("18.00"),
            hsn_sac_code="998315",
        )

    def test_delete_product_without_invoice_items_succeeds(self):
        response = self.client.delete(f"/api/v1/products/{self.product.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Product.objects.filter(id=self.product.id).exists())

    def test_delete_product_with_invoice_item_returns_409(self):
        invoice = Invoice.objects.create(
            invoice_number="INV-PRODUCT-DELETE-TEST-001",
            customer=self.customer,
            issue_date="2026-01-01",
            due_date="2026-01-31",
            seller_name="Test Seller Pvt Ltd",
            seller_gstin="27AAAPL1234C1Z5",
            seller_state="27",
            seller_address="Test Seller Address, Pune",
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            product=self.product,
            quantity=Decimal("1"),
            unit_price=self.product.unit_price,
            tax_rate=self.product.default_tax_rate,
            hsn_sac_code=self.product.hsn_sac_code,
        )

        response = self.client.delete(f"/api/v1/products/{self.product.id}/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("detail", response.data)
        self.assertTrue(Product.objects.filter(id=self.product.id).exists())


class ProductValidationTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="testadmin4", password="testpass123")
        self.client.force_authenticate(user=self.user)

    def test_negative_unit_price_rejected(self):
        response = self.client.post("/api/v1/products/", {
            "name": "Bad Price Product",
            "unit_price": "-5.00",
            "default_tax_rate": "18.00",
            "hsn_sac_code": "998316",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("unit_price", response.data)

    def test_zero_unit_price_rejected(self):
        response = self.client.post("/api/v1/products/", {
            "name": "Zero Price Product",
            "unit_price": "0.00",
            "default_tax_rate": "18.00",
            "hsn_sac_code": "998316",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("unit_price", response.data)

    def test_negative_tax_rate_rejected(self):
        response = self.client.post("/api/v1/products/", {
            "name": "Bad Tax Product",
            "unit_price": "100.00",
            "default_tax_rate": "-1.00",
            "hsn_sac_code": "998316",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("default_tax_rate", response.data)

    def test_zero_tax_rate_accepted(self):
        response = self.client.post("/api/v1/products/", {
            "name": "Exempt Product",
            "unit_price": "100.00",
            "default_tax_rate": "0.00",
            "hsn_sac_code": "998316",
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class InvoiceSerializerBugFixTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="testadmin2", password="testpass123")
        self.client.force_authenticate(user=self.user)

        self.company = Company.objects.create(
            name="Test Seller Pvt Ltd",
            gstin="27AAAPL1234C1Z5",
            state="27",
            registered_address="Test Seller Address, Pune",
        )
        self.customer = Customer.objects.create(
            name="Test Customer 2",
            email="customer2@example.com",
            phone="9999999998",
            billing_address="456 Test Street",
        )
        self.product_a = Product.objects.create(
            name="Product A",
            unit_price=Decimal("10.05"),
            default_tax_rate=Decimal("9.00"),
            hsn_sac_code="998314",
        )
        self.product_b = Product.objects.create(
            name="Product B",
            unit_price=Decimal("10.15"),
            default_tax_rate=Decimal("9.00"),
            hsn_sac_code="998315",
        )

    def test_per_line_rounding_diverges_from_aggregate_rounding(self):
        data = {
            "customer": self.customer.id,
            "issue_date": "2026-01-01",
            "due_date": "2026-01-31",
            "items": [
                {"product": self.product_a.id, "quantity": "1.00", "discount": "0"},
                {"product": self.product_b.id, "quantity": "1.00", "discount": "0"},
            ],
        }
        serializer = InvoiceSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()

        # Per-line-then-sum (the fix): round(0.9045)=0.90, round(0.9135)=0.91 -> 1.81
        # Aggregate-then-round (the bug this fix replaced): 0.9045+0.9135=1.818 -> 1.82
        self.assertEqual(invoice.tax_total, Decimal("1.81"))

    def test_create_rolls_back_partial_invoice_on_mid_creation_failure(self):
        data = {
            "customer": self.customer.id,
            "issue_date": "2026-01-01",
            "due_date": "2026-01-31",
            "items": [
                {"product": self.product_a.id, "quantity": "1.00", "discount": "0"},
                {"product": self.product_b.id, "quantity": "1.00", "discount": "0"},
            ],
        }
        serializer = InvoiceSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        invoice_count_before = Invoice.objects.count()
        counter_before = InvoiceNumberCounter.objects.get(pk=1).last_number

        real_create = InvoiceItem.objects.create
        call_count = {"n": 0}

        def flaky_create(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise IntegrityError("simulated mid-creation failure")
            return real_create(*args, **kwargs)

        # First call goes through to the real manager method (a genuine committed
        # row), second call raises - this only proves atomic() works if there was
        # something real for it to undo.
        with mock.patch.object(InvoiceItem.objects, "create", side_effect=flaky_create):
            with self.assertRaises(IntegrityError):
                serializer.save()

        self.assertEqual(Invoice.objects.count(), invoice_count_before)
        self.assertEqual(
            InvoiceNumberCounter.objects.get(pk=1).last_number, counter_before
        )
        self.assertFalse(
            InvoiceItem.objects.filter(product=self.product_a).exists()
        )

    def _create_invoice_payload(self):
        return {
            "customer": self.customer.id,
            "issue_date": "2026-01-01",
            "due_date": "2026-01-31",
            "items": [
                {"product": self.product_a.id, "quantity": "1.00", "discount": "0"},
            ],
        }

    def test_sequential_creates_get_sequential_numbers(self):
        start = InvoiceNumberCounter.objects.get(pk=1).last_number
        numbers = []
        for _ in range(2):
            serializer = InvoiceSerializer(data=self._create_invoice_payload())
            serializer.is_valid(raise_exception=True)
            numbers.append(serializer.save().invoice_number)
        self.assertEqual(numbers, [f"INV-{start + 1:06d}", f"INV-{start + 2:06d}"])

    def test_client_supplied_invoice_number_is_ignored(self):
        start = InvoiceNumberCounter.objects.get(pk=1).last_number
        payload = self._create_invoice_payload()
        payload["invoice_number"] = "INV-CLIENT-CHOSEN"
        serializer = InvoiceSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()
        self.assertEqual(invoice.invoice_number, f"INV-{start + 1:06d}")

    def test_missing_counter_row_logs_and_raises_api_exception(self):
        InvoiceNumberCounter.objects.all().delete()
        invoice_count_before = Invoice.objects.count()
        serializer = InvoiceSerializer(data=self._create_invoice_payload())
        serializer.is_valid(raise_exception=True)

        with self.assertLogs("billing.serializers", level="ERROR") as logs:
            with self.assertRaises(APIException):
                serializer.save()

        self.assertIn("InvoiceNumberCounter", logs.output[0])
        self.assertEqual(Invoice.objects.count(), invoice_count_before)

    def test_create_rejects_non_draft_status_with_400(self):
        for status_value in ["sent", "paid", "overdue", "cancelled"]:
            with self.subTest(status=status_value):
                invoice_count_before = Invoice.objects.count()
                counter_before = InvoiceNumberCounter.objects.get(pk=1).last_number
                payload = self._create_invoice_payload()
                payload["status"] = status_value
                response = self.client.post("/api/v1/invoices/", payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("status", response.data)
                self.assertEqual(Invoice.objects.count(), invoice_count_before)
                self.assertEqual(
                    InvoiceNumberCounter.objects.get(pk=1).last_number, counter_before
                )

    def test_create_accepts_explicit_draft_status(self):
        payload = self._create_invoice_payload()
        payload["status"] = "draft"
        response = self.client.post("/api/v1/invoices/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "draft")

    def test_create_rejects_quantity_below_minimum(self):
        for quantity in ["0", "0.00", "-1.00"]:
            with self.subTest(quantity=quantity):
                invoice_count_before = Invoice.objects.count()
                counter_before = InvoiceNumberCounter.objects.get(pk=1).last_number
                payload = self._create_invoice_payload()
                payload["items"][0]["quantity"] = quantity
                response = self.client.post("/api/v1/invoices/", payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("quantity", response.data["items"][0])
                self.assertEqual(Invoice.objects.count(), invoice_count_before)
                self.assertEqual(
                    InvoiceNumberCounter.objects.get(pk=1).last_number, counter_before
                )

    def test_create_accepts_minimum_quantity(self):
        payload = self._create_invoice_payload()
        payload["items"][0]["quantity"] = "0.01"
        response = self.client.post("/api/v1/invoices/", payload, format="json")
        self.assertEqual(response.status_code, 201)

    def test_create_rejects_discount_above_line_amount(self):
        cases = [("1.00", "10.06"), ("2.00", "20.11"), ("0.50", "5.03")]
        for quantity, discount in cases:
            with self.subTest(quantity=quantity, discount=discount):
                invoice_count_before = Invoice.objects.count()
                counter_before = InvoiceNumberCounter.objects.get(pk=1).last_number
                payload = self._create_invoice_payload()
                payload["items"][0]["quantity"] = quantity
                payload["items"][0]["discount"] = discount
                response = self.client.post("/api/v1/invoices/", payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("discount", response.data["items"][0])
                self.assertEqual(Invoice.objects.count(), invoice_count_before)
                self.assertEqual(
                    InvoiceNumberCounter.objects.get(pk=1).last_number, counter_before
                )

    def test_create_accepts_discount_up_to_line_amount(self):
        cases = [("1.00", "10.05"), ("0.50", "5.02")]
        for quantity, discount in cases:
            with self.subTest(quantity=quantity, discount=discount):
                payload = self._create_invoice_payload()
                payload["items"][0]["quantity"] = quantity
                payload["items"][0]["discount"] = discount
                response = self.client.post("/api/v1/invoices/", payload, format="json")
                self.assertEqual(response.status_code, 201)

    def test_create_rejects_due_date_before_issue_date(self):
        cases = [("2026-01-01", "2025-12-31"), ("2026-01-02", "2026-01-01")]
        for issue_date, due_date in cases:
            with self.subTest(issue_date=issue_date, due_date=due_date):
                invoice_count_before = Invoice.objects.count()
                counter_before = InvoiceNumberCounter.objects.get(pk=1).last_number
                payload = self._create_invoice_payload()
                payload["issue_date"] = issue_date
                payload["due_date"] = due_date
                response = self.client.post("/api/v1/invoices/", payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("due_date", response.data)
                self.assertEqual(Invoice.objects.count(), invoice_count_before)
                self.assertEqual(
                    InvoiceNumberCounter.objects.get(pk=1).last_number, counter_before
                )

    def test_create_accepts_due_date_on_or_after_issue_date(self):
        cases = [("2026-01-15", "2026-01-15"), ("2026-01-15", "2026-02-14")]
        for issue_date, due_date in cases:
            with self.subTest(issue_date=issue_date, due_date=due_date):
                payload = self._create_invoice_payload()
                payload["issue_date"] = issue_date
                payload["due_date"] = due_date
                response = self.client.post("/api/v1/invoices/", payload, format="json")
                self.assertEqual(response.status_code, 201)

    def test_create_rejects_negative_discount(self):
        for discount in ["-0.01", "-1.00", "-10.05"]:
            with self.subTest(discount=discount):
                invoice_count_before = Invoice.objects.count()
                counter_before = InvoiceNumberCounter.objects.get(pk=1).last_number
                payload = self._create_invoice_payload()
                payload["items"][0]["discount"] = discount
                response = self.client.post("/api/v1/invoices/", payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("discount", response.data["items"][0])
                self.assertEqual(Invoice.objects.count(), invoice_count_before)
                self.assertEqual(
                    InvoiceNumberCounter.objects.get(pk=1).last_number, counter_before
                )

    def test_create_accepts_zero_and_small_positive_discount(self):
        for discount in ["0", "0.00", "0.01"]:
            with self.subTest(discount=discount):
                payload = self._create_invoice_payload()
                payload["items"][0]["discount"] = discount
                response = self.client.post("/api/v1/invoices/", payload, format="json")
                self.assertEqual(response.status_code, 201)


class InvoiceNumberCounterConcurrencyTests(TransactionTestCase):
    THREADS = 8

    def setUp(self):
        InvoiceNumberCounter.objects.update_or_create(pk=1, defaults={"last_number": 0})

    def test_concurrent_get_next_number_returns_distinct_numbers(self):
        barrier = threading.Barrier(self.THREADS)
        results_lock = threading.Lock()
        numbers = []
        errors = []
        real_save = InvoiceNumberCounter.save

        def slow_save(instance, *args, **kwargs):
            time.sleep(0.05)
            return real_save(instance, *args, **kwargs)

        def worker():
            try:
                barrier.wait(timeout=10)
                with transaction.atomic():
                    number = InvoiceNumberCounter.get_next_number()
                with results_lock:
                    numbers.append(number)
            except Exception as exc:
                with results_lock:
                    errors.append(exc)
            finally:
                connections.close_all()

        with mock.patch.object(InvoiceNumberCounter, "save", slow_save):
            threads = [threading.Thread(target=worker) for _ in range(self.THREADS)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)

        self.assertEqual(errors, [])
        self.assertEqual(len(numbers), self.THREADS)
        self.assertEqual(len(set(numbers)), self.THREADS)
        self.assertEqual(
            InvoiceNumberCounter.objects.get(pk=1).last_number, self.THREADS
        )


class CustomerProductListOrderingTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="testadmin_ordering", password="testpass123")
        self.client.force_authenticate(user=self.user)

    def test_customers_with_equal_names_are_listed_in_id_order(self):
        customers = [
            Customer.objects.create(
                name="Same Name",
                email=f"samename{i}@example.com",
                phone=f"90000000{i:02d}",
                billing_address="1 Same Name Street",
                state="27",
            )
            for i in range(3)
        ]
        customers[0].phone = "9111111111"
        customers[0].save()
        response = self.client.get("/api/v1/customers/")
        self.assertEqual(response.status_code, 200)
        listed_ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(listed_ids, sorted(c.id for c in customers))

    def test_products_with_equal_names_are_listed_in_id_order(self):
        products = [
            Product.objects.create(
                name="Same Name",
                unit_price=Decimal("100.00"),
                default_tax_rate=Decimal("18.00"),
                hsn_sac_code="998315",
            )
            for _ in range(3)
        ]
        products[0].unit_price = Decimal("101.00")
        products[0].save()
        response = self.client.get("/api/v1/products/")
        self.assertEqual(response.status_code, 200)
        listed_ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(listed_ids, sorted(p.id for p in products))


class PaymentConcurrencyTests(TransactionTestCase):
    THREADS = 2

    def setUp(self):
        self.customer = Customer.objects.create(
            name="Test Customer",
            email="customer@example.com",
            phone="9999999999",
            billing_address="123 Test Street",
        )
        self.product = Product.objects.create(
            name="Test Product",
            unit_price=Decimal("1000.00"),
            default_tax_rate=Decimal("0.00"),
            hsn_sac_code="998314",
        )
        self.invoice = Invoice.objects.create(
            invoice_number="INV-CONC-001",
            customer=self.customer,
            issue_date="2026-01-01",
            due_date="2026-01-31",
            seller_name="Test Seller Pvt Ltd",
            seller_gstin="27AAAPL1234C1Z5",
            seller_state="27",
            seller_address="Test Seller Address, Pune",
        )
        InvoiceItem.objects.create(
            invoice=self.invoice,
            product=self.product,
            quantity=Decimal("1"),
            unit_price=self.product.unit_price,
            tax_rate=self.product.default_tax_rate,
            hsn_sac_code=self.product.hsn_sac_code,
        )
        self.invoice.subtotal = Decimal("1000.00")
        self.invoice.tax_total = Decimal("0.00")
        self.invoice.total = Decimal("1000.00")
        self.invoice.save(update_fields=["subtotal", "tax_total", "total"])
        self.invoice.refresh_from_db()
        self.invoice.transition_to(Invoice.STATUS_SENT)

    def test_concurrent_payments_cannot_jointly_exceed_outstanding_balance(self):
        barrier = threading.Barrier(self.THREADS)
        results_lock = threading.Lock()
        successes = []
        errors = []
        real_save = Payment.save

        def slow_save(instance, *args, **kwargs):
            time.sleep(0.05)
            return real_save(instance, *args, **kwargs)

        def worker():
            try:
                barrier.wait(timeout=10)
                serializer = PaymentSerializer(data={
                    "invoice": self.invoice.id,
                    "amount": "700.00",
                    "payment_date": "2026-01-15",
                    "method": Payment.METHOD_CASH,
                    "idempotency_key": str(uuid4()),
                })
                serializer.is_valid(raise_exception=True)
                serializer.save()
                with results_lock:
                    successes.append(True)
            except Exception as exc:
                with results_lock:
                    errors.append(exc)
            finally:
                connections.close_all()

        with mock.patch.object(Payment, "save", slow_save):
            threads = [threading.Thread(target=worker) for _ in range(self.THREADS)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(errors), 1)
        self.assertEqual(Payment.objects.filter(invoice=self.invoice).count(), 1)
        total_paid = sum(p.amount for p in Payment.objects.filter(invoice=self.invoice))
        self.invoice.refresh_from_db()
        self.assertLessEqual(total_paid, self.invoice.total)
