from datetime import date
from decimal import Decimal
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


class DashboardInvoiceCountsTests(InvoiceApiFixture):
    def test_invoice_counts_match_the_number_of_invoices_per_status(self):
        wanted = {
            Invoice.STATUS_DRAFT: 1,
            Invoice.STATUS_SENT: 2,
            Invoice.STATUS_OVERDUE: 3,
            Invoice.STATUS_PAID: 4,
            Invoice.STATUS_CANCELLED: 5,
        }
        for status, how_many in wanted.items():
            for _ in range(how_many):
                invoice = self.make_invoice(send=status != Invoice.STATUS_DRAFT)
                if status in (Invoice.STATUS_OVERDUE, Invoice.STATUS_PAID, Invoice.STATUS_CANCELLED):
                    invoice.transition_to(status)
        response = self.client.get('/api/v1/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['invoice_counts'], wanted)


class DashboardOutstandingOverdueTests(InvoiceApiFixture):
    def setUp(self):
        super().setUp()
        patcher = mock.patch('billing.dates.business_today', return_value=FIXED_TODAY)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.make_invoice(total='1000.00', due_date=date(2030, 6, 15))
        self.make_invoice(total='500.00', due_date=date(2030, 6, 14))
        part_paid = self.make_invoice(total='400.00', due_date=date(2030, 5, 16))
        self.add_payment(part_paid, '150.25')
        flagged = self.make_invoice(total='300.00', due_date=date(2030, 5, 15))
        flagged.transition_to(Invoice.STATUS_OVERDUE)
        fully_paid = self.make_invoice(total='700.00', due_date=date(2030, 4, 1))
        self.add_payment(fully_paid, '700.00')
        self.make_invoice(total='900.00', due_date=date(2030, 7, 15), send=False)
        cancelled = self.make_invoice(total='800.00', due_date=date(2030, 5, 6))
        cancelled.transition_to(Invoice.STATUS_CANCELLED)

    def get_dashboard(self):
        response = self.client.get('/api/v1/dashboard/')
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_outstanding_is_the_unpaid_balance_of_issued_invoices_only(self):
        self.assertEqual(self.get_dashboard()['outstanding'], '2049.75')

    def test_overdue_is_the_part_of_outstanding_past_its_due_date(self):
        self.assertEqual(self.get_dashboard()['overdue'], '1049.75')

    def test_dashboard_figures_equal_the_sums_of_the_aging_buckets(self):
        aging = self.client.get('/api/v1/invoices/aging/').data
        dashboard = self.get_dashboard()
        overdue_keys = ['days_0_30', 'days_31_60', 'days_61_90', 'days_90_plus']

        def bucket_total(keys):
            return sum(
                (Decimal(row['outstanding']) for key in keys for row in aging[key]),
                Decimal('0'),
            )

        self.assertEqual(dashboard['outstanding'], str(bucket_total(['not_due'] + overdue_keys)))
        self.assertEqual(dashboard['overdue'], str(bucket_total(overdue_keys)))


class DashboardMonthlyRevenueTests(InvoiceApiFixture):
    def setUp(self):
        super().setUp()
        patcher = mock.patch('billing.dates.business_today', return_value=FIXED_TODAY)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.invoice = self.make_invoice(total='100000.00')

    def add_payments(self, rows):
        for payment_date, amount in rows:
            self.add_payment(self.invoice, amount, payment_date)

    def get_months(self):
        response = self.client.get('/api/v1/dashboard/')
        self.assertEqual(response.status_code, 200)
        return [(m['month'], m['revenue']) for m in response.data['monthly_revenue']]

    def test_months_sum_payments_by_calendar_month_within_the_window(self):
        self.add_payments([
            ('2029-12-31', '1.00'),
            ('2030-01-01', '10.00'),
            ('2030-01-31', '20.00'),
            ('2030-03-10', '5.50'),
            ('2030-03-11', '0.25'),
            ('2030-06-30', '7.25'),
            ('2030-07-01', '100.00'),
        ])
        self.add_payment(self.invoice, '3.00')
        self.assertEqual(self.get_months(), [
            ('2030-01', '30.00'),
            ('2030-02', '0.00'),
            ('2030-03', '5.75'),
            ('2030-04', '0.00'),
            ('2030-05', '0.00'),
            ('2030-06', '7.25'),
        ])

    def test_window_crosses_the_year_boundary(self):
        with mock.patch('billing.dates.business_today', return_value=date(2030, 2, 10)):
            self.add_payments([
                ('2029-08-31', '1.00'),
                ('2029-09-01', '2.00'),
                ('2029-12-31', '4.00'),
                ('2030-01-01', '8.00'),
                ('2030-02-28', '16.00'),
                ('2030-03-01', '32.00'),
            ])
            self.assertEqual(self.get_months(), [
                ('2029-09', '2.00'),
                ('2029-10', '0.00'),
                ('2029-11', '0.00'),
                ('2029-12', '4.00'),
                ('2030-01', '8.00'),
                ('2030-02', '16.00'),
            ])
