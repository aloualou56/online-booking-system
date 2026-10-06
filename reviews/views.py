from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from bookings.models import Booking
from .models import Review


def submit_review(request, booking_id, guest_token=None):
    """Submit a review for a completed booking (verified reviews only).
    
    Supports both authenticated customers (via login) and guests (via token).
    """
    # Determine how the user is authenticated
    if guest_token:
        # Guest access via token
        booking = get_object_or_404(
            Booking,
            id=booking_id,
            guest_access_token=guest_token,
            status='completed',
        )
        # Check if guest already reviewed
        if hasattr(booking, 'review'):
            messages.info(request, 'Έχετε ήδη αξιολογήσει αυτό το ραντεβού.')
            return redirect('public_booking:guest_booking_view',
                          business_slug=booking.business.slug,
                          access_token=guest_token)
        is_guest = True
    else:
        # Authenticated customer
        if not request.user.is_authenticated:
            messages.error(request, 'Πρέπει να είστε συνδεδεμένος για να αξιολογήσετε.')
            return redirect('accounts:login')
        
        booking = get_object_or_404(
            Booking,
            id=booking_id,
            customer=request.user,
            status='completed',
        )
        # Check if customer already reviewed
        if hasattr(booking, 'review'):
            messages.info(request, 'Έχετε ήδη αξιολογήσει αυτό το ραντεβού.')
            return redirect('accounts:my_bookings')
        is_guest = False

    if request.method == 'POST':
        rating = request.POST.get('rating', '')
        comment = request.POST.get('comment', '').strip()

        # Validate rating is provided
        if not rating:
            messages.error(request, 'Παρακαλώ επιλέξτε βαθμολογία.')
            context = {
                'booking': booking,
                'business': booking.business,
                'is_guest': is_guest,
                'guest_token': guest_token,
            }
            return render(request, 'reviews/review_form.html', context)

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                rating = 5
        except (ValueError, TypeError):
            messages.error(request, 'Άκυρη βαθμολογία.')
            context = {
                'booking': booking,
                'business': booking.business,
                'is_guest': is_guest,
                'guest_token': guest_token,
            }
            return render(request, 'reviews/review_form.html', context)

        if is_guest:
            review = Review.objects.create(
                business=booking.business,
                booking=booking,
                customer=None,
                guest_name=booking.guest_name,
                guest_email=booking.guest_email,
                rating=rating,
                comment=comment,
                is_verified=True,
            )
        else:
            review = Review.objects.create(
                business=booking.business,
                booking=booking,
                customer=request.user,
                guest_name='',
                guest_email='',
                rating=rating,
                comment=comment,
                is_verified=True,
            )
        
        # Auto-reply if enabled for the business
        if booking.business.auto_reply_enabled:
            review.business_reply = booking.business.auto_reply_template
            review.replied_at = timezone.now()
            review.save(update_fields=['business_reply', 'replied_at'])
        
        messages.success(request, 'Ευχαριστούμε για την αξιολόγησή σας!')
        
        if is_guest:
            return redirect('public_booking:guest_booking_view',
                          business_slug=booking.business.slug,
                          access_token=guest_token)
        else:
            return redirect('accounts:my_bookings')

    context = {
        'booking': booking,
        'business': booking.business,
        'is_guest': is_guest,
        'guest_token': guest_token,
    }
    return render(request, 'reviews/review_form.html', context)


def business_reviews(request, business_slug):
    """Public reviews page for a business."""
    from businesses.models import Business
    business = get_object_or_404(Business, slug=business_slug, is_active=True)
    reviews = Review.objects.filter(business=business, is_verified=True)
    can_reply = request.user.is_authenticated and (
        request.user == business.owner or getattr(request.user, 'role', '') == 'super_admin'
    )

    if request.method == 'POST':
        if not can_reply:
            messages.error(request, 'Δεν έχετε δικαίωμα απάντησης σε αυτή τη σελίδα.')
            return redirect('reviews:business_reviews', business_slug=business_slug)

        review_id = request.POST.get('review_id', '').strip()
        reply_text = request.POST.get('business_reply', '').strip()
        review = get_object_or_404(Review, id=review_id, business=business, is_verified=True)

        if review.business_reply:
            messages.info(request, 'Η κριτική έχει ήδη απαντηθεί.')
            return redirect('reviews:business_reviews', business_slug=business_slug)

        if not reply_text:
            messages.error(request, 'Συμπληρώστε την απάντηση πριν την υποβολή.')
            return redirect('reviews:business_reviews', business_slug=business_slug)

        review.business_reply = reply_text
        review.replied_at = timezone.now()
        review.save(update_fields=['business_reply', 'replied_at'])
        messages.success(request, 'Η απάντηση αποθηκεύτηκε.')
        return redirect('reviews:business_reviews', business_slug=business_slug)

    context = {
        'business': business,
        'reviews': reviews,
        'avg_rating': business.average_rating,
        'review_count': business.review_count,
        'can_reply': can_reply,
    }
    return render(request, 'reviews/review_list.html', context)
