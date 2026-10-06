"""
Management command: Send review invite SMS for completed bookings.
Run via cron or Celery beat: python manage.py send_review_invites
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from bookings.models import Booking
from notifications.utils import send_review_invite_sms


class Command(BaseCommand):
    help = 'Send review invite SMS for bookings completed in the last 24 hours.'

    def handle(self, *args, **options):
        now = timezone.now()
        yesterday = now - timedelta(hours=24)

        bookings = Booking.objects.filter(
            status='completed',
            review_invite_sent=False,
            updated_at__gte=yesterday,
        ).select_related('customer', 'business')

        sent = 0
        for booking in bookings:
            result = send_review_invite_sms(booking)
            if result:
                sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} review invite(s).'))
