from django.contrib import admin
from .models import Business, Employee, Service, WorkingHours, SpecialDayOff


class EmployeeInline(admin.TabularInline):
    model = Employee
    extra = 0


class ServiceInline(admin.TabularInline):
    model = Service
    extra = 0


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'category', 'is_active', 'is_approved', 'auto_confirm', 'requires_deposit')
    list_filter = ('is_active', 'is_approved', 'category', 'auto_confirm')
    search_fields = ('name', 'owner__username', 'owner__email')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [EmployeeInline, ServiceInline]


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'title', 'is_active')
    list_filter = ('is_active', 'business')
    search_fields = ('name', 'business__name')


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'duration_minutes', 'price', 'is_active')
    list_filter = ('is_active', 'business')


@admin.register(WorkingHours)
class WorkingHoursAdmin(admin.ModelAdmin):
    list_display = ('employee', 'day_of_week', 'start_time', 'end_time', 'is_day_off')
    list_filter = ('day_of_week', 'is_day_off')


@admin.register(SpecialDayOff)
class SpecialDayOffAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'reason')
    list_filter = ('date',)
