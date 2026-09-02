import re

from rest_framework import serializers
from django.db import IntegrityError
from .models import Customer, Product, Invoice, InvoiceItem, Payment

GSTIN_REGEX = re.compile(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$')


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name', 'email', 'phone', 'gstin', 'billing_address']

    def validate_gstin(self, value):
        if value in (None, ''):
            return value
        if not GSTIN_REGEX.match(value):
            raise serializers.ValidationError(
                'GSTIN must be 15 characters in the format: 2-digit state code, '
                '10-character PAN, 1-digit entity number, "Z", 1 checksum character.'
            )
        # TODO: This only checks structural format, not the actual checksum digit.
        # Full GSTIN checksum validation (mod-36 algorithm against the PAN) is deferred
        # to the polish pass at the end of the project.
        return value


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'unit_price', 'default_tax_rate', 'hsn_sac_code']


class InvoiceItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = InvoiceItem
        fields = [
            "id", "product", "product_name", "quantity",
            "unit_price", "tax_rate", "discount", "hsn_sac_code", "line_total",
        ]
        read_only_fields = ["unit_price", "tax_rate", "hsn_sac_code", "line_total"]


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "invoice_number", "customer", "status", "issue_date", "due_date",
            "subtotal", "tax_total", "total", "irn", "qr_code", "items",
        ]
        read_only_fields = ["subtotal", "tax_total", "total", "irn", "qr_code"]

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("An invoice must have at least one item.")
        return value

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        invoice = Invoice.objects.create(**validated_data)
        self._create_items(invoice, items_data)
        self._recalculate_totals(invoice)
        return invoice

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        new_status = validated_data.pop("status", None)

        if instance.status != Invoice.STATUS_DRAFT and items_data is not None:
            raise serializers.ValidationError(
                "Cannot modify items on an invoice that is not in draft status."
            )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if new_status is not None and new_status != instance.status:
            try:
                instance.transition_to(new_status)
            except ValueError as e:
                raise serializers.ValidationError(str(e))

        if items_data is not None:
            instance.items.all().delete()
            self._create_items(instance, items_data)
            self._recalculate_totals(instance)

        return instance

    def _create_items(self, invoice, items_data):
        for item_data in items_data:
            product = item_data["product"]
            InvoiceItem.objects.create(
                invoice=invoice,
                product=product,
                quantity=item_data["quantity"],
                unit_price=product.unit_price,
                tax_rate=product.default_tax_rate,
                hsn_sac_code=product.hsn_sac_code,
                discount=item_data.get("discount", 0),
            )

    def _recalculate_totals(self, invoice):
        items = invoice.items.all()
        subtotal = sum(item.line_total for item in items)
        tax_total = sum(
            (item.line_total * item.tax_rate / 100) for item in items
        )
        invoice.subtotal = subtotal
        invoice.tax_total = tax_total
        invoice.total = subtotal + tax_total
        invoice.save(update_fields=["subtotal", "tax_total", "total"])


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "invoice", "amount", "payment_date", "method", "idempotency_key"]
        extra_kwargs = {
            "idempotency_key": {"required": True},
        }

    def validate(self, data):
        invoice = data.get("invoice")
        amount = data.get("amount")
        idempotency_key = data.get("idempotency_key")

        if invoice and invoice.status not in (Invoice.STATUS_SENT, Invoice.STATUS_OVERDUE):
            raise serializers.ValidationError(
                "Payments can only be recorded against invoices in sent or overdue status."
            )

        if amount is not None and amount <= 0:
            raise serializers.ValidationError("Payment amount must be greater than zero.")

        if invoice and amount is not None:
            already_paid = sum(p.amount for p in invoice.payments.all())
            outstanding = invoice.total - already_paid
            if amount > outstanding:
                raise serializers.ValidationError(
                    f"Payment of {amount} exceeds outstanding balance of {outstanding}."
                )

        if idempotency_key and Payment.objects.filter(idempotency_key=idempotency_key).exists():
            raise serializers.ValidationError(
                "A payment with this idempotency key has already been recorded."
            )

        return data

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                "A payment with this idempotency key has already been recorded."
            )
