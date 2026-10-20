from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import Invoice
from .test_invoice_api import InvoiceApiFixture


class DashboardAnonymousTests(APITestCase):
    def test_anonymous_request_gets_401(self):
        response = self.client.get("/api/v1/dashboard/")
        self.assertEqual(response.status_code, 401)


FIXED_TODAY = date(2030, 6, 15)
MONEY_KEYS = ["revenue_collected", "outstanding", "overdue"]
STATUSES = ["draft", "sent", "paid", "overdue", "cancelled"]
EXPECTED_MONTHS = ["2030-01", "2030-02", "2030-03", "2030-04", "2030-05", "2030-06"]


class DashboardEmptyDatabaseTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="dashemptyadmin", password="testpass123"
        )
        self.client.force_authenticate(user=user)

    def get_dashboard(self):
        with mock.patch("billing.dates.business_today", return_value=FIXED_TODAY):
            response = self.client.get("/api/v1/dashboard/")
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_exact_key_set_is_present(self):
        self.assertEqual(
            set(self.get_dashboard()),
            {
                "revenue_collected",
                "outstanding",
                "overdue",
                "invoice_counts",
                "monthly_revenue",
                "recent_invoices",
            },
        )

    def test_money_fields_are_the_string_0_00(self):
        data = self.get_dashboard()
        for key in MONEY_KEYS:
            with self.subTest(field=key):
                self.assertEqual(data.get(key), "0.00")

    def test_all_five_status_counts_are_present_as_integer_zero(self):
        self.assertEqual(
            self.get_dashboard().get("invoice_counts"),
            {status: 0 for status in STATUSES},
        )

    def test_six_zero_filled_months_oldest_first(self):
        self.assertEqual(
            self.get_dashboard().get("monthly_revenue"),
            [{"month": m, "revenue": "0.00"} for m in EXPECTED_MONTHS],
        )

    def test_recent_invoices_is_an_empty_list(self):
        self.assertEqual(self.get_dashboard().get("recent_invoices"), [])


class DashboardRevenueCollectedTests(InvoiceApiFixture):
    def test_revenue_collected_includes_payments_on_cancelled_invoices(self):
        kept = self.make_invoice()
        cancelled = self.make_invoice()
        self.add_payment(kept, '300.00')
        self.add_payment(kept, '100.25')
        self.add_payment(cancelled, '200.50')
        cancelled.transition_to(Invoice.STATUS_CANCELLED)
        response = self.client.get('/api/v1/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['revenue_collected'], '600.75')
