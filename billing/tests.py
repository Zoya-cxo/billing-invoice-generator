from decimal import Decimal
from unittest import mock
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Customer, Product, Invoice, InvoiceItem, Payment, Company
from .serializers import InvoiceSerializer


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
            "invoice_number": "INV-ROUND-001",
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
            "invoice_number": "INV-ROLLBACK-001",
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

        self.assertFalse(
            Invoice.objects.filter(invoice_number="INV-ROLLBACK-001").exists()
        )
        self.assertFalse(
            InvoiceItem.objects.filter(product=self.product_a).exists()
        )
