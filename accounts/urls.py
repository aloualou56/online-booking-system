from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_customer, name='register_customer'),
    path('register/professional/', views.register_professional, name='register_professional'),
    
    # Email verification with OTP
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.resend_verification_otp, name='resend_otp'),
    path('verify-professional-otp/', views.verify_professional_otp, name='verify_professional_otp'),
    path('resend-professional-otp/', views.resend_professional_verification_otp, name='resend_professional_otp'),
    
    # Account deletion
    path('delete-account/', views.delete_account, name='delete_account'),
    
    # Business deletion request
    path('request-business-deletion/', views.request_business_deletion, name='request_business_deletion'),
    
    path('redirect/', views.redirect_after_login, name='redirect_after_login'),
    path('welcome/', views.welcome_flow, name='welcome_flow'),
    path('welcome/complete/', views.complete_welcome_flow, name='complete_welcome_flow'),
    path('pending/', views.pending_approval, name='pending_approval'),
    path('profile/', views.profile, name='profile'),
    path('profile/send-password-change-email/', views.send_password_change_email, name='send_password_change_email'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('exit-customer-mode/', views.exit_customer_mode, name='exit_customer_mode'),
    path('switch-account/', views.switch_account, name='switch_account'),
    path('switch-account/<int:user_id>/', views.perform_account_switch, name='perform_account_switch'),
    path('help/', views.customer_help, name='customer_help'),

    # Employee invitation acceptance
    path('employee-invitation/<str:token>/', views.accept_employee_invitation, name='accept_employee_invitation'),

    # Employee portal
    path('employee/', views.employee_dashboard, name='employee_dashboard'),
    path('employee/help/', views.employee_help, name='employee_help'),
    path('employee/switch-workplace/<int:employee_id>/', views.switch_employee_workplace, name='switch_employee_workplace'),
    path('employee/bookings/', views.employee_bookings, name='employee_bookings'),
    path('employee/bookings/<int:booking_id>/confirm/', views.employee_confirm_booking, name='employee_confirm_booking'),
    path('employee/bookings/<int:booking_id>/reject/', views.employee_reject_booking, name='employee_reject_booking'),
    path('employee/bookings/<int:booking_id>/no-show/', views.employee_mark_no_show, name='employee_mark_no_show'),
    path('employee/bookings/<int:booking_id>/completed/', views.employee_mark_completed, name='employee_mark_completed'),
    path('employee/add-day-off/', views.employee_add_day_off, name='employee_add_day_off'),
    path('employee/day-off/<int:dayoff_id>/remove/', views.employee_remove_day_off, name='employee_remove_day_off'),
    path('employee/day-off/<int:dayoff_id>/chat/', views.employee_absence_request_detail, name='employee_absence_request_detail'),

    # Email Management APIs
    path('add-email/', views.add_email, name='add_email'),
    path('remove-email/', views.remove_email, name='remove_email'),
    path('set-primary-email/', views.set_primary_email, name='set_primary_email'),

    # Admin Database Management (Super Admin Only)
    path('admin/database-wipe/', views.admin_database_wipe, name='admin_database_wipe'),

    # Password Reset URLs
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='accounts/password_reset.html',
             email_template_name='accounts/password_reset_email.txt',
             html_email_template_name='accounts/password_reset_email.html',
             subject_template_name='accounts/password_reset_subject.txt',
             success_url='/accounts/password-reset/done/'
         ),
         name='password_reset'),

    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/password_reset_done.html'
         ),
         name='password_reset_done'),

    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password_reset_confirm.html',
             success_url='/accounts/password-reset-complete/'
         ),
         name='password_reset_confirm'),

    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/password_reset_complete.html'
         ),
         name='password_reset_complete'),
]
