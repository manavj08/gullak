from django.contrib import admin
from .models import (
    SharedAccountMember, GroupInvite, GroupOccasion, AdminTransferRequest,
    Notification, SharedContribution,
)


@admin.register(SharedAccountMember)
class SharedAccountMemberAdmin(admin.ModelAdmin):
    list_display = ('account', 'user', 'role', 'joined_at')
    list_filter = ('role',)


@admin.register(GroupInvite)
class GroupInviteAdmin(admin.ModelAdmin):
    list_display = ('account', 'invited_by', 'invited_user', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(GroupOccasion)
class GroupOccasionAdmin(admin.ModelAdmin):
    list_display = ('account', 'name', 'occasion_date', 'reminder_enabled')


@admin.register(AdminTransferRequest)
class AdminTransferRequestAdmin(admin.ModelAdmin):
    list_display = ('account', 'requested_by', 'target_user', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'status', 'actionable', 'created_at')
    list_filter = ('type', 'status', 'actionable')


@admin.register(SharedContribution)
class SharedContributionAdmin(admin.ModelAdmin):
    list_display = ('account', 'user', 'contributed_amount')
