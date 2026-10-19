from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import Customer, Invoice

FIXED_TODAY = date(2030, 6, 15)
ORIGINAL_NAME = "Original Name Traders"
RENAMED = "Renamed Name Traders"


class AgingKeepsSnapshotNameTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="agingnameadmin", password="testpass123"
        )
        self.client.force_authenticate(user=user)
        self.customer = Customer.objects.create(
            name=ORIGINAL_NAME,
            email="agingname@example.com",
            phone="9999999992",
            state="27",
            billing_address="Aging Name Address",
        )
        self.invoice = Invoice.objects.create(
            invoice_number="NAME-0001",
            customer=self.customer,
            customer_name=ORIGINAL_NAME,
            customer_state="27",
            customer_billing_address="Aging Name Address",
            status="sent",
            seller_name="Name Seller",
            seller_gstin="00TEST0000T1Z5",
            seller_state="27",
            seller_address="Name Seller Address",
            issue_date=FIXED_TODAY,
            due_date=date(2030, 6, 5),
            subtotal=Decimal("500.00"),
            tax_total=Decimal("0.00"),
            total=Decimal("500.00"),
        )

    def aging_row(self):
        with mock.patch("billing.dates.business_today", return_value=FIXED_TODAY):
            response = self.client.get("/api/v1/invoices/aging/")
        self.assertEqual(response.status_code, 200)
        rows = [r for bucket in response.data.values() for r in bucket]
        matching = [r for r in rows if r["invoice_number"] == "NAME-0001"]
        self.assertEqual(len(matching), 1)
        return matching[0]

    def test_row_shows_snapshot_name_before_any_rename(self):
        self.assertEqual(self.aging_row()["customer"], ORIGINAL_NAME)

    def test_row_keeps_snapshot_name_after_the_live_customer_is_renamed(self):
        Customer.objects.filter(pk=self.customer.pk).update(name=RENAMED)
        self.assertEqual(Customer.objects.get(pk=self.customer.pk).name, RENAMED)
        self.assertEqual(self.aging_row()["customer"], ORIGINAL_NAME)
