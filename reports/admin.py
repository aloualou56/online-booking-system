from django.contrib import admin
from .models import BusinessReport


@admin.register(BusinessReport)
class BusinessReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'business', 'reporter', 'category', 'status', 'created_at')
    list_filter = ('category', 'status')
    search_fields = ('business__name', 'reporter__username', 'description')
    readonly_fields = ('business', 'reporter', 'booking', 'category', 'description', 'created_at')
