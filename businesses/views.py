from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Sum, Q
from django.urls import reverse
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings as django_settings
from datetime import datetime, timedelta
import csv
import re
from accounts.decorators import professional_required
from .models import Business, Employee, Service, WorkingHours, SpecialDayOff, BusinessHours, BusinessDayOff, EmployeeInvitation
from bookings.models import Booking, BookingStatusLog
from notifications.models import News
from notifications.utils import send_booking_approval_notifications, send_employee_new_booking_email
from .customer_utils import business_customer_queryset, upsert_business_customer_from_booking

def _ensure_business_hours(business):
    """Create default BusinessHours rows (Mon-Fri 09-17, Sat-Sun closed) if none exist."""
    if not BusinessHours.objects.filter(business=business).exists():
        for day in range(5):  # Mon-Fri
            BusinessHours.objects.create(
                business=business, day_of_week=day,
                start_time='09:00', end_time='17:00', is_closed=False,
            )
        for day in range(5, 7):  # Sat-Sun
            BusinessHours.objects.create(
                business=business, day_of_week=day,
                start_time='09:00', end_time='17:00', is_closed=True,
            )


def _get_accessible_business(request):
    """Resolve business for owner or superadmin troubleshooting session."""
    if request.user.role == 'super_admin':
        business_id = request.session.get('superadmin_business_access_id')
        if business_id:
            business = Business.objects.filter(
                id=business_id,
                allow_superadmin_troubleshooting_access=True,
            ).first()
            if business:
                return business

            # Access was revoked or business not found: clear stale session state.
            request.session.pop('superadmin_business_access_id', None)
            request.session.pop('superadmin_business_access_name', None)

    return get_object_or_404(Business, owner=request.user)


@login_required
@professional_required
def dashboard(request):
    """Business owner dashboard."""
    # Clear customer mode when returning to business dashboard
    if 'customer_mode' in request.session:
        del request.session['customer_mode']

    business = _get_accessible_business(request)
    now = timezone.now()
    today = now.date()
    month_start = now.replace(day=1, hour=0, minute=0, second=0)

    today_bookings = Booking.objects.filter(
        business=business, date=today
    ).select_related('employee', 'service', 'customer').order_by('start_time')

    pending_bookings = Booking.objects.filter(
        business=business, status='pending'
    ).select_related('employee', 'service', 'customer').order_by('date', 'start_time')

    overdue_bookings = Booking.objects.filter(
        business=business,
        status__in=['pending', 'confirmed'],
    ).filter(
        Q(date__lt=today) | Q(date=today, end_time__lt=now.time())
    ).select_related('employee', 'service', 'customer').order_by('date', 'start_time')

    stats = {
        'total_bookings': Booking.objects.filter(business=business).exclude(status='cancelled').count(),
        'month_bookings': Booking.objects.filter(business=business, created_at__gte=month_start).exclude(status='cancelled').count(),
        'completed': Booking.objects.filter(business=business, status='completed').count(),
        'cancelled': Booking.objects.filter(business=business, status='cancelled').count(),
        'no_shows': Booking.objects.filter(business=business, status='no_show').count(),
        'employees': business.employees.filter(is_active=True).count(),
        'services': business.services.filter(is_active=True).count(),
        'reviews_count': business.review_count,
        'avg_rating': business.average_rating,
    }

    # Revenue from completed bookings
    from payments.models import Payment
    stats['month_revenue'] = Payment.objects.filter(
        booking__business=business,
        status='succeeded',
        created_at__gte=month_start,
    ).aggregate(total=Sum('amount'))['total'] or 0

    from datetime import timedelta
    upcoming_bookings = Booking.objects.filter(
        business=business,
        date__gt=today,
        date__lte=today + timedelta(days=7),
        status__in=['pending', 'confirmed'],
    ).select_related('employee', 'service', 'customer').order_by('date', 'start_time')

    # Get latest published news
    latest_news = News.objects.filter(status='published').order_by('-published_at')[:5]

    context = {
        'business': business,
        'today_bookings': today_bookings,
        'pending_bookings': pending_bookings,
        'overdue_bookings': overdue_bookings,
        'upcoming_bookings': upcoming_bookings,
        'stats': stats,
        'latest_news': latest_news,
    }
    return render(request, 'businesses/dashboard.html', context)


@login_required
@professional_required
def tutorial(request):
    """Tutorial/Help page for business owners."""
    business = _get_accessible_business(request)
    context = {'business': business}
    return render(request, 'businesses/tutorial.html', context)


@login_required
@professional_required
def business_settings(request):
    """Edit business settings."""
    business = _get_accessible_business(request)
    _ensure_business_hours(business)

    if request.method == 'POST':
        business.name = request.POST.get('name', '').strip()
        business.category = request.POST.get('category', 'other')
        if business.category == 'other':
            business.custom_category_gr = request.POST.get('custom_category_gr', '').strip()
            business.custom_category_en = request.POST.get('custom_category_en', '').strip()
            # Keep legacy field in sync as fallback for older templates/data paths.
            business.custom_category = business.custom_category_gr or business.custom_category_en
            if not business.custom_category_gr or not business.custom_category_en:
                messages.error(request, 'Συμπληρώστε και την ελληνική και την αγγλική κατηγορία όταν επιλέγετε Άλλο.')
                return redirect('businesses:settings')
        else:
            business.custom_category = ''
            business.custom_category_gr = ''
            business.custom_category_en = ''
        business.description = request.POST.get('description', '').strip()
        business.address = request.POST.get('address', '').strip()
        phone = request.POST.get('phone', '').strip()
        
        # Validate phone if provided
        if phone and (not phone.isdigit() or len(phone) != 10):
            messages.error(request, 'Το τηλέφωνο πρέπει να είναι 10 ψηφία.')
            return redirect('businesses:settings')
        
        business.phone = phone
        business.email = request.POST.get('email', '').strip()
        business.auto_confirm = request.POST.get('auto_confirm') == 'on'
        business.allow_employee_selection = request.POST.get('allow_employee_selection') == 'on'
        
        # Capacity
        hourly_capacity = request.POST.get('hourly_capacity', '1')
        business.hourly_capacity = int(hourly_capacity) if hourly_capacity.isdigit() else 1

        booking_gap_enabled = request.POST.get('booking_gap_enabled') == 'on'
        booking_gap_minutes_raw = request.POST.get('booking_gap_minutes', '0').strip()
        if not booking_gap_minutes_raw.isdigit():
            messages.error(request, 'Το κενό μεταξύ ραντεβού πρέπει να είναι αριθμός λεπτών.')
            return redirect('businesses:settings')

        booking_gap_minutes = int(booking_gap_minutes_raw)
        if booking_gap_minutes < 0 or booking_gap_minutes > 240:
            messages.error(request, 'Το κενό μεταξύ ραντεβού πρέπει να είναι από 0 έως 240 λεπτά.')
            return redirect('businesses:settings')

        business.booking_gap_enabled = booking_gap_enabled
        business.booking_gap_minutes = booking_gap_minutes if booking_gap_enabled else booking_gap_minutes

        reminder_minutes_raw = request.POST.get('sms_reminder_minutes_before', '30').strip()
        if not reminder_minutes_raw.isdigit():
            messages.error(request, 'Το πεδίο SMS υπενθύμισης πρέπει να είναι αριθμός.')
            return redirect('businesses:settings')

        reminder_minutes = int(reminder_minutes_raw)
        if reminder_minutes < 5 or reminder_minutes > 1440:
            messages.error(request, 'Η SMS υπενθύμιση πρέπει να είναι από 5 έως 1440 λεπτά.')
            return redirect('businesses:settings')
        business.sms_reminder_minutes_before = reminder_minutes

        business.requires_deposit = request.POST.get('requires_deposit') == 'on'
        deposit_pct = request.POST.get('deposit_percentage', '30')
        business.deposit_percentage = int(deposit_pct) if deposit_pct.isdigit() else 30
        
        business.charge_cancellation_fee = request.POST.get('charge_cancellation_fee') == 'on'
        cancel_fee_pct = request.POST.get('cancellation_fee_percentage', '30')
        business.cancellation_fee_percentage = int(cancel_fee_pct) if cancel_fee_pct.isdigit() else 30

        # Employee accounts
        business.allow_employee_accounts = request.POST.get('allow_employee_accounts') == 'on'

        # Superadmin troubleshooting consent
        business.allow_superadmin_troubleshooting_access = request.POST.get('allow_superadmin_troubleshooting_access') == 'on'

        hex_pattern = re.compile(r'^#[0-9A-Fa-f]{6}$')

        def cleaned_color(field_name, fallback):
            value = request.POST.get(field_name, '').strip()
            if not value:
                return fallback
            if not hex_pattern.match(value):
                messages.error(request, 'Μη έγκυρη παλέτα widget. Χρησιμοποιήστε έγκυρα hex χρώματα.')
                raise ValueError('Invalid widget color')
            return value

        try:
            business.widget_primary_color = cleaned_color('widget_primary_color', '#c9a227')
            business.widget_secondary_color = cleaned_color('widget_secondary_color', '#f0c04a')
            business.widget_dark_color = cleaned_color('widget_dark_color', '#8a6500')
            business.widget_background_color = cleaned_color('widget_background_color', '#f8fafc')
        except ValueError:
            return redirect('businesses:settings')

        widget_theme_profile = request.POST.get('widget_theme_profile', '').strip()
        if widget_theme_profile not in {'classic', 'site_match'}:
            widget_theme_profile = 'site_match' if request.POST.get('custom_site_enabled') == 'on' else 'classic'
        business.widget_theme_profile = widget_theme_profile

        public_site_mode = request.POST.get('public_site_mode', '').strip()
        if public_site_mode not in {'booking_page', 'custom_html', 'built_in_site', 'external_website'}:
            public_site_mode = 'booking_page'
        business.public_site_mode = public_site_mode

        remove_custom_html = request.POST.get('remove_custom_landing_html') == 'on'
        uploaded_custom_html = request.FILES.get('custom_landing_html')

        if remove_custom_html and business.custom_landing_html:
            try:
                business.custom_landing_html.delete(save=False)
                business.custom_landing_html = None
            except (PermissionError, OSError):
                messages.error(request, 'Αποτυχία αφαίρεσης της τρέχουσας HTML σελίδας λόγω δικαιωμάτων αρχείων στο server.')
                return redirect('businesses:settings')

        if uploaded_custom_html:
            file_name = (uploaded_custom_html.name or '').lower()
            if not (file_name.endswith('.html') or file_name.endswith('.htm')):
                messages.error(request, 'Η προσαρμοσμένη σελίδα πρέπει να είναι αρχείο .html ή .htm.')
                return redirect('businesses:settings')
            business.custom_landing_html = uploaded_custom_html

        external_website_url = request.POST.get('external_website_url', '').strip()
        if public_site_mode == 'external_website' and not external_website_url:
            messages.error(request, 'Συμπληρώστε το εξωτερικό website για να ενεργοποιηθεί αυτή η επιλογή.')
            return redirect('businesses:settings')

        business.external_website_url = external_website_url

        business.custom_site_enabled = request.POST.get('custom_site_enabled') == 'on'
        business.custom_site_title = request.POST.get('custom_site_title', '').strip()
        business.custom_site_subtitle = request.POST.get('custom_site_subtitle', '').strip()
        business.custom_site_about_title = request.POST.get('custom_site_about_title', '').strip()
        business.custom_site_about_text = request.POST.get('custom_site_about_text', '').strip()
        business.custom_site_cta_text = request.POST.get('custom_site_cta_text', '').strip()
        business.custom_site_gallery_title = request.POST.get('custom_site_gallery_title', '').strip()

        for field_name in ['custom_site_image_1', 'custom_site_image_2', 'custom_site_image_3']:
            uploaded_image = request.FILES.get(field_name)
            if uploaded_image:
                setattr(business, field_name, uploaded_image)

        # Optional daily break period
        break_enabled = request.POST.get('break_enabled') == 'on'
        break_start_raw = request.POST.get('break_start_time', '').strip()
        break_end_raw = request.POST.get('break_end_time', '').strip()

        if break_enabled:
            if not break_start_raw or not break_end_raw:
                messages.error(request, 'Συμπληρώστε ώρα έναρξης και λήξης διαλείμματος.')
                return redirect('businesses:settings')
            try:
                break_start_time = datetime.strptime(break_start_raw, '%H:%M').time()
                break_end_time = datetime.strptime(break_end_raw, '%H:%M').time()
            except ValueError:
                messages.error(request, 'Μη έγκυρη μορφή ώρας διαλείμματος.')
                return redirect('businesses:settings')

            if break_start_time >= break_end_time:
                messages.error(request, 'Η λήξη διαλείμματος πρέπει να είναι μετά την έναρξη.')
                return redirect('businesses:settings')

            business.break_start_time = break_start_time
            business.break_end_time = break_end_time
        else:
            business.break_start_time = None
            business.break_end_time = None

        remove_logo = request.POST.get('remove_logo') == 'on'
        if remove_logo and business.logo:
            try:
                business.logo.delete(save=False)
                business.logo = None
            except (PermissionError, OSError):
                messages.error(request, 'Αποτυχία αφαίρεσης logo λόγω δικαιωμάτων αρχείων στο server.')
                return redirect('businesses:settings')

        if 'logo' in request.FILES:
            business.logo = request.FILES['logo']

        # Auto-reply settings for reviews
        business.auto_reply_enabled = request.POST.get('auto_reply_enabled') == 'on'
        auto_reply_template = request.POST.get('auto_reply_template', '').strip()
        if auto_reply_template:
            business.auto_reply_template = auto_reply_template

        try:
            business.save()
        except (PermissionError, OSError):
            messages.error(
                request,
                'Αποτυχία αποθήκευσης αρχείων (logo/HTML) λόγω δικαιωμάτων φακέλου media στον server. Επικοινωνήστε με διαχειριστή server.',
            )
            return redirect('businesses:settings')

        # Save per-day BusinessHours
        for day in range(7):
            is_closed = request.POST.get(f'day_{day}_closed') == 'on'
            start = request.POST.get(f'day_{day}_start', '09:00') or '09:00'
            end = request.POST.get(f'day_{day}_end', '17:00') or '17:00'
            BusinessHours.objects.update_or_create(
                business=business, day_of_week=day,
                defaults={'is_closed': is_closed, 'start_time': start, 'end_time': end},
            )

        messages.success(request, 'Οι ρυθμίσεις αποθηκεύτηκαν.')
        return redirect('businesses:settings')

    business_hours = {bh.day_of_week: bh for bh in business.business_hours.all()}
    day_names = ['Δευτέρα', 'Τρίτη', 'Τετάρτη', 'Πέμπτη', 'Παρασκευή', 'Σάββατο', 'Κυριακή']
    schedule = []
    for i, name in enumerate(day_names):
        bh = business_hours.get(i)
        schedule.append({
            'day': i,
            'name': name,
            'start': bh.start_time.strftime('%H:%M') if bh else '09:00',
            'end': bh.end_time.strftime('%H:%M') if bh else '17:00',
            'is_closed': bh.is_closed if bh else (i >= 5),
        })

    context = {'business': business, 'schedule': schedule}
    return render(request, 'businesses/business_settings.html', context)


# ── Employees ───────────────────────────────────────────

@login_required
@professional_required
def employee_list(request):
    """List employees for the business."""
    business = _get_accessible_business(request)
    employees = business.employees.exclude(
        name='Σύστημα',
        title='Αυτόματη Ανάθεση',
    )
    today = timezone.now().date()
    unavailable_today_ids = set(
        SpecialDayOff.objects.filter(
            employee__business=business, date=today
        ).values_list('employee_id', flat=True)
    )
    context = {
        'business': business,
        'employees': employees,
        'unavailable_today_ids': unavailable_today_ids,
    }
    return render(request, 'businesses/employee_list.html', context)


@login_required
@professional_required
def add_employee(request):
    """Add a new employee."""
    business = _get_accessible_business(request)

    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        
        # Validate phone if provided
        if phone and (not phone.isdigit() or len(phone) != 10):
            messages.error(request, 'Το τηλέφωνο πρέπει να είναι 10 ψηφία.')
            return render(request, 'businesses/employee_form.html', {'business': business})
        
        employee = Employee.objects.create(
            business=business,
            name=request.POST.get('name', '').strip(),
            title=request.POST.get('title', '').strip(),
            email=request.POST.get('email', '').strip(),
            phone=phone,
        )
        if 'photo' in request.FILES:
            employee.photo = request.FILES['photo']
            employee.save()

        # Create default working hours (Mon-Fri 09:00-17:00)
        for day in range(5):
            WorkingHours.objects.create(
                employee=employee,
                day_of_week=day,
                start_time='09:00',
                end_time='17:00',
            )
        for day in range(5, 7):
            WorkingHours.objects.create(
                employee=employee,
                day_of_week=day,
                start_time='09:00',
                end_time='17:00',
                is_day_off=True,
            )

        messages.success(request, f'Ο υπάλληλος {employee.name} προστέθηκε.')
        return redirect('businesses:employee_list')

    return render(request, 'businesses/employee_form.html', {'business': business})


@login_required
@professional_required
def edit_employee(request, employee_id):
    """Edit an employee."""
    business = _get_accessible_business(request)
    employee = get_object_or_404(Employee, id=employee_id, business=business)

    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        
        # Validate phone if provided
        if phone and (not phone.isdigit() or len(phone) != 10):
            messages.error(request, 'Το τηλέφωνο πρέπει να είναι 10 ψηφία.')
            return render(request, 'businesses/employee_form.html', {'business': business, 'employee': employee})
        
        employee.name = request.POST.get('name', '').strip()
        employee.title = request.POST.get('title', '').strip()
        employee.email = request.POST.get('email', '').strip()
        employee.phone = phone
        employee.is_active = request.POST.get('is_active') == 'on'
        if 'photo' in request.FILES:
            employee.photo = request.FILES['photo']
        employee.save()
        messages.success(request, f'Ο υπάλληλος {employee.name} ενημερώθηκε.')
        return redirect('businesses:employee_list')

    context = {'business': business, 'employee': employee}
    return render(request, 'businesses/employee_form.html', context)


@login_required
@professional_required
def delete_employee(request, employee_id):
    """Deactivate ('fire') an employee with safe handling of future bookings."""
    business = _get_accessible_business(request)
    employee = get_object_or_404(Employee, id=employee_id, business=business)
    if request.method == 'POST':
        today = timezone.now().date()
        affected_bookings = Booking.objects.filter(
            employee=employee, date__gte=today, status__in=['pending', 'confirmed']
        ).select_related('service', 'customer')

        replacement = business.employees.filter(
            is_active=True,
        ).exclude(
            id=employee.id,
        ).exclude(
            name='Σύστημα',
            title='Αυτόματη Ανάθεση',
        ).order_by('id').first()

        reassigned_count = 0
        cancelled_count = 0

        for booking in affected_bookings:
            old_status = booking.status
            if replacement:
                booking.employee = replacement
                booking.save(update_fields=['employee', 'updated_at'])
                BookingStatusLog.objects.create(
                    booking=booking,
                    old_status=old_status,
                    new_status=old_status,
                    changed_by=request.user,
                    notes=f'Ανατέθηκε σε νέο υπάλληλο λόγω αποχώρησης: {replacement.name}',
                )
                send_employee_new_booking_email(booking)
                reassigned_count += 1
            else:
                booking.status = 'cancelled'
                booking.rejection_reason = (
                    f'Ο υπάλληλος {employee.name} αποχώρησε και δεν υπάρχει διαθέσιμος αντικαταστάτης.'
                )
                booking.save(update_fields=['status', 'rejection_reason', 'updated_at'])
                BookingStatusLog.objects.create(
                    booking=booking,
                    old_status=old_status,
                    new_status='cancelled',
                    changed_by=request.user,
                    notes='Ακύρωση λόγω αποχώρησης υπαλλήλου',
                )
                from notifications.utils import send_booking_rejected_email
                send_booking_rejected_email(booking)
                cancelled_count += 1

        employee.is_active = False
        employee.user = None
        employee.save(update_fields=['is_active', 'user'])

        messages.success(
            request,
            f'Ο υπάλληλος {employee.name} απενεργοποιήθηκε. '
            f'Επανανατέθηκαν: {reassigned_count}, Ακυρώθηκαν: {cancelled_count}.',
        )
    return redirect('businesses:employee_list')


@login_required
@professional_required
def toggle_employee_accounts(request):
    """Toggle the allow_employee_accounts setting for the business."""
    business = _get_accessible_business(request)
    if request.method == 'POST':
        business.allow_employee_accounts = not business.allow_employee_accounts
        business.save()
        if business.allow_employee_accounts:
            messages.success(request, 'Οι λογαριασμοί υπαλλήλων ενεργοποιήθηκαν.')
        else:
            messages.info(request, 'Οι λογαριασμοί υπαλλήλων απενεργοποιήθηκαν.')
    return redirect('businesses:employee_list')


@login_required
@professional_required
def toggle_employee_booking_actions(request):
    """Toggle whether employees can confirm/reject their bookings."""
    business = _get_accessible_business(request)
    if request.method == 'POST':
        business.allow_employee_booking_actions = not business.allow_employee_booking_actions
        business.save(update_fields=['allow_employee_booking_actions'])
        if business.allow_employee_booking_actions:
            messages.success(request, 'Οι ενέργειες ραντεβού από υπαλλήλους ενεργοποιήθηκαν.')
        else:
            messages.info(request, 'Οι ενέργειες ραντεβού από υπαλλήλους απενεργοποιήθηκαν.')
    return redirect('businesses:employee_list')


@login_required
@professional_required
def send_employee_invitation(request, employee_id):
    """Send invitation email to employee to create account."""
    business = _get_accessible_business(request)

    if not business.allow_employee_accounts:
        messages.error(request, 'Οι λογαριασμοί υπαλλήλων δεν είναι ενεργοποιημένοι.')
        return redirect('businesses:employee_list')

    employee = get_object_or_404(Employee, id=employee_id, business=business)

    if employee.user:
        messages.warning(request, f'Ο {employee.name} έχει ήδη λογαριασμό.')
        return redirect('businesses:employee_list')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()

        if not email:
            messages.error(request, 'Παρακαλώ εισάγετε email.')
            return redirect('businesses:edit_employee', employee_id=employee.id)

        # Update employee email
        employee.email = email
        employee.save()

        # Invalidate any existing unused invitations
        EmployeeInvitation.objects.filter(employee=employee, is_used=False).update(is_used=True)

        # Create new invitation
        invitation = EmployeeInvitation.objects.create(
            employee=employee,
            email=email,
        )

        # Build accept URL
        site_url = getattr(django_settings, 'SITE_URL', 'http://localhost:8000')
        accept_url = f"{site_url}/accounts/employee-invitation/{invitation.token}/"

        context = {
            'employee': employee,
            'business': business,
            'invitation': invitation,
            'accept_url': accept_url,
        }

        try:
            html_message = render_to_string('accounts/employee_invitation_email.html', context)

            # Plain text version for email compatibility
            plain_message = f"""
Πρόσκληση από {business.name}

Γεια σας {employee.name},

Η επιχείρηση {business.name} σας προσκαλεί να δημιουργήσετε λογαριασμό υπαλλήλου στην πλατφόρμα Reserva.

Με τον λογαριασμό σας θα μπορείτε να:
- Βλέπετε το πρόγραμμα και τα ραντεβού σας
- Δηλώνετε άδειες ή ημέρες απουσίας
- Ενημερώνετε τη διαθεσιμότητά σας

Για να δημιουργήσετε τον λογαριασμό σας, επισκεφθείτε:
{accept_url}

Ο σύνδεσμος ισχύει για 7 ημέρες.

Με εκτίμηση,
Η Ομάδα του Reserva
"""

            send_mail(
                subject=f'Πρόσκληση από {business.name} - Reserva',
                message=plain_message,
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False,
            )
            messages.success(request, f'Η πρόσκληση εστάλη στο {email}!')
        except Exception as e:
            messages.error(request, f'Αποτυχία αποστολής email: {str(e)}')

    return redirect('businesses:employee_list')


@login_required
@professional_required
def resend_employee_invitation(request, employee_id):
    """Resend invitation email to employee."""
    business = _get_accessible_business(request)
    employee = get_object_or_404(Employee, id=employee_id, business=business)

    if not business.allow_employee_accounts:
        messages.error(request, 'Οι λογαριασμοί υπαλλήλων δεν είναι ενεργοποιημένοι.')
        return redirect('businesses:employee_list')

    if employee.user:
        messages.warning(request, f'Ο {employee.name} έχει ήδη λογαριασμό.')
        return redirect('businesses:employee_list')

    if not employee.email:
        messages.error(request, 'Ο υπάλληλος δεν έχει email.')
        return redirect('businesses:employee_list')

    if request.method == 'POST':
        # Invalidate old invitations
        EmployeeInvitation.objects.filter(employee=employee, is_used=False).update(is_used=True)

        # Create new invitation
        invitation = EmployeeInvitation.objects.create(
            employee=employee,
            email=employee.email,
        )

        # Build accept URL
        site_url = getattr(django_settings, 'SITE_URL', 'http://localhost:8000')
        accept_url = f"{site_url}/accounts/employee-invitation/{invitation.token}/"

        context = {
            'employee': employee,
            'business': business,
            'invitation': invitation,
            'accept_url': accept_url,
        }

        try:
            html_message = render_to_string('accounts/employee_invitation_email.html', context)

            # Plain text version for email compatibility
            plain_message = f"""
Πρόσκληση από {business.name}

Γεια σας {employee.name},

Η επιχείρηση {business.name} σας προσκαλεί να δημιουργήσετε λογαριασμό υπαλλήλου στην πλατφόρμα Reserva.

Με τον λογαριασμό σας θα μπορείτε να:
- Βλέπετε το πρόγραμμα και τα ραντεβού σας
- Δηλώνετε άδειες ή ημέρες απουσίας
- Ενημερώνετε τη διαθεσιμότητά σας

Για να δημιουργήσετε τον λογαριασμό σας, επισκεφθείτε:
{accept_url}

Ο σύνδεσμος ισχύει για 7 ημέρες.

Με εκτίμηση,
Η Ομάδα του Reserva
"""

            send_mail(
                subject=f'Πρόσκληση από {business.name} - Reserva',
                message=plain_message,
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=[employee.email],
                html_message=html_message,
                fail_silently=False,
            )
            messages.success(request, f'Νέα πρόσκληση εστάλη στο {employee.email}!')
        except Exception as e:
            messages.error(request, f'Αποτυχία αποστολής email: {str(e)}')

    return redirect('businesses:employee_list')


# ── Services ────────────────────────────────────────────

@login_required
@professional_required
def service_list(request):
    """List services."""
    business = _get_accessible_business(request)
    services = business.services.all()
    context = {'business': business, 'services': services}
    return render(request, 'businesses/service_list.html', context)


@login_required
@professional_required
def add_service(request):
    """Add a new service."""
    business = _get_accessible_business(request)

    if request.method == 'POST':
        service_name = request.POST.get('name', '').strip()
        duration = int(request.POST.get('duration_minutes', 30))
        cancellation_deadline_hours = int(request.POST.get('cancellation_deadline_hours', 24) or 24)
        
        # Check for duplicate service name
        if Service.objects.filter(business=business, name__iexact=service_name).exists():
            messages.error(request, f'Μια υπηρεσία με το όνομα "{service_name}" υπάρχει ήδη.')
            return render(request, 'businesses/service_form.html', {'business': business})
        
        if duration < 5:
            messages.error(request, 'Η διάρκεια πρέπει να είναι τουλάχιστον 5 λεπτά.')
            return render(request, 'businesses/service_form.html', {'business': business})
        if cancellation_deadline_hours < 0 or cancellation_deadline_hours > 720:
            messages.error(request, 'Η προθεσμία ακύρωσης πρέπει να είναι από 0 έως 720 ώρες.')
            return render(request, 'businesses/service_form.html', {'business': business})
        Service.objects.create(
            business=business,
            name=service_name,
            description=request.POST.get('description', '').strip(),
            duration_minutes=duration,
            price=request.POST.get('price', 0),
            cancellation_deadline_hours=cancellation_deadline_hours,
        )
        messages.success(request, 'Η υπηρεσία προστέθηκε.')
        return redirect('businesses:service_list')

    return render(request, 'businesses/service_form.html', {'business': business})


@login_required
@professional_required
def edit_service(request, service_id):
    """Edit a service."""
    business = _get_accessible_business(request)
    service = get_object_or_404(Service, id=service_id, business=business)

    if request.method == 'POST':
        service_name = request.POST.get('name', '').strip()
        duration = int(request.POST.get('duration_minutes', 30))
        cancellation_deadline_hours = int(request.POST.get('cancellation_deadline_hours', 24) or 24)
        
        # Check for duplicate service name (excluding current service)
        if Service.objects.filter(business=business, name__iexact=service_name).exclude(id=service_id).exists():
            messages.error(request, f'Μια υπηρεσία με το όνομα "{service_name}" υπάρχει ήδη.')
            return render(request, 'businesses/service_form.html', {'business': business, 'service': service})
        
        if duration < 5:
            messages.error(request, 'Η διάρκεια πρέπει να είναι τουλάχιστον 5 λεπτά.')
            return render(request, 'businesses/service_form.html', {'business': business, 'service': service})
        if cancellation_deadline_hours < 0 or cancellation_deadline_hours > 720:
            messages.error(request, 'Η προθεσμία ακύρωσης πρέπει να είναι από 0 έως 720 ώρες.')
            return render(request, 'businesses/service_form.html', {'business': business, 'service': service})
        service.name = service_name
        service.description = request.POST.get('description', '').strip()
        service.duration_minutes = duration
        service.price = request.POST.get('price', 0)
        service.cancellation_deadline_hours = cancellation_deadline_hours
        service.is_active = request.POST.get('is_active') == 'on'
        service.save()
        messages.success(request, f'Η υπηρεσία "{service.name}" ενημερώθηκε.')
        return redirect('businesses:service_list')

    context = {'business': business, 'service': service}
    return render(request, 'businesses/service_form.html', context)


@login_required
@professional_required
def delete_service(request, service_id):
    """Delete a service."""
    business = _get_accessible_business(request)
    service = get_object_or_404(Service, id=service_id, business=business)
    if request.method == 'POST':
        today = timezone.now().date()
        future_count = Booking.objects.filter(
            service=service, date__gte=today, status__in=['pending', 'confirmed']
        ).count()
        if future_count > 0:
            messages.error(request, f'Η υπηρεσία έχει {future_count} επερχόμενα ραντεβού και δεν μπορεί να διαγραφεί.')
            return redirect('businesses:service_list')
        service.delete()
        messages.success(request, 'Η υπηρεσία διαγράφηκε.')
    return redirect('businesses:service_list')


# ── Schedule / Working Hours ────────────────────────────

@login_required
@professional_required
def schedule_view(request, employee_id):
    """View/edit employee schedule (working hours)."""
    business = _get_accessible_business(request)
    employee = get_object_or_404(Employee, id=employee_id, business=business)
    hours = employee.working_hours.all()
    days_off = employee.days_off.filter(date__gte=timezone.now().date()).order_by('date')

    if request.method == 'POST':
        # Update working hours
        for day in range(7):
            wh, created = WorkingHours.objects.get_or_create(
                employee=employee, day_of_week=day,
                defaults={'start_time': '09:00', 'end_time': '17:00'}
            )
            wh.is_day_off = request.POST.get(f'day_off_{day}') == 'on'
            wh.start_time = request.POST.get(f'start_{day}', '09:00')
            wh.end_time = request.POST.get(f'end_{day}', '17:00')
            wh.save()

        messages.success(request, f'Το ωράριο του {employee.name} αποθηκεύτηκε.')
        return redirect('businesses:schedule', employee_id=employee.id)

    context = {
        'business': business,
        'employee': employee,
        'hours': hours,
        'days_off': days_off,
    }
    return render(request, 'businesses/schedule.html', context)


@login_required
@professional_required
def add_day_off(request, employee_id):
    """Add a special day off for employee."""
    business = _get_accessible_business(request)
    employee = get_object_or_404(Employee, id=employee_id, business=business)

    if request.method == 'POST':
        date_str = request.POST.get('date', '')
        reason = request.POST.get('reason', '').strip()
        if date_str:
            from datetime import datetime
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            if date < timezone.now().date():
                messages.error(request, 'Δεν μπορείτε να προσθέσετε αργία σε παρελθοντική ημερομηνία.')
            else:
                SpecialDayOff.objects.get_or_create(
                    employee=employee, date=date,
                    defaults={'reason': reason}
                )
                messages.success(request, 'Η ειδική αργία προστέθηκε.')

    return redirect('businesses:schedule', employee_id=employee.id)


@login_required
@professional_required
def delete_day_off(request, dayoff_id):
    """Remove a special day off."""
    business = _get_accessible_business(request)
    dayoff = get_object_or_404(SpecialDayOff, id=dayoff_id, employee__business=business)
    emp_id = dayoff.employee.id
    if request.method == 'POST':
        dayoff.delete()
        messages.success(request, 'Η ειδική αργία αφαιρέθηκε.')
    return redirect('businesses:schedule', employee_id=emp_id)


# ── Booking Management ──────────────────────────────────

@login_required
@professional_required
def booking_list(request):
    """List all bookings for this business."""
    business = _get_accessible_business(request)
    status_filter = request.GET.get('status', '')
    bookings = Booking.objects.filter(business=business).select_related(
        'employee', 'service', 'customer'
    ).order_by('-date', '-start_time')

    if status_filter:
        bookings = bookings.filter(status=status_filter)

    bookings_calendar_data = [
        {
            'id': booking.id,
            'date': booking.date.isoformat(),
            'start_time': booking.start_time.strftime('%H:%M:%S'),
            'end_time': booking.end_time.strftime('%H:%M:%S'),
            'status': booking.status,
            'status_display': booking.get_status_display(),
            'can_no_show': booking.date <= timezone.now().date(),
            'service': {
                'name': booking.service.name if booking.service else '',
            },
            'employee': {
                'name': booking.employee.name if booking.employee else '',
            },
            'customer': {
                'first_name': booking.customer.first_name if booking.customer else '',
                'username': booking.customer.username if booking.customer else '',
                'phone': booking.customer.phone if booking.customer else '',
            },
            'guest_name': booking.guest_name,
            'guest_phone': booking.guest_phone,
            'notes': booking.notes,
            'action_urls': {
                'confirm': reverse('businesses:confirm_booking', args=[booking.id]),
                'reject': reverse('businesses:reject_booking', args=[booking.id]),
                'complete': reverse('businesses:mark_completed', args=[booking.id]),
                'no_show': reverse('businesses:mark_no_show', args=[booking.id]),
            },
        }
        for booking in bookings
    ]

    context = {
        'business': business,
        'bookings': bookings,
        'bookings_calendar_data': bookings_calendar_data,
        'status_filter': status_filter,
        'today': timezone.now().date(),
    }
    return render(request, 'businesses/booking_list.html', context)


def _booking_export_queryset(business, status_filter=''):
    bookings = Booking.objects.filter(business=business).select_related(
        'employee', 'service', 'customer'
    ).order_by('-date', '-start_time')
    if status_filter:
        bookings = bookings.filter(status=status_filter)
    return bookings


@login_required
@professional_required
def export_bookings_csv(request):
    """Export business bookings to CSV."""
    from io import StringIO
    
    business = _get_accessible_business(request)
    status_filter = request.GET.get('status', '')
    bookings = _booking_export_queryset(business, status_filter=status_filter)

    # Write to StringIO first to properly handle UTF-8 with BOM
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'ID', 'Ημερομηνία', 'Ώρα', 'Κατάσταση', 'Πελάτης', 'Τηλέφωνο', 'Email',
        'Υπηρεσία', 'Υπάλληλος', 'Σημειώσεις', 'Τιμή', 'Πληρωμή', 'Δημιουργήθηκε',
    ])

    for booking in bookings:
        customer_name = booking.customer.get_full_name() if booking.customer else booking.guest_name
        customer_phone = booking.customer_phone or booking.guest_phone or (booking.customer.phone if booking.customer else '')
        customer_email = booking.customer.email if booking.customer else booking.guest_email
        writer.writerow([
            booking.id,
            booking.date.strftime('%d/%m/%Y'),
            f'{booking.start_time.strftime("%H:%M")}-{booking.end_time.strftime("%H:%M")}',
            booking.get_status_display(),
            customer_name,
            customer_phone,
            customer_email,
            booking.service.name,
            booking.employee.name,
            booking.notes,
            booking.price_at_booking,
            booking.get_payment_status_display(),
            booking.created_at.strftime('%d/%m/%Y %H:%M'),
        ])

    # Encode with UTF-8 BOM so Excel recognizes Greek characters
    csv_content = output.getvalue()
    response = HttpResponse(csv_content.encode('utf-8-sig'), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="bookings-{business.slug}.csv"'
    return response


@login_required
@professional_required
def export_bookings_xlsx(request):
    """Export business bookings to Excel."""
    business = _get_accessible_business(request)
    status_filter = request.GET.get('status', '')
    bookings = _booking_export_queryset(business, status_filter=status_filter)
    from .spreadsheet_utils import build_xlsx_bytes

    headers = [
        'ID', 'Ημερομηνία', 'Ώρα', 'Κατάσταση', 'Πελάτης', 'Τηλέφωνο', 'Email',
        'Υπηρεσία', 'Υπάλληλος', 'Σημειώσεις', 'Τιμή', 'Πληρωμή', 'Δημιουργήθηκε',
    ]
    rows = []
    for booking in bookings:
        customer_name = booking.customer.get_full_name() if booking.customer else booking.guest_name
        customer_phone = booking.customer_phone or booking.guest_phone or (booking.customer.phone if booking.customer else '')
        customer_email = booking.customer.email if booking.customer else booking.guest_email
        rows.append([
            booking.id,
            booking.date.strftime('%d/%m/%Y'),
            f'{booking.start_time.strftime("H:%M")}-{booking.end_time.strftime("H:%M")}',
            booking.get_status_display(),
            customer_name,
            customer_phone,
            customer_email,
            booking.service.name,
            booking.employee.name,
            booking.notes,
            float(booking.price_at_booking),
            booking.get_payment_status_display(),
            booking.created_at.strftime('%d/%m/%Y %H:%M'),
        ])

    output = build_xlsx_bytes('Bookings', headers, rows)
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="bookings-{business.slug}.xlsx"'
    return response


@login_required
@professional_required
def customers_list(request):
    """List business customers and allow storing notes about preferences."""
    business = _get_accessible_business(request)

    if request.method == 'POST':
        from .models import BusinessCustomer

        customer_id = request.POST.get('customer_id', '').strip()
        customer = get_object_or_404(BusinessCustomer, id=customer_id, business=business)
        customer.notes = request.POST.get('notes', '').strip()
        customer.save(update_fields=['notes', 'updated_at'])
        messages.success(request, f'Οι σημειώσεις για τον πελάτη {customer.display_name} αποθηκεύτηκαν.')
        return redirect('businesses:customers_list')

    customers = business_customer_queryset(business)

    context = {
        'business': business,
        'customers': customers,
    }
    return render(request, 'businesses/customers_list.html', context)


@login_required
@professional_required
def manual_booking_add(request):
    """Create a booking manually for a phone call or walk-in customer."""
    business = _get_accessible_business(request)
    services = business.services.filter(is_active=True).order_by('name')
    employees = business.employees.filter(is_active=True).exclude(
        name='Σύστημα',
        title='Αυτόματη Ανάθεση',
    ).order_by('name')

    if request.method == 'POST':
        employee_id = (request.POST.get('employee_id') or '').strip()
        service_id = (request.POST.get('service_id') or '').strip()
        date_str = (request.POST.get('date') or '').strip()
        start_time_str = (request.POST.get('start_time') or '').strip()
        guest_name = (request.POST.get('guest_name') or '').strip()
        guest_phone = (request.POST.get('guest_phone') or '').strip()
        guest_email = (request.POST.get('guest_email') or '').strip()
        notes = (request.POST.get('notes') or '').strip()
        booking_status = (request.POST.get('status') or 'confirmed').strip()

        if not guest_name:
            messages.error(request, 'Συμπληρώστε όνομα πελάτη.')
            return render(request, 'businesses/manual_booking_form.html', {
                'business': business,
                'services': services,
                'employees': employees,
                'status_choices': Booking.STATUS_CHOICES,
            })

        if not guest_phone or not guest_phone.isdigit() or len(guest_phone) != 10:
            messages.error(request, 'Συμπληρώστε έγκυρο τηλέφωνο 10 ψηφίων.')
            return render(request, 'businesses/manual_booking_form.html', {
                'business': business,
                'services': services,
                'employees': employees,
                'status_choices': Booking.STATUS_CHOICES,
            })

        if booking_status not in {'pending', 'confirmed'}:
            booking_status = 'confirmed'

        try:
            booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
        except ValueError:
            messages.error(request, 'Μη έγκυρη ημερομηνία ή ώρα.')
            return render(request, 'businesses/manual_booking_form.html', {
                'business': business,
                'services': services,
                'employees': employees,
                'status_choices': Booking.STATUS_CHOICES,
            })

        service = get_object_or_404(Service, id=service_id, business=business, is_active=True)
        end_time = (datetime.combine(booking_date, start_time) + timedelta(minutes=service.duration_minutes)).time()

        employee = None
        use_capacity_mode = False
        if employee_id and employee_id.lower() != 'auto':
            employee = get_object_or_404(Employee, id=employee_id, business=business)
        else:
            use_capacity_mode = True

        if use_capacity_mode:
            employee = employees.first()
            if not employee:
                employee, _ = Employee.objects.get_or_create(
                    business=business,
                    name='Σύστημα',
                    title='Αυτόματη Ανάθεση',
                    defaults={'is_active': True},
                )

        from businesses.models import BusinessDayOff
        if BusinessDayOff.objects.filter(business=business, date=booking_date).exists():
            messages.error(request, f'Η επιχείρηση είναι κλειστή στις {booking_date.strftime("%d/%m/%Y")}.' )
            return render(request, 'businesses/manual_booking_form.html', {
                'business': business,
                'services': services,
                'employees': employees,
                'status_choices': Booking.STATUS_CHOICES,
            })

        from bookings.utils import get_available_slots, get_available_slots_capacity

        with transaction.atomic():
            Booking.objects.select_for_update().filter(
                employee=employee, date=booking_date
            ).values('id')

            if use_capacity_mode:
                available = get_available_slots_capacity(business, service, booking_date)
            else:
                available = get_available_slots(employee, service, booking_date)

            slot_available = any(slot['start'] == start_time for slot in available)
            if not slot_available:
                messages.error(request, 'Αυτή η ώρα δεν είναι διαθέσιμη.')
                return render(request, 'businesses/manual_booking_form.html', {
                    'business': business,
                    'services': services,
                    'employees': employees,
                    'status_choices': Booking.STATUS_CHOICES,
                })

            guest_contact_preference = 'phone'
            if guest_email:
                guest_contact_preference = 'both'

            deposit_amount = 0
            payment_status = 'not_required'
            if business.requires_deposit:
                deposit_amount = round(float(service.price) * business.deposit_percentage / 100, 2)
                payment_status = 'pending'

            booking = Booking.objects.create(
                business=business,
                employee=employee,
                service=service,
                customer=None,
                guest_name=guest_name,
                guest_phone=guest_phone,
                guest_email=guest_email,
                guest_access_token=secrets.token_urlsafe(32),
                guest_contact_preference=guest_contact_preference,
                customer_contact_preference='',
                customer_phone='',
                date=booking_date,
                start_time=start_time,
                end_time=end_time,
                price_at_booking=service.price,
                status=booking_status,
                payment_status=payment_status,
                deposit_amount=deposit_amount,
                notes=notes,
            )

            BookingStatusLog.objects.create(
                booking=booking,
                old_status='',
                new_status=booking_status,
                changed_by=request.user,
                notes='Χειροκίνητη προσθήκη από επιχείρηση',
            )

            upsert_business_customer_from_booking(booking)

        if booking_status == 'confirmed':
            send_booking_approval_notifications(booking)

        send_employee_new_booking_email(booking)

        messages.success(request, f'Το ραντεβού #{booking.id} προστέθηκε επιτυχώς.')
        return redirect('businesses:booking_list')

    return render(request, 'businesses/manual_booking_form.html', {
        'business': business,
        'services': services,
        'employees': employees,
        'status_choices': Booking.STATUS_CHOICES,
    })


@login_required
@professional_required
def approve_booking(request, booking_id):
    """Approve a pending booking."""
    business = _get_accessible_business(request)
    booking = get_object_or_404(Booking, id=booking_id, business=business)
    
    if booking.status != 'pending':
        messages.warning(request, f'Το ραντεβού #{booking.id} δεν είναι σε κατάσταση αναμονής.')
        return redirect('businesses:booking_list')
    
    old_status = booking.status
    booking.status = 'confirmed'
    booking.save()

    BookingStatusLog.objects.create(
        booking=booking,
        old_status=old_status,
        new_status='confirmed',
        changed_by=request.user,
        notes='Έγκριση από επαγγελματία',
    )

    send_booking_approval_notifications(booking)

    messages.success(request, f'Το ραντεβού #{booking.id} εγκρίθηκε.')
    return redirect('businesses:booking_list')


@login_required
@professional_required
def reject_booking(request, booking_id):
    """Reject a pending or confirmed booking."""
    business = _get_accessible_business(request)
    booking = get_object_or_404(Booking, id=booking_id, business=business)
    if booking.status not in ('pending', 'confirmed'):
        messages.error(request, 'Δεν μπορείτε να απορρίψετε αυτό το ραντεβού.')
        return redirect('businesses:booking_list')

    rejection_reason = request.POST.get('rejection_reason', '').strip()
    if not rejection_reason:
        messages.error(request, 'Παρακαλώ συμπληρώστε λόγο απόρριψης.')
        return redirect('businesses:booking_list')

    old_status = booking.status
    booking.status = 'cancelled'
    booking.rejection_reason = rejection_reason
    booking.save()

    BookingStatusLog.objects.create(
        booking=booking,
        old_status=old_status,
        new_status='cancelled',
        changed_by=request.user,
        notes=f'Απόρριψη από επαγγελματία. Λόγος: {rejection_reason}',
    )

    # Refund if deposit paid
    if booking.deposit_amount > 0:
        from payments.utils import process_refund
        process_refund(booking, refund_percentage=100)

    from notifications.utils import send_booking_rejected_email
    send_booking_rejected_email(booking)

    messages.info(request, f'Το ραντεβού #{booking.id} απορρίφθηκε.')
    return redirect('businesses:booking_list')


@login_required
@professional_required
def mark_no_show(request, booking_id):
    """Mark a booking as no-show."""
    business = _get_accessible_business(request)
    booking = get_object_or_404(Booking, id=booking_id, business=business)
    old_status = booking.status
    booking.status = 'no_show'
    booking.save()

    BookingStatusLog.objects.create(
        booking=booking,
        old_status=old_status,
        new_status='no_show',
        changed_by=request.user,
        notes='Σημειώθηκε ως no-show από επαγγελματία',
    )

    messages.info(request, f'Το ραντεβού #{booking.id} σημειώθηκε ως no-show.')
    next_url = request.POST.get('next', '').strip()
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect('businesses:booking_list')


@login_required
@professional_required
def mark_completed(request, booking_id):
    """Mark a booking as completed."""
    business = _get_accessible_business(request)
    booking = get_object_or_404(Booking, id=booking_id, business=business)
    old_status = booking.status
    booking.status = 'completed'
    booking.save()

    BookingStatusLog.objects.create(
        booking=booking,
        old_status=old_status,
        new_status='completed',
        changed_by=request.user,
        notes='Ολοκλήρωση από επαγγελματία',
    )

    messages.success(request, f'Το ραντεβού #{booking.id} ολοκληρώθηκε.')
    next_url = request.POST.get('next', '').strip()
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect('businesses:booking_list')


# ── Employee Quick Toggle ──────────────────────────────

@login_required
@professional_required
def toggle_employee_today(request, employee_id):
    """Toggle employee availability for today (creates/removes SpecialDayOff for today)."""
    business = _get_accessible_business(request)
    employee = get_object_or_404(Employee, id=employee_id, business=business)
    today = timezone.now().date()

    existing = SpecialDayOff.objects.filter(employee=employee, date=today).first()
    if existing:
        existing.delete()
        messages.success(request, f'Ο {employee.name} είναι πάλι διαθέσιμος σήμερα.')
    else:
        SpecialDayOff.objects.create(employee=employee, date=today, reason='Μη διαθέσιμος')
        messages.info(request, f'Ο {employee.name} μπήκε σε ρεπό για σήμερα.')

    return redirect('businesses:employee_list')


# ── Business Day-Off (temp closure) ────────────────────

@login_required
@professional_required
def business_closures(request):
    """View & manage business temporary closures."""
    business = _get_accessible_business(request)
    _ensure_business_hours(business)
    today = timezone.now().date()
    closures = business.days_off.filter(date__gte=today).order_by('date')

    if request.method == 'POST':
        date_str = request.POST.get('date', '')
        reason = request.POST.get('reason', '').strip()
        if date_str:
            from datetime import datetime as dt
            try:
                closure_date = dt.strptime(date_str, '%Y-%m-%d').date()
                closure, created = BusinessDayOff.objects.get_or_create(
                    business=business, date=closure_date,
                    defaults={'reason': reason}
                )

                if not created and reason and closure.reason != reason:
                    closure.reason = reason
                    closure.save(update_fields=['reason'])

                if created:
                    from payments.utils import process_refund
                    from notifications.utils import (
                        send_business_closed_cancellation_email,
                    )

                    affected_bookings = Booking.objects.filter(
                        business=business,
                        date=closure_date,
                        status__in=('pending', 'confirmed'),
                    ).select_related('customer', 'service', 'employee')

                    cancelled_count = 0
                    day_reason = reason or 'Η επιχείρηση παραμένει κλειστή για αυτή την ημερομηνία.'
                    for booking in affected_bookings:
                        booking.status = 'cancelled'
                        booking.rejection_reason = (
                            f'Η επιχείρηση είναι κλειστή στις {closure_date.strftime("%d/%m/%Y")}. '
                            f'{day_reason}'
                        )
                        booking.save()

                        if booking.deposit_amount > 0:
                            process_refund(booking, refund_percentage=100)

                        send_business_closed_cancellation_email(booking, day_reason)
                        cancelled_count += 1

                    if cancelled_count:
                        messages.success(
                            request,
                            (
                                f'Το κλείσιμο για {closure_date.strftime("%d/%m/%Y")} προστέθηκε. '
                                f'Ακυρώθηκαν {cancelled_count} ραντεβού και οι πελάτες ενημερώθηκαν.'
                            ),
                        )
                    else:
                        messages.success(request, f'Το κλείσιμο για {closure_date.strftime("%d/%m/%Y")} προστέθηκε.')
                else:
                    messages.info(request, f'Υπάρχει ήδη κλείσιμο για {closure_date.strftime("%d/%m/%Y")}.')
            except ValueError:
                messages.error(request, 'Μη έγκυρη ημερομηνία.')
        return redirect('businesses:closures')

    context = {'business': business, 'closures': closures, 'today': today}
    return render(request, 'businesses/closures.html', context)


@login_required
@professional_required
def delete_business_closure(request, closure_id):
    """Remove a business temporary closure."""
    business = _get_accessible_business(request)
    closure = get_object_or_404(BusinessDayOff, id=closure_id, business=business)
    if request.method == 'POST':
        closure.delete()
        messages.success(request, 'Το κλείσιμο αφαιρέθηκε.')
    return redirect('businesses:closures')


# ── Business Reviews ────────────────────────────────────

@login_required
@professional_required
def owner_reviews(request):
    """Business owner view of their reviews."""
    business = _get_accessible_business(request)
    from reviews.models import Review

    if request.method == 'POST':
        review_id = request.POST.get('review_id', '').strip()
        reply_text = request.POST.get('business_reply', '').strip()

        review = get_object_or_404(Review, id=review_id, business=business)

        if review.business_reply:
            messages.info(request, 'Η κριτική έχει ήδη απαντηθεί.')
            return redirect('businesses:reviews')

        if not reply_text:
            messages.error(request, 'Συμπληρώστε την απάντηση πριν την υποβολή.')
            return redirect('businesses:reviews')

        review.business_reply = reply_text
        review.replied_at = timezone.now()
        review.save(update_fields=['business_reply', 'replied_at'])
        messages.success(request, 'Η απάντηση αποθηκεύτηκε.')
        return redirect('businesses:reviews')

    reviews = Review.objects.filter(business=business).select_related('customer', 'booking').order_by('-created_at')
    context = {
        'business': business,
        'reviews': reviews,
        'avg_rating': business.average_rating,
        'review_count': business.review_count,
    }
    return render(request, 'businesses/reviews.html', context)


# ── Absence Request Management ──────────────────────────────

@login_required
@professional_required
def absence_requests(request):
    """Business owner view of absence requests."""
    business = _get_accessible_business(request)

    # Get all absence requests for this business
    requests = SpecialDayOff.objects.filter(
        employee__business=business
    ).select_related('employee', 'reviewed_by').order_by('status', 'date')

    # Filter by status if provided
    status_filter = request.GET.get('status', '')
    if status_filter:
        requests = requests.filter(status=status_filter)

    paginator = Paginator(requests, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Count by status
    pending_count = SpecialDayOff.objects.filter(
        employee__business=business, status='pending'
    ).count()
    approved_count = SpecialDayOff.objects.filter(
        employee__business=business, status='approved'
    ).count()
    rejected_count = SpecialDayOff.objects.filter(
        employee__business=business, status='rejected'
    ).count()

    context = {
        'business': business,
        'requests': page_obj.object_list,
        'page_obj': page_obj,
        'status_filter': status_filter,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
    }
    return render(request, 'businesses/absence_requests.html', context)


@login_required
@professional_required
def approve_absence_request(request, request_id):
    """Approve an absence request; reassign impacted bookings when possible, otherwise cancel."""
    business = _get_accessible_business(request)
    absence_request = get_object_or_404(
        SpecialDayOff,
        id=request_id,
        employee__business=business,
        status='pending'
    )

    if request.method == 'POST':
        admin_response = request.POST.get('admin_response', '').strip()

        absence_request.status = 'approved'
        absence_request.admin_response = admin_response
        absence_request.reviewed_at = timezone.now()
        absence_request.reviewed_by = request.user
        absence_request.save()

        replacement = business.employees.filter(
            is_active=True,
        ).exclude(
            id=absence_request.employee_id,
        ).exclude(
            name='Σύστημα',
            title='Αυτόματη Ανάθεση',
        ).order_by('id').first()

        # Reassign/cancel active bookings for this employee on the approved day
        affected_bookings = Booking.objects.filter(
            employee=absence_request.employee,
            date=absence_request.date,
            status__in=('pending', 'confirmed'),
        )
        reassigned_count = 0
        cancelled_count = 0
        for booking in affected_bookings:
            old_status = booking.status
            if replacement:
                booking.employee = replacement
                booking.save(update_fields=['employee', 'updated_at'])
                BookingStatusLog.objects.create(
                    booking=booking,
                    old_status=old_status,
                    new_status=old_status,
                    changed_by=request.user,
                    notes=f'Επαναανάθεση λόγω έγκρισης άδειας #{absence_request.id} προς {replacement.name}',
                )
                send_employee_new_booking_email(booking)
                reassigned_count += 1
            else:
                booking.status = 'cancelled'
                booking.rejection_reason = (
                    f'Ο υπάλληλος {absence_request.employee.name} δεν είναι διαθέσιμος '
                    f'στις {absence_request.date.strftime("%d/%m/%Y")}. '
                )
                booking.save(update_fields=['status', 'rejection_reason', 'updated_at'])
                BookingStatusLog.objects.create(
                    booking=booking,
                    old_status=old_status,
                    new_status='cancelled',
                    changed_by=request.user,
                    notes=f'Αυτόματη ακύρωση λόγω έγκρισης άδειας #{absence_request.id}',
                )
                # Notify customer
                from notifications.utils import send_booking_rejected_email
                send_booking_rejected_email(booking)
                cancelled_count += 1

        # Send notification email to employee
        _send_absence_decision_email(absence_request, approved=True)

        if reassigned_count or cancelled_count:
            messages.success(
                request,
                f'Η άδεια του {absence_request.employee.name} εγκρίθηκε. '
                f'Επανανατέθηκαν {reassigned_count} και ακυρώθηκαν {cancelled_count} ραντεβού εκείνης της ημέρας.',
            )
        else:
            messages.success(request, f'Η άδεια του {absence_request.employee.name} εγκρίθηκε.')
        return redirect('businesses:absence_requests')

    # Count existing bookings to show in the confirmation page
    existing_bookings_count = Booking.objects.filter(
        employee=absence_request.employee,
        date=absence_request.date,
        status__in=('pending', 'confirmed'),
    ).count()

    context = {
        'business': business,
        'absence_request': absence_request,
        'action': 'approve',
        'existing_bookings_count': existing_bookings_count,
    }
    return render(request, 'businesses/absence_decision.html', context)


@login_required
@professional_required
def reject_absence_request(request, request_id):
    """Reject an absence request."""
    business = _get_accessible_business(request)
    absence_request = get_object_or_404(
        SpecialDayOff,
        id=request_id,
        employee__business=business,
        status='pending'
    )

    if request.method == 'POST':
        admin_response = request.POST.get('admin_response', '').strip()

        if not admin_response:
            messages.error(request, 'Παρακαλώ προσθέστε αιτιολογία για την απόρριψη.')
            context = {
                'business': business,
                'absence_request': absence_request,
                'action': 'reject'
            }
            return render(request, 'businesses/absence_decision.html', context)

        absence_request.status = 'rejected'
        absence_request.admin_response = admin_response
        absence_request.reviewed_at = timezone.now()
        absence_request.reviewed_by = request.user
        absence_request.save()

        # Send notification email to employee
        _send_absence_decision_email(absence_request, approved=False)

        messages.info(request, f'Η άδεια του {absence_request.employee.name} απορρίφθηκε.')
        return redirect('businesses:absence_requests')

    context = {
        'business': business,
        'absence_request': absence_request,
        'action': 'reject'
    }
    return render(request, 'businesses/absence_decision.html', context)


@login_required
@professional_required
def absence_request_detail(request, request_id):
    """Professional: view absence request details with chat."""
    business = _get_accessible_business(request)
    absence_request = get_object_or_404(
        SpecialDayOff,
        id=request_id,
        employee__business=business,
    )
    from .models import AbsenceRequestChat

    if request.method == 'POST':
        message_text = request.POST.get('message', '').strip()
        if message_text:
            AbsenceRequestChat.objects.create(
                absence_request=absence_request,
                sender=request.user,
                message=message_text,
            )
            # Mark employee messages as read when professional views/replies
            absence_request.chat_messages.filter(
                is_read=False
            ).exclude(sender=request.user).update(is_read=True)
        return redirect('businesses:absence_request_detail', request_id=request_id)

    # Mark unread messages as read when professional opens the detail
    absence_request.chat_messages.filter(
        is_read=False
    ).exclude(sender=request.user).update(is_read=True)

    chat_messages = absence_request.chat_messages.select_related('sender').order_by('created_at')
    context = {
        'business': business,
        'absence_request': absence_request,
        'chat_messages': chat_messages,
    }
    return render(request, 'businesses/absence_request_detail.html', context)


def _send_absence_decision_email(absence_request, approved):
    """Send email notification to employee about absence decision."""
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.conf import settings as django_settings

    employee = absence_request.employee
    business = employee.business

    if not employee.user or not employee.user.email:
        return  # No email to send to

    if approved:
        subject = f'Η άδεια σας εγκρίθηκε - {business.name}'
        template = 'accounts/absence_approved_email.html'
    else:
        subject = f'Η άδεια σας απορρίφθηκε - {business.name}'
        template = 'accounts/absence_rejected_email.html'

    context = {
        'absence_request': absence_request,
        'employee': employee,
        'business': business,
        'approved': approved,
    }

    # Plain text version
    status_text = 'εγκρίθηκε' if approved else 'απορρίφθηκε'
    plain_message = f"""
Η άδεια σας {status_text}

Ημερομηνία: {absence_request.date.strftime('%d/%m/%Y')}
Λόγος: {absence_request.reason}
Κατάσταση: {"Εγκρίθηκε" if approved else "Απορρίφθηκε"}

{'Απάντηση εργοδότη: ' + absence_request.admin_response if absence_request.admin_response else ''}

Με εκτίμηση,
{business.name}
"""

    try:
        html_message = render_to_string(template, context)
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[employee.user.email],
            html_message=html_message,
            fail_silently=True,
        )
    except Exception:
        pass  # Silently fail email notifications


# ── Notification Contacts Management ───────────────────────

@login_required
@professional_required
def notification_contacts(request):
    """Manage additional notification contacts for the business."""
    business = _get_accessible_business(request)
    from .models import NotificationContact

    contacts = NotificationContact.objects.filter(
        business=business
    ).order_by('contact_type', 'label')

    context = {
        'business': business,
        'contacts': contacts,
    }
    return render(request, 'businesses/notification_contacts.html', context)


@login_required
@professional_required
def add_notification_contact(request):
    """Add a new notification contact."""
    business = _get_accessible_business(request)
    from .models import NotificationContact

    if request.method == 'POST':
        contact_type = request.POST.get('contact_type')
        value = request.POST.get('value', '').strip()
        label = request.POST.get('label', '').strip()

        if not value:
            messages.error(request, 'Παρακαλώ εισάγετε την τιμή επαφής.')
            return redirect('businesses:notification_contacts')

        # Validate email
        if contact_type == 'email':
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError
            try:
                validate_email(value)
            except ValidationError:
                messages.error(request, 'Παρακαλώ εισάγετε έγκυρο email.')
                return redirect('businesses:notification_contacts')

        # Validate phone
        elif contact_type == 'phone':
            import re
            if not re.match(r'^[\d\s\+\-\(\)]+$', value):
                messages.error(request, 'Παρακαλώ εισάγετε έγκυρο τηλέφωνο.')
                return redirect('businesses:notification_contacts')

        NotificationContact.objects.create(
            business=business,
            contact_type=contact_type,
            value=value,
            label=label
        )

        contact_type_display = 'Email' if contact_type == 'email' else 'Τηλέφωνο'
        messages.success(request, f'Η επαφή {contact_type_display} προστέθηκε.')

    return redirect('businesses:notification_contacts')


@login_required
@professional_required
def delete_notification_contact(request, contact_id):
    """Delete a notification contact."""
    business = _get_accessible_business(request)
    from .models import NotificationContact

    contact = get_object_or_404(
        NotificationContact,
        id=contact_id,
        business=business
    )

    if request.method == 'POST':
        contact.delete()
        messages.success(request, 'Η επαφή διαγράφηκε.')

    return redirect('businesses:notification_contacts')

