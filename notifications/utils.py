"""
SMS notification utilities using ClickSend.
All SMS functions are fail-safe - they log errors but never crash the app.
"""
import logging
import re
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from .models import SMSNotification, SystemSettings

logger = logging.getLogger(__name__)
ALLOWED_SMS_TYPES = {
    'confirmation',
    'reminder',
    'approved',
    'rejected',
    'cancellation',
    'review_invite',
    'new_booking',
    'new_business',
}


def _extract_site_host():
    """Return host[:port] without scheme for compact SMS links."""
    site_url = (settings.SITE_URL or '').strip()
    if not site_url:
        return 'reserva.gr'

    candidate = site_url if '://' in site_url else f'https://{site_url}'
    parsed = urlparse(candidate)
    host = parsed.netloc or parsed.path
    return host.strip('/').lower() or 'reserva.gr'


def _get_short_link_host():
    """Host used in compact guest links (can be overridden in settings)."""
    preferred = (getattr(settings, 'SMS_SHORT_LINK_HOST', '') or '').strip().lower().strip('/')
    if preferred:
        return preferred
    host = _extract_site_host()
    # Keep host compact for short-message constraints.
    if len(host) > 22:
        return 'reserva.gr'
    return host


def _build_guest_short_code(booking):
    """Short temporary guest code: <booking_id_hex>-<token_prefix>."""
    token = (booking.guest_access_token or '').strip()
    if not token:
        return ''
    return f'{booking.id:x}-{token[:8]}'


def build_guest_short_url(booking):
    """Return compact URL for guest booking details/cancel page."""
    token = (booking.guest_access_token or '').strip()
    if not token:
        return ''

    host = _get_short_link_host()
    base_prefix = f'{booking.id:x}-'

    # Keep URL within 40 chars: <host>/g/<idhex>-<tokenprefix>
    max_token_len = 40 - len(host) - len('/g/') - len(base_prefix)
    if max_token_len < 4:
        return ''

    code = f'{base_prefix}{token[:max_token_len]}'
    return f'{host}/g/{code}'


def _is_sms_globally_enabled():
    """Return whether SMS sending is globally enabled by Super Admin."""
    return SystemSettings.get_solo().sms_enabled


def get_business_notification_contacts(business, contact_type=None):
    """
    Get all notification contacts for a business.
    Returns a list of contact values (emails or phones).
    If contact_type is None, returns all types.
    """
    contacts = []

    # Primary business contact
    if contact_type in (None, 'email') and business.email:
        contacts.append(business.email)
    if contact_type in (None, 'phone') and business.phone:
        contacts.append(business.phone)

    # Owner contact if no business contact
    if contact_type in (None, 'email') and not business.email and business.owner.email:
        contacts.append(business.owner.email)
    if contact_type in (None, 'phone') and not business.phone and business.owner.phone:
        contacts.append(business.owner.phone)

    # Additional notification contacts
    from businesses.models import NotificationContact
    additional_contacts = NotificationContact.objects.filter(
        business=business,
        is_active=True
    )

    if contact_type:
        additional_contacts = additional_contacts.filter(contact_type=contact_type)

    for contact in additional_contacts:
        contacts.append(contact.value)

    return list(set(contacts))  # Remove duplicates


def get_superadmin_notification_contacts(contact_type=None):
    """
    Get all notification contacts for super_admin users.
    Returns a list of contact values (emails or phones).
    If contact_type is None, returns all types.
    """
    from accounts.models import CustomUser
    from businesses.models import NotificationContact

    contacts = []

    # Primary super_admin contacts
    super_admins = CustomUser.objects.filter(role='super_admin')

    for admin in super_admins:
        if contact_type in (None, 'email') and admin.email:
            contacts.append(admin.email)
        if contact_type in (None, 'phone') and admin.phone:
            contacts.append(admin.phone)

        # Additional notification contacts for this admin
        additional_contacts = NotificationContact.objects.filter(
            user=admin,
            is_active=True
        )

        if contact_type:
            additional_contacts = additional_contacts.filter(contact_type=contact_type)

        for contact in additional_contacts:
            contacts.append(contact.value)

    return list(set(contacts))  # Remove duplicates


def _get_customer_info(booking):
    """Return (phone, name) for a booking — handles both registered and guest bookings."""
    if booking.customer:
        # For authenticated users, prefer the stored booking phone, then profile phone
        phone = booking.customer_phone or booking.customer.phone or ''
        return phone, booking.customer.get_full_name()
    return booking.guest_phone or '', booking.guest_name or 'Επισκέπτης'


def _normalize_phone_for_clicksend(phone):
    """Normalize GR phone numbers to E.164 format expected by ClickSend."""
    raw = (phone or '').strip()
    if not raw:
        return ''

    raw = raw.replace(' ', '').replace('-', '')
    if raw.startswith('+'):
        digits = '+' + re.sub(r'\D', '', raw[1:])
    else:
        digits = re.sub(r'\D', '', raw)

    if not digits:
        return ''

    if digits.startswith('+'):
        return digits
    if digits.startswith('30') and len(digits) >= 12:
        return f'+{digits}'
    if len(digits) == 10:
        return f'+30{digits}'
    return f'+{digits}'


def _send_sms(phone, message, booking=None, sms_type='confirmation', recipient_name=''):
    """
    Internal: Send an SMS via ClickSend and log it.
    Returns the SMSNotification record.
    """
    if sms_type not in ALLOWED_SMS_TYPES:
        logger.info('Skipping unsupported SMS type: %s', sms_type)
        return None

    normalized_phone = _normalize_phone_for_clicksend(phone)
    if not normalized_phone:
        logger.warning('Skipping SMS because phone is invalid: %s', phone)
        return None

    notification = SMSNotification.objects.create(
        booking=booking,
        recipient_phone=normalized_phone,
        recipient_name=recipient_name,
        message=message,
        sms_type=sms_type,
        status='pending',
    )

    if not _is_sms_globally_enabled():
        notification.status = 'failed'
        notification.error_message = 'SMS disabled by Super Admin'
        notification.save(update_fields=['status', 'error_message'])
        logger.info('SMS skipped because global SMS toggle is OFF.')
        return notification

    if not all([
        settings.CLICKSEND_USERNAME,
        settings.CLICKSEND_API_KEY,
        settings.CLICKSEND_SENDER_ID,
    ]):
        logger.warning(f'ClickSend not configured. SMS to {normalized_phone} NOT sent: {message[:50]}...')
        notification.status = 'failed'
        notification.error_message = 'ClickSend credentials not configured'
        notification.save()
        return notification

    def _attempt_send(endpoint, payload, channel_label):
        response = requests.post(
            endpoint,
            json=payload,
            auth=(settings.CLICKSEND_USERNAME, settings.CLICKSEND_API_KEY),
            timeout=15,
        )
        response.raise_for_status()
        response_json = response.json() if response.content else {}
        first_message = ((response_json.get('data') or {}).get('messages') or [{}])[0]
        provider_message_id = first_message.get('message_id', '')
        provider_status = str(first_message.get('status') or '').upper()
        provider_text = first_message.get('status_text') or f'{channel_label} status: {provider_status or "UNKNOWN"}'
        ok = provider_status in {'SUCCESS', 'QUEUED', 'SENT'}
        return ok, provider_message_id, provider_text

    try:
        sms_payload = {
            'messages': [{
                'source': 'python',
                'from': settings.CLICKSEND_SENDER_ID,
                'to': normalized_phone,
                'body': message,
            }]
        }
        ok, msg_id, status_text = _attempt_send('https://rest.clicksend.com/v3/sms/send', sms_payload, 'SMS')
        notification.twilio_sid = msg_id
        if ok:
            notification.status = 'sent'
            notification.sent_at = timezone.now()
            notification.save(update_fields=['twilio_sid', 'status', 'sent_at'])
            logger.info('SMS sent via ClickSend to %s', normalized_phone)
        else:
            notification.status = 'failed'
            notification.error_message = status_text
            notification.save(update_fields=['twilio_sid', 'status', 'error_message'])
            logger.warning('SMS failed for %s: %s', normalized_phone, status_text)
    except Exception as e:
        notification.status = 'failed'
        notification.error_message = str(e)
        notification.save(update_fields=['status', 'error_message'])
        logger.error(f'SMS failed to {normalized_phone}: {e}')

    return notification


def send_booking_confirmation_sms(booking):
    """SMS to customer: booking confirmed."""
    phone, name = _get_customer_info(booking)
    if not phone:
        return None

    if not booking.customer and booking.guest_access_token:
        guest_url = build_guest_short_url(booking)
        if guest_url:
            return _send_sms(
                phone,
                guest_url,
                booking=booking,
                sms_type='confirmation',
                recipient_name=name,
            )

    host = _extract_site_host()
    message = (
        f'Reserva OK {booking.date.strftime("%d/%m")} {booking.start_time.strftime("%H:%M")}. '
        f'{host}/accounts/my-bookings/'
    )
    return _send_sms(
        phone, message, booking=booking,
        sms_type='confirmation',
        recipient_name=name,
    )


def send_booking_confirmed_sms(booking):
    """SMS to customer: booking approved by professional (manual approval)."""
    phone, name = _get_customer_info(booking)
    if not phone:
        return None

    if not booking.customer and booking.guest_access_token:
        guest_url = build_guest_short_url(booking)
        if guest_url:
            return _send_sms(
                phone,
                guest_url,
                booking=booking,
                sms_type='approved',
                recipient_name=name,
            )

    host = _extract_site_host()
    message = (
        f'Reserva approved {booking.date.strftime("%d/%m")} {booking.start_time.strftime("%H:%M")}. '
        f'{host}/accounts/my-bookings/'
    )
    return _send_sms(
        phone, message, booking=booking,
        sms_type='approved',
        recipient_name=name,
    )


def send_booking_approval_notifications(booking):
    """Send approval notifications based on the booking contact preference."""
    preference = (
        booking.customer_contact_preference
        if booking.customer_id
        else booking.guest_contact_preference
    ) or 'both'

    logger.info(f'Approval notification for booking {booking.id}: preference={preference}, customer_id={booking.customer_id}, phone={booking.customer_phone or booking.guest_phone}')
    
    should_send_sms = preference in ('phone', 'both')
    should_send_email = preference in ('email', 'both')

    if should_send_sms:
        logger.info(f'Sending SMS for booking {booking.id}')
        send_booking_confirmed_sms(booking)
    else:
        logger.info(f'Skipping SMS for booking {booking.id}: preference={preference}')

    if should_send_email:
        logger.info(f'Sending email for booking {booking.id}')
        if booking.customer_id and booking.customer and booking.customer.email:
            send_customer_booking_confirmation_email(booking)
        elif booking.guest_email:
            send_guest_booking_confirmation_email(booking)
    else:
        logger.info(f'Skipping email for booking {booking.id}: preference={preference}')


def send_booking_rejected_sms(booking):
    """SMS to customer: booking rejected by professional."""
    phone, name = _get_customer_info(booking)
    if not phone:
        return None

    message = (
        f'Reserva: Λυπούμαστε, το ραντεβού σας δεν εγκρίθηκε.\n'
        f'📍 {booking.business.name}\n'
        f'📅 {booking.date.strftime("%d/%m/%Y")} στις {booking.start_time.strftime("%H:%M")}\n'
        f'Μπορείτε να κλείσετε νέο ραντεβού: {settings.SITE_URL}/b/{booking.business.slug}/'
    )
    return _send_sms(
        phone, message, booking=booking,
        sms_type='rejected',
        recipient_name=name,
    )


def send_booking_rejected_email(booking):
    """Email to customer/guest: booking rejected by business with reason."""
    customer_email = booking.customer.email if booking.customer and booking.customer.email else booking.guest_email
    if not customer_email:
        return

    customer_name = booking.customer.get_full_name() if booking.customer else (booking.guest_name or 'πελάτη')
    reason = (booking.rejection_reason or '').strip() or 'Δεν δόθηκε συγκεκριμένος λόγος.'
    booking_url = f'{settings.SITE_URL}/b/{booking.business.slug}/'

    try:
        context = {
            'booking': booking,
            'customer_name': customer_name,
            'rejection_reason': reason,
            'booking_url': booking_url,
        }
        html_content = render_to_string('emails/booking_rejected.html', context)

        subject = f'Απόρριψη Ραντεβού - {booking.business.name}'
        text_content = (
            f'Γεια σας {customer_name},\n\n'
            f'Το ραντεβού σας στο {booking.business.name} για {booking.date.strftime("%d/%m/%Y")} '
            f'στις {booking.start_time.strftime("%H:%M")} απορρίφθηκε.\n\n'
            f'Λόγος απόρριψης:\n{reason}\n\n'
            f'Μπορείτε να κλείσετε νέο ραντεβού εδώ: {booking_url}\n\n'
            'Reserva'
        )

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[customer_email],
        )
        email.attach_alternative(html_content, 'text/html')
        email.send(fail_silently=True)
        logger.info(f'Rejection email sent to {customer_email} for booking {booking.id}')
    except Exception as e:
        logger.error(f'Failed to send rejection email for booking {booking.id}: {e}')


def send_business_closed_cancellation_sms(booking, closure_reason=''):
    """SMS to customer: booking cancelled because business is closed that day."""
    phone, name = _get_customer_info(booking)
    if not phone:
        return None

    reason_part = f' Λόγος: {closure_reason}' if closure_reason else ''
    message = (
        f'Reserva: Το ραντεβού σας ακυρώθηκε γιατί η επιχείρηση θα είναι κλειστή εκείνη την ημέρα.\n'
        f'📍 {booking.business.name}\n'
        f'📅 {booking.date.strftime("%d/%m/%Y")} στις {booking.start_time.strftime("%H:%M")}\n'
        f'Θα λάβετε πλήρη επιστροφή όπου υπάρχει πληρωμή.{reason_part}\n'
        f'Νέα κράτηση: {settings.SITE_URL}/b/{booking.business.slug}/'
    )
    return _send_sms(
        phone,
        message,
        booking=booking,
        sms_type='cancellation',
        recipient_name=name,
    )


def send_business_closed_cancellation_email(booking, closure_reason=''):
    """Email to customer/guest: booking cancelled because business is closed that day."""
    customer_email = booking.customer.email if booking.customer and booking.customer.email else booking.guest_email
    if not customer_email:
        return

    customer_name = booking.customer.get_full_name() if booking.customer else (booking.guest_name or 'πελάτη')
    reason = (closure_reason or '').strip() or 'Η επιχείρηση παραμένει κλειστή για την επιλεγμένη ημερομηνία.'
    booking_url = f'{settings.SITE_URL}/b/{booking.business.slug}/'

    try:
        context = {
            'booking': booking,
            'customer_name': customer_name,
            'closure_reason': reason,
            'booking_url': booking_url,
        }
        html_content = render_to_string('emails/business_closed_cancellation.html', context)

        subject = f'Ακύρωση Ραντεβού - {booking.business.name} (Κλείσιμο Επιχείρησης)'
        text_content = (
            f'Γεια σας {customer_name},\n\n'
            f'Το ραντεβού σας στο {booking.business.name} για {booking.date.strftime("%d/%m/%Y")} '
            f'στις {booking.start_time.strftime("%H:%M")} ακυρώθηκε, γιατί η επιχείρηση θα είναι κλειστή εκείνη την ημέρα.\n\n'
            f'Λόγος:\n{reason}\n\n'
            f'Θα λάβετε πλήρη επιστροφή όπου υπάρχει πληρωμή.\n'
            f'Μπορείτε να κλείσετε νέο ραντεβού εδώ: {booking_url}\n\n'
            'Reserva'
        )

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[customer_email],
        )
        email.attach_alternative(html_content, 'text/html')
        email.send(fail_silently=True)
        logger.info(f'Business-closure cancellation email sent to {customer_email} for booking {booking.id}')
    except Exception as e:
        logger.error(f'Failed to send business-closure cancellation email for booking {booking.id}: {e}')


def send_reminder_sms(booking):
    """SMS reminder to business before appointment time."""
    phones = get_business_notification_contacts(booking.business, contact_type='phone')
    if not phones:
        return None

    customer_name = booking.customer.get_full_name() if booking.customer else (booking.guest_name or 'Επισκέπτης')
    message = (
        f'Reserva: Υπενθύμιση ραντεβού σε λίγο.\n'
        f'👤 {customer_name}\n'
        f'📅 {booking.date.strftime("%d/%m/%Y")} στις {booking.start_time.strftime("%H:%M")}\n'
        f'💈 {booking.service.name} ({booking.employee.name})\n'
        f'Διαχείριση: {settings.SITE_URL}/business/bookings/'
    )
    first_result = None
    for phone in phones:
        result = _send_sms(
            phone,
            message,
            booking=booking,
            sms_type='reminder',
            recipient_name=booking.business.name,
        )
        if result and first_result is None:
            first_result = result
    return first_result


def send_review_invite_sms(booking):
    """SMS after appointment: invite to leave a review."""
    phone, name = _get_customer_info(booking)
    if not phone:
        return None

    message = (
        f'Reserva: Πώς ήταν η εμπειρία σας στο {booking.business.name};\n'
        f'Αφήστε μια αξιολόγηση: {settings.SITE_URL}/reviews/submit/{booking.id}/'
    )
    result = _send_sms(
        phone, message, booking=booking,
        sms_type='review_invite',
        recipient_name=name,
    )
    if result and result.status == 'sent':
        booking.review_invite_sent = True
        booking.save(update_fields=['review_invite_sent'])
    return result


def send_cancellation_sms(booking, refund_percentage):
    """SMS to customer: booking cancelled with refund info."""
    phone, name = _get_customer_info(booking)
    if not phone:
        return None

    refund_text = {
        100: 'Θα λάβετε πλήρη επιστροφή.',
        50: 'Θα λάβετε 50% επιστροφή.',
        0: 'Δεν δικαιούστε επιστροφή (< 24 ώρες).',
    }.get(refund_percentage, '')

    message = (
        f'Reserva: Το ραντεβού σας ακυρώθηκε.\n'
        f'📍 {booking.business.name}\n'
        f'📅 {booking.date.strftime("%d/%m/%Y")} στις {booking.start_time.strftime("%H:%M")}\n'
        f'{refund_text}'
    )
    return _send_sms(
        phone, message, booking=booking,
        sms_type='cancellation',
        recipient_name=name,
    )


def send_new_booking_notification(booking):
    """SMS to business owner: new booking received (manual approval)."""
    phones = get_business_notification_contacts(booking.business, contact_type='phone')
    if not phones:
        return None

    _, customer_name = _get_customer_info(booking)
    message = (
        f'Reserva: Νέο ραντεβού προς έγκριση!\n'
        f'👤 {customer_name}\n'
        f'📅 {booking.date.strftime("%d/%m/%Y")} στις {booking.start_time.strftime("%H:%M")}\n'
        f'💈 {booking.service.name}\n'
        f'Διαχείριση: {settings.SITE_URL}/business/bookings/'
    )

    notifications = []
    for phone in phones:
        notification = _send_sms(
            phone, message, booking=booking,
            sms_type='new_booking',
            recipient_name=booking.business.name,
        )
        notifications.append(notification)

    return notifications[0] if notifications else None


def send_new_business_application_sms(business):
    """SMS to every Super Admin: a business is waiting for approval."""
    phones = get_superadmin_notification_contacts(contact_type='phone')
    if not phones:
        logger.info('No Super Admin phone contacts; skipping new business SMS.')
        return None

    owner = getattr(business, 'owner', None)
    owner_name = ''
    if owner:
        owner_name = owner.get_full_name() or owner.username

    message = (
        f'Reserva: Νέα αίτηση επιχείρησης προς έγκριση!\n'
        f'🏢 {business.name}\n'
        f'👤 {owner_name}\n'
        f'Έγκριση: {settings.SITE_URL}/superadmin/pending/'
    )

    notifications = []
    # A Super Admin can register more than one phone, so de-duplicate first.
    for phone in dict.fromkeys(phones):
        notification = _send_sms(
            phone, message,
            sms_type='new_business',
            recipient_name='Super Admin',
        )
        notifications.append(notification)

    return notifications[0] if notifications else None


def send_employee_new_booking_email(booking):
    """Email to assigned employee when a new booking is created or reassigned."""
    employee = getattr(booking, 'employee', None)
    if not employee or not employee.user or not employee.user.email:
        return

    customer_name = booking.customer.get_full_name() if booking.customer else (booking.guest_name or 'Επισκέπτης')
    subject = f'Νέο Ραντεβού: {booking.business.name} - {booking.date.strftime("%d/%m/%Y")} {booking.start_time.strftime("%H:%M")}'
    text_content = (
        f'Γεια σας {employee.name},\n\n'
        f'Σας ανατέθηκε νέο ραντεβού.\n'
        f'Επιχείρηση: {booking.business.name}\n'
        f'Πελάτης: {customer_name}\n'
        f'Ημερομηνία: {booking.date.strftime("%d/%m/%Y")}\n'
        f'Ώρα: {booking.start_time.strftime("%H:%M")}-{booking.end_time.strftime("%H:%M")}\n'
        f'Υπηρεσία: {booking.service.name}\n\n'
        f'Διαχείριση: {settings.SITE_URL}/accounts/employee/bookings/\n\n'
        'Reserva'
    )

    try:
        send_mail(
            subject=subject,
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[employee.user.email],
            fail_silently=True,
        )
        logger.info('Employee booking email sent to %s for booking %s', employee.user.email, booking.id)
    except Exception as exc:
        logger.error('Failed employee booking email for booking %s: %s', booking.id, exc)


def send_guest_booking_confirmation_email(booking):
    """
    Send confirmation email to guest with booking details and access link.
    This is fail-safe — logs errors but never crashes the app.
    """
    if not booking.guest_email or not booking.guest_access_token:
        logger.warning(f'Cannot send email for booking {booking.id}: missing email or token')
        return

    try:
        # Build booking access URL
        access_url = f'{settings.SITE_URL}/b/{booking.business.slug}/booking/{booking.guest_access_token}/'

        # Email context
        context = {
            'booking': booking,
            'business': booking.business,
            'access_url': access_url,
        }

        # Render HTML email
        html_content = render_to_string('emails/guest_booking_confirmation.html', context)

        # Create email
        subject = f'Επιβεβαίωση Κράτησης - {booking.business.name}'
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = booking.guest_email

        email = EmailMultiAlternatives(
            subject=subject,
            body=f'Το ραντεβού σας επιβεβαιώθηκε. Δείτε τις λεπτομέρειες εδώ: {access_url}',
            from_email=from_email,
            to=[to_email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=True)

        logger.info(f'Confirmation email sent to {to_email} for booking {booking.id}')
    except Exception as e:
        logger.error(f'Failed to send confirmation email for booking {booking.id}: {e}')


def send_customer_booking_confirmation_email(booking):
    """Email confirmation for authenticated customer bookings."""
    if not booking.customer or not booking.customer.email:
        return

    customer_email = booking.customer.email
    customer_name = booking.customer.get_full_name() or booking.customer.username

    try:
        subject = f'Επιβεβαίωση Ραντεβού - {booking.business.name}'
        text_content = (
            f'Γεια σας {customer_name},\n\n'
            f'Το ραντεβού σας επιβεβαιώθηκε στο {booking.business.name}.\n'
            f'Ημερομηνία: {booking.date.strftime("%d/%m/%Y")}\n'
            f'Ώρα: {booking.start_time.strftime("%H:%M")}\n'
            f'Υπηρεσία: {booking.service.name}\n\n'
            f'Διαχείριση ραντεβού: {settings.SITE_URL}/accounts/my-bookings/\n\n'
            'Reserva'
        )

        send_mail(
            subject=subject,
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer_email],
            fail_silently=True,
        )
        logger.info(f'Customer confirmation email sent to {customer_email} for booking {booking.id}')
    except Exception as e:
        logger.error(f'Failed to send customer confirmation email for booking {booking.id}: {e}')


def send_business_booking_cancelled_email(booking, cancelled_by='customer'):
    """Notify business contacts by email when a booking is cancelled by customer/guest."""
    emails = get_business_notification_contacts(booking.business, contact_type='email')
    if not emails:
        return

    actor = 'πελάτη' if cancelled_by == 'customer' else 'επισκέπτη'
    customer_name = booking.customer.get_full_name() if booking.customer else (booking.guest_name or 'Επισκέπτης')

    try:
        subject = f'Ακύρωση Ραντεβού - {booking.business.name}'
        text_content = (
            f'Ακυρώθηκε ραντεβού από {actor}.\n\n'
            f'Πελάτης: {customer_name}\n'
            f'Ημερομηνία: {booking.date.strftime("%d/%m/%Y")}\n'
            f'Ώρα: {booking.start_time.strftime("%H:%M")}\n'
            f'Υπηρεσία: {booking.service.name}\n'
            f'Υπάλληλος: {booking.employee.name}\n\n'
            f'Διαχείριση: {settings.SITE_URL}/business/bookings/\n\n'
            'Reserva'
        )

        send_mail(
            subject=subject,
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=emails,
            fail_silently=True,
        )
        logger.info(f'Business cancellation email sent for booking {booking.id} to {len(emails)} recipient(s)')
    except Exception as e:
        logger.error(f'Failed to send business cancellation email for booking {booking.id}: {e}')

