from django.contrib import admin
from .models import ExpenseEntry, ExpenseShare, Settlement


class ExpenseShareInline(admin.TabularInline):
    model = ExpenseShare
    extra = 0


@admin.register(ExpenseEntry)
class ExpenseEntryAdmin(admin.ModelAdmin):
    list_display = ['description', 'account', 'paid_by', 'amount', 'split_type', 'expense_date']
    list_filter = ['category', 'split_type']
    search_fields = ['description', 'account__name']
    inlines = [ExpenseShareInline]


@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    list_display = ['account', 'payer', 'payee', 'amount', 'status', 'generated_at']
    list_filter = ['status']
