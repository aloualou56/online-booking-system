from django.contrib import admin
from .models import Booking, BookingStatusLog


class BookingStatusLogInline(admin.TabularInline):
    model = BookingStatusLog
    extra = 0
    readonly_fields = ('old_status', 'new_status', 'changed_by', 'notes', 'created_at')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'business', 'employee', 'service', 'customer',
        'date', 'start_time', 'status', 'payment_status', 'deposit_amount',
    )
    list_filter = ('status', 'payment_status', 'date', 'business')
    search_fields = (
        'business__name', 'customer__username', 'customer__email',
        'employee__name', 'service__name',
    )
    date_hierarchy = 'date'
    inlines = [BookingStatusLogInline]


@admin.register(BookingStatusLog)
class BookingStatusLogAdmin(admin.ModelAdmin):
    list_display = ('booking', 'old_status', 'new_status', 'changed_by', 'created_at')
    list_filter = ('new_status',)
