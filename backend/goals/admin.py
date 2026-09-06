from django.contrib import admin
from .models import Goal, PendingGoalDeduction


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'target_amount', 'allocated_amount', 'status', 'is_achieved')
    list_filter = ('status', 'is_achieved')
    search_fields = ('name', 'user__email')


@admin.register(PendingGoalDeduction)
class PendingGoalDeductionAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'resolved', 'created_at')
    list_filter = ('resolved',)
    search_fields = ('user__email',)
