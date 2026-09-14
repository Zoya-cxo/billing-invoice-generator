from django.contrib import admin
from .models import Customer, Product, Invoice, InvoiceItem, Payment, Company


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'gstin')
    search_fields = ('name', 'email', 'gstin')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit_price', 'default_tax_rate', 'hsn_sac_code')
    search_fields = ('name', 'hsn_sac_code')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'customer', 'status', 'issue_date', 'due_date', 'total')
    list_filter = ('status',)
    search_fields = ('invoice_number', 'customer__name')
    inlines = [InvoiceItemInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'amount', 'payment_date', 'method')
    search_fields = ('invoice__invoice_number',)

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'gstin', 'state')
