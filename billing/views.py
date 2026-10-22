from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, Prefetch, ProtectedError, Sum
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from . import dates, receivables
from .models import Customer, Product, Invoice, Payment
from .serializers import (
    CustomerSerializer,
    ProductSerializer,
    InvoiceSerializer,
    PaymentSerializer,
)


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all().order_by('name', 'id')
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Cannot delete customer with existing invoices."},
                status=status.HTTP_409_CONFLICT,
            )


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('name', 'id')
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Cannot delete product with existing invoice items."},
                status=status.HTTP_409_CONFLICT,
            )


class InvoiceViewSet(mixins.CreateModelMixin,
                     mixins.ListModelMixin,
                     mixins.RetrieveModelMixin,
                     mixins.UpdateModelMixin,
                     viewsets.GenericViewSet):
    queryset = (
        Invoice.objects
        .order_by('-issue_date', '-id')
        .prefetch_related(
            'items__product',
            Prefetch('payments', queryset=Payment.objects.order_by('payment_date', 'id')),
        )
    )
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def aging(self, request):
        buckets = {
            'not_due': [],
            'days_0_30': [],
            'days_31_60': [],
            'days_61_90': [],
            'days_90_plus': [],
        }

        for inv, outstanding, days_overdue in receivables.open_receivables():
            row = {
                'id': inv.id,
                'invoice_number': inv.invoice_number,
                'customer': inv.customer_name,
                'due_date': inv.due_date,
                'total': str(inv.total),
                'outstanding': str(outstanding),
                'days_overdue': max(days_overdue, 0),
            }
            if days_overdue <= 0:
                buckets['not_due'].append(row)
            elif days_overdue <= 30:
                buckets['days_0_30'].append(row)
            elif days_overdue <= 60:
                buckets['days_31_60'].append(row)
            elif days_overdue <= 90:
                buckets['days_61_90'].append(row)
            else:
                buckets['days_90_plus'].append(row)

        return Response(buckets)


class PaymentViewSet(mixins.CreateModelMixin,
                      mixins.ListModelMixin,
                      mixins.RetrieveModelMixin,
                      viewsets.GenericViewSet):
    queryset = Payment.objects.all().order_by("-payment_date")
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = dates.business_today()
        total_paid = Payment.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        revenue_collected = total_paid.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        counts = dict(Invoice.objects.values_list('status').annotate(n=Count('id')))
        months = []
        for offset in range(5, -1, -1):
            year, month_index = divmod(today.year * 12 + today.month - 1 - offset, 12)
            months.append({'month': f'{year:04d}-{month_index + 1:02d}', 'revenue': '0.00'})
        window_start = f"{months[0]['month']}-01"
        next_year, next_index = divmod(today.year * 12 + today.month, 12)
        window_end = f'{next_year:04d}-{next_index + 1:02d}-01'
        monthly_totals = {}
        window_payments = Payment.objects.filter(
            payment_date__gte=window_start, payment_date__lt=window_end
        ).values_list('payment_date', 'amount')
        for payment_date, amount in window_payments:
            key = f'{payment_date.year:04d}-{payment_date.month:02d}'
            monthly_totals[key] = monthly_totals.get(key, Decimal('0')) + amount
        for entry in months:
            month_total = monthly_totals.get(entry['month'], Decimal('0'))
            entry['revenue'] = str(month_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        rows = receivables.open_receivables()
        outstanding = sum((row[1] for row in rows), Decimal('0'))
        overdue = sum((row[1] for row in rows if row[2] > 0), Decimal('0'))
        recent_invoices = [
            {
                'id': inv.id,
                'invoice_number': inv.invoice_number,
                'customer': inv.customer_name,
                'total': str(inv.total),
                'status': inv.status,
                'issue_date': inv.issue_date,
            }
            for inv in Invoice.objects.order_by('-issue_date', '-id')[:10]
        ]
        return Response({
            'revenue_collected': str(revenue_collected),
            'outstanding': str(outstanding.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'overdue': str(overdue.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'invoice_counts': {status: counts.get(status, 0) for status, _ in Invoice.STATUS_CHOICES},
            'monthly_revenue': months,
            'recent_invoices': recent_invoices,
        })
