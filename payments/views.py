from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import stripe
import json

from bookings.models import Booking
from .models import Payment
from .utils import create_checkout_session


@login_required
def create_checkout(request, booking_id):
    """Create Stripe Checkout Session and redirect."""
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)

    if booking.deposit_amount <= 0:
        messages.info(request, 'Δεν απαιτείται προκαταβολή.')
        return redirect('public_booking:booking_success',
                        business_slug=booking.business.slug,
                        booking_id=booking.id)

    success_url = request.build_absolute_uri(
        f'/payments/success/{booking.id}/'
    )
    cancel_url = request.build_absolute_uri(
        f'/payments/cancel/{booking.id}/'
    )

    try:
        session = create_checkout_session(booking, success_url, cancel_url)
        return redirect(session.url, code=303)
    except Exception as e:
        messages.error(request, f'Σφάλμα πληρωμής: {str(e)}')
        return redirect('public_booking:booking_page',
                        business_slug=booking.business.slug)


@login_required
def payment_success(request, booking_id):
    """Handle successful payment return from Stripe."""
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)

    # Update booking payment status
    booking.payment_status = 'paid'
    booking.save()

    # Send confirmation SMS only for already-confirmed bookings.
    if booking.status == 'confirmed':
        should_send_sms = booking.customer_contact_preference in ['phone', 'both']
        should_send_email = booking.customer_contact_preference in ['email', 'both']

        if should_send_sms:
            from notifications.utils import send_booking_confirmation_sms
            send_booking_confirmation_sms(booking)
        if should_send_email:
            from notifications.utils import send_customer_booking_confirmation_email
            send_customer_booking_confirmation_email(booking)

    messages.success(request, 'Η πληρωμή ολοκληρώθηκε επιτυχώς!')
    return redirect('public_booking:booking_success',
                    business_slug=booking.business.slug,
                    booking_id=booking.id)


@login_required
def payment_cancel(request, booking_id):
    """Handle cancelled payment from Stripe."""
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
    messages.warning(request, 'Η πληρωμή ακυρώθηκε. Μπορείτε να δοκιμάσετε ξανά.')
    return redirect('public_booking:booking_page',
                    business_slug=booking.business.slug)


@csrf_exempt
def stripe_webhook(request):
    """Handle Stripe webhooks for payment events."""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    # Handle checkout.session.completed
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        booking_id = session.get('metadata', {}).get('booking_id')

        if booking_id:
            try:
                payment = Payment.objects.get(
                    stripe_checkout_session_id=session['id']
                )
                payment.stripe_payment_intent_id = session.get('payment_intent', '')
                payment.status = 'succeeded'
                payment.save()

                booking = payment.booking
                booking.payment_status = 'paid'
                booking.save()
            except Payment.DoesNotExist:
                pass

    return HttpResponse(status=200)
