from django.utils import timezone


def business_today():
    return timezone.localdate()
