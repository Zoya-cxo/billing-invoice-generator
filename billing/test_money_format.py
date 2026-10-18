import re
from datetime import timedelta

from . import dates
from .models import Invoice
from .test_invoice_api import InvoiceApiFixture

TWO_DECIMALS = re.compile(r"^\d+\.\d{2}$")
DETAIL_MONEY_FIELDS = ["subtotal", "tax_total", "total", "paid", "outstanding"]


class InvoiceMoneyFormatTests(InvoiceApiFixture):
    def test_fully_paid_invoice_reports_zero_outstanding_as_0_00(self):
        invoice = self.make_invoice()
        self.add_payment(invoice, "1000.00")
        data = self.get_detail(invoice)
        self.assertEqual(data["paid"], "1000.00")
        self.assertEqual(data["outstanding"], "0.00")

    def test_zero_total_invoice_reports_0_00_for_paid_and_outstanding(self):
        invoice = self.make_invoice(total="0.00")
        data = self.get_detail(invoice)
        self.assertEqual(data["total"], "0.00")
        self.assertEqual(data["paid"], "0.00")
        self.assertEqual(data["outstanding"], "0.00")

    def test_part_paid_invoice_reports_two_decimal_strings(self):
        invoice = self.make_invoice()
        self.add_payment(invoice, "400.00")
        data = self.get_detail(invoice)
        self.assertEqual(data["paid"], "400.00")
        self.assertEqual(data["outstanding"], "600.00")

    def test_every_money_field_is_a_two_decimal_string_on_detail_and_list(self):
        paid_in_full = self.make_invoice()
        self.add_payment(paid_in_full, "1000.00")
        zero_total = self.make_invoice(total="0.00")
        part_paid = self.make_invoice(total="250.50")
        self.add_payment(part_paid, "0.50")
        for invoice in (paid_in_full, zero_total, part_paid):
            detail = self.get_detail(invoice)
            for field in DETAIL_MONEY_FIELDS:
                with self.subTest(view="detail", invoice=invoice.id, field=field):
                    self.assertIsInstance(detail[field], str)
                    self.assertRegex(detail[field], TWO_DECIMALS)
        for invoice_id, row in self.get_list_rows().items():
            for field in DETAIL_MONEY_FIELDS:
                with self.subTest(view="list", invoice=invoice_id, field=field):
                    self.assertIsInstance(row[field], str)
                    self.assertRegex(row[field], TWO_DECIMALS)

    def test_aging_rows_emit_two_decimal_strings(self):
        today = dates.business_today()
        self.make_invoice(total="1000.00", due_date=today - timedelta(days=5))
        part = self.make_invoice(total="250.50", due_date=today - timedelta(days=40))
        self.add_payment(part, "0.50")
        response = self.client.get("/api/v1/invoices/aging/")
        self.assertEqual(response.status_code, 200)
        rows = [row for bucket in response.data.values() for row in bucket]
        self.assertEqual(len(rows), 2)
        for row in rows:
            for field in ("total", "outstanding"):
                with self.subTest(invoice=row["invoice_number"], field=field):
                    self.assertRegex(row[field], TWO_DECIMALS)
