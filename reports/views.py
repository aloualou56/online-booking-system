from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from businesses.models import Business
from bookings.models import Booking
from .models import BusinessReport


@login_required
def submit_report(request, business_slug):
    """Customer submits a report about a business."""
    business = get_object_or_404(Business, slug=business_slug, is_active=True)

    # Optional: link to a specific booking
    booking_id = request.GET.get('booking_id') or request.POST.get('booking_id')
    booking = None
    if booking_id:
        booking = Booking.objects.filter(
            id=booking_id, customer=request.user, business=business
        ).first()

    if request.method == 'POST':
        category = request.POST.get('category', '').strip()
        description = request.POST.get('description', '').strip()

        valid_categories = [c[0] for c in BusinessReport.CATEGORY_CHOICES]
        if category not in valid_categories:
            messages.error(request, 'Παρακαλώ επιλέξτε έγκυρη κατηγορία.')
        elif len(description) < 10:
            messages.error(request, 'Παρακαλώ δώστε μια πιο λεπτομερή περιγραφή (τουλάχιστον 10 χαρακτήρες).')
        else:
            BusinessReport.objects.create(
                business=business,
                reporter=request.user,
                booking=booking,
                category=category,
                description=description,
            )
            messages.success(request, 'Η αναφορά σας υποβλήθηκε επιτυχώς. Θα εξεταστεί από τον διαχειριστή.')
            return redirect('accounts:my_bookings')

    context = {
        'business': business,
        'booking': booking,
        'categories': BusinessReport.CATEGORY_CHOICES,
    }
    return render(request, 'reports/submit_report.html', context)
