from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_exempt
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from erantevou.decorators import cross_business_api, cross_business_view
from datetime import datetime, timedelta
import secrets
from businesses.models import Business, Employee, Service
from .models import Booking, BookingStatusLog
from .utils import get_available_slots, get_available_dates
from notifications.models import SystemSettings
from notifications.utils import send_employee_new_booking_email
from businesses.customer_utils import upsert_business_customer_from_booking
from .guest_otp_utils import generate_guest_booking_otp, send_guest_booking_otps

GUEST_BOOKING_PENDING_SESSION_KEY = 'guest_booking_pending'
GUEST_BOOKING_OTP_SESSION_KEY = 'guest_booking_otp_state'


def _guest_booking_payload(
    business_slug,
    service_id,
    employee_id,
    capacity_mode,
    date_str,
    start_time_str,
    guest_name,
    guest_phone,
    guest_email,
    guest_contact_preference,
    notes,
):
    return {
        'business_slug': business_slug,
        'service_id': str(service_id or ''),
        'employee_id': str(employee_id or ''),
        'capacity_mode': '1' if capacity_mode else '0',
        'date': date_str,
        'start_time': start_time_str,
        'guest_name': guest_name,
        'guest_phone': guest_phone,
        'guest_email': guest_email,
        'guest_contact_preference': guest_contact_preference,
        'notes': notes,
    }


def _render_guest_booking_verification(request, business, payload):
    service = get_object_or_404(Service, id=payload['service_id'], business=business)
    employee = None
    if payload['employee_id']:
        employee = get_object_or_404(Employee, id=payload['employee_id'], business=business)
    booking_date = datetime.strptime(payload['date'], '%Y-%m-%d').date()
    start_time = datetime.strptime(payload['start_time'], '%H:%M').time()
    end_time = (datetime.combine(booking_date, start_time) + timedelta(minutes=service.duration_minutes)).time()
    deposit_amount = 0
    if business.requires_deposit:
        deposit_amount = round(float(service.price) * business.deposit_percentage / 100, 2)

    sms_enabled = SystemSettings.get_solo().sms_enabled
    guest_contact_preference = (payload.get('guest_contact_preference') or 'both').strip()
    require_email_otp = guest_contact_preference in ['email', 'both']
    require_sms_otp = sms_enabled and guest_contact_preference in ['phone', 'both']

    return render(request, 'bookings/guest_booking_verify.html', {
        'business': business,
        'service': service,
        'employee': employee,
        'date': booking_date,
        'start_time': start_time,
        'end_time': end_time,
        'deposit_amount': deposit_amount,
        'payload': payload,
        'sms_enabled': sms_enabled,
        'require_email_otp': require_email_otp,
        'require_sms_otp': require_sms_otp,
    })


def _is_auto_placeholder_employee(employee):
    """Return True when employee row is the virtual automatic-assignment placeholder."""
    if not employee:
        return False
    normalized_name = (employee.name or '').strip().lower()
    normalized_title = (employee.title or '').strip().lower()
    auto_names = {'system', 'σύστημα', 'automatic selection'}
    auto_titles = {'automatic assignment', 'αυτόματη ανάθεση'}
    return normalized_name in auto_names or normalized_title in auto_titles


@cross_business_view
def booking_page(request, business_slug):
    """
    Public booking page — Step 1: Choose service & employee.
    Accessible at /b/<slug>/
    """
    business = get_object_or_404(
        Business, slug=business_slug, is_active=True, is_approved=True
    )
    services = business.services.filter(is_active=True)
    employees = business.employees.filter(is_active=True).exclude(
        Q(name__iexact='system', title__iexact='automatic assignment') |
        Q(name='Σύστημα', title='Αυτόματη Ανάθεση')
    )

    context = {
        'business': business,
        'services': services,
        'employees': employees,
        'sms_enabled': SystemSettings.get_solo().sms_enabled,
        'hide_sidebar': True,
    }
    return render(request, 'bookings/booking_page.html', context)


@cross_business_api
def get_slots_api(request, business_slug):
    """
    AJAX API: get available slots for a date/employee/service combo.
    GET params: employee_id, service_id, date (YYYY-MM-DD)
    Supports capacity-based booking when employee_id is empty.
    """
    business = get_object_or_404(Business, slug=business_slug, is_active=True)
    employee_id = (request.GET.get('employee_id') or '').strip()
    if employee_id.lower() == 'auto':
        employee_id = ''
    service_id = request.GET.get('service_id')
    date_str = request.GET.get('date')

    if not all([service_id, date_str]):
        return JsonResponse({'error': 'Missing parameters'}, status=400)

    service = get_object_or_404(Service, id=service_id, business=business)

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date'}, status=400)

    # Use capacity-based or employee-based slots
    if employee_id:
        employee = get_object_or_404(Employee, id=employee_id, business=business)
        if _is_auto_placeholder_employee(employee):
            from .utils import get_available_slots_capacity
            slots = get_available_slots_capacity(business, service, target_date)
        else:
            from .utils import get_available_slots
            slots = get_available_slots(employee, service, target_date)
    else:
        from .utils import get_available_slots_capacity
        slots = get_available_slots_capacity(business, service, target_date)
    
    # Filter out past slots when the requested date is today
    today = timezone.now().date()
    if target_date == today:
        now_time = timezone.localtime(timezone.now()).time()
        slots = [s for s in slots if s['start'] >= now_time]

    # Strip non-serializable time objects for JSON
    safe_slots = [
        {k: v for k, v in s.items() if k not in ('start', 'end')}
        for s in slots
    ]
    return JsonResponse({'slots': safe_slots})


@cross_business_api
def get_dates_api(request, business_slug):
    """
    AJAX API: get available dates for employee/service.
    GET params: employee_id, service_id
    Supports capacity-based booking when employee_id is empty.
    """
    business = get_object_or_404(Business, slug=business_slug, is_active=True)
    employee_id = (request.GET.get('employee_id') or '').strip()
    if employee_id.lower() == 'auto':
        employee_id = ''
    service_id = request.GET.get('service_id')

    if not service_id:
        return JsonResponse({'error': 'Missing service_id'}, status=400)

    service = get_object_or_404(Service, id=service_id, business=business)

    start_date = timezone.now().date() + timedelta(days=1)  # Start from tomorrow
    
    # Use capacity-based or employee-based dates
    if employee_id:
        employee = get_object_or_404(Employee, id=employee_id, business=business)
        if _is_auto_placeholder_employee(employee):
            from .utils import get_available_dates_capacity
            dates = get_available_dates_capacity(business, service, start_date)
        else:
            from .utils import get_available_dates
            dates = get_available_dates(employee, service, start_date)
    else:
        from .utils import get_available_dates_capacity
        dates = get_available_dates_capacity(business, service, start_date)
    
    # Strip non-serializable date objects for JSON
    safe_dates = [
        {k: v for k, v in d.items() if k != 'date'}
        for d in dates
    ]
    return JsonResponse({'dates': safe_dates})


def booking_confirm(request, business_slug):
    """
    Step 2: Confirm booking details, enter notes.
    POST with employee_id, service_id, date, start_time.
    """
    business = get_object_or_404(Business, slug=business_slug, is_active=True)

    if request.method != 'POST':
        return redirect('public_booking:booking_page', business_slug=business_slug)

    employee_id = request.POST.get('employee_id')
    service_id = request.POST.get('service_id')
    date_str = request.POST.get('date')
    start_time_str = request.POST.get('start_time')

    employee = get_object_or_404(Employee, id=employee_id, business=business) if employee_id else None
    service = get_object_or_404(Service, id=service_id, business=business)
    booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    start_time = datetime.strptime(start_time_str, '%H:%M').time()
    end_time = (datetime.combine(booking_date, start_time) +
                timedelta(minutes=service.duration_minutes)).time()

    # Calculate deposit
    deposit_amount = 0
    if business.requires_deposit:
        deposit_amount = round(float(service.price) * business.deposit_percentage / 100, 2)

    context = {
        'business': business,
        'employee': employee,
        'service': service,
        'date': booking_date,
        'date_str': date_str,
        'start_time': start_time,
        'start_time_str': start_time_str,
        'end_time': end_time,
        'deposit_amount': deposit_amount,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
    }
    return render(request, 'bookings/booking_confirm.html', context)


@csrf_exempt
@xframe_options_exempt
def booking_create(request, business_slug):
    """
    Step 3: Actually create the booking (final submit).
    If deposit required, redirect to Stripe first.
    Supports both authenticated users and guest bookings.
    """
    if request.method != 'POST':
        return redirect('public_booking:booking_page', business_slug=business_slug)

    business = get_object_or_404(Business, slug=business_slug, is_active=True)
    
    # Get employee (or auto-assign if not provided, or use capacity-based booking)
    employee_id = (request.POST.get('employee_id') or '').strip()
    if employee_id.lower() == 'auto':
        employee_id = ''
    use_capacity_mode = False  # track if we should use capacity-based checks
    if employee_id:
        employee = get_object_or_404(Employee, id=employee_id, business=business)
        if _is_auto_placeholder_employee(employee):
            employee_id = ''
            use_capacity_mode = True
            employee = None
    else:
        use_capacity_mode = True

    if use_capacity_mode:
        # Try to get first available real employee (exclude virtual auto-assignment placeholder)
        employee = business.employees.filter(is_active=True).exclude(
            Q(name='Σύστημα', title='Αυτόματη Ανάθεση') |
            Q(name__iexact='system', title__iexact='automatic assignment')
        ).first()
        if not employee:
            # No employees - create a virtual "System" employee only as FK placeholder
            employee, created = Employee.objects.get_or_create(
                business=business,
                name='Σύστημα',
                title='Αυτόματη Ανάθεση',
                defaults={
                    'is_active': True,
                }
            )
    
    service = get_object_or_404(Service, id=request.POST.get('service_id'), business=business)

    if service.duration_minutes < 5:
        messages.error(request, 'Η υπηρεσία έχει μη έγκυρη διάρκεια. Επικοινωνήστε με την επιχείρηση.')
        return redirect('public_booking:booking_page', business_slug=business_slug)

    date_str = request.POST.get('date')
    start_time_str = request.POST.get('start_time')
    notes = request.POST.get('notes', '').strip()
    
    # Handle guest bookings
    guest_name = request.POST.get('guest_name', '').strip()
    guest_phone = request.POST.get('guest_phone', '').strip()
    guest_email = request.POST.get('guest_email', '').strip()
    guest_contact_preference = request.POST.get('guest_contact_preference', 'both').strip()
    customer_contact_preference = request.POST.get('customer_contact_preference', 'both').strip()
    sms_enabled = SystemSettings.get_solo().sms_enabled

    # Validate guest fields by selected contact preference.
    if not request.user.is_authenticated:
        if guest_contact_preference not in ['email', 'phone', 'both']:
            guest_contact_preference = 'both'

        if not guest_name:
            messages.error(request, 'Παρακαλώ συμπληρώστε το όνομά σας.')
            return redirect('public_booking:booking_page', business_slug=business_slug)

        if sms_enabled:
            if guest_contact_preference in ['email', 'both'] and not guest_email:
                messages.error(request, 'Παρακαλώ συμπληρώστε το email σας.')
                return redirect('public_booking:booking_page', business_slug=business_slug)
            if guest_contact_preference in ['phone', 'both'] and not guest_phone:
                messages.error(request, 'Παρακαλώ συμπληρώστε το τηλέφωνό σας.')
                return redirect('public_booking:booking_page', business_slug=business_slug)
            if guest_contact_preference in ['phone', 'both'] and (not guest_phone.isdigit() or len(guest_phone) != 10):
                messages.error(request, 'Το τηλέφωνο πρέπει να είναι 10 ψηφία.')
                return redirect('public_booking:booking_page', business_slug=business_slug)
        else:
            if not guest_email:
                messages.error(request, 'Παρακαλώ συμπληρώστε το email σας.')
                return redirect('public_booking:booking_page', business_slug=business_slug)
            guest_phone = ''
            guest_contact_preference = 'email'
    else:
        if customer_contact_preference not in ['email', 'phone', 'both']:
            customer_contact_preference = 'both'
        if not sms_enabled and customer_contact_preference in ['phone', 'both']:
            customer_contact_preference = 'email'

    booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    start_time = datetime.strptime(start_time_str, '%H:%M').time()
    end_time = (datetime.combine(booking_date, start_time) +
                timedelta(minutes=service.duration_minutes)).time()

    # Check if business is closed on this date
    from businesses.models import BusinessDayOff
    if BusinessDayOff.objects.filter(business=business, date=booking_date).exists():
        messages.error(request, f'Η επιχείρηση είναι κλειστή στις {booking_date.strftime("%d/%m/%Y")}. Παρακαλώ επιλέξτε άλλη ημερομηνία.')
        return redirect('public_booking:booking_page', business_slug=business_slug)

    with transaction.atomic():
        # Acquire row-level lock on existing bookings for the same slot to prevent double-booking
        Booking.objects.select_for_update().filter(
            employee=employee, date=booking_date
        ).values('id')  # evaluates the queryset, acquiring the lock

        # Re-verify slot availability under the lock
        if use_capacity_mode:
            from .utils import get_available_slots_capacity
            available = get_available_slots_capacity(business, service, booking_date)
        else:
            from .utils import get_available_slots
            available = get_available_slots(employee, service, booking_date)
        slot_available = any(
            s['start'] == start_time for s in available
        )
        if not slot_available:
            messages.error(request, 'Αυτή η ώρα δεν είναι πλέον διαθέσιμη. Παρακαλώ επιλέξτε άλλη.')
            return redirect('public_booking:booking_page', business_slug=business_slug)

        if not request.user.is_authenticated:
            payload = _guest_booking_payload(
                business_slug=business_slug,
                service_id=service.id,
                employee_id=employee_id,
                capacity_mode=use_capacity_mode,
                date_str=date_str,
                start_time_str=start_time_str,
                guest_name=guest_name,
                guest_phone=guest_phone,
                guest_email=guest_email,
                guest_contact_preference=guest_contact_preference,
                notes=notes,
            )

            if request.POST.get('guest_otp_submission') == '1':
                pending_payload = request.session.get(GUEST_BOOKING_PENDING_SESSION_KEY)
                otp_state = request.session.get(GUEST_BOOKING_OTP_SESSION_KEY, {})
                email_otp_entered = (request.POST.get('guest_email_otp') or '').strip()
                sms_otp_entered = (request.POST.get('guest_sms_otp') or '').strip()
                verify_capacity_mode = (request.POST.get('capacity_mode') or '').strip() == '1'
                require_email_otp = bool(otp_state.get('require_email_otp'))
                require_sms_otp = bool(otp_state.get('require_sms_otp'))

                if not pending_payload or pending_payload != payload:
                    messages.error(request, 'Η συνεδρία επιβεβαίωσης έληξε ή τα στοιχεία της κράτησης άλλαξαν. Ξεκινήστε ξανά.')
                    return redirect('public_booking:booking_page', business_slug=business_slug)

                if not otp_state:
                    messages.error(request, 'Δεν βρέθηκαν κωδικοί OTP. Ξεκινήστε ξανά.')
                    return redirect('public_booking:booking_page', business_slug=business_slug)

                if timezone.now().timestamp() > otp_state.get('expires_at', 0):
                    request.session.pop(GUEST_BOOKING_PENDING_SESSION_KEY, None)
                    request.session.pop(GUEST_BOOKING_OTP_SESSION_KEY, None)
                    messages.error(request, 'Οι κωδικοί OTP έληξαν. Ξεκινήστε ξανά.')
                    return redirect('public_booking:booking_page', business_slug=business_slug)

                if verify_capacity_mode:
                    use_capacity_mode = True
                    employee = business.employees.filter(is_active=True).exclude(
                        Q(name='Σύστημα', title='Αυτόματη Ανάθεση') |
                        Q(name__iexact='system', title__iexact='automatic assignment')
                    ).first()
                    if not employee:
                        employee, created = Employee.objects.get_or_create(
                            business=business,
                            name='Σύστημα',
                            title='Αυτόματη Ανάθεση',
                            defaults={
                                'is_active': True,
                            }
                        )

                if require_email_otp and email_otp_entered != otp_state.get('email_otp'):
                    messages.error(request, 'Ο email OTP δεν είναι σωστός.')
                    return _render_guest_booking_verification(request, business, payload)

                if require_sms_otp and sms_otp_entered != otp_state.get('sms_otp'):
                    messages.error(request, 'Ο SMS OTP δεν είναι σωστός.')
                    return _render_guest_booking_verification(request, business, payload)

                request.session.pop(GUEST_BOOKING_PENDING_SESSION_KEY, None)
                request.session.pop(GUEST_BOOKING_OTP_SESSION_KEY, None)
            else:
                require_email_otp = guest_contact_preference in ['email', 'both']
                require_sms_otp = sms_enabled and guest_contact_preference in ['phone', 'both']

                email_otp = generate_guest_booking_otp() if require_email_otp else ''
                sms_otp = generate_guest_booking_otp() if require_sms_otp else ''
                request.session[GUEST_BOOKING_PENDING_SESSION_KEY] = payload
                request.session[GUEST_BOOKING_OTP_SESSION_KEY] = {
                    'email_otp': email_otp,
                    'sms_otp': sms_otp,
                    'require_email_otp': require_email_otp,
                    'require_sms_otp': require_sms_otp,
                    'expires_at': (timezone.now() + timedelta(minutes=10)).timestamp(),
                }

                sent = send_guest_booking_otps(
                    guest_email,
                    guest_phone,
                    business.name,
                    email_otp,
                    sms_otp,
                    send_email=require_email_otp,
                    send_sms=require_sms_otp,
                )
                if not sent:
                    messages.error(
                        request,
                        'Στείλαμε την κράτηση στην οθόνη επιβεβαίωσης, αλλά η αποστολή των OTP κωδικών δεν ολοκληρώθηκε πλήρως. '
                        'Ελέγξτε email/SMS ή δοκιμάστε ξανά αν δεν λάβατε τους κωδικούς.',
                    )

                return _render_guest_booking_verification(request, business, payload)

        # Determine status
        if business.auto_confirm:
            status = 'confirmed'
        else:
            status = 'pending'

        # Calculate deposit
        deposit_amount = 0
        payment_status = 'not_required'
        if business.requires_deposit:
            deposit_amount = round(float(service.price) * business.deposit_percentage / 100, 2)
            payment_status = 'pending'

        # Generate access token for guest bookings
        guest_access_token = None
        if not request.user.is_authenticated:
            guest_access_token = secrets.token_urlsafe(32)

        customer_phone = ''
        if request.user.is_authenticated and sms_enabled:
            # Use phone from form if provided, otherwise use profile phone
            customer_phone = request.POST.get('customer_phone', '').strip() or (request.user.phone or '')

        booking = Booking.objects.create(
            business=business,
            employee=employee,
            service=service,
            customer=request.user if request.user.is_authenticated else None,
            guest_name=guest_name if not request.user.is_authenticated else '',
            guest_phone=guest_phone if not request.user.is_authenticated and sms_enabled else '',
            guest_email=guest_email if not request.user.is_authenticated else '',
            guest_access_token=guest_access_token,
            guest_contact_preference=guest_contact_preference if not request.user.is_authenticated else '',
            customer_contact_preference=customer_contact_preference if request.user.is_authenticated else '',
            customer_phone=customer_phone if request.user.is_authenticated else '',
            date=booking_date,
            start_time=start_time,
            end_time=end_time,
            price_at_booking=service.price,  # locked at booking time
            status=status,
            payment_status=payment_status,
            deposit_amount=deposit_amount,
            notes=notes,
        )

        # Log status
        BookingStatusLog.objects.create(
            booking=booking,
            old_status='',
            new_status=status,
            changed_by=request.user if request.user.is_authenticated else None,
            notes='Δημιουργία ραντεβού',
        )

        upsert_business_customer_from_booking(booking)

    # Notify assigned employee for the new booking (email).
    send_employee_new_booking_email(booking)

    # If deposit required, redirect to payment
    if business.requires_deposit and deposit_amount > 0:
        return redirect('payments:create_checkout', booking_id=booking.id)

    # Send confirmation SMS (only if preference is phone or both)
    if not request.user.is_authenticated:
        # For guest bookings, respect their contact preference
        should_send_sms = sms_enabled and guest_contact_preference in ['phone', 'both']
        should_send_email = guest_contact_preference in ['email', 'both']

        if should_send_sms and booking.status == 'confirmed':
            from notifications.utils import send_booking_confirmation_sms
            send_booking_confirmation_sms(booking)

        # Send confirmation email for guest bookings (only if preference is email or both)
        if should_send_email and guest_email:
            from notifications.utils import send_guest_booking_confirmation_email
            send_guest_booking_confirmation_email(booking)
    else:
        # For authenticated users, respect their contact preference.
        should_send_sms = sms_enabled and customer_contact_preference in ['phone', 'both']
        should_send_email = customer_contact_preference in ['email', 'both']

        if booking.status == 'confirmed':
            if should_send_sms:
                from notifications.utils import send_booking_confirmation_sms
                send_booking_confirmation_sms(booking)
            if should_send_email:
                from notifications.utils import send_customer_booking_confirmation_email
                send_customer_booking_confirmation_email(booking)

    messages.success(request, 'Το ραντεβού σας καταχωρήθηκε επιτυχώς!')
    # Pass from_widget flag so success page renders minimal (no sidebar)
    from_widget = request.POST.get('from_widget', '')
    redirect_url = f"/b/{business_slug}/success/{booking.id}/"
    if from_widget:
        redirect_url += '?widget=1'
    return redirect(redirect_url)


@xframe_options_exempt
def booking_success(request, business_slug, booking_id):
    """Success page after booking is created."""
    booking = get_object_or_404(Booking, id=booking_id, business__slug=business_slug)

    # Access control: owner, or guest booking (no customer FK)
    if booking.customer and request.user.is_authenticated and booking.customer != request.user:
        from django.http import Http404
        raise Http404("Booking not found")
    
    is_widget = request.GET.get('widget') == '1'
    return render(request, 'bookings/booking_success.html', {
        'booking': booking,
        'business': booking.business,
        'hide_sidebar': True,
        'is_widget': is_widget,
    })


@cross_business_api
def check_duplicate_booking(request, business_slug):
    """
    AJAX: check if the same email or phone already has an active booking
    at the requested date and start_time for the same business.
    Returns JSON { "duplicate": true/false }.
    """
    if request.method != 'POST':
        return JsonResponse({'duplicate': False})

    business = get_object_or_404(Business, slug=business_slug, is_active=True)
    guest_email = request.POST.get('guest_email', '').strip()
    guest_phone = request.POST.get('guest_phone', '').strip()
    date_str = request.POST.get('date', '').strip()
    start_time_str = request.POST.get('start_time', '').strip()

    if not date_str or not start_time_str:
        return JsonResponse({'duplicate': False})

    try:
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
    except ValueError:
        return JsonResponse({'duplicate': False})

    base_q = Q(
        business=business,
        date=booking_date,
        start_time=start_time,
        status__in=['pending', 'confirmed'],
    )

    duplicate = False
    if guest_email:
        duplicate = Booking.objects.filter(base_q, guest_email__iexact=guest_email).exists()
    if not duplicate and guest_phone:
        duplicate = Booking.objects.filter(base_q, guest_phone=guest_phone).exists()
    if not duplicate and request.user.is_authenticated:
        duplicate = Booking.objects.filter(base_q, customer=request.user).exists()

    return JsonResponse({'duplicate': duplicate})


@login_required
def cancel_booking(request, booking_id):
    """Customer cancels their booking."""
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)

    if not booking.is_cancellable:
        messages.error(request, 'Αυτό το ραντεβού δεν μπορεί να ακυρωθεί.')
        return redirect('accounts:my_bookings')

    if request.method == 'POST':
        old_status = booking.status
        refund_pct = booking.cancellation_refund_percentage

        booking.status = 'cancelled'
        booking.save()

        BookingStatusLog.objects.create(
            booking=booking,
            old_status=old_status,
            new_status='cancelled',
            changed_by=request.user,
            notes=f'Ακύρωση από πελάτη. Επιστροφή: {refund_pct}%',
        )

        # Process refund if deposit was paid
        if booking.deposit_amount > 0 and booking.payment_status == 'paid':
            from payments.utils import process_refund
            process_refund(booking, refund_percentage=refund_pct)

        from notifications.utils import send_business_booking_cancelled_email
        send_business_booking_cancelled_email(booking, cancelled_by='customer')

        messages.info(request, f'Το ραντεβού ακυρώθηκε. Επιστροφή: {refund_pct}%.')
        return redirect('accounts:my_bookings')

    context = {
        'booking': booking,
        'refund_percentage': booking.cancellation_refund_percentage,
    }
    return render(request, 'bookings/cancel_confirm.html', context)


@login_required
def reschedule_booking(request, booking_id):
    """Customer reschedules their booking before the service deadline."""
    # Allow customers to reschedule their own bookings
    try:
        booking = Booking.objects.get(id=booking_id, customer=request.user)
    except Booking.DoesNotExist:
        messages.error(request, 'Το ραντεβού δεν βρέθηκε ή δεν έχετε πρόσβαση.')
        return redirect('accounts:my_bookings')

    if booking.status not in ('pending', 'confirmed'):
        messages.error(request, 'Αυτό το ραντεβού δεν μπορεί να επαναπρογραμματιστεί.')
        return redirect('accounts:my_bookings')

    if not booking.is_reschedulable:
        messages.error(request, 'Έχει λήξει η προθεσμία επαναπρογραμματισμού για αυτή την υπηρεσία.')
        return redirect('accounts:my_bookings')

    selected_date_str = (request.GET.get('date') or '').strip()
    selected_date = booking.date
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = booking.date

    today = timezone.now().date()
    if selected_date < today:
        selected_date = today

    use_capacity_mode = _is_auto_placeholder_employee(booking.employee)
    if use_capacity_mode:
        from .utils import get_available_dates_capacity, get_available_slots_capacity
        available_dates = get_available_dates_capacity(booking.business, booking.service, today, num_days=45)
        available_slots = get_available_slots_capacity(booking.business, booking.service, selected_date)
    else:
        from .utils import get_available_dates
        available_dates = get_available_dates(booking.employee, booking.service, today, num_days=45)
        available_slots = get_available_slots(booking.employee, booking.service, selected_date)

    if request.method == 'POST':
        date_str = (request.POST.get('date') or '').strip()
        start_time_str = (request.POST.get('start_time') or '').strip()

        if not booking.is_reschedulable:
            messages.error(request, 'Η προθεσμία επαναπρογραμματισμού έληξε.')
            return redirect('accounts:my_bookings')

        try:
            new_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            new_start_time = datetime.strptime(start_time_str, '%H:%M').time()
        except ValueError:
            messages.error(request, 'Μη έγκυρη ημερομηνία ή ώρα.')
            return redirect('bookings:reschedule_booking', booking_id=booking.id)

        if new_date < today:
            messages.error(request, 'Δεν μπορείτε να επιλέξετε παρελθοντική ημερομηνία.')
            return redirect('bookings:reschedule_booking', booking_id=booking.id)

        if new_date == booking.date and new_start_time == booking.start_time:
            messages.info(request, 'Επιλέξατε την ίδια ώρα. Δεν έγινε αλλαγή.')
            return redirect('accounts:my_bookings')

        if use_capacity_mode:
            from .utils import get_available_slots_capacity
            fresh_slots = get_available_slots_capacity(booking.business, booking.service, new_date)
        else:
            fresh_slots = get_available_slots(booking.employee, booking.service, new_date)

        slot_available = any(slot['start'] == new_start_time for slot in fresh_slots)
        if not slot_available:
            messages.error(request, 'Η ώρα που επιλέξατε δεν είναι διαθέσιμη.')
            return redirect(f"{reverse('bookings:reschedule_booking', args=[booking.id])}?date={new_date.strftime('%Y-%m-%d')}")

        new_end_time = (datetime.combine(new_date, new_start_time) + timedelta(minutes=booking.service.duration_minutes)).time()

        old_date = booking.date
        old_start = booking.start_time
        old_end = booking.end_time
        booking.date = new_date
        booking.start_time = new_start_time
        booking.end_time = new_end_time
        booking.save(update_fields=['date', 'start_time', 'end_time', 'updated_at'])

        BookingStatusLog.objects.create(
            booking=booking,
            old_status=booking.status,
            new_status=booking.status,
            changed_by=request.user,
            notes=(
                f'Επαναπρογραμματισμός από πελάτη: '
                f'{old_date.strftime("%d/%m/%Y")} {old_start.strftime("%H:%M")}-{old_end.strftime("%H:%M")} '
                f'→ {new_date.strftime("%d/%m/%Y")} {new_start_time.strftime("%H:%M")}-{new_end_time.strftime("%H:%M")}'
            ),
        )

        send_employee_new_booking_email(booking)
        messages.success(request, 'Το ραντεβού επαναπρογραμματίστηκε επιτυχώς.')
        return redirect('accounts:my_bookings')

    context = {
        'booking': booking,
        'available_dates': available_dates,
        'available_slots': available_slots,
        'selected_date': selected_date,
        'hide_sidebar': request.session.get('customer_mode', False),
    }
    return render(request, 'bookings/reschedule_booking.html', context)


@xframe_options_exempt
def guest_booking_view(request, business_slug, access_token):
    """
    View booking details for guests using their unique access token.
    Accessible at /b/<slug>/booking/<token>/
    """
    business = get_object_or_404(Business, slug=business_slug, is_active=True)
    booking = get_object_or_404(
        Booking,
        business=business,
        guest_access_token=access_token,
        customer__isnull=True,  # Ensure it's a guest booking
    )

    context = {
        'booking': booking,
        'business': business,
        'hide_sidebar': True,
    }
    return render(request, 'bookings/guest_booking_detail.html', context)


@xframe_options_exempt
def guest_cancel_booking(request, business_slug, access_token):
    """Allow guests to cancel their booking from the tokenized guest page."""
    if request.method != 'POST':
        return redirect('public_booking:guest_booking_view', business_slug=business_slug, access_token=access_token)

    business = get_object_or_404(Business, slug=business_slug, is_active=True)
    booking = get_object_or_404(
        Booking,
        business=business,
        guest_access_token=access_token,
        customer__isnull=True,
    )

    if not booking.is_cancellable:
        messages.error(request, 'Αυτό το ραντεβού δεν μπορεί να ακυρωθεί πλέον.')
        return redirect('public_booking:guest_booking_view', business_slug=business_slug, access_token=access_token)

    old_status = booking.status
    refund_pct = booking.cancellation_refund_percentage
    booking.status = 'cancelled'
    booking.save(update_fields=['status', 'updated_at'])

    BookingStatusLog.objects.create(
        booking=booking,
        old_status=old_status,
        new_status='cancelled',
        changed_by=None,
        notes=f'Ακύρωση από επισκέπτη. Επιστροφή: {refund_pct}%',
    )

    if booking.deposit_amount > 0 and booking.payment_status == 'paid':
        from payments.utils import process_refund
        process_refund(booking, refund_percentage=refund_pct)

    from notifications.utils import send_business_booking_cancelled_email
    send_business_booking_cancelled_email(booking, cancelled_by='guest')

    messages.success(request, f'Το ραντεβού ακυρώθηκε. Επιστροφή: {refund_pct}%.')
    return redirect('public_booking:guest_booking_view', business_slug=business_slug, access_token=access_token)


def guest_short_link(request, guest_code):
    """Resolve a short temporary guest URL to the full booking access token page."""
    parts = (guest_code or '').split('-', 1)
    if len(parts) != 2:
        from django.http import Http404
        raise Http404('Invalid guest link')

    booking_part = parts[0].strip().lower()
    token_prefix = parts[1].strip()

    try:
        booking_id = int(booking_part, 16)
    except ValueError:
        from django.http import Http404
        raise Http404('Invalid guest link')

    booking = get_object_or_404(
        Booking,
        id=booking_id,
        customer__isnull=True,
    )

    if not booking.guest_access_token or not booking.guest_access_token.startswith(token_prefix):
        from django.http import Http404
        raise Http404('Invalid guest link')

    # Temporary window for short links.
    if timezone.now() > booking.created_at + timedelta(days=30):
        from django.http import Http404
        raise Http404('Guest link expired')

    return redirect(
        'public_booking:guest_booking_view',
        business_slug=booking.business.slug,
        access_token=booking.guest_access_token,
    )
