from django.db.models import ProtectedError
from rest_framework import viewsets, mixins, status
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
    queryset = Customer.objects.all().order_by('name')
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
    queryset = Product.objects.all().order_by('name')
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


class PaymentViewSet(mixins.CreateModelMixin,
                      mixins.ListModelMixin,
                      mixins.RetrieveModelMixin,
                      viewsets.GenericViewSet):
    queryset = Payment.objects.all().order_by("-payment_date")
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
