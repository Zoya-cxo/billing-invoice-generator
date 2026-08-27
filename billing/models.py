from django.db import models


class Customer(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    gstin = models.CharField(max_length=15, null=True, blank=True)
    billing_address = models.TextField()

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    default_tax_rate = models.DecimalField(max_digits=5, decimal_places=2)
    hsn_sac_code = models.CharField(max_length=20)

    def __str__(self):
        return self.name


class Invoice(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SENT = 'sent'
    STATUS_PAID = 'paid'
    STATUS_OVERDUE = 'overdue'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SENT, 'Sent'),
        (STATUS_PAID, 'Paid'),
        (STATUS_OVERDUE, 'Overdue'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    ALLOWED_TRANSITIONS = {
        STATUS_DRAFT: {STATUS_SENT, STATUS_CANCELLED},
        STATUS_SENT: {STATUS_PAID, STATUS_OVERDUE, STATUS_CANCELLED},
        STATUS_OVERDUE: {STATUS_PAID, STATUS_CANCELLED},
        STATUS_PAID: set(),
        STATUS_CANCELLED: set(),
    }

    invoice_number = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='invoices')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    issue_date = models.DateField()
    due_date = models.DateField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    irn = models.CharField(max_length=100, null=True, blank=True)
    qr_code = models.TextField(null=True, blank=True)

    def transition_to(self, new_status):
        allowed = self.ALLOWED_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(f'Cannot transition invoice from {self.status} to {new_status}')
        self.status = new_status
        self.save(update_fields=['status'])

    def __str__(self):
        return self.invoice_number


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='invoice_items')
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hsn_sac_code = models.CharField(max_length=20)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        if self.pk is not None and self.invoice.status != Invoice.STATUS_DRAFT:
            raise ValueError('Cannot modify invoice items once invoice has left draft status')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.invoice.status != Invoice.STATUS_DRAFT:
            raise ValueError('Cannot delete invoice items once invoice has left draft status')
        super().delete(*args, **kwargs)

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'


class Payment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField()
    method = models.CharField(max_length=50)

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError('Payment records are immutable and cannot be edited')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Payment records are immutable and cannot be deleted')

    def __str__(self):
        return f'{self.amount} for {self.invoice.invoice_number}'
