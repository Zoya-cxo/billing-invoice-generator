from decimal import Decimal

from .models import Invoice
from .serializers import InvoiceSerializer
from .test_invoice_api import InvoiceApiFixture


class PaidStatusGuardTests(InvoiceApiFixture):
    def patch_status(self, invoice, new_status):
        return self.client.patch(
            f"/api/v1/invoices/{invoice.id}/",
            {"status": new_status},
            format="json",
        )

    def status_in_db(self, invoice):
        invoice.refresh_from_db()
        return invoice.status

    def test_paid_rejected_on_sent_invoice_with_full_balance(self):
        invoice = self.make_invoice()
        response = self.patch_status(invoice, "paid")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.status_in_db(invoice), Invoice.STATUS_SENT)

    def test_paid_rejected_on_overdue_invoice_with_balance(self):
        invoice = self.make_invoice()
        invoice.transition_to(Invoice.STATUS_OVERDUE)
        self.add_payment(invoice, "400.00")
        response = self.patch_status(invoice, "paid")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.status_in_db(invoice), Invoice.STATUS_OVERDUE)

    def test_paid_rejected_when_one_paisa_is_outstanding(self):
        invoice = self.make_invoice()
        self.add_payment(invoice, "999.99")
        self.assertEqual(invoice.amount_outstanding, Decimal("0.01"))
        response = self.patch_status(invoice, "paid")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.status_in_db(invoice), Invoice.STATUS_SENT)

    def test_paid_accepted_when_outstanding_is_exactly_zero(self):
        invoice = self.make_invoice()
        self.add_payment(invoice, "1000.00")
        self.assertEqual(invoice.amount_outstanding, Decimal("0.00"))
        response = self.patch_status(invoice, "paid")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.status_in_db(invoice), Invoice.STATUS_PAID)

    def test_paid_accepted_on_zero_total_invoice_with_no_payments(self):
        invoice = self.make_invoice(total="0.00")
        self.assertEqual(invoice.amount_outstanding, Decimal("0.00"))
        response = self.patch_status(invoice, "paid")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.status_in_db(invoice), Invoice.STATUS_PAID)

    def test_cancel_with_balance_is_not_affected_by_the_guard(self):
        invoice = self.make_invoice()
        response = self.patch_status(invoice, "cancelled")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.status_in_db(invoice), Invoice.STATUS_CANCELLED)

    def test_overdue_with_balance_is_not_affected_by_the_guard(self):
        invoice = self.make_invoice()
        response = self.patch_status(invoice, "overdue")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.status_in_db(invoice), Invoice.STATUS_OVERDUE)

    def test_draft_to_sent_with_balance_is_not_affected_by_the_guard(self):
        invoice = self.make_invoice(send=False)
        response = self.patch_status(invoice, "sent")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.status_in_db(invoice), Invoice.STATUS_SENT)

    def test_rejection_body_is_a_status_keyed_list_of_strings(self):
        invoice = self.make_invoice()
        response = self.patch_status(invoice, "paid")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(response.data.keys()), ["status"])
        self.assertIsInstance(response.data["status"], list)
        self.assertTrue(all(isinstance(m, str) for m in response.data["status"]))

    def test_draft_to_paid_keeps_the_transition_error_not_the_balance_error(self):
        invoice = self.make_invoice(send=False)
        response = self.patch_status(invoice, "paid")
        self.assertEqual(response.status_code, 400)
        self.assertIsInstance(response.data, list)
        self.assertIn(
            "Cannot transition invoice from draft to paid", str(response.data[0])
        )

    def test_items_and_paid_in_one_patch_roll_back_the_item_change(self):
        invoice = self.make_invoice(
            items=[(self.product_a, Decimal("1.00"))], send=False, total="10.05"
        )
        before_items = list(
            invoice.items.values_list("pk", "product_id", "quantity")
        )
        before_total = Invoice.objects.get(pk=invoice.pk).total
        response = self.client.patch(
            f"/api/v1/invoices/{invoice.id}/",
            {
                "items": [
                    {"product": self.product_b.id, "quantity": "2.00", "discount": "0"}
                ],
                "status": "paid",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        after_items = list(invoice.items.values_list("pk", "product_id", "quantity"))
        self.assertEqual(after_items, before_items)
        self.assertEqual(Invoice.objects.get(pk=invoice.pk).total, before_total)
        self.assertEqual(self.status_in_db(invoice), Invoice.STATUS_DRAFT)

    def test_guard_uses_payments_added_after_the_instance_was_loaded(self):
        invoice = self.make_invoice()
        stale = Invoice.objects.prefetch_related("payments").get(pk=invoice.pk)
        self.assertEqual(stale.amount_outstanding, Decimal("1000.00"))
        self.add_payment(invoice, "1000.00")
        self.assertEqual(stale.amount_outstanding, Decimal("1000.00"))
        serializer = InvoiceSerializer(
            instance=stale, data={"status": "paid"}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        self.assertEqual(self.status_in_db(invoice), Invoice.STATUS_PAID)
