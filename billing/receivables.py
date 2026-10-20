from decimal import Decimal

from django.db.models import DecimalField, Sum
from django.db.models.functions import Coalesce

from . import dates
from .models import Invoice


def open_receivables():
    today = dates.business_today()
    invoices = (
        Invoice.objects
        .exclude(status__in=[Invoice.STATUS_DRAFT, Invoice.STATUS_CANCELLED])
        .select_related('customer')
        .annotate(
            paid=Coalesce(
                Sum('payments__amount'),
                Decimal('0'),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
    )
    result = []
    for inv in invoices:
        outstanding = inv.total - inv.paid
        if outstanding <= 0:
            continue
        result.append((inv, outstanding, (today - inv.due_date).days))
    return result
