from datetime import date
from decimal import Decimal
from django.db.models import ProtectedError, Sum, DecimalField
from django.db.models.functions import Coalesce
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
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


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all().order_by('-issue_date')
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def aging(self, request):
        today = date.today()
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

        buckets = {
            'not_due': [],
            'days_0_30': [],
            'days_31_60': [],
            'days_61_90': [],
            'days_90_plus': [],
        }

        for inv in invoices:
            outstanding = inv.total - inv.paid
            if outstanding <= 0:
                continue
            days_overdue = (today - inv.due_date).days
            row = {
                'id': inv.id,
                'invoice_number': inv.invoice_number,
                'customer': inv.customer.name,
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
