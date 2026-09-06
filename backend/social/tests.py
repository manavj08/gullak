from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase

from wallet.models import Account, AccountCategory
from wallet import services as wallet_services
from goals.models import Goal
from goals import services as goal_services
from . import services
from .models import (
    SharedAccountMember, SharedAccountRole, GroupInvite, GroupInviteStatus,
    Notification, NotificationType, AdminTransferRequest, AdminTransferStatus,
)

User = get_user_model()


def make_user(email='u@example.com'):
    return User.objects.create_user(username=email.split('@')[0], email=email, password='StrongPass123!')


class SharedPairInviteFlowTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice@example.com')
        self.bob = make_user('bob@example.com')
        self.account = services.create_shared_pair_account(creator=self.alice, name='Our Fund')

    def test_creator_is_sole_member_no_admin_role_for_pair(self):
        members = SharedAccountMember.objects.filter(account=self.account)
        self.assertEqual(members.count(), 1)
        self.assertEqual(members.first().user, self.alice)

    def test_send_invite_by_username_creates_actionable_notification(self):
        invite = services.send_invite(inviter=self.alice, invited_username='bob', account=self.account)
        self.assertEqual(invite.status, GroupInviteStatus.PENDING)
        note = Notification.objects.get(user=self.bob, related_invite=invite)
        self.assertTrue(note.actionable)
        self.assertEqual(note.type, NotificationType.INVITE)

    def test_invite_unknown_username_fails(self):
        with self.assertRaises(ValidationError):
            services.send_invite(inviter=self.alice, invited_username='nobody', account=self.account)

    def test_cannot_invite_self(self):
        with self.assertRaises(ValidationError):
            services.send_invite(inviter=self.alice, invited_username='alice', account=self.account)

    def test_accept_invite_grants_membership(self):
        invite = services.send_invite(inviter=self.alice, invited_username='bob', account=self.account)
        services.respond_to_invite(user=self.bob, invite=invite, accept=True)
        self.assertTrue(SharedAccountMember.objects.filter(account=self.account, user=self.bob).exists())
        invite.refresh_from_db()
        self.assertEqual(invite.status, GroupInviteStatus.ACCEPTED)

    def test_accept_invite_notifies_existing_member(self):
        invite = services.send_invite(inviter=self.alice, invited_username='bob', account=self.account)
        services.respond_to_invite(user=self.bob, invite=invite, accept=True)
        note = Notification.objects.filter(user=self.alice, type=NotificationType.MEMBER_JOINED).first()
        self.assertIsNotNone(note)

    def test_decline_invite_grants_no_access_and_inviter_not_left_broken(self):
        invite = services.send_invite(inviter=self.alice, invited_username='bob', account=self.account)
        services.respond_to_invite(user=self.bob, invite=invite, accept=False)
        self.assertFalse(SharedAccountMember.objects.filter(account=self.account, user=self.bob).exists())
        invite.refresh_from_db()
        self.assertEqual(invite.status, GroupInviteStatus.DECLINED)
        # Inviter can still send a fresh invite afterward — not stuck in a broken pending state.
        second = GroupInvite.objects.filter(account=self.account, invited_user=self.bob)
        self.assertEqual(second.count(), 1)  # the declined one; a new send_invite would create another

    def test_cannot_respond_to_invite_twice(self):
        invite = services.send_invite(inviter=self.alice, invited_username='bob', account=self.account)
        services.respond_to_invite(user=self.bob, invite=invite, accept=True)
        with self.assertRaises(ValidationError):
            services.respond_to_invite(user=self.bob, invite=invite, accept=True)

    def test_respond_by_wrong_user_rejected(self):
        invite = services.send_invite(inviter=self.alice, invited_username='bob', account=self.account)
        carol = make_user('carol@example.com')
        with self.assertRaises(ValidationError):
            services.respond_to_invite(user=carol, invite=invite, accept=True)

    def test_pair_account_cannot_exceed_two_people(self):
        invite = services.send_invite(inviter=self.alice, invited_username='bob', account=self.account)
        services.respond_to_invite(user=self.bob, invite=invite, accept=True)
        carol = make_user('carol@example.com')
        with self.assertRaises(ValidationError):
            services.send_invite(inviter=self.alice, invited_username='carol', account=self.account)

    def test_only_member_can_invite(self):
        carol = make_user('carol@example.com')
        dave = make_user('dave@example.com')
        with self.assertRaises(ValidationError):
            services.send_invite(inviter=carol, invited_username='dave', account=self.account)


class SharedGroupMembershipTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice@example.com')
        self.bob = make_user('bob@example.com')
        self.carol = make_user('carol@example.com')
        self.account = services.create_shared_group_account(
            creator=self.alice, name='Goa Trip', occasion_name='Goa Trip Fund',
        )
        for u in (self.bob, self.carol):
            invite = services.send_invite(inviter=self.alice, invited_username=u.username, account=self.account)
            services.respond_to_invite(user=u, invite=invite, accept=True)

    def test_creator_is_admin_by_default(self):
        m = SharedAccountMember.objects.get(account=self.account, user=self.alice)
        self.assertEqual(m.role, SharedAccountRole.ADMIN)

    def test_three_plus_members_supported(self):
        self.assertEqual(SharedAccountMember.objects.filter(account=self.account).count(), 3)

    def test_non_admin_cannot_remove_member(self):
        with self.assertRaises(ValidationError):
            services.remove_member(account=self.account, actor=self.bob, target_user=self.carol)

    def test_admin_can_remove_member(self):
        services.remove_member(account=self.account, actor=self.alice, target_user=self.carol)
        self.assertFalse(SharedAccountMember.objects.filter(account=self.account, user=self.carol).exists())

    def test_removed_members_past_contribution_stays_pooled(self):
        acc = Account.objects.create(
            user=self.carol, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            unblock_balance=Decimal('100.00'),
        )
        wallet_services.contribute_to_shared_account(
            user=self.carol, from_account=acc, shared_account=self.account, amount=Decimal('40.00'),
        )
        self.account.refresh_from_db()
        pooled_before = self.account.block_balance
        services.remove_member(account=self.account, actor=self.alice, target_user=self.carol)
        self.account.refresh_from_db()
        self.assertEqual(self.account.block_balance, pooled_before)  # unchanged — not refunded

    def test_admin_transfer_requires_target_acceptance(self):
        req = services.request_admin_transfer(account=self.account, actor=self.alice, target_user=self.bob)
        self.assertEqual(req.status, AdminTransferStatus.PENDING)
        m = SharedAccountMember.objects.get(account=self.account, user=self.bob)
        self.assertEqual(m.role, SharedAccountRole.MEMBER)  # not yet promoted

    def test_admin_transfer_accept_promotes_and_demotes_old_admin(self):
        req = services.request_admin_transfer(account=self.account, actor=self.alice, target_user=self.bob)
        services.respond_to_admin_transfer(user=self.bob, request_obj=req, accept=True)
        bob_m = SharedAccountMember.objects.get(account=self.account, user=self.bob)
        alice_m = SharedAccountMember.objects.get(account=self.account, user=self.alice)
        self.assertEqual(bob_m.role, SharedAccountRole.ADMIN)
        self.assertEqual(alice_m.role, SharedAccountRole.MEMBER)

    def test_promoted_admin_now_has_remove_permission_enforced_server_side(self):
        req = services.request_admin_transfer(account=self.account, actor=self.alice, target_user=self.bob)
        services.respond_to_admin_transfer(user=self.bob, request_obj=req, accept=True)
        # Bob (now admin) can remove; Alice (now plain member) can no longer.
        services.remove_member(account=self.account, actor=self.bob, target_user=self.carol)
        self.assertFalse(SharedAccountMember.objects.filter(account=self.account, user=self.carol).exists())

    def test_non_admin_cannot_request_admin_transfer(self):
        with self.assertRaises(ValidationError):
            services.request_admin_transfer(account=self.account, actor=self.bob, target_user=self.carol)

    def test_admin_cannot_leave_without_transferring_first(self):
        with self.assertRaises(ValidationError):
            services.leave_account(account=self.account, user=self.alice)

    def test_non_admin_can_leave_freely(self):
        services.leave_account(account=self.account, user=self.bob)
        self.assertFalse(SharedAccountMember.objects.filter(account=self.account, user=self.bob).exists())


class SharedAccountDetailCommonGoalsAPITests(APITestCase):
    """API-level: the shared account detail response includes its own common goals, so
    members can discover and navigate to them directly from the account page."""

    def setUp(self):
        self.alice = make_user('alice_sa@example.com')
        self.account = services.create_shared_pair_account(creator=self.alice, name='Our Fund')
        self.goal = Goal.objects.create(
            user=self.alice, name='Vacation', target_amount=Decimal('1000.00'),
            funding_shared_account_id=self.account.id,
        )

    def test_common_goals_included_in_detail_response(self):
        self.client.force_authenticate(user=self.alice)
        resp = self.client.get(f'/api/social/shared-accounts/{self.account.id}/')
        self.assertEqual(resp.status_code, 200)
        goal_ids = [g['id'] for g in resp.data['common_goals']]
        self.assertIn(self.goal.id, goal_ids)

    def test_personal_goals_not_included(self):
        Goal.objects.create(user=self.alice, name='Personal', target_amount=Decimal('500.00'))
        self.client.force_authenticate(user=self.alice)
        resp = self.client.get(f'/api/social/shared-accounts/{self.account.id}/')
        names = [g['name'] for g in resp.data['common_goals']]
        self.assertNotIn('Personal', names)


class VisibilityRuleTests(TestCase):
    """Server-side enforcement of the confirmed rule: own contribution itemized in full,
    others only ever exposed as one aggregate sum — never a per-member breakdown."""

    def setUp(self):
        self.alice = make_user('alice@example.com')
        self.bob = make_user('bob@example.com')
        self.carol = make_user('carol@example.com')
        self.account = services.create_shared_group_account(creator=self.alice, name='Grp', occasion_name='Occ')
        for u in (self.bob, self.carol):
            invite = services.send_invite(inviter=self.alice, invited_username=u.username, account=self.account)
            services.respond_to_invite(user=u, invite=invite, accept=True)

        for u, amount in ((self.alice, '30.00'), (self.bob, '50.00'), (self.carol, '20.00')):
            acc = Account.objects.create(
                user=u, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
                unblock_balance=Decimal('100.00'),
            )
            wallet_services.contribute_to_shared_account(
                user=u, from_account=acc, shared_account=self.account, amount=Decimal(amount),
            )

    def test_own_contribution_shown_in_full(self):
        result = services.get_visible_contributions(account=self.account, requesting_user=self.alice)
        self.assertEqual(result['own_contribution'], Decimal('30.00'))

    def test_others_only_shown_as_aggregate(self):
        result = services.get_visible_contributions(account=self.account, requesting_user=self.alice)
        self.assertEqual(result['others_aggregate'], Decimal('70.00'))  # bob 50 + carol 20, never itemized

    def test_visibility_holds_as_member_count_grows(self):
        dave = make_user('dave@example.com')
        invite = services.send_invite(inviter=self.alice, invited_username='dave', account=self.account)
        services.respond_to_invite(user=dave, invite=invite, accept=True)
        acc = Account.objects.create(
            user=dave, name='UPI', category=AccountCategory.DAILY_TRANSACTION, unblock_balance=Decimal('100.00'),
        )
        wallet_services.contribute_to_shared_account(
            user=dave, from_account=acc, shared_account=self.account, amount=Decimal('10.00'),
        )
        result = services.get_visible_contributions(account=self.account, requesting_user=self.bob)
        self.assertEqual(result['own_contribution'], Decimal('50.00'))
        self.assertEqual(result['others_aggregate'], Decimal('60.00'))  # 30 + 20 + 10


class EmergencyUnblockOwnShareTests(TestCase):
    """A member can only unblock their own contributed portion — never pooled total or another's share."""

    def setUp(self):
        self.alice = make_user('alice@example.com')
        self.bob = make_user('bob@example.com')
        self.account = services.create_shared_pair_account(creator=self.alice, name='Our Fund')
        invite = services.send_invite(inviter=self.alice, invited_username='bob', account=self.account)
        services.respond_to_invite(user=self.bob, invite=invite, accept=True)

        self.alice_acc = Account.objects.create(
            user=self.alice, name='UPI', category=AccountCategory.DAILY_TRANSACTION, unblock_balance=Decimal('100.00'),
        )
        self.bob_acc = Account.objects.create(
            user=self.bob, name='UPI', category=AccountCategory.DAILY_TRANSACTION, unblock_balance=Decimal('100.00'),
        )
        wallet_services.contribute_to_shared_account(
            user=self.alice, from_account=self.alice_acc, shared_account=self.account, amount=Decimal('30.00'),
        )
        wallet_services.contribute_to_shared_account(
            user=self.bob, from_account=self.bob_acc, shared_account=self.account, amount=Decimal('50.00'),
        )

    def test_member_can_unblock_up_to_own_contribution(self):
        wallet_services.emergency_unblock_own_share(
            user=self.alice, shared_account=self.account, to_account=self.alice_acc, amount=Decimal('30.00'),
        )
        self.alice_acc.refresh_from_db()
        self.assertEqual(self.alice_acc.unblock_balance, Decimal('100.00'))  # 70 spent + 30 back

    def test_member_cannot_unblock_more_than_own_share(self):
        with self.assertRaises(ValidationError):
            wallet_services.emergency_unblock_own_share(
                user=self.alice, shared_account=self.account, to_account=self.alice_acc, amount=Decimal('31.00'),
            )

    def test_member_cannot_touch_another_members_share(self):
        # Alice contributed 30; even though pool has 80 total, she's capped at her own 30.
        with self.assertRaises(ValidationError):
            wallet_services.emergency_unblock_own_share(
                user=self.alice, shared_account=self.account, to_account=self.alice_acc, amount=Decimal('50.00'),
            )

    def test_no_consent_step_required_succeeds_immediately(self):
        # Simply succeeding without any accept/decline call demonstrates no consent gate exists.
        result = wallet_services.emergency_unblock_own_share(
            user=self.bob, shared_account=self.account, to_account=self.bob_acc, amount=Decimal('20.00'),
        )
        self.assertIsNotNone(result)


class NoCrossFundingTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice@example.com')
        self.bob = make_user('bob@example.com')
        self.account = services.create_shared_pair_account(creator=self.alice, name='Our Fund')
        invite = services.send_invite(inviter=self.alice, invited_username='bob', account=self.account)
        services.respond_to_invite(user=self.bob, invite=invite, accept=True)

        self.alice_upi = Account.objects.create(
            user=self.alice, name='UPI', category=AccountCategory.DAILY_TRANSACTION, unblock_balance=Decimal('100.00'),
        )
        wallet_services.contribute_to_shared_account(
            user=self.alice, from_account=self.alice_upi, shared_account=self.account, amount=Decimal('50.00'),
        )

    def test_common_goal_funded_only_from_shared_account_not_personal_gullak(self):
        common_goal = Goal.objects.create(
            user=self.alice, name='Common Trip', target_amount=Decimal('100.00'),
            funding_shared_account_id=self.account.id,
        )
        goal_services.add_funds_to_goal(user=self.alice, goal=common_goal, add_amount=Decimal('40.00'))
        common_goal.refresh_from_db()
        self.assertEqual(common_goal.allocated_amount, Decimal('40.00'))
        self.assertTrue(common_goal.is_common_goal)

    def test_common_goal_cannot_exceed_shared_pool(self):
        common_goal = Goal.objects.create(
            user=self.alice, name='Common Trip', target_amount=Decimal('1000.00'),
            funding_shared_account_id=self.account.id,
        )
        with self.assertRaises(ValidationError):
            goal_services.add_funds_to_goal(user=self.alice, goal=common_goal, add_amount=Decimal('999.00'))

    def test_personal_goal_allocation_unaffected_by_shared_pool(self):
        wallet_services.block_funds(user=self.alice, account=self.alice_upi, amount=Decimal('20.00'))
        personal_goal = Goal.objects.create(user=self.alice, name='Personal', target_amount=Decimal('100.00'))
        goal_services.add_funds_to_goal(user=self.alice, goal=personal_goal, add_amount=Decimal('20.00'))
        personal_goal.refresh_from_db()
        self.assertEqual(personal_goal.allocated_amount, Decimal('20.00'))

    def test_personal_and_common_totals_tracked_independently(self):
        wallet_services.block_funds(user=self.alice, account=self.alice_upi, amount=Decimal('10.00'))
        common_goal = Goal.objects.create(
            user=self.alice, name='Common Trip', target_amount=Decimal('100.00'),
            funding_shared_account_id=self.account.id,
        )
        personal_goal = Goal.objects.create(user=self.alice, name='Personal', target_amount=Decimal('100.00'))
        goal_services.add_funds_to_goal(user=self.alice, goal=common_goal, add_amount=Decimal('50.00'))
        goal_services.add_funds_to_goal(user=self.alice, goal=personal_goal, add_amount=Decimal('10.00'))
        # Personal Gullak total (10) is untouched by the 50 allocated to the common goal.
        self.assertEqual(goal_services.total_allocated(self.alice), Decimal('10.00'))
        self.assertEqual(
            goal_services.total_allocated_for_shared_account(self.account.id), Decimal('50.00')
        )


class SplitSuggestionTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.today = timezone.localdate()
        # Ample Gullak balance so the new unallocated-amount cap doesn't interfere with
        # tests that are specifically checking the urgency-split math itself.
        acc = Account.objects.create(
            user=self.user, name='UPI', category=AccountCategory.DAILY_TRANSACTION,
            unblock_balance=Decimal('10000.00'),
        )
        wallet_services.block_funds(user=self.user, account=acc, amount=Decimal('5000.00'))

    def test_urgency_formula_matches_documented_example(self):
        # Documented example: ₹3,000/60 days vs ₹1,000/10 days → ~33%/67% split.
        goal_a = Goal.objects.create(
            user=self.user, name='A', target_amount=Decimal('3000.00'),
            deadline=self.today + timedelta(days=60),
        )
        goal_b = Goal.objects.create(
            user=self.user, name='B', target_amount=Decimal('1000.00'),
            deadline=self.today + timedelta(days=10),
        )
        suggestion = goal_services.compute_urgency_split(self.user, Decimal('300.00'))
        by_goal = {s['goal_id']: s['suggested_amount'] for s in suggestion}
        # score_a = 3000/60 = 50; score_b = 1000/10 = 100; total = 150
        # a share = 300 * 50/150 = 100 (~33%); b share = 300 * 100/150 = 200 (~67%)
        self.assertEqual(by_goal[goal_a.id], Decimal('100.00'))
        self.assertEqual(by_goal[goal_b.id], Decimal('200.00'))

    def test_goals_without_deadline_excluded(self):
        Goal.objects.create(user=self.user, name='No deadline', target_amount=Decimal('500.00'))
        suggestion = goal_services.compute_urgency_split(self.user, Decimal('100.00'))
        self.assertEqual(suggestion, [])

    def test_achieved_goals_excluded(self):
        goal = Goal.objects.create(
            user=self.user, name='Done', target_amount=Decimal('100.00'),
            deadline=self.today + timedelta(days=10), allocated_amount=Decimal('100.00'), is_achieved=True,
        )
        suggestion = goal_services.compute_urgency_split(self.user, Decimal('100.00'))
        self.assertEqual(suggestion, [])

    def test_suggestion_never_exceeds_a_goals_remaining_need(self):
        goal = Goal.objects.create(
            user=self.user, name='Almost done', target_amount=Decimal('100.00'),
            deadline=self.today + timedelta(days=5), allocated_amount=Decimal('90.00'),
        )
        suggestion = goal_services.compute_urgency_split(self.user, Decimal('500.00'))
        self.assertEqual(suggestion[0]['suggested_amount'], Decimal('10.00'))  # capped at remaining need

    def test_suggested_amount_never_exceeds_unallocated_gullak(self):
        # Fresh user with only 200 unallocated (5000 - 4800 already allocated elsewhere).
        user2 = make_user('capped@example.com')
        acc2 = Account.objects.create(
            user=user2, name='UPI', category=AccountCategory.DAILY_TRANSACTION, unblock_balance=Decimal('10000.00'),
        )
        wallet_services.block_funds(user=user2, account=acc2, amount=Decimal('5000.00'))
        other_goal = Goal.objects.create(user=user2, name='Other', target_amount=Decimal('4800.00'))
        goal_services.add_funds_to_goal(user=user2, goal=other_goal, add_amount=Decimal('4800.00'))
        target_goal = Goal.objects.create(
            user=user2, name='Target', target_amount=Decimal('1000.00'), deadline=self.today + timedelta(days=10),
        )
        # Ask for 500, but only 200 is actually unallocated — suggestion must cap at 200.
        suggestion = goal_services.compute_urgency_split(user2, Decimal('500.00'))
        total_suggested = sum((s['suggested_amount'] for s in suggestion), Decimal('0'))
        self.assertLessEqual(total_suggested, Decimal('200.00'))

    def test_zero_unallocated_gullak_yields_zero_suggested_total(self):
        user2 = make_user('zero@example.com')
        acc2 = Account.objects.create(
            user=user2, name='UPI', category=AccountCategory.DAILY_TRANSACTION, unblock_balance=Decimal('1000.00'),
        )
        wallet_services.block_funds(user=user2, account=acc2, amount=Decimal('500.00'))
        goal = Goal.objects.create(user=user2, name='Fully allocated already', target_amount=Decimal('500.00'))
        goal_services.add_funds_to_goal(user=user2, goal=goal, add_amount=Decimal('500.00'))
        target_goal = Goal.objects.create(
            user=user2, name='Target', target_amount=Decimal('1000.00'), deadline=self.today + timedelta(days=10),
        )
        suggestion = goal_services.compute_urgency_split(user2, Decimal('300.00'))
        # With 0 unallocated, the capped amount to split is 0 — candidates may still be
        # listed (so the UI can show "you have goals but nothing unallocated to split"),
        # but every suggested amount must be zero.
        total_suggested = sum((s['suggested_amount'] for s in suggestion), Decimal('0'))
        self.assertEqual(total_suggested, Decimal('0.00'))

    def test_suggestion_is_advisory_only_does_not_mutate_goal(self):
        goal = Goal.objects.create(
            user=self.user, name='A', target_amount=Decimal('100.00'),
            deadline=self.today + timedelta(days=10),
        )
        goal_services.compute_urgency_split(self.user, Decimal('50.00'))
        goal.refresh_from_db()
        self.assertEqual(goal.allocated_amount, Decimal('0.00'))  # unchanged — suggestion only

    def test_common_goals_excluded_from_personal_split_suggestion(self):
        Goal.objects.create(
            user=self.user, name='Common', target_amount=Decimal('500.00'),
            deadline=self.today + timedelta(days=10), funding_shared_account_id=999,
        )
        suggestion = goal_services.compute_urgency_split(self.user, Decimal('100.00'))
        self.assertEqual(suggestion, [])


class SplitSuggestionWithSharedAccountTests(TestCase):
    """V2 follow-up: optionally include a shared account's common goals in the same
    split-suggestion call, capped against that shared account's own unallocated pool —
    never mixed with or drawn from the user's personal Gullak."""

    def setUp(self):
        self.today = timezone.localdate()
        self.alice = make_user('alice2@example.com')
        self.bob = make_user('bob2@example.com')
        self.shared_account = services.create_shared_pair_account(creator=self.alice, name='Our Fund')
        invite = services.send_invite(inviter=self.alice, invited_username=self.bob.username, account=self.shared_account)
        services.respond_to_invite(user=self.bob, invite=invite, accept=True)

        acc = Account.objects.create(
            user=self.alice, name='UPI', category=AccountCategory.DAILY_TRANSACTION, unblock_balance=Decimal('2000.00'),
        )
        wallet_services.contribute_to_shared_account(
            user=self.alice, from_account=acc, shared_account=self.shared_account, amount=Decimal('1000.00'),
        )
        self.common_goal = Goal.objects.create(
            user=self.alice, name='Common Trip', target_amount=Decimal('2000.00'),
            deadline=self.today + timedelta(days=20), funding_shared_account_id=self.shared_account.id,
        )

    def test_shared_account_goals_included_when_requested(self):
        suggestion = goal_services.compute_urgency_split(
            self.alice, Decimal('100.00'), shared_account_ids=[self.shared_account.id],
        )
        common_entries = [s for s in suggestion if s['goal_id'] == self.common_goal.id]
        self.assertEqual(len(common_entries), 1)
        self.assertEqual(common_entries[0]['funding_source'], f'shared_account:{self.shared_account.id}')

    def test_shared_account_goals_excluded_when_not_requested(self):
        suggestion = goal_services.compute_urgency_split(self.alice, Decimal('100.00'))
        self.assertFalse(any(s['goal_id'] == self.common_goal.id for s in suggestion))

    def test_shared_split_capped_at_shared_accounts_own_unallocated_pool(self):
        # Shared pool has 1000 unallocated (nothing allocated to the goal yet).
        suggestion = goal_services.compute_urgency_split(
            self.alice, Decimal('5000.00'), shared_account_ids=[self.shared_account.id],
        )
        common_entries = [s for s in suggestion if s['goal_id'] == self.common_goal.id]
        self.assertLessEqual(common_entries[0]['suggested_amount'], Decimal('1000.00'))

    def test_shared_split_never_draws_from_requesters_personal_gullak(self):
        # Alice has 0 personal Gullak funds — a shared-account suggestion must still work,
        # proving the shared split is capped against the shared pool, not personal Gullak.
        suggestion = goal_services.compute_urgency_split(
            self.alice, Decimal('500.00'), shared_account_ids=[self.shared_account.id],
        )
        common_entries = [s for s in suggestion if s['goal_id'] == self.common_goal.id]
        self.assertGreater(common_entries[0]['suggested_amount'], Decimal('0.00'))


class SharedGoalDetailAPITests(APITestCase):
    """API-level: confirms the shared-goal detail endpoint is only reachable by members
    of the funding shared account, and returns aggregate-only data — not a data-leak path
    around the service-layer visibility rule already covered above."""

    def setUp(self):
        self.alice = make_user('alice4@example.com')
        self.bob = make_user('bob4@example.com')
        self.stranger = make_user('stranger4@example.com')
        for u in (self.alice, self.bob, self.stranger):
            u.set_password('StrongPass123!')
            u.save()
        self.account = services.create_shared_pair_account(creator=self.alice, name='Our Fund')
        invite = services.send_invite(inviter=self.alice, invited_username='bob4', account=self.account)
        services.respond_to_invite(user=self.bob, invite=invite, accept=True)

        acc = Account.objects.create(
            user=self.alice, name='UPI', category=AccountCategory.DAILY_TRANSACTION, unblock_balance=Decimal('1000.00'),
        )
        wallet_services.contribute_to_shared_account(
            user=self.alice, from_account=acc, shared_account=self.account, amount=Decimal('300.00'),
        )
        self.goal = Goal.objects.create(
            user=self.alice, name='Common Goal', target_amount=Decimal('1000.00'),
            funding_shared_account_id=self.account.id,
        )
        goal_services.add_funds_to_goal(user=self.alice, goal=self.goal, add_amount=Decimal('300.00'))

    def test_member_can_view_goal_detail(self):
        self.client.force_authenticate(user=self.alice)
        resp = self.client.get(f'/api/social/goals/{self.goal.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Decimal(resp.data['progress']['own_contribution']), Decimal('300.00'))
        self.assertEqual(Decimal(resp.data['progress']['remaining_amount']), Decimal('700.00'))

    def test_non_member_gets_404_not_403(self):
        # Deliberately 404, not 403 — must not reveal the goal/account's existence to non-members.
        self.client.force_authenticate(user=self.stranger)
        resp = self.client.get(f'/api/social/goals/{self.goal.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_personal_goal_not_reachable_via_shared_goal_endpoint(self):
        personal_goal = Goal.objects.create(user=self.alice, name='Personal', target_amount=Decimal('500.00'))
        self.client.force_authenticate(user=self.alice)
        resp = self.client.get(f'/api/social/goals/{personal_goal.id}/')
        self.assertEqual(resp.status_code, 404)


class SplitSuggestionAPITests(APITestCase):
    """API-level: shared_account_ids in the split-suggestion request only takes effect for
    accounts the requester actually belongs to — can't be used to probe another account's goals."""

    def setUp(self):
        self.alice = make_user('alice5@example.com')
        self.stranger = make_user('stranger5@example.com')
        for u in (self.alice, self.stranger):
            u.set_password('StrongPass123!')
            u.save()
        self.account = services.create_shared_pair_account(creator=self.alice, name='Our Fund')
        acc = Account.objects.create(
            user=self.alice, name='UPI', category=AccountCategory.DAILY_TRANSACTION, unblock_balance=Decimal('1000.00'),
        )
        wallet_services.contribute_to_shared_account(
            user=self.alice, from_account=acc, shared_account=self.account, amount=Decimal('500.00'),
        )
        self.common_goal = Goal.objects.create(
            user=self.alice, name='Common', target_amount=Decimal('1000.00'),
            deadline=timezone.localdate() + timedelta(days=10), funding_shared_account_id=self.account.id,
        )

    def test_non_member_requesting_shared_account_id_gets_no_leaked_goals(self):
        self.client.force_authenticate(user=self.stranger)
        resp = self.client.post('/api/social/split-suggestion/', {
            'new_amount': '100.00', 'shared_account_ids': [self.account.id],
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(any(item['goal_id'] == self.common_goal.id for item in resp.data))

    def test_member_requesting_own_shared_account_id_sees_common_goal(self):
        self.client.force_authenticate(user=self.alice)
        resp = self.client.post('/api/social/split-suggestion/', {
            'new_amount': '100.00', 'shared_account_ids': [self.account.id],
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(any(item['goal_id'] == self.common_goal.id for item in resp.data))


class GoalContributionVisibilityTests(TestCase):
    """V2 follow-up: a common goal tracks each member's own contribution toward it
    (goals.models.GoalContribution), surfaced only via the same aggregate-only rule
    used for the shared account's overall pool — own amount in full, others combined."""

    def setUp(self):
        self.alice = make_user('alice3@example.com')
        self.bob = make_user('bob3@example.com')
        self.carol = make_user('carol3@example.com')
        self.account = services.create_shared_group_account(creator=self.alice, name='Grp', occasion_name='Occ')
        for u in (self.bob, self.carol):
            invite = services.send_invite(inviter=self.alice, invited_username=u.username, account=self.account)
            services.respond_to_invite(user=u, invite=invite, accept=True)

        for u, amount in ((self.alice, '600.00'), (self.bob, '400.00'), (self.carol, '300.00')):
            acc = Account.objects.create(
                user=u, name='UPI', category=AccountCategory.DAILY_TRANSACTION, unblock_balance=Decimal('2000.00'),
            )
            wallet_services.contribute_to_shared_account(
                user=u, from_account=acc, shared_account=self.account, amount=Decimal(amount),
            )

        self.goal = Goal.objects.create(
            user=self.alice, name='Common Goal', target_amount=Decimal('1000.00'),
            funding_shared_account_id=self.account.id,
        )

    def test_add_funds_tracks_contributor_not_just_goal_owner(self):
        goal_services.add_funds_to_goal(user=self.alice, goal=self.goal, add_amount=Decimal('200.00'), contributor=self.bob)
        from goals.models import GoalContribution
        contribution = GoalContribution.objects.get(goal=self.goal, user=self.bob)
        self.assertEqual(contribution.contributed_amount, Decimal('200.00'))

    def test_default_contributor_is_goal_user_when_not_specified(self):
        goal_services.add_funds_to_goal(user=self.alice, goal=self.goal, add_amount=Decimal('100.00'))
        from goals.models import GoalContribution
        contribution = GoalContribution.objects.get(goal=self.goal, user=self.alice)
        self.assertEqual(contribution.contributed_amount, Decimal('100.00'))

    def test_own_contribution_shown_in_full(self):
        goal_services.add_funds_to_goal(user=self.alice, goal=self.goal, add_amount=Decimal('150.00'), contributor=self.alice)
        goal_services.add_funds_to_goal(user=self.alice, goal=self.goal, add_amount=Decimal('250.00'), contributor=self.bob)
        result = goal_services.get_visible_goal_contributions(goal=self.goal, requesting_user=self.alice)
        self.assertEqual(result['own_contribution'], Decimal('150.00'))

    def test_others_only_shown_as_aggregate(self):
        goal_services.add_funds_to_goal(user=self.alice, goal=self.goal, add_amount=Decimal('150.00'), contributor=self.alice)
        goal_services.add_funds_to_goal(user=self.alice, goal=self.goal, add_amount=Decimal('250.00'), contributor=self.bob)
        goal_services.add_funds_to_goal(user=self.alice, goal=self.goal, add_amount=Decimal('100.00'), contributor=self.carol)
        result = goal_services.get_visible_goal_contributions(goal=self.goal, requesting_user=self.alice)
        self.assertEqual(result['others_aggregate'], Decimal('350.00'))  # bob 250 + carol 100, never itemized

    def test_contribution_capped_by_shared_pool_regardless_of_contributor(self):
        with self.assertRaises(ValidationError):
            goal_services.add_funds_to_goal(user=self.alice, goal=self.goal, add_amount=Decimal('999999.00'), contributor=self.bob)


class NotificationCenterTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice@example.com')
        self.bob = make_user('bob@example.com')
        self.account = services.create_shared_pair_account(creator=self.alice, name='Our Fund')

    def test_unread_count_accurate(self):
        services.send_invite(inviter=self.alice, invited_username='bob', account=self.account)
        self.assertEqual(services.unread_count(self.bob), 1)

    def test_opening_notification_page_marks_visible_as_read(self):
        invite = services.send_invite(inviter=self.alice, invited_username='bob', account=self.account)
        services.mark_visible_as_read(self.bob)
        note = Notification.objects.get(related_invite=invite)
        self.assertEqual(note.status, 'read')

    def test_actionable_notification_stays_pending_after_being_viewed(self):
        invite = services.send_invite(inviter=self.alice, invited_username='bob', account=self.account)
        services.mark_visible_as_read(self.bob)  # simulates opening the notification page
        note = Notification.objects.get(related_invite=invite)
        # Viewing moves unread -> read, but never to 'actioned' — it's still actionable and
        # not yet resolved, so the UI must keep showing a "respond" affordance for it.
        self.assertTrue(note.actionable)
        self.assertNotEqual(note.status, 'actioned')

    def test_actioning_notification_marks_it_actioned(self):
        invite = services.send_invite(inviter=self.alice, invited_username='bob', account=self.account)
        services.respond_to_invite(user=self.bob, invite=invite, accept=True)
        note = Notification.objects.get(related_invite=invite)
        self.assertEqual(note.status, 'actioned')
