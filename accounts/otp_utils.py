"""
OTP utility functions for email verification.
"""
import re

import requests
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings


def send_otp_email(user, otp):
    """
    Send OTP verification email to the user.
    
    Args:
        user: CustomUser instance
        otp: The 6-digit OTP to send
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    if not user.email:
        return False

    site_url = (settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'https://reserva.gr').rstrip('/')
    
    context = {
        'user': user,
        'otp': otp,
        'otp_expires_minutes': 10,
        'verification_url': f"{site_url}/accounts/verify-otp/",
        'site_url': site_url,
    }

    try:
        html_message = render_to_string('accounts/otp_verification_email.html', context)
        
        send_mail(
            subject='Κώδικας Επαλήθευσης Email - Reserva',
            message=f'Ο κωδικός επαλήθευσης σας είναι: {otp}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending OTP email to {user.email}: {str(e)}")
        return False


def resend_otp(user):
    """
    Generate and resend OTP to user.
    
    Args:
        user: CustomUser instance
    
    Returns:
        bool: True if OTP sent successfully, False otherwise
    """
    otp = user.generate_otp()
    return send_otp_email(user, otp)


def _normalize_phone_for_clicksend(phone):
    raw = (phone or '').strip().replace(' ', '').replace('-', '')
    if not raw:
        return ''
    if raw.startswith('+'):
        digits = '+' + re.sub(r'\D', '', raw[1:])
    else:
        digits = re.sub(r'\D', '', raw)

    if digits.startswith('+'):
        return digits
    if digits.startswith('30') and len(digits) >= 12:
        return f'+{digits}'
    if len(digits) == 10:
        return f'+30{digits}'
    return f'+{digits}'


def send_otp_sms(phone, otp):
    """Send OTP to phone via ClickSend SMS."""
    normalized_phone = _normalize_phone_for_clicksend(phone)
    if not normalized_phone:
        return False

    if not all([
        settings.CLICKSEND_USERNAME,
        settings.CLICKSEND_API_KEY,
        settings.CLICKSEND_SENDER_ID,
    ]):
        return False

    payload = {
        'messages': [{
            'source': 'python',
            'from': settings.CLICKSEND_SENDER_ID,
            'to': normalized_phone,
            'body': f'Reserva OTP: {otp}',
        }]
    }

    try:
        response = requests.post(
            'https://rest.clicksend.com/v3/sms/send',
            json=payload,
            auth=(settings.CLICKSEND_USERNAME, settings.CLICKSEND_API_KEY),
            timeout=15,
        )
        response.raise_for_status()
        data = response.json() if response.content else {}
        first_message = ((data.get('data') or {}).get('messages') or [{}])[0]
        status = str(first_message.get('status') or '').upper()
        return status in {'SUCCESS', 'QUEUED', 'SENT'}
    except Exception:
        return False


def send_professional_registration_otps(user):
    """Send professional registration OTPs (email always, phone when mobile)."""
    requires_phone_otp = (user.phone or '').startswith('69')

    email_otp = user.generate_otp()
    if not send_otp_email(user, email_otp):
        return False, requires_phone_otp, 'email'

    if requires_phone_otp:
        phone_otp = user.generate_phone_otp()
        if not send_otp_sms(user.phone, phone_otp):
            return False, True, 'phone'
    else:
        # Landline numbers (starting with 2) are considered already phone-verified.
        user.is_phone_verified = True
        user.phone_otp = None
        user.phone_otp_expires_at = None
        user.save(update_fields=['is_phone_verified', 'phone_otp', 'phone_otp_expires_at'])

    return True, requires_phone_otp, None
