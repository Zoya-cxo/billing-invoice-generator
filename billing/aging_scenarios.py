from datetime import timedelta
from decimal import Decimal

BUCKET_NOT_DUE = 'not_due'
BUCKET_0_30 = 'days_0_30'
BUCKET_31_60 = 'days_31_60'
BUCKET_61_90 = 'days_61_90'
BUCKET_90_PLUS = 'days_90_plus'
EXCLUDED = 'excluded'

SCENARIOS = [
    {
        'name': 'due_today_not_due',
        'status': 'sent',
        'due_offset_days': 0,
        'total': Decimal('1000.00'),
        'payment_fraction': Decimal('0'),
        'expected': BUCKET_NOT_DUE,
    },
    {
        'name': 'overdue_1_day',
        'status': 'sent',
        'due_offset_days': -1,
        'total': Decimal('1000.00'),
        'payment_fraction': Decimal('0'),
        'expected': BUCKET_0_30,
    },
    {
        'name': 'overdue_30_days',
        'status': 'sent',
        'due_offset_days': -30,
        'total': Decimal('1000.00'),
        'payment_fraction': Decimal('0'),
        'expected': BUCKET_0_30,
    },
    {
        'name': 'overdue_31_days',
        'status': 'sent',
        'due_offset_days': -31,
        'total': Decimal('1000.00'),
        'payment_fraction': Decimal('0'),
        'expected': BUCKET_31_60,
    },
    {
        'name': 'overdue_60_days',
        'status': 'sent',
        'due_offset_days': -60,
        'total': Decimal('1000.00'),
        'payment_fraction': Decimal('0'),
        'expected': BUCKET_31_60,
    },
    {
        'name': 'overdue_61_days',
        'status': 'sent',
        'due_offset_days': -61,
        'total': Decimal('1000.00'),
        'payment_fraction': Decimal('0'),
        'expected': BUCKET_61_90,
    },
    {
        'name': 'overdue_90_days',
        'status': 'sent',
        'due_offset_days': -90,
        'total': Decimal('1000.00'),
        'payment_fraction': Decimal('0'),
        'expected': BUCKET_61_90,
    },
    {
        'name': 'overdue_91_days',
        'status': 'overdue',
        'due_offset_days': -91,
        'total': Decimal('1000.00'),
        'payment_fraction': Decimal('0'),
        'expected': BUCKET_90_PLUS,
    },
    {
        'name': 'fully_paid_but_sent',
        'status': 'sent',
        'due_offset_days': -15,
        'total': Decimal('1000.00'),
        'payment_fraction': Decimal('1'),
        'expected': EXCLUDED,
    },
    {
        'name': 'cancelled_overdue',
        'status': 'cancelled',
        'due_offset_days': -45,
        'total': Decimal('1000.00'),
        'payment_fraction': Decimal('0'),
        'expected': EXCLUDED,
    },
]


def due_date_for(scenario, today):
    return today + timedelta(days=scenario['due_offset_days'])


def payment_amount_for(scenario):
    return (scenario['total'] * scenario['payment_fraction']).quantize(Decimal('0.01'))
