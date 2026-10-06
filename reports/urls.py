from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('report/<slug:business_slug>/', views.submit_report, name='submit_report'),
]
