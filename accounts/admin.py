from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, UserEmail


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_approved', 'is_active')
    list_filter = ('role', 'is_approved', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone')
    fieldsets = UserAdmin.fieldsets + (
        ('Reserva', {'fields': ('role', 'phone', 'is_approved')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Reserva', {'fields': ('role', 'phone')}),
    )


@admin.register(UserEmail)
class UserEmailAdmin(admin.ModelAdmin):
    list_display = ('user', 'email_address', 'is_primary', 'is_verified', 'created_at')
    list_filter = ('is_primary', 'is_verified', 'created_at')
    search_fields = ('user__username', 'user__email', 'email_address')
    raw_id_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
