from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from django.core.management import call_command
from django.urls import reverse
from urllib.parse import urlencode
import subprocess
import json
from .models import CustomUser
from .otp_utils import send_otp_email, resend_otp, send_professional_registration_otps
from businesses.models import Business, BusinessDeletionRequest
from notifications.models import News
import logging

logger = logging.getLogger(__name__)


def login_view(request):
    """Custom login view."""
    if request.user.is_authenticated:
        return redirect('accounts:redirect_after_login')

    if request.method == 'POST':
        login_identifier = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        remember = request.POST.get('remember_me')

        user = None

        # Allow authentication with either username or email address.
        if login_identifier:
            email_candidates = CustomUser.objects.filter(
                email__iexact=login_identifier
            ).values_list('username', flat=True)

            for candidate_username in email_candidates:
                user = authenticate(request, username=candidate_username, password=password)
                if user is not None:
                    break

            if user is None:
                user = authenticate(request, username=login_identifier, password=password)

        if user is not None:
            auth_login(request, user)
            if remember:
                request.session.set_expiry(settings.SESSION_COOKIE_AGE)
            else:
                request.session.set_expiry(0)
            next_url = request.GET.get('next', '')
            return redirect(next_url if next_url else 'accounts:redirect_after_login')
        else:
            # Inactive unverified customers cannot authenticate yet.
            # If credentials are correct, guide them back to OTP verification and resend a code.
            unverified_user = CustomUser.objects.filter(
                Q(username=login_identifier) | Q(email__iexact=login_identifier),
                role='customer',
                is_email_verified=False,
            ).first()

            if unverified_user and unverified_user.check_password(password):
                request.session['pending_verification_user_id'] = unverified_user.id
                resend_otp(unverified_user)
                messages.warning(
                    request,
                    f'Ο λογαριασμός σας δεν έχει επαληθευτεί ακόμα. Στείλαμε νέο κωδικό στο {unverified_user.email}.',
                )
                return redirect('accounts:verify_otp')

            return render(request, 'accounts/login.html', {
                'login_error': True,
                'entered_username': login_identifier,
                'hide_sidebar': True,
            })

    return render(request, 'accounts/login.html', {'hide_sidebar': True})


def logout_view(request):
    """Custom logout view."""
    auth_logout(request)
    return redirect('landing')


def register_customer(request):
    """Customer registration with OTP email verification."""
    if request.user.is_authenticated:
        return redirect('landing')

    # Clear any lingering messages from other operations
    storage = messages.get_messages(request)
    for message in storage:
        pass  # This consumes/clears all messages
    storage.used = True

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        form_data = {
            'username': username,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
        }

        if password != password2:
            messages.error(request, 'Οι κωδικοί δεν ταιριάζουν.')
            return render(request, 'accounts/register_customer.html', {
                'hide_sidebar': True,
                'form_data': form_data,
            })

        if not phone.isdigit() or len(phone) != 10:
            messages.error(request, 'Το τηλέφωνο πρέπει να είναι 10 ψηφία.')
            return render(request, 'accounts/register_customer.html', {
                'hide_sidebar': True,
                'form_data': form_data,
            })

        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, 'Αυτό το username υπάρχει ήδη.')
            return render(request, 'accounts/register_customer.html', {
                'hide_sidebar': True,
                'form_data': form_data,
            })

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Αυτό το email υπάρχει ήδη.')
            return render(request, 'accounts/register_customer.html', {
                'hide_sidebar': True,
                'form_data': form_data,
            })

        # Create user with is_active=False until email is verified
        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role='customer',
            is_approved=True,  # Customers are auto-approved
            is_active=False,   # Not active until email verified
            is_email_verified=False,
        )

        # Generate and send OTP
        otp = user.generate_otp()
        if send_otp_email(user, otp):
            messages.info(request, f'Κώδικας επαλήθευσης αποστάλθηκε στο {email}. Έχει ισχύ για 10 λεπτά.')
            request.session['pending_verification_user_id'] = user.id
            return redirect('accounts:verify_otp')
        else:
            user.delete()
            messages.error(request, 'Σφάλμα κατά την αποστολή του email. Προσπαθήστε ξανά.')
            return render(request, 'accounts/register_customer.html', {
                'hide_sidebar': True,
                'form_data': form_data,
            })

    return render(request, 'accounts/register_customer.html', {
        'hide_sidebar': True,
        'form_data': {},
    })


def register_professional(request):
    """Professional registration — requires Super Admin approval."""
    if request.user.is_authenticated:
        return redirect('landing')

    base_context = {
        'hide_sidebar': True,
    }

    # Clear any lingering messages from other operations
    storage = messages.get_messages(request)
    for message in storage:
        pass  # This consumes/clears all messages
    storage.used = True

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        business_name = request.POST.get('business_name', '').strip()
        business_category = request.POST.get('business_category', '').strip()
        business_description = request.POST.get('business_description', '').strip()
        business_address = request.POST.get('business_address', '').strip()
        business_phone = request.POST.get('business_phone', '').strip()
        custom_category_gr = request.POST.get('custom_category_gr', '').strip()
        custom_category_en = request.POST.get('custom_category_en', '').strip()

        form_data = {
            'username': username, 'email': email,
            'first_name': first_name, 'last_name': last_name,
            'phone': phone, 'business_name': business_name,
            'business_category': business_category,
            'business_description': business_description,
            'business_address': business_address, 'business_phone': business_phone,
            'custom_category_gr': custom_category_gr, 'custom_category_en': custom_category_en,
        }
        errors = []

        if password != password2:
            errors.append('Οι κωδικοί δεν ταιριάζουν.')
        if not phone.isdigit() or len(phone) != 10:
            errors.append('Το τηλέφωνο πρέπει να είναι 10 ψηφία.')
        if business_phone and (not business_phone.isdigit() or len(business_phone) != 10):
            errors.append('Το τηλέφωνο επιχείρησης πρέπει να είναι 10 ψηφία.')
        if CustomUser.objects.filter(username=username).exists():
            errors.append('Αυτό το username υπάρχει ήδη.')
        if email and CustomUser.objects.filter(email=email).exists():
            errors.append('Αυτό το email υπάρχει ήδη.')

        if business_category == 'other':
            if not custom_category_gr:
                errors.append('Συμπληρώστε την προσαρμοσμένη κατηγορία στα Ελληνικά.')
            if not custom_category_en:
                errors.append('Συμπληρώστε την προσαρμοσμένη κατηγορία στα Αγγλικά.')

        if errors:
            return render(request, 'accounts/register_professional.html', {
                **base_context,
                'errors': errors,
                'form_data': form_data,
            })

        requires_phone_otp = phone.startswith('69')

        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role='professional',
            is_approved=False,  # Requires Super Admin approval
            is_active=False,
            is_email_verified=False,
            is_phone_verified=not requires_phone_otp,
        )

        # Create Business profile
        from django.utils.text import slugify
        slug = slugify(business_name)
        # Ensure unique slug
        base_slug = slug
        counter = 1
        while Business.objects.filter(slug=slug).exists():
            slug = f'{base_slug}-{counter}'
            counter += 1

        business = Business.objects.create(
            owner=user,
            name=business_name,
            slug=slug,
            category=business_category,
            custom_category_gr=custom_category_gr if business_category == 'other' else '',
            custom_category_en=custom_category_en if business_category == 'other' else '',
            custom_category=custom_category_gr if business_category == 'other' else '',
            description=business_description,
            address=business_address,
            phone=business_phone or phone,
        )

        # Notify all super_admin users about the new business application
        from notifications.utils import get_superadmin_notification_contacts
        super_admin_emails = get_superadmin_notification_contacts(contact_type='email')

        if super_admin_emails and business:
            from django.core.mail import send_mail
            from django.template.loader import render_to_string

            pending_url = f"{settings.SITE_URL}/superadmin/pending/"
            context = {
                'user': user,
                'business': business,
                'pending_url': pending_url,
            }
            html_message = render_to_string('accounts/new_business_application_email.html', context)
            try:
                send_mail(
                    subject=f'Νέα Αίτηση Επιχείρησης: {business.name} - Reserva',
                    message=f'Νέα αίτηση επιχείρησης από {user.get_full_name()} ({business.name}). Διαχείριση: {pending_url}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=super_admin_emails,
                    html_message=html_message,
                    fail_silently=True,
                )
            except Exception:
                pass

        sent_ok, requires_phone_otp, failed_channel = send_professional_registration_otps(user)
        if not sent_ok:
            business.delete()
            user.delete()
            if failed_channel == 'phone':
                errors.append('Ο λογαριασμός δημιουργήθηκε αλλά απέτυχε η αποστολή OTP στο κινητό. Δοκιμάστε ξανά.')
            else:
                errors.append('Αποτυχία αποστολής OTP στο email. Δοκιμάστε ξανά.')
            return render(request, 'accounts/register_professional.html', {
                **base_context,
                'errors': errors,
                'form_data': form_data,
            })

        request.session['pending_professional_verification_user_id'] = user.id
        request.session['pending_professional_requires_phone_otp'] = requires_phone_otp

        if requires_phone_otp:
            messages.info(request, f'Στάλθηκε OTP στο email ({email}) και στο κινητό σας.')
        else:
            messages.info(request, f'Στάλθηκε OTP στο email ({email}).')
        return redirect('accounts:verify_professional_otp')

    return render(request, 'accounts/register_professional.html', base_context)


@never_cache
def verify_otp(request):
    """OTP verification for new customer accounts."""
    if request.user.is_authenticated:
        return redirect('landing')

    user_id = request.session.get('pending_verification_user_id')
    if not user_id:
        messages.error(request, 'Δεν βρέθηκε εκκρεμές λογαριασμό. Παρακαλώ εγγραφείτε ξανά.')
        return redirect('accounts:register_customer')

    try:
        user = CustomUser.objects.get(id=user_id, role='customer', is_active=False)
    except CustomUser.DoesNotExist:
        verified_user = CustomUser.objects.filter(id=user_id, role='customer', is_email_verified=True).first()
        if verified_user:
            request.session.pop('pending_verification_user_id', None)
            messages.info(request, 'Το email σας έχει ήδη επαληθευτεί. Συνδεθείτε για να συνεχίσετε.')
            return redirect('accounts:login')
        messages.error(request, 'Ο λογαριασμός δεν βρέθηκε.')
        return redirect('accounts:register_customer')

    if request.method == 'POST':
        otp = request.POST.get('otp', '').strip()

        if not otp:
            messages.error(request, 'Παρακαλώ εισάγετε τον κωδικό.')
            return render(request, 'accounts/verify_otp.html', {
                'user_email': user.email,
                'hide_sidebar': True,
            })

        if user.verify_otp(otp):
            user.mark_email_verified()
            user.is_active = True
            user.save(update_fields=['is_active'])
            del request.session['pending_verification_user_id']
            messages.success(request, 'Email επαληθευτεί! Ο λογαριασμός σας είναι ενεργός.')
            auth_login(request, user)
            return redirect('accounts:redirect_after_login')
        else:
            messages.error(request, 'Ο κωδικός είναι λάθος ή έληξε. Παρακαλώ δοκιμάστε ξανά.')
            return render(request, 'accounts/verify_otp.html', {
                'user_email': user.email,
                'hide_sidebar': True,
            })

    return render(request, 'accounts/verify_otp.html', {
        'user_email': user.email,
        'hide_sidebar': True,
    })


def resend_verification_otp(request):
    """Resend OTP to user email."""
    if request.user.is_authenticated:
        return redirect('landing')

    user_id = request.session.get('pending_verification_user_id')
    if not user_id:
        return JsonResponse({'success': False, 'message': 'No pending account'})

    try:
        user = CustomUser.objects.get(id=user_id)
        if resend_otp(user):
            return JsonResponse({
                'success': True,
                'message': f'Κώδικας αποστάλθηκε στο {user.email}'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Σφάλμα κατά την αποστολή του email'
            })
    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found'})


@never_cache
def verify_professional_otp(request):
    """OTP verification for professional registration (email + conditional phone)."""
    if request.user.is_authenticated:
        return redirect('landing')

    user_id = request.session.get('pending_professional_verification_user_id')
    requires_phone_otp = bool(request.session.get('pending_professional_requires_phone_otp'))

    if not user_id:
        messages.error(request, 'Δεν βρέθηκε εκκρεμές λογαριασμό επαγγελματία. Παρακαλώ εγγραφείτε ξανά.')
        return redirect('accounts:register_professional')

    try:
        user = CustomUser.objects.get(id=user_id, role='professional', is_active=False)
    except CustomUser.DoesNotExist:
        verified_user = CustomUser.objects.filter(id=user_id, role='professional', is_email_verified=True).first()
        if verified_user:
            request.session.pop('pending_professional_verification_user_id', None)
            request.session.pop('pending_professional_requires_phone_otp', None)
            messages.info(request, 'Το OTP έχει ήδη επαληθευτεί. Συνδεθείτε για να συνεχίσετε.')
            return redirect('accounts:login')
        messages.error(request, 'Ο λογαριασμός δεν βρέθηκε.')
        return redirect('accounts:register_professional')

    if request.method == 'POST':
        email_otp = request.POST.get('email_otp', '').strip()
        phone_otp = request.POST.get('phone_otp', '').strip()

        if not email_otp:
            messages.error(request, 'Παρακαλώ εισάγετε τον κωδικό email OTP.')
        elif not user.verify_otp(email_otp):
            messages.error(request, 'Ο κωδικός email OTP είναι λάθος ή έληξε.')
        elif requires_phone_otp and not phone_otp:
            messages.error(request, 'Παρακαλώ εισάγετε τον κωδικό OTP κινητού.')
        elif requires_phone_otp and not user.verify_phone_otp(phone_otp):
            messages.error(request, 'Ο κωδικός OTP κινητού είναι λάθος ή έληξε.')
        else:
            user.mark_email_verified()
            if requires_phone_otp:
                user.mark_phone_verified()
            user.is_active = True
            user.save(update_fields=['is_active'])

            # Alert the Super Admins now rather than at registration: only a
            # verified owner is genuinely waiting for approval, and an
            # unverified signup can still be discarded before reaching here.
            business = getattr(user, 'business', None)
            if business:
                try:
                    from notifications.utils import send_new_business_application_sms
                    send_new_business_application_sms(business)
                except Exception:
                    logger.exception('Failed to send new business application SMS')

            request.session.pop('pending_professional_verification_user_id', None)
            request.session.pop('pending_professional_requires_phone_otp', None)

            auth_login(request, user)
            messages.success(request, 'Η επαλήθευση ολοκληρώθηκε! Ο λογαριασμός σας δημιουργήθηκε και περιμένει έγκριση.')
            return redirect('accounts:pending_approval')

    return render(request, 'accounts/verify_professional_otp.html', {
        'user_email': user.email,
        'user_phone': user.phone,
        'requires_phone_otp': requires_phone_otp,
        'hide_sidebar': True,
    })


def resend_professional_verification_otp(request):
    """Resend OTPs for professional verification."""
    if request.user.is_authenticated:
        return redirect('landing')

    user_id = request.session.get('pending_professional_verification_user_id')
    requires_phone_otp = bool(request.session.get('pending_professional_requires_phone_otp'))
    if not user_id:
        return JsonResponse({'success': False, 'message': 'No pending professional account'})

    try:
        user = CustomUser.objects.get(id=user_id, role='professional', is_active=False)
    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found'})

    sent_ok, _, failed_channel = send_professional_registration_otps(user)
    if not sent_ok:
        if failed_channel == 'phone':
            return JsonResponse({'success': False, 'message': 'Αποτυχία αποστολής OTP στο κινητό.'})
        return JsonResponse({'success': False, 'message': 'Αποτυχία αποστολής OTP στο email.'})

    if requires_phone_otp:
        return JsonResponse({'success': True, 'message': f'Στάλθηκαν νέα OTP σε email και κινητό ({user.phone}).'})
    return JsonResponse({'success': True, 'message': f'Στάλθηκε νέο OTP στο email {user.email}.'})


def delete_account(request):
    """Delete customer account with confirmation."""
    if not request.user.is_authenticated or not request.user.is_customer:
        return redirect('landing')

    if request.method == 'POST':
        confirm_value = request.POST.get('confirm', '').strip().lower()
        confirm = confirm_value in ['yes', 'on', 'true', '1']
        if not confirm:
            messages.error(request, 'Παρακαλώ επιβεβαιώστε την διαγραφή του λογαριασμού.')
            return render(request, 'accounts/delete_account.html', {})

        user_id = request.user.id
        username = request.user.get_full_name() or request.user.username
        request.user.delete()
        messages.success(request, f'Ο λογαριασμός του {username} διαγράφηκε μόνιμα.')
        return redirect('landing')

    return render(request, 'accounts/delete_account.html', {})


def request_business_deletion(request):
    """Professional: Request business deletion (requires super_admin approval)."""
    if not request.user.is_authenticated or not request.user.is_professional:
        return redirect('landing')

    business = get_object_or_404(Business, owner=request.user)

    # Check if there's already a pending request
    pending_request = BusinessDeletionRequest.objects.filter(
        business=business,
        status__in=['pending', 'approved']
    ).first()

    if pending_request:
        messages.info(request, 'Υπάρχει ήδη άνοιχτο αίτημα διαγραφής για αυτή την επιχείρηση.')
        return redirect('businesses:dashboard')

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        confirm = request.POST.get('confirm', '').lower() == 'yes'

        if not confirm:
            messages.error(request, 'Παρακαλώ επιβεβαιώστε το αίτημα διαγραφής.')
            return render(request, 'businesses/request_deletion.html', {'business': business})

        deletion_request = BusinessDeletionRequest.objects.create(
            business=business,
            owner=request.user,
            reason=reason,
            status='pending'
        )

        # Notify super_admin
        from notifications.utils import get_superadmin_notification_contacts
        super_admin_emails = get_superadmin_notification_contacts(contact_type='email')

        if super_admin_emails:
            from django.core.mail import send_mail
            from django.template.loader import render_to_string

            admin_url = f"{settings.SITE_URL}/superadmin/business-deletions/"
            context = {
                'user': request.user,
                'business': business,
                'reason': reason,
                'admin_url': admin_url,
            }
            html_message = render_to_string('businesses/business_deletion_request_email.html', context)
            try:
                send_mail(
                    subject=f'Αίτημα Διαγραφής Επιχείρησης: {business.name}',
                    message=f'Αίτημα διαγραφής επιχείρησης {business.name} από {request.user.get_full_name()}.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=super_admin_emails,
                    html_message=html_message,
                    fail_silently=True,
                )
            except Exception:
                pass

        messages.success(request, 'Το αίτημα διαγραφής εστάλθηκε στο διαχειριστή.')
        return redirect('businesses:dashboard')

    return render(request, 'businesses/request_deletion.html', {'business': business})


@login_required
def redirect_after_login(request):
    """Redirect user based on role after login."""
    target_url = _default_post_login_url(request)

    if not request.user.has_seen_welcome_flow:
        params = urlencode({'next': target_url})
        return redirect(f"{reverse('accounts:welcome_flow')}?{params}")

    return redirect(target_url)


def _default_post_login_url(request):
    """Compute default destination URL for a logged-in user based on role/state."""
    if request.user.is_super_admin:
        return reverse('superadmin:dashboard')

    if request.user.is_professional:
        if request.user.is_approved:
            return reverse('businesses:dashboard')
        return reverse('accounts:pending_approval')

    if request.user.is_employee:
        from businesses.models import Employee
        default_employee = Employee.objects.filter(user=request.user, is_active=True).order_by('id').first()
        if default_employee:
            request.session['active_employee_profile_id'] = default_employee.id
            return reverse('accounts:employee_dashboard')
        messages.warning(request, 'Δεν υπάρχει ενεργή θέση εργασίας. Μπορείτε να συνεχίσετε ως πελάτης.')
        return reverse('accounts:my_bookings')

    return reverse('accounts:my_bookings')


@login_required
def welcome_flow(request):
    """Optional welcome flow shown on first login and available anytime from navigation."""
    next_url = (request.GET.get('next') or '').strip()
    default_next = _default_post_login_url(request)
    if not next_url.startswith('/'):
        next_url = default_next

    role_features = {
        'super_admin': [
            'Έγκριση/διαχείριση επαγγελματιών και πελατών',
            'Στατιστικά πλατφόρμας, αναφορές και ειδήσεις',
            'Troubleshooting πρόσβαση σε επιλεγμένες επιχειρήσεις',
        ],
        'professional': [
            'Dashboard με ραντεβού, έσοδα και βασικά metrics',
            'Διαχείριση υπηρεσιών, υπαλλήλων και ωραρίου',
            'Επιβεβαίωση/απόρριψη/ολοκλήρωση ραντεβού και ειδοποιήσεις',
        ],
        'employee': [
            'Προβολή και διαχείριση των ραντεβού σας',
            'Ενέργειες ραντεβού (επιβεβαίωση, no-show, ολοκλήρωση)',
            'Αιτήματα άδειας και εναλλαγή θέσης εργασίας',
        ],
        'customer': [
            'Αναζήτηση επιχειρήσεων και online κράτηση σε λίγα βήματα',
            'Πίνακας με επερχόμενα/παλαιότερα ραντεβού',
            'Ακύρωση ή επαναπρογραμματισμός βάσει προθεσμίας υπηρεσίας',
        ],
    }

    context = {
        'next_url': next_url,
        'has_seen_welcome_flow': request.user.has_seen_welcome_flow,
        'role_features': role_features.get(request.user.role, []),
        'hide_sidebar': request.session.get('customer_mode', False),
    }
    return render(request, 'accounts/welcome_flow.html', context)


@login_required
@require_http_methods(["POST"])
def complete_welcome_flow(request):
    """Mark welcome flow as completed/skipped and continue to target page."""
    if not request.user.has_seen_welcome_flow:
        request.user.has_seen_welcome_flow = True
        request.user.save(update_fields=['has_seen_welcome_flow'])

    next_url = (request.POST.get('next') or '').strip()
    if not next_url.startswith('/'):
        next_url = _default_post_login_url(request)

    return redirect(next_url)


@login_required
def pending_approval(request):
    """Page shown to professionals waiting for approval."""
    if not request.user.is_professional:
        return redirect('landing')
    if request.user.is_approved:
        return redirect('businesses:dashboard')
    return render(request, 'accounts/pending_approval.html')


@login_required
def profile(request):
    """User profile view/edit."""
    if request.method == 'POST':
        user = request.user
        # Username is immutable from profile settings.
        original_username = user.username
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        
        # Validate phone if provided
        if phone and (not phone.isdigit() or len(phone) != 10):
            messages.error(request, 'Το τηλέφωνο πρέπει να είναι 10 ψηφία.')
            return redirect('accounts:profile')
        
        user.username = original_username
        user.phone = phone
        user.save()
        messages.success(request, 'Το προφίλ ενημερώθηκε.')
        return redirect('accounts:profile')

    return render(request, 'accounts/profile.html', {
        'hide_sidebar': request.session.get('customer_mode', False),
    })


@login_required
@require_http_methods(["POST"])
def send_password_change_email(request):
    """Send password reset email to the logged-in user's email for identity verification."""
    user_email = (request.user.email or '').strip()
    if not user_email:
        messages.error(request, 'Δεν υπάρχει διαθέσιμο email για επαλήθευση αλλαγής κωδικού.')
        return redirect('accounts:profile')

    form = PasswordResetForm({'email': user_email})
    if form.is_valid():
        form.save(
            request=request,
            use_https=request.is_secure(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            email_template_name='accounts/password_reset_email.txt',
            html_email_template_name='accounts/password_reset_email.html',
            subject_template_name='accounts/password_reset_subject.txt',
        )
        messages.success(request, f'Στάλθηκε email αλλαγής κωδικού στο {user_email}.')
    else:
        messages.error(request, 'Δεν ήταν δυνατή η αποστολή email αλλαγής κωδικού.')

    return redirect('accounts:profile')


@login_required
def my_bookings(request):
    """Customer: view their booking history, search bookings, and find businesses to book."""
    from bookings.models import Booking
    from reviews.models import Review
    from businesses.models import Business
    from django.db.models import Q
    from datetime import datetime

    # Enable customer mode for non-customer roles viewing this page.
    if request.user.is_professional or request.user.is_employee:
        request.session['customer_mode'] = True

    # --- Search / filter parameters ---
    q = request.GET.get('q', '').strip()          # free-text search (business or service name)
    status_filter = request.GET.get('status', '') # status filter
    date_from = request.GET.get('date_from', '')  # start date filter (YYYY-MM-DD)
    date_to = request.GET.get('date_to', '')      # end date filter (YYYY-MM-DD)

    # --- Active tab (my_bookings or book_new) ---
    active_tab = request.GET.get('tab', 'my_bookings')

    bookings_qs = Booking.objects.filter(
        customer=request.user
    ).select_related('business', 'employee', 'service').order_by('-date', '-start_time')

    # Apply filters
    if q:
        bookings_qs = bookings_qs.filter(
            Q(business__name__icontains=q) | Q(service__name__icontains=q)
        )

    if status_filter:
        bookings_qs = bookings_qs.filter(status=status_filter)

    if date_from:
        try:
            bookings_qs = bookings_qs.filter(date__gte=datetime.strptime(date_from, '%Y-%m-%d').date())
        except ValueError:
            pass

    if date_to:
        try:
            bookings_qs = bookings_qs.filter(date__lte=datetime.strptime(date_to, '%Y-%m-%d').date())
        except ValueError:
            pass

    reviewed_booking_ids = set(
        Review.objects.filter(
            booking__customer=request.user
        ).values_list('booking_id', flat=True)
    )

    # All bookings (unfiltered) for stats
    all_bookings = Booking.objects.filter(customer=request.user)
    upcoming = all_bookings.filter(status__in=['pending', 'confirmed'])
    past_all = all_bookings.filter(status__in=['completed', 'cancelled', 'no_show'])

    # Filtered bookings split into upcoming/past
    upcoming_filtered = bookings_qs.filter(status__in=['pending', 'confirmed'])
    past_filtered = bookings_qs.filter(status__in=['completed', 'cancelled', 'no_show'])

    # --- Businesses for "Book New Appointment" tab ---
    business_search = request.GET.get('business_q', '').strip()
    business_category = request.GET.get('business_category', '').strip()

    businesses = Business.objects.filter(
        is_active=True, is_approved=True
    ).prefetch_related('services').order_by('name')

    if business_search:
        businesses = businesses.filter(name__icontains=business_search)
        active_tab = 'book_new'

    if business_category:
        businesses = businesses.filter(category=business_category)
        active_tab = 'book_new'

    context = {
        'bookings': bookings_qs,
        'upcoming': upcoming_filtered,
        'past': past_filtered,
        'reviewed_booking_ids': reviewed_booking_ids,
        'total_count': all_bookings.count(),
        'upcoming_count': upcoming.count(),
        'completed_count': past_all.filter(status='completed').count(),
        'cancelled_count': past_all.filter(status__in=['cancelled', 'no_show']).count(),
        # Search state
        'q': q,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'active_tab': active_tab,
        # Book new appointment
        'businesses': businesses,
        'business_search': business_search,
        'business_category': business_category,
        'category_choices': Business.CATEGORY_CHOICES,
        # Hide sidebar for professionals in customer mode
        'hide_sidebar': request.session.get('customer_mode', False),
        # News
        'latest_news': News.objects.filter(status='published').order_by('-published_at')[:5],
    }
    return render(request, 'accounts/my_bookings.html', context)


@login_required
def exit_customer_mode(request):
    """Exit customer mode and return to the user's primary dashboard."""
    if 'customer_mode' in request.session:
        del request.session['customer_mode']
    return redirect('accounts:redirect_after_login')


@login_required
def switch_account(request):
    """Show available accounts to switch to."""
    current_user = request.user

    # Find other accounts with same email
    other_accounts = CustomUser.objects.filter(
        email=current_user.email
    ).exclude(id=current_user.id)

    # Do not expose super admin accounts in switch-account for non-super-admin users.
    if not current_user.is_super_admin:
        other_accounts = other_accounts.exclude(role='super_admin')

    other_accounts = other_accounts.order_by('role')

    # Also check for accounts with same phone if email is not available
    if not other_accounts.exists() and current_user.phone:
        other_accounts = CustomUser.objects.filter(
            phone=current_user.phone
        ).exclude(id=current_user.id)

        if not current_user.is_super_admin:
            other_accounts = other_accounts.exclude(role='super_admin')

        other_accounts = other_accounts.order_by('role')

    context = {
        'current_user': current_user,
        'other_accounts': other_accounts,
        'hide_sidebar': request.session.get('customer_mode', False),
    }
    return render(request, 'accounts/switch_account.html', context)


@login_required
def perform_account_switch(request, user_id):
    """Switch to another account."""
    current_user = request.user

    try:
        target_user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        messages.error(request, 'Ο λογαριασμός δεν βρέθηκε.')
        return redirect('accounts:switch_account')

    # Security check: can only switch to accounts with same email or phone
    if (target_user.email != current_user.email and
        target_user.phone != current_user.phone):
        messages.error(request, 'Δεν έχετε δικαίωμα να μεταβείτε σε αυτόν τον λογαριασμό.')
        return redirect('accounts:switch_account')

    if target_user.role == 'super_admin' and not current_user.is_super_admin:
        messages.error(request, 'Δεν έχετε δικαίωμα να μεταβείτε σε αυτόν τον λογαριασμό.')
        return redirect('accounts:switch_account')

    if request.method == 'POST':
        # Clear any previous session data
        if 'customer_mode' in request.session:
            del request.session['customer_mode']
        if 'active_employee_profile_id' in request.session:
            del request.session['active_employee_profile_id']

        # Login as the target user
        from django.contrib.auth import login as auth_login
        auth_login(request, target_user, backend='django.contrib.auth.backends.ModelBackend')

        messages.success(request, f'Μεταβήκατε στον λογαριασμό: {target_user.get_full_name() or target_user.username} ({target_user.get_role_display()})')

        # Redirect to appropriate dashboard
        return redirect('accounts:redirect_after_login')

    context = {
        'target_user': target_user,
        'hide_sidebar': request.session.get('customer_mode', False),
    }
    return render(request, 'accounts/confirm_switch.html', context)


@login_required
def customer_help(request):
    """Customer help/FAQ page."""
    return render(request, 'accounts/customer_help.html', {
        'hide_sidebar': request.session.get('customer_mode', False),
    })


@login_required
def employee_help(request):
    """Employee help/FAQ page."""
    if not request.user.is_employee:
        return redirect('landing')
    employee, employee_profiles = _get_active_employee_profile(request)
    if not employee:
        messages.error(request, 'Δεν βρέθηκε ενεργή θέση εργασίας για τον λογαριασμό σας.')
        return redirect('accounts:my_bookings')
    return render(request, 'accounts/employee_help.html', {
        'employee': employee,
        'employee_profiles': employee_profiles,
        'business': employee.business,
    })


def _get_employee_profiles_for_user(user):
    """Return all employee profiles linked to the logged-in employee user."""
    from businesses.models import Employee
    profiles = Employee.objects.filter(user=user, is_active=True).select_related('business').order_by('business__name', 'id')
    if profiles.exists():
        return profiles

    # Legacy data recovery: after old invitation/account flows, some employee users
    # may exist without linked Employee rows. Auto-link by unique contact identity.
    candidates = Employee.objects.none()
    normalized_email = (user.email or '').strip()
    normalized_phone = (user.phone or '').strip()

    if normalized_email:
        candidates = Employee.objects.filter(user__isnull=True, is_active=True, email__iexact=normalized_email)
    elif normalized_phone:
        candidates = Employee.objects.filter(user__isnull=True, is_active=True, phone=normalized_phone)

    if candidates.exists():
        candidates.update(user=user)

    return Employee.objects.filter(user=user, is_active=True).select_related('business').order_by('business__name', 'id')


def _get_active_employee_profile(request):
    """Return the active employee profile selected in session (or first available)."""
    profiles = _get_employee_profiles_for_user(request.user)
    if not profiles.exists():
        return None, profiles

    active_employee_id = request.session.get('active_employee_profile_id')
    if active_employee_id:
        active_profile = profiles.filter(id=active_employee_id).first()
        if active_profile:
            return active_profile, profiles

    active_profile = profiles.first()
    request.session['active_employee_profile_id'] = active_profile.id
    return active_profile, profiles


@login_required
def switch_employee_workplace(request, employee_id):
    """Switch active workplace for employee users with multiple employee profiles."""
    if not request.user.is_employee:
        return redirect('landing')

    profiles = _get_employee_profiles_for_user(request.user)
    target_profile = profiles.filter(id=employee_id).first()
    if not target_profile:
        messages.error(request, 'Δεν έχετε πρόσβαση σε αυτή τη θέση εργασίας.')
        return redirect('accounts:employee_dashboard')

    request.session['active_employee_profile_id'] = target_profile.id
    messages.success(request, f'Ενεργή θέση: {target_profile.business.name} ({target_profile.name})')

    next_url = (request.GET.get('next') or '').strip()
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect('accounts:employee_dashboard')


# ── Employee Invitation & Portal ──────────────────────────

def accept_employee_invitation(request, token):
    """Employee accepts invitation and creates account or links an existing employee account."""
    from businesses.models import EmployeeInvitation

    invitation = get_object_or_404(EmployeeInvitation, token=token)

    if not invitation.is_valid:
        return render(request, 'accounts/employee_invitation_invalid.html', {
            'is_expired': invitation.is_expired,
            'is_used': invitation.is_used,
            'hide_sidebar': True,
        })

    employee = invitation.employee
    business = employee.business
    existing_employee_user = CustomUser.objects.filter(
        role='employee',
        email__iexact=invitation.email,
    ).order_by('id').first()

    if employee.user:
        messages.info(request, 'Αυτός ο υπάλληλος έχει ήδη συνδεμένο λογαριασμό.')
        return redirect('accounts:login')

    if request.user.is_authenticated and request.user.is_employee:
        session_user_email = (request.user.email or '').strip().lower()
        invitation_email = (invitation.email or '').strip().lower()
        if session_user_email and invitation_email and session_user_email != invitation_email:
            messages.error(request, 'Το email του λογαριασμού σας δεν ταιριάζει με την πρόσκληση.')
            return redirect('accounts:employee_dashboard')

        if request.method == 'POST' and request.POST.get('link_existing') == '1':
            employee.user = request.user
            employee.save(update_fields=['user'])
            invitation.is_used = True
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=['is_used', 'accepted_at'])
            request.session['active_employee_profile_id'] = employee.id
            messages.success(request, f'Η θέση στην επιχείρηση {business.name} προστέθηκε στον λογαριασμό σας.')
            return redirect('accounts:employee_dashboard')

        return render(request, 'accounts/employee_invitation_accept.html', {
            'invitation': invitation,
            'employee': employee,
            'business': business,
            'link_existing_mode': True,
            'hide_sidebar': True,
        })

    if request.user.is_authenticated and not request.user.is_employee:
        messages.error(request, 'Για αποδοχή πρόσκλησης υπαλλήλου συνδεθείτε με λογαριασμό υπαλλήλου.')
        return redirect('accounts:redirect_after_login')

    if request.method == 'POST':
        if request.POST.get('link_by_username') == '1':
            existing_username = (request.POST.get('existing_username') or '').strip()
            existing_password = request.POST.get('existing_password', '')
            if not existing_username or not existing_password:
                messages.error(request, 'Συμπληρώστε username και κωδικό για σύνδεση υπάρχοντος λογαριασμού.')
                return render(request, 'accounts/employee_invitation_accept.html', {
                    'invitation': invitation,
                    'employee': employee,
                    'business': business,
                    'existing_employee_user': existing_employee_user,
                    'hide_sidebar': True,
                })

            existing_user = authenticate(request, username=existing_username, password=existing_password)
            if not existing_user:
                messages.error(request, 'Μη έγκυρα στοιχεία λογαριασμού.')
                return render(request, 'accounts/employee_invitation_accept.html', {
                    'invitation': invitation,
                    'employee': employee,
                    'business': business,
                    'existing_employee_user': existing_employee_user,
                    'hide_sidebar': True,
                })

            linked_employee_user = existing_user
            if existing_user.role != 'employee':
                base_username = f"{existing_user.username}_emp"
                candidate_username = base_username
                counter = 1
                while CustomUser.objects.filter(username=candidate_username).exists():
                    candidate_username = f"{base_username}{counter}"
                    counter += 1

                linked_employee_user = CustomUser.objects.create_user(
                    username=candidate_username,
                    email=existing_user.email or invitation.email,
                    password=existing_password,
                    first_name=existing_user.first_name,
                    last_name=existing_user.last_name,
                    phone=existing_user.phone,
                    role='employee',
                    is_approved=True,
                    is_active=True,
                    is_email_verified=existing_user.is_email_verified,
                )

            employee.user = linked_employee_user
            employee.save(update_fields=['user'])
            invitation.is_used = True
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=['is_used', 'accepted_at'])

            auth_login(request, linked_employee_user)
            request.session['active_employee_profile_id'] = employee.id
            messages.success(request, f'Η πρόσκληση συνδέθηκε επιτυχώς με τον λογαριασμό {linked_employee_user.username}.')
            return redirect('accounts:employee_dashboard')

        if existing_employee_user:
            messages.info(request, 'Υπάρχει ήδη λογαριασμός υπαλλήλου με αυτό το email. Συνδεθείτε και ξανανοίξτε τον σύνδεσμο πρόσκλησης για να προστεθεί η νέα θέση.')
            return redirect(f"{reverse('accounts:login')}?next={request.path}")

        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        errors = []

        if password != password2:
            errors.append('Οι κωδικοί δεν ταιριάζουν.')

        if len(password) < 8:
            errors.append('Ο κωδικός πρέπει να είναι τουλάχιστον 8 χαρακτήρες.')

        if CustomUser.objects.filter(username=username).exists():
            errors.append('Αυτό το username υπάρχει ήδη.')

        if errors:
            return render(request, 'accounts/employee_invitation_accept.html', {
                'invitation': invitation,
                'employee': employee,
                'business': business,
                'errors': errors,
                'entered_username': username,
                'hide_sidebar': True,
            })

        # Create user account
        user = CustomUser.objects.create_user(
            username=username,
            email=invitation.email,
            password=password,
            first_name=employee.name.split()[0] if employee.name else '',
            last_name=' '.join(employee.name.split()[1:]) if employee.name else '',
            role='employee',
            is_approved=True,
        )

        # Link employee to user
        employee.user = user
        employee.save(update_fields=['user'])

        # Mark invitation as used
        invitation.is_used = True
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=['is_used', 'accepted_at'])

        # Log them in
        auth_login(request, user)
        request.session['active_employee_profile_id'] = employee.id
        messages.success(request, f'Καλώς ήρθατε {employee.name}! Ο λογαριασμός σας δημιουργήθηκε.')
        return redirect('accounts:employee_dashboard')

    return render(request, 'accounts/employee_invitation_accept.html', {
        'invitation': invitation,
        'employee': employee,
        'business': business,
        'existing_employee_user': existing_employee_user,
        'hide_sidebar': True,
    })


@login_required
def employee_dashboard(request):
    """Employee dashboard - view schedule and manage availability."""
    if not request.user.is_employee:
        messages.error(request, 'Πρόσβαση μόνο για υπαλλήλους.')
        return redirect('landing')

    from businesses.models import SpecialDayOff
    employee, employee_profiles = _get_active_employee_profile(request)
    if not employee:
        messages.error(request, 'Δεν βρέθηκε ενεργή θέση εργασίας για τον λογαριασμό σας.')
        return redirect('landing')
    business = employee.business
    today = timezone.now().date()

    # Get upcoming bookings for this employee
    from bookings.models import Booking
    upcoming_bookings = Booking.objects.filter(
        employee=employee,
        date__gte=today,
        status__in=['pending', 'confirmed'],
    ).select_related('service', 'customer').order_by('date', 'start_time')[:10]

    # Get working hours
    working_hours = employee.working_hours.all()

    # Get approved days off (only show approved ones as actual days off)
    days_off = employee.days_off.filter(date__gte=today, status='approved').order_by('date')

    # Get all absence requests (pending, approved, rejected)
    absence_requests = employee.days_off.filter(date__gte=today).order_by('-date', 'id')

    # Check if today is an approved day off
    is_off_today = employee.days_off.filter(date=today, status='approved').exists()

    context = {
        'employee': employee,
        'employee_profiles': employee_profiles,
        'business': business,
        'upcoming_bookings': upcoming_bookings,
        'working_hours': working_hours,
        'days_off': days_off,
        'absence_requests': absence_requests,
        'is_off_today': is_off_today,
        'today': today,
    }
    return render(request, 'accounts/employee_dashboard.html', context)


@login_required
def employee_bookings(request):
    """Employee bookings page with optional confirm/reject actions."""
    if not request.user.is_employee:
        messages.error(request, 'Πρόσβαση μόνο για υπαλλήλους.')
        return redirect('landing')

    from bookings.models import Booking

    employee, employee_profiles = _get_active_employee_profile(request)
    if not employee:
        messages.error(request, 'Δεν βρέθηκε ενεργή θέση εργασίας για τον λογαριασμό σας.')
        return redirect('landing')
    today = timezone.now().date()
    status_filter = (request.GET.get('status') or '').strip()

    bookings = Booking.objects.filter(
        employee=employee,
    ).select_related('service', 'customer').order_by('-date', '-start_time')

    if status_filter:
        bookings = bookings.filter(status=status_filter)

    paginator = Paginator(bookings, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    bookings_calendar_data = [
        {
            'id': booking.id,
            'date': booking.date.isoformat(),
            'start_time': booking.start_time.strftime('%H:%M:%S'),
            'end_time': booking.end_time.strftime('%H:%M:%S'),
            'status': booking.status,
            'status_display': booking.get_status_display(),
            'service_name': booking.service.name if booking.service else '',
            'customer_name': booking.customer.get_full_name() if booking.customer else (booking.guest_name or 'Επισκέπτης'),
            'phone': booking.customer.phone if booking.customer and booking.customer.phone else (booking.guest_phone or ''),
            'notes': booking.notes or '',
        }
        for booking in bookings
    ]

    context = {
        'employee': employee,
        'employee_profiles': employee_profiles,
        'business': employee.business,
        'bookings': page_obj.object_list,
        'page_obj': page_obj,
        'bookings_calendar_data': bookings_calendar_data,
        'status_filter': status_filter,
        'today': today,
    }
    return render(request, 'accounts/employee_bookings.html', context)


@login_required
def employee_mark_no_show(request, booking_id):
    """Employee marks assigned booking as no-show."""
    if not request.user.is_employee:
        messages.error(request, 'Πρόσβαση μόνο για υπαλλήλους.')
        return redirect('landing')

    from bookings.models import Booking, BookingStatusLog

    employee, _ = _get_active_employee_profile(request)
    if not employee:
        messages.error(request, 'Δεν βρέθηκε ενεργή θέση εργασίας για τον λογαριασμό σας.')
        return redirect('accounts:my_bookings')

    business = employee.business
    if not business.allow_employee_booking_actions:
        messages.error(request, 'Η επιχείρηση δεν επιτρέπει ενέργειες ραντεβού από υπαλλήλους.')
        return redirect('accounts:employee_bookings')

    booking = get_object_or_404(Booking, id=booking_id, business=business, employee=employee)
    if booking.status not in ('pending', 'confirmed'):
        messages.error(request, 'Δεν μπορείτε να αλλάξετε αυτή την κατάσταση ραντεβού.')
        return redirect('accounts:employee_bookings')

    old_status = booking.status
    booking.status = 'no_show'
    booking.save(update_fields=['status', 'updated_at'])

    BookingStatusLog.objects.create(
        booking=booking,
        old_status=old_status,
        new_status='no_show',
        changed_by=request.user,
        notes='Σημειώθηκε ως no-show από υπάλληλο',
    )

    messages.info(request, f'Το ραντεβού #{booking.id} σημειώθηκε ως no-show.')
    return redirect('accounts:employee_bookings')


@login_required
def employee_mark_completed(request, booking_id):
    """Employee marks assigned booking as completed."""
    if not request.user.is_employee:
        messages.error(request, 'Πρόσβαση μόνο για υπαλλήλους.')
        return redirect('landing')

    from bookings.models import Booking, BookingStatusLog

    employee, _ = _get_active_employee_profile(request)
    if not employee:
        messages.error(request, 'Δεν βρέθηκε ενεργή θέση εργασίας για τον λογαριασμό σας.')
        return redirect('accounts:my_bookings')

    business = employee.business
    if not business.allow_employee_booking_actions:
        messages.error(request, 'Η επιχείρηση δεν επιτρέπει ενέργειες ραντεβού από υπαλλήλους.')
        return redirect('accounts:employee_bookings')

    booking = get_object_or_404(Booking, id=booking_id, business=business, employee=employee)
    if booking.status not in ('pending', 'confirmed'):
        messages.error(request, 'Δεν μπορείτε να αλλάξετε αυτή την κατάσταση ραντεβού.')
        return redirect('accounts:employee_bookings')

    old_status = booking.status
    booking.status = 'completed'
    booking.save(update_fields=['status', 'updated_at'])

    BookingStatusLog.objects.create(
        booking=booking,
        old_status=old_status,
        new_status='completed',
        changed_by=request.user,
        notes='Ολοκλήρωση από υπάλληλο',
    )

    messages.success(request, f'Το ραντεβού #{booking.id} σημειώθηκε ως ολοκληρωμένο.')
    return redirect('accounts:employee_bookings')


@login_required
def employee_confirm_booking(request, booking_id):
    """Employee confirms a pending booking assigned to them."""
    if not request.user.is_employee:
        messages.error(request, 'Πρόσβαση μόνο για υπαλλήλους.')
        return redirect('landing')

    from bookings.models import Booking, BookingStatusLog
    from notifications.utils import send_booking_approval_notifications

    employee, _ = _get_active_employee_profile(request)
    if not employee:
        messages.error(request, 'Δεν βρέθηκε ενεργή θέση εργασίας για τον λογαριασμό σας.')
        return redirect('landing')
    business = employee.business

    if not business.allow_employee_booking_actions:
        messages.error(request, 'Η επιχείρηση δεν επιτρέπει ενέργειες ραντεβού από υπαλλήλους.')
        return redirect('accounts:employee_bookings')

    booking = get_object_or_404(
        Booking,
        id=booking_id,
        business=business,
        employee=employee,
        status='pending',
    )

    old_status = booking.status
    booking.status = 'confirmed'
    booking.save(update_fields=['status', 'updated_at'])

    BookingStatusLog.objects.create(
        booking=booking,
        old_status=old_status,
        new_status='confirmed',
        changed_by=request.user,
        notes='Έγκριση από υπάλληλο',
    )

    send_booking_approval_notifications(booking)
    messages.success(request, f'Το ραντεβού #{booking.id} εγκρίθηκε.')
    return redirect('accounts:employee_bookings')


@login_required
def employee_reject_booking(request, booking_id):
    """Employee rejects a pending/confirmed booking assigned to them."""
    if not request.user.is_employee:
        messages.error(request, 'Πρόσβαση μόνο για υπαλλήλους.')
        return redirect('landing')

    from bookings.models import Booking, BookingStatusLog
    from notifications.utils import send_booking_rejected_email

    employee, _ = _get_active_employee_profile(request)
    if not employee:
        messages.error(request, 'Δεν βρέθηκε ενεργή θέση εργασίας για τον λογαριασμό σας.')
        return redirect('landing')
    business = employee.business

    if not business.allow_employee_booking_actions:
        messages.error(request, 'Η επιχείρηση δεν επιτρέπει ενέργειες ραντεβού από υπαλλήλους.')
        return redirect('accounts:employee_bookings')

    booking = get_object_or_404(
        Booking,
        id=booking_id,
        business=business,
        employee=employee,
    )
    if booking.status not in ('pending', 'confirmed'):
        messages.error(request, 'Δεν μπορείτε να απορρίψετε αυτό το ραντεβού.')
        return redirect('accounts:employee_bookings')

    rejection_reason = request.POST.get('rejection_reason', '').strip()
    if not rejection_reason:
        messages.error(request, 'Παρακαλώ συμπληρώστε λόγο απόρριψης.')
        return redirect('accounts:employee_bookings')

    old_status = booking.status
    booking.status = 'cancelled'
    booking.rejection_reason = rejection_reason
    booking.save(update_fields=['status', 'rejection_reason', 'updated_at'])

    BookingStatusLog.objects.create(
        booking=booking,
        old_status=old_status,
        new_status='cancelled',
        changed_by=request.user,
        notes=f'Απόρριψη από υπάλληλο. Λόγος: {rejection_reason}',
    )

    if booking.deposit_amount > 0:
        from payments.utils import process_refund
        process_refund(booking, refund_percentage=100)

    send_booking_rejected_email(booking)
    messages.info(request, f'Το ραντεβού #{booking.id} απορρίφθηκε.')
    return redirect('accounts:employee_bookings')



@login_required
def employee_add_day_off(request):
    """Employee requests a day off."""
    if not request.user.is_employee:
        return redirect('landing')

    from businesses.models import SpecialDayOff
    employee, _ = _get_active_employee_profile(request)
    if not employee:
        messages.error(request, 'Δεν βρέθηκε ενεργή θέση εργασίας για τον λογαριασμό σας.')
        return redirect('landing')

    if request.method == 'POST':
        date_str = request.POST.get('date', '')
        reason = request.POST.get('reason', '').strip()
        request_notes = request.POST.get('request_notes', '').strip()

        if date_str:
            from datetime import datetime
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                if date < timezone.now().date():
                    messages.error(request, 'Δεν μπορείτε να προσθέσετε άδεια σε παρελθοντική ημερομηνία.')
                else:
                    absence_request, created = SpecialDayOff.objects.get_or_create(
                        employee=employee, date=date,
                        defaults={
                            'reason': reason or 'Άδεια',
                            'status': 'pending',
                            'request_notes': request_notes
                        }
                    )
                    if created:
                        # Send email notification to business owner
                        _send_absence_notification_email(absence_request)
                        messages.success(request, f'Το αίτημα άδειας για {date.strftime("%d/%m/%Y")} υποβλήθηκε για έγκριση.')
                    else:
                        messages.warning(request, f'Υπάρχει ήδη αίτημα για {date.strftime("%d/%m/%Y")}.')
            except ValueError:
                messages.error(request, 'Μη έγκυρη ημερομηνία.')

    return redirect('accounts:employee_dashboard')


@login_required
def employee_remove_day_off(request, dayoff_id):
    """Employee cancels a pending absence request."""
    if not request.user.is_employee:
        return redirect('landing')

    from businesses.models import SpecialDayOff
    employee, _ = _get_active_employee_profile(request)
    if not employee:
        messages.error(request, 'Δεν βρέθηκε ενεργή θέση εργασίας για τον λογαριασμό σας.')
        return redirect('landing')
    absence_request = get_object_or_404(SpecialDayOff, id=dayoff_id, employee=employee)

    if request.method == 'POST':
        if absence_request.status == 'pending':
            absence_request.delete()
            messages.success(request, 'Το αίτημα άδειας ακυρώθηκε.')
        elif absence_request.status == 'approved':
            messages.error(request, 'Δεν μπορείτε να ακυρώσετε εγκεκριμένη άδεια. Επικοινωνήστε με τον εργοδότη σας.')
        else:
            messages.warning(request, 'Δεν μπορείτε να ακυρώσετε αυτό το αίτημα.')

    return redirect('accounts:employee_dashboard')


@login_required
def employee_absence_request_detail(request, dayoff_id):
    """Employee: view absence request details with chat."""
    if not request.user.is_employee:
        return redirect('landing')

    from businesses.models import SpecialDayOff, AbsenceRequestChat
    employee, employee_profiles = _get_active_employee_profile(request)
    if not employee:
        messages.error(request, 'Δεν βρέθηκε ενεργή θέση εργασίας για τον λογαριασμό σας.')
        return redirect('landing')
    absence_request = get_object_or_404(SpecialDayOff, id=dayoff_id, employee=employee)

    if request.method == 'POST':
        message_text = request.POST.get('message', '').strip()
        if message_text:
            AbsenceRequestChat.objects.create(
                absence_request=absence_request,
                sender=request.user,
                message=message_text,
            )
            # Mark professional messages as read when employee replies
            absence_request.chat_messages.filter(
                is_read=False
            ).exclude(sender=request.user).update(is_read=True)
        return redirect('accounts:employee_absence_request_detail', dayoff_id=dayoff_id)

    # Mark unread messages as read when employee opens the detail
    absence_request.chat_messages.filter(
        is_read=False
    ).exclude(sender=request.user).update(is_read=True)

    chat_messages = absence_request.chat_messages.select_related('sender').order_by('created_at')
    context = {
        'employee': employee,
        'employee_profiles': employee_profiles,
        'business': employee.business,
        'absence_request': absence_request,
        'chat_messages': chat_messages,
    }
    return render(request, 'accounts/employee_absence_request_detail.html', context)

def _send_absence_notification_email(absence_request, is_urgent=False):
    """Send email notification to business owner about absence request."""
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.conf import settings as django_settings

    business = absence_request.employee.business
    business_owner = business.owner
    employee = absence_request.employee

    if not business_owner.email:
        return  # No email to send to

    if is_urgent:
        subject = f'ΕΠΕΙΓΟΝ: {employee.name} δεν είναι διαθέσιμος/η σήμερα - {business.name}'
        template = 'accounts/absence_urgent_notification_email.html'
    else:
        subject = f'Αίτημα άδειας από {employee.name} - {business.name}'
        template = 'accounts/absence_request_notification_email.html'

    # Build URLs for approval/rejection
    site_url = getattr(django_settings, 'SITE_URL', 'http://localhost:8000')
    approve_url = f"{site_url}/business/absence-requests/{absence_request.id}/approve/"
    reject_url = f"{site_url}/business/absence-requests/{absence_request.id}/reject/"
    requests_url = f"{site_url}/business/absence-requests/"

    context = {
        'absence_request': absence_request,
        'employee': employee,
        'business': business,
        'is_urgent': is_urgent,
        'approve_url': approve_url,
        'reject_url': reject_url,
        'requests_url': requests_url,
    }

    # Plain text version
    plain_message = f"""
{'ΕΠΕΙΓΟΝΤΟΣ ΕΙΔΟΠΟΙΗΣΗ' if is_urgent else 'ΑΙΤΗΜΑ ΑΔΕΙΑΣ'}

Υπάλληλος: {employee.name}
Ημερομηνία: {absence_request.date.strftime('%d/%m/%Y')}
Λόγος: {absence_request.reason}

{'Ο υπάλληλος δήλωσε ότι δεν είναι διαθέσιμος σήμερα.' if is_urgent else f'Σημειώσεις: {absence_request.request_notes}'}

Για να διαχειριστείτε αυτό το αίτημα, συνδεθείτε στο Reserva:
{requests_url}

Με εκτίμηση,
Η Ομάδα του Reserva
"""

    try:
        html_message = render_to_string(template, context)
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[business_owner.email],
            html_message=html_message,
            fail_silently=True,  # Don't break the flow if email fails
        )
    except Exception:
        pass  # Silently fail email notifications


# Database Management (Super Admin Only)

@login_required
def admin_database_wipe(request):
    """Super Admin panel for database wiping with safety confirmations"""
    # Only super admins can access this
    if not request.user.is_super_admin:
        messages.error(request, 'Access denied. Super Admin privileges required.')
        return redirect('landing')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'confirm_wipe':
            # Safety confirmation step
            confirmation_text = request.POST.get('confirmation_text', '').strip()
            if confirmation_text != 'RESET':
                messages.error(request, 'You must type "RESET" exactly to confirm database wipe.')
                return render(request, 'accounts/admin_database_wipe.html')

            # Mark that user has confirmed
            return render(request, 'accounts/admin_database_wipe.html', {
                'confirmed': True,
            })

        elif action == 'perform_wipe':
            # Final confirmation received, perform the wipe
            try:
                # Call the reset_database management command
                call_command('reset_database', yes_i_am_sure=True, verbosity=0)

                # Clear any existing messages to prevent persistence
                storage = messages.get_messages(request)
                storage.used = True

                # Don't set any message - just redirect silently
                # User knows the wipe was successful because they'll be on login page

                # Redirect to login since the current session is now invalid
                return redirect('accounts:login')

            except Exception as e:
                messages.error(request, f'Database reset failed: {str(e)}')
                return render(request, 'accounts/admin_database_wipe.html')

    return render(request, 'accounts/admin_database_wipe.html')


# Email Management API Views

@login_required
@require_http_methods(["POST"])
def add_email(request):
    """Add a new email address to user account (for super_admin and professional only)"""
    import json
    from django.http import JsonResponse
    from .models import UserEmail

    if not request.user.can_have_multiple_emails:
        return JsonResponse({
            'success': False,
            'error': 'Your account type cannot have multiple emails'
        })

    try:
        data = json.loads(request.body)
        email_address = data.get('email', '').strip()

        if not email_address:
            return JsonResponse({'success': False, 'error': 'Email address is required'})

        # Check if email already exists for this user
        if (request.user.email == email_address or
            UserEmail.objects.filter(user=request.user, email_address=email_address).exists()):
            return JsonResponse({'success': False, 'error': 'This email is already associated with your account'})

        # Create new email
        UserEmail.objects.create(
            user=request.user,
            email_address=email_address,
            is_primary=False,  # New emails are never primary by default
            is_verified=False
        )

        return JsonResponse({'success': True})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def remove_email(request):
    """Remove an email address from user account"""
    import json
    from django.http import JsonResponse
    from .models import UserEmail

    try:
        data = json.loads(request.body)
        email_id = data.get('email_id')

        if not email_id:
            return JsonResponse({'success': False, 'error': 'Email ID is required'})

        # Get the email object
        try:
            email_obj = UserEmail.objects.get(id=email_id, user=request.user)
        except UserEmail.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Email not found'})

        # Don't allow removing primary email
        if email_obj.is_primary:
            return JsonResponse({'success': False, 'error': 'Cannot remove primary email address'})

        # Delete the email
        email_obj.delete()

        return JsonResponse({'success': True})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def set_primary_email(request):
    """Set an email address as primary"""
    import json
    from django.http import JsonResponse
    from .models import UserEmail

    try:
        data = json.loads(request.body)
        email_id = data.get('email_id')

        if not email_id:
            return JsonResponse({'success': False, 'error': 'Email ID is required'})

        # Get the email object
        try:
            email_obj = UserEmail.objects.get(id=email_id, user=request.user)
        except UserEmail.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Email not found'})

        # Set as primary (this will automatically unset other primary emails via the model's save method)
        email_obj.is_primary = True
        email_obj.save()

        return JsonResponse({'success': True})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
