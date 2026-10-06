from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Review(models.Model):
    """
    Verified review — only customers who completed a booking can leave one.
    Supports both authenticated customers and guests.
    """
    business = models.ForeignKey(
        'businesses.Business',
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='review',
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
        null=True,
        blank=True,
    )
    # Guest info (for non-authenticated bookings)
    guest_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Όνομα Επισκέπτη',
    )
    guest_email = models.EmailField(
        blank=True,
        verbose_name='Email Επισκέπτη',
    )
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Βαθμολογία',
    )
    comment = models.TextField(blank=True, verbose_name='Σχόλιο')
    business_reply = models.TextField(blank=True, verbose_name='Απάντηση Επιχείρησης')
    replied_at = models.DateTimeField(null=True, blank=True, verbose_name='Ημερομηνία Απάντησης')
    is_verified = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Αξιολόγηση'
        verbose_name_plural = 'Αξιολογήσεις'
        ordering = ['-created_at']
        unique_together = ('booking', 'customer')

    def __str__(self):
        return f'Review by {self.customer.username} for {self.business.name} - {self.rating}★'
