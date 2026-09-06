from django.contrib import admin
from .models import Account, Transaction


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'category', 'account_type', 'unblock_balance', 'block_balance', 'is_archived')
    list_filter = ('category', 'is_archived')
    search_fields = ('name', 'user__email')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'account', 'type', 'amount', 'category', 'settled', 'timestamp')
    list_filter = ('type', 'category', 'settled')
    search_fields = ('user__email', 'account__name', 'note')
