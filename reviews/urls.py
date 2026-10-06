from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    path('submit/<int:booking_id>/', views.submit_review, name='submit_review'),
    path('submit/<int:booking_id>/<str:guest_token>/', views.submit_review, name='submit_review_guest'),
    path('business/<slug:business_slug>/', views.business_reviews, name='business_reviews'),
]
