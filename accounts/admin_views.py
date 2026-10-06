from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from .decorators import super_admin_required
from .models import CustomUser
from businesses.models import Business
from bookings.models import Booking
from payments.models import Payment
from reports.models import BusinessReport
from notifications.models import SystemSettings, News, SMSNotification


@login_required
@super_admin_required
def dashboard(request):
    """Super Admin dashboard with platform overview.""" #kalimera
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0)

    total_users = CustomUser.objects.count()
    active_pros = CustomUser.objects.filter(
        role='professional', is_approved=True, is_active=True
    ).count()
    month_bookings = Booking.objects.filter(created_at__gte=month_start).count()
    mrr = Payment.objects.filter(
        status='succeeded', created_at__gte=month_start
    ).aggregate(total=Sum('amount'))['total'] or 0

    pending_count = CustomUser.objects.filter(
        role='professional', is_approved=False, is_active=True
    ).count()
    pending_pros = CustomUser.objects.filter(
        role='professional', is_approved=False, is_active=True
    ).order_by('-date_joined')[:10]

    new_reports_count = BusinessReport.objects.filter(status='new').count()
    system_settings = SystemSettings.get_solo()
    contact_pref_email = Booking.objects.filter(
        Q(customer__isnull=False, customer_contact_preference='email') |
        Q(customer__isnull=True, guest_contact_preference='email')
    ).count()
    contact_pref_phone = Booking.objects.filter(
        Q(customer__isnull=False, customer_contact_preference='phone') |
        Q(customer__isnull=True, guest_contact_preference='phone')
    ).count()
    contact_pref_both = Booking.objects.filter(
        Q(customer__isnull=False, customer_contact_preference='both') |
        Q(customer__isnull=True, guest_contact_preference='both')
    ).count()

    context = {
        'stats': {
            'total_users': total_users,
            'active_pros': active_pros,
            'month_bookings': month_bookings,
            'mrr': mrr,
            'contact_pref_email': contact_pref_email,
            'contact_pref_phone': contact_pref_phone,
            'contact_pref_both': contact_pref_both,
        },
        'pending_count': pending_count,
        'pending_pros': pending_pros,
        'new_reports_count': new_reports_count,
        'sms_enabled': system_settings.sms_enabled,
    }
    return render(request, 'admin_panel/dashboard.html', context)


@login_required
@super_admin_required
def toggle_sms_system(request):
    """Super Admin: globally enable/disable SMS sending."""
    if request.method != 'POST':
        return redirect('superadmin:dashboard')

    system_settings = SystemSettings.get_solo()
    system_settings.sms_enabled = not system_settings.sms_enabled
    system_settings.save(update_fields=['sms_enabled'])

    if system_settings.sms_enabled:
        messages.success(request, 'Η αποστολή SMS ενεργοποιήθηκε ξανά.')
    else:
        messages.warning(request, 'Η αποστολή SMS απενεργοποιήθηκε προσωρινά.')

    return redirect('superadmin:dashboard')


@login_required
@super_admin_required
def pending_professionals(request):
    """List professionals awaiting approval."""
    pending = CustomUser.objects.filter(
        role='professional', is_approved=False, is_active=True
    ).select_related().order_by('-date_joined')

    pending_with_biz = [
        {'user': user, 'business': Business.objects.filter(owner=user).first()}
        for user in pending
    ]

    context = {
        'pending_with_biz': pending_with_biz,
    }
    return render(request, 'admin_panel/pending_professionals.html', context)


@login_required
@super_admin_required
def approve_professional(request, user_id):
    """Approve a professional account."""
    user = get_object_or_404(CustomUser, id=user_id, role='professional')
    user.is_approved = True
    user.save()

    # Also activate their business
    Business.objects.filter(owner=user).update(is_approved=True, is_active=True)

    # Send approval email
    if user.email:
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        from django.conf import settings

        business = Business.objects.filter(owner=user).first()
        site_url = (settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'https://reserva.gr').rstrip('/')

        context = {
            'user': user,
            'business': business,
            'login_url': f"{site_url}/accounts/login/",
            'public_url': f"{site_url}/b/{business.slug}/" if business and business.slug else '',
            'privacy_url': f"{site_url}/privacy/",
            'terms_url': f"{site_url}/terms/",
            'contact_url': f"{site_url}/contact/",
        }

        html_message = render_to_string('accounts/business_approved_email.html', context)

        try:
            send_mail(
                subject='Η Επιχείρησή σας Εγκρίθηκε! - Reserva',
                message=(
                    f"Γεια σας {user.get_full_name() or user.username},\n\n"
                    f"Η επιχείρησή σας {business.name if business else ''} εγκρίθηκε και είναι πλέον ενεργή στο Reserva.\n"
                    f"Σύνδεση: {site_url}/accounts/login/\n\n"
                    "Η Ομάδα του Reserva"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            messages.success(request, f'Ο {user.get_full_name()} εγκρίθηκε και ενημερώθηκε με email!')
        except Exception as e:
            messages.success(request, f'Ο {user.get_full_name()} εγκρίθηκε! (Email απέτυχε: {str(e)})')
    else:
        messages.success(request, f'Ο {user.get_full_name()} εγκρίθηκε!')

    return redirect('superadmin:pending_professionals')


@login_required
@super_admin_required
def reject_professional(request, user_id):
    """Reject/delete a professional account."""
    if request.method != 'POST':
        return redirect('superadmin:pending_professionals')
    user = get_object_or_404(CustomUser, id=user_id, role='professional')
    name = user.get_full_name() or user.username
    Business.objects.filter(owner=user).delete()
    user.delete()
    messages.info(request, f'Ο {name} απορρίφθηκε και διαγράφηκε.')
    return redirect('superadmin:pending_professionals')


@login_required
@super_admin_required
def manage_professionals(request):
    """List all approved professionals."""
    professionals = CustomUser.objects.filter(
        role='professional', is_approved=True
    ).order_by('-date_joined')

    data = []
    for pro in professionals:
        biz = Business.objects.filter(owner=pro).first()
        booking_count = Booking.objects.filter(business=biz).count() if biz else 0
        data.append({
            'user': pro,
            'business': biz,
            'booking_count': booking_count,
        })

    context = {'professionals': data}
    return render(request, 'admin_panel/manage_professionals.html', context)


@login_required
@super_admin_required
def manage_customers(request):
    """List all customer accounts for moderation actions."""
    customers = CustomUser.objects.filter(role='customer').order_by('-date_joined')
    context = {'customers': customers}
    return render(request, 'admin_panel/manage_customers.html', context)


@login_required
@super_admin_required
def toggle_customer(request, user_id):
    """Ban/unban customer by toggling is_active."""
    if request.method != 'POST':
        return redirect('superadmin:manage_customers')

    user = CustomUser.objects.filter(id=user_id).first()
    if not user or user.role != 'customer':
        messages.error(request, 'Ο συγκεκριμένος χρήστης δεν βρέθηκε ως πελάτης.')
        return redirect('superadmin:manage_customers')

    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])

    status = 'ενεργοποιήθηκε' if user.is_active else 'απενεργοποιήθηκε'
    messages.info(request, f'Ο πελάτης {user.get_full_name() or user.username} {status}.')
    return redirect('superadmin:manage_customers')


@login_required
@super_admin_required
def delete_customer(request, user_id):
    """Super Admin: confirm and permanently delete a customer account."""
    user = CustomUser.objects.filter(id=user_id).first()
    if not user or user.role != 'customer':
        messages.error(request, 'Ο συγκεκριμένος χρήστης δεν βρέθηκε ως πελάτης.')
        return redirect('superadmin:manage_customers')

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, 'Παρακαλώ γράψτε τον λόγο διαγραφής.')
            return render(request, 'admin_panel/delete_customer.html', {'customer': user})

        customer_email = user.email
        customer_name = user.get_full_name() or user.username
        email_sent = False
        email_error = None

        if customer_email:
            from django.conf import settings
            from django.core.mail import send_mail
            from django.template.loader import render_to_string

            context = {
                'customer_name': customer_name,
                'reason': reason,
                'support_email': settings.DEFAULT_FROM_EMAIL,
            }
            html_message = render_to_string('accounts/customer_deleted_by_admin_email.html', context)
            plain_message = (
                f'Γεια σας {customer_name},\n\n'
                'Ο λογαριασμός σας στην Reserva διαγράφηκε από τη διαχείριση.\n'
                f'Λόγος: {reason}\n\n'
                f'Για διευκρινίσεις μπορείτε να επικοινωνήσετε στο {settings.DEFAULT_FROM_EMAIL}.\n'
            )

            try:
                sent_count = send_mail(
                    subject='Ο λογαριασμός σας διαγράφηκε - Reserva',
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[customer_email],
                    html_message=html_message,
                    fail_silently=False,
                )
                email_sent = sent_count > 0
                if not email_sent:
                    email_error = 'Δεν στάλθηκε email (0 μηνύματα στάλθηκαν).'
            except Exception as exc:
                email_error = str(exc)
        else:
            email_error = 'Ο πελάτης δεν έχει αποθηκευμένο email.'

        user.delete()

        if email_sent:
            messages.success(request, f'Ο πελάτης {customer_name} διαγράφηκε οριστικά και στάλθηκε email ενημέρωσης.')
        else:
            messages.warning(
                request,
                f'Ο πελάτης {customer_name} διαγράφηκε οριστικά, αλλά το email δεν στάλθηκε. {email_error or ""}'.strip()
            )
        return redirect('superadmin:manage_customers')

    return render(request, 'admin_panel/delete_customer.html', {'customer': user})


@login_required
@super_admin_required
def toggle_professional(request, user_id):
    """Activate/deactivate a professional."""
    user = get_object_or_404(CustomUser, id=user_id, role='professional')
    user.is_active = not user.is_active
    user.save()
    Business.objects.filter(owner=user).update(is_active=user.is_active)
    status = 'ενεργοποιήθηκε' if user.is_active else 'απενεργοποιήθηκε'
    messages.info(request, f'Ο {user.get_full_name()} {status}.')
    return redirect('superadmin:manage_professionals')


@login_required
@super_admin_required
def professional_detail(request, user_id):
    """Detailed profile view of a professional for Super Admin."""
    user = get_object_or_404(CustomUser, id=user_id, role='professional')
    business = Business.objects.filter(owner=user).first()
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0)

    bookings_qs = Booking.objects.filter(business=business) if business else Booking.objects.none()
    stats = {
        'total': bookings_qs.count(),
        'completed': bookings_qs.filter(status='completed').count(),
        'cancelled': bookings_qs.filter(status='cancelled').count(),
        'no_shows': bookings_qs.filter(status='no_show').count(),
        'pending': bookings_qs.filter(status='pending').count(),
        'confirmed': bookings_qs.filter(status='confirmed').count(),
        'month': bookings_qs.filter(created_at__gte=month_start).count(),
    }
    revenue = Payment.objects.filter(
        booking__business=business, status='succeeded'
    ).aggregate(total=Sum('amount'))['total'] or 0 if business else 0
    month_revenue = Payment.objects.filter(
        booking__business=business, status='succeeded', created_at__gte=month_start
    ).aggregate(total=Sum('amount'))['total'] or 0 if business else 0
    recent_bookings = bookings_qs.select_related('service', 'employee', 'customer').order_by('-created_at')[:5]

    context = {
        'pro': user,
        'business': business,
        'stats': stats,
        'revenue': revenue,
        'month_revenue': month_revenue,
        'recent_bookings': recent_bookings,
    }
    return render(request, 'admin_panel/professional_detail.html', context)


@login_required
@super_admin_required
def platform_stats(request):
    """Detailed platform statistics."""
    now = timezone.now()
    last_30 = now - timedelta(days=30)
    month_start = now.replace(day=1, hour=0, minute=0, second=0)

    stats = {
        'total_users': CustomUser.objects.count(),
        'total_customers': CustomUser.objects.filter(role='customer').count(),
        'active_pros': CustomUser.objects.filter(role='professional', is_approved=True, is_active=True).count(),
        'mrr': CustomUser.objects.filter(role='professional', is_approved=True, is_active=True).count() * 25,
        'total_bookings': Booking.objects.count(),
        'completed': Booking.objects.filter(status='completed').count(),
        'cancelled': Booking.objects.filter(status='cancelled').count(),
        'no_shows': Booking.objects.filter(status='no_show').count(),
        'month_bookings': Booking.objects.filter(created_at__gte=last_30).count(),
        'month_cancelled': Booking.objects.filter(status='cancelled', created_at__gte=month_start).count(),
        'total_sms': SMSNotification.objects.filter(status='sent').count(),
        'contact_pref_email': Booking.objects.filter(
            Q(customer__isnull=False, customer_contact_preference='email') |
            Q(customer__isnull=True, guest_contact_preference='email')
        ).count(),
        'contact_pref_phone': Booking.objects.filter(
            Q(customer__isnull=False, customer_contact_preference='phone') |
            Q(customer__isnull=True, guest_contact_preference='phone')
        ).count(),
        'contact_pref_both': Booking.objects.filter(
            Q(customer__isnull=False, customer_contact_preference='both') |
            Q(customer__isnull=True, guest_contact_preference='both')
        ).count(),
        'total_revenue': Payment.objects.filter(status='succeeded').aggregate(
            total=Sum('amount'))['total'] or 0,
        'month_revenue': Payment.objects.filter(
            status='succeeded', created_at__gte=last_30
        ).aggregate(total=Sum('amount'))['total'] or 0,
        'total_refunds': Payment.objects.filter(
            refund_amount__gt=0
        ).aggregate(total=Sum('refund_amount'))['total'] or 0,
        'total_reviews': 0,
        'avg_rating': None,
    }

    try:
        from reviews.models import Review
        stats['total_reviews'] = Review.objects.count()
        avg_rating = Review.objects.aggregate(avg=Avg('rating'))['avg']
        stats['avg_rating'] = round(float(avg_rating), 2) if avg_rating is not None else None
    except Exception:
        pass

    context = {'stats': stats}
    return render(request, 'admin_panel/stats.html', context)


@login_required
@super_admin_required
def admin_reports(request):
    """Super Admin: view all business reports."""
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')

    reports = BusinessReport.objects.select_related(
        'business', 'reporter', 'booking'
    ).order_by('-created_at')

    if category_filter:
        reports = reports.filter(category=category_filter)
    if status_filter:
        reports = reports.filter(status=status_filter)

    # Handle status update from admin
    if request.method == 'POST':
        report_id = request.POST.get('report_id')
        new_status = request.POST.get('new_status')
        admin_notes = request.POST.get('admin_notes', '').strip()
        report = get_object_or_404(BusinessReport, id=report_id)
        valid_statuses = [s[0] for s in BusinessReport.STATUS_CHOICES]
        if new_status in valid_statuses:
            report.status = new_status
            if admin_notes:
                report.admin_notes = admin_notes
            report.save()
            messages.success(request, f'Αναφορά #{report.id} ενημερώθηκε.')
        return redirect(request.path + (f'?category={category_filter}&status={status_filter}' if category_filter or status_filter else ''))

    counts = {
        'new': BusinessReport.objects.filter(status='new').count(),
        'under_review': BusinessReport.objects.filter(status='under_review').count(),
        'resolved': BusinessReport.objects.filter(status='resolved').count(),
        'dismissed': BusinessReport.objects.filter(status='dismissed').count(),
    }

    context = {
        'reports': reports,
        'categories': BusinessReport.CATEGORY_CHOICES,
        'statuses': BusinessReport.STATUS_CHOICES,
        'active_category': category_filter,
        'active_status': status_filter,
        'counts': counts,
    }
    return render(request, 'admin_panel/reports.html', context)


@login_required
@super_admin_required
def business_deletion_requests(request):
    """Super Admin: view pending business deletion requests."""
    from businesses.models import BusinessDeletionRequest

    status_filter = request.GET.get('status', 'pending')

    deletion_requests = BusinessDeletionRequest.objects.select_related(
        'business', 'owner', 'reviewed_by'
    ).order_by('-requested_at')

    if status_filter:
        deletion_requests = deletion_requests.filter(status=status_filter)

    counts = {
        'pending': BusinessDeletionRequest.objects.filter(status='pending').count(),
        'approved': BusinessDeletionRequest.objects.filter(status='approved').count(),
        'rejected': BusinessDeletionRequest.objects.filter(status='rejected').count(),
        'cancelled': BusinessDeletionRequest.objects.filter(status='cancelled').count(),
    }

    statuses_with_counts = [
        (status_value, status_label, counts.get(status_value, 0))
        for status_value, status_label in BusinessDeletionRequest._meta.get_field('status').choices
    ]

    context = {
        'deletion_requests': deletion_requests,
        'statuses_with_counts': statuses_with_counts,
        'active_status': status_filter,
        'counts': counts,
    }
    return render(request, 'admin_panel/business_deletion_requests.html', context)


@login_required
@super_admin_required
def delete_business_deletion_request(request, request_id):
    """Super Admin: permanently delete a business deletion request record."""
    from businesses.models import BusinessDeletionRequest

    if request.method != 'POST':
        return redirect('superadmin:business_deletion_requests')

    deletion_request = get_object_or_404(BusinessDeletionRequest, id=request_id)
    business_name = deletion_request.business.name
    deletion_request.delete()
    messages.success(request, f'Το αίτημα διαγραφής για την επιχείρηση {business_name} διαγράφηκε.')
    return redirect('superadmin:business_deletion_requests')


@login_required
@super_admin_required
def approve_business_deletion(request, request_id):
    """Super Admin: approve business deletion (deactivates business)."""
    from businesses.models import BusinessDeletionRequest

    deletion_request = get_object_or_404(BusinessDeletionRequest, id=request_id)

    if deletion_request.status != 'pending':
        messages.error(request, 'Αυτό το αίτημα δεν είναι σε κατάσταση αναμονής.')
        return redirect('superadmin:business_deletion_requests')

    if request.method == 'POST':
        admin_notes = request.POST.get('admin_notes', '').strip()

        # Deactivate the business instead of deleting
        business = deletion_request.business
        business.is_active = False
        business.save(update_fields=['is_active'])

        # Mark the owner as deactivated
        owner = deletion_request.owner
        owner.is_deactivated = True
        owner.save(update_fields=['is_deactivated'])

        # Update deletion request
        deletion_request.status = 'approved'
        deletion_request.reviewed_by = request.user
        deletion_request.reviewed_at = timezone.now()
        deletion_request.admin_notes = admin_notes
        deletion_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'admin_notes'])

        # Send email to owner
        if owner.email:
            from django.core.mail import send_mail
            from django.template.loader import render_to_string

            context = {
                'user': owner,
                'business': business,
                'admin_notes': admin_notes,
            }
            html_message = render_to_string('businesses/business_deletion_approved_email.html', context)
            try:
                send_mail(
                    subject=f'Αίτημα Διαγραφής Επιχείρησης Εγκρίθηκε - Reserva',
                    message=f'Το αίτημα διαγραφής για {business.name} εγκρίθηκε.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[owner.email],
                    html_message=html_message,
                    fail_silently=True,
                )
            except Exception:
                pass

        messages.success(request, f'Η επιχείρηση {business.name} απενεργοποιήθηκε.')
        return redirect('superadmin:business_deletion_requests')

    context = {'deletion_request': deletion_request}
    return render(request, 'admin_panel/approve_business_deletion.html', context)


@login_required
@super_admin_required
def reject_business_deletion(request, request_id):
    """Super Admin: reject business deletion request."""
    from businesses.models import BusinessDeletionRequest

    deletion_request = get_object_or_404(BusinessDeletionRequest, id=request_id)

    if deletion_request.status != 'pending':
        messages.error(request, 'Αυτό το αίτημα δεν είναι σε κατάσταση αναμονής.')
        return redirect('superadmin:business_deletion_requests')

    if request.method == 'POST':
        admin_notes = request.POST.get('admin_notes', '').strip()

        deletion_request.status = 'rejected'
        deletion_request.reviewed_by = request.user
        deletion_request.reviewed_at = timezone.now()
        deletion_request.admin_notes = admin_notes
        deletion_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'admin_notes'])

        # Send email to owner
        owner = deletion_request.owner
        if owner.email:
            from django.core.mail import send_mail
            from django.template.loader import render_to_string

            context = {
                'user': owner,
                'business': deletion_request.business,
                'admin_notes': admin_notes,
            }
            html_message = render_to_string('businesses/business_deletion_rejected_email.html', context)
            try:
                send_mail(
                    subject=f'Αίτημα Διαγραφής Επιχείρησης Απορρίφθηκε - Reserva',
                    message=f'Το αίτημα διαγραφής για {deletion_request.business.name} απορρίφθηκε.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[owner.email],
                    html_message=html_message,
                    fail_silently=True,
                )
            except Exception:
                pass

        messages.info(request, 'Το αίτημα απορρίφθηκε και ο ιδιοκτήτης ειδοποιήθηκε.')
        return redirect('superadmin:business_deletion_requests')

    context = {'deletion_request': deletion_request}
    return render(request, 'admin_panel/reject_business_deletion.html', context)


# ==================== NEWS MANAGEMENT ====================

@login_required
@super_admin_required
def manage_news(request):
    """Super Admin: List and manage news announcements."""
    status_filter = request.GET.get('status', '')
    search_q = request.GET.get('q', '').strip()
    
    news_qs = News.objects.all().order_by('-published_at', '-created_at')
    
    if status_filter:
        news_qs = news_qs.filter(status=status_filter)
    
    if search_q:
        news_qs = news_qs.filter(
            Q(title_gr__icontains=search_q) | 
            Q(title_en__icontains=search_q) |
            Q(description_gr__icontains=search_q) |
            Q(description_en__icontains=search_q)
        )
    
    # Count by status
    stats = {
        'total': News.objects.count(),
        'published': News.objects.filter(status='published').count(),
        'draft': News.objects.filter(status='draft').count(),
    }
    
    context = {
        'news_list': news_qs,
        'stats': stats,
        'status_filter': status_filter,
        'search_q': search_q,
    }
    return render(request, 'admin_panel/manage_news.html', context)


@login_required
@super_admin_required
def create_news(request):
    """Super Admin: Create new news announcement."""
    if request.method == 'POST':
        title_gr = request.POST.get('title_gr', '').strip()
        title_en = request.POST.get('title_en', '').strip()
        description_gr = request.POST.get('description_gr', '').strip()
        description_en = request.POST.get('description_en', '').strip()
        content_gr = request.POST.get('content_gr', '').strip()
        content_en = request.POST.get('content_en', '').strip()
        status = request.POST.get('status', 'draft')
        image = request.FILES.get('image')
        
        # Validation
        if not (title_gr and title_en and description_gr and description_en):
            messages.error(request, 'Παρακαλώ συμπληρώστε τίτλο και περιγραφή σε και στις δύο γλώσσες.')
            context = {
                'title_gr': title_gr,
                'title_en': title_en,
                'description_gr': description_gr,
                'description_en': description_en,
                'content_gr': content_gr,
                'content_en': content_en,
                'status': status,
            }
            return render(request, 'admin_panel/create_news.html', context)
        
        # Create news
        news = News(
            title_gr=title_gr,
            title_en=title_en,
            description_gr=description_gr,
            description_en=description_en,
            content_gr=content_gr,
            content_en=content_en,
            status=status,
            created_by=request.user,
        )
        
        # Auto-set published_at if published
        if status == 'published':
            news.published_at = timezone.now()
        
        news.save()
        
        messages.success(request, f'Η ειδήσεις "{title_gr}" δημιουργήθηκαν επιτυχώς.')
        return redirect('superadmin:manage_news')
    
    context = {}
    return render(request, 'admin_panel/create_news.html', context)


@login_required
@super_admin_required
def edit_news(request, news_id):
    """Super Admin: Edit news announcement."""
    news = get_object_or_404(News, id=news_id)
    
    if request.method == 'POST':
        title_gr = request.POST.get('title_gr', '').strip()
        title_en = request.POST.get('title_en', '').strip()
        description_gr = request.POST.get('description_gr', '').strip()
        description_en = request.POST.get('description_en', '').strip()
        content_gr = request.POST.get('content_gr', '').strip()
        content_en = request.POST.get('content_en', '').strip()
        status = request.POST.get('status', 'draft')
        
        # Validation
        if not (title_gr and title_en and description_gr and description_en):
            messages.error(request, 'Παρακαλώ συμπληρώστε τίτλο και περιγραφή σε και στις δύο γλώσσες.')
            context = {
                'news': news,
                'title_gr': title_gr,
                'title_en': title_en,
                'description_gr': description_gr,
                'description_en': description_en,
                'content_gr': content_gr,
                'content_en': content_en,
                'status': status,
            }
            return render(request, 'admin_panel/edit_news.html', context)
        
        # Check if status changed from draft to published
        status_changed_to_published = (news.status == 'draft' and status == 'published')
        
        # Update news
        news.title_gr = title_gr
        news.title_en = title_en
        news.description_gr = description_gr
        news.description_en = description_en
        news.content_gr = content_gr
        news.content_en = content_en
        news.status = status
        
        # Set published_at if transitioning to published
        if status_changed_to_published:
            news.published_at = timezone.now()
        
        news.save()
        
        messages.success(request, f'Η ειδήσεις "{title_gr}" ενημερώθηκαν επιτυχώς.')
        return redirect('superadmin:manage_news')
    
    context = {'news': news}
    return render(request, 'admin_panel/edit_news.html', context)


@login_required
@super_admin_required
def delete_news(request, news_id):
    """Super Admin: Delete news announcement."""
    news = get_object_or_404(News, id=news_id)
    
    if request.method == 'POST':
        title = news.title_gr
        news.delete()
        messages.success(request, f'Η ειδήσεις "{title}" διαγράφηκαν.')
        return redirect('superadmin:manage_news')
    
    context = {'news': news}
    return render(request, 'admin_panel/delete_news.html', context)


@login_required
@super_admin_required
def toggle_news_status(request, news_id):
    """Super Admin: Toggle news status between draft and published."""
    news = get_object_or_404(News, id=news_id)
    
    if news.status == 'draft':
        news.status = 'published'
        news.published_at = timezone.now()
        messages.success(request, f'Η ειδήσεις "{news.title_gr}" δημοσιεύθηκαν.')
    else:
        news.status = 'draft'
        news.published_at = None
        messages.info(request, f'Η ειδήσεις "{news.title_gr}" επαναφέρθηκαν σε σχέδιο.')
    
    news.save(update_fields=['status', 'published_at'])
    
    return redirect('superadmin:manage_news')


@login_required
@super_admin_required
def business_access(request):
    """Super Admin: list businesses that opted in for troubleshooting access."""
    query = (request.GET.get('q') or '').strip()
    businesses = Business.objects.filter(
        allow_superadmin_troubleshooting_access=True,
    ).select_related('owner').order_by('name')

    if query:
        businesses = businesses.filter(
            Q(name__icontains=query)
            | Q(owner__email__icontains=query)
            | Q(owner__first_name__icontains=query)
            | Q(owner__last_name__icontains=query)
        )

    context = {
        'businesses': businesses,
        'query': query,
        'active_access_business_id': request.session.get('superadmin_business_access_id'),
    }
    return render(request, 'admin_panel/business_access.html', context)


@login_required
@super_admin_required
def enter_business_access(request, business_id):
    """Super Admin: enter opted-in business panel for troubleshooting."""
    business = get_object_or_404(
        Business,
        id=business_id,
        allow_superadmin_troubleshooting_access=True,
    )

    request.session['superadmin_business_access_id'] = business.id
    request.session['superadmin_business_access_name'] = business.name
    messages.success(request, f'Εισήλθατε στο panel της επιχείρησης "{business.name}" για troubleshooting.')
    return redirect('businesses:dashboard')


@login_required
@super_admin_required
def exit_business_access(request):
    """Super Admin: exit troubleshooting mode and return to superadmin panel."""
    active_name = request.session.get('superadmin_business_access_name')
    request.session.pop('superadmin_business_access_id', None)
    request.session.pop('superadmin_business_access_name', None)

    if active_name:
        messages.info(request, f'Βγήκατε από το business panel "{active_name}".')
    else:
        messages.info(request, 'Η λειτουργία troubleshooting έκλεισε.')
    return redirect('superadmin:business_access')
