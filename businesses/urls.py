from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'businesses'

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='businesses:dashboard', permanent=False)),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('settings/', views.business_settings, name='settings'),
    path('tutorial/', views.tutorial, name='tutorial'),

    # Employees
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/add/', views.add_employee, name='add_employee'),
    path('employees/<int:employee_id>/edit/', views.edit_employee, name='edit_employee'),
    path('employees/<int:employee_id>/delete/', views.delete_employee, name='delete_employee'),
    path('employees/toggle-accounts/', views.toggle_employee_accounts, name='toggle_employee_accounts'),
    path('employees/toggle-booking-actions/', views.toggle_employee_booking_actions, name='toggle_employee_booking_actions'),
    path('employees/<int:employee_id>/invite/', views.send_employee_invitation, name='send_employee_invitation'),
    path('employees/<int:employee_id>/resend-invite/', views.resend_employee_invitation, name='resend_employee_invitation'),

    # Services
    path('services/', views.service_list, name='service_list'),
    path('services/add/', views.add_service, name='add_service'),
    path('services/<int:service_id>/edit/', views.edit_service, name='edit_service'),
    path('services/<int:service_id>/delete/', views.delete_service, name='delete_service'),

    # Schedule
    path('schedule/<int:employee_id>/', views.schedule_view, name='schedule'),
    path('schedule/<int:employee_id>/dayoff/', views.add_day_off, name='add_day_off'),
    path('dayoff/<int:dayoff_id>/delete/', views.delete_day_off, name='delete_day_off'),

    # Bookings Management
    path('bookings/', views.booking_list, name='booking_list'),
    path('bookings/add/', views.manual_booking_add, name='manual_booking_add'),
    path('bookings/export/csv/', views.export_bookings_csv, name='export_bookings_csv'),
    path('bookings/export/xlsx/', views.export_bookings_xlsx, name='export_bookings_xlsx'),
    path('bookings/<int:booking_id>/confirm/', views.approve_booking, name='confirm_booking'),
    path('bookings/<int:booking_id>/approve/', views.approve_booking, name='approve_booking'),
    path('bookings/<int:booking_id>/reject/', views.reject_booking, name='reject_booking'),
    path('bookings/<int:booking_id>/no-show/', views.mark_no_show, name='mark_no_show'),
    path('bookings/<int:booking_id>/completed/', views.mark_completed, name='mark_completed'),

    # Customers
    path('customers/', views.customers_list, name='customers_list'),

    # Employee quick availability toggle
    path('employees/<int:employee_id>/toggle-today/', views.toggle_employee_today, name='toggle_employee_today'),

    # Business temporary closures
    path('closures/', views.business_closures, name='closures'),
    path('closures/<int:closure_id>/delete/', views.delete_business_closure, name='delete_closure'),

    # Reviews
    path('reviews/', views.owner_reviews, name='reviews'),

    # Absence Request Management
    path('absence-requests/', views.absence_requests, name='absence_requests'),
    path('absence-requests/<int:request_id>/approve/', views.approve_absence_request, name='approve_absence_request'),
    path('absence-requests/<int:request_id>/reject/', views.reject_absence_request, name='reject_absence_request'),
    path('absence-requests/<int:request_id>/', views.absence_request_detail, name='absence_request_detail'),

    # Notification Contacts
    path('notification-contacts/', views.notification_contacts, name='notification_contacts'),
    path('notification-contacts/add/', views.add_notification_contact, name='add_notification_contact'),
    path('notification-contacts/<int:contact_id>/delete/', views.delete_notification_contact, name='delete_notification_contact'),
]
