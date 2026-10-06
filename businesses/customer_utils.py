from django.db.models import F
from django.utils import timezone

from .models import BusinessCustomer


def _normalize_phone(phone):
    raw = (phone or '').strip()
    return ''.join(ch for ch in raw if ch.isdigit())


def build_customer_identity_key(booking):
    if booking.customer_id:
        return f'user:{booking.customer_id}'

    phone = booking.customer_phone or booking.guest_phone or ''
    phone = _normalize_phone(phone)
    if phone:
        return f'phone:{phone}'

    email = (booking.guest_email or '').strip().lower()
    if email:
        return f'email:{email}'

    return f'booking:{booking.id}'


def _display_name_from_booking(booking):
    if booking.customer_id and booking.customer:
        full_name = booking.customer.get_full_name().strip()
        if full_name:
            return full_name
        return booking.customer.username

    return (booking.guest_name or booking.customer_phone or booking.guest_phone or 'Επισκέπτης').strip()


def upsert_business_customer_from_booking(booking):
    """Create or update a business customer record from a booking."""
    business = booking.business
    identity_key = build_customer_identity_key(booking)
    display_name = _display_name_from_booking(booking)
    phone = (booking.customer_phone or booking.guest_phone or '').strip()
    email = ''
    if booking.customer_id and booking.customer:
        email = (booking.customer.email or '').strip()
        phone = phone or (booking.customer.phone or '').strip()
    else:
        email = (booking.guest_email or '').strip()

    customer = None
    if booking.customer_id:
        customer = BusinessCustomer.objects.filter(business=business, identity_key=identity_key).first()
        if not customer and phone:
            customer = BusinessCustomer.objects.filter(business=business, phone=phone).first()
        if not customer and email:
            customer = BusinessCustomer.objects.filter(business=business, email__iexact=email).first()
    else:
        if phone:
            customer = BusinessCustomer.objects.filter(business=business, phone=phone).first()
        if not customer and email:
            customer = BusinessCustomer.objects.filter(business=business, email__iexact=email).first()

    defaults = {
        'display_name': display_name,
        'phone': phone,
        'email': email,
        'user': booking.customer if booking.customer_id else None,
        'last_booking_at': booking.created_at or timezone.now(),
    }

    if customer:
        changed_fields = []
        if customer.identity_key != identity_key:
            customer.identity_key = identity_key
            changed_fields.append('identity_key')
        if customer.display_name != display_name:
            customer.display_name = display_name
            changed_fields.append('display_name')
        if phone and customer.phone != phone:
            customer.phone = phone
            changed_fields.append('phone')
        if email and customer.email.lower() != email.lower():
            customer.email = email
            changed_fields.append('email')
        if booking.customer_id and customer.user_id != booking.customer_id:
            customer.user = booking.customer
            changed_fields.append('user')
        customer.booking_count = F('booking_count') + 1
        customer.last_booking_at = booking.created_at or timezone.now()
        customer.save(update_fields=changed_fields + ['booking_count', 'last_booking_at', 'updated_at'])
        customer.refresh_from_db()
        return customer

    customer = BusinessCustomer.objects.create(
        business=business,
        identity_key=identity_key,
        display_name=display_name,
        phone=phone,
        email=email,
        user=booking.customer if booking.customer_id else None,
        booking_count=1,
        last_booking_at=booking.created_at or timezone.now(),
    )
    return customer


def business_customer_queryset(business):
    return BusinessCustomer.objects.filter(business=business).select_related('user').order_by('display_name')
