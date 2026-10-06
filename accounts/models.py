from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
import secrets
import string


class CustomUser(AbstractUser):
    """
    Extended User model with role-based access.
    Roles: super_admin, professional, customer, employee
    """
    ROLE_CHOICES = (
        ('super_admin', 'Super Admin'),
        ('professional', 'Επαγγελματίας'),
        ('customer', 'Πελάτης'),
        ('employee', 'Υπάλληλος'),
    )

    phone_validator = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Εισάγετε έγκυρο τηλέφωνο (π.χ. 6912345678)."
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    phone = models.CharField(
        max_length=15,
        validators=[phone_validator],
        verbose_name='Τηλέφωνο',
        blank=True,
    )
    is_approved = models.BooleanField(
        default=False,
        help_text='Για επαγγελματίες: εγκρίνεται από Super Admin.',
    )
    is_email_verified = models.BooleanField(
        default=False,
        verbose_name='Email Verified',
        help_text='Email verification status'
    )
    email_otp = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        verbose_name='Email OTP'
    )
    email_otp_expires_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='OTP Expiration Time'
    )
    is_phone_verified = models.BooleanField(
        default=False,
        verbose_name='Phone Verified',
        help_text='Phone verification status (for professionals with mobile numbers)',
    )
    phone_otp = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        verbose_name='Phone OTP'
    )
    phone_otp_expires_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Phone OTP Expiration Time'
    )
    is_deactivated = models.BooleanField(
        default=False,
        verbose_name='Account Deactivated',
        help_text='For professionals: account is deactivated but not deleted'
    )
    has_seen_welcome_flow = models.BooleanField(
        default=False,
        verbose_name='Seen Welcome Flow',
        help_text='Whether the user has completed or skipped the first-time welcome flow.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Χρήστης'
        verbose_name_plural = 'Χρήστες'

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.get_role_display()})'

    def generate_otp(self):
        """Generate a 6-digit OTP valid for 10 minutes."""
        otp = ''.join(secrets.choice(string.digits) for _ in range(6))
        self.email_otp = otp
        self.email_otp_expires_at = timezone.now() + timedelta(minutes=10)
        self.save(update_fields=['email_otp', 'email_otp_expires_at'])
        return otp

    def generate_phone_otp(self):
        """Generate a 6-digit phone OTP valid for 10 minutes."""
        otp = ''.join(secrets.choice(string.digits) for _ in range(6))
        self.phone_otp = otp
        self.phone_otp_expires_at = timezone.now() + timedelta(minutes=10)
        self.save(update_fields=['phone_otp', 'phone_otp_expires_at'])
        return otp

    def verify_otp(self, otp):
        """Verify the OTP and check if it's not expired."""
        if not self.email_otp:
            return False
        if self.email_otp != otp:
            return False
        if timezone.now() > self.email_otp_expires_at:
            return False
        return True

    def mark_email_verified(self):
        """Mark email as verified and clear OTP."""
        self.is_email_verified = True
        self.email_otp = None
        self.email_otp_expires_at = None
        self.save(update_fields=['is_email_verified', 'email_otp', 'email_otp_expires_at'])

    def verify_phone_otp(self, otp):
        """Verify phone OTP and check if it's not expired."""
        if not self.phone_otp:
            return False
        if self.phone_otp != otp:
            return False
        if timezone.now() > self.phone_otp_expires_at:
            return False
        return True

    def mark_phone_verified(self):
        """Mark phone as verified and clear phone OTP."""
        self.is_phone_verified = True
        self.phone_otp = None
        self.phone_otp_expires_at = None
        self.save(update_fields=['is_phone_verified', 'phone_otp', 'phone_otp_expires_at'])

    @property
    def is_super_admin(self):
        return self.role == 'super_admin'

    @property
    def is_professional(self):
        return self.role == 'professional'

    @property
    def is_customer(self):
        return self.role == 'customer'

    @property
    def is_employee(self):
        return self.role == 'employee'

    @property
    def can_have_multiple_emails(self):
        """Business and super admin accounts can have multiple emails"""
        return self.role in ['super_admin', 'professional']

    def get_primary_email_object(self):
        """Get the primary email object"""
        return self.user_emails.filter(is_primary=True).first()

    def get_all_emails(self):
        """Get all email addresses as a list"""
        emails = [email.email_address for email in self.user_emails.all()]
        # Include the main email field if not already in additional emails
        if self.email and self.email not in emails:
            emails.insert(0, self.email)
        return emails

    def add_email(self, email_address, is_primary=False):
        """Add a new email address"""
        if not self.can_have_multiple_emails:
            raise ValidationError("This user type cannot have multiple emails")

        # If setting as primary, unset other primary emails
        if is_primary:
            self.user_emails.update(is_primary=False)
            # Also update the main email field
            self.email = email_address
            self.save()

        return UserEmail.objects.create(
            user=self,
            email_address=email_address,
            is_primary=is_primary
        )


class UserEmail(models.Model):
    """
    Additional email addresses for users.
    Only super_admin and professional users can have multiple emails.
    """
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='user_emails',
        verbose_name='Χρήστης'
    )
    email_address = models.EmailField(
        verbose_name='Email Address'
    )
    is_primary = models.BooleanField(
        default=False,
        verbose_name='Primary Email',
        help_text='Only one email can be primary per user'
    )
    is_verified = models.BooleanField(
        default=False,
        verbose_name='Verified'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'email_address']
        verbose_name = 'User Email'
        verbose_name_plural = 'User Emails'

    def __str__(self):
        primary_text = " (Primary)" if self.is_primary else ""
        return f'{self.user.username} - {self.email_address}{primary_text}'

    def save(self, *args, **kwargs):
        # Validate user can have multiple emails
        if not self.user.can_have_multiple_emails:
            raise ValidationError(f"User role '{self.user.role}' cannot have multiple emails")

        # If this is being set as primary, unset other primary emails
        if self.is_primary:
            UserEmail.objects.filter(user=self.user, is_primary=True).update(is_primary=False)
            # Update the main email field
            self.user.email = self.email_address
            self.user.save()

        super().save(*args, **kwargs)
