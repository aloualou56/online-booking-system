from django.db import models
from django.conf import settings


class SMSNotification(models.Model):
    """SMS notification log."""
    TYPE_CHOICES = (
        ('confirmation', 'Επιβεβαίωση ραντεβού'),
        ('reminder', 'Υπενθύμιση 24ωρο'),
        ('review_invite', 'Πρόσκληση αξιολόγησης'),
        ('cancellation', 'Ακύρωση ραντεβού'),
        ('approved', 'Εγκρίθηκε ραντεβού'),
        ('rejected', 'Απορρίφθηκε ραντεβού'),
        ('new_booking', 'Νέο ραντεβού (προς επαγγελματία)'),
        ('new_business', 'Νέα αίτηση επιχείρησης (προς Super Admin)'),
    )

    STATUS_CHOICES = (
        ('pending', 'Αναμονή'),
        ('sent', 'Εστάλη'),
        ('failed', 'Αποτυχία'),
    )

    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='sms_notifications',
        null=True,
        blank=True,
    )
    recipient_phone = models.CharField(max_length=15, verbose_name='Τηλέφωνο')
    recipient_name = models.CharField(max_length=100, blank=True)
    message = models.TextField(verbose_name='Μήνυμα')
    sms_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='Τύπος')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    twilio_sid = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'SMS Ειδοποίηση'
        verbose_name_plural = 'SMS Ειδοποιήσεις'
        ordering = ['-created_at']

    def __str__(self):
        return f'SMS → {self.recipient_phone} ({self.sms_type}) - {self.status}'


class News(models.Model):
    """Platform news announcements for professionals and customers."""
    STATUS_CHOICES = (
        ('draft', 'Σχέδιο'),
        ('published', 'Δημοσιευμένο'),
    )

    title_gr = models.CharField(max_length=200, verbose_name='Τίτλος (Ελληνικά)')
    title_en = models.CharField(max_length=200, verbose_name='Title (English)')
    
    description_gr = models.TextField(verbose_name='Περιγραφή (Ελληνικά)')
    description_en = models.TextField(verbose_name='Description (English)')
    
    content_gr = models.TextField(verbose_name='Περιεχόμενο (Ελληνικά)', blank=True)
    content_en = models.TextField(verbose_name='Content (English)', blank=True)
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name='Κατάσταση'
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='news_created',
        verbose_name='Δημιουργήθηκε από'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Δημιουργήθηκε')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Ενημερώθηκε')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='Δημοσιεύθηκε')

    class Meta:
        verbose_name = 'Ειδήσεις'
        verbose_name_plural = 'Ειδήσεις'
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['-published_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.title_gr} ({self.get_status_display()})'

    def get_title(self, language='gr'):
        return self.title_gr if language == 'gr' else self.title_en

    def get_description(self, language='gr'):
        return self.description_gr if language == 'gr' else self.description_en

    def get_content(self, language='gr'):
        return self.content_gr if language == 'gr' else self.content_en


class SystemSettings(models.Model):
    """Global platform switches controlled by Super Admin."""
    sms_enabled = models.BooleanField(default=True, verbose_name='SMS Enabled')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'System Setting'
        verbose_name_plural = 'System Settings'

    def __str__(self):
        return f'System Settings (SMS: {"ON" if self.sms_enabled else "OFF"})'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
