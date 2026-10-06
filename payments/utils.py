"""
Stripe payment utilities — checkout session creation and refund processing.
"""
import stripe
from django.conf import settings
from django.utils import timezone

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_checkout_session(booking, success_url, cancel_url):
    """
    Create a Stripe Checkout Session for the booking deposit.
    Returns the Session object.
    """
    from .models import Payment

    amount_cents = int(booking.deposit_amount * 100)

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'unit_amount': amount_cents,
                'product_data': {
                    'name': f'Προκαταβολή - {booking.service.name}',
                    'description': (
                        f'{booking.business.name} | '
                        f'{booking.date.strftime("%d/%m/%Y")} {booking.start_time.strftime("%H:%M")}'
                    ),
                },
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            'booking_id': str(booking.id),
        },
    )

    # Create Payment record
    Payment.objects.create(
        booking=booking,
        amount=booking.deposit_amount,
        stripe_checkout_session_id=session.id,
        status='pending',
    )

    return session


def process_refund(booking, refund_percentage=100):
    """
    Process a Stripe refund based on cancellation policy.
    refund_percentage: 0, 50, or 100
    """
    from .models import Payment

    if refund_percentage == 0:
        return None

    payment = Payment.objects.filter(
        booking=booking,
        status='succeeded',
    ).first()

    if not payment or not payment.stripe_payment_intent_id:
        return None

    refund_amount = round(float(payment.amount) * refund_percentage / 100, 2)
    refund_amount_cents = int(refund_amount * 100)

    try:
        refund = stripe.Refund.create(
            payment_intent=payment.stripe_payment_intent_id,
            amount=refund_amount_cents,
        )

        payment.refund_amount = refund_amount
        payment.refunded_at = timezone.now()
        if refund_percentage == 100:
            payment.status = 'refunded'
            booking.payment_status = 'refunded'
        else:
            payment.status = 'partially_refunded'
            booking.payment_status = 'partially_refunded'
        payment.save()
        booking.save()

        return refund
    except stripe.error.StripeError:
        return None
