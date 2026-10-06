from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    path('cancel/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    path('reschedule/<int:booking_id>/', views.reschedule_booking, name='reschedule_booking'),
]
