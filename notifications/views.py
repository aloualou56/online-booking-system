from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone
from accounts.decorators import professional_required
from businesses.models import Business
from bookings.models import Booking, BookingStatusLog
from .models import SMSNotification, News


def _get_business_for_notifications(request):
    business = Business.objects.filter(owner=request.user).first()
    if business:
        return business

    from businesses.views import _get_accessible_business
    return _get_accessible_business(request)


@login_required
@professional_required
def notification_center(request):
    """Business notification center with booking activity, SMS and announcements."""
    business = _get_business_for_notifications(request)
    today = timezone.now().date()
    now = timezone.now()

    pending_bookings = Booking.objects.filter(business=business, status='pending').count()
    overdue_bookings = Booking.objects.filter(
        business=business,
        status__in=['pending', 'confirmed'],
    ).filter(
        Q(date__lt=today) | Q(date=today, end_time__lt=now.time())
    ).count()

    recent_activity = BookingStatusLog.objects.filter(
        booking__business=business,
    ).select_related(
        'booking', 'booking__service', 'booking__employee', 'booking__customer', 'changed_by'
    ).order_by('-created_at')[:15]

    sms_notifications = SMSNotification.objects.filter(
        booking__business=business,
    ).select_related('booking').order_by('-created_at')[:15]

    latest_news = News.objects.filter(status='published').order_by('-published_at')[:5]

    context = {
        'business': business,
        'pending_bookings': pending_bookings,
        'overdue_bookings': overdue_bookings,
        'recent_activity': recent_activity,
        'sms_notifications': sms_notifications,
        'latest_news': latest_news,
    }
    return render(request, 'notifications/center.html', context)


@login_required
@professional_required
def sms_log(request):
    """View SMS notification log for the business."""
    from businesses.models import Business
    business = Business.objects.filter(owner=request.user).first()
    if business:
        notifications = SMSNotification.objects.filter(
            booking__business=business
        ).order_by('-created_at')[:100]
    else:
        notifications = SMSNotification.objects.none()

    return render(request, 'notifications/sms_log.html', {
        'notifications': notifications,
    })
