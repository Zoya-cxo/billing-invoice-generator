from datetime import date
from unittest import mock

from .test_invoice_api import InvoiceApiFixture


class BusinessTodayPatchTargetTests(InvoiceApiFixture):
    def test_patching_dates_business_today_moves_the_aging_clock(self):
        invoice = self.make_invoice(
            issue_date=date(2030, 1, 1), due_date=date(2030, 1, 14)
        )
        with mock.patch("billing.dates.business_today", return_value=date(2030, 1, 15)):
            response = self.client.get("/api/v1/invoices/aging/")
        self.assertEqual(response.status_code, 200)
        in_bucket = [r["id"] for r in response.data["days_0_30"]]
        self.assertEqual(in_bucket, [invoice.id])
