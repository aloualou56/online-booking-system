from django.db import models
from django.conf import settings


class Payment(models.Model):
    """Payment record linked to a booking (Stripe)."""
    STATUS_CHOICES = (
        ('pending', 'Αναμονή'),
        ('succeeded', 'Επιτυχής'),
        ('failed', 'Αποτυχία'),
        ('refunded', 'Επιστροφή'),
        ('partially_refunded', 'Μερική Επιστροφή'),
    )

    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='payments',
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Ποσό')
    currency = models.CharField(max_length=3, default='eur')
    stripe_payment_intent_id = models.CharField(max_length=200, blank=True)
    stripe_checkout_session_id = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    refund_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    refunded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Πληρωμή'
        verbose_name_plural = 'Πληρωμές'
        ordering = ['-created_at']

    def __str__(self):
        return f'Payment #{self.id} - {self.amount}€ ({self.status})'
