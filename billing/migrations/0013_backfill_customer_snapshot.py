from django.db import migrations


def backfill_customer_snapshot(apps, schema_editor):
    Invoice = apps.get_model('billing', 'Invoice')
    for invoice in Invoice.objects.select_related('customer').all():
        invoice.customer_name = invoice.customer.name
        invoice.customer_gstin = invoice.customer.gstin
        invoice.customer_state = invoice.customer.state
        invoice.customer_billing_address = invoice.customer.billing_address
        invoice.save(update_fields=[
            'customer_name', 'customer_gstin', 'customer_state', 'customer_billing_address',
        ])


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0012_add_customer_snapshot_fields'),
    ]

    operations = [
        migrations.RunPython(backfill_customer_snapshot, migrations.RunPython.noop),
    ]
