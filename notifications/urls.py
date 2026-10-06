from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_center, name='center'),
    path('sms-log/', views.sms_log, name='sms_log'),
]
