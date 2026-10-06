"""
Management command: Send business SMS reminders before appointments.
Run via cron or Celery beat: python manage.py send_reminders
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from bookings.models import Booking
from notifications.utils import send_reminder_sms


class Command(BaseCommand):
    help = 'Send SMS reminders to businesses before appointments based on business settings.'

    def handle(self, *args, **options):
        now = timezone.now()
        window_start = now - timedelta(minutes=2)
        window_end = now + timedelta(minutes=2)
        max_future_date = (now + timedelta(days=2)).date()

        bookings = Booking.objects.filter(
            status__in=['confirmed', 'pending'],
            reminder_sent=False,
            date__gte=now.date(),
            date__lte=max_future_date,
        ).select_related('customer', 'business', 'employee', 'service')

        sent = 0
        for booking in bookings:
            from datetime import datetime
            booking_dt = timezone.make_aware(
                datetime.combine(booking.date, booking.start_time)
            )
            reminder_minutes = getattr(booking.business, 'sms_reminder_minutes_before', 30) or 30
            reminder_dt = booking_dt - timedelta(minutes=reminder_minutes)

            if window_start <= reminder_dt <= window_end:
                result = send_reminder_sms(booking)
                if result and result.status == 'sent':
                    booking.reminder_sent = True
                    booking.save(update_fields=['reminder_sent'])
                    sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} reminder(s).'))
