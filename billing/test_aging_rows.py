from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .aging_scenarios import SCENARIOS, EXCLUDED, due_date_for, payment_amount_for
from .models import Customer, Invoice, Payment

FIXED_TODAY = date(2030, 6, 15)
BUCKETS = ["not_due", "days_0_30", "days_31_60", "days_61_90", "days_90_plus"]
CUSTOMER_NAME = "Characterisation Customer"

FUTURE_DUE = {
    "name": "due_in_10_days",
    "status": "sent",
    "due_offset_days": 10,
    "total": Decimal("1000.00"),
    "payment_fraction": Decimal("0"),
    "expected": "not_due",
}

PART_PAID = {
    "name": "part_paid_40_days",
    "status": "sent",
    "due_offset_days": -40,
    "total": Decimal("1000.00"),
    "payment_fraction": Decimal("0.3"),
    "expected": "days_31_60",
}


class AgingRowCharacterisationTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="characterisationadmin", password="testpass123"
        )
        self.client.force_authenticate(user=user)
        self.customer = Customer.objects.create(
            name=CUSTOMER_NAME,
            email="characterisation@example.com",
            phone="9999999991",
            state="27",
            billing_address="Characterisation Address",
        )
        self.invoices = {}
        for scenario in SCENARIOS + [PART_PAID, FUTURE_DUE]:
            total = scenario["total"]
            invoice = Invoice.objects.create(
                invoice_number=f"CHAR-{scenario['name']}",
                customer=self.customer,
                customer_name=self.customer.name,
                customer_state=self.customer.state,
                customer_billing_address=self.customer.billing_address,
                status=scenario["status"],
                seller_name="Characterisation Seller",
                seller_gstin="00TEST0000T1Z5",
                seller_state="27",
                seller_address="Characterisation Seller Address",
                issue_date=FIXED_TODAY,
                due_date=due_date_for(scenario, FIXED_TODAY),
                subtotal=total,
                tax_total=Decimal("0.00"),
                total=total,
            )
            self.invoices[scenario["name"]] = invoice
            paid = payment_amount_for(scenario)
            if paid > 0:
                Payment.objects.create(
                    invoice=invoice,
                    amount=paid,
                    payment_date=FIXED_TODAY,
                    method=Payment.METHOD_CASH,
                )

    def expected_buckets(self):
        expected = {key: [] for key in BUCKETS}
        for scenario in SCENARIOS + [PART_PAID, FUTURE_DUE]:
            if scenario["expected"] == EXCLUDED:
                continue
            invoice = self.invoices[scenario["name"]]
            expected[scenario["expected"]].append({
                "id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "customer": CUSTOMER_NAME,
                "due_date": due_date_for(scenario, FIXED_TODAY),
                "total": str(scenario["total"]),
                "outstanding": str(scenario["total"] - payment_amount_for(scenario)),
                "days_overdue": max(-scenario["due_offset_days"], 0),
            })
        for rows in expected.values():
            rows.sort(key=lambda r: r["invoice_number"])
        return expected

    def test_every_row_matches_exactly_on_a_fixed_clock(self):
        with mock.patch("billing.dates.business_today", return_value=FIXED_TODAY):
            response = self.client.get("/api/v1/invoices/aging/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data.keys()), set(BUCKETS))
        actual = {
            key: sorted(response.data[key], key=lambda r: r["invoice_number"])
            for key in BUCKETS
        }
        self.assertEqual(actual, self.expected_buckets())
