from django.contrib import admin
from .models import DailyCheckIn


@admin.register(DailyCheckIn)
class DailyCheckInAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'had_transaction', 'is_manual_checkin')
    list_filter = ('had_transaction', 'is_manual_checkin')
    search_fields = ('user__email',)
