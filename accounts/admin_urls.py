from django.urls import path
from . import admin_views

app_name = 'superadmin'

urlpatterns = [
    path('', admin_views.dashboard, name='dashboard'),
    path('pending/', admin_views.pending_professionals, name='pending_professionals'),
    path('approve/<int:user_id>/', admin_views.approve_professional, name='approve_professional'),
    path('reject/<int:user_id>/', admin_views.reject_professional, name='reject_professional'),
    path('professionals/', admin_views.manage_professionals, name='manage_professionals'),
    path('professionals/<int:user_id>/', admin_views.professional_detail, name='professional_detail'),
    path('toggle/<int:user_id>/', admin_views.toggle_professional, name='toggle_professional'),
    path('customers/', admin_views.manage_customers, name='manage_customers'),
    path('customers/<int:user_id>/toggle/', admin_views.toggle_customer, name='toggle_customer'),
    path('customers/<int:user_id>/delete/', admin_views.delete_customer, name='delete_customer'),
    path('stats/', admin_views.platform_stats, name='platform_stats'),
    path('reports/', admin_views.admin_reports, name='admin_reports'),
    path('toggle-sms-system/', admin_views.toggle_sms_system, name='toggle_sms_system'),
    
    # Business deletion requests
    path('business-deletions/', admin_views.business_deletion_requests, name='business_deletion_requests'),
    path('business-deletions/<int:request_id>/approve/', admin_views.approve_business_deletion, name='approve_business_deletion'),
    path('business-deletions/<int:request_id>/reject/', admin_views.reject_business_deletion, name='reject_business_deletion'),
    path('business-deletions/<int:request_id>/delete/', admin_views.delete_business_deletion_request, name='delete_business_deletion_request'),
    
    # News management
    path('news/', admin_views.manage_news, name='manage_news'),
    path('news/create/', admin_views.create_news, name='create_news'),
    path('news/<int:news_id>/edit/', admin_views.edit_news, name='edit_news'),
    path('news/<int:news_id>/delete/', admin_views.delete_news, name='delete_news'),
    path('news/<int:news_id>/toggle-status/', admin_views.toggle_news_status, name='toggle_news_status'),

    # Business troubleshooting access
    path('business-access/', admin_views.business_access, name='business_access'),
    path('business-access/<int:business_id>/enter/', admin_views.enter_business_access, name='enter_business_access'),
    path('business-access/exit/', admin_views.exit_business_access, name='exit_business_access'),
]
