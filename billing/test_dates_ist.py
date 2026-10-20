from datetime import date, datetime, timezone
from unittest import mock

from django.test import SimpleTestCase

from . import dates

PINNED_UTC = datetime(2026, 10, 18, 20, 41, tzinfo=timezone.utc)


class BusinessTodayIstTests(SimpleTestCase):
    def test_utc_evening_is_already_the_next_day_in_ist(self):
        with mock.patch("django.utils.timezone.now", return_value=PINNED_UTC):
            self.assertEqual(dates.business_today(), date(2026, 10, 19))
