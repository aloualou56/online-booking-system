from django.urls import path
from . import views

app_name = 'public_booking'

urlpatterns = [
    path('', views.booking_page, name='booking_page'),
    path('api/slots/', views.get_slots_api, name='get_slots'),
    path('api/dates/', views.get_dates_api, name='get_dates'),
    path('api/check-duplicate/', views.check_duplicate_booking, name='check_duplicate'),
    path('confirm/', views.booking_confirm, name='booking_confirm'),
    path('create/', views.booking_create, name='booking_create'),
    path('success/<int:booking_id>/', views.booking_success, name='booking_success'),
    path('booking/<str:access_token>/', views.guest_booking_view, name='guest_booking_view'),
    path('booking/<str:access_token>/cancel/', views.guest_cancel_booking, name='guest_cancel_booking'),
]
