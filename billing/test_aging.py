from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APITestCase

from .aging_scenarios import SCENARIOS, EXCLUDED, due_date_for, payment_amount_for
from .models import Company, Customer, Invoice, Payment, Product
from .serializers import InvoiceSerializer

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


class SeedAgingCleanTests(APITestCase):
    def setUp(self):
        Company.objects.create(
            name="Clean Test Seller",
            gstin="27AAAPL1234C1Z5",
            state="27",
            registered_address="Clean Test Address",
        )
        self.customer = Customer.objects.create(
            name="Clean Test Customer",
            email="clean@example.com",
            phone="9999999997",
            billing_address="789 Test Street",
        )
        self.product = Product.objects.create(
            name="Clean Product",
            unit_price=Decimal("10.00"),
            default_tax_rate=Decimal("9.00"),
            hsn_sac_code="998316",
        )

    def seeded_pks(self):
        return set(
            Invoice.objects.filter(
                invoice_number__startswith="SEED-AGING-"
            ).values_list("pk", flat=True)
        )

    def test_clean_removes_prior_seed_rows_and_payment_then_reseeds(self):
        expected_payments = sum(
            1 for s in SCENARIOS if payment_amount_for(s) > 0
        )

        call_command("seed_aging_dev_data", stdout=StringIO())
        old_pks = self.seeded_pks()
        self.assertEqual(len(old_pks), len(SCENARIOS))
        self.assertEqual(
            Payment.objects.filter(invoice__pk__in=old_pks).count(),
            expected_payments,
        )

        serializer = InvoiceSerializer(
            data={
                "customer": self.customer.id,
                "issue_date": "2026-01-01",
                "due_date": "2026-01-31",
                "items": [
                    {"product": self.product.id, "quantity": "1.00", "discount": "0"}
                ],
            }
        )
        serializer.is_valid(raise_exception=True)
        real_invoice = serializer.save()
        real_payment = Payment.objects.create(
            invoice=real_invoice,
            amount=Decimal("1.00"),
            payment_date=date.today(),
            method=Payment.METHOD_CASH,
        )

        call_command("seed_aging_dev_data", "--clean", stdout=StringIO())

        new_pks = self.seeded_pks()
        self.assertEqual(len(new_pks), len(SCENARIOS))
        self.assertTrue(old_pks.isdisjoint(new_pks))
        self.assertEqual(
            Payment.objects.filter(invoice__pk__in=new_pks).count(),
            expected_payments,
        )
        self.assertTrue(Invoice.objects.filter(pk=real_invoice.pk).exists())
        self.assertTrue(Payment.objects.filter(pk=real_payment.pk).exists())
