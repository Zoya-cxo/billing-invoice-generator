from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from billing.aging_scenarios import SCENARIOS, due_date_for, payment_amount_for
from billing.models import Customer, Invoice, Payment

SEED_PREFIX = 'SEED-AGING-'


class Command(BaseCommand):
    help = 'Seeds dev-only invoices/payments covering aging report boundary scenarios.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Delete previously seeded aging rows before creating new ones.',
        )

    def handle(self, *args, **options):
        if options['clean']:
            deleted, _ = Invoice.objects.filter(
                invoice_number__startswith=SEED_PREFIX
            ).delete()
            self.stdout.write(f'Deleted {deleted} previously seeded row(s).')

        customer = Customer.objects.first()
        if customer is None:
            raise CommandError(
                'No Customer rows exist. Create at least one Customer before seeding.'
            )

        today = date.today()

        with transaction.atomic():
            for scenario in SCENARIOS:
                invoice_number = f"{SEED_PREFIX}{scenario['name']}"
                due_date = due_date_for(scenario, today)
                total = scenario['total']

                invoice = Invoice.objects.create(
                    invoice_number=invoice_number,
                    customer=customer,
                    status=scenario['status'],
                    seller_name='Seed Seller',
                    seller_gstin='00SEED0000S1Z5',
                    seller_state='27',
                    seller_address='Seed Address',
                    issue_date=today,
                    due_date=due_date,
                    subtotal=total,
                    tax_total=Decimal('0.00'),
                    total=total,
                )

                payment_amount = payment_amount_for(scenario)
                if payment_amount > 0:
                    Payment.objects.create(
                        invoice=invoice,
                        amount=payment_amount,
                        payment_date=today,
                        method=Payment.METHOD_CASH,
                    )

                self.stdout.write(
                    f'Seeded {invoice_number}: status={scenario["status"]} '
                    f'due_date={due_date} expected={scenario["expected"]}'
                )
