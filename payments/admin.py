from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'amount', 'status', 'refund_amount', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('booking__id', 'stripe_payment_intent_id', 'stripe_checkout_session_id')
    readonly_fields = ('stripe_payment_intent_id', 'stripe_checkout_session_id')
