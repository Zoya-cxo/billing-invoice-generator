from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models
from django.core.exceptions import ImproperlyConfigured


GST_STATE_CHOICES = [
    ('35', 'Andaman and Nicobar Islands'),
    ('37', 'Andhra Pradesh'),
    ('12', 'Arunachal Pradesh'),
    ('18', 'Assam'),
    ('10', 'Bihar'),
    ('04', 'Chandigarh'),
    ('22', 'Chhattisgarh'),
    ('26', 'Dadra and Nagar Haveli and Daman and Diu'),
    ('07', 'Delhi'),
    ('30', 'Goa'),
    ('24', 'Gujarat'),
    ('06', 'Haryana'),
    ('02', 'Himachal Pradesh'),
    ('01', 'Jammu and Kashmir'),
    ('20', 'Jharkhand'),
    ('29', 'Karnataka'),
    ('32', 'Kerala'),
    ('38', 'Ladakh'),
    ('31', 'Lakshadweep'),
    ('23', 'Madhya Pradesh'),
    ('27', 'Maharashtra'),
    ('14', 'Manipur'),
    ('17', 'Meghalaya'),
    ('15', 'Mizoram'),
    ('13', 'Nagaland'),
    ('21', 'Odisha'),
    ('97', 'Other Territory'),
    ('34', 'Puducherry'),
    ('03', 'Punjab'),
    ('08', 'Rajasthan'),
    ('11', 'Sikkim'),
    ('33', 'Tamil Nadu'),
    ('36', 'Telangana'),
    ('16', 'Tripura'),
    ('09', 'Uttar Pradesh'),
    ('05', 'Uttarakhand'),
    ('19', 'West Bengal'),
]


class Customer(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    gstin = models.CharField(max_length=15, null=True, blank=True)
    state = models.CharField(max_length=2, choices=GST_STATE_CHOICES)
    billing_address = models.TextField()

    def __str__(self):
        return self.name


class Company(models.Model):
    """Singleton seller/company profile. Single-admin app, no multi-tenant,
    so there is intentionally no FK from Invoice to Company - Invoice snapshots
    the relevant fields at creation time instead (see seller_* fields on Invoice).
    This mirrors the InvoiceItem/Product snapshot pattern: editing Company after
    an invoice exists must never change that invoice's already-filed GST details.
    """
    name = models.CharField(max_length=255)
    gstin = models.CharField(max_length=15)
    state = models.CharField(max_length=2, choices=GST_STATE_CHOICES)
    registered_address = models.TextField()

    class Meta:
        verbose_name_plural = 'Companies'

    _SAVE_ERROR = 'A Company row already exists — only one is allowed. Edit the existing row instead of creating a new one.'
    _GET_ZERO_ERROR = 'No Company row exists — seed one via Django admin before creating invoices.'
    _GET_MULTI_ERROR = (
        'Multiple Company rows exist. This indicates direct database manipulation '
        '(bulk_create, raw SQL, fixtures, or manual edits) — the save() guard blocks '
        'this through normal app use. Resolve by deleting the extra row(s) before '
        'creating invoices.'
    )

    def save(self, *args, **kwargs):
        if self.pk is None and Company.objects.exists():
            raise ValueError(self._SAVE_ERROR)
        super().save(*args, **kwargs)

    @classmethod
    def get_singleton(cls):
        count = cls.objects.count()
        if count == 0:
            raise ImproperlyConfigured(cls._GET_ZERO_ERROR)
        if count > 1:
            raise ImproperlyConfigured(cls._GET_MULTI_ERROR)
        return cls.objects.get()

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    default_tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
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
    # NOTE: customer is a live FK, not snapshotted, unlike seller_* below and unlike
    # InvoiceItem's snapshot of Product. If Customer.billing_address (or other fields)
    # is edited after this invoice exists, the invoice will display today's customer
    # data, not what was true at billing time. Same bug shape as the Company/seller
    # snapshot problem this file solves for - just not yet fixed on the customer side.
    # Deliberately deferred (out of scope for this step), but flagging now because by
    # the time PDF export is built, fixing this means a migration + backfilling old
    # invoices, not just adding a field. Revisit before/during PDF export work.
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='invoices')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    seller_name = models.CharField(max_length=255)
    seller_gstin = models.CharField(max_length=15)
    seller_state = models.CharField(max_length=2, choices=GST_STATE_CHOICES)
    seller_address = models.TextField()
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
        if self.invoice.status != Invoice.STATUS_DRAFT:
            raise ValueError('Cannot create or modify invoice items once invoice has left draft status')
        self.line_total = (self.quantity * self.unit_price) - self.discount
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
    METHOD_CASH = 'cash'
    METHOD_UPI = 'upi'
    METHOD_BANK_TRANSFER = 'bank_transfer'
    METHOD_CHEQUE = 'cheque'

    METHOD_CHOICES = [
        (METHOD_CASH, 'Cash'),
        (METHOD_UPI, 'UPI'),
        (METHOD_BANK_TRANSFER, 'Bank Transfer'),
        (METHOD_CHEQUE, 'Cheque'),
    ]

    method = models.CharField(max_length=50, choices=METHOD_CHOICES)
    idempotency_key = models.UUIDField(unique=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError('Payment records are immutable and cannot be edited')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Payment records are immutable and cannot be deleted')

    def __str__(self):
        return f'{self.amount} for {self.invoice.invoice_number}'