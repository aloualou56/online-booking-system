from django.db import models
from django.conf import settings


class BusinessReport(models.Model):
    CATEGORY_CHOICES = (
        ('missed_appointment', 'Δεν τήρησε το ραντεβού'),
        ('offensive_language', 'Προσβλητική γλώσσα'),
        ('no_show_business', 'Επιχείρηση δεν εμφανίστηκε'),
        ('poor_service', 'Κακή εξυπηρέτηση'),
        ('fraud', 'Απάτη / Παραπλάνηση'),
        ('other', 'Άλλο'),
    )

    STATUS_CHOICES = (
        ('new', 'Νέα'),
        ('under_review', 'Υπό εξέταση'),
        ('resolved', 'Επιλύθηκε'),
        ('dismissed', 'Απορρίφθηκε'),
    )

    business = models.ForeignKey(
        'businesses.Business',
        on_delete=models.CASCADE,
        related_name='reports',
        verbose_name='Επιχείρηση',
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submitted_reports',
        verbose_name='Αναφέρων',
    )
    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports',
        verbose_name='Σχετικό Ραντεβού',
    )
    category = models.CharField(
        max_length=40,
        choices=CATEGORY_CHOICES,
        verbose_name='Κατηγορία',
    )
    description = models.TextField(verbose_name='Περιγραφή')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new',
        verbose_name='Κατάσταση',
    )
    admin_notes = models.TextField(blank=True, verbose_name='Σημειώσεις Διαχειριστή')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Αναφορά'
        verbose_name_plural = 'Αναφορές'
        ordering = ['-created_at']

    def __str__(self):
        return f'Αναφορά #{self.id} — {self.business.name} ({self.get_category_display()})'
