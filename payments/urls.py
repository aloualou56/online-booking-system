from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('checkout/<int:booking_id>/', views.create_checkout, name='create_checkout'),
    path('success/<int:booking_id>/', views.payment_success, name='payment_success'),
    path('cancel/<int:booking_id>/', views.payment_cancel, name='payment_cancel'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
]
