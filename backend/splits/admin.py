from django.contrib import admin

from .models import Settlement, SplitExpense, SplitExpenseShare, SplitGroup, SplitGroupMember


class SplitGroupMemberInline(admin.TabularInline):
    model = SplitGroupMember
    extra = 0


@admin.register(SplitGroup)
class SplitGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_by', 'settlement_mode', 'created_at']
    list_filter = ['settlement_mode']
    search_fields = ['name']
    inlines = [SplitGroupMemberInline]


class SplitExpenseShareInline(admin.TabularInline):
    model = SplitExpenseShare
    extra = 0


@admin.register(SplitExpense)
class SplitExpenseAdmin(admin.ModelAdmin):
    list_display = ['description', 'group', 'amount', 'paid_by', 'split_type', 'expense_date']
    list_filter = ['split_type', 'expense_date']
    search_fields = ['description']
    inlines = [SplitExpenseShareInline]


@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    list_display = ['group', 'payer', 'payee', 'amount', 'status', 'generated_at']
    list_filter = ['status']
