from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'phone', 'is_staff', 'is_active')
    search_fields = ('email', 'username', 'phone')
    fieldsets = UserAdmin.fieldsets + (
        ('Gullak Profile', {'fields': ('phone', 'daily_reminder_time')}),
    )
