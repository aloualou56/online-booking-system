from django.contrib import admin
from .models import SMSNotification


@admin.register(SMSNotification)
class SMSNotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient_phone', 'sms_type', 'status', 'sent_at', 'created_at')
    list_filter = ('sms_type', 'status', 'created_at')
    search_fields = ('recipient_phone', 'recipient_name', 'message')
    readonly_fields = ('twilio_sid',)


# News is managed through superadmin panel only, not through Django admin
