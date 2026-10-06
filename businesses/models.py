from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta
import uuid


class Business(models.Model):
    """Business profile owned by a Professional."""
    CATEGORY_CHOICES = (
        ('health', 'Υγεία & Ιατρική'),
        ('beauty', 'Ομορφιά & Κομμωτική'),
        ('fitness', 'Fitness & Γυμναστήριο'),
        ('education', 'Εκπαίδευση & Φροντιστήρια'),
        ('legal', 'Νομικές Υπηρεσίες'),
        ('accounting', 'Λογιστικές Υπηρεσίες'),
        ('auto', 'Αυτοκίνητο & Συνεργείο'),
        ('tech', 'Τεχνολογία & IT'),
        ('other', 'Άλλο'),
    )

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='business',
    )
    name = models.CharField(max_length=200, verbose_name='Επωνυμία')
    slug = models.SlugField(max_length=200, unique=True, verbose_name='URL Slug')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other', verbose_name='Κατηγορία')
    custom_category = models.CharField(max_length=120, blank=True, verbose_name='Προσαρμοσμένη Κατηγορία')
    custom_category_gr = models.CharField(max_length=120, blank=True, verbose_name='Προσαρμοσμένη Κατηγορία (Ελληνικά)')
    custom_category_en = models.CharField(max_length=120, blank=True, verbose_name='Προσαρμοσμένη Κατηγορία (Αγγλικά)')
    description = models.TextField(blank=True, verbose_name='Περιγραφή')
    address = models.CharField(max_length=300, blank=True, verbose_name='Διεύθυνση')
    phone = models.CharField(max_length=15, blank=True, verbose_name='Τηλέφωνο')
    email = models.EmailField(blank=True, verbose_name='Email')
    logo = models.ImageField(upload_to='business_logos/', blank=True, null=True)

    # Booking settings
    auto_confirm = models.BooleanField(
        default=True,
        verbose_name='Αυτόματη επιβεβαίωση',
        help_text='Αν είναι OFF, κάθε ραντεβού χρειάζεται χειροκίνητη έγκριση.',
    )
    allow_employee_selection = models.BooleanField(
        default=True,
        verbose_name='Επιλογή υπαλλήλου',
        help_text='Επιτρέπει στους πελάτες να επιλέξουν συγκεκριμένο υπάλληλο.',
    )
    hourly_capacity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name='Χωρητικότητα ανά ώρα',
        help_text='Πόσα ραντεβού μπορείτε να εξυπηρετήσετε ταυτόχρονα (χρήσιμο αν δεν έχετε καταχωρημένους υπαλλήλους).',
    )
    requires_deposit = models.BooleanField(
        default=False,
        verbose_name='Απαιτεί προκαταβολή',
    )
    deposit_percentage = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(10), MaxValueValidator(100)],
        verbose_name='Ποσοστό προκαταβολής (%)',
    )
    
    # Cancellation fee settings
    charge_cancellation_fee = models.BooleanField(
        default=False,
        verbose_name='Χρέωση ακύρωσης',
        help_text='Αν είναι ενεργό, κρατείται ποσοστό σε περίπτωση ακύρωσης από τον πελάτη.',
    )
    cancellation_fee_percentage = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Ποσοστό χρέωσης ακύρωσης (%)',
        help_text='Το ποσοστό που θα κρατηθεί σε περίπτωση ακύρωσης (π.χ. 30% = επιστροφή 70%).',
    )

    # Employee accounts
    allow_employee_accounts = models.BooleanField(
        default=False,
        verbose_name='Λογαριασμοί Υπαλλήλων',
        help_text='Επιτρέπει στους υπαλλήλους να δημιουργήσουν λογαριασμό και να διαχειρίζονται τη διαθεσιμότητά τους.',
    )
    allow_employee_booking_actions = models.BooleanField(
        default=True,
        verbose_name='Ενέργειες Ραντεβού από Υπαλλήλους',
        help_text='Επιτρέπει στους υπαλλήλους να επιβεβαιώνουν ή να απορρίπτουν τα ραντεβού που τους έχουν ανατεθεί.',
    )

    allow_superadmin_troubleshooting_access = models.BooleanField(
        default=False,
        verbose_name='Πρόσβαση Super Admin για Troubleshooting',
        help_text='Επιτρέπει προσωρινή πρόσβαση στον Super Admin στο panel της επιχείρησης για τεχνική υποστήριξη.',
    )

    sms_reminder_minutes_before = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(1440)],
        verbose_name='SMS υπενθύμιση πριν το ραντεβού (λεπτά)',
        help_text='Πόσα λεπτά πριν το ραντεβού θα σταλεί SMS υπενθύμιση στην επιχείρηση.',
    )

    booking_gap_enabled = models.BooleanField(
        default=False,
        verbose_name='Κενό μεταξύ ραντεβού',
        help_text='Αν είναι ενεργό, προστίθεται κενό χρόνος μεταξύ των ραντεβού.',
    )
    booking_gap_minutes = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(240)],
        verbose_name='Κενό μεταξύ ραντεβού (λεπτά)',
        help_text='Πόσα λεπτά να αφήνονται ανάμεσα σε δύο ραντεβού.',
    )

    # Stripe
    stripe_account_id = models.CharField(max_length=100, blank=True)

    # Default business hours (used when no employees are set up)
    default_start_time = models.TimeField(
        default='09:00',
        verbose_name='Ώρα έναρξης (προεπιλογή)',
        help_text='Προεπιλεγμένη ώρα έναρξης εργασίας',
    )
    default_end_time = models.TimeField(
        default='17:00',
        verbose_name='Ώρα λήξης (προεπιλογή)',
        help_text='Προεπιλεγμένη ώρα λήξης εργασίας',
    )

    # Widget palette customization
    widget_primary_color = models.CharField(
        max_length=7,
        default='#c9a227',
        validators=[RegexValidator(r'^#[0-9A-Fa-f]{6}$', 'Χρησιμοποιήστε χρώμα σε μορφή #RRGGBB.')],
        verbose_name='Widget primary χρώμα',
    )
    widget_secondary_color = models.CharField(
        max_length=7,
        default='#f0c04a',
        validators=[RegexValidator(r'^#[0-9A-Fa-f]{6}$', 'Χρησιμοποιήστε χρώμα σε μορφή #RRGGBB.')],
        verbose_name='Widget secondary χρώμα',
    )
    widget_dark_color = models.CharField(
        max_length=7,
        default='#8a6500',
        validators=[RegexValidator(r'^#[0-9A-Fa-f]{6}$', 'Χρησιμοποιήστε χρώμα σε μορφή #RRGGBB.')],
        verbose_name='Widget dark χρώμα',
    )
    widget_background_color = models.CharField(
        max_length=7,
        default='#f8fafc',
        validators=[RegexValidator(r'^#[0-9A-Fa-f]{6}$', 'Χρησιμοποιήστε χρώμα σε μορφή #RRGGBB.')],
        verbose_name='Widget background χρώμα',
    )
    widget_theme_profile = models.CharField(
        max_length=20,
        choices=(
            ('classic', 'Κλασικό χρυσό'),
            ('site_match', 'Προφίλ που ταιριάζει με το custom site'),
        ),
        default='classic',
        verbose_name='Προφίλ widget',
        help_text='Επιλέξτε την οπτική ταυτότητα του booking widget.',
    )

    custom_landing_html = models.FileField(
        upload_to='business_custom_pages/',
        blank=True,
        null=True,
        verbose_name='Προσαρμοσμένη HTML Σελίδα',
        help_text='Προαιρετικά ανεβάστε αρχείο .html για δημόσια σελίδα στο /<slug>/',
    )

    PUBLIC_SITE_MODE_CHOICES = (
        ('booking_page', 'Σελίδα κρατήσεων'),
        ('custom_html', 'Προσαρμοσμένη HTML σελίδα'),
        ('built_in_site', 'Προκατασκευασμένη δημόσια σελίδα'),
        ('external_website', 'Εξωτερικό website'),
    )

    public_site_mode = models.CharField(
        max_length=20,
        choices=PUBLIC_SITE_MODE_CHOICES,
        default='booking_page',
        verbose_name='Τρόπος δημόσιας σελίδας',
        help_text='Επιλέξτε τι θα ανοίγει όταν κάποιος επισκέπτεται το δημόσιο link της επιχείρησης.',
    )
    external_website_url = models.URLField(
        blank=True,
        verbose_name='Εξωτερικό website',
        help_text='Προαιρετικός σύνδεσμος προς το δικό σας website.',
    )

    # Built-in public site builder
    custom_site_enabled = models.BooleanField(
        default=False,
        verbose_name='Ενεργή έτοιμη δημόσια σελίδα',
        help_text='Εμφανίζει την προσαρμοσμένη δημόσια σελίδα με προκαθορισμένο layout.',
    )
    custom_site_title = models.CharField(max_length=200, blank=True, verbose_name='Τίτλος σελίδας')
    custom_site_subtitle = models.CharField(max_length=300, blank=True, verbose_name='Υπότιτλος σελίδας')
    custom_site_about_title = models.CharField(max_length=200, blank=True, verbose_name='Τίτλος ενότητας')
    custom_site_about_text = models.TextField(blank=True, verbose_name='Κείμενο ενότητας')
    custom_site_cta_text = models.CharField(max_length=100, blank=True, verbose_name='Κείμενο κουμπιού')
    custom_site_gallery_title = models.CharField(max_length=200, blank=True, verbose_name='Τίτλος gallery')
    custom_site_image_1 = models.ImageField(upload_to='business_site_images/', blank=True, null=True, verbose_name='Εικόνα 1')
    custom_site_image_2 = models.ImageField(upload_to='business_site_images/', blank=True, null=True, verbose_name='Εικόνα 2')
    custom_site_image_3 = models.ImageField(upload_to='business_site_images/', blank=True, null=True, verbose_name='Εικόνα 3')

    break_start_time = models.TimeField(
        blank=True,
        null=True,
        verbose_name='Έναρξη διαλείμματος',
        help_text='Προαιρετικό καθημερινό διάλειμμα κατά το οποίο δεν δέχονται ραντεβού.',
    )
    break_end_time = models.TimeField(
        blank=True,
        null=True,
        verbose_name='Λήξη διαλείμματος',
        help_text='Προαιρετικό καθημερινό διάλειμμα κατά το οποίο δεν δέχονται ραντεβού.',
    )

    # Review auto-reply settings
    auto_reply_enabled = models.BooleanField(
        default=False,
        verbose_name='Αυτόματη απάντηση σε κριτικές',
        help_text='Ενεργοποιήστε για αυτόματη απάντηση σε όλες τις κριτικές με το προεπιλεγμένο μήνυμα.',
    )
    auto_reply_template = models.TextField(
        default='Σας ευχαριστούμε πολύ για την αξιολόγηση και τα σχόλιά σας.\n\nΗ ομάδα μας εκτιμά τη στήριξή σας.',
        verbose_name='Πρόσχεδιο αυτόματης απάντησης',
        help_text='Το μήνυμα που θα αποστέλλεται αυτόματα σε κάθε κριτική.',
    )

    # Status
    is_active = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Επιχείρηση'
        verbose_name_plural = 'Επιχειρήσεις'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_booking_url(self):
        return f'/b/{self.slug}/'

    @property
    def category_label(self):
        """Return custom category label when category is 'other'."""
        if self.category == 'other':
            return self.custom_category_gr or self.custom_category_en or self.custom_category
        return self.get_category_display()

    def category_label_for_lang(self, lang='gr'):
        """Return category label for a specific UI language."""
        if self.category != 'other':
            return self.get_category_display()
        if lang == 'en':
            return self.custom_category_en or self.custom_category_gr or self.custom_category
        return self.custom_category_gr or self.custom_category_en or self.custom_category

    @property
    def average_rating(self):
        from reviews.models import Review
        avg = Review.objects.filter(business=self).aggregate(
            avg=models.Avg('rating')
        )['avg']
        return round(avg, 1) if avg else 0

    @property
    def review_count(self):
        from reviews.models import Review
        return Review.objects.filter(business=self).count()


class BusinessDayOff(models.Model):
    """Temporary business closure for a specific date (e.g. sick day, holiday)."""
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='days_off',
    )
    date = models.DateField(verbose_name='Ημερομηνία Κλεισίματος')
    reason = models.CharField(max_length=200, blank=True, verbose_name='Λόγος')

    class Meta:
        verbose_name = 'Κλείσιμο Επιχείρησης'
        verbose_name_plural = 'Κλεισίματα Επιχείρησης'
        unique_together = ('business', 'date')
        ordering = ['date']

    def __str__(self):
        return f'{self.business.name} - {self.date} ({self.reason or "Κλειστό"})'


class BusinessHours(models.Model):
    """Per-day working hours for a business (independent of employees)."""
    DAY_CHOICES = (
        (0, 'Δευτέρα'),
        (1, 'Τρίτη'),
        (2, 'Τετάρτη'),
        (3, 'Πέμπτη'),
        (4, 'Παρασκευή'),
        (5, 'Σάββατο'),
        (6, 'Κυριακή'),
    )

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='business_hours',
    )
    day_of_week = models.IntegerField(choices=DAY_CHOICES, verbose_name='Ημέρα')
    start_time = models.TimeField(default='09:00', verbose_name='Ώρα Έναρξης')
    end_time = models.TimeField(default='17:00', verbose_name='Ώρα Λήξης')
    is_closed = models.BooleanField(default=False, verbose_name='Κλειστό')

    class Meta:
        verbose_name = 'Ωράριο Επιχείρησης'
        verbose_name_plural = 'Ωράρια Επιχείρησης'
        unique_together = ('business', 'day_of_week')
        ordering = ['day_of_week']

    def __str__(self):
        if self.is_closed:
            return f'{self.business.name} - {self.get_day_of_week_display()} - Κλειστό'
        return f'{self.business.name} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}'


class Employee(models.Model):
    """Employee / staff member of a business."""
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='employees',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employee_profiles',
        help_text='Προαιρετικά: σύνδεση με sub-account.',
    )
    name = models.CharField(max_length=100, verbose_name='Ονοματεπώνυμο')
    title = models.CharField(max_length=100, blank=True, verbose_name='Ειδικότητα / Ρόλος')
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=15, blank=True)
    photo = models.ImageField(upload_to='employee_photos/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Υπάλληλος'
        verbose_name_plural = 'Υπάλληλοι'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['business', 'user'],
                condition=models.Q(user__isnull=False),
                name='unique_employee_user_per_business',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.business.name})'

    @property
    def has_pending_invitation(self):
        """Check if employee has valid unused invitation."""
        return self.invitations.filter(is_used=False).exists()


class Service(models.Model):
    """Service offered by a business."""
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='services',
    )
    name = models.CharField(max_length=200, verbose_name='Υπηρεσία')
    description = models.TextField(blank=True, verbose_name='Περιγραφή')
    duration_minutes = models.PositiveIntegerField(
        default=30,
        verbose_name='Διάρκεια (λεπτά)',
        validators=[MinValueValidator(5)],
    )
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        verbose_name='Τιμή (€)',
    )
    cancellation_deadline_hours = models.PositiveIntegerField(
        default=24,
        validators=[MinValueValidator(0), MaxValueValidator(720)],
        verbose_name='Προθεσμία ακύρωσης (ώρες πριν)',
        help_text='Πόσες ώρες πριν το ραντεβού επιτρέπεται ακύρωση/επαναπρογραμματισμός.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Υπηρεσία'
        verbose_name_plural = 'Υπηρεσίες'
        ordering = ['name']
        unique_together = ('business', 'name')

    def __str__(self):
        return f'{self.name} - {self.duration_minutes}λ - {self.price}€'


class WorkingHours(models.Model):
    """Weekly working hours per employee."""
    DAY_CHOICES = (
        (0, 'Δευτέρα'),
        (1, 'Τρίτη'),
        (2, 'Τετάρτη'),
        (3, 'Πέμπτη'),
        (4, 'Παρασκευή'),
        (5, 'Σάββατο'),
        (6, 'Κυριακή'),
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='working_hours',
    )
    day_of_week = models.IntegerField(choices=DAY_CHOICES, verbose_name='Ημέρα')
    start_time = models.TimeField(verbose_name='Ώρα Έναρξης')
    end_time = models.TimeField(verbose_name='Ώρα Λήξης')
    is_day_off = models.BooleanField(default=False, verbose_name='Ρεπό')

    class Meta:
        verbose_name = 'Ωράριο Εργασίας'
        verbose_name_plural = 'Ωράρια Εργασίας'
        unique_together = ('employee', 'day_of_week')
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        if self.is_day_off:
            return f'{self.employee.name} - {self.get_day_of_week_display()} - Ρεπό'
        return f'{self.employee.name} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}'


class SpecialDayOff(models.Model):
    """Special day-off / holiday request for an employee."""
    STATUS_CHOICES = (
        ('pending', 'Αναμονή'),
        ('approved', 'Εγκρίθηκε'),
        ('rejected', 'Απορρίφθηκε'),
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='days_off',
    )
    date = models.DateField(verbose_name='Ημερομηνία')
    reason = models.CharField(max_length=200, blank=True, verbose_name='Λόγος')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Κατάσταση'
    )
    request_notes = models.TextField(
        blank=True,
        verbose_name='Σημειώσεις Αιτήματος',
        help_text='Πρόσθετες πληροφορίες από τον υπάλληλο'
    )
    admin_response = models.TextField(
        blank=True,
        verbose_name='Απάντηση Διαχειριστή',
        help_text='Σημειώσεις από τον εργοδότη'
    )
    requested_at = models.DateTimeField(auto_now_add=True, verbose_name='Ημερομηνία Αιτήματος')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='Ημερομηνία Αξιολόγησης')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_requests',
        verbose_name='Αξιολογήθηκε από'
    )

    class Meta:
        verbose_name = 'Αίτημα Άδειας'
        verbose_name_plural = 'Αιτήματα Αδειών'
        unique_together = ('employee', 'date')
        ordering = ['-date', '-id']

    def __str__(self):
        return f'{self.employee.name} - {self.date} - {self.get_status_display()}'

    @property
    def is_approved(self):
        return self.status == 'approved'

    @property
    def is_pending(self):
        return self.status == 'pending'

    @property
    def is_rejected(self):
        return self.status == 'rejected'


class AbsenceRequestChat(models.Model):
    """Chat messages for absence requests between employee and business owner."""
    absence_request = models.ForeignKey(
        SpecialDayOff,
        on_delete=models.CASCADE,
        related_name='chat_messages',
        verbose_name='Αίτημα Άδειας'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Αποστολέας'
    )
    message = models.TextField(verbose_name='Μήνυμα')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Ημερομηνία')
    is_read = models.BooleanField(default=False, verbose_name='Αναγνώστηκε')

    class Meta:
        verbose_name = 'Μήνυμα Αιτήματος'
        verbose_name_plural = 'Μηνύματα Αιτημάτων'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender.get_full_name()} - {self.created_at.strftime("%d/%m %H:%M")}'

    @property
    def sender_name(self):
        if self.sender.employee_profiles.exists():
            return f'{self.sender.get_full_name()} (Υπάλληλος)'
        else:
            return f'{self.sender.get_full_name()} (Εργοδότης)'


class BusinessDeletionRequest(models.Model):
    """Request for business deletion by owner. Requires super_admin approval."""
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved - Deactivated'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled by Owner'),
    )

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='deletion_requests',
        verbose_name='Business'
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='business_deletion_requests',
        verbose_name='Owner'
    )
    reason = models.TextField(
        blank=True,
        verbose_name='Reason for Deletion',
        help_text='Optional reason provided by the owner'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Status'
    )
    requested_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Requested At'
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Reviewed At'
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_business_deletions',
        verbose_name='Reviewed By'
    )
    admin_notes = models.TextField(
        blank=True,
        verbose_name='Admin Notes'
    )

    class Meta:
        verbose_name = 'Business Deletion Request'
        verbose_name_plural = 'Business Deletion Requests'
        ordering = ['-requested_at']

    def __str__(self):
        return f'{self.business.name} - {self.get_status_display()}'


class EmployeeInvitation(models.Model):
    """Invitation for an employee to create an account."""
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='invitations',
    )
    email = models.EmailField(verbose_name='Email Πρόσκλησης')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Πρόσκληση Υπαλλήλου'
        verbose_name_plural = 'Προσκλήσεις Υπαλλήλων'
        ordering = ['-created_at']

    def __str__(self):
        return f'Πρόσκληση για {self.employee.name} ({self.email})'

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = uuid.uuid4().hex + uuid.uuid4().hex  # 64 chars
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        """Check if invitation is still valid (not used and not expired)."""
        return not self.is_used and timezone.now() < self.expires_at

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at


class NotificationContact(models.Model):
    """Additional notification contacts for businesses and super admins."""
    CONTACT_TYPE_CHOICES = (
        ('email', 'Email'),
        ('phone', 'Τηλέφωνο'),
    )

    # Either business OR user (for super admins)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='notification_contacts',
        null=True,
        blank=True,
        verbose_name='Επιχείρηση'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_contacts',
        null=True,
        blank=True,
        verbose_name='Χρήστης'
    )

    contact_type = models.CharField(
        max_length=10,
        choices=CONTACT_TYPE_CHOICES,
        verbose_name='Τύπος Επαφής'
    )
    value = models.CharField(
        max_length=100,
        verbose_name='Τιμή (Email ή Τηλέφωνο)'
    )
    label = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Ετικέτα',
        help_text='π.χ. "Ιδιοκτήτης", "Υπεύθυνος", κ.λπ.'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Ενεργό'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Επαφή Ειδοποιήσεων'
        verbose_name_plural = 'Επαφές Ειδοποιήσεων'
        ordering = ['contact_type', 'label', 'value']
        constraints = [
            models.CheckConstraint(
                check=models.Q(business__isnull=False) | models.Q(user__isnull=False),
                name='notification_contact_has_owner'
            ),
            models.CheckConstraint(
                check=~(models.Q(business__isnull=False) & models.Q(user__isnull=False)),
                name='notification_contact_single_owner'
            )
        ]

    def __str__(self):
        owner = self.business.name if self.business else self.user.get_full_name()
        label = f" ({self.label})" if self.label else ""
        return f'{owner} - {self.get_contact_type_display()}: {self.value}{label}'

    def clean(self):
        from django.core.exceptions import ValidationError
        from django.core.validators import validate_email

        # Ensure exactly one of business or user is set
        if not self.business and not self.user:
            raise ValidationError('Either business or user must be set.')
        if self.business and self.user:
            raise ValidationError('Cannot set both business and user.')

        # Validate email format
        if self.contact_type == 'email':
            try:
                validate_email(self.value)
            except ValidationError:
                raise ValidationError({'value': 'Enter a valid email address.'})

        # Basic phone validation
        if self.contact_type == 'phone':
            import re
            if not re.match(r'^[\d\s\+\-\(\)]+$', self.value):
                raise ValidationError({'value': 'Enter a valid phone number.'})


class BusinessCustomer(models.Model):
    """Customer directory entry scoped to a business."""

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='business_customers',
        verbose_name='Επιχείρηση',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='business_customer_profiles',
        verbose_name='Χρήστης',
    )
    identity_key = models.CharField(max_length=255, verbose_name='Κλειδί Ταυτότητας')
    display_name = models.CharField(max_length=150, verbose_name='Ονοματεπώνυμο')
    phone = models.CharField(max_length=20, blank=True, verbose_name='Τηλέφωνο')
    email = models.EmailField(blank=True, verbose_name='Email')
    notes = models.TextField(blank=True, verbose_name='Σημειώσεις / Προτιμήσεις')
    booking_count = models.PositiveIntegerField(default=0, verbose_name='Συνολικά Ραντεβού')
    last_booking_at = models.DateTimeField(null=True, blank=True, verbose_name='Τελευταίο Ραντεβού')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Πελάτης Επιχείρησης'
        verbose_name_plural = 'Πελάτες Επιχείρησης'
        ordering = ['display_name']
        constraints = [
            models.UniqueConstraint(fields=['business', 'identity_key'], name='unique_business_customer_identity'),
        ]

    def __str__(self):
        return f'{self.display_name} - {self.business.name}'
