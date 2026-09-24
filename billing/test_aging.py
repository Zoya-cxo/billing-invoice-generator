from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from .aging_scenarios import SCENARIOS, EXCLUDED, due_date_for, payment_amount_for
from .models import Customer, Invoice, Payment

ALL_BUCKET_KEYS = ['not_due', 'days_0_30', 'days_31_60', 'days_61_90', 'days_90_plus']


class AgingReportTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="testadmin", password="testpass123")
        self.client.force_authenticate(user=self.user)

        self.customer = Customer.objects.create(
            name="Test Customer",
            email="customer@example.com",
            phone="9999999999",
            state="27",
            billing_address="Test Address",
        )

        self.today = date.today()
        self.invoices_by_name = {}

        for scenario in SCENARIOS:
            due_date = due_date_for(scenario, self.today)
            total = scenario['total']

            invoice = Invoice.objects.create(
                invoice_number=f"TEST-AGING-{scenario['name']}",
                customer=self.customer,
                status=scenario['status'],
                seller_name='Test Seller',
                seller_gstin='00TEST0000T1Z5',
                seller_state='27',
                seller_address='Test Seller Address',
                issue_date=self.today,
                due_date=due_date,
                subtotal=total,
                tax_total=Decimal('0.00'),
                total=total,
            )
            self.invoices_by_name[scenario['name']] = invoice

            payment_amount = payment_amount_for(scenario)
            if payment_amount > 0:
                Payment.objects.create(
                    invoice=invoice,
                    amount=payment_amount,
                    payment_date=self.today,
                    method=Payment.METHOD_CASH,
                )

    def _get_aging_response(self):
        url = reverse('invoice-aging')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return response.data

    def _find_bucket_containing(self, data, invoice_number):
        found_in = []
        for bucket_key in ALL_BUCKET_KEYS:
            for row in data[bucket_key]:
                if row['invoice_number'] == invoice_number:
                    found_in.append(bucket_key)
        return found_in

    def test_each_scenario_lands_in_expected_bucket_or_is_excluded(self):
        data = self._get_aging_response()

        for scenario in SCENARIOS:
            invoice = self.invoices_by_name[scenario['name']]
            found_in = self._find_bucket_containing(data, invoice.invoice_number)

            if scenario['expected'] == EXCLUDED:
                self.assertEqual(
                    found_in, [],
                    f"{scenario['name']} expected to be excluded but found in {found_in}"
                )
            else:
                self.assertEqual(
                    found_in, [scenario['expected']],
                    f"{scenario['name']} expected in {scenario['expected']} but found in {found_in}"
                )

    def test_no_scenario_appears_in_more_than_one_bucket(self):
        data = self._get_aging_response()

        for scenario in SCENARIOS:
            invoice = self.invoices_by_name[scenario['name']]
            found_in = self._find_bucket_containing(data, invoice.invoice_number)
            self.assertLessEqual(
                len(found_in), 1,
                f"{scenario['name']} appeared in multiple buckets: {found_in}"
            )

    def test_total_and_outstanding_are_strings_not_floats(self):
        data = self._get_aging_response()

        for bucket_key in ALL_BUCKET_KEYS:
            for row in data[bucket_key]:
                self.assertIsInstance(
                    row['total'], str,
                    f"total for {row['invoice_number']} is not a string: {row['total']!r}"
                )
                self.assertIsInstance(
                    row['outstanding'], str,
                    f"outstanding for {row['invoice_number']} is not a string: {row['outstanding']!r}"
                )

    def test_draft_invoice_excluded_regardless_of_due_date(self):
        draft_invoice = Invoice.objects.create(
            invoice_number="TEST-AGING-draft-overdue",
            customer=self.customer,
            status=Invoice.STATUS_DRAFT,
            seller_name='Test Seller',
            seller_gstin='00TEST0000T1Z5',
            seller_state='27',
            seller_address='Test Seller Address',
            issue_date=self.today,
            due_date=self.today - timedelta(days=45),
            subtotal=Decimal('1000.00'),
            tax_total=Decimal('0.00'),
            total=Decimal('1000.00'),
        )

        data = self._get_aging_response()
        found_in = self._find_bucket_containing(data, draft_invoice.invoice_number)
        self.assertEqual(found_in, [], f"draft invoice unexpectedly appeared in {found_in}")
