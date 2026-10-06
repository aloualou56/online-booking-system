from django.db import models
from django.conf import settings


class Booking(models.Model):
    """Appointment / booking record."""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('no_show', 'No-Show'),
    )

    PAYMENT_STATUS_CHOICES = (
        ('not_required', 'Not Required'),
        ('pending', 'Pending Payment'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    )

    business = models.ForeignKey(
        'businesses.Business',
        on_delete=models.CASCADE,
        related_name='bookings',
    )
    employee = models.ForeignKey(
        'businesses.Employee',
        on_delete=models.CASCADE,
        related_name='bookings',
    )
    service = models.ForeignKey(
        'businesses.Service',
        on_delete=models.CASCADE,
        related_name='bookings',
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings',
        null=True,
        blank=True,
        verbose_name='Πελάτης',
    )

    # Guest booking info (when customer is not registered)
    guest_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Όνομα Επισκέπτη',
    )
    guest_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Τηλέφωνο Επισκέπτη',
    )
    guest_email = models.EmailField(
        blank=True,
        verbose_name='Email Επισκέπτη',
    )
    guest_access_token = models.CharField(
        max_length=64,
        blank=True,
        unique=True,
        null=True,
        verbose_name='Κωδικός Πρόσβασης Επισκέπτη',
    )

    # Guest contact preferences
    CONTACT_PREFERENCE_CHOICES = (
        ('email', 'Email'),
        ('phone', 'Telephone'),
        ('both', 'Both'),
    )
    guest_contact_preference = models.CharField(
        max_length=10,
        choices=CONTACT_PREFERENCE_CHOICES,
        default='both',
        blank=True,
        verbose_name='Προτίμηση Επικοινωνίας',
    )
    customer_contact_preference = models.CharField(
        max_length=10,
        choices=CONTACT_PREFERENCE_CHOICES,
        default='both',
        blank=True,
        verbose_name='Προτίμηση Επικοινωνίας Πελάτη',
    )
    customer_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Τηλέφωνο Πελάτη (για SMS)',
    )

    date = models.DateField(verbose_name='Ημερομηνία')
    start_time = models.TimeField(verbose_name='Ώρα Έναρξης')
    end_time = models.TimeField(verbose_name='Ώρα Λήξης')

    # Price locked at booking time — unchanged even if service price changes later
    price_at_booking = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        verbose_name='Τιμή Κατά την Κράτηση',
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Κατάσταση',
    )
    payment_status = models.CharField(
        max_length=30,
        choices=PAYMENT_STATUS_CHOICES,
        default='not_required',
        verbose_name='Κατάσταση Πληρωμής',
    )

    # Deposit / payment info
    deposit_amount = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        verbose_name='Ποσό Προκαταβολής',
    )
    stripe_payment_intent_id = models.CharField(max_length=200, blank=True)

    notes = models.TextField(blank=True, verbose_name='Σημειώσεις')
    rejection_reason = models.TextField(blank=True, verbose_name='Λόγος Απόρριψης')
    reminder_sent = models.BooleanField(default=False)
    review_invite_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Ραντεβού'
        verbose_name_plural = 'Ραντεβού'
        ordering = ['-date', '-start_time']

    def __str__(self):
        customer_name = self.customer.get_full_name() if self.customer else self.guest_name
        return (
            f'#{self.id} - {self.business.name} | '
            f'{self.service.name} | {customer_name} | {self.date} {self.start_time}'
        )

    @property
    def is_cancellable(self):
        """Check if booking can still be cancelled."""
        from django.utils import timezone
        from datetime import datetime, timedelta
        if self.status in ('cancelled', 'completed', 'no_show'):
            return False
        booking_datetime = timezone.make_aware(
            datetime.combine(self.date, self.start_time)
        )
        deadline_hours = int(getattr(self.service, 'cancellation_deadline_hours', 24) or 0)
        cancellation_deadline = booking_datetime - timedelta(hours=max(0, deadline_hours))
        return timezone.now() <= cancellation_deadline

    @property
    def cancellation_deadline_at(self):
        """Return datetime until when cancellation/reschedule is allowed."""
        from django.utils import timezone
        from datetime import datetime, timedelta
        booking_datetime = timezone.make_aware(
            datetime.combine(self.date, self.start_time)
        )
        deadline_hours = int(getattr(self.service, 'cancellation_deadline_hours', 24) or 0)
        return booking_datetime - timedelta(hours=max(0, deadline_hours))

    @property
    def is_reschedulable(self):
        """Rescheduling follows the same deadline policy as cancellation."""
        return self.is_cancellable

    @property
    def hours_until(self):
        """Hours until the appointment."""
        from django.utils import timezone
        from datetime import datetime
        booking_datetime = timezone.make_aware(
            datetime.combine(self.date, self.start_time)
        )
        delta = booking_datetime - timezone.now()
        return delta.total_seconds() / 3600

    @property
    def cancellation_refund_percentage(self):
        """Calculate refund percentage based on cancellation policy."""
        # Check if business has custom cancellation fee enabled
        if self.business.charge_cancellation_fee:
            # Business charges a cancellation fee, so refund = 100% - fee%
            return 100 - self.business.cancellation_fee_percentage
        
        # Otherwise use time-based default policy
        hours = self.hours_until
        if hours > settings.CANCELLATION_FULL_REFUND_HOURS:
            return 100  # >48h → 100%
        elif hours > settings.CANCELLATION_HALF_REFUND_HOURS:
            return 50   # 24-48h → 50%
        else:
            return 0    # <24h → 0%

    @property
    def employee_display_name(self):
        """Customer-friendly employee label for auto-assigned placeholder rows."""
        if not self.employee_id:
            return ''
        normalized_name = (self.employee.name or '').strip().lower()
        normalized_title = (self.employee.title or '').strip().lower()
        auto_names = {'system', 'σύστημα', 'automatic selection'}
        auto_titles = {'automatic assignment', 'αυτόματη ανάθεση'}
        if normalized_name in auto_names or normalized_title in auto_titles:
            return 'Automatic selection'
        return self.employee.name


class BookingStatusLog(models.Model):
    """Audit log for booking status changes."""
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='status_logs',
    )
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Booking #{self.booking.id}: {self.old_status} → {self.new_status}'
