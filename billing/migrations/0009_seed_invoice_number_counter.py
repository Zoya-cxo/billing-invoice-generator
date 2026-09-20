from django.db import migrations


def seed_counter(apps, schema_editor):
    InvoiceNumberCounter = apps.get_model('billing', 'InvoiceNumberCounter')
    InvoiceNumberCounter.objects.get_or_create(pk=1, defaults=dict(last_number=0))


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0008_invoice_number_counter'),
    ]

    operations = [
        migrations.RunPython(seed_counter, migrations.RunPython.noop),
    ]
