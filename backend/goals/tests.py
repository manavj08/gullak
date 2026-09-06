from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APITestCase

from wallet.models import Account, AccountCategory
from wallet import services as wallet_services
from .models import Goal, GoalStatus, PendingGoalDeduction
from . import services

User = get_user_model()


def make_user(email='u@example.com'):
    return User.objects.create_user(username=email.split('@')[0], email=email, password='StrongPass123!')


class AddFundsToGoalTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.acc = Account.objects.create(
            user=self.user, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('100.00'), block_balance=Decimal('0.00'),
        )
        wallet_services.block_funds(user=self.user, account=self.acc, amount=Decimal('50.00'))  # Gullak = 50

    def test_add_funds_within_gullak_succeeds(self):
        goal = Goal.objects.create(user=self.user, name='Phone', target_amount=Decimal('200.00'))
        services.add_funds_to_goal(user=self.user, goal=goal, add_amount=Decimal('30.00'))
        goal.refresh_from_db()
        self.assertEqual(goal.allocated_amount, Decimal('30.00'))
        self.assertEqual(goal.status, GoalStatus.ON_TRACK)

    def test_add_funds_is_incremental_not_absolute(self):
        goal = Goal.objects.create(user=self.user, name='Phone', target_amount=Decimal('200.00'))
        services.add_funds_to_goal(user=self.user, goal=goal, add_amount=Decimal('10.00'))
        services.add_funds_to_goal(user=self.user, goal=goal, add_amount=Decimal('15.00'))
        goal.refresh_from_db()
        self.assertEqual(goal.allocated_amount, Decimal('25.00'))

    def test_over_allocation_across_multiple_goals_is_blocked(self):
        goal1 = Goal.objects.create(user=self.user, name='Phone', target_amount=Decimal('200.00'))
        goal2 = Goal.objects.create(user=self.user, name='Trip', target_amount=Decimal('200.00'))
        services.add_funds_to_goal(user=self.user, goal=goal1, add_amount=Decimal('30.00'))
        with self.assertRaises(ValidationError):
            services.add_funds_to_goal(user=self.user, goal=goal2, add_amount=Decimal('30.00'))  # 30+30 > 50

    def test_add_funds_amount_must_be_positive(self):
        goal = Goal.objects.create(user=self.user, name='Phone', target_amount=Decimal('200.00'))
        with self.assertRaises(ValidationError):
            services.add_funds_to_goal(user=self.user, goal=goal, add_amount=Decimal('0.00'))

    def test_allocated_amounts_sum_correctly_against_gullak(self):
        goal1 = Goal.objects.create(user=self.user, name='Phone', target_amount=Decimal('200.00'))
        goal2 = Goal.objects.create(user=self.user, name='Trip', target_amount=Decimal('200.00'))
        services.add_funds_to_goal(user=self.user, goal=goal1, add_amount=Decimal('20.00'))
        services.add_funds_to_goal(user=self.user, goal=goal2, add_amount=Decimal('30.00'))
        self.assertEqual(services.total_allocated(self.user), Decimal('50.00'))

    def test_delete_goal_returns_allocation_to_unallocated(self):
        goal = Goal.objects.create(user=self.user, name='Phone', target_amount=Decimal('200.00'))
        services.add_funds_to_goal(user=self.user, goal=goal, add_amount=Decimal('30.00'))
        services.delete_goal(user=self.user, goal=goal)
        self.assertEqual(services.total_allocated(self.user), Decimal('0.00'))

    def test_goal_marked_achieved_when_fully_funded(self):
        goal = Goal.objects.create(user=self.user, name='Phone', target_amount=Decimal('40.00'))
        services.add_funds_to_goal(user=self.user, goal=goal, add_amount=Decimal('40.00'))
        goal.refresh_from_db()
        self.assertTrue(goal.is_achieved)


class AutoApplyDeductionTests(TestCase):
    """
    V2 Section 5: emergency-unblock overage is now deducted automatically and
    proportionally from underfunded goals, instead of waiting for manual resolution.
    A PendingGoalDeduction row is still created for history, but pre-resolved.
    """
    def setUp(self):
        self.user = make_user()
        self.acc = Account.objects.create(
            user=self.user, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('100.00'), block_balance=Decimal('0.00'),
        )
        wallet_services.block_funds(user=self.user, account=self.acc, amount=Decimal('50.00'))
        self.goal = Goal.objects.create(user=self.user, name='Trip', target_amount=Decimal('200.00'))
        services.add_funds_to_goal(user=self.user, goal=self.goal, add_amount=Decimal('40.00'))
        # Gullak=50, allocated=40, unallocated=10. Unblock 25 -> overage of 15.
        wallet_services.emergency_unblock_funds(user=self.user, account=self.acc, amount=Decimal('25.00'))
        self.record = PendingGoalDeduction.objects.get(user=self.user)

    def test_deduction_record_created_with_correct_overage_and_already_resolved(self):
        self.assertEqual(self.record.amount, Decimal('15.00'))
        self.assertTrue(self.record.resolved)

    def test_goal_allocation_automatically_reduced_by_overage(self):
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.allocated_amount, Decimal('25.00'))  # 40 - 15, applied automatically

    def test_no_action_required_list_pending_deductions_is_empty(self):
        # Since the deduction is auto-applied and pre-resolved, nothing is left for the
        # user to manually resolve — list_pending_deductions() (unresolved only) is empty.
        self.assertEqual(services.list_pending_deductions(self.user).count(), 0)

    def test_informational_notification_created(self):
        from social.models import Notification, NotificationType
        note = Notification.objects.filter(user=self.user, type=NotificationType.GOAL_UNDERFUNDED).first()
        self.assertIsNotNone(note)
        self.assertFalse(note.actionable)
        self.assertIn('Trip', note.body)

    def test_emergency_unblock_within_unallocated_creates_no_deduction_amount(self):
        user2 = make_user('u2@example.com')
        acc2 = Account.objects.create(
            user=user2, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('100.00'), block_balance=Decimal('0.00'),
        )
        wallet_services.block_funds(user=user2, account=acc2, amount=Decimal('50.00'))
        wallet_services.emergency_unblock_funds(user=user2, account=acc2, amount=Decimal('20.00'))
        self.assertEqual(PendingGoalDeduction.objects.filter(user=user2).count(), 0)

    def test_proportional_split_across_multiple_underfunded_goals(self):
        # Fresh user: two goals allocated 40 and 10 (total 50 = whole Gullak).
        user2 = make_user('u3@example.com')
        acc2 = Account.objects.create(
            user=user2, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('100.00'), block_balance=Decimal('0.00'),
        )
        wallet_services.block_funds(user=user2, account=acc2, amount=Decimal('50.00'))
        goal_a = Goal.objects.create(user=user2, name='A', target_amount=Decimal('200.00'))
        goal_b = Goal.objects.create(user=user2, name='B', target_amount=Decimal('200.00'))
        services.add_funds_to_goal(user=user2, goal=goal_a, add_amount=Decimal('40.00'))
        services.add_funds_to_goal(user=user2, goal=goal_b, add_amount=Decimal('10.00'))
        # Unblock all 50 -> overage of 50 (0 unallocated), split 40:10 proportionally.
        wallet_services.emergency_unblock_funds(user=user2, account=acc2, amount=Decimal('50.00'))
        goal_a.refresh_from_db()
        goal_b.refresh_from_db()
        self.assertEqual(goal_a.allocated_amount, Decimal('0.00'))
        self.assertEqual(goal_b.allocated_amount, Decimal('0.00'))


class ManualResolvePendingDeductionTests(TestCase):
    """
    The pre-V2 manual resolution service function is retained (not called by the current
    emergency-unblock flow, which now auto-applies) and remains fully functional, tested
    here directly against the service layer.
    """
    def setUp(self):
        self.user = make_user()
        self.goal = Goal.objects.create(user=self.user, name='Trip', target_amount=Decimal('200.00'))
        self.acc = Account.objects.create(
            user=self.user, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            account_type='UPI', unblock_balance=Decimal('100.00'), block_balance=Decimal('0.00'),
        )
        wallet_services.block_funds(user=self.user, account=self.acc, amount=Decimal('50.00'))
        services.add_funds_to_goal(user=self.user, goal=self.goal, add_amount=Decimal('40.00'))
        self.pending = PendingGoalDeduction.objects.create(user=self.user, amount=Decimal('15.00'))

    def test_resolve_against_single_goal_reduces_its_allocation(self):
        services.resolve_pending_deduction(
            user=self.user, deduction=self.pending,
            allocations=[{'goal_id': self.goal.id, 'amount': Decimal('15.00')}],
        )
        self.goal.refresh_from_db()
        self.pending.refresh_from_db()
        self.assertEqual(self.goal.allocated_amount, Decimal('25.00'))  # 40 - 15
        self.assertTrue(self.pending.resolved)

    def test_resolve_across_multiple_goals_must_sum_exactly(self):
        with self.assertRaises(ValidationError):
            services.resolve_pending_deduction(
                user=self.user, deduction=self.pending,
                allocations=[{'goal_id': self.goal.id, 'amount': Decimal('10.00')}],  # only 10, needs 15
            )

    def test_cannot_deduct_more_than_a_goals_allocation(self):
        with self.assertRaises(ValidationError):
            services.resolve_pending_deduction(
                user=self.user, deduction=self.pending,
                allocations=[{'goal_id': self.goal.id, 'amount': Decimal('999.00')}],
            )

    def test_cannot_resolve_already_resolved_deduction(self):
        services.resolve_pending_deduction(
            user=self.user, deduction=self.pending,
            allocations=[{'goal_id': self.goal.id, 'amount': Decimal('15.00')}],
        )
        with self.assertRaises(ValidationError):
            services.resolve_pending_deduction(
                user=self.user, deduction=self.pending,
                allocations=[{'goal_id': self.goal.id, 'amount': Decimal('0.00')}],
            )


class CommonGoalCreationAPITests(APITestCase):
    """API-level: creating a goal funded from a shared account is only allowed if the
    requester is actually a member of that shared account — prevents fabricating a
    common goal against an account you don't belong to."""

    def setUp(self):
        from social import services as social_services
        self.alice = make_user('alice_g@example.com')
        self.stranger = make_user('stranger_g@example.com')
        self.account = social_services.create_shared_pair_account(creator=self.alice, name='Our Fund')

    def test_member_can_create_common_goal(self):
        self.client.force_authenticate(user=self.alice)
        resp = self.client.post('/api/goals/', {
            'name': 'Trip', 'target_amount': '1000.00', 'funding_shared_account_id': self.account.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['funding_source'], 'shared_account')

    def test_non_member_cannot_create_common_goal_against_others_account(self):
        self.client.force_authenticate(user=self.stranger)
        resp = self.client.post('/api/goals/', {
            'name': 'Trip', 'target_amount': '1000.00', 'funding_shared_account_id': self.account.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_funding_shared_account_id_cannot_be_changed_via_update(self):
        self.client.force_authenticate(user=self.alice)
        create_resp = self.client.post('/api/goals/', {
            'name': 'Personal', 'target_amount': '500.00',
        }, format='json')
        goal_id = create_resp.data['id']
        update_resp = self.client.patch(f'/api/goals/{goal_id}/', {
            'funding_shared_account_id': self.account.id,
        }, format='json')
        self.assertEqual(update_resp.status_code, 200)
        self.assertIsNone(update_resp.data['funding_shared_account_id'])  # unchanged, still personal
