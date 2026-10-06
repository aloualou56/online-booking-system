from django.conf import settings
from django.core.mail import send_mail

from accounts.otp_utils import send_otp_sms


def generate_guest_booking_otp():
    from secrets import choice
    from string import digits

    return ''.join(choice(digits) for _ in range(6))


def send_guest_booking_otp_email(guest_email, business_name, otp):
    if not guest_email:
        return False

    subject = f'Κωδικός επιβεβαίωσης κράτησης - {business_name}'
    message = (
        f'Ο κωδικός επιβεβαίωσης για την κράτησή σας στο {business_name} είναι: {otp}\n\n'
        'Ο κωδικός ισχύει για 10 λεπτά.'
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[guest_email],
            fail_silently=False,
        )
        return True
    except Exception:
        return False


def send_guest_booking_otp_sms(guest_phone, business_name, otp):
    if not guest_phone:
        return False

    return send_otp_sms(guest_phone, otp=otp) if otp else False


def send_guest_booking_otps(
    guest_email,
    guest_phone,
    business_name,
    email_otp,
    sms_otp,
    send_email=True,
    send_sms=True,
):
    email_ok = True
    sms_ok = True
    if send_email:
        email_ok = send_guest_booking_otp_email(guest_email, business_name, email_otp)
    if send_sms:
        sms_ok = send_guest_booking_otp_sms(guest_phone, business_name, sms_otp)
    return email_ok and sms_ok
